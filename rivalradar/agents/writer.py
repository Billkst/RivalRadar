from __future__ import annotations

from rivalradar.schema.feature_tree import assemble_tree
from rivalradar.schema.models import CompetitorProfile, EvidenceRef, FeatureItem


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
