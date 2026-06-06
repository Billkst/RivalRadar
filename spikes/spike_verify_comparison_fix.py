"""验证修复:用真 structured_call(新默认 max_retries=4 = 5 次)跑 run_11cad7660461 的
同款重输入(273 证据 ≈ 247K char),确认能稳定拿到合法 ComparisonExtraction。

真打 Doubao(放 spikes/,不进 pytest)。日志级别开到 WARNING 可看到每次重试。
"""
from __future__ import annotations

import logging
import sqlite3

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
names = ", ".join(COMPETITORS)
dims = ", ".join(DIMENSIONS)
block = build_evidence_block(evidence)
msgs = [{"role": "user", "content":
         f"{_REFS_RULE}\n\n对竞品 [{names}] **只在这些维度**做横向对比:{dims}。"
         f"**不要新增其它维度**(超出上述维度的对比一律不要输出)。"
         f"每个 cell 标 value_type(bool/enum/number/quote_text)与 value,并挂 evidence_refs。"
         f"\n\n证据:\n{block}"}]

client = get_doubao_client()
model = doubao_model()
print(f"输入字符数:{len(msgs[0]['content'])} / 证据 {len(evidence)} 条")
print("调用真 structured_call(max_retries 默认=4,最多 5 次)…")
result = structured_call(ComparisonExtraction, msgs, client=client, model=model)
print(f"✅ 成功!rows={len(result.rows)}")
for r in result.rows[:3]:
    print("  -", getattr(r, "dimension", "?"), "→", len(getattr(r, "cells", []) or []), "cells")
