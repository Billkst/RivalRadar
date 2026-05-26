import pytest

from rivalradar.schema.models import (
    CompetitorAnalysis,
    CompetitorProfile,
    Evidence,
    PricingModel,
    SWOT,
)
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


def _evidence(eid="e1"):
    return Evidence(
        id=eid, competitor="Notion", dimension="pricing", content="$10/mo",
        source_url="https://notion.so/pricing", source_title="Pricing",
        language="en", fetched_at="2026-05-25T00:00:00Z",
    )


def test_evidence_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.insert_evidence(conn, "r1", _evidence("e1"))
    repo.insert_evidence(conn, "r1", _evidence("e2"))
    got = repo.get_evidence(conn, "e1")
    assert got == _evidence("e1")
    assert {e.id for e in repo.list_evidence(conn, "r1")} == {"e1", "e2"}


def test_get_missing_evidence_returns_none(conn):
    assert repo.get_evidence(conn, "nope") is None


def test_analysis_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="freemium"), swot=SWOT(),
    )])
    repo.save_analysis(conn, "r1", analysis)
    assert repo.get_analysis(conn, "r1") == analysis


def test_report_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.save_report(conn, "r1", "# Notion\n...")
    assert repo.get_report(conn, "r1") == "# Notion\n..."


def test_trace_append_preserves_order(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.append_trace(conn, "r1", "collect", prompt="p1", input_summary="i1",
                      output_summary="o1", tokens=100, latency_ms=1200)
    repo.append_trace(conn, "r1", "analyze", prompt="p2", input_summary="i2",
                      output_summary="o2", tokens=200, latency_ms=2400)
    rows = repo.list_trace(conn, "r1")
    assert [t["node"] for t in rows] == ["collect", "analyze"]
    assert rows[0]["tokens"] == 100


def test_run_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion", "飞书"], ["pricing", "features"])
    run = repo.get_run(conn, "r1")
    assert run["competitors"] == ["Notion", "飞书"]
    assert run["status"] == "running"


def test_update_run_status(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(conn, "r1", "done")
    assert repo.get_run(conn, "r1")["status"] == "done"


def test_list_runs_orders_newest_first(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.create_run(conn, "r2", ["Linear"], ["pricing"])
    runs = repo.list_runs(conn)
    assert [r["run_id"] for r in runs] == ["r2", "r1"]
    assert runs[0]["status"] == "running"


def test_annotation_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    aid = repo.insert_annotation(
        conn, run_id="r1", evidence_id="ev1",
        conclusion_path="competitors[0].swot.strengths[0]", note="此处存疑")
    assert isinstance(aid, int) and aid > 0
    rows = repo.list_annotations(conn, "r1")
    assert len(rows) == 1
    assert rows[0]["note"] == "此处存疑"
    assert rows[0]["evidence_id"] == "ev1"


def test_annotation_evidence_id_optional(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.insert_annotation(conn, run_id="r1", evidence_id=None,
                           conclusion_path="competitors[0]", note="整体可疑")
    rows = repo.list_annotations(conn, "r1")
    assert rows[0]["evidence_id"] is None
