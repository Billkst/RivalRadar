from __future__ import annotations

from typing import Annotated, TypedDict


def merge_evidence(left: list[dict], right: list[dict]) -> list[dict]:
    """证据累加去重 reducer(spec §8「累加不覆盖」)。

    按 evidence id 合并、先到先留:id = sha1(competitor|dimension|url),所以同源重采
    (同 url)→ 同 id → 丢弃;换源(新 url)→ 新 id → 追加。这让「第二版证据真增加」
    等价于「采到了新源」,正是真闭环要的不变量。
    """
    seen = {e["id"] for e in left}
    out = list(left)
    for e in right:
        if e["id"] not in seen:
            out.append(e)
            seen.add(e["id"])
    return out


class ResearchState(TypedDict, total=False):
    """LangGraph 共享状态(spec §4)。

    证据/分析/质检以 **dict 原语** 存(不是 Pydantic 对象):LangGraph 1.2.1 的
    JsonPlusSerializer 反序列化未注册 Pydantic 类型会告警且未来会 block,dict 原语
    则 checkpoint 零风险。节点边界做 Evidence(**d) / .model_dump() 转换。
    """
    competitors: list[str]            # 目标竞品
    dimensions: list[str]             # 受控维度(首遍采集用)
    evidence: Annotated[list[dict], merge_evidence]  # Evidence.model_dump() 列表,append-only 去重
    analysis: dict                    # CompetitorAnalysis.model_dump()
    report: str                       # markdown 报告
    qc_result: dict                   # QCResult.model_dump()
    retry_count: int                  # 已重试次数(仅 qc 节点递增;首遍=0)
    degraded: bool                    # 本轮 LLM 蕴含是否降级
    status: str                       # 终态:done / insufficient_evidence / degraded
    # ── full-C 决策管道(Epic 2.2-2.3)──────────────────────────────────────
    decision_context: str             # 用户决策处境(Epic 1.2 RunRequest 注入;空=通用浏览)
    decisions: dict                   # DecisionSet.model_dump()(decide 节点产出)
    decision_degraded: bool           # 决策溯源/蕴含是否降级(并入终态 degraded)
