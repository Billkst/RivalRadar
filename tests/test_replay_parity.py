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


def test_replay_reconstructs_retry_count_from_qc_trace_rows(tmp_path):
    """ship-review P2:retryCount 由 trace 的 qc 行数推(qc_rounds - 1),不用 queries.round。
    关键 retry_analyze 场景:queries 全 round 0(重分析不重采集,无新 query 轮),但 qc 跑了 2 轮
    (2 个 qc trace 行)→ retry_count 必须是 1。旧 max(queries.round) 在此会错算成 0。"""
    from rivalradar.schema.models import QCResult
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    # 全 round 0:模拟 retry_analyze(没有 broaden 采集,故无 round>0 query)
    repo.insert_queries(c, "r1", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "q0", "round": 0, "hit_count": 1},
    ])
    _seed_analysis(c, "r1")
    repo.save_qc_result(c, "r1", QCResult(verdict="pass", issues=[]))
    # 2 个 qc trace 行 = 2 轮质检 = 自我纠错 1 次
    repo.append_trace(c, "r1", "qc", output_summary="verdict=retry_analyze", latency_ms=10)
    repo.append_trace(c, "r1", "qc", output_summary="verdict=pass", latency_ms=10)
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    qc_nodes = [json.loads(e["data"]) for e in events
                if e["event"] == "node" and json.loads(e["data"]).get("node") == "qc"]
    assert len(qc_nodes) == 1
    assert qc_nodes[0]["summary"]["retry_count"] == 1  # trace qc 行数 2 - 1(queries.round 全 0)
    assert qc_nodes[0]["summary"]["verdict"] == "pass"


def test_replay_single_qc_round_retry_count_zero(tmp_path):
    """一次性通过(1 个 qc trace 行)→ retry_count 0;无 qc trace 也安全 max(0, -1)=0。"""
    from rivalradar.schema.models import QCResult
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    _seed_analysis(c, "r1")
    repo.save_qc_result(c, "r1", QCResult(verdict="pass", issues=[]))
    repo.append_trace(c, "r1", "qc", output_summary="verdict=pass", latency_ms=10)
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    qc = next(json.loads(e["data"]) for e in events
              if e["event"] == "node" and json.loads(e["data"]).get("node") == "qc")
    assert qc["summary"]["retry_count"] == 0


def test_replay_qc_node_aggregates_issue_types(tmp_path):
    """ship-review P2:合成 qc node 的 issue_types 从终态 issues 聚合 problem_type,不硬编码 {}
    (否则前端「问题类型(N 项)」列表空白)。"""
    from rivalradar.schema.models import QCResult, QCIssue
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    _seed_analysis(c, "r1")
    repo.save_qc_result(c, "r1", QCResult(verdict="insufficient_evidence", issues=[
        QCIssue(competitor="飞书", dimension="pricing", problem_type="low_coverage", detail="x"),
        QCIssue(competitor="钉钉", dimension="pricing", problem_type="low_coverage", detail="y"),
        QCIssue(competitor="飞书", dimension="core_workflows", problem_type="missing_evidence", detail="z"),
    ]))
    repo.append_trace(c, "r1", "qc", output_summary="verdict=insufficient_evidence", latency_ms=10)
    repo.update_run_status(c, "r1", "insufficient_evidence")

    events = _replay(c, "r1")
    qc = next(json.loads(e["data"]) for e in events
              if e["event"] == "node" and json.loads(e["data"]).get("node") == "qc")
    assert qc["summary"]["issues"] == 3
    assert qc["summary"]["issue_types"] == {"low_coverage": 2, "missing_evidence": 1}


def test_replay_qc_node_carries_degraded(tmp_path):
    """ship-review P2(workflow test-adequacy):降级 run replay 时合成 qc node summary.degraded=True,
    前端据此显降级横幅。原测试只覆盖 degraded=False 路。"""
    from rivalradar.schema.models import QCResult
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    _seed_analysis(c, "r1")
    repo.save_qc_result(c, "r1", QCResult(verdict="pass", issues=[]))
    repo.append_trace(c, "r1", "qc", output_summary="verdict=pass", latency_ms=10)
    repo.update_run_degraded(c, "r1", True)
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    qc = next(json.loads(e["data"]) for e in events
              if e["event"] == "node" and json.loads(e["data"]).get("node") == "qc")
    assert qc["summary"]["degraded"] is True


def test_replay_absent_dim_with_evidence_marks_failed_not_empty(tmp_path):
    """ship-review honesty P2:缺维若有该维证据 → 标 failed(分析过无产出),不标 empty(否则前端
    「未找到公开数据」把"我们没产出"谎报成"市场无数据")。无证据维仍 empty。"""
    from rivalradar.schema.models import Evidence
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    # 请求 3 维;analysis 只有 pricing+core_workflows;integrations 有证据但无 row(分析失败);
    # review_sentiment 无证据无 row(确实空)。
    repo.create_run(c, "r1", ["飞书", "钉钉"],
                    ["pricing", "core_workflows", "integrations", "review_sentiment"])
    _seed_analysis(c, "r1")
    repo.insert_evidence(c, "r1", Evidence(
        id="ev_integ", competitor="飞书", dimension="integrations", content="开放平台",
        source_url="https://open.feishu.cn", source_title="开放平台", language="zh",
        fetched_at="2026-05-28T10:00:03Z"))
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    by_dim = {r["dimension"]: r for r in
              (json.loads(e["data"]) for e in events if e["event"] == "cell_row")}
    assert by_dim["integrations"]["status"] == "failed"   # 有证据 → 分析失败,非"无数据"
    assert by_dim["review_sentiment"]["status"] == "empty"  # 无证据 → 确实空
    assert by_dim["pricing"]["status"] == "ok"


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
