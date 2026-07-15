"""BYOK(Bring Your Own Key):X-LLM-* 三请求头 → per-request LLM client。

契约:三头齐全走 BYOK(头里的 key/base_url/model 构造 per-request client);
只给 1-2 个 → 422(防静默 fallback);全无 → env fallback(app.state.doubao_client),
fallback 也没有 → 503。base_url 做 SSRF 校验(拒 IP 字面量 / localhost)。
POST /llm/ping 恒 200,ok/error_type 分类给前端「模型设置」测试按钮消费。

外部 openai.OpenAI 构造一律 monkeypatch 拦截(rivalradar.api.deps.OpenAI),不真打。
🔑 KEY 纪律:假 key 绝不落库 / 日志 / 响应,本文件有专门断言。
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from rivalradar.agents.discover import DiscoveredCompetitor, DiscoverySet
from rivalradar.api.app import create_app
from rivalradar.config import doubao_model
from rivalradar.llm.redact import redact
from rivalradar.llm.structured import _DEFAULT_MAX_TOKENS
from rivalradar.llm.structured import StructuredCallError, structured_call
from rivalradar.storage.db import connect, init_db

FAKE_KEY = "sk-fakeleak1234567890abcdef"
BYOK_HEADERS = {
    "X-LLM-Base-URL": "https://api.deepseek.com/v1",
    "X-LLM-API-Key": FAKE_KEY,
    "X-LLM-Model": "deepseek-chat",
}


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "byok.db")


def _discovery(*names: str) -> DiscoverySet:
    return DiscoverySet(competitors=[
        DiscoveredCompetitor(name=n, rationale="r") for n in names])


def _stub_chat_client(create_fn):
    """最小 OpenAI 形状 stub:只有 chat.completions.create。"""
    return SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create_fn)))


class _FakeOpenAI:
    """拦截 deps 模块内的 OpenAI 构造点,记录构造参数。"""
    last_kwargs: dict = {}

    def __init__(self, *, api_key: str, base_url: str, max_retries: int = 2,
                 http_client=None):
        _FakeOpenAI.last_kwargs = {
            "api_key": api_key, "base_url": base_url, "max_retries": max_retries,
            # 记录重定向策略而非 client 对象本身,方便断言(SSRF:必须 False)
            "follow_redirects": getattr(http_client, "follow_redirects", None),
        }
        if http_client is not None:
            http_client.close()  # 测试里别泄漏真 httpx client 的 socket


# ── 三头齐全 → per-request client ───────────────────────────────────────────
def test_byok_headers_build_per_request_client_for_discover(db_path, monkeypatch):
    """三头齐全:client 用头里的 key/base_url 构造,model 用头里的。"""
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", _FakeOpenAI)
    seen = {}

    def fake_discover(seed, hint, *, client, model):
        seen["client"], seen["model"] = client, model
        return _discovery("钉钉")

    monkeypatch.setattr("rivalradar.api.runs.discover_competitors", fake_discover)
    client = TestClient(create_app(db_path=db_path))  # 无 env fallback 也能走 BYOK
    r = client.post("/discover-competitors", json={"seed": "飞书"}, headers=BYOK_HEADERS)
    assert r.status_code == 200
    # max_retries=0 必须显式关掉:重试已活在 structured_call(3 次),SDK 默认 2 次
    # HTTP 重试会叠成最坏 9 次真请求;ping 黑洞域名时还占线程池 ~46s(红队)。
    # follow_redirects=False:堵「域名过校验→302 跳内网」的 SSRF 绕过(评审)。
    assert _FakeOpenAI.last_kwargs == {
        "api_key": FAKE_KEY, "base_url": "https://api.deepseek.com/v1",
        "max_retries": 0, "follow_redirects": False}
    assert isinstance(seen["client"], _FakeOpenAI)
    assert seen["model"] == "deepseek-chat"


def test_byok_headers_reach_research_graph_on_post_run(db_path, monkeypatch):
    """POST /run:BYOK client/model 必须一路传进 build_research_graph。"""
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", _FakeOpenAI)
    captured = {}

    def fake_build(**kw):
        captured.update(kw)
        raise HTTPException(418, "captured")  # 短路:不真跑图

    monkeypatch.setattr("rivalradar.api.runs.build_research_graph", fake_build)
    client = TestClient(create_app(db_path=db_path))
    r = client.post("/run", json={"competitors": ["Notion"], "dimensions": ["pricing"]},
                    headers=BYOK_HEADERS)
    assert r.status_code == 418
    assert isinstance(captured["client"], _FakeOpenAI)
    assert captured["model"] == "deepseek-chat"


# ── 只给 1-2 个头 → 422 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("keys", [
    ("X-LLM-Base-URL",),
    ("X-LLM-API-Key",),
    ("X-LLM-Model",),
    ("X-LLM-Base-URL", "X-LLM-API-Key"),
    ("X-LLM-Base-URL", "X-LLM-Model"),
    ("X-LLM-API-Key", "X-LLM-Model"),
])
def test_partial_headers_422(db_path, keys):
    """缺头必须硬报错,防静默 fallback 让用户以为在用自己配的模型。"""
    client = TestClient(create_app(db_path=db_path, doubao_client="stub"))
    headers = {k: BYOK_HEADERS[k] for k in keys}
    r = client.post("/discover-competitors", json={"seed": "飞书"}, headers=headers)
    assert r.status_code == 422
    assert r.json()["detail"] == (
        "BYOK 模式需同时提供 X-LLM-Base-URL / X-LLM-API-Key / X-LLM-Model 三个请求头")


# ── 无头 fallback ───────────────────────────────────────────────────────────
def test_no_headers_falls_back_to_env_client(db_path, monkeypatch):
    """无头 + app.state.doubao_client 非 None → 用 env 单例(现有行为不变)。"""
    seen = {}

    def fake_discover(seed, hint, *, client, model):
        seen["client"], seen["model"] = client, model
        return _discovery("钉钉")

    monkeypatch.setattr("rivalradar.api.runs.discover_competitors", fake_discover)
    # 不依赖机器上的私有 .env(克隆者没有它,测试会假红)—— 塞假 endpoint id
    monkeypatch.setenv("DOUBAO_MODEL", "ep-test-dummy-endpoint")
    client = TestClient(create_app(db_path=db_path, doubao_client="stub-client"))
    r = client.post("/discover-competitors", json={"seed": "飞书"})
    assert r.status_code == 200
    assert seen["client"] == "stub-client"
    assert seen["model"] == "ep-test-dummy-endpoint"


def test_no_headers_no_env_client_503_on_run_and_discover(db_path):
    """无头 + doubao_client=None → 503,detail 指引前端「模型设置」。"""
    client = TestClient(create_app(db_path=db_path))  # doubao_client 默认 None
    r1 = client.post("/discover-competitors", json={"seed": "飞书"})
    assert r1.status_code == 503
    assert "未配置模型" in r1.json()["detail"]
    r2 = client.post("/run", json={"competitors": ["Notion"], "dimensions": ["pricing"]})
    assert r2.status_code == 503
    assert "未配置模型" in r2.json()["detail"]


# ── base_url SSRF 校验 ──────────────────────────────────────────────────────
# scheme 拒绝:明文 http(key 裸奔,评审 P1)与非 http(s) 一律拒。
@pytest.mark.parametrize("bad_url", [
    "http://api.deepseek.com/v1",  # 明文 http:合法域名也拒 —— key 不能走明文
    "http://127.0.0.1:9999",       # 明文 + 回环
    "ftp://api.deepseek.com/v1",   # 非 http(s) scheme
    "https://[::1",                # 未闭合 IPv6 括号:urlparse.hostname 抛 ValueError,须 422 非 500
])
def test_bad_base_url_scheme_422(db_path, bad_url):
    client = TestClient(create_app(db_path=db_path))
    headers = dict(BYOK_HEADERS, **{"X-LLM-Base-URL": bad_url})
    r = client.post("/discover-competitors", json={"seed": "飞书"}, headers=headers)
    assert r.status_code == 422
    assert "https" in r.json()["detail"]


# 编码绕过拒绝(ASCII 形态,可经 HTTP 头传输):全部用 **https** scheme,确保真正走到 host
# 编码检查(而非在 scheme 就短路)。
@pytest.mark.parametrize("bad_url", [
    "https://localhost/",           # localhost 字面量
    "https://169.254.169.254/",     # 云 metadata 端点(点分)
    "https://[::1]/",               # IPv6 回环
    "https://2852039166/",          # 十进制 IP 编码(→ 169.254.169.254),绕字面量检测
    "https://0xA9FEA9FE/v1",        # 十六进制 IP 编码,同上
    "https://127.1/",               # 点分短写:inet_aton 语义解析到 127.0.0.1(评审实测绕过)
    "https://0177.0.0.1/",          # 点分八进制,同上
    "https://0x7f.0.0.1/v1",        # 点分十六进制,同上
    "https://169.254.169.254./",    # FQDN 尾点:ipaddress 判非字面量,OS 解析器照样送到 metadata
])
def test_bad_base_url_encoding_422(db_path, bad_url):
    client = TestClient(create_app(db_path=db_path))
    headers = dict(BYOK_HEADERS, **{"X-LLM-Base-URL": bad_url})
    r = client.post("/discover-competitors", json={"seed": "飞书"}, headers=headers)
    assert r.status_code == 422
    # 成功路径(正常域名通过)由 test_byok_headers_build_per_request_client_for_discover 覆盖


# Unicode/IDNA 归一化绕过:在**校验函数层**直接测,不经 HTTP 头 —— HTTP 头值是 latin-1,
# 原始 U+3002/全角字符根本传不过来(httpx/浏览器 fetch 都拒非 ASCII 头值,服务端也只会拿到
# latin-1 mojibake 而非真 Unicode)。所以这是**纵深防御**:防的是未来若 base_url 改从 JSON
# body / query 传入(UTF-8 原样到达)时的 IDNA 绕过(评审 F1)。校验器该识破,单元层钉死。
@pytest.mark.parametrize("bad_host_url", [
    "https://169。254。169。254/",   # 表意句号 U+3002 → IDNA 还原成点分 169.254.169.254
    "https://０x７f.0.0.1/",         # 全角 0x7f → NFKC 还原 0x7f.0.0.1 → 127.0.0.1
    "https://127．0．0．1/",          # 全角句号 U+FF0E → 127.0.0.1
])
def test_validate_base_url_rejects_unicode_idna_encodings(bad_host_url):
    from rivalradar.api.deps import _validate_base_url

    with pytest.raises(HTTPException) as ei:
        _validate_base_url(bad_host_url)
    assert ei.value.status_code == 422


# ── POST /llm/ping ──────────────────────────────────────────────────────────
def test_ping_ok_returns_latency(db_path, monkeypatch):
    """stub client 正常返回 → ok true + latency_ms;调用参数符合契约。"""
    monkeypatch.setenv("DOUBAO_MODEL", "ep-test-dummy-endpoint")  # 不依赖私有 .env
    calls = {}

    def create(**kw):
        calls.update(kw)
        return SimpleNamespace()

    client = TestClient(create_app(db_path=db_path, doubao_client=_stub_chat_client(create)))
    r = client.post("/llm/ping")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["latency_ms"], int)
    assert calls["model"] == doubao_model()
    assert calls["messages"] == [{"role": "user", "content": "ping"}]
    # 曾断言 == 1 —— **那条断言把 bug 钉死了**:ping 发 1 token 任何厂商都必过,
    # 而真 run 发 131072(方舟端点的实测硬上限)→ 换 DeepSeek/OpenAI 一律 400。
    # 「测试通过、真跑就死」。连通性测试必须发真 run 会发的那个值。
    assert calls["max_tokens"] == _DEFAULT_MAX_TOKENS
    assert calls["timeout"] == 15
    # 响应不带 usage / reasoning_content 时,归因字段必须省略(而非 null/0 占位)
    assert "completion_tokens" not in body
    assert "thinking" not in body


def test_ping_reports_completion_tokens_and_thinking(db_path):
    """默认开 thinking 的厂商(DeepSeek V4 系)延迟主要花在思考 token 上 ——
    ping 成功时把 completion_tokens / thinking 一并返回,让「XXXms」可归因
    (慢在思考还是慢在网络)。没有 token 数的延迟数字在推理模型上不可解读。"""
    def create(**kw):
        return SimpleNamespace(
            usage=SimpleNamespace(completion_tokens=512),
            choices=[SimpleNamespace(message=SimpleNamespace(
                content="pong", reasoning_content="模型的内部思考过程"))])

    client = TestClient(create_app(db_path=db_path, doubao_client=_stub_chat_client(create)))
    body = client.post("/llm/ping").json()
    assert body["ok"] is True
    assert body["completion_tokens"] == 512
    assert body["thinking"] is True
    # 思考/回答的**内容**都不进响应体(ping 是无鉴权公开端点,只回计数与布尔)
    assert "pong" not in str(body)
    assert "模型的内部思考过程" not in str(body)


def test_ping_auth_error_masks_key(db_path, monkeypatch):
    """AuthenticationError → error_type=auth;异常消息里的 key 必须被脱敏成 ***。"""
    def boom(**kw):
        raise openai.AuthenticationError(
            f"Incorrect API key provided: {FAKE_KEY} (also sk-otherleak987654321)",
            response=httpx.Response(401, request=httpx.Request("POST", "http://t")),
            body=None)

    monkeypatch.setattr("rivalradar.api.deps.OpenAI",
                        lambda **kw: _stub_chat_client(boom))
    client = TestClient(create_app(db_path=db_path))
    r = client.post("/llm/ping", headers=BYOK_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error_type"] == "auth"
    assert FAKE_KEY not in body["detail"]                 # 头里的 key 被替换
    assert "sk-otherleak987654321" not in body["detail"]  # sk- 正则打码
    assert "***" in body["detail"]
    assert len(body["detail"]) <= 200


def test_ping_timeout_error(db_path):
    def boom(**kw):
        raise openai.APITimeoutError(request=httpx.Request("POST", "http://t"))

    client = TestClient(create_app(db_path=db_path, doubao_client=_stub_chat_client(boom)))
    body = client.post("/llm/ping").json()
    assert body["ok"] is False
    assert body["error_type"] == "timeout"


@pytest.mark.parametrize("exc_factory,expected", [
    (lambda: openai.NotFoundError(
        "model not found",
        response=httpx.Response(404, request=httpx.Request("POST", "http://t")),
        body=None), "not_found"),
    (lambda: openai.APIConnectionError(
        request=httpx.Request("POST", "http://t")), "connection"),
    (lambda: ValueError("boom"), "other"),
])
def test_ping_error_classification(db_path, exc_factory, expected):
    """其余分类分支:not_found / connection / other。"""
    def boom(**kw):
        raise exc_factory()

    client = TestClient(create_app(db_path=db_path, doubao_client=_stub_chat_client(boom)))
    body = client.post("/llm/ping").json()
    assert body["ok"] is False
    assert body["error_type"] == expected


def test_ping_unconfigured(db_path):
    """无头 + 无 env fallback:ping 返 200 分类结果(unconfigured),不是 503。"""
    client = TestClient(create_app(db_path=db_path))
    r = client.post("/llm/ping")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error_type"] == "unconfigured"


def test_ping_partial_headers_still_422(db_path):
    """ping 的头解析与其他端点一致:缺头照样 422(只有未配置才特殊化)。"""
    client = TestClient(create_app(db_path=db_path))
    r = client.post("/llm/ping", headers={"X-LLM-API-Key": FAKE_KEY})
    assert r.status_code == 422


# ── discover 的 BYOK 专属 503 文案 ──────────────────────────────────────────
def test_discover_503_byok_message_surfaces_root_cause(db_path, monkeypatch):
    """BYOK 的 503 必须透传 StructuredCallError 原文(已脱敏)。曾只回一句
    「检查 base_url / API Key / 模型名」—— 三样全对时(ping 通、真调被厂商 400 拒)
    用户被指去检查根本没错的东西,厂商的真实拒因被吞掉(DeepSeek 首跑实测踩中)。"""
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", _FakeOpenAI)

    def boom(*a, **k):
        raise StructuredCallError("被厂商拒绝(400,不重试):Invalid tool_choice")

    monkeypatch.setattr("rivalradar.api.runs.discover_competitors", boom)
    client = TestClient(create_app(db_path=db_path))
    r = client.post("/discover-competitors", json={"seed": "飞书"}, headers=BYOK_HEADERS)
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "Invalid tool_choice" in detail  # 厂商拒因必须可见,不许再吞
    # 「竞品发现失败:」前缀由前端加(RunsPage.tsx),后端不加,防双重前缀
    assert not detail.startswith("竞品发现失败")


def test_discover_503_env_keeps_original_message(db_path, monkeypatch):
    def boom(*a, **k):
        raise StructuredCallError("llm down")

    monkeypatch.setattr("rivalradar.api.runs.discover_competitors", boom)
    client = TestClient(create_app(db_path=db_path, doubao_client="stub"))
    r = client.post("/discover-competitors", json={"seed": "飞书"})
    assert r.status_code == 503
    assert r.json()["detail"] == "竞品发现暂时不可用,请手动输入竞品名"


# ── KEY 纪律:key 绝不落地 ──────────────────────────────────────────────────
def test_key_never_lands_in_db_logs_or_response(db_path, monkeypatch, caplog):
    """带假 key 跑 discover(失败路径)+ POST /run(真实落库路径),之后全表扫
    sqlite + caplog:key 零出现。曾只打 discover —— 它不带 conn 依赖、零写库,
    全表扫的是空库,断言恒真(评审抓出的空转测试)。post_run 的 create_run 在
    图构建**之前**落库,418 短路图构建后 runs 表里就有 BYOK 请求写下的真行。"""
    monkeypatch.setattr("rivalradar.api.deps.OpenAI", _FakeOpenAI)

    def boom(*a, **k):
        raise StructuredCallError("llm down")

    def fake_build(**kw):
        raise HTTPException(418, "captured")  # 短路:不真跑图,但 create_run 已落库

    monkeypatch.setattr("rivalradar.api.runs.discover_competitors", boom)
    monkeypatch.setattr("rivalradar.api.runs.build_research_graph", fake_build)
    client = TestClient(create_app(db_path=db_path))
    with caplog.at_level(logging.DEBUG):
        r = client.post("/discover-competitors", json={"seed": "飞书"},
                        headers=BYOK_HEADERS)
        r2 = client.post("/run", json={"competitors": ["钉钉"], "dimensions": ["pricing"]},
                         headers=BYOK_HEADERS)
    assert FAKE_KEY not in r.text            # 响应不回显
    assert FAKE_KEY not in r2.text
    assert FAKE_KEY not in caplog.text       # 日志不出现

    # 全表扫 sqlite:任何表任何行都不得含假 key
    c = connect(db_path)
    init_db(c)
    assert c.execute("SELECT count(*) FROM runs").fetchone()[0] > 0, \
        "扫描前提:BYOK 请求确已写库(否则又是空转)"
    tables = [row[0] for row in
              c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert tables, "schema 未建表,扫描无意义"
    for t in tables:
        rows = c.execute(f"SELECT * FROM {t}").fetchall()  # noqa: S608 — 表名来自 sqlite_master
        assert FAKE_KEY not in str(rows), f"key 泄漏到表 {t}"
    c.close()


# ── redact 脱敏单元 ─────────────────────────────────────────────────────────
def test_redact_masks_patterns_and_secrets():
    """正则打 sk-/Bearer 形态;精确 secret 打非 sk- 形态(如火山方舟 UUID);空 secret 跳过。"""
    assert redact("key sk-abcdefgh12345678 end") == "key *** end"
    assert redact("auth Bearer tok_abcdefgh12") == "auth ***"
    assert redact("id ep-20250101-xyz done", "ep-20250101-xyz") == "id *** done"
    assert redact("plain text") == "plain text"          # 无 key,原样
    assert redact("k sk-SECRETSECRET1", None, "") == "k ***"  # None/空 secret 不报错


def _client_with_key(api_key, create_fn):
    """带 api_key 属性的 chat client stub —— structured_call 从此取精确 key 值脱敏。"""
    ns = _stub_chat_client(create_fn)
    ns.api_key = api_key
    return ns


def test_structured_call_redacts_key_in_logs_and_error(caplog):
    """核心防线:provider 401 body 回显 BYOK key → structured_call 的 logger.warning
    与 StructuredCallError 消息都必须脱敏。审查发现现有 KEY 纪律测试短路了这条真实路径。"""
    uuid_key = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # 火山方舟 UUID 形态,sk- 正则打不到

    def boom(**kw):
        raise openai.AuthenticationError(
            f"Incorrect API key: {uuid_key} / sk-anotherleak12345678",
            response=httpx.Response(401, request=httpx.Request("POST", "http://t")),
            body=None)

    client = _client_with_key(uuid_key, boom)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(StructuredCallError) as ei:
            structured_call(DiscoveredCompetitor,
                            [{"role": "user", "content": "x"}],
                            client=client, model="deepseek-chat", max_retries=0)
    # UUID 形态靠精确 secret(client.api_key)打掉,sk- 形态靠正则兜底
    for leak in (uuid_key, "sk-anotherleak12345678"):
        assert leak not in caplog.text, f"key 泄漏进日志:{leak}"
        assert leak not in str(ei.value), f"key 泄漏进异常消息:{leak}"
    assert "***" in str(ei.value)


def test_ping_env_fallback_masks_endpoint_id(db_path, monkeypatch):
    """env fallback:上游错误里的 DOUBAO_MODEL endpoint ID 也必须脱敏(视同 KEY 敏感);
    /llm/ping 是无鉴权公开端点,不能把服务端自有凭据的上游报错回显给客户端。"""
    monkeypatch.setenv("DOUBAO_MODEL", "ep-test-dummy-endpoint")  # 不依赖私有 .env
    model = doubao_model()

    def boom(**kw):
        raise openai.NotFoundError(
            f"The model or endpoint {model} does not exist",
            response=httpx.Response(404, request=httpx.Request("POST", "http://t")),
            body=None)

    client = TestClient(create_app(db_path=db_path, doubao_client=_stub_chat_client(boom)))
    r = client.post("/llm/ping")  # 无头 → env source
    body = r.json()
    assert body["error_type"] == "not_found"
    assert model not in body["detail"], "endpoint id 泄漏进 ping 响应"
    assert "***" in body["detail"]


def test_env_fallback_missing_model_returns_503_not_500(db_path, monkeypatch):
    """配了 env client 却漏设 DOUBAO_MODEL:视为未配置返 503,而非 ValueError 穿透成 500。"""
    def no_model():
        raise ValueError("DOUBAO_MODEL is not set")

    monkeypatch.setattr("rivalradar.api.deps.doubao_model", no_model)
    client = TestClient(create_app(db_path=db_path, doubao_client="stub"))
    r = client.post("/run", json={"competitors": ["X"], "dimensions": ["pricing"]})
    assert r.status_code == 503
    assert "未配置模型" in r.json()["detail"]
    # ping 恒 200 契约:未配置 model → unconfigured 分类,不是 500
    r2 = client.post("/llm/ping")
    assert r2.status_code == 200
    assert r2.json()["error_type"] == "unconfigured"
