from rivalradar.agents.analyst import (
    evidence_for, FeatureExtraction, PersonaExtraction, ComparisonExtraction,
)
from rivalradar.schema.models import Evidence, FeatureItem


def _ev(eid, competitor, dimension):
    return Evidence(id=eid, competitor=competitor, dimension=dimension, content="c",
                    source_url="u", source_title="t", language="en", fetched_at="2026-05-25T00:00:00Z")


def test_evidence_for_filters_by_competitor():
    evs = [_ev("1", "Notion", "pricing"), _ev("2", "飞书", "pricing")]
    out = evidence_for(evs, "Notion")
    assert [e.id for e in out] == ["1"]


def test_evidence_for_filters_by_competitor_and_dimension():
    evs = [_ev("1", "Notion", "pricing"), _ev("2", "Notion", "core_workflows")]
    out = evidence_for(evs, "Notion", dimension="pricing")
    assert [e.id for e in out] == ["1"]


def test_wrapper_models_hold_lists():
    fe = FeatureExtraction(items=[FeatureItem(id="f1", name="db", description="", category="core_workflows")])
    assert fe.items[0].id == "f1"
    assert PersonaExtraction(personas=[]).personas == []
    assert ComparisonExtraction(rows=[]).rows == []


import json
from types import SimpleNamespace

from rivalradar.agents.analyst import (
    extract_features, extract_pricing, build_evidence_block,
)
from rivalradar.schema.models import PricingModel


class _Completions:
    def __init__(self, payloads):
        self.payloads = list(payloads); self.calls = 0; self.last_kwargs = None
    def create(self, **kwargs):
        self.last_kwargs = kwargs
        p = self.payloads[self.calls]; self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=p))]))],
            usage=SimpleNamespace(total_tokens=10))


class _FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=_Completions(payloads))


def test_build_evidence_block_numbers_and_ids():
    block = build_evidence_block([_ev("e1", "Notion", "pricing"), _ev("e2", "Notion", "pricing")])
    assert "e1" in block and "e2" in block  # evidence_id 出现,供模型引用


def test_extract_features_returns_feature_items():
    payload = json.dumps({"items": [
        {"id": "f1", "name": "数据库", "description": "表格", "category": "core_workflows",
         "evidence_refs": [{"evidence_id": "e1", "quote": "支持数据库", "support_verdict": "supported"}]}]})
    client = _FakeClient([payload])
    feats = extract_features([_ev("e1", "Notion", "core_workflows")], "Notion",
                             client=client, model="m")
    assert feats[0].name == "数据库"
    assert feats[0].evidence_refs[0].evidence_id == "e1"


def test_extract_pricing_returns_pricing_model():
    payload = json.dumps({"model_type": "freemium", "tiers": [
        {"name": "Free", "price": "$0", "billing_cycle": "monthly"}], "evidence_refs": []})
    client = _FakeClient([payload])
    pricing = extract_pricing([_ev("e1", "Notion", "pricing")], "Notion", client=client, model="m")
    assert isinstance(pricing, PricingModel) and pricing.model_type == "freemium"
