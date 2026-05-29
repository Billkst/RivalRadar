from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel

from rivalradar.llm.structured import structured_call
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, Decision, Evidence, EvidenceRef,
    QCIssue, QCResult, QCVerdict,
)


def _iter_conclusions(
    analysis: CompetitorAnalysis,
) -> Iterator[tuple[str, str, str, list[EvidenceRef]]]:
    """遍历每条挂引用的结论 → (competitor, dimension, 结论文本, evidence_refs)。"""
    for prof in analysis.competitors:
        for f in prof.features:
            yield prof.name, "core_workflows", f"功能:{f.name}", f.evidence_refs
        yield prof.name, "pricing", f"定价:{prof.pricing.model_type}", prof.pricing.evidence_refs
        for p in prof.personas:
            yield prof.name, "review_sentiment", f"画像:{p.segment}", p.evidence_refs
        quads = (("优势", prof.swot.strengths), ("劣势", prof.swot.weaknesses),
                 ("机会", prof.swot.opportunities), ("威胁", prof.swot.threats))
        for label, points in quads:
            for pt in points:
                yield prof.name, "swot", f"SWOT-{label}:{pt.text}", pt.evidence_refs
    for row in analysis.comparison:
        for cell in row.cells:
            yield cell.competitor, row.dimension, f"对比:{cell.value}", cell.evidence_refs


def check_traceability(analysis: CompetitorAnalysis, evidence: list[Evidence]) -> list[QCIssue]:
    """硬闸:每条结论必须挂非空、且 evidence_id 存在于证据集的 evidence_refs。"""
    valid = {e.id for e in evidence}
    issues: list[QCIssue] = []
    for comp, dim, text, refs in _iter_conclusions(analysis):
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
    analysis: CompetitorAnalysis, *, required: tuple[str, ...] = CONTROLLED_DIMENSIONS
) -> list[QCIssue]:
    """覆盖度:每个竞品在每个受控维度上都应有对比 cell,缺则 low_coverage。"""
    covered: dict[str, set[str]] = {}
    for row in analysis.comparison:
        if row.dimension in required:
            for cell in row.cells:
                covered.setdefault(cell.competitor, set()).add(row.dimension)
    issues: list[QCIssue] = []
    for prof in analysis.competitors:
        have = covered.get(prof.name, set())
        for dim in required:
            if dim not in have:
                issues.append(QCIssue(competitor=prof.name, dimension=dim,
                                      problem_type="low_coverage",
                                      detail=f"{prof.name} 缺少维度 {dim} 的对比"))
    return issues


class EntailmentVerdict(BaseModel):
    supported: bool
    reason: str = ""


def check_entailment(
    analysis: CompetitorAnalysis, evidence: list[Evidence], *, client, model
) -> list[QCIssue]:
    """LLM 蕴含判定:被引证据是否真支撑结论;不支撑 → hallucination。每条结论一次调用。
    错误契约:本函数不吞错——structured_call 失败会上抛;"尽力/失败降级"由 Lane D 编排层
    捕获后降级为仅确定性闸的 verdict(spec §5 尽力 + §8 trace)。"""
    idx = {e.id: e for e in evidence}
    issues: list[QCIssue] = []
    for comp, dim, text, refs in _iter_conclusions(analysis):
        if not refs:
            continue  # 空引用由 check_traceability 负责
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
            issues.append(QCIssue(competitor=comp, dimension=dim,
                                  problem_type="hallucination",
                                  detail=f"证据不支撑结论({text}):{verdict.reason}"))
    return issues


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
