import json
from types import SimpleNamespace

from rivalradar.agents.analyst import (
    evidence_for, FeatureExtraction, PersonaExtraction, ComparisonExtraction,
    extract_features, extract_pricing, build_evidence_block,
    analyze_competitor, build_comparison, analyze, _safe_extract,
)
from rivalradar.llm.structured import StructuredCallError
from rivalradar.schema.models import Evidence, FeatureItem, PricingModel, SWOT, CompetitorAnalysis, CompetitorProfile


def test_safe_extract_degrades_on_structured_call_error():
    # 真 run 钓出:单项抽取 LLM 截断 → StructuredCallError 不该杀死整个 run
    def boom():
        raise StructuredCallError("Unterminated string ...")
    assert _safe_extract("features", "钉钉", boom, []) == []
    assert _safe_extract("pricing", "钉钉", boom, PricingModel(model_type="未知")).model_type == "未知"


def test_safe_extract_passes_through_on_success():
    assert _safe_extract("features", "Notion", lambda: ["ok"], []) == ["ok"]


def test_safe_extract_records_degrade_into_sink():
    # silent-failure 修复:降级必可见 —— label 记入 sink 供 analyze_node 置 run 级 degraded
    def boom():
        raise StructuredCallError("truncated")
    sink: list[str] = []
    _safe_extract("features", "钉钉", boom, [], sink=sink)
    assert sink == ["钉钉.features"]
    # 成功路径不污染 sink
    _safe_extract("pricing", "钉钉", lambda: PricingModel(model_type="x"), None, sink=sink)
    assert sink == ["钉钉.features"]


def test_analyze_threads_degraded_sink_on_extraction_failure(monkeypatch):
    # analyze() 把单竞品抽取降级汇聚进 degraded_sink(端到端:analyze_node 据此置 degraded)
    import rivalradar.agents.analyst as an
    monkeypatch.setattr(an, "extract_features",
                        lambda *a, **k: (_ for _ in ()).throw(StructuredCallError("boom")))
    monkeypatch.setattr(an, "extract_pricing", lambda *a, **k: PricingModel(model_type="x"))
    monkeypatch.setattr(an, "extract_personas", lambda *a, **k: [])
    monkeypatch.setattr(an, "extract_swot", lambda *a, **k: SWOT())
    monkeypatch.setattr(an, "build_comparison", lambda *a, **k: [])
    sink: list[str] = []
    ev = [Evidence(id="e1", competitor="Notion", dimension="core_workflows", content="c",
                   source_url="u", source_title="t", language="en", fetched_at="t0")]
    an.analyze(ev, ["Notion"], degraded_sink=sink, client=None, model="m")
    assert "Notion.features" in sink


def test_safe_extract_records_degrade_into_sink():
    # silent-failure 修复:降级必可见 —— label 记入 sink 供 analyze_node 置 run 级 degraded
    def boom():
        raise StructuredCallError("truncated")
    sink: list[str] = []
    _safe_extract("features", "钉钉", boom, [], sink=sink)
    assert sink == ["钉钉.features"]
    # 成功路径不污染 sink
    _safe_extract("pricing", "钉钉", lambda: PricingModel(model_type="x"), None, sink=sink)
    assert sink == ["钉钉.features"]


def test_analyze_threads_degraded_sink_on_extraction_failure(monkeypatch):
    # analyze() 把单竞品抽取降级汇聚进 degraded_sink(端到端:analyze_node 据此置 degraded)
    import rivalradar.agents.analyst as an
    monkeypatch.setattr(an, "extract_features",
                        lambda *a, **k: (_ for _ in ()).throw(StructuredCallError("boom")))
    monkeypatch.setattr(an, "extract_pricing", lambda *a, **k: PricingModel(model_type="x"))
    monkeypatch.setattr(an, "extract_personas", lambda *a, **k: [])
    monkeypatch.setattr(an, "extract_swot", lambda *a, **k: SWOT())
    monkeypatch.setattr(an, "build_comparison", lambda *a, **k: [])
    sink: list[str] = []
    ev = [Evidence(id="e1", competitor="Notion", dimension="core_workflows", content="c",
                   source_url="u", source_title="t", language="en", fetched_at="t0")]
    an.analyze(ev, ["Notion"], degraded_sink=sink, client=None, model="m")
    assert "Notion.features" in sink


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
    # 校验格式标记而非裸 id,避免 content 恰含 "e1" 时假阳性
    assert "[evidence_id=e1]" in block and "[evidence_id=e2]" in block


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


