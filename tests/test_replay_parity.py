import asyncio
import json

from rivalradar.api.sse import _replay_from_trace
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


async def _collect(gen):
    out = []
    async for ev in gen:
        out.append(ev)
    return out


def _replay(conn, run_id):
    return asyncio.run(_collect(_replay_from_trace(conn, run_id, pacing=0.0)))


def _seed_analysis(c, run_id):
    """造 2 维 × 真 support_verdict 的 curated analysis(unsupported 已被 curate 丢弃,
    故只放 supported/partial,模拟落库后形态)。"""
    from rivalradar.schema.models import (
        CompetitorAnalysis, ComparisonRow, ComparisonCell, EvidenceRef)
    analysis = CompetitorAnalysis(comparison=[
        ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="飞书", value_type="quote_text",
                           value="商业版按人/月", support_verdict="supported",
                           evidence_refs=[EvidenceRef(evidence_id="ev_1", quote="¥/人/月")]),
            ComparisonCell(competitor="钉钉", value_type="quote_text",
                           value="专业版年付", support_verdict="partial"),
        ]),
        ComparisonRow(dimension="core_workflows", cells=[
            ComparisonCell(competitor="飞书", value_type="quote_text",
                           value="一体化协作", support_verdict="supported"),
        ]),
    ])
    repo.save_analysis(c, run_id, analysis)


def test_replay_reconstructs_query_and_query_hit(tmp_path):
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_queries(c, "r1", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 定价 套餐", "round": 0, "hit_count": 4},
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 商业版 价格", "round": 1, "hit_count": 0},
    ])
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    queries = [json.loads(e["data"]) for e in events if e["event"] == "query"]
    hits = [json.loads(e["data"]) for e in events if e["event"] == "query_hit"]
    assert [q["query_text"] for q in queries] == ["飞书 定价 套餐", "飞书 商业版 价格"]
    assert [q["round"] for q in queries] == [0, 1]
    assert [h["hit_count"] for h in hits] == [4, 0]
    assert hits[1]["hit_count"] == 0


def test_replay_reconstructs_source_cards(tmp_path):
    from rivalradar.schema.models import Evidence
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_evidence(c, "r1", Evidence(
        id="ev_1", competitor="飞书", dimension="pricing",
        content="商业版按人/月计费", source_url="https://www.feishu.cn/price",
        source_title="飞书定价 - 官网", language="zh", fetched_at="2026-05-28T10:00:03Z"))
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    sources = [json.loads(e["data"]) for e in events if e["event"] == "source"]
    assert len(sources) == 1
    s = sources[0]
    assert s["evidence_id"] == "ev_1"
    assert s["source_title"] == "飞书定价 - 官网"
    assert s["source_url"] == "https://www.feishu.cn/price"
    assert s["fetched_at"] == "2026-05-28T10:00:03Z"
    assert s["round"] == 0
    assert "provider" not in s and "confidence" not in s


def test_replay_reconstructs_cell_row_per_dimension(tmp_path):
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书", "钉钉"], ["pricing", "core_workflows"])
    _seed_analysis(c, "r1")
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    rows = [json.loads(e["data"]) for e in events if e["event"] == "cell_row"]
    ok_rows = [r for r in rows if r["status"] == "ok"]
    assert [r["dimension"] for r in ok_rows] == ["pricing", "core_workflows"]
    pricing = ok_rows[0]
    assert [cell["competitor"] for cell in pricing["cells"]] == ["飞书", "钉钉"]
    assert pricing["cells"][0]["evidence_refs"] == [{"evidence_id": "ev_1", "quote": "¥/人/月"}]
    assert "support_verdict" not in pricing["cells"][0]


def test_replay_emits_empty_cell_row_for_dimension_absent_from_analysis(tmp_path):
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书", "钉钉"],
                    ["pricing", "core_workflows", "review_sentiment"])
    _seed_analysis(c, "r1")
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    rows = [json.loads(e["data"]) for e in events if e["event"] == "cell_row"]
    by_dim = {r["dimension"]: r for r in rows}
    assert by_dim["review_sentiment"]["status"] == "empty"
    assert by_dim["review_sentiment"]["cells"] == []
    assert by_dim["pricing"]["status"] == "ok"


def test_replay_reconstructs_verdict_recheck(tmp_path):
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书", "钉钉"], ["pricing", "core_workflows"])
    _seed_analysis(c, "r1")
    repo.replace_curation_drops(c, "r1", "cell", [
        {"competitor": "钉钉", "dimension": "review_sentiment",
         "detail": "引用证据不支撑结论,策展剔除"},
    ])
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    vr = [json.loads(e["data"]) for e in events if e["event"] == "verdict_recheck"]
    assert len(vr) == 1
    v = vr[0]
    verdicts = {(cv["dimension"], cv["competitor"]): cv["support_verdict"]
                for cv in v["cell_verdicts"]}
    assert verdicts[("pricing", "飞书")] == "supported"
    assert verdicts[("pricing", "钉钉")] == "partial"
    assert v["dropped"] == [{"dimension": "review_sentiment", "competitor": "钉钉",
                             "detail": "引用证据不支撑结论,策展剔除"}]
    assert v["summary"] == {"supported": 2, "partial": 1, "dropped": 1}
    assert v["downgraded"] == [{"dimension": "pricing", "competitor": "钉钉",
                                "support_verdict": "partial"}]
    assert "decision_verdicts" not in v


def test_replay_reconstructs_retry_count_from_query_rounds(tmp_path):
    from rivalradar.schema.models import QCResult
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_queries(c, "r1", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "q0", "round": 0, "hit_count": 1},
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "q1 broaden", "round": 1, "hit_count": 2},
    ])
    _seed_analysis(c, "r1")
    repo.save_qc_result(c, "r1", QCResult(verdict="pass", issues=[]))
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    qc_nodes = [json.loads(e["data"]) for e in events
                if e["event"] == "node" and json.loads(e["data"]).get("node") == "qc"]
    assert len(qc_nodes) == 1
    assert qc_nodes[0]["summary"]["retry_count"] == 1
    assert qc_nodes[0]["summary"]["verdict"] == "pass"


def test_replay_no_analysis_emits_no_cell_or_verdict(tmp_path):
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r2", ["飞书"], ["pricing"])
    repo.update_run_status(c, "r2", "failed")
    events = _replay(c, "r2")
    assert not any(e["event"] in ("cell_row", "verdict_recheck", "node") for e in events)
    assert events[0]["event"] == "start"
    assert events[-1]["event"] == "done"
    assert json.loads(events[-1]["data"])["status"] == "failed"


def test_replay_event_order_and_trace_preserved(tmp_path):
    from rivalradar.schema.models import Evidence
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_queries(c, "r1", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 定价", "round": 0, "hit_count": 1}])
    repo.insert_evidence(c, "r1", Evidence(
        id="ev_1", competitor="飞书", dimension="pricing", content="x",
        source_url="https://feishu.cn", source_title="官网", language="zh",
        fetched_at="2026-05-28T10:00:03Z"))
    _seed_analysis(c, "r1")
    repo.append_trace(c, "r1", "collect", output_summary="+1", latency_ms=10)
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    order = [e["event"] for e in events]
    assert order[0] == "start" and order[-1] == "done"
    assert order.index("query") < order.index("cell_row") < order.index("verdict_recheck")
    assert order.index("verdict_recheck") < order.index("trace")
    assert "trace" in order
