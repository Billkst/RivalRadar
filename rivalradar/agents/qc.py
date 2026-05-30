from __future__ import annotations

import concurrent.futures as cf
from collections.abc import Iterator

from pydantic import BaseModel

from rivalradar.llm.structured import structured_call
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, Decision, Evidence, EvidenceRef,
    QCIssue, QCResult, QCVerdict,
)

# 蕴含判定并行度:check_entailment / curate_decisions 逐结论独立调 LLM,线程池并发。
# qc 在 analyze 之后跑、不与之线程重叠;client 多线程并发安全已由 analyst M1 测锁死。
# 每次蕴含 payload 小(src[:600]),单调 ~4-5s,一轮 12-18 格串行 → 并行后单轮省数十秒。
_MAX_ENTAIL_WORKERS = 8


def _iter_conclusions(
    analysis: CompetitorAnalysis, *, dimensions: tuple[str, ...] | None = None,
    comparison_only: bool = False,
) -> Iterator[tuple[str, str, str, list[EvidenceRef]]]:
    """遍历每条挂引用的结论 → (competitor, dimension, 结论文本, evidence_refs)。

    dimensions:只产「请求维度」的结论(None = 全产,向后兼容)。真 run 续集:
    用户只请求 pricing/core_workflows/integrations 时,analyze_competitor 仍对每个竞品
    产全套 profile,其中 personas(→review_sentiment)/SWOT(→"swot",非可搜索本体)是
    综合产物。把这些越界结论喂给 check_entailment 这个 LLM 判定闸,会因前瞻推断/越界断言
    产 hallucination → degraded;且 SWOT 前瞻判定本就是范畴错误。scope 到请求维度即只对
    用户真正要的维度严判(check_traceability 仍全量,保证 SWOT 仍需挂引用)。

    comparison_only:只产对比矩阵 cell——即 showcase 真正呈现的「分析主张」,跳过 profile 的
    features/pricing/personas/SWOT 这些描述性辅助结论(它们喂 v0.4 已退役的报告、不进驾驶舱)。
    check_entailment(阻断性 LLM 判定)用它把"是否 grounded"的严判聚焦到展示内容;真 run
    钓出:分析员对细粒度功能过度拆解(证据写「资源分配」→ 脑补「人员分配/预算控制」),这类
    描述性脚注的小越界不该拿去否决整个 run。矩阵 cell 与决策仍被严判(它们越界照样 degraded,
    诚实);check_traceability 仍全量(辅助结论仍需挂引用)。
    """
    def _in_scope(dim: str) -> bool:
        return dimensions is None or dim in dimensions

    if not comparison_only:
        for prof in analysis.competitors:
            for f in prof.features:
                if _in_scope("core_workflows"):
                    yield prof.name, "core_workflows", f"功能:{f.name}", f.evidence_refs
            if _in_scope("pricing"):
                yield prof.name, "pricing", f"定价:{prof.pricing.model_type}", prof.pricing.evidence_refs
            for p in prof.personas:
                if _in_scope("review_sentiment"):
                    yield prof.name, "review_sentiment", f"画像:{p.segment}", p.evidence_refs
            quads = (("优势", prof.swot.strengths), ("劣势", prof.swot.weaknesses),
                     ("机会", prof.swot.opportunities), ("威胁", prof.swot.threats))
            for label, points in quads:
                for pt in points:
                    if _in_scope("swot"):
                        yield prof.name, "swot", f"SWOT-{label}:{pt.text}", pt.evidence_refs
    for row in analysis.comparison:
        if _in_scope(row.dimension):
            for cell in row.cells:
                yield cell.competitor, row.dimension, f"对比:{cell.value}", cell.evidence_refs


