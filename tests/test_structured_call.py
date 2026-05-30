import json
from types import SimpleNamespace

import pytest

from rivalradar.llm.structured import StructuredCallError, structured_call
from rivalradar.schema.models import EvidenceRef


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
