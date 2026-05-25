from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from rivalradar.schema.doubao_schema import to_doubao_schema

T = TypeVar("T", bound=BaseModel)

_SCHEMA_INSTRUCTION = (
    "只输出一个 JSON 对象,严格符合下面的 JSON Schema,"
    "不要任何额外文字或 markdown 代码块。\nJSON Schema:\n"
)


class StructuredCallError(RuntimeError):
    """结构化调用在重试封顶后仍失败 —— 显式抛出,绝不静默吞掉(spec §9)。"""


def _strip_fences(raw: str | None) -> str:
    """去掉模型偶尔包裹的 ```json ... ``` 围栏。None/空 → 空串(交给 JSON 解析报错走重试)。"""
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith("```"):
        s = s[3:]
        if s[:4].lower() == "json":
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def structured_call(
    model_cls: type[T],
    messages: list[dict],
    *,
    client,
    model: str,
    max_retries: int = 2,
) -> T:
    """调 Doubao 吐结构化输出 → Pydantic 校验 → 不合格带错重试 → 封顶显式报错。

    被 4 个 Agent 复用(DRY)。max_retries=2 表示最多 3 次尝试。

    注:目标模型(EP ep-20260514111325-xjmj7)实测不支持 response_format 的
    json_schema / json_object(均 400,见 spikes/SPIKE_RESULTS.md),故走
    "把 JSON Schema 注入 system prompt + 去围栏 + Pydantic 校验 + 带错重试"。
    没有原生强制,可靠性全靠这套校验重试循环。
    """
    schema = to_doubao_schema(model_cls)
    schema_msg = {
        "role": "system",
        "content": _SCHEMA_INSTRUCTION + json.dumps(schema, ensure_ascii=False),
    }
    convo = [schema_msg] + list(messages)
    last_err: Exception | None = None

    for _ in range(max_retries + 1):
        resp = client.chat.completions.create(model=model, messages=convo)
        raw = resp.choices[0].message.content
        try:
            return model_cls.model_validate(json.loads(_strip_fences(raw)))
        except (json.JSONDecodeError, ValidationError, TypeError) as err:
            last_err = err
            convo = convo + [
                {"role": "assistant", "content": raw or ""},
                {
                    "role": "user",
                    "content": (
                        f"上次输出未通过校验:{err}\n"
                        "只返回符合 schema 的合法 JSON,不要任何额外文字。"
                    ),
                },
            ]

    raise StructuredCallError(
        f"structured_call({model_cls.__name__}) 在 {max_retries + 1} 次尝试后仍失败:{last_err}"
    )