def check_traceability(
    analysis: CompetitorAnalysis, evidence: list[Evidence],
    *, comparison_only: bool = False,
) -> list[QCIssue]:
    """硬闸:每条结论必须挂非空、且 evidence_id 存在于证据集的 evidence_refs。

    comparison_only:只机械校验对比矩阵 cell(cockpit showcase 面),跳过 profile 的
    描述性结论(features/pricing/personas/SWOT,喂 v0.4 退役报告、不进驾驶舱)。Part B
    策展化:qc_node 用它把阻断性溯源闸 scope 到展示内容,profile 描述性结论的小瑕疵不
    再触发 retry_collect 死循环/insufficient(与 check_entailment 的 comparison_only 对称)。"""
    valid = {e.id for e in evidence}
    issues: list[QCIssue] = []
    for comp, dim, text, refs in _iter_conclusions(analysis, comparison_only=comparison_only):
        if not refs:
            issues.append(QCIssue(competitor=comp, dimension=dim,
                                  problem_type="missing_evidence", detail=f"无引用:{text}"))
            continue
        for r in refs:
            if r.evidence_id not in valid:
                issues.append(QCIssue(competitor=comp, dimension=dim,
                                      problem_type="missing_evidence",
                                      detail=f"引用了不存在的 evidence_id={r.evidence_id}:{text}"))
    return issues


def check_ontology(analysis: CompetitorAnalysis, evidence: list[Evidence]) -> list[QCIssue]:
    """硬闸:对比维度与证据维度必须落在受控本体内(收 C-2a 遗留④)。"""
    allowed = set(CONTROLLED_DIMENSIONS)
    issues: list[QCIssue] = []
    for row in analysis.comparison:
        if row.dimension not in allowed:
            issues.append(QCIssue(competitor="*", dimension=row.dimension,
                                  problem_type="schema_incomplete",
                                  detail=f"对比维度不在受控本体:{row.dimension}"))
    for e in evidence:
        if e.dimension not in allowed:
            issues.append(QCIssue(competitor=e.competitor, dimension=e.dimension,
                                  problem_type="schema_incomplete",
                                  detail=f"证据维度不在受控本体:{e.dimension}"))
    return issues


def check_coverage(
    analysis: CompetitorAnalysis, *, required: tuple[str, ...] = CONTROLLED_DIMENSIONS,
    evidence: list[Evidence] | None = None,
) -> list[QCIssue]:
    """覆盖度(策展人模型):每个竞品在每个受控维度上都应有对比 cell,缺则 low_coverage。

    evidence(真 run 暴露的"重试空转"修复):区分两种「缺 cell」——
    - 该 (竞品,维度) **零证据**:真·欠采 → low_coverage → retry_collect(broaden 能补、会收敛);
    - 该 (竞品,维度) **采到了证据但 cell 被策展丢掉**(蕴含判结论无据):已覆盖、只是结论站不住,
      该在矩阵显「—」**不该重采**——非确定的策展会在维度间反复重开缺口 → 不收敛的重试空转
      (占真 run ~2 轮 wall-clock,纯亏)。
    **取舍(ship-time 评审 MINOR)**:我们以收敛性优先,**放弃**对"已有证据但 cell 被丢"维度的
    二次 broaden 机会——broaden 会改写查询词(CRAG),理论上对首轮恰好采到垃圾证据的维度**可能**
    换到更好的源让结论站住。但为根治不收敛空转,这条二次恢复路径被有意舍弃(若真 run 数据证明
    "首采垃圾"常见,可改成仅 retry_count==0 时放行一次重采;当前不做,空转是更大的痛)。
    传入 evidence 即只对零证据维度报 low_coverage。evidence=None:老行为(任何缺 cell 都
    low_coverage),向后兼容老调用与单测。"""
    covered: dict[str, set[str]] = {}
    for row in analysis.comparison:
        if row.dimension in required:
            for cell in row.cells:
                covered.setdefault(cell.competitor, set()).add(row.dimension)
    has_evidence: dict[str, set[str]] = {}
    if evidence is not None:
        for e in evidence:
            has_evidence.setdefault(e.competitor, set()).add(e.dimension)
    issues: list[QCIssue] = []
    for prof in analysis.competitors:
        have = covered.get(prof.name, set())
        for dim in required:
            if dim in have:
                continue
            # 采到了证据但 cell 被策展丢掉 → 已覆盖(显「—」),不算欠采、不触发 retry_collect。
            if evidence is not None and dim in has_evidence.get(prof.name, set()):
                continue
            issues.append(QCIssue(competitor=prof.name, dimension=dim,
                                  problem_type="low_coverage",
                                  detail=f"{prof.name} 缺少维度 {dim} 的对比"))
    return issues


