from __future__ import annotations

import concurrent.futures as cf
import logging
from typing import Callable, TypeVar

from pydantic import BaseModel, Field

from rivalradar.llm.structured import StructuredCallError, structured_call
from rivalradar.schema.models import (
    ComparisonRow, CompetitorAnalysis, CompetitorProfile, CONTROLLED_DIMENSIONS,
    Evidence, FeatureItem, PricingModel, SWOT, UserPersona,
)

logger = logging.getLogger(__name__)

_X = TypeVar("_X")

# 分析层并发上限。真 run 钓出:analyze 全串行(3 竞品 × 4 抽取 + 1 对比 = 13 次
# 顺序 LLM 调用)单轮 ~460s,3 轮重试 ~22min,真 run 无法 live demo。抽取是
# IO-bound(等 Doubao HTTP),线程池足够;client(OpenAI SDK)线程安全。
# 双层独立线程池(竞品间 + 单竞品 4 抽取)。峰值线程 = 外层竞品并发 × 内层抽取并发
# = 4 × 4 = 16 的天然上界:即使竞品很多,外层也只 4 并发,内层最多 4×4=16,
# 自动防把上游限流。两层必须是独立池——共享一个 executor 嵌套 submit-and-wait
# 会经典死锁(外层 worker 占槽等内层任务,内层抢不到槽)。
_MAX_COMPETITOR_WORKERS = 4   # 竞品间并行度
_MAX_EXTRACT_WORKERS = 4      # 单竞品 4 抽取并行度(features/pricing/personas/swot)

# 抽取项中文名(增量进度文案用):真跑 analyze ~174s 是最长静默段,每项抽取完成 emit
# 一次 → 前端执行流"竞品·维度"逐项亮起,等待过程看得到中间步骤(不再 174s 干挂)。
_EXTRACT_ZH = {"features": "功能", "pricing": "定价", "personas": "用户画像", "swot": "SWOT"}


def _safe_extract(
    label: str, competitor: str, fn: Callable[[], _X], default: _X,
    *, sink: list[str] | None = None,
) -> _X:
    """单项 profile 抽取的优雅降级:structured_call 封顶失败(真 run 钓出——竞品功能多时
    LLM 输出超 max_tokens 被截断 → Unterminated JSON → StructuredCallError)不应杀死整个
    run。这里记日志 + 把降级 label 记入 sink(供 analyze_node 置 run 级 degraded,保证
    「降级必可见」契约——否则整竞品 profile 半瘫却 status=done/degraded=False,用户零警示),
    再返空默认让该竞品其余抽取与下游决策照常产出。

    sink:降级事件汇聚处(`{competitor}.{label}`)。None = 不汇聚(向后兼容直接调用/单测)。
    注意:被降级的 profile 项(features/personas/swot/pricing)**不进 check_entailment**(qc_node
    用 comparison_only=True 只严判对比矩阵 cell);它们仍受 check_traceability 全量机械门约束
    (空引用/悬空 id 仍被抓)。所以降级项的可见性靠 sink→degraded 横幅,而非 entailment。

    捕获范围(ship outside-voice C2):catch **任何** 异常,不只 StructuredCallError——本函数
    存在的唯一理由就是"单项抽取失败不杀整 run",只兜截断这一种太窄:pydantic 构造异常 /
    未被 structured_call 包裹的 openai 异常类 / 大响应 MemoryError 等都该降级该项而非让一个
    竞品的一项抽取拖垮整轮(并行后还会丢弃已完成的兄弟抽取结果)。logger 只 type(e).__name__
    (不 exc_info 全 traceback 给 server log;sink 只记 label,绝不把模型/异常文本带出)。"""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — 单项抽取任何失败都降级该项,绝不杀整 run(本函数唯一职责)
        logger.warning("analyze_competitor[%s] %s 抽取降级(%s,返空默认)",
                       competitor, label, type(e).__name__, exc_info=True)
        if sink is not None:
            sink.append(f"{competitor}.{label}")
        return default


# structured_call 返回单个 BaseModel;抽取 list 用 wrapper 模型
class FeatureExtraction(BaseModel):
    items: list[FeatureItem] = Field(default_factory=list)


class PersonaExtraction(BaseModel):
    personas: list[UserPersona] = Field(default_factory=list)


class ComparisonExtraction(BaseModel):
    rows: list[ComparisonRow] = Field(default_factory=list)


