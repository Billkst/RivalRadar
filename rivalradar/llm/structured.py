from __future__ import annotations

import json
import logging
from typing import TypeVar

from openai import APIConnectionError, APIError, APITimeoutError
from pydantic import BaseModel, ValidationError

from rivalradar.schema.doubao_schema import to_doubao_schema

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_TOOL_NAME = "emit_result"

# 单次 SDK 调用上限(秒)。Clash fake-ip 偶发把 Doubao 端口路由到慢路径,
# 不设 timeout SDK default 是 600s/无限,WSL2 真打 14 min hang 实测踩过。
#
# 90s 选择依据(post-real-run-5 二次校准):
# - 直接 ping max_tokens=5 → 4-5s(欺骗性快)
# - Mock realistic call(~3K char input + 1.2K token output)→ 24-25s
# - Backend 真实 call(172 evidence × ~200 char = ~34K char input)→ 35-70s
# - 60s 仍卡在 backend payload 边缘,run #5 在 analyst 又触发全 retry 失败
# - 90s = backend worst realistic 70s 的 1.3x headroom,Clash 抖动 +20s 兜底
_DEFAULT_REQUEST_TIMEOUT = 90.0


class StructuredCallError(RuntimeError):
    """结构化调用在重试封顶后仍失败 —— 显式抛出,绝不静默吞掉(spec §9)。"""


def _extract_tool_args(resp) -> str | None:
    """取第一个 tool_call 的参数 JSON 字符串;模型没调用工具则返回 None。"""
    msg = resp.choices[0].message
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls:
        return None
    return tool_calls[0].function.arguments


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

    实现走 **function-calling(tools)**:把 JSON Schema 作为工具的 parameters,
    强制 tool_choice,从 tool_call 参数里取结构化结果。原因(见 spikes/SPIKE_RESULTS.md):
    目标 EP ${DOUBAO_MODEL} 不支持 response_format 的 json_schema/json_object
    (均 400);tools 路径实测 5/5、~4.6s、~1113 token,比 prompt 注入更快更省更稳。
    校验重试循环仍是可靠性兜底(模型可能不调用工具或参数不合 schema)。
    """
    schema = to_doubao_schema(model_cls)
    tools = [{
        "type": "function",
        "function": {
            "name": _TOOL_NAME,
            "description": f"emit one {model_cls.__name__} as structured arguments",
            "parameters": schema,
        },
    }]
    tool_choice = {"type": "function", "function": {"name": _TOOL_NAME}}
    convo = list(messages)
    last_err: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model, messages=convo, tools=tools, tool_choice=tool_choice,
                timeout=_DEFAULT_REQUEST_TIMEOUT,
            )
        except (APITimeoutError, APIConnectionError, APIError) as err:
            # 网络层失败(timeout / connection drop / 上游 5xx)归入 retry 循环。
            # 不带 prompt 修改 — 同一 messages 重试,假设下次网络好。Clash 抖动
            # 时 1-2 个 retry 一般够;如果全打不通,封顶后 raise 让上层走降级。
            last_err = err
            logger.warning(
                "structured_call attempt %d/%d network error: %s: %s",
                attempt + 1, max_retries + 1, type(err).__name__, str(err)[:200],
            )
            continue
        raw = _extract_tool_args(resp)
        try:
            if raw is None:
                raise ValueError("模型未返回工具调用")
            return model_cls.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as err:
            last_err = err
            convo = convo + [{
                "role": "user",
                "content": (
                    f"上次结构化结果未通过校验:{err}\n"
                    f"请重新调用工具 {_TOOL_NAME},返回符合 schema 的合法参数。"
                ),
            }]

    raise StructuredCallError(
        f"structured_call({model_cls.__name__}) 在 {max_retries + 1} 次尝试后仍失败:{last_err}"
    )