class EntailmentVerdict(BaseModel):
    supported: bool
    reason: str = ""


def check_entailment(
    analysis: CompetitorAnalysis, evidence: list[Evidence],
    *, dimensions: tuple[str, ...] | None = None, comparison_only: bool = False,
    client, model,
) -> list[QCIssue]:
    """LLM 蕴含判定:被引证据是否真支撑结论;不支撑 → hallucination。每条结论一次调用。

    dimensions:只对「请求维度」的结论做蕴含判定(None = 全判,向后兼容)。SWOT/persona
    等越界综合产物不进这个 LLM 闸(见 _iter_conclusions docstring)。
    comparison_only:阻断性 LLM 判定只严判 showcase 呈现的对比矩阵 cell,profile 的描述性
    features/pricing/personas/SWOT 不进此闸(见 _iter_conclusions docstring)。
    错误契约:本函数不吞错——structured_call 失败会上抛;"尽力/失败降级"由 Lane D 编排层
    捕获后降级为仅确定性闸的 verdict(spec §5 尽力 + §8 trace)。"""
    idx = {e.id: e for e in evidence}
    # 只判挂引用的结论(空引用归 check_traceability);各结论独立 → 线程池并发判蕴含。
    conclusions = [
        (comp, dim, text, refs)
        for comp, dim, text, refs in _iter_conclusions(
            analysis, dimensions=dimensions, comparison_only=comparison_only)
        if refs
    ]
    if not conclusions:
        return []

    def _judge(item: tuple[str, str, str, list[EvidenceRef]]) -> QCIssue | None:
        comp, dim, text, refs = item
        quotes = []
        for r in refs:
            src = idx[r.evidence_id].content if r.evidence_id in idx else ""
            quotes.append(f"- 引语:{r.quote}\n  证据原文:{src[:600]}")
        msgs = [{"role": "user", "content":
                 "判断下列证据是否支撑该结论。supported=true 表示证据确实支撑该结论;"
                 "false 表示不支撑或无关。\n\n"
                 f"结论:{text}\n\n证据:\n" + "\n".join(quotes)}]
        verdict = structured_call(EntailmentVerdict, msgs, client=client, model=model)
        if not verdict.supported:
            return QCIssue(competitor=comp, dimension=dim,
                           problem_type="hallucination",
                           detail=f"证据不支撑结论({text}):{verdict.reason}")
        return None

    # ex.map 保序(issue 顺序确定);任一 structured_call 上抛 → 迭代结果时重新抛出
    # (错误契约不变:失败上抛,由 qc_node 捕获降级为机械门 fallback)。
    with cf.ThreadPoolExecutor(max_workers=min(_MAX_ENTAIL_WORKERS, len(conclusions))) as ex:
        results = list(ex.map(_judge, conclusions))
    return [r for r in results if r is not None]


