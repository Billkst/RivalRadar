"""量化「analyze 卡住」:用 run_2dfd75424fd0(钉钉/企业微信,6 维,112 证据)的真证据,
分两阶段计时跑新版 analyze,定位慢在哪、是慢还是真挂。WARNING 日志显示每次结构化调用的重试。

真打 Doubao(放 spikes/)。后台运行,可能数分钟。
"""
from __future__ import annotations

import concurrent.futures as cf
import logging
import sqlite3
import time

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")

from rivalradar.config import db_path, doubao_model, get_doubao_client
from rivalradar.storage.repository import list_evidence
from rivalradar.agents.analyst import analyze_competitor, build_comparison

RID = "run_2dfd75424fd0"
COMPS = ["钉钉", "企业微信"]
DIMS = ("pricing", "core_workflows", "deployment", "integrations",
        "target_users", "review_sentiment")

conn = sqlite3.connect(db_path())
conn.row_factory = sqlite3.Row
evidence = list_evidence(conn, RID)
client = get_doubao_client()
model = doubao_model()
print(f"[起] 证据 {len(evidence)} 条,{len(COMPS)} 竞品 × {len(DIMS)} 维", flush=True)

# 阶段 1:逐竞品 profile 抽取(并行,复刻生产拓扑)
t0 = time.time()
with cf.ThreadPoolExecutor(max_workers=len(COMPS)) as ex:
    futs = [ex.submit(analyze_competitor, evidence, c, client=client, model=model) for c in COMPS]
    profiles = [f.result() for f in futs]
t1 = time.time()
print(f"[阶段1] 抽取 {len(COMPS)}竞品×4 = {len(COMPS)*4} 调用(并行)→ {t1-t0:.1f}s", flush=True)

# 阶段 2:build_comparison(按维度拆分,并行)
sink: list[str] = []
rows = build_comparison(profiles, evidence, dimensions=DIMS, degraded_sink=sink,
                        client=client, model=model)
t2 = time.time()
print(f"[阶段2] build_comparison 6 维(并行)→ {t2-t1:.1f}s  | 产 {len(rows)}/6 维, 降级 sink={sink}", flush=True)
print(f"[总计] analyze ≈ {t2-t0:.1f}s（={(t2-t0)/60:.1f} 分钟）", flush=True)