def _profile_payloads():
    # 顺序:features, pricing, personas, swot
    return [
        json.dumps({"items": [{"id": "f1", "name": "db", "description": "", "category": "core_workflows", "evidence_refs": []}]}),
        json.dumps({"model_type": "freemium", "tiers": [], "evidence_refs": []}),
        json.dumps({"personas": []}),
        json.dumps({"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}),
    ]


def test_analyze_competitor_assembles_profile():
    client = _FakeClient(_profile_payloads())
    prof = analyze_competitor([_ev("e1", "Notion", "core_workflows")], "Notion", client=client, model="m")
    assert isinstance(prof, CompetitorProfile)
    assert prof.name == "Notion" and prof.features[0].name == "db"
    assert prof.pricing.model_type == "freemium"


def test_build_comparison_returns_rows():
    payload = json.dumps({"rows": [{"dimension": "pricing", "cells": [
        {"competitor": "Notion", "value_type": "number", "value": "0", "evidence_refs": []}]}]})
    client = _FakeClient([payload])
    rows = build_comparison([CompetitorProfile(name="Notion",
                             pricing=PricingModel(model_type="freemium"), swot=SWOT())],
                            [_ev("e1", "Notion", "pricing")], client=client, model="m")
    assert rows[0].dimension == "pricing"


def test_analyze_end_to_end_with_fake_client():
    # 1 竞品:4 次抽取 + 1 次对比 = 5 次调用
    payloads = _profile_payloads() + [json.dumps({"rows": []})]
    client = _FakeClient(payloads)
    out = analyze([_ev("e1", "Notion", "core_workflows")], ["Notion"], client=client, model="m")
    assert isinstance(out, CompetitorAnalysis)
    assert out.competitors[0].name == "Notion"
    assert client.chat.completions.calls == 5


def test_analyze_threads_requested_dimensions_into_comparison(monkeypatch):
    """真 run 回归:analyze 把请求的 dimensions 穿进 build_comparison(约束对比范围),
    不再硬编码全 6 受控本体(否则分析员超范围产出 → 越界 hallucination + 质检覆盖死循环)。"""
    captured = {}

    def spy(profiles, evidence, *, dimensions, client, model):
        captured["dims"] = dimensions
        return []

    import rivalradar.agents.analyst as analyst_mod
    monkeypatch.setattr(analyst_mod, "build_comparison", spy)
    payloads = _profile_payloads()
    analyze([_ev("e1", "Notion", "pricing")], ["Notion"],
            dimensions=("pricing", "core_workflows"), client=_FakeClient(payloads), model="m")
    assert captured["dims"] == ("pricing", "core_workflows")


def test_analyze_two_competitors_aggregates_and_compares():
    # 2 竞品:每个 4 次抽取 + 1 次对比 = 9 次调用;对比 rows 真流入结果
    comparison = json.dumps({"rows": [{"dimension": "pricing", "cells": [
        {"competitor": "Notion", "value_type": "enum", "value": "freemium", "evidence_refs": []}]}]})
    client = _FakeClient(_profile_payloads() + _profile_payloads() + [comparison])
    out = analyze([_ev("e1", "Notion", "core_workflows"), _ev("e2", "飞书", "pricing")],
                  ["Notion", "飞书"], client=client, model="m")
    assert [c.name for c in out.competitors] == ["Notion", "飞书"]
    assert client.chat.completions.calls == 9
    assert out.comparison[0].dimension == "pricing"
