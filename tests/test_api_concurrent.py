"""并发安全 spike:WAL 下并发读写不死锁、不应 SQLITE_BUSY。

⚠️ 历史教训(opus reviewer Task 11):不要做"主线程跑 POST + poller 用 SSE 返回的
run_id"—— TestClient 的 portal.call 阻塞到 ASGI response_complete 才返回,主线程
在 POST 期间无法做任何事,poller 永远拿不到 run_id → 0 个真实 GET → assert errors
== [] 假绿。正确做法:POST 在**独立线程**跑(让 graph 在线程里写 evidence/trace),
主线程从 `GET /runs` 列表挑出 status=running 的 rid 后再发起并发 GET。
"""
import hashlib
import threading
import time

from fastapi.testclient import TestClient

from rivalradar.agents import qc
from rivalradar.api.app import create_app
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, CompetitorProfile,
    PricingModel, SWOT, EvidenceRef, ReportInsight,
)
from rivalradar.search.base import SearchResult
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


class _SlowProvider:
    """每次 search 故意 sleep 80ms,模拟真实网络延迟,拉长 graph 写窗口让并发读必然撞上。"""
    name = "slow"
    def search(self, query, *, max_results=5):
        time.sleep(0.08)
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="s",
                             raw_content="body for " + query)]


def _fake_analyze(evidence, competitors, *, dimensions=None, degraded_sink=None, client, model):
    profiles = []
    for c in competitors:
        ev = next((e for e in evidence if e.competitor == c
                   and e.dimension == "pricing"), None)
        refs = [EvidenceRef(evidence_id=ev.id, quote="q")] if ev else []
        profiles.append(CompetitorProfile(
            name=c, pricing=PricingModel(model_type="freemium", evidence_refs=refs),
            swot=SWOT()))
    return CompetitorAnalysis(competitors=profiles, comparison=[])


def _parse_sse(raw_bytes: bytes) -> list[dict]:
    events, cur = [], {}
    for line in raw_bytes.decode("utf-8").splitlines():
        if line == "":
            if cur:
                events.append(cur); cur = {}
        elif line.startswith("event: "):
            cur["event"] = line[7:]
        elif line.startswith("data: "):
            cur["data"] = line[6:]
    if cur:
        events.append(cur)
    return events


def _stub_graph_agents(monkeypatch):
    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _fake_analyze)
    monkeypatch.setattr("rivalradar.graph.nodes.write_report_with_insight",
                        lambda *a, **k: ("# 报告", ReportInsight(
                            market_context="m", differentiation_thesis="d",
                            actionable_takeaway="a")))
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])


