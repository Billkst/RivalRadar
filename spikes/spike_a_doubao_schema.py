"""Spike A:实测 Doubao 能否对扁平 Schema 稳定吐合法结构化输出。

跑 N 次,统计成功解析率、平均耗时、平均 token。决策规则见 SPIKE_RESULTS.md。

实测发现(2026-05-25,EP ${DOUBAO_MODEL}):
- response_format=json_schema → 400 not supported
- response_format=json_object → 400 not supported
- **function-calling(tools)→ 可用且最优**(5/5,~4.6s,~1113 token)
本脚本测的就是 tools 路径(schema 作为工具 parameters + 强制 tool_choice + Pydantic 校验)。
"""
from __future__ import annotations

import pathlib
import sys

# 允许 `python spikes/spike_a_doubao_schema.py` 直接运行时找到 rivalradar 包
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import json
import time

from pydantic import BaseModel, ValidationError

from rivalradar import config
from rivalradar.schema.doubao_schema import to_doubao_schema
from rivalradar.schema.models import FeatureItem

N_RUNS = 5

# 真实证据片段(Notion 功能页节选,英文),让 Doubao 抽成扁平 FeatureItem
EVIDENCE = (
    "Notion combines notes, docs, wikis, and projects. Databases support table, "
    "board, calendar, gallery, and timeline views. Sub-items let you nest tasks "
    "under a parent task. AI features include writing assistance and Q&A."
)


class FeatureList(BaseModel):
    items: list[FeatureItem]


def run_once() -> tuple[bool, float, int]:
    client = config.get_doubao_client()
    schema = to_doubao_schema(FeatureList)
    tools = [{
        "type": "function",
        "function": {
            "name": "emit_feature_list",
            "description": "emit extracted features",
            "parameters": schema,
        },
    }]
    messages = [
        {"role": "user", "content": f"抽取功能项(category 用 core_workflows,parent_id 表父子层级):\n{EVIDENCE}"},
    ]
    t0 = time.time()
    resp = client.chat.completions.create(
        model=config.doubao_model(),
        messages=messages,
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "emit_feature_list"}},
    )
    latency = time.time() - t0
    tokens = getattr(resp.usage, "total_tokens", 0) if resp.usage else 0
    tool_calls = resp.choices[0].message.tool_calls
    try:
        raw = tool_calls[0].function.arguments if tool_calls else None
        parsed = FeatureList.model_validate(json.loads(raw))
        ok = len(parsed.items) >= 1
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        print(f"  parse failed: {e}")
        ok = False
    return ok, latency, tokens


def main() -> None:
    results = []
    for i in range(N_RUNS):
        print(f"run {i + 1}/{N_RUNS} ...")
        results.append(run_once())
    oks = sum(1 for ok, _, _ in results if ok)
    avg_latency = sum(l for _, l, _ in results) / len(results)
    avg_tokens = sum(t for _, _, t in results) / len(results)
    print("\n=== SPIKE A RESULT ===")
    print(f"parse success: {oks}/{N_RUNS}")
    print(f"avg latency:   {avg_latency:.2f}s")
    print(f"avg tokens:    {avg_tokens:.0f}")
    print("approach: function-calling (tools) — model rejects response_format json_schema & json_object")
    print("decision: GO if >=4/5 parse cleanly")


if __name__ == "__main__":
    main()
