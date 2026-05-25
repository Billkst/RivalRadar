from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from rivalradar.schema.doubao_schema import to_doubao_schema

T = TypeVar("T", bound=BaseModel)


class StructuredCallError(RuntimeError):
    """结构化调用在重试封顶后仍失败 —— 显式抛出,绝不静默吞掉(spec §9)。"""


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
    """
    schema = to_doubao_schema(model_cls)
    convo = list(messages)
    last_err: Exception | None = None

    for _ in range(max_retries + 1):
        resp = client.chat.completions.create(
            model=model,
            messages=convo,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": model_cls.__name__, "schema": schema},
            },
        )
        raw = resp.choices[0].message.content
        try:
            return model_cls.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as err:
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
