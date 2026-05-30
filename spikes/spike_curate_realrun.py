"""真 run 验证 spike(Part A 提速 + Part B 策展)。

直连 run_research(非 HTTP/SSE),新 temp DB,真打 Doubao + Tavily。
- 计时 analyze 节点墙钟(并行后应 ≈ 最慢单抽取,而非 13 次之和)。
- 检查策展:对比矩阵 cell 是否被丢弃、verdict 是否收敛 pass / 诚实 insufficient。

跑法(必须 unset proxy 防 Clash fake-ip 卡 LLM):
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
  export NO_PROXY=localhost,127.0.0.1,github.com
  .venv/bin/python spikes/spike_curate_realrun.py <case>
  case = clean | hard
"""
from __future__ import annotations

import sys
import time
import json

from rivalradar import config as cfg
from rivalradar.storage.db import connect, init_db
from rivalradar.graph import nodes as nodes_mod
from rivalradar.graph.build import run_research
from rivalradar.search.tavily_provider import TavilyProvider

CASES = {
    # 干净基线:已知 pass 的组合(run_79498869 同输入)→ 验证提速 + 仍 pass。
    "clean": {
        "competitors": ["飞书", "钉钉", "企业微信"],
        "dimensions": ["pricing", "core_workflows", "integrations"],
        "decision_context": "选型PM:为团队评估并选型合适的协作办公平台",
    },
    # 更难:冷门小众竞品 + 冷门维度 → 公开资料薄,钓策展丢 cell / 诚实 insufficient 路径。
    "hard": {
        "competitors": ["PingCode", "Tapd", "ones.com"],
        "dimensions": ["pricing", "deployment", "review_sentiment"],
        "decision_context": "技术负责人:为 30 人研发团队选研发管理工具,关注私有化与口碑",
    },
}


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else "clean"
    spec = CASES[case]
    # 可选第二参数 = DB 路径:传主库(rivalradar.db)即把这次干净 run 落库当 demo replay 种子;
    # 不传则用 /tmp 隔离库(只测时长不污染主库)。
    db = sys.argv[2] if len(sys.argv) > 2 else f"/tmp/spike_{case}_{int(time.time())}.db"
    conn = connect(db)
    init_db(conn)
    client = cfg.get_doubao_client()
    provider = TavilyProvider(api_key=cfg.tavily_api_key())

    # 包裹 analyze 计时(墙钟)。
    orig_analyze = nodes_mod.analyze
    timings = []

    def timed_analyze(*a, **k):
        t0 = time.monotonic()
        out = orig_analyze(*a, **k)
        dt = time.monotonic() - t0
        timings.append(dt)
        print(f"  [analyze] round {len(timings)}: {dt:.1f}s "
              f"({len(out.competitors)} profiles, {len(out.comparison)} rows)", flush=True)
        return out

    nodes_mod.analyze = timed_analyze

    print(f"=== CASE {case} | db={db} ===", flush=True)
    print(f"  competitors={spec['competitors']} dims={spec['dimensions']}", flush=True)
    t_start = time.monotonic()
    run_id, final = run_research(
        spec["competitors"], spec["dimensions"],
        conn=conn, client=client, model=cfg.doubao_model(),
        provider=provider, as_of="2026-05-30",
        decision_context=spec["decision_context"],
    )
    total = time.monotonic() - t_start
    nodes_mod.analyze = orig_analyze

    # 读终态
    cur = conn.cursor()
    cur.row_factory = None
    status = cur.execute("select status, degraded from runs where run_id=?", (run_id,)).fetchone()
    qc_raw = cur.execute("select payload from qc_result where run_id=?", (run_id,)).fetchone()
    an_raw = cur.execute("select * from analysis where run_id=?", (run_id,)).fetchone()
    ev_n = cur.execute("select count(*) from evidence where run_id=?", (run_id,)).fetchone()[0]
    dc_raw = cur.execute("select * from decisions where run_id=?", (run_id,)).fetchone()
    tr = cur.execute("select node, output_summary from trace where run_id=? order by id", (run_id,)).fetchall()

    print(f"\n=== RESULT {run_id} ({total:.0f}s total) ===", flush=True)
    print(f"  status={status[0]} degraded={status[1]}", flush=True)
    print(f"  evidence={ev_n}  analyze_rounds={len(timings)}  analyze_times={[f'{t:.0f}s' for t in timings]}", flush=True)
    if qc_raw:
        q = json.loads(qc_raw[0])
        print(f"  qc verdict={q['verdict']} issues={len(q.get('issues', []))}", flush=True)
    # matrix cell count (curation visible here)
    if an_raw:
        for col in an_raw if not isinstance(an_raw, tuple) else []:
            pass
        # analysis row is tuple; find the json column
        adata = None
        for v in an_raw:
            if isinstance(v, str) and v.strip().startswith("{"):
                adata = json.loads(v); break
        if adata:
            comp = adata.get("comparison", [])
            cells = sum(len(r.get("cells", [])) for r in comp)
            print(f"  MATRIX: {len(comp)} rows, {cells} cells (策展后)", flush=True)
            for r in comp:
                print(f"    [{r['dimension']}] {len(r['cells'])} cells: "
                      f"{[c['competitor'] for c in r['cells']]}", flush=True)
    if dc_raw:
        ddata = None
        for v in dc_raw:
            if isinstance(v, str) and v.strip().startswith("{"):
                ddata = json.loads(v); break
        if ddata:
            ds = ddata.get("decisions", [])
            print(f"  DECISIONS: {len(ds)}", flush=True)
            for d in ds:
                print(f"    [{d.get('stance')}] {str(d.get('action'))[:60]}", flush=True)
    print("\n  TRACE:", flush=True)
    for node, summ in tr:
        print(f"    {node:9s} {summ}", flush=True)


if __name__ == "__main__":
    main()
