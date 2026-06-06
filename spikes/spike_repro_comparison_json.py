"""复现 run_11cad7660461 的 analyst ComparisonExtraction JSON 解析失败,抓原始坏 JSON。

真打 Doubao(放 spikes/,不进 pytest)。用库里存的真证据,精确复现 build_comparison 的
那次结构化调用,在 json.loads 失败时 dump 原始 tool 参数 + char 501 附近,定位坏在哪。

运行:
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
  NO_PROXY=ark.cn-beijing.volces.com,api.tavily.com,localhost,127.0.0.1 \
    .venv/bin/python spikes/spike_repro_comparison_json.py
"""
from __future__ import annotations

import json
import sqlite3

from rivalradar.config import db_path, doubao_model, get_doubao_client
from rivalradar.storage.repository import list_evidence
from rivalradar.agents.analyst import (
    build_evidence_block, _REFS_RULE, ComparisonExtraction,
)
from rivalradar.schema.doubao_schema import to_doubao_schema

RUN_ID = "run_11cad7660461"
COMPETITORS = ["QQ音乐", "酷狗音乐", "酷我音乐", "咪咕音乐", "汽水音乐"]
DIMENSIONS = ("pricing", "core_workflows", "deployment", "integrations",
              "target_users", "review_sentiment")

conn = sqlite3.connect(db_path())
conn.row_factory = sqlite3.Row
evidence = list_evidence(conn, RUN_ID)
print(f"证据条数:{len(evidence)}")

names = ", ".join(COMPETITORS)
dims = ", ".join(DIMENSIONS)
block = build_evidence_block(evidence)
msgs = [{"role": "user", "content":
         f"{_REFS_RULE}\n\n对竞品 [{names}] **只在这些维度**做横向对比:{dims}。"
         f"**不要新增其它维度**(超出上述维度的对比一律不要输出)。"
         f"每个 cell 标 value_type(bool/enum/number/quote_text)与 value,并挂 evidence_refs。"
         f"\n\n证据:\n{block}"}]
print(f"输入字符数:{len(msgs[0]['content'])}")

schema = to_doubao_schema(ComparisonExtraction)
tools = [{"type": "function", "function": {
    "name": "emit_result",
    "description": "emit one ComparisonExtraction as structured arguments",
    "parameters": schema}}]
tool_choice = {"type": "function", "function": {"name": "emit_result"}}

client = get_doubao_client()
model = doubao_model()

for attempt in range(3):
    print(f"\n===== 尝试 {attempt + 1} =====")
    resp = client.chat.completions.create(
        model=model, messages=msgs, tools=tools, tool_choice=tool_choice,
        timeout=90.0, max_tokens=131072,
    )
    msg = resp.choices[0].message
    tcs = getattr(msg, "tool_calls", None)
    if not tcs:
        print("!! 模型没调用工具;message.content =", (msg.content or "")[:300])
        continue
    raw = tcs[0].function.arguments
    print(f"原始参数长度:{len(raw)}")
    try:
        obj = json.loads(raw)
        print(f"✅ JSON 合法,rows={len(obj.get('rows', []))}")
        break
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败:{e}")
        c = e.pos
        print(f"  char {c} 附近(±60):")
        print("  …" + repr(raw[max(0, c - 60):c + 60]) + "…")
        with open(f"/tmp/bad_comparison_{attempt}.json", "w", encoding="utf-8") as f:
            f.write(raw)
        print(f"  完整原始已存 /tmp/bad_comparison_{attempt}.json ({len(raw)} 字节)")
