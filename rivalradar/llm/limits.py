"""厂商能力边界钳制:让「模型可插拔」在真 run 上真的成立。

**为什么需要**:structured.py 的 `_DEFAULT_MAX_TOKENS = 131072` 是**实测出来的火山方舟端点
硬上限**(注释在案:131073 报 400)。它对方舟是对的,对别家一律是错的 —— DeepSeek / OpenAI /
Kimi 的输出上限都远低于此。BYOK 换厂商后:
  - `/llm/ping` 发 max_tokens=1 → **必过**(测不出问题);
  - 真 run 的第一次 structured_call 发 131072 → 400 → 被重试循环当网络错误**重试 3 次**
    (400 是确定性错误,重试必然还是 400)→ 抽取全败 → 死 run。
用户会以为「DeepSeek 不兼容」,其实是**我们把一家厂商的参数硬编码进了 harness**。

**修法**:把「想要多少」与「厂商给多少」分开 —— 上层照旧要它想要的(不设截断天花板),
这一层按厂商上限 `min(想要的, 上限)` 钳掉。agent 层与 structured_call **一行不用改**,
厂商差异被 harness 吸收在这一层,上层感知不到。这正是 harness 的职责边界。

上限从 BYOK 的 X-LLM-Max-Tokens 头进来(前端按厂商预设填默认值);env(方舟)路径不传 →
无上限 → 保持 131072 的现状行为。
"""
from __future__ import annotations

from typing import Any


class _CappedCompletions:
    def __init__(self, inner: Any, cap: int) -> None:
        self._inner = inner
        self._cap = cap

    def create(self, **kwargs: Any) -> Any:
        requested = kwargs.get("max_tokens")
        if requested is None:
            # 未声明 max_tokens 的调用(如 writer 的流式 insight 草稿)原先完全绕过钳制 ——
            # 「cap 让 client 天然安全」的不变量就有个洞(评审 F4)。声明了上限就该对**所有**
            # 调用生效:缺省时直接设成上限(= 厂商允许的最大,不会截断,只是补上天花板)。
            kwargs["max_tokens"] = self._cap
        else:
            # min 而非覆盖:ping 的 max_tokens=1 不该被抬成上限值,
            # structured_call 的 131072 该被压到厂商上限。取小者两头都对。
            kwargs["max_tokens"] = min(int(requested), self._cap)
        return self._inner.create(**kwargs)


class _CappedChat:
    def __init__(self, inner: Any, cap: int) -> None:
        self._inner = inner
        self._cap = cap

    @property
    def completions(self) -> _CappedCompletions:
        return _CappedCompletions(self._inner.completions, self._cap)


class _CappedClient:
    """包装 OpenAI 同步 client:只钳 .chat.completions.create 的 max_tokens,其余透传。

    __getattr__ 透传是**必须的**:structured.py 靠 getattr(client, "api_key") 取 BYOK key
    做日志脱敏,包装层吞掉这个属性会让 provider 401 回显的 key 漏进日志。
    """

    def __init__(self, inner: Any, cap: int) -> None:
        self._inner = inner
        self._cap = cap

    @property
    def chat(self) -> _CappedChat:
        return _CappedChat(self._inner.chat, self._cap)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def cap_client(client: Any, max_output_tokens: int | None) -> Any:
    """None(env / 未声明上限)→ 原样返回,行为不变;否则包一层输出上限钳制。"""
    return client if max_output_tokens is None else _CappedClient(client, max_output_tokens)
