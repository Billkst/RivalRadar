import pytest

from rivalradar.schema.models import (
    CompetitorAnalysis,
    CompetitorProfile,
    Decision,
    DecisionSet,
    Evidence,
    EvidenceRef,
    PricingModel,
    QCIssue,
    QCResult,
    ReportInsight,
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


def test_decisions_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    ds = DecisionSet(decisions=[Decision(
        stance="建议采用", action="本周评估飞书审批", horizon="短期",
        risk_reversibility="可逆", risk_cost="低", why="生态成熟",
        evidence_refs=[EvidenceRef(evidence_id="e1", quote="q")])])
    repo.save_decisions(conn, "r1", ds)
    assert repo.get_decisions(conn, "r1") == ds


def test_get_decisions_none_for_old_run(conn):
    """老 run(decisions 表无行)→ get 返 None(GET /decisions 据此 404,天然 null 态)。"""
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    assert repo.get_decisions(conn, "r1") is None


def test_qc_result_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    result = QCResult(verdict="retry_analyze", issues=[QCIssue(
        competitor="*", dimension="decision", problem_type="hallucination", detail="模型文本")])
    repo.save_qc_result(conn, "r1", result)
    assert repo.get_qc_result(conn, "r1") == result
    assert repo.get_qc_result(conn, "no_run") is None


def test_insight_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    ins = ReportInsight(market_context="赛道", differentiation_thesis="因为X所以Y",
                        actionable_takeaway="短/中/长")
    repo.save_insight(conn, "r1", ins)
    assert repo.get_insight(conn, "r1") == ins
    assert repo.get_insight(conn, "no_run") is None


def test_create_run_persists_decision_context(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"], decision_context="选型PM:要不要采购飞书")
    assert repo.get_run(conn, "r1")["decision_context"] == "选型PM:要不要采购飞书"


def test_create_run_defaults_empty_decision_context(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    assert repo.get_run(conn, "r1")["decision_context"] == ""


def test_insert_evidence_same_id_across_runs_no_integrity_error(conn):
    """ship round-2 (Codex Critical #2):evidence.id 派生自 (comp|dim|url),
    多次跑同 competitor+dimension+url 必然撞同 id。旧 schema 单列 PRIMARY KEY (id)
    会触 IntegrityError 让 SSE 流崩(Codex 实测复现)。
    新 schema 复合 PRIMARY KEY (run_id, id) 让不同 run 各持一份 evidence 副本,
    重跑无冲突;同 run 重插同 id 走 INSERT OR IGNORE 安全降级。"""
    repo.create_run(conn, "r_a", ["Notion"], ["pricing"])
    repo.create_run(conn, "r_b", ["Notion"], ["pricing"])
    # run_a 和 run_b 都 insert 同一个 evidence id（重跑同 competitor+dim+url 的真实场景）
    repo.insert_evidence(conn, "r_a", _evidence("ev_shared"))
    repo.insert_evidence(conn, "r_b", _evidence("ev_shared"))  # 旧 schema 会 IntegrityError
    # 两个 run 各自能查到 evidence
    assert {e.id for e in repo.list_evidence(conn, "r_a")} == {"ev_shared"}
    assert {e.id for e in repo.list_evidence(conn, "r_b")} == {"ev_shared"}
    # 同 run 重插同 id 走 OR IGNORE,不报错,不重复
    repo.insert_evidence(conn, "r_a", _evidence("ev_shared"))
    assert len(repo.list_evidence(conn, "r_a")) == 1


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


def test_update_run_degraded(conn):
    """update_run_degraded 持久化蕴含降级标志;False 后再 True 可覆写。"""
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    assert repo.get_run(conn, "r1")["degraded"] is False  # 默认 0
    repo.update_run_degraded(conn, "r1", True)
    assert repo.get_run(conn, "r1")["degraded"] is True
    repo.update_run_degraded(conn, "r1", False)
    assert repo.get_run(conn, "r1")["degraded"] is False


def test_list_runs_respects_limit(conn):
    """list_runs(limit=N) 只返最多 N 条。"""
    for i in range(5):
        repo.create_run(conn, f"r{i}", ["Notion"], ["pricing"])
    runs = repo.list_runs(conn, limit=3)
    assert len(runs) == 3
