"""端到端验证新版 build_comparison(按维度拆分 + 单维优雅降级):用 run_11cad7660461
的真证据跑,确认产出多数维度、脆维度(review_sentiment)降级进 sink、整体不抛异常。

真打 Doubao(放 spikes/)。review_sentiment 会重试封顶后降级,故整体偏慢(给足超时)。
"""
from __future__ import annotations

import logging
import sqlite3

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from rivalradar.config import db_path, doubao_model, get_doubao_client
from rivalradar.storage.repository import list_evidence
from rivalradar.agents.analyst import build_comparison
from rivalradar.schema.models import CompetitorProfile, PricingModel, SWOT

RUN_ID = "run_11cad7660461"
COMPETITORS = ["QQ音乐", "酷狗音乐", "酷我音乐", "咪咕音乐", "汽水音乐"]
DIMENSIONS = ("pricing", "core_workflows", "deployment", "integrations",
              "target_users", "review_sentiment")

conn = sqlite3.connect(db_path())
conn.row_factory = sqlite3.Row
evidence = list_evidence(conn, RUN_ID)
profiles = [CompetitorProfile(name=n, pricing=PricingModel(model_type="未知"), swot=SWOT())
            for n in COMPETITORS]
sink: list[str] = []

print(f"证据 {len(evidence)} 条,跑新版 build_comparison(按维度拆分,并行)…")
rows = build_comparison(profiles, evidence, dimensions=DIMENSIONS,
                        degraded_sink=sink,
                        client=get_doubao_client(), model=doubao_model())
print(f"\n✅ 未崩溃。产出 {len(rows)}/{len(DIMENSIONS)} 维:")
for r in rows:
    print(f"  - {r.dimension}: {len(r.cells)} cells")
print(f"降级(可见)维度 sink = {sink}")
