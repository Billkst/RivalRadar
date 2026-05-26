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