def evidence_for(
    evidence: list[Evidence], competitor: str, *, dimension: str | None = None
) -> list[Evidence]:
    """过滤出某竞品(可选某维度)的证据,缩小喂给 LLM 的上下文。"""
    return [
        e for e in evidence
        if e.competitor == competitor and (dimension is None or e.dimension == dimension)
    ]


def build_evidence_block(evidence: list[Evidence]) -> str:
    """把证据编号成清单注入 prompt,标出 evidence_id 供模型在 evidence_refs 里引用。"""
    lines = []
    for e in evidence:
        snippet = (e.content or "")[:1200]
        lines.append(f"[evidence_id={e.id}] ({e.source_title} | {e.source_url})\n{snippet}")
    return "\n\n".join(lines)


_REFS_RULE = (
    "只依据下面证据作答,不得编造。每条结论必须挂 evidence_refs,其中 evidence_id "
    "只能取自给定证据的 evidence_id,quote 为被引的原句。无证据支撑的结论不要输出。\n"
    "**粒度不得超过证据(真 run 钓出的过度拆解硬纪律)**:只输出证据原文明确点名的内容,"
    "严禁把证据里的大类/概称拆成证据未逐一点名的子项。反例(一律禁止):证据只写"
    "「资源分配」→ 不得输出「人员分配」「预算控制」等未点名子功能;证据只写「数据分析」→ "
    "不得拆成「绩效分析」「风险分析」;证据只写「团队协作」→ 不得拆成「文件管理」等细项。"
    "列举多项(如对比 cell 罗列能力清单)时,**每一项都必须能在被引证据原句里找到对应字样**,"
    "找不到对应字样的项一律删掉。宁可粗粒度但每条都站得住,不要细粒度而被质检判为不支撑。"
)


def extract_features(evidence: list[Evidence], competitor: str, *, client, model) -> list[FeatureItem]:
    """从证据抽取竞品功能项,每条挂 evidence_refs。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。抽取其功能项(用 parent_id 表父子层级,"
             f"category 取功能类别)。\n\n证据:\n{block}"}]
    return structured_call(FeatureExtraction, msgs, client=client, model=model).items


def extract_pricing(evidence: list[Evidence], competitor: str, *, client, model) -> PricingModel:
    """从证据抽取竞品定价模型。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。抽取其定价模型(model_type 与各 tier)。\n\n证据:\n{block}"}]
    return structured_call(PricingModel, msgs, client=client, model=model)


def extract_personas(evidence: list[Evidence], competitor: str, *, client, model) -> list[UserPersona]:
    """从证据抽取竞品用户画像。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。从公开用户评价抽取用户画像(segment/needs/"
             f"pain_points/praise)。\n\n证据:\n{block}"}]
    return structured_call(PersonaExtraction, msgs, client=client, model=model).personas


def extract_swot(evidence: list[Evidence], competitor: str, *, client, model) -> SWOT:
    """从证据抽取竞品 SWOT(每点挂 evidence_refs)。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。基于证据给出 SWOT(每点挂 evidence_refs)。\n\n证据:\n{block}"}]
    return structured_call(SWOT, msgs, client=client, model=model)


def analyze_competitor(
    evidence: list[Evidence], competitor: str, *, degraded_sink: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None, client, model,
) -> CompetitorProfile:
    """对单个竞品做四项抽取并拼成 CompetitorProfile。

    degraded_sink:任一项抽取降级时,label 记入此 list(透传给 _safe_extract)。None =
    不汇聚(向后兼容)。pricing 降级占位用中性的 "未知"(不是英文 unknown,也不当错误码——
    错误信道职责交给 degraded_sink→横幅,model_type 保持纯产品数据字段语言一致)。"""
    ev = evidence_for(evidence, competitor)  # 已按竞品过滤;下面按维度取子集,缺则回退全量
    feat_ev = evidence_for(ev, competitor, dimension="core_workflows") or ev
    price_ev = evidence_for(ev, competitor, dimension="pricing") or ev
    pers_ev = evidence_for(ev, competitor, dimension="review_sentiment") or ev
    # 4 项抽取并行(各自 _safe_extract 内已优雅降级 + sink.append CPython 原子)。
    # 串行时 4 次顺序等 HTTP;并行后墙钟 ≈ 最慢一项。client 线程安全。
    thunks = {
        "features": lambda: _safe_extract(
            "features", competitor,
            lambda: extract_features(feat_ev, competitor, client=client, model=model),
            [], sink=degraded_sink),
        "pricing": lambda: _safe_extract(
            "pricing", competitor,
            lambda: extract_pricing(price_ev, competitor, client=client, model=model),
            PricingModel(model_type="未知"), sink=degraded_sink),
        "personas": lambda: _safe_extract(
            "personas", competitor,
            lambda: extract_personas(pers_ev, competitor, client=client, model=model),
            [], sink=degraded_sink),
        "swot": lambda: _safe_extract(
            "swot", competitor,
            lambda: extract_swot(ev, competitor, client=client, model=model),
            SWOT(), sink=degraded_sink),
    }
    with cf.ThreadPoolExecutor(max_workers=_MAX_EXTRACT_WORKERS) as ex:
        fut_to_key = {ex.submit(fn): k for k, fn in thunks.items()}
        out: dict[str, object] = {}
        # as_completed:每项抽取一完成就回收 + emit 增量进度(on_progress 在 worker 线程调,
        # 由调用方传入的 ticker 锁内串行化 put_nowait,线程安全)。on_progress=None → 不报(单测)。
        for fut in cf.as_completed(fut_to_key):
            k = fut_to_key[fut]
            out[k] = fut.result()
            if on_progress is not None:
                on_progress(f"分析 {competitor}·{_EXTRACT_ZH.get(k, k)}")
    return CompetitorProfile(
        name=competitor,
        features=out["features"], pricing=out["pricing"],
        personas=out["personas"], swot=out["swot"],
    )


