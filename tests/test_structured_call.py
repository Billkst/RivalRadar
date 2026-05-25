import json
from types import SimpleNamespace

import pytest

from rivalradar.llm.structured import StructuredCallError, structured_call
from rivalradar.schema.models import EvidenceRef


class _Completions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        content = self.responses[self.calls]
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
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


def test_none_content_retries_then_succeeds():
    client = FakeClient([None, _VALID])
    out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                          client=client, model="m", max_retries=2)
    assert out.evidence_id == "e1"
    assert client.chat.completions.calls == 2


def test_strips_markdown_fences():
    fenced = "```json\n" + _VALID + "\n```"
    client = FakeClient([fenced])
    out = structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                          client=client, model="m")
    assert out.evidence_id == "e1"
    assert client.chat.completions.calls == 1


def test_injects_schema_as_system_and_sends_no_response_format():
    # 目标模型不支持 response_format(json_schema/json_object 均 400);
    # 改为把 schema 注入 system 消息。锁定这一行为,防回归。
    client = FakeClient([_VALID])
    structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                    client=client, model="m")
    kwargs = client.chat.completions.last_kwargs
    assert "response_format" not in kwargs
    assert kwargs["messages"][0]["role"] == "system"
    assert "JSON Schema" in kwargs["messages"][0]["content"]
