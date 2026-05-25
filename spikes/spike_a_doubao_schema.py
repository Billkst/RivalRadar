"""Spike A:实测 Doubao 能否对扁平 Schema 稳定吐合法结构化输出。

跑 N 次,统计成功解析率、平均耗时、平均 token。决策规则见 SPIKE_RESULTS.md。
"""
from __future__ import annotations

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
    messages = [
        {"role": "system", "content": "你是竞品功能抽取器。只输出 JSON,符合给定 schema。"
                                       "用 parent_id 表达功能的父子层级,顶层功能 parent_id 为 null。"},
        {"role": "user", "content": f"从下面文本抽取功能项(category 用 core_workflows):\n{EVIDENCE}"},
    ]
    t0 = time.time()
    resp = client.chat.completions.create(
        model=config.doubao_model(),
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "FeatureList", "schema": schema},
        },
    )
    latency = time.time() - t0
    tokens = getattr(resp.usage, "total_tokens", 0) if resp.usage else 0
    raw = resp.choices[0].message.content
    try:
        parsed = FeatureList.model_validate(json.loads(raw))
        ok = len(parsed.items) >= 1
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"  parse failed: {e}\n  raw: {raw[:300]}")
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
    print("decision: GO if >=4/5 parse cleanly; else investigate strict/additionalProperties/flatten")


if __name__ == "__main__":
    main()
