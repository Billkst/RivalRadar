from rivalradar.agents.writer import _fmt_refs, render_competitor, render_comparison, render_sources, render_body
from rivalradar.schema.models import (
    CompetitorProfile, FeatureItem, PricingModel, PricingTier,
    UserPersona, SWOT, SWOTPoint, EvidenceRef,
    CompetitorAnalysis, ComparisonRow, ComparisonCell, Evidence,
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


def _ev(eid):
    return Evidence(id=eid, competitor="Notion", dimension="pricing", content="c",
                    source_url="https://notion.so/pricing", source_title="Pricing",
                    language="en", fetched_at="2026-05-25T00:00:00Z")


def test_render_comparison_table_has_competitor_columns_and_refs():
    rows = [ComparisonRow(dimension="pricing", cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                       evidence_refs=[_ref("e3")]),
        ComparisonCell(competitor="飞书", value_type="enum", value="freemium"),
    ])]
    md = render_comparison(rows, ["Notion", "飞书"])
    assert "| 维度 | Notion | 飞书 |" in md
    assert "pricing" in md and "freemium" in md and "[e3]" in md


def test_render_comparison_empty():
    assert "无对比数据" in render_comparison([], ["Notion"])


def test_render_sources_resolves_and_marks_missing():
    analysis = CompetitorAnalysis(
        competitors=[],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                           evidence_refs=[_ref("e3"), _ref("e_missing")])])],
    )
    md = render_sources(analysis, [_ev("e3")])
    assert "[e3]" in md and "Pricing" in md and "notion.so/pricing" in md
    assert "as of 2026-05-25T00:00:00Z" in md
    assert "e_missing" in md and "missing" in md  # 不在证据集 → 标 missing


def test_render_body_stamps_as_of_and_preserves_all_cited_ids():
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(
            name="Notion",
            features=[FeatureItem(id="f1", name="数据库", description="", category="core_workflows",
                                  evidence_refs=[_ref("e1")])],
            pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e3")]),
            swot=SWOT(),
        )],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                           evidence_refs=[_ref("e3")])])],
    )
    body = render_body(analysis, [_ev("e1"), _ev("e3")], as_of="2026-05-25")
    assert "as of 2026-05-25" in body
    # 引用忠实度:analysis 里每个被引 id 都出现在正文
    for eid in ("e1", "e3"):
        assert f"[{eid}]" in body or f"[{eid}," in body or f", {eid}]" in body
