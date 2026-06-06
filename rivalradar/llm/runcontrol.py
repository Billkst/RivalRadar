"""per-run 中止控制:协作式取消 + 全局墙钟预算(post-real-run-7 结构性修)。

为什么需要:图节点是同步函数,LLM 调用跑在嵌套 ThreadPoolExecutor 的 worker 线程里、
是阻塞的 `client.chat.completions.create(...)`,**没有 await 边界**——asyncio 的
`task.cancel()` 注入不进去,杀不掉在飞的 LLM,取消只改了 DB 状态、后台仍空磨 5×90s 重试环
(诊断见 post-real-run-7)。

修法:协作式取消。包装 OpenAI client,**每次 create() 前**查一个线程安全的 RunControl:
- 已被 /cancel 置位 → 抛 RunAborted('cancelled'),后续重试/维度即止(最多再等 1 个在飞的 90s 调用)。
- 超出 run 级墙钟预算 → 抛 RunAborted('timeout'),防病态 run 无上限磨下去(只能人工取消)。

RunAborted 绕过 structured_call 的重试与各处 `except Exception` 降级(降级处理器须显式
re-raise),一路传到 SSE 生成器按 reason 区分终态(cancelled 保持已标的 cancelled;timeout 标 failed)。
不改任何 agent 函数签名——节点处把 client 包一层即可。
"""
from __future__ import annotations

import threading
import time


class RunAborted(BaseException):
    """run 中止信号。reason ∈ {'cancelled', 'timeout'}。

    刻意继承 **BaseException**(同 asyncio.CancelledError / KeyboardInterrupt)——它是
    控制流信号,不是"业务失败":这样能自动穿透代码里所有 `except Exception` 降级处理器
    (analyst._safe_extract / build_comparison.work / qc_node / decide_node …),无需在每处
    加 re-raise,只在最顶层(SSE 生成器)显式接住。防"取消被某个 except Exception 咽掉"。
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(detail or reason)


class RunControl:
    """线程安全的 per-run 中止控制:worker 线程查 check(),事件循环线程置 cancel()。"""

    def __init__(self, *, deadline: float | None = None) -> None:
        self._cancel = threading.Event()
        self._deadline = deadline  # time.monotonic() 基准;None = 无墙钟预算

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        """LLM 调用前查;已取消 → RunAborted('cancelled');超预算 → RunAborted('timeout')。"""
        if self._cancel.is_set():
            raise RunAborted("cancelled")
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise RunAborted("timeout")


class _CancellableCompletions:
    def __init__(self, inner, control: RunControl) -> None:
        self._inner = inner
        self._control = control

    def create(self, **kwargs):
        self._control.check()  # 取消/超时 → RunAborted,不发起 HTTP
        return self._inner.create(**kwargs)


class _CancellableChat:
    def __init__(self, inner, control: RunControl) -> None:
        self._inner = inner
        self._control = control

    @property
    def completions(self):
        return _CancellableCompletions(self._inner.completions, self._control)


class _CancellableClient:
    """包装 OpenAI 同步 client:只在 .chat.completions.create 路径插入取消检查,其余透传。"""

    def __init__(self, inner, control: RunControl) -> None:
        self._inner = inner
        self._control = control

    @property
    def chat(self):
        return _CancellableChat(self._inner.chat, self._control)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def wrap_client(client, control: RunControl | None):
    """control 为 None(单测/CLI/无控制)→ 原样返回;否则包一层每调用取消检查。"""
    return client if control is None else _CancellableClient(client, control)