def test_concurrent_post_writes_and_get_trace_reads_no_busy(tmp_path, monkeypatch):
    """1 写 + N 读并发:graph 节点写 evidence/trace 时,GET /trace 应 200 + 单调增长。"""
    db_path = str(tmp_path / "concurrent_rw.db")
    c = connect(db_path); init_db(c); c.close()
    _stub_graph_agents(monkeypatch)

    app = create_app(db_path=db_path, doubao_client="stub",
                     provider=_SlowProvider(), as_of="2026-05-26")
    client = TestClient(app)

    # POST 在独立线程跑(关键:不在主线程跑,否则 TestClient 阻塞到 SSE complete)
    post_result = {"sse": None, "exc": None}
    def _poster():
        try:
            r = client.post("/run", json={"competitors": ["Notion"],
                                          "dimensions": list(CONTROLLED_DIMENSIONS)})
            post_result["sse"] = (r.status_code, _parse_sse(r.content))
        except Exception as e:  # noqa: BLE001
            post_result["exc"] = e

    poster = threading.Thread(target=_poster)
    poster.start()

    # 主线程:每 50ms 调 /runs 拿到正在跑的 rid(POST 内 create_run 已落库)
    rid = None
    for _ in range(40):  # 最多 2s 等
        time.sleep(0.05)
        try:
            r = client.get("/runs")
            if r.status_code == 200:
                for run in r.json():
                    if run.get("status") == "running":
                        rid = run["run_id"]; break
            if rid:
                break
        except Exception:  # noqa: BLE001
            pass
    assert rid, "couldn't grab rid from /runs while POST was running"

    # 真并发读 GET /trace/{rid},验证 WAL 下不 BUSY + 快照单调
    read_errors = []
    prev_len = 0
    for _ in range(20):  # 20 × 30ms = 600ms 真并发窗口
        time.sleep(0.03)
        try:
            r = client.get(f"/trace/{rid}")
            assert r.status_code == 200, f"trace GET status {r.status_code}"
            data = r.json()
            assert isinstance(data, list)
            # append-only 写者,读者快照只能增长不能缩
            assert len(data) >= prev_len, f"trace shrank: {prev_len} → {len(data)}"
            prev_len = len(data)
        except Exception as e:  # noqa: BLE001
            read_errors.append(e)

    poster.join(timeout=5.0)
    assert not poster.is_alive(), "poster did not finish in 5s"
    assert post_result["exc"] is None, f"poster raised: {post_result['exc']}"
    assert post_result["sse"][0] == 200
    assert read_errors == [], f"concurrent reads failed: {read_errors}"
    # 并发窗口内至少看到 1 条 trace,证明真撞上了写窗口(否则就是 0 并发假绿)
    assert prev_len >= 1, f"concurrent window saw 0 trace — likely no real overlap"
    # 整图跑完后再读一次,验证 trace 完整(spike 的写完整性收尾断言)
    final = client.get(f"/trace/{rid}").json()
    assert len(final) >= 5, f"final trace has only {len(final)} entries (expect 5+ nodes)"


def test_concurrent_two_posts_no_busy(tmp_path, monkeypatch):
    """两条独立 POST /run 同时跑(WAL 多写场景),验证 SQLite 写锁不死锁、两 run 都完整落库。

    这才是真正会 SQLITE_BUSY 的路径:1 写 + N 读 WAL 文档保证不互斥,真风险是写写并发。"""
    db_path = str(tmp_path / "two_posts.db")
    c = connect(db_path); init_db(c); c.close()
    _stub_graph_agents(monkeypatch)

    app = create_app(db_path=db_path, doubao_client="stub",
                     provider=_SlowProvider(), as_of="2026-05-26")
    client = TestClient(app)

    results = {"a": None, "b": None}
    def _runner(key, comp):
        try:
            r = client.post("/run", json={"competitors": [comp],
                                          "dimensions": list(CONTROLLED_DIMENSIONS)})
            results[key] = ("ok", r.status_code, _parse_sse(r.content))
        except Exception as e:  # noqa: BLE001
            results[key] = ("err", repr(e), None)

    a = threading.Thread(target=_runner, args=("a", "Notion"))
    b = threading.Thread(target=_runner, args=("b", "Linear"))
    a.start(); b.start()
    a.join(timeout=15.0); b.join(timeout=15.0)
    assert not (a.is_alive() or b.is_alive()), "POST threads did not finish in 15s"

    for key in ("a", "b"):
        out = results[key]
        assert out is not None, f"{key} returned nothing"
        assert out[0] == "ok", f"{key} failed: {out[1]}"
        assert out[1] == 200, f"{key} HTTP {out[1]}"
        events = out[2]
        assert events[-1]["event"] == "done", f"{key} stream not ended cleanly"

    # 两 run 都落库 + 各自有 evidence(WAL 下写写并发完整性保障)
    c = connect(db_path); init_db(c)
    runs = repo.list_runs(c)
    assert len(runs) == 2, f"expected 2 runs, got {len(runs)}"
    for run in runs:
        evs = repo.list_evidence(c, run["run_id"])
        assert len(evs) > 0, f"run {run['run_id']} has no evidence"
    c.close()
