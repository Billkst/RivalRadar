from __future__ import annotations

from rivalradar.schema.feature_tree import assemble_tree
from rivalradar.schema.models import CompetitorAnalysis, CompetitorProfile, ComparisonRow, EvidenceRef, Evidence, FeatureItem


def _fmt_refs(refs: list[EvidenceRef]) -> str:
    """把 evidence_refs 渲染成内联引用标记,如 ' [e1, e2]';无引用则空串。"""
    ids = [r.evidence_id for r in refs]
    return f" [{', '.join(ids)}]" if ids else ""


def _render_features(features: list[FeatureItem]) -> str:
    """按 assemble_tree 的层级缩进渲染功能项,每项挂内联引用。"""
    lines: list[str] = []

    def walk(nodes: list[dict], depth: int) -> None:
        for n in nodes:
            it = n["item"]
            indent = "  " * depth
            desc = f":{it.description}" if it.description else ""
            lines.append(f"{indent}- {it.name}{desc}{_fmt_refs(it.evidence_refs)}")
            walk(n["children"], depth + 1)

    walk(assemble_tree(features), 0)
    return "\n".join(lines)


def render_competitor(profile: CompetitorProfile) -> str:
    """确定性渲染单个竞品 Profile 为 Markdown,每条结论挂内联引用。"""
    parts = [f"## {profile.name}", "### 功能"]
    parts.append(_render_features(profile.features) if profile.features else "_(无)_")

    parts.append(f"### 定价({profile.pricing.model_type}){_fmt_refs(profile.pricing.evidence_refs)}")
    if profile.pricing.tiers:
        for t in profile.pricing.tiers:
            tail = f" — {t.limits}" if t.limits else ""
            parts.append(f"- {t.name}:{t.price} / {t.billing_cycle}{tail}")
    else:
        parts.append("_(无)_")

    parts.append("### 用户画像")
    if profile.personas:
        for p in profile.personas:
            needs = "、".join(p.needs) or "—"
            pains = "、".join(p.pain_points) or "—"
            praise = "、".join(p.praise) or "—"
            parts.append(f"- {p.segment}:需求 {needs};痛点 {pains};好评 {praise}{_fmt_refs(p.evidence_refs)}")
    else:
        parts.append("_(无)_")

    parts.append("### SWOT")
    quads = (("优势", profile.swot.strengths), ("劣势", profile.swot.weaknesses),
             ("机会", profile.swot.opportunities), ("威胁", profile.swot.threats))
    swot_lines = [f"- {label}:{pt.text}{_fmt_refs(pt.evidence_refs)}"
                  for label, points in quads for pt in points]
    parts.append("\n".join(swot_lines) if swot_lines else "_(无)_")

    return "\n".join(parts)


def render_comparison(rows: list[ComparisonRow], competitors: list[str]) -> str:
    """跨竞品对比表:行=维度,列=竞品,cell 标 value + 内联引用;缺 cell 标 '—'。"""
    if not rows:
        return "## 跨竞品对比\n\n_(无对比数据)_"
    header = "| 维度 | " + " | ".join(competitors) + " |"
    sep = "|" + "---|" * (len(competitors) + 1)
    lines = ["## 跨竞品对比", "", header, sep]
    for row in rows:
        by_comp = {c.competitor: c for c in row.cells}
        cells = []
        for name in competitors:
            cell = by_comp.get(name)
            cells.append(f"{cell.value}{_fmt_refs(cell.evidence_refs)}" if cell else "—")
        lines.append(f"| {row.dimension} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _cited_ids(analysis: CompetitorAnalysis) -> list[str]:
    """按出现顺序收集 analysis 中所有被引的 evidence_id(去重)。"""
    ids: list[str] = []
    seen: set[str] = set()

    def add(refs: list[EvidenceRef]) -> None:
        for r in refs:
            if r.evidence_id not in seen:
                seen.add(r.evidence_id)
                ids.append(r.evidence_id)

    for prof in analysis.competitors:
        for f in prof.features:
            add(f.evidence_refs)
        add(prof.pricing.evidence_refs)
        for p in prof.personas:
            add(p.evidence_refs)
        for points in (prof.swot.strengths, prof.swot.weaknesses,
                       prof.swot.opportunities, prof.swot.threats):
            for pt in points:
                add(pt.evidence_refs)
    for row in analysis.comparison:
        for cell in row.cells:
            add(cell.evidence_refs)
    return ids


def render_sources(analysis: CompetitorAnalysis, evidence: list[Evidence]) -> str:
    """被引证据清单:evidence_id → [标题](URL)(as of fetched_at);不在证据集的标 missing。"""
    idx = {e.id: e for e in evidence}
    cited = _cited_ids(analysis)
    lines = ["## 来源"]
    if not cited:
        lines.append("_(无引用)_")
        return "\n".join(lines)
    for eid in cited:
        e = idx.get(eid)
        if e is None:
            lines.append(f"- [{eid}] (missing:该 evidence_id 不在证据集)")
        else:
            lines.append(f"- [{eid}] [{e.source_title}]({e.source_url})(as of {e.fetched_at})")
    return "\n".join(lines)


def render_body(analysis: CompetitorAnalysis, evidence: list[Evidence], *, as_of: str) -> str:
    """确定性正文:as-of 时效 + 逐竞品 Profile + 对比表 + 来源清单。"""
    parts = [f"> 数据时效:as of {as_of}"]
    parts += [render_competitor(p) for p in analysis.competitors]
    parts.append(render_comparison(analysis.comparison, [p.name for p in analysis.competitors]))
    parts.append(render_sources(analysis, evidence))
    return "\n\n".join(parts)
