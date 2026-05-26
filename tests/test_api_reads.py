import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, Evidence, PricingModel, SWOT,
)
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "reads.db")


@pytest.fixture()
def seeded(db_path):
    """种入 1 个 run + 1 条 evidence + analysis + report + 2 条 trace。"""
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    ev = Evidence(id="ev1", competitor="Notion", dimension="pricing",
                  content="$10/mo", source_url="https://notion.so/pricing",
                  source_title="Pricing", language="en",
                  fetched_at="2026-05-25T00:00:00Z")
    repo.insert_evidence(c, "r1", ev)
    repo.save_analysis(c, "r1", CompetitorAnalysis(competitors=[
        CompetitorProfile(name="Notion",
                          pricing=PricingModel(model_type="freemium"),
                          swot=SWOT())]))
    repo.save_report(c, "r1", "# 报告\n正文")
    repo.append_trace(c, "r1", "collect", input_summary="targets=all",
                      output_summary="+1", latency_ms=12)
    repo.append_trace(c, "r1", "analyze", input_summary="1 evidence",
                      output_summary="1 profiles", latency_ms=34)
    c.close()


@pytest.fixture()
def client(db_path, seeded):
    return TestClient(create_app(db_path=db_path))


def test_get_evidence_returns_pydantic(client):
    r = client.get("/evidence/ev1")
    assert r.status_code == 200
    body = r.json()
    assert body["competitor"] == "Notion"
    assert body["source_url"] == "https://notion.so/pricing"


def test_get_evidence_404_when_missing(client):
    r = client.get("/evidence/nonexistent")
    assert r.status_code == 404


def test_get_analysis_returns_competitor_analysis(client):
    r = client.get("/analysis/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["competitors"][0]["name"] == "Notion"


def test_get_analysis_404_when_missing(client):
    r = client.get("/analysis/no_run")
    assert r.status_code == 404


def test_get_report_returns_markdown(client):
    r = client.get("/report/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["markdown"].startswith("# 报告")


def test_get_report_404(client):
    r = client.get("/report/no_run")
    assert r.status_code == 404


def test_get_trace_returns_entries(client):
    r = client.get("/trace/r1")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert items[0]["node"] == "collect"
    assert items[1]["node"] == "analyze"
    assert items[1]["latency_ms"] == 34


def test_get_trace_empty_list_for_unknown_run(client):
    r = client.get("/trace/no_run")
    assert r.status_code == 200
    assert r.json() == []
