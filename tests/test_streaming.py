"""stream_chat wrapper tests(plan v3.2 §10 D5 Epic 7.5b + Epic 2.7)。

覆盖 3 个核心行为:
  1. 累积 chunks 返完整 text(skip None/empty content chunks)
  2. emit callback 每 chunk 调用一次,带 agent_id + step + delta payload
  3. emit=None 退化普通 stream,不 crash(backward compat 测试 / CLI 调用路径)

LLM 全 mock —— FakeClient 模拟 OpenAI streaming response shape
(chunk.choices[0].delta.content),不打真 API。
"""
from rivalradar.llm.streaming import stream_chat


# ── Mock OpenAI streaming response shape ─────────────────────────────────────


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return iter(self._chunks)


class _FakeChat:
    def __init__(self, chunks):
        self.completions = _FakeCompletions(chunks)


class _FakeClient:
    def __init__(self, chunks):
        self.chat = _FakeChat(chunks)


def test_stream_chat_aggregates_full_text_and_skips_empty_chunks():
    """正常 chunks 拼接成完整 text;None / empty content 被 skip 不进 text。"""
    chunks = [
        _FakeChunk(None),     # role chunk (OpenAI delta.content=None) — skip
        _FakeChunk("Hello"),
        _FakeChunk(""),       # empty string — skip
        _FakeChunk(" "),
        _FakeChunk("World"),
        _FakeChunk(None),     # 末尾 chunk content=None — skip
    ]
    client = _FakeClient(chunks)
    result = stream_chat([{"role": "user", "content": "x"}], client=client, model="ep-test")
    assert result == "Hello World"

    # 验 stream=True 被传给 client.chat.completions.create
    assert client.chat.completions.last_kwargs["stream"] is True


def test_stream_chat_emit_called_per_chunk_with_payload():
    """emit callback 每非空 chunk 调用一次,payload 含 agent_id + step + delta。"""
    chunks = [
        _FakeChunk("a"),
        _FakeChunk(None),  # skip,emit 不被调用
        _FakeChunk("b"),
        _FakeChunk("c"),
    ]
    client = _FakeClient(chunks)
    calls = []

    def emit(ev_type, data):
        calls.append((ev_type, data))

    result = stream_chat(
        [],
        client=client,
        model="ep-test",
        emit=emit,
        agent_id="analyst",
        step="thinking",
    )
    assert result == "abc"

    # 3 个非空 chunk → 3 次 emit
    assert len(calls) == 3
    assert all(c[0] == "chunk" for c in calls)
    assert calls[0][1] == {"agent_id": "analyst", "step": "thinking", "delta": "a"}
    assert calls[1][1] == {"agent_id": "analyst", "step": "thinking", "delta": "b"}
    assert calls[2][1] == {"agent_id": "analyst", "step": "thinking", "delta": "c"}


def test_stream_chat_emit_none_no_op_aggregates_correctly():
    """emit=None 不 crash,仍累积 text 返回。backward compat 路径 — tests
    不传 emit / CLI 调 stream_chat 走这条。"""
    chunks = [_FakeChunk("hello"), _FakeChunk(" world")]
    client = _FakeClient(chunks)
    # 不传 emit,默认 None
    result = stream_chat([], client=client, model="ep-test")
    assert result == "hello world"
