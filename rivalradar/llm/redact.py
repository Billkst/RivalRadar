"""🔑 KEY 纪律:LLM 错误文本落日志 / 异常消息 / API 响应前的脱敏。

BYOK 让用户 key 经 per-request client 进入 run 管线;provider 在 401 等错误
body 里可能原样回显 key(本仓库 tests/test_llm_byok.py 模拟过该场景)。任何
`str(exception)` 在写 logger、拼进异常消息、或回给客户端前都必须先过 redact。

精确 key 值由调用方显式传入(从 `client.api_key` 取,覆盖火山方舟 UUID 这类
非 sk- 形态);正则兜底打掉 sk- / Bearer 形态,防调用方漏传。
"""
from __future__ import annotations

import re

_PATTERNS = (
    # OpenAI / DeepSeek / Moonshot / Anthropic 通用 sk- 前缀
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    # Authorization: Bearer <token> 兜底
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
)


def redact(text: str, *secrets: str | None) -> str:
    """把已知 key 值 + 常见 key 形态替换为 ***。secret 为空/None 则跳过。"""
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    for pat in _PATTERNS:
        text = pat.sub("***", text)
    return text
