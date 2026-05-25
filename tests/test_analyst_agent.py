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
