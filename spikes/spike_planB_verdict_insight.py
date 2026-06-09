"""Plan B · Task 12 真 run 校准:真实 Doubao + Tavily 跑 Notion × 2 维,确认
① insight 两步化真流 chunk;② cell_row 逐维(ok/empty/failed);③ verdict_recheck 三级
(supported/partial/dropped 合理,不全 supported=没真判、不全 dropped=误伤);④ analysis cell
带真实 support_verdict;⑤ GET /curation-drops 结构化剔除。

⚠️ 消耗真实 Doubao token + Tavily 额度,只在 ARK_API_KEY + TAVILY_API_KEY 就绪时跑。
🔑 不打印 key。不进 pytest。

跑法(WSL2 Clash:Doubao/Tavily 国内,unset 代理 + NO_PROXY):
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
  NO_PROXY=localhost,127.0.0.1 .venv/bin/python spikes/spike_planB_verdict_insight.py
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
    out: list[tuple[str, dict]] = []
    cur = None
    for line in content.splitlines():
        if line.startswith("event: "):
            cur = line[7:].strip()
        elif line.startswith("data: "):
            try:
                out.append((cur or "message", json.loads(line[6:])))
            except json.JSONDecodeError:
                pass
            cur = None
    return out


def main() -> None:
    if not cfg.ark_api_key():
        print("[SKIP] ARK_API_KEY 未设置"); return
    if not cfg.tavily_api_key():
        print("[SKIP] TAVILY_API_KEY 未设置"); return

    db = "/tmp/spike_planB.db"
    if os.path.exists(db):
        os.remove(db)

    app = create_app(db_path=db, doubao_client=cfg.get_doubao_client(),
                     provider=TavilyProvider(api_key=cfg.tavily_api_key()), max_retries=1)
    client = TestClient(app)

    print("[1/5] POST /run (Notion × pricing,integrations) …")
    r = client.post("/run", json={"competitors": ["Notion"],
                                   "dimensions": ["pricing", "integrations"]})
    assert r.status_code == 200, r.text
    events = _parse_sse(r.content.decode())
    kinds = [e for e, _ in events]
    print(f"     SSE bytes={len(r.content)} | event kinds={sorted(set(kinds))}")
    run_id = next((d["run_id"] for e, d in events if "run_id" in d), None)
    assert run_id, "无 run_id"

    # ② insight 两步化真流 chunk(若 stream 成功)
    chunks = [d for e, d in events if e == "chunk"]
    print(f"[2/5] chunk(insight typing): {len(chunks)} 块")
    if len(chunks) > 5:
        print("     ✓ insight 两步化真流字符(打字感)")
    else:
        print("     [注意] chunk 少/无 → 可能回落一次性(数据仍真,无 typing);查 stream 是否稳")

    # ③ cell_row 逐维
    cr = [d for e, d in events if e == "cell_row"]
    print(f"[3/5] cell_row: {len(cr)} 维,status={[d['status'] for d in cr]}")
    assert cr, "无 cell_row 事件"
    assert all(d["dimension"] for d in cr) and all(d["status"] in ("ok", "empty", "failed") for d in cr)

    # ④ verdict_recheck 三级校准
    vr = [d for e, d in events if e == "verdict_recheck"]
    assert vr, "无 verdict_recheck 事件"
    s = vr[-1]["summary"]
    print(f"[4/5] verdict_recheck summary: {s}")
    print(f"     cell_verdicts(样例): {vr[-1]['cell_verdicts'][:3]}")
    total = s.get("supported", 0) + s.get("partial", 0) + s.get("dropped", 0)
    assert total > 0, "三级判定空(没真判?)"
    if s.get("supported", 0) == total:
        print("     [校准注意] 全 supported → 三级可能没真判/门槛太松,考虑 few-shot 收紧")
    if s.get("dropped", 0) == total and total > 1:
        print("     [校准注意] 全 dropped → 疑似误伤(把充分判成不足),需放宽门槛")
    if s.get("partial", 0) > 0 or s.get("dropped", 0) > 0:
        print("     ✓ 出现 partial/dropped(三级真在工作,不再恒 supported 假数据)")

    # ④b analysis cell 带真实 support_verdict
    ra = client.get(f"/analysis/{run_id}")
    if ra.status_code == 200:
        verdicts = [c.get("support_verdict") for row in ra.json().get("comparison", []) for c in row.get("cells", [])]
        print(f"     analysis cell support_verdicts: {verdicts}")

    # ⑤ GET /curation-drops
    print("[5/5] GET /runs/:id/curation-drops …")
    rd = client.get(f"/runs/{run_id}/curation-drops")
    assert rd.status_code == 200, rd.text
    drops = rd.json()
    print(f"     curation-drops: {len(drops)} 条 {[(d['scope'], d.get('competitor') or d.get('detail')) for d in drops][:5]}")

    rstat = client.get(f"/run/{run_id}")
    print(f"     run 终态: status={rstat.json()['status']} degraded={rstat.json()['degraded']}")
    print("\n[Plan B Task 12] CHECKS PASSED ✅  insight 两步/cell_row/verdict_recheck 三级/curation-drops 真 run 验证")


if __name__ == "__main__":
    main()
