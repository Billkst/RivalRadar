"""厂商输出上限钳制:让「模型可插拔」在真 run 上真的成立。

背景(这批测试防的是什么病):`structured_call` 默认按 131072 要输出额度 —— 那是**火山方舟
端点的实测硬上限**,写死在 harness 里。BYOK 换成 DeepSeek/OpenAI 后:
  - `/llm/ping` 原先发 max_tokens=1 → **必过**;
  - 真 run 的第一次 structured_call 发 131072 → 400 → 被当网络抖动重试 3 次 → 死 run。
「测试通过、真跑就死」,而且用户会误以为是厂商不兼容。
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.llm.limits import cap_client
from rivalradar.llm.structured import _DEFAULT_MAX_TOKENS, StructuredCallError, structured_call
from rivalradar.schema.models import EvidenceRef


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "t.db")


class _Recorder:
    """记录每次 create 的 kwargs;可选择性抛异常。"""

    def __init__(self, err: Exception | None = None):
        self.calls: list[dict] = []
        self._err = err

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._err is not None:
            raise self._err
        return SimpleNamespace(choices=[], usage=None)


def _client(rec: _Recorder, api_key: str = "sk-secret"):
    return SimpleNamespace(chat=SimpleNamespace(completions=rec), api_key=api_key)


# ── 钳制本身 ─────────────────────────────────────────────────────────────────

def test_no_cap_returns_client_unchanged():
    """env(方舟)路径不声明上限 → 原样返回,行为与改动前逐字节一致。"""
    c = _client(_Recorder())
    assert cap_client(c, None) is c


def test_cap_clamps_oversized_request():
    """131072(方舟硬上限)对 DeepSeek 过大 → 被钳到厂商上限,而不是发出去挨 400。"""
    rec = _Recorder()
    cap_client(_client(rec), 8192).chat.completions.create(
        model="deepseek-chat", messages=[], max_tokens=_DEFAULT_MAX_TOKENS)
    assert rec.calls[0]["max_tokens"] == 8192


def test_cap_does_not_inflate_smaller_request():
    """取 min 而非覆盖:ping 若只要 1 个 token,不该被抬成上限值。"""
    rec = _Recorder()
    cap_client(_client(rec), 8192).chat.completions.create(
        model="m", messages=[], max_tokens=1)
    assert rec.calls[0]["max_tokens"] == 1


def test_cap_injects_when_max_tokens_absent():
    """调用方没传 max_tokens(如 writer 的流式 insight 草稿)→ cap 补上上限,让「声明了
    上限就对所有调用生效」的不变量真的成立(评审 F4)。补的是厂商允许的最大值,不截断。"""
    rec = _Recorder()
    cap_client(_client(rec), 8192).chat.completions.create(model="m", messages=[])
    assert rec.calls[0]["max_tokens"] == 8192


def test_cap_wrapper_passes_through_api_key_for_redaction():
    """脱敏门闩:structured.py 靠 getattr(client,'api_key') 取 key 打码,包装层不能吞掉它。"""
    assert cap_client(_client(_Recorder(), api_key="sk-live-9"), 8192).api_key == "sk-live-9"


# ── 400 快速失败(不再白烧 3 次调用)────────────────────────────────────────

def _bad_request(msg: str = "max_tokens must be <= 8192") -> openai.BadRequestError:
    req = httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
    return openai.BadRequestError(msg, response=httpx.Response(400, request=req), body=None)


def test_structured_call_fails_fast_on_400_without_retrying():
    """400 是**确定性**错误:同样的请求重试必然同样失败。原先它落进 APIError 分支被重试 3 次
    —— 白烧 3 次真金白银的调用(每次还叠一个 90s timeout),还把「我们发错了参数」的诊断
    埋进超时噪声里。必须一次就停,并把厂商的 400 原文(脱敏后)带出来。"""
    rec = _Recorder(err=_bad_request())
    with pytest.raises(StructuredCallError) as ei:
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=_client(rec), model="deepseek-chat")
    assert len(rec.calls) == 1                       # 只调了一次 = 没有重复计费
    assert "不重试" in str(ei.value)
    assert "max_tokens must be <= 8192" in str(ei.value)   # 厂商原文可见 = 一眼看懂病因


def test_structured_call_400_message_is_redacted():
    """400 的 body 可能回显 key(某些厂商会把整个请求回显)→ 必须脱敏后再进异常消息。"""
    rec = _Recorder(err=_bad_request("bad request with key sk-leak-abcdefgh12345"))
    with pytest.raises(StructuredCallError) as ei:
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=_client(rec, api_key="sk-leak-abcdefgh12345"),
                        model="m")
    assert "sk-leak-abcdefgh12345" not in str(ei.value)
    assert "***" in str(ei.value)


def test_structured_call_400_does_not_leak_key_via_exception_chain():
    """外层消息脱敏还不够:`from err` 会把**未脱敏**的原始 BadRequestError 挂到 __cause__ 上,
    调用方一句 logger.warning(..., exc_info=True)(analyst._safe_extract 正是如此)就把整条
    traceback(含 __cause__ 的 str)打进日志 → key 从异常链泄漏(评审 P1)。必须 from None 断链。"""
    import traceback

    leak = "sk-leak-abcdefgh12345"
    rec = _Recorder(err=_bad_request(f"provider echoed your key {leak}"))
    with pytest.raises(StructuredCallError) as ei:
        structured_call(EvidenceRef, [{"role": "user", "content": "x"}],
                        client=_client(rec, api_key=leak), model="m")
    exc = ei.value
    # from None:__cause__ 断开,__context__ 被抑制,exc_info 打印时不会带出原始异常
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    rendered = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    assert leak not in rendered, "key 从异常链(exc_info 渲染)泄漏"


# ── 端到端:头 → 钳制 → ping 发的是真 run 的那个值 ───────────────────────────

_BYOK = {
    "X-LLM-Base-URL": "https://api.deepseek.com/v1",
    "X-LLM-API-Key": "sk-user-key",
    "X-LLM-Model": "deepseek-chat",
}


def test_ping_sends_capped_max_tokens_matching_real_run(db_path, monkeypatch):
    """整条链的验收:声明上限 8192 → ping 实际发出 8192(= min(131072, 8192))。
    这正是真 run 的 structured_call 会发的值 —— **连通性测试与真 run 逐字节一致**。"""
    rec = _Recorder()
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", lambda **kw: _client(rec))
    client = TestClient(create_app(db_path=db_path, doubao_client=None))

    r = client.post("/llm/ping", headers={**_BYOK, "X-LLM-Max-Tokens": "8192"})

    assert r.status_code == 200 and r.json()["ok"] is True
    assert rec.calls[0]["max_tokens"] == 8192


def test_ping_without_cap_sends_full_default(db_path, monkeypatch):
    """不声明上限(老配置 / 方舟)→ 发默认 131072,与改动前一致。"""
    rec = _Recorder()
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", lambda **kw: _client(rec))
    client = TestClient(create_app(db_path=db_path, doubao_client=None))

    client.post("/llm/ping", headers=_BYOK)

    assert rec.calls[0]["max_tokens"] == _DEFAULT_MAX_TOKENS


def test_ping_classifies_400_as_bad_request(db_path, monkeypatch):
    """上限填得比厂商允许的大 → ping 当场分类 bad_request,前端渲染「按厂商文档调小」。
    这就是「点一下按钮就知道」而不是「跑 7 分钟死 run 才知道」。"""
    rec = _Recorder(err=_bad_request())
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", lambda **kw: _client(rec))
    client = TestClient(create_app(db_path=db_path, doubao_client=None))

    body = client.post("/llm/ping", headers={**_BYOK, "X-LLM-Max-Tokens": "999999"}).json()

    assert body["ok"] is False
    assert body["error_type"] == "bad_request"
    assert "max_tokens" in body["detail"]


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1048577", "1.5"])
def test_invalid_max_tokens_header_is_422_not_silently_ignored(db_path, monkeypatch, bad):
    """非法值必须 422。静默忽略最坏 —— 用户以为设了上限,真 run 仍按 131072 发出去挨 400,
    排查成本极高(界面显示「已配置 8192」,实际发的是 131072)。"""
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", lambda **kw: _client(_Recorder()))
    client = TestClient(create_app(db_path=db_path, doubao_client=None))

    r = client.post("/llm/ping", headers={**_BYOK, "X-LLM-Max-Tokens": bad})

    assert r.status_code == 422
    assert "X-LLM-Max-Tokens" in r.json()["detail"]


def test_max_tokens_header_alone_does_not_trigger_all_or_nothing(db_path):
    """第 4 个头是**可选**的,不进「全有或全无」契约:只给它(无三头)仍应走 env fallback
    路径的 503,而不是 422「BYOK 需三头齐全」—— 否则老前端一发这个头就全挂。"""
    client = TestClient(create_app(db_path=db_path, doubao_client=None))
    r = client.post("/llm/ping", headers={"X-LLM-Max-Tokens": "8192"})
    assert r.status_code == 200
    assert r.json()["error_type"] == "unconfigured"
