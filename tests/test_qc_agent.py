import json
from types import SimpleNamespace

from rivalradar.agents.qc import (
    check_traceability, check_ontology, check_coverage, EntailmentVerdict, check_entailment,
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


class _Completions:
    def __init__(self, payloads):
        self.payloads = list(payloads); self.calls = 0

    def create(self, **kwargs):
        p = self.payloads[self.calls]; self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=p))]))],
            usage=SimpleNamespace(total_tokens=10))


class _FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=_Completions(payloads))


def test_check_entailment_flags_unsupported():
    # 单结论(pricing 挂 e1),模型判 not supported → hallucination
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    client = _FakeClient([json.dumps({"supported": False, "reason": "证据未提定价"})])
    issues = check_entailment(analysis, [_ev("e1")], client=client, model="m")
    assert len(issues) == 1 and issues[0].problem_type == "hallucination"


def test_check_entailment_passes_supported():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    client = _FakeClient([json.dumps({"supported": True, "reason": ""})])
    assert check_entailment(analysis, [_ev("e1")], client=client, model="m") == []


def test_check_entailment_skips_empty_refs():
    # 空引用归 traceability 管,蕴含不调用 LLM(payloads 给空也不该被取用)
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="x", evidence_refs=[]), swot=SWOT())])
    client = _FakeClient([])
    assert check_entailment(analysis, [_ev("e1")], client=client, model="m") == []