# ── Part B:QC 策展化(信任模型「否决闸」→「策展人」)─────────────────────────
# v0.4 真 run 钓出:entailment 把过度拆解的越界 cell 判 hallucination → retry_analyze
# 耗尽 → 整个 run degraded + 丑横幅。但人类分析师不这么干:站不住的结论直接不写,只
# 展示站得住的。curate_analysis 把这个理念落地——丢弃站不住的对比 cell,而非否决整 run。
# 防虚构契约因此更强(主动删而非仅标记),且降级横幅只留给真·覆盖耗尽(诚实 insufficient)。
def curate_analysis(
    analysis: CompetitorAnalysis, evidence: list[Evidence],
    *, dimensions: tuple[str, ...] | None = None, client, model,
) -> tuple[CompetitorAnalysis, list[str]]:
    """策展对比矩阵:丢弃无引用/悬空引用(机械)+ 蕴含不支撑(LLM)的 cell,返回
    (curated_analysis, dropped_labels)。只动 showcase 的对比矩阵(请求维度内);profile
    描述性结论不在此(喂退役报告、不进驾驶舱)。错误契约同 check_entailment:structured_call
    失败上抛,由 qc_node 捕获降级。"""
    # Phase 1 机械门(免费、确定):丢弃无引用/悬空引用的 in-scope cell,空 row 消失。
    # 先于 LLM 跑,保证悬空引用 cell 绝不进 check_entailment(不耗 LLM 预算)。
    mech_analysis, dropped = _curate_mechanical(analysis, evidence, dimensions)

    # Phase 2 LLM 门(贵):只对机械门幸存的 cell 判蕴含(已 scope comparison_only + 请求维度)。
    unsupported = {
        (i.competitor, i.dimension)
        for i in check_entailment(mech_analysis, evidence, dimensions=dimensions,
                                  comparison_only=True, client=client, model=model)
    }

    # Phase 3 组装:丢弃蕴含不支撑的 cell;空 row 直接消失(coverage 发现缺口 → broaden 补搜环)。
    final_rows: list[ComparisonRow] = []
    for row in mech_analysis.comparison:
        in_scope = dimensions is None or row.dimension in dimensions
        if not in_scope:
            final_rows.append(row)
            continue
        kept = []
        for cell in row.cells:
            if (cell.competitor, row.dimension) in unsupported:
                dropped.append(f"{cell.competitor}/{row.dimension}")  # 蕴含:不支撑
                continue
            kept.append(cell)
        if kept:
            final_rows.append(row.model_copy(update={"cells": kept}))
    curated = analysis.model_copy(update={"comparison": final_rows})
    return curated, dropped


def _curate_mechanical(
    analysis: CompetitorAnalysis, evidence: list[Evidence],
    dimensions: tuple[str, ...] | None,
) -> tuple[CompetitorAnalysis, list[str]]:
    """机械门策展(免 LLM):丢弃 in-scope 且无引用/悬空引用的对比 cell,空 row 消失,
    out-of-scope row 原样保留。返回 (curated_analysis, dropped)。curate_analysis 的 Phase 1,
    也是 qc_node 在 LLM 蕴含失败降级时的 fallback(不调 LLM 仍能给干净 showcase)。"""
    valid = {e.id for e in evidence}
    dropped: list[str] = []
    rows: list[ComparisonRow] = []
    for row in analysis.comparison:
        in_scope = dimensions is None or row.dimension in dimensions
        if not in_scope:
            rows.append(row)
            continue
        kept = []
        for cell in row.cells:
            if not cell.evidence_refs or any(r.evidence_id not in valid for r in cell.evidence_refs):
                dropped.append(f"{cell.competitor}/{row.dimension}")
                continue
            kept.append(cell)
        if kept:
            rows.append(row.model_copy(update={"cells": kept}))
    return analysis.model_copy(update={"comparison": rows}), dropped


# ── QC-on-decisions(full-C / Epic 2.3)──────────────────────────────────────
# 决策级 QC issue 用 dimension='decision' 标记,与 analysis issue 区分:它们不进
# analysis 的 retry_collect/retry_analyze 路由,而是由 decide 节点内部消费(有界重生)。
def check_decision_traceability(
    decisions: list[Decision], evidence: list[Evidence]
) -> list[QCIssue]:
    """机械门:每条决策必须挂非空、且 evidence_id 存在于证据集的 evidence_refs。"""
    valid = {e.id for e in evidence}
    issues: list[QCIssue] = []
    for d in decisions:
        if not d.evidence_refs:
            issues.append(QCIssue(competitor="*", dimension="decision",
                                  problem_type="missing_evidence",
                                  detail=f"决策无引用:{d.action}"))
            continue
        for r in d.evidence_refs:
            if r.evidence_id not in valid:
                issues.append(QCIssue(competitor="*", dimension="decision",
                                      problem_type="missing_evidence",
                                      detail=f"决策引用了不存在的 evidence_id={r.evidence_id}:{d.action}"))
    return issues


