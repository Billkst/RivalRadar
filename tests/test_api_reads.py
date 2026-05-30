import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, Decision, DecisionSet, Evidence,
    EvidenceRef, PricingModel, QCIssue, QCResult, ReportInsight, SWOT,
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
    # full-C 决策管道产物(Epic 2.4):qc_result(含模型文本 detail)/ insight / decisions
    repo.save_qc_result(c, "r1", QCResult(verdict="pass", issues=[QCIssue(
        competitor="Notion", dimension="decision", problem_type="hallucination",
        detail="模型原话敏感片段 LEAK_xyz")]))
    repo.save_insight(c, "r1", ReportInsight(
        market_context="协同办公赛道", differentiation_thesis="因为X所以Y",
        actionable_takeaway="短/中/长"))
    repo.save_decisions(c, "r1", DecisionSet(decisions=[Decision(
        stance="建议采用", action="本周评估接入", horizon="短期",
        risk_reversibility="可逆", risk_cost="低", why="生态成熟",
        evidence_refs=[EvidenceRef(evidence_id="ev1", quote="q")])]))
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


# ── full-C 决策管道只读端点(Epic 2.4)──────────────────────────────────────
def test_get_qc_sanitized_strips_model_text(client):
    r = client.get("/qc/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "pass"
    issue = body["issues"][0]
    assert issue["competitor"] == "Notion" and issue["problem_type"] == "hallucination"
    assert "LEAK_xyz" not in issue["detail"]          # 关键:模型文本不泄漏(Codex #9)
    assert issue["detail"] == "证据未能支撑该结论"     # 罐装文案


def test_get_qc_404_when_missing(client):
    assert client.get("/qc/no_run").status_code == 404


def test_get_insight_returns_three_sections(client):
    r = client.get("/insight/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["market_context"] == "协同办公赛道"
    assert body["differentiation_thesis"] == "因为X所以Y"


def test_get_insight_404_when_missing(client):
    assert client.get("/insight/no_run").status_code == 404


def test_get_decisions_returns_decision_set(client):
    r = client.get("/decisions/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["decisions"][0]["action"] == "本周评估接入"
    assert body["decisions"][0]["stance"] == "建议采用"


def test_get_decisions_404_when_missing(client):
    assert client.get("/decisions/no_run").status_code == 404


def test_list_run_evidence_returns_list(client):
    r = client.get("/runs/r1/evidence")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1 and items[0]["id"] == "ev1"


def test_list_run_evidence_404_for_unknown_run(client):
    assert client.get("/runs/no_run/evidence").status_code == 404
