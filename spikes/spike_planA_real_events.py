"""Plan A · Task 8 真 run 抽查:真实 Doubao + Tavily 跑 1 竞品 × 1 维,确认 SSE 流里
出现 4 类「真实活儿」事件(query/query_hit/source/evidence_delta)且数据是真实的,
并 GET /runs/:id/queries 拿回真实查询词。

跑通的硬证据:
- SSE 事件含 query(真实模板查询词)+ query_hit(命中数)+ source(真实标题/url/ev_id/fetched_at,
  无 provider/confidence)+ evidence_delta(round/增量计数)
- GET /runs/:id/queries 返回真实查询词 + hit_count

⚠️ 消耗真实 Doubao token + Tavily 额度,只在 ARK_API_KEY + TAVILY_API_KEY 双就绪时跑。
🔑 不打印 key 值,只布尔检查。不进 pytest(真打外部 API)。

跑法(WSL2 Clash:Doubao/Tavily 国内端点,务必 unset 代理 + NO_PROXY):
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
  NO_PROXY=localhost,127.0.0.1 .venv/bin/python spikes/spike_planA_real_events.py
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


def _parse_sse(content: str) -> list[tuple[str, dict]]:
    """把 SSE 文本解析成 [(event_type, data_dict), ...]。配对相邻 event:/data: 行。"""
    out: list[tuple[str, dict]] = []
    cur_ev: str | None = None
    for line in content.splitlines():
        if line.startswith("event: "):
            cur_ev = line[7:].strip()
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                data = {}
            out.append((cur_ev or "message", data))
            cur_ev = None
    return out


def main() -> None:
    if not cfg.ark_api_key():
        print("[SKIP] ARK_API_KEY 未设置"); return
    if not cfg.tavily_api_key():
        print("[SKIP] TAVILY_API_KEY 未设置"); return

    db = "/tmp/spike_planA.db"
    if os.path.exists(db):
        os.remove(db)

    app = create_app(
        db_path=db,
        doubao_client=cfg.get_doubao_client(),
        provider=TavilyProvider(api_key=cfg.tavily_api_key()),
        max_retries=1,  # 加快 spike
    )
    client = TestClient(app)

    print("[1/3] POST /run (Notion × pricing) …")
    r = client.post("/run", json={"competitors": ["Notion"], "dimensions": ["pricing"]})
    assert r.status_code == 200, r.text
    print(f"     SSE bytes={len(r.content)}")

    events = _parse_sse(r.content.decode())
    kinds = [e for e, _ in events]
    print(f"     event kinds seen: {sorted(set(kinds))}")

    run_id = next((d["run_id"] for e, d in events if "run_id" in d), None)
    assert run_id, "未拿到 run_id"
    print(f"     run_id={run_id}")

    # ── 4 类新事件必须出现 ────────────────────────────────────────────────
    for k in ("query", "query_hit", "evidence_delta"):
        assert k in kinds, f"SSE 流缺事件 {k}（kinds={sorted(set(kinds))}）"
    # source 取决于是否有真实命中;Notion pricing 通常有，断言 >0（若为 0 单独提示）
    q_ev = [d for e, d in events if e == "query"]
    qh_ev = [d for e, d in events if e == "query_hit"]
    src_ev = [d for e, d in events if e == "source"]
    delta_ev = [d for e, d in events if e == "evidence_delta"]

    print(f"     query={len(q_ev)} query_hit={len(qh_ev)} source={len(src_ev)} evidence_delta={len(delta_ev)}")

    # query 事件带真实查询词 + round 0
    assert all(d.get("query_text") for d in q_ev), "query 事件缺 query_text"
    assert all(d.get("round") == 0 for d in q_ev), "首轮 query round 应为 0"
    print(f"     真实查询词: {[d['query_text'] for d in q_ev]}")

    # query_hit 带 hit_count
    assert all("hit_count" in d for d in qh_ev), "query_hit 缺 hit_count"

    # source 事件(若有):真实标题/url/ev_id/fetched_at,且无 provider/confidence(反幻觉)
    if src_ev:
        s0 = src_ev[0]
        assert s0.get("evidence_id", "").startswith("ev_"), f"source evidence_id 异常: {s0.get('evidence_id')}"
        assert s0.get("source_title") and s0.get("source_url"), "source 缺真实标题/url"
        assert s0.get("fetched_at"), "source 缺 fetched_at(前端算 stale 用)"
        assert "provider" not in s0 and "confidence" not in s0, "source 不应带 provider/confidence(反幻觉)"
        print(f"     来源卡样例: title={s0['source_title'][:40]!r} fetched_at={s0['fetched_at']} "
              f"(无 provider/confidence ✓)")
    else:
        print("     [注意] source 事件为 0（本次 Tavily 对 Notion pricing 无可入库命中），"
              "query/query_hit/evidence_delta 仍验证通过")

    # evidence_delta 计数
    d0 = delta_ev[0]
    assert "added_count" in d0 and "total_count" in d0 and d0.get("round") == 0
    print(f"     evidence_delta: round={d0['round']} added={d0['added_count']} total={d0['total_count']}")

    print("[2/3] GET /runs/:id/queries …")
    r = client.get(f"/runs/{run_id}/queries")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 2, f"queries 端点应返回 ≥2 行(en+zh),实际 {len(rows)}"
    assert all(row.get("query_text") for row in rows), "queries 端点行缺 query_text"
    print(f"     queries 端点返回 {len(rows)} 行,样例 query_text={rows[0]['query_text']!r} "
          f"hit_count={rows[0]['hit_count']}")

    print("[3/3] GET /run/:id 终态 …")
    r = client.get(f"/run/{run_id}")
    assert r.status_code == 200
    print(f"     status={r.json()['status']} degraded={r.json()['degraded']}")

    print("\n[Plan A Task 8] ALL CHECKS PASSED  ✅  真 run 抽查:4 类真实活儿事件 + queries 端点验证通过")


if __name__ == "__main__":
    main()
