from __future__ import annotations

import json
import logging
from typing import TypeVar

from openai import APIConnectionError, APIError, APITimeoutError, BadRequestError
from pydantic import BaseModel, ValidationError

from rivalradar.llm.redact import redact
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


# 已确认「拒绝点名 tool_choice」的厂商端点(进程级,按 base_url+model 分键防跨厂商误伤)。
# 降级是厂商行为的**确定性事实**,不记住它就得每次调用都花一次注定 400 的全 payload 往返
# 去重新发现 —— 满矩阵 65 次 structured_call,白烧分钟级墙钟 + 双倍上行带宽(ship 前评审)。
_NAMED_TOOL_CHOICE_REJECTED: set[tuple[str, str]] = set()


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
    # 🔑 BYOK:provider 的 401 等错误 body 可能回显本次 client 的 key。从 client 取
    # 精确 key 值,任何 str(err) 落日志 / 进异常消息前用它 + 正则兜底脱敏。
    _secret = getattr(client, "api_key", None)
    # 点名 tool_choice 是首选(Doubao 实测最稳);但部分厂商在特定模式下拒绝它 ——
    # DeepSeek V4 thinking 模式(默认开)实测 400「Thinking mode does not support
    # this tool_choice」。被点名拒绝时去掉该参数重发:带 tools 时厂商默认即 auto,
    # 「必须调用工具」的契约由下方校验重试循环兜底,不必在参数层强制。
    _vendor_key = (str(getattr(client, "base_url", "")), model)
    send_tool_choice = _vendor_key not in _NAMED_TOOL_CHOICE_REJECTED
    _memo_pending = False  # 降级已发生、待「厂商接受了降级后的请求」确认后才写记忆

    # while 而非 for:tool_choice 降级是**参数协商**,不是模型给了坏结果,不计入尝试
    # 次数(真 run 实测:计入会把 SWOT 格的 3 次真机会吃成 2 次,到顶被优雅跳过)。
    attempt = 0
    while attempt < max_retries + 1:
        kwargs: dict = dict(model=model, messages=convo, tools=tools,
                            timeout=_DEFAULT_REQUEST_TIMEOUT, max_tokens=max_tokens)
        if send_tool_choice:
            kwargs["tool_choice"] = tool_choice
        try:
            resp = client.chat.completions.create(**kwargs)
        except BadRequestError as err:
            detail = redact(str(err), _secret)
            # 落日志前再脱一层 model:env 模式下 model 是 DOUBAO_MODEL endpoint id(项目
            # 纪律视同 KEY),厂商 400 body 若回显 model= 就会进日志(对抗评审)。异常消息
            # **不**脱 model —— BYOK 的 503 诊断要让用户看见自己的模型名;env 路径的异常
            # 文本从不回显给客户端(post_discover env 分支回笼统文案,SSE 只回异常类型名)。
            log_detail = redact(detail, model)
            if send_tool_choice and "tool_choice" in detail:
                # 厂商点名拒绝 tool_choice → 降级重发。**先降级、后验证、才记忆**:
                # 400 文案只做子串匹配,若在这里就写记忆,任何恰好含 "tool_choice" 字样的
                # 无关 400 都会把 (base_url, model) 永久毒化(红队);降级后的请求被厂商
                # 接受(成功拿到 resp)才确认拒因属实,写入记忆(见 attempt+=1 之后)。
                send_tool_choice = False
                _memo_pending = True
                last_err = err
                logger.warning(
                    "structured_call(%s) 厂商拒绝点名 tool_choice,去掉该参数重发:%s",
                    model_cls.__name__, log_detail[:200])
                continue  # 不计 attempt
            # 其余 400 = 请求本身不合法(参数超出厂商上限 / schema 不被支持),**确定性错误**:
            # 同样的请求重试必然同样失败。原先它落进下面的 APIError 分支被当网络抖动重试 3 次
            # —— 白烧 3 次真金白银的调用,还把「是我们发错了参数」这个诊断埋进超时噪声里。
            # BYOK 换厂商时这是最可能踩的一条(见 llm/limits.py):快失败 + 原样回传厂商的
            # 400 文案(已脱敏),用户一眼看到「max_tokens 超上限」而不是「网络失败」。
            # 上层若吞掉异常文本,服务端日志是最后一处能看到厂商真实拒因的地方 → 也留 warning。
            logger.warning("structured_call(%s) 被厂商拒绝(400,不重试):%s",
                           model_cls.__name__, log_detail[:300])
            # from None(不是 from err):厂商 400 body 可能回显 key,外层消息已脱敏,但
            # `from err` 会把**未脱敏**的原始异常挂到 __cause__ 上;任何调用方用 exc_info=True
            # / logger.exception 打印时,traceback 会把 __cause__ 的 str() 原样写进日志 →
            # key 从异常链泄漏(评审 P1,analyst._safe_extract 正是 exc_info=True)。
            # from None 断链:StructuredCallError 永不携带未脱敏的 key,任何调用方都安全。
            raise StructuredCallError(
                f"structured_call({model_cls.__name__}) 被厂商拒绝(400,不重试):{detail}"
            ) from None
        except (APITimeoutError, APIConnectionError, APIError) as err:
            # 网络层失败(timeout / connection drop / 上游 5xx)归入 retry 循环。
            # 不带 prompt 修改 — 同一 messages 重试,假设下次网络好。Clash 抖动
            # 时 1-2 个 retry 一般够;如果全打不通,封顶后 raise 让上层走降级。
            attempt += 1
            last_err = err
            logger.warning(
                "structured_call attempt %d/%d network error: %s: %s",
                attempt, max_retries + 1, type(err).__name__,
                redact(str(err), _secret, model)[:200],
            )
            continue
        attempt += 1
        if _memo_pending:
            # 降级后的请求被厂商接受了 → 拒因确系 tool_choice,此刻才写进程级记忆,
            # 后续 structured_call 直接跳过探测。容量兜底:BYOK 方可控 base_url,
            # 能造无限 (base_url, model) 组合,封顶防集合无界膨胀(满了就退回每次探测)。
            if len(_NAMED_TOOL_CHOICE_REJECTED) < 128:
                _NAMED_TOOL_CHOICE_REJECTED.add(_vendor_key)
                # 只记 base_url,**不打 model** —— env 模式下 model 是 DOUBAO_MODEL
                # endpoint id,项目纪律视同 KEY 敏感(评审 P2);base_url 非敏感,够定位。
                logger.warning(
                    "structured_call(%s) 确认端点 %s 拒绝点名 tool_choice,已记忆,"
                    "本进程后续调用不再探测", model_cls.__name__, _vendor_key[0])
            _memo_pending = False
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
                model_cls.__name__, attempt, max_retries + 1, err,
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
        f"structured_call({model_cls.__name__}) 在 {max_retries + 1} 次尝试后仍失败:"
        f"{redact(str(last_err), _secret)}"
    )