def check_decision_entailment(
    decisions: list[Decision], evidence: list[Evidence], *, client, model,
    max_calls: int = 8,
) -> list[QCIssue]:
    """LLM 蕴含:被引证据是否支撑决策的 action+why;不支撑 → hallucination。

    COST GUARD(Codex #4):每条决策一次调用,但**封顶 max_calls 次** —— 决策通常
    3-5 条(DecisionSet.max_length=8 源头硬封),cap 防 LLM 失控吐 N 条触发 retry-storm
    撞 90s SDK timeout;超额 / 悬空引用决策跳过蕴含(机械门 check_decision_traceability
    仍覆盖其溯源)。错误契约同 check_entailment:structured_call 失败上抛,由 decide 节点
    捕获降级。

    真实 SDK 请求口径(adversarial review M3):每次"调用"是一次 structured_call,其内部
    max_retries=2(最多 3 次 SDK create);decide 节点最多重生 1 轮。故单 decide 节点最坏
    SDK 请求 ≈ 重生 2 轮 ×(generate ×3 + entail max_calls ×3)。有界(非无限 storm),
    每次受 90s per-call 保护;但若要进一步压总时长,调小 max_calls 或 decide 重生轮数。"""
    idx = {e.id: e for e in evidence}
    issues: list[QCIssue] = []
    calls = 0
    for d in decisions:
        # 空引用 / 任一悬空引用都归 check_decision_traceability 负责 → 跳过蕴含,
        # 不耗 cost guard 预算去验证机械门已判 ungrounded 的决策(adversarial review)。
        if not d.evidence_refs or any(r.evidence_id not in idx for r in d.evidence_refs):
            continue
        if calls >= max_calls:
            break  # cost guard:超额不再调 LLM
        quotes = []
        for r in d.evidence_refs:
            src = idx[r.evidence_id].content if r.evidence_id in idx else ""
            quotes.append(f"- 引语:{r.quote}\n  证据原文:{src[:600]}")
        msgs = [{"role": "user", "content":
                 "判断下列证据是否支撑该决策建议。supported=true 表示证据确实支撑该建议的"
                 "行动与理由;false 表示不支撑或无关。\n\n"
                 f"决策(行动):{d.action}\n理由:{d.why}\n\n证据:\n" + "\n".join(quotes)}]
        verdict = structured_call(EntailmentVerdict, msgs, client=client, model=model)
        calls += 1
        if not verdict.supported:
            issues.append(QCIssue(competitor="*", dimension="decision",
                                  problem_type="hallucination",
                                  detail=f"证据不支撑决策({d.action}):{verdict.reason}"))
    return issues


def curate_decisions(
    decisions: list[Decision], evidence: list[Evidence], *, client, model,
    max_calls: int = 8,
) -> tuple[list[Decision], list[str]]:
    """策展决策:丢弃无引用/悬空引用(机械)+ 蕴含不支撑(LLM)的决策,返回
    (kept, dropped_actions)。与 curate_analysis 对称——ungrounded 决策静默丢弃,而非
    decision_degraded 标降级整批。cost guard 同 check_decision_entailment(封顶 max_calls,
    超额不再调 LLM、视为保留)。错误契约:structured_call 失败上抛,由 decide 节点捕获。"""
    idx = {e.id: e for e in evidence}
    dropped: list[str] = []
    # 机械门(免 LLM):无引用 / 任一悬空引用 → 丢弃;其余进 candidates(保序)。
    candidates: list[Decision] = []
    for d in decisions:
        if not d.evidence_refs or any(r.evidence_id not in idx for r in d.evidence_refs):
            dropped.append(d.action)
        else:
            candidates.append(d)
    # cost guard(Codex #4):仅前 max_calls 条判蕴含,超额保留不判(机械门已过)。
    to_judge = candidates[:max_calls]

    def _supported(d: Decision) -> bool:
        quotes = []
        for r in d.evidence_refs:
            src = idx[r.evidence_id].content if r.evidence_id in idx else ""
            quotes.append(f"- 引语:{r.quote}\n  证据原文:{src[:600]}")
        msgs = [{"role": "user", "content":
                 "判断下列证据是否支撑该决策建议。supported=true 表示证据确实支撑该建议的"
                 "行动与理由;false 表示不支撑或无关。\n\n"
                 f"决策(行动):{d.action}\n理由:{d.why}\n\n证据:\n" + "\n".join(quotes)}]
        return structured_call(EntailmentVerdict, msgs, client=client, model=model).supported

    # ex.map 保序对齐 to_judge;任一上抛 → 迭代时重新抛出(由 decide 节点捕获机械门 fallback)。
    flags: list[bool] = []
    if to_judge:
        with cf.ThreadPoolExecutor(max_workers=min(_MAX_ENTAIL_WORKERS, len(to_judge))) as ex:
            flags = list(ex.map(_supported, to_judge))

    kept: list[Decision] = []
    for j, d in enumerate(candidates):
        if j >= len(flags):
            kept.append(d)            # cost guard 超额:保留不判
        elif flags[j]:
            kept.append(d)            # 蕴含支撑:保留
        else:
            dropped.append(d.action)  # 蕴含不支撑:丢弃
    return kept, dropped