def build_comparison(
    profiles: list[CompetitorProfile], evidence: list[Evidence],
    *, dimensions: tuple[str, ...] = CONTROLLED_DIMENSIONS,
    on_progress: Callable[[str], None] | None = None, client, model,
) -> list[ComparisonRow]:
    """收尾产出跨竞品对比(受控本体 + 类型化值 + evidence_refs,spec D5 / §6)。

    **只在用户请求的 `dimensions` 上对比**(默认全受控本体,兼容直接调用)。原先硬编码
    CONTROLLED_DIMENSIONS 让分析员对全 6 维 + 自创维度产出 → 越界 hallucination + 触发
    质检覆盖未请求维度 → retry_collect 死循环 → insufficient_evidence(真 run 暴露)。
    """
    names = ", ".join(p.name for p in profiles)
    dims = ", ".join(dimensions)
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n对竞品 [{names}] **只在这些维度**做横向对比:{dims}。"
             f"**不要新增其它维度**(超出上述维度的对比一律不要输出)。"
             f"每个 cell 标 value_type(bool/enum/number/quote_text)与 value,并挂 evidence_refs。"
             f"\n\n证据:\n{block}"}]
    # 对比是 analyze 最后一步、单次大调用(~35-70s)。**调用前** emit 一次进度,让执行流在这段
    # 显"正在生成对比矩阵"(否则前 N 项抽取报完后这段又静默几十秒)。
    if on_progress is not None:
        on_progress("生成跨竞品对比矩阵")
    return structured_call(ComparisonExtraction, msgs, client=client, model=model).rows


def analyze(
    evidence: list[Evidence], competitors: list[str],
    *, dimensions: tuple[str, ...] = CONTROLLED_DIMENSIONS,
    degraded_sink: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None, client, model,
) -> CompetitorAnalysis:
    """分析 Agent 入口:证据 → 结构化分析(逐竞品 profile + 跨竞品对比)。

    `dimensions`:本次请求的维度,穿到 build_comparison 约束对比范围(默认全受控本体,
    兼容老调用/单测)。节点传 state["dimensions"];否则对比会超范围触发质检覆盖死循环。
    `degraded_sink`:任一竞品任一项抽取降级时 label 汇聚于此(透传给 analyze_competitor)。
    None = 不汇聚(向后兼容)。analyze_node 据此置 run 级 degraded,保证「降级必可见」。
    """
    # 竞品间并行(外层池);每个竞品内部再并行 4 抽取(内层池)。f.result() 按
    # 提交顺序回收 → profiles 保持 competitors 顺序(单测/对比稳定)。
    with cf.ThreadPoolExecutor(
        max_workers=min(_MAX_COMPETITOR_WORKERS, len(competitors) or 1)
    ) as ex:
        futures = [
            ex.submit(analyze_competitor, evidence, c,
                      degraded_sink=degraded_sink, on_progress=on_progress,
                      client=client, model=model)
            for c in competitors
        ]
        profiles = [f.result() for f in futures]
    comparison = build_comparison(
        profiles, evidence, dimensions=dimensions, on_progress=on_progress,
        client=client, model=model)
    return CompetitorAnalysis(competitors=profiles, comparison=comparison)
