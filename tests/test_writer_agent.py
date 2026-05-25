from rivalradar.agents.writer import _fmt_refs, render_competitor
from rivalradar.schema.models import (
    CompetitorProfile, FeatureItem, PricingModel, PricingTier,
    UserPersona, SWOT, SWOTPoint, EvidenceRef,
)


def _ref(eid):
    return EvidenceRef(evidence_id=eid, quote="q")


def test_fmt_refs_joins_ids_in_brackets():
    assert _fmt_refs([_ref("e1"), _ref("e2")]) == " [e1, e2]"
    assert _fmt_refs([]) == ""


def test_render_competitor_includes_facts_and_inline_citations():
    prof = CompetitorProfile(
        name="Notion",
        features=[
            FeatureItem(id="f1", name="数据库", description="多视图", category="core_workflows",
                        evidence_refs=[_ref("e1")]),
            FeatureItem(id="f2", name="表格视图", description="", category="core_workflows",
                        parent_id="f1", evidence_refs=[_ref("e2")]),
        ],
        pricing=PricingModel(model_type="freemium",
                             tiers=[PricingTier(name="Free", price="$0", billing_cycle="monthly")],
                             evidence_refs=[_ref("e3")]),
        personas=[UserPersona(segment="团队", needs=["协作"], evidence_refs=[_ref("e4")])],
        swot=SWOT(strengths=[SWOTPoint(text="生态强", evidence_refs=[_ref("e5")])]),
    )
    md = render_competitor(prof)
    assert "## Notion" in md
    assert "数据库" in md and "[e1]" in md
    assert "表格视图" in md and "[e2]" in md       # 子功能也渲染
    assert "freemium" in md and "[e3]" in md
    assert "Free" in md
    assert "团队" in md and "[e4]" in md
    assert "生态强" in md and "[e5]" in md


def test_render_competitor_handles_empty_sections():
    prof = CompetitorProfile(name="空", pricing=PricingModel(model_type="unknown"), swot=SWOT())
    md = render_competitor(prof)
    assert "## 空" in md
    assert "_(无)_" in md  # 空功能/定价/画像不崩
