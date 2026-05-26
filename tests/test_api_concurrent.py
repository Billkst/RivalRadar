"""并发安全 spike:WAL 下 POST /run 写 + 并发 GET /trace 读不应死锁、不应 SQLITE_BUSY。

注意:TestClient 是同步的,真正"并行"用线程开两路。"""
import hashlib
import json
import threading
import time
import pytest

from fastapi.testclient import TestClient

from rivalradar.agents import qc
from rivalradar.api.app import create_app
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, CompetitorProfile,
    PricingModel, SWOT, ComparisonRow, ComparisonCell, EvidenceRef,
)
from rivalradar.search.base import SearchResult
from rivalradar.storage.db import connect, init_db


class _SlowProvider:
    """每次 search 故意 sleep 80ms,模拟真实网络延迟,拉长写窗口让并发读必然撞上。"""
    name = "slow"
    def search(self, query, *, max_results=5):
        time.sleep(0.08)
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="s",
                             raw_content="body for " + query)]


def _fake_analyze(evidence, competitors, *, client, model):
    profiles = []
    for c in competitors:
        ev = next((e for e in evidence if e.competitor == c
                   and e.dimension == "pricing"), None)
        refs = [EvidenceRef(evidence_id=ev.id, quote="q")] if ev else []
        profiles.append(CompetitorProfile(
            name=c, pricing=PricingModel(model_type="freemium", evidence_refs=refs),
            swot=SWOT()))
    return CompetitorAnalysis(competitors=profiles, comparison=[])


def test_concurrent_post_and_get_trace_no_busy(tmp_path, monkeypatch):
    db_path = str(tmp_path / "concurrent.db")
    # 初始化(让 WAL 模式落到磁盘 + 表就绪)
    c = connect(db_path); init_db(c); c.close()

    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _fake_analyze)
    monkeypatch.setattr("rivalradar.graph.nodes.write_report",
                        lambda *a, **k: "# 报告")
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])

    app = create_app(db_path=db_path, doubao_client="stub",
                     provider=_SlowProvider(), as_of="2026-05-26")
    client = TestClient(app)

    # 后台并发拉 /trace/(POST 进行中)
    errors = []
    def _poll_traces(run_id_ref):
        for _ in range(20):  # 20 * 30ms = 600ms,覆盖 POST 跑图时长
            time.sleep(0.03)
            rid = run_id_ref.get("v")
            if not rid:
                continue
            try:
                r = client.get(f"/trace/{rid}")
                assert r.status_code == 200
                # 读出来的 trace 必须是合法 JSON 列表
                assert isinstance(r.json(), list)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

    run_id_ref = {"v": None}
    poller = threading.Thread(target=_poll_traces, args=(run_id_ref,))
    poller.start()

    r = client.post("/run", json={"competitors": ["Notion"],
                                   "dimensions": list(CONTROLLED_DIMENSIONS)})
    assert r.status_code == 200
    # 拿到 run_id 后让 poller 锁定
    events = []
    for line in r.content.decode().splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    rid = next((d["run_id"] for d in events if "run_id" in d), None)
    assert rid
    run_id_ref["v"] = rid
    poller.join(timeout=3.0)

    assert errors == [], f"concurrent reads failed: {errors}"
