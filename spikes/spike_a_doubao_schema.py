"""Spike A:实测 Doubao 能否对扁平 Schema 稳定吐合法结构化输出。

跑 N 次,统计成功解析率、平均耗时、平均 token。决策规则见 SPIKE_RESULTS.md。

实测发现(2026-05-25):EP ep-20260514111325-xjmj7 既不支持 response_format=json_schema
也不支持 json_object(均 400)。可行路径 = plain 模式 + 把 JSON Schema 写进 system prompt
+ 去 markdown 围栏 + Pydantic 校验。本脚本测的就是这条真实路径。
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


def _strip_fences(raw: str) -> str:
    """去掉模型偶尔包裹的 ```json ... ``` 围栏。"""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
        if s.startswith("json"):
            s = s[4:]
    return s.strip()


def run_once() -> tuple[bool, float, int]:
    client = config.get_doubao_client()
    schema = to_doubao_schema(FeatureList)
    messages = [
        {"role": "system", "content": (
            "你是竞品功能抽取器。只输出一个 JSON 对象,严格符合下面的 JSON Schema,"
            "不要任何额外文字或 markdown 代码块。用 parent_id 表达功能的父子层级,"
            "顶层功能 parent_id 为 null。\nJSON Schema:\n"
            + json.dumps(schema, ensure_ascii=False)
        )},
        {"role": "user", "content": f"从下面文本抽取功能项(category 用 core_workflows):\n{EVIDENCE}"},
    ]
    t0 = time.time()
    resp = client.chat.completions.create(model=config.doubao_model(), messages=messages)
    latency = time.time() - t0
    tokens = getattr(resp.usage, "total_tokens", 0) if resp.usage else 0
    raw = resp.choices[0].message.content
    try:
        parsed = FeatureList.model_validate(json.loads(_strip_fences(raw)))
        ok = len(parsed.items) >= 1
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        print(f"  parse failed: {e}\n  raw: {(raw or '')[:300]}")
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
    print("approach: plain mode + schema-in-prompt + Pydantic validate "
          "(model rejects json_schema & json_object)")
    print("decision: GO if >=4/5 parse cleanly")


if __name__ == "__main__":
    main()
