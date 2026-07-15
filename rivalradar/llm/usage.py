"""per-node token 计量:成本这条边的取数口(「成本 · 质量 · 延迟」三角原本缺成本)。

为什么包 client 而不改 structured_call 签名:
`response.usage` 只在 SDK 调用点拿得到,而 trace 是**一节点一行**写的。中间隔着
analyst / writer / qc / discover 十余个调用点,让 structured_call 返回 (result, usage)
要改遍所有签名。但**所有 LLM 调用都必经 `client.chat.completions.create`**,而节点已经
在用 runcontrol.wrap_client 包 client(查取消)——同一个接缝再包一层计量即可,agent 层零改动。

组合顺序(nodes._run_client):meter(外) → cancellable(内) → 真 client。
取消检查先于 HTTP 也先于计量,故被取消的调用不会被计入成本。

**流式调用的静默少算陷阱**:writer 生成洞察走 stream_chat(stream=True),SDK 返回的是
迭代器不是 ChatCompletion,`resp.usage` **根本不存在** → 天真实现会把整个洞察生成少算成 0
token,且不报任何错。修法:见 _MeteredCompletions.create —— stream=True 时自动注入
stream_options={"include_usage": True}(OpenAI 标准:末 chunk 带 usage),BYOK 下厂商不认
(400)则退回普通流并把该次调用记为 **unmeasured**。宁可诚实报「有 N 次没算到」,
也绝不假装算准了 —— 少算的成本数字会直接毒化模型路由决策。
"""
from __future__ import annotations

import threading
from typing import Any, Iterator

from openai import BadRequestError


class TokenMeter:
    """线程安全的 per-node token 计量器。

    加锁的原因:节点内的 LLM 调用跑在嵌套 ThreadPoolExecutor 的 worker 线程里
    (analyst 竞品×抽取项、qc 逐 cell 蕴含判定),自增不加锁会丢计数。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.unmeasured_calls = 0

    def record(self, usage: Any) -> None:
        """记一次调用。usage 为 None(流式无 usage / 单测 fake client)→ 计入 unmeasured。"""
        if usage is None:
            self.record_unmeasured()
            return
        p = int(getattr(usage, "prompt_tokens", 0) or 0)
        c = int(getattr(usage, "completion_tokens", 0) or 0)
        with self._lock:
            self.prompt_tokens += p
            self.completion_tokens += c
            self.calls += 1

    def record_unmeasured(self) -> None:
        """记一次拿不到 usage 的调用:调用次数照计,token 不计,并显式留痕。"""
        with self._lock:
            self.calls += 1
            self.unmeasured_calls += 1

    @property
    def total_tokens(self) -> int:
        """OpenAI usage 契约:total = prompt + completion(reasoning token 已含在 completion 内)。"""
        return self.prompt_tokens + self.completion_tokens

    def trace_fields(self) -> dict[str, int]:
        """摊平成 append_trace 的关键字参数。"""
        return {
            "tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "llm_calls": self.calls,
        }

    def note(self) -> str:
        """未计量调用的可见性尾注(折进 trace.output_summary,同 analyze 的 degraded_note 风格)。

        非空即表示本节点的 token 数**不完整**,读数的人必须知道。"""
        if not self.unmeasured_calls:
            return ""
        return f" (未计量 LLM 调用 {self.unmeasured_calls} 次)"


class _MeteredCompletions:
    def __init__(self, inner: Any, meter: TokenMeter) -> None:
        self._inner = inner
        self._meter = meter

    def create(self, **kwargs: Any) -> Any:
        if not kwargs.get("stream"):
            resp = self._inner.create(**kwargs)
            self._meter.record(getattr(resp, "usage", None))
            return resp

        # 流式:请厂商在末 chunk 附 usage。调用方已显式传了 stream_options 就不覆盖。
        if "stream_options" in kwargs:
            stream = self._inner.create(**kwargs)
        else:
            try:
                stream = self._inner.create(**kwargs, stream_options={"include_usage": True})
            except BadRequestError as err:
                # 只接 400 = 厂商不认这个参数(BYOK 下厂商各异)。网络/鉴权错误照常上抛,
                # 绝不吞掉重试 —— 否则会把一次失败调用变成两次真实计费。
                # 且 400 必须**点名这个参数**才回退:别的 400(如 max_tokens 超上限)与
                # stream_options 无关,盲目重发一次注定同样失败的请求纯属浪费(对抗评审)。
                if not any(k in str(err) for k in ("stream_options", "include_usage")):
                    raise
                stream = self._inner.create(**kwargs)
        return self._tee(stream)

    def _tee(self, stream: Any) -> Iterator[Any]:
        """透传每个 chunk,顺手截获带 usage 的那个;没见到 usage → 记为未计量。

        finally 而非循环后直落:流中途抛异常(网络断)或消费方提前弃流(GeneratorExit)
        时,这次**真实计费**的调用会连「未计量」都记不上 —— 恰好违反本模块自己声明的
        诚实不变量(红队抓出)。finally 保证弃流/断流也至少留下未计量痕迹。"""
        seen = False
        try:
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    self._meter.record(usage)
                    seen = True
                yield chunk
        finally:
            if not seen:
                self._meter.record_unmeasured()


class _MeteredChat:
    def __init__(self, inner: Any, meter: TokenMeter) -> None:
        self._inner = inner
        self._meter = meter

    @property
    def completions(self) -> _MeteredCompletions:
        return _MeteredCompletions(self._inner.completions, self._meter)


class _MeteredClient:
    """包装 OpenAI 同步 client:只在 .chat.completions.create 路径计量,其余透传。

    __getattr__ 透传是**必须的**:structured.py 靠 `getattr(client, "api_key")` 取本次
    BYOK key 做日志脱敏,包装层吞掉这个属性就会让 provider 401 回显的 key 漏进日志。
    """

    def __init__(self, inner: Any, meter: TokenMeter) -> None:
        self._inner = inner
        self._meter = meter

    @property
    def chat(self) -> _MeteredChat:
        return _MeteredChat(self._inner.chat, self._meter)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def meter_client(client: Any, meter: TokenMeter | None) -> Any:
    """meter 为 None(单测/CLI/无计量)→ 原样返回;否则包一层每调用累加 usage。"""
    return client if meter is None else _MeteredClient(client, meter)