def decide_verdict(issues: list[QCIssue]) -> QCVerdict:
    """单遍质检 issues → verdict(纯逻辑)。
    insufficient_evidence 由 Lane D 路由在有界重试耗尽后赋予,不在此产出。"""
    if not issues:
        return "pass"
    kinds = {i.problem_type for i in issues}
    if "missing_evidence" in kinds or "low_coverage" in kinds:
        return "retry_collect"   # 缺证据/覆盖不足 → 先补采集(优先于重分析)
    return "retry_analyze"        # hallucination / schema_incomplete → 重新分析现有证据


# ── /qc 端点 sanitize(Epic 2.4 / Codex #9)──────────────────────────────────
# GET /qc/:run 是公开端点(与 /trace 同级)。QCIssue.detail 含 check_entailment 写入的
# 模型文本({verdict.reason})—— 绝不能原样暴露。投影成按 problem_type 的罐装中文文案
# (我方构造,零模型文本 / 零异常)。
# dimension 也必须白名单:schema_incomplete issue 的 dimension 就是 LLM 产出的"越界
# 维度名"(check_ontology 用 row.dimension / e.dimension 构造),本体越界时 LLM 可塞任意
# 字符串 → 越界即替占位,守住"零模型文本"契约(adversarial review M1)。competitor 为
# 竞品名短标签(多数来自用户请求列表),保留供前端定位,不视作模型文本泄漏向量。
_SANITIZED_DETAIL: dict[str, str] = {
    "missing_evidence": "结论缺少证据支撑",
    "low_coverage": "维度覆盖不足",
    "hallucination": "证据未能支撑该结论",
    "schema_incomplete": "维度不在受控本体内",
}
_SAFE_DIMENSIONS: frozenset[str] = frozenset(CONTROLLED_DIMENSIONS) | {"decision"}


def sanitize_qc_result(result: QCResult) -> dict:
    """把 QCResult 投影成可公开 serve 的 sanitized 形状:detail 换罐装文案、越界 dimension
    替占位 'out_of_ontology'(零模型文本)。"""
    return {
        "verdict": result.verdict,
        "issues": [
            {
                "competitor": i.competitor,
                "dimension": i.dimension if i.dimension in _SAFE_DIMENSIONS else "out_of_ontology",
                "problem_type": i.problem_type,
                "detail": _SANITIZED_DETAIL.get(i.problem_type, "质检发现问题"),
            }
            for i in result.issues
        ],
    }


def check(analysis: CompetitorAnalysis, evidence: list[Evidence], *, client, model) -> QCResult:
    """质检入口:确定性硬闸(溯源+本体+覆盖,始终运行)+ LLM 蕴含(可能上抛)→ QCResult。
    Lane D 编排层应捕获蕴含异常,降级为仅确定性闸的 verdict 并记 trace(spec §5/§8)。"""
    issues: list[QCIssue] = []
    issues += check_traceability(analysis, evidence)
    issues += check_ontology(analysis, evidence)
    issues += check_coverage(analysis)
    issues += check_entailment(analysis, evidence, client=client, model=model)
    return QCResult(verdict=decide_verdict(issues), issues=issues)
