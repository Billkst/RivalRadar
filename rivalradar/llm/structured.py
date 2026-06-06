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


# 单次结构化输出的 token 上限,取端点硬上限(给足不保守)。真 run 钓出——竞品功能多时
# (钉钉 27 项)feature 抽取 JSON 巨大,不设 max_tokens 走模型默认(实测 ~4096 token /
# char 9575)就被截断 → JSON Unterminated string → 三次重试全败 → StructuredCallError
# 杀死整个 run。
#
# 131072 = 端点 doubao-seed-2-0-lite(256K 上下文)的真实 max_tokens 硬上限(实测探得:
# max_tokens=131072 接受 / 131073 报 400 InvalidParameter "integer above maximum value")。
# max_tokens 是输出上限参数,模型自然停止不会真吐满,设最大值只去掉截断天花板,不影响
# 正常输出速度/成本。若换端点上限不同,API 会 400 报真实上限,据此调整。
_DEFAULT_MAX_TOKENS = 131072


def structured_call(
    model_cls: type[T],
    messages: list[dict],
    *,
    client,
    model: str,
    max_retries: int = 2,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> T:
    """调 Doubao 吐结构化输出 → Pydantic 校验 → 不合格带错重试 → 封顶显式报错。

    被 4 个 Agent 复用(DRY)。max_retries=2 表示最多 3 次尝试。max_tokens 给足防截断。

    **3 次而非 5 次的依据(post-real-run-7)**:曾因大矩阵调用偶发坏 JSON 把 max_retries
    提到 4(5 次),但 build_comparison 已改成**按维度拆分的小调用**(输入骤减、单次坏 JSON
    概率本就低),5 次属过度保险;且重试是**串行无早停**(structured.py 下方循环),每多 1 次
    就在最坏路径上叠一个 _DEFAULT_REQUEST_TIMEOUT(90s)——5 次把单调用最坏从 270s 抬到 450s,
    实测让真 run 的 analyze 最坏墙钟膨胀到 ~22min、用户感知"卡死"(post-real-run-7 诊断)。
    回到 3 次:单调用最坏 270s,典型 1-2 次即过(spike 实测 attempt2 即合法)。
    **绝不补括号"修复"** 截断 JSON——会造出残缺/虚构对比行,违反反幻觉硬门;只重试拿干净结果。

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
                timeout=_DEFAULT_REQUEST_TIMEOUT, max_tokens=max_tokens,
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
            # 记录原始 JSON 头尾(不记全文,防日志爆 + 不外泄)便于诊断坏在哪——
            # 真 run-6 因日志不带 raw,只能靠 spike 复现才看清是"截断不完整"。
            logger.warning(
                "structured_call(%s) attempt %d/%d 解析/校验失败:%s | raw head=%r tail=%r",
                model_cls.__name__, attempt + 1, max_retries + 1, err,
                (raw or "")[:160], (raw or "")[-160:],
            )
            convo = convo + [{
                "role": "user",
                "content": (
                    f"上次返回的 JSON 无效或不完整({err})。请重新调用工具 {_TOOL_NAME},"
                    f"一次性输出**完整且语法合法**的 JSON 参数:所有括号 / 方括号闭合、"
                    f"字符串内的双引号转义为 \\\"、不要中途截断。"
                ),
            }]

    raise StructuredCallError(
        f"structured_call({model_cls.__name__}) 在 {max_retries + 1} 次尝试后仍失败:{last_err}"
    )
