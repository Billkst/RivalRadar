import threading

from rivalradar.graph.nodes import _collect_round, make_collect_node
from rivalradar.search.base import SearchResult
from rivalradar.storage.db import connect, init_db
from rivalradar.storage.repository import create_run, list_queries


class _OneHitProvider:
    name = "mock"
    def search(self, query, *, max_results=5):
        return [SearchResult(url=f"https://x/{query}", title=f"T:{query}",
                             content="c", raw_content="body", provider="mock")]


def _capture_emit():
    events, lock = [], threading.Lock()
    def emit(ev_type, data):
        with lock:
            events.append((ev_type, data))
    return events, emit


def test_collect_node_emits_real_work_events():
    conn = connect(":memory:"); init_db(conn)
    create_run(conn, "run1", ["飞书"], ["pricing"])
    node = make_collect_node(conn=conn, provider=_OneHitProvider(), official_domains={})
    events, emit = _capture_emit()
    state = {"evidence": [], "competitors": ["飞书"], "dimensions": ["pricing"],
             "qc_result": None, "retry_count": 0}
    config = {"configurable": {"thread_id": "run1", "emit": emit}}

    out = node(state, config)

    kinds = [e[0] for e in events]
    assert "query" in kinds and "query_hit" in kinds and "source" in kinds and "evidence_delta" in kinds
    # 1 竞品 × 1 维 × 2 语 = 2 query
    assert kinds.count("query") == 2
    assert kinds.count("query_hit") == 2
    # query 事件带真实查询词 + round 0
    q_ev = [d for t, d in events if t == "query"]
    assert all(d["query_text"] and d["round"] == 0 for d in q_ev)
    assert {d["query_text"] for d in q_ev} == {"飞书 价格 套餐 收费", "飞书 pricing plans cost"}
    # source 事件带真实标题/url + 落库的 evidence_id + 采集日期(spec §5.2,前端算 stale 用)
    src = [d for t, d in events if t == "source"]
    assert all(d["source_title"].startswith("T:") and d["evidence_id"].startswith("ev_") for d in src)
    assert all(d["fetched_at"] for d in src)
    # evidence_delta round 汇总
    delta = [d for t, d in events if t == "evidence_delta"][0]
    assert delta["round"] == 0 and delta["added_count"] == len(out["evidence"])
    # queries 落库
    rows = list_queries(conn, "run1")
    assert len(rows) == 2 and all(r["round"] == 0 for r in rows)


def test_collect_round_first_pass_is_zero():
    # 首轮:无 qc_result → round 0
    assert _collect_round({"qc_result": None, "retry_count": 0}) == 0
    assert _collect_round({"retry_count": 0}) == 0


def test_collect_round_retry_derives_from_qc_presence():
    # 第一次 retry collect:qc_result 已存在但 retry_count 仍 0(qc 节点首轮不 +1)→ round 1
    assert _collect_round({"qc_result": {"verdict": "retry_collect"}, "retry_count": 0}) == 1
    # 第二次 retry:retry_count=1 → round 2
    assert _collect_round({"qc_result": {"verdict": "retry_collect"}, "retry_count": 1}) == 2
