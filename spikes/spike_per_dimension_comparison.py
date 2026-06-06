"""验证「按维度拆分」对比调用:只比 5 家在 1 个维度上、只喂该维证据,看是否
干净(合法 JSON)+ 完整(5 个 cell)+ 快(小输入)。逐维真打 Doubao。

对照:原单次 5×6 全矩阵调用,输入 247K、偶发坏 JSON、可能只产 2/6 维。
"""
from __future__ import annotations

import logging
import sqlite3
import time

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from rivalradar.config import db_path, doubao_model, get_doubao_client
from rivalradar.storage.repository import list_evidence
from rivalradar.agents.analyst import (
    build_evidence_block, _REFS_RULE, ComparisonExtraction,
)
from rivalradar.llm.structured import structured_call

RUN_ID = "run_11cad7660461"
COMPETITORS = ["QQ音乐", "酷狗音乐", "酷我音乐", "咪咕音乐", "汽水音乐"]
DIMENSIONS = ("pricing", "core_workflows", "deployment", "integrations",
              "target_users", "review_sentiment")

conn = sqlite3.connect(db_path())
conn.row_factory = sqlite3.Row
evidence = list_evidence(conn, RUN_ID)
client = get_doubao_client()
model = doubao_model()
names = ", ".join(COMPETITORS)

for dim in DIMENSIONS:
    dim_ev = [e for e in evidence if e.dimension == dim]
    block = build_evidence_block(dim_ev)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n对竞品 [{names}] 在维度「{dim}」上做横向对比。"
             f"为每个竞品产一个 cell,标 value_type(bool/enum/number/quote_text)与 value,挂 evidence_refs。"
             f"\n\n证据:\n{block}"}]
    t0 = time.time()
    try:
        rows = structured_call(ComparisonExtraction, msgs, client=client, model=model).rows
        row = next((r for r in rows if getattr(r, "dimension", None) == dim), rows[0] if rows else None)
        cells = len(getattr(row, "cells", []) or []) if row else 0
        print(f"[{dim}] 证据 {len(dim_ev)} 条 / 输入 {len(block)} 字符 / {time.time()-t0:.1f}s "
              f"→ ✅ rows={len(rows)} cells={cells}")
    except Exception as e:
        print(f"[{dim}] 证据 {len(dim_ev)} 条 / {time.time()-t0:.1f}s → ❌ {type(e).__name__}: {str(e)[:80]}")
