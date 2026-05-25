from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel

from rivalradar.llm.structured import structured_call
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, Evidence, EvidenceRef, QCIssue,
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
    """LLM 蕴含(尽力):被引证据是否真支撑结论;不支撑 → hallucination。每条结论一次调用。"""
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
