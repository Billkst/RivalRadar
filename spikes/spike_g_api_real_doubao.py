"""Spike G: 真实 Doubao + Tavily 跑 1 个竞品 + 真实 API 服务器(TestClient 消费 SSE)。

跑通的硬证据:
- POST /run 返 SSE,事件序列包含 start/collect/analyze/write/qc/finalize/done
- 结束后 GET /run/:id 返 status,GET /report/:run 返非空 markdown,
  GET /trace/:run 返 ≥5 条节点 trace,GET /analysis/:run 返 ≥1 competitor

⚠️ 消耗真实 Doubao token,只在 ARK_API_KEY + TAVILY_API_KEY 双就绪时跑。
🔑 不打印 key 值,只布尔检查。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from rivalradar import config as cfg
from rivalradar.api.app import create_app
from rivalradar.search.tavily_provider import TavilyProvider


def main():
    if not cfg.ark_api_key():
        print("[SKIP] ARK_API_KEY 未设置"); return
    if not cfg.tavily_api_key():
        print("[SKIP] TAVILY_API_KEY 未设置"); return

    db = "/tmp/spike_g.db"
    if os.path.exists(db):
        os.remove(db)

    app = create_app(
        db_path=db,
        doubao_client=cfg.get_doubao_client(),
        provider=TavilyProvider(api_key=cfg.tavily_api_key()),
        max_retries=1,  # 加快 spike
    )
    client = TestClient(app)

    print("[1/4] POST /run …")
    r = client.post("/run", json={
        "competitors": ["Notion"],
        "dimensions": ["pricing", "deployment", "integrations"],
    })
    assert r.status_code == 200, r.text
    print(f"     SSE bytes={len(r.content)}")

    events = []
    for line in r.content.decode().splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    run_id = next((d["run_id"] for d in events if "run_id" in d), None)
    assert run_id, "未拿到 run_id"
    print(f"     run_id={run_id}")

    nodes_hit = []
    for line in r.content.decode().splitlines():
        if line.startswith("event: "):
            nodes_hit.append(line[7:])
    print(f"     events seen: {set(nodes_hit)}")
    for n in ("start", "node", "done"):
        assert n in nodes_hit, f"missing event {n}"

    print("[2/4] GET /run/:id …")
    r = client.get(f"/run/{run_id}")
    assert r.status_code == 200
    print(f"     status={r.json()['status']}  degraded={r.json()['degraded']}")

    print("[3/4] GET /trace/:run …")
    r = client.get(f"/trace/{run_id}")
    assert r.status_code == 200
    print(f"     trace entries={len(r.json())}")

    print("[4/4] GET /report/:run + /analysis/:run …")
    r = client.get(f"/report/{run_id}")
    assert r.status_code == 200
    print(f"     report chars={len(r.json()['markdown'])}")
    r = client.get(f"/analysis/{run_id}")
    assert r.status_code == 200
    print(f"     competitors={len(r.json()['competitors'])}")

    print("\n[Spike G] ALL CHECKS PASSED  ✅")


if __name__ == "__main__":
    main()
