import json
from types import SimpleNamespace

import pytest

import rivalradar.llm.structured as structured_mod
from rivalradar.llm.structured import StructuredCallError, structured_call
from rivalradar.schema.models import EvidenceRef


@pytest.fixture(autouse=True)
def _fresh_tool_choice_memory():
    """降级记忆是进程级的 —— 不清空则测试互相污染(先跑的降级测试会让后跑的
    「首发带 tool_choice」断言失败),且暴露测试执行顺序依赖。"""
    structured_mod._NAMED_TOOL_CHOICE_REJECTED.clear()
    yield
    structured_mod._NAMED_TOOL_CHOICE_REJECTED.clear()


class _Completions:
    """模拟 OpenAI 兼容端点的 function-calling 响应。

    responses 里每一项:
    - str  → 当作 tool_call 的 arguments JSON 字符串
    - None → 模型没调用工具(无 tool_calls)
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        item = self.responses[self.calls]
        self.calls += 1
        if item is None:
            tool_calls = None
        else:
            tool_calls = [SimpleNamespace(function=SimpleNamespace(arguments=item))]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=tool_calls))],
            usage=SimpleNamespace(total_tokens=10),
        )


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_Completions(responses))


_VALID = json.dumps({"evidence_id": "e1", "quote": "每月 $10 起", "support_verdict": "supported"})
_BAD = "{not json"


def test_returns_validated_model_on_first_success():
    client = FakeClient([_VALID])
    out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                          client=client, model="m")
    assert isinstance(out, EvidenceRef)
    assert out.evidence_id == "e1"
    assert client.chat.completions.calls == 1


def test_retries_with_error_then_succeeds():
    client = FakeClient([_BAD, _VALID])
    out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                          client=client, model="m", max_retries=2)
    assert out.evidence_id == "e1"
    assert client.chat.completions.calls == 2


def test_raises_explicitly_after_cap():
    client = FakeClient([_BAD, _BAD, _BAD])
    with pytest.raises(StructuredCallError):
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=client, model="m", max_retries=2)
    assert client.chat.completions.calls == 3


def test_missing_tool_call_retries_then_succeeds():
    # 模型某次没调用工具(tool_calls=None)→ 当作失败重试,而非崩或静默
    client = FakeClient([None, _VALID])
    out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                          client=client, model="m", max_retries=2)
    assert out.evidence_id == "e1"
    assert client.chat.completions.calls == 2


def test_forces_tool_choice_and_sends_no_response_format():
    # 目标模型不支持 response_format;改用 tools+强制 tool_choice。锁定行为防回归。
    client = FakeClient([_VALID])
    structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                    client=client, model="m")
    kwargs = client.chat.completions.last_kwargs
    assert "response_format" not in kwargs
    assert kwargs["tool_choice"]["function"]["name"] == "emit_result"
    assert kwargs["tools"][0]["function"]["name"] == "emit_result"
    # schema 作为工具 parameters 传入(含 EvidenceRef 字段)
    assert "evidence_id" in kwargs["tools"][0]["function"]["parameters"]["properties"]


def test_passes_timeout_to_sdk_call():
    """post-real-run fix:防 Doubao SDK hang(Clash fake-ip 慢路径实测 14 min)。

    timeout 范围 30-180s:backend realistic call(172 evidence ~34K char input)
    实测 35-70s,90s 是 ~1.3x headroom + Clash 抖动 cap;< 30s 必 false positive。
    """
    client = FakeClient([_VALID])
    structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                    client=client, model="m")
    kwargs = client.chat.completions.last_kwargs
    assert "timeout" in kwargs
    assert 30 <= kwargs["timeout"] <= 180


def test_passes_generous_max_tokens_to_sdk_call():
    """真 run 钓出:不设 max_tokens 走默认(~4096)→ 大 feature 列表 JSON 被截断 →
    Unterminated string → StructuredCallError 杀死整个 run。给足 16384+ 防截断。"""
    client = FakeClient([_VALID])
    structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                    client=client, model="m")
    kwargs = client.chat.completions.last_kwargs
    assert "max_tokens" in kwargs
    assert kwargs["max_tokens"] >= 16384


class _NetworkErrorClient:
    """模拟 SDK 抛 APITimeoutError / APIConnectionError 等网络层异常。"""
    def __init__(self, errors_then_responses):
        from openai import APITimeoutError
        self._items = list(errors_then_responses)
        self.calls = 0
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        item = self._items[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        tool_calls = [SimpleNamespace(function=SimpleNamespace(arguments=item))]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=tool_calls))],
            usage=SimpleNamespace(total_tokens=10),
        )


class _ToolChoiceRejectingClient:
    """模拟 DeepSeek V4 thinking 模式(默认开):带点名 tool_choice 的请求一律 400,
    去掉该参数就正常。responses 语义同 _Completions(str=工具参数 JSON,None=没调工具)。"""

    def __init__(self, responses):
        import httpx
        from openai import BadRequestError
        self._responses = list(responses)
        self._reject = BadRequestError(
            "Error code: 400 - {'error': {'message': 'Thinking mode does not "
            "support this tool_choice', 'type': 'invalid_request_error'}}",
            response=httpx.Response(
                400, request=httpx.Request("POST", "https://api.deepseek.com/x")),
            body=None)
        self.calls = []  # 每次调用的完整 kwargs
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if "tool_choice" in kwargs:
            raise self._reject
        item = self._responses.pop(0)
        tool_calls = (
            [SimpleNamespace(function=SimpleNamespace(arguments=item))] if item else None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=tool_calls))],
            usage=SimpleNamespace(total_tokens=10))


def test_downgrades_tool_choice_when_vendor_rejects_it(caplog):
    """DeepSeek V4 thinking 模式不支持点名 tool_choice(首跑实测 400)。
    对策:400 文案点名 tool_choice 时**去掉该参数重发**(带 tools 时厂商默认 auto),
    「必须调用工具」的契约由校验重试循环兜底 —— 厂商无关,不嗅探厂商名。"""
    import logging
    client = _ToolChoiceRejectingClient([_VALID])
    with caplog.at_level(logging.WARNING):
        out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                              client=client, model="deepseek-v4-flash", max_retries=2)
    assert out.evidence_id == "e1"
    assert len(client.calls) == 2
    assert "tool_choice" in client.calls[0]          # 首选仍是点名(Doubao 实测最稳)
    assert "tool_choice" not in client.calls[1]      # 被拒后去掉重发
    assert client.calls[1]["tools"][0]["function"]["name"] == "emit_result"  # tools 保留
    assert any("tool_choice" in r.message for r in caplog.records)  # 降级必须留日志痕迹


def test_downgraded_call_still_enforces_tool_call_via_retry_loop():
    """降级成 auto 后模型可能不调工具 → 走原有校验重试(而非崩/静默),且不再回退点名。"""
    client = _ToolChoiceRejectingClient([None, _VALID])
    out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                          client=client, model="deepseek-v4-flash", max_retries=2)
    assert out.evidence_id == "e1"
    assert len(client.calls) == 3  # 400 → 没调工具 → 成功
    assert all("tool_choice" not in kw for kw in client.calls[1:])


def test_tool_choice_rejection_is_memoized_across_calls():
    """降级是厂商行为的确定性事实:同一 (base_url, model) 的**第二次** structured_call
    必须直接跳过点名探测(首个请求就不带 tool_choice)—— 不记忆的话,满矩阵 65 次
    调用每次都白付一次注定 400 的全 payload 往返(ship 前评审 CRITICAL)。"""
    client = _ToolChoiceRejectingClient([_VALID, _VALID])
    structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                    client=client, model="deepseek-v4-flash", max_retries=2)
    assert len(client.calls) == 2                    # 第一次:400 探测 + 降级重发

    out = structured_call(EvidenceRef, [{"role": "user", "content": "y"}],
                          client=client, model="deepseek-v4-flash", max_retries=2)
    assert out.evidence_id == "e1"
    assert len(client.calls) == 3                    # 第二次:只发 1 个请求
    assert "tool_choice" not in client.calls[2]      # 且首发就不带点名

    # 不同模型不受污染:记忆按 (base_url, model) 分键
    other = _ToolChoiceRejectingClient([_VALID])
    structured_call(EvidenceRef, [{"role": "user", "content": "z"}],
                    client=other, model="another-model", max_retries=2)
    assert "tool_choice" in other.calls[0]           # 新模型仍然首选点名探测


def test_memo_not_poisoned_when_downgraded_call_also_400s():
    """记忆必须**先降级、后验证、才写入**:任何恰好含 "tool_choice" 字样的无关 400
    (如 tools schema 报错文案提及它)若在降级瞬间就写记忆,会把 (base_url, model)
    永久毒化 —— 之后所有调用都不再点名,而真正的病根没人发现(红队)。"""
    import httpx
    from openai import BadRequestError

    class _Always400:
        """带 tool_choice → 400 提及 tool_choice;去掉后 → 400 换个理由(拒因另有其人)。"""
        def __init__(self):
            self.calls = []
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            self.calls.append(kwargs)
            msg = ("tools and tool_choice require ..." if "tool_choice" in kwargs
                   else "max_tokens must be <= 8192")
            raise BadRequestError(msg, response=httpx.Response(
                400, request=httpx.Request("POST", "https://x")), body=None)

    client = _Always400()
    with pytest.raises(StructuredCallError):
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=client, model="m", max_retries=2)
    assert len(client.calls) == 2                    # 探测 400 + 降级仍 400 → 快失败
    assert not structured_mod._NAMED_TOOL_CHOICE_REJECTED  # 降级没被厂商接受 → 不写记忆

    client2 = _Always400()
    with pytest.raises(StructuredCallError):
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=client2, model="m", max_retries=2)
    assert "tool_choice" in client2.calls[0]         # 下一次调用仍首选点名(未被毒化)


def test_tool_choice_downgrade_does_not_consume_an_attempt():
    """400 参数协商 ≠ 一次「尝试」。真 run 实测踩中:SWOT 格的 3 次尝试被 400 探测
    吃掉 1 次,只剩 2 次真机会(一次没调工具 + 一次坏 JSON)就到顶被跳过 ——
    降级后模型仍应有完整的 max_retries+1 次输出机会。"""
    client = _ToolChoiceRejectingClient([_BAD, _BAD, _VALID])
    out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                          client=client, model="deepseek-v4-flash", max_retries=2)
    assert out.evidence_id == "e1"
    assert len(client.calls) == 4  # 400 探测 + 完整 3 次真尝试(坏、坏、成)


def test_400_without_tool_choice_mention_still_fails_fast():
    """降级只对点名拒绝 tool_choice 的 400 生效;其余 400(如 max_tokens 超上限)
    仍走确定性快失败,不进重试。(限位细节见 test_llm_limits.py)"""
    from openai import BadRequestError
    import httpx
    err = BadRequestError(
        "max_tokens must be <= 8192",
        response=httpx.Response(400, request=httpx.Request("POST", "https://x")),
        body=None)
    client = _NetworkErrorClient([err])
    with pytest.raises(StructuredCallError) as ei:
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=client, model="m", max_retries=2)
    assert client.chat.completions.calls == 1
    assert "max_tokens must be <= 8192" in str(ei.value)


def test_recovers_from_transient_timeout_then_succeeds(caplog):
    """post-real-run fix:第 1 次 APITimeoutError → 第 2 次成功返回。"""
    from openai import APITimeoutError
    import httpx, logging
    err = APITimeoutError(request=httpx.Request("POST", "https://x"))
    client = _NetworkErrorClient([err, _VALID])
    with caplog.at_level(logging.WARNING):
        out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                              client=client, model="m", max_retries=2)
    assert out.evidence_id == "e1"
    assert client.chat.completions.calls == 2
    assert any("network error" in r.message for r in caplog.records)


def test_raises_after_all_retries_exhausted_by_network_errors():
    """post-real-run fix:全部 retry 都 timeout → 显式 StructuredCallError 让上层降级。"""
    from openai import APITimeoutError
    import httpx
    err1 = APITimeoutError(request=httpx.Request("POST", "https://x"))
    err2 = APITimeoutError(request=httpx.Request("POST", "https://x"))
    err3 = APITimeoutError(request=httpx.Request("POST", "https://x"))
    client = _NetworkErrorClient([err1, err2, err3])
    with pytest.raises(StructuredCallError) as exc_info:
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=client, model="m", max_retries=2)
    msg = str(exc_info.value).lower()
    assert "timed out" in msg or "timeout" in msg
    assert client.chat.completions.calls == 3
