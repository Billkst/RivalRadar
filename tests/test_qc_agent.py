from rivalradar.agents.qc import (
    check_traceability, check_ontology, check_coverage,
)
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, FeatureItem, PricingModel,
    SWOT, SWOTPoint, ComparisonRow, ComparisonCell, EvidenceRef, Evidence,
)


def _ref(eid):
    return EvidenceRef(evidence_id=eid, quote="q")


def _ev(eid, dimension="pricing"):
    return Evidence(id=eid, competitor="Notion", dimension=dimension, content="c",
                    source_url="u", source_title="t", language="en",
                    fetched_at="2026-05-25T00:00:00Z")


def test_check_traceability_flags_empty_refs():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        features=[FeatureItem(id="f1", name="db", description="", category="core_workflows",
                              evidence_refs=[])],  # 空引用
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    issues = check_traceability(analysis, [_ev("e1")])
    assert any(i.problem_type == "missing_evidence" for i in issues)


def test_check_traceability_flags_dangling_evidence_id():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e_ghost")]),  # 不存在
        swot=SWOT())])
    issues = check_traceability(analysis, [_ev("e1")])
    assert any("e_ghost" in i.detail for i in issues)


def test_check_traceability_clean_when_all_valid():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    assert check_traceability(analysis, [_ev("e1")]) == []


def test_check_ontology_flags_bad_comparison_and_evidence_dimension():
    analysis = CompetitorAnalysis(
        competitors=[],
        comparison=[ComparisonRow(dimension="天气", cells=[])])  # 非受控维度
    issues = check_ontology(analysis, [_ev("e1", dimension="八卦")])  # 证据维度也非受控
    kinds = [i.detail for i in issues]
    assert any("天气" in d for d in kinds)
    assert any("八卦" in d for d in kinds)
    assert all(i.problem_type == "schema_incomplete" for i in issues)


def test_check_coverage_flags_missing_dimension():
    # Notion 只在 pricing 有对比 cell,缺其余 5 个受控维度
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium")])])
    issues = check_coverage(analysis)
    missing_dims = {i.dimension for i in issues if i.problem_type == "low_coverage"}
    assert "deployment" in missing_dims and "pricing" not in missing_dims
