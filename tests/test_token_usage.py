"""token 成本埋点(TokenMeter + 计量 client 包装 + trace 落库 + 老库迁移)。

为什么这套测试值得写细:一个**会静默少算**的成本指标,比没有指标更危险 —— 数字看起来
是真的,拿它去做模型路由决策就会做错。故这里逐条钉死「什么时候算得准 / 什么时候必须
诚实报未计量 / 什么时候绝不能算」。
"""
import threading
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError, BadRequestError

from rivalradar.api.schemas import TraceEntry
from rivalradar.graph.nodes import make_analyze_node
from rivalradar.llm.runcontrol import RunAborted, RunControl, wrap_client
from rivalradar.llm.usage import TokenMeter, meter_client
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


def _usage(prompt: int, completion: int):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def _bad_request() -> BadRequestError:
    """真 openai.BadRequestError(400)—— 厂商不认 stream_options 时 SDK 抛的就是它。"""
    req = httpx.Request("POST", "https://provider.example/v1/chat/completions")
    return BadRequestError("unknown field: stream_options",
                           response=httpx.Response(400, request=req), body=None)


class _Completions:
    """可编排的 fake:非流式返回带/不带 usage 的响应;流式返回 chunk 序列。

    stream_err:第一次带 stream_options 的调用抛出的异常(模拟厂商不认该参数)。
    """

    def __init__(self, *, usage=None, chunks=None, stream_err=None):
        self._usage = usage
        self._chunks = chunks or []
        self._stream_err = stream_err
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not kwargs.get("stream"):
            return SimpleNamespace(choices=[], usage=self._usage)
        if self._stream_err is not None and "stream_options" in kwargs:
            raise self._stream_err
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, completions: _Completions, api_key: str = "sk-secret"):
        self.chat = SimpleNamespace(completions=completions)
        self.api_key = api_key


def _chunk(*, content=None, usage=None):
    choices = [] if content is None else [SimpleNamespace(delta=SimpleNamespace(content=content))]
    return SimpleNamespace(choices=choices, usage=usage)


# ── TokenMeter 本身 ──────────────────────────────────────────────────────────

def test_meter_accumulates_and_totals():
    m = TokenMeter()
    m.record(_usage(100, 20))
    m.record(_usage(50, 5))
    assert (m.prompt_tokens, m.completion_tokens) == (150, 25)
    assert m.total_tokens == 175          # OpenAI 契约:total = prompt + completion
    assert m.calls == 2
    assert m.unmeasured_calls == 0
    assert m.note() == ""                 # 全算准了 → 无尾注
    assert m.trace_fields() == {"tokens": 175, "prompt_tokens": 150,
                                "completion_tokens": 25, "llm_calls": 2}


def test_meter_records_missing_usage_as_unmeasured_not_zero():
    """usage 拿不到时**照记调用次数**并留痕 —— 绝不静默当成 0 token 的成功调用。"""
    m = TokenMeter()
    m.record(None)
    assert m.total_tokens == 0
    assert m.calls == 1
    assert m.unmeasured_calls == 1
    assert "未计量" in m.note()           # 尾注非空 = 本节点 token 数不完整,读数的人必须知道


def test_meter_is_thread_safe():
    """analyst 竞品×抽取项、qc 逐 cell 蕴含都在 ThreadPoolExecutor worker 里调 LLM,
    不加锁会丢计数(丢的是成本,且丢得静默)。每线程只 record 一次撑不起真竞争
    (临界区三条 += 远短于 GIL 切换间隔,去掉锁也几乎必绿)—— 8 线程 × 2000 次
    连环 record 才能让无锁版本以高概率丢数(评审抓出弱断言)。"""
    m = TokenMeter()
    per_thread = 2000

    def hammer():
        for _ in range(per_thread):
            m.record(_usage(10, 1))

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = 8 * per_thread
    assert m.calls == total
    assert m.prompt_tokens == total * 10
    assert m.completion_tokens == total


def test_stream_abandoned_or_broken_still_records_unmeasured():
    """流中途断(网络)或消费方提前弃流(GeneratorExit)时,这次**真实计费**的调用
    必须至少记成未计量 —— 循环后直落的写法会让它连痕迹都不留,成本静默少算(红队)。"""
    meter = TokenMeter()
    comp = _Completions(chunks=[_chunk(content="a"), _chunk(content="b")])
    client = meter_client(_FakeClient(comp), meter)

    # ① 提前弃流:拿一个 chunk 就 close
    gen = client.chat.completions.create(model="m", messages=[], stream=True)
    next(gen)
    gen.close()
    assert meter.unmeasured_calls == 1

    # ② 流中途抛异常:上抛之余必须补记未计量
    def _broken():
        yield _chunk(content="a")
        raise RuntimeError("network drop")

    class _BrokenCompletions:
        def create(self, **kwargs):
            return _broken()

    client2 = meter_client(_FakeClient(_BrokenCompletions()), meter)
    gen2 = client2.chat.completions.create(model="m", messages=[], stream=True,
                                           stream_options={"include_usage": True})
    with pytest.raises(RuntimeError):
        list(gen2)
    assert meter.unmeasured_calls == 2


# ── 计量 client 包装 ─────────────────────────────────────────────────────────

def test_meter_client_without_meter_returns_client_unchanged():
    """单测 / CLI 无计量 → 原样返回,零包装、零行为改变(backward compat)。"""
    c = _FakeClient(_Completions())
    assert meter_client(c, None) is c


def test_non_stream_call_records_usage():
    comp = _Completions(usage=_usage(1200, 300))
    m = TokenMeter()
    meter_client(_FakeClient(comp), m).chat.completions.create(model="m", messages=[])
    assert m.trace_fields() == {"tokens": 1500, "prompt_tokens": 1200,
                                "completion_tokens": 300, "llm_calls": 1}


def test_non_stream_call_without_usage_is_unmeasured():
    comp = _Completions(usage=None)          # 厂商没回 usage
    m = TokenMeter()
    meter_client(_FakeClient(comp), m).chat.completions.create(model="m", messages=[])
    assert m.calls == 1 and m.unmeasured_calls == 1 and m.total_tokens == 0


def test_wrapper_passes_through_api_key_for_redaction():
    """structured.py 靠 getattr(client, 'api_key') 取 BYOK key 做日志脱敏。包装层若吞掉
    这个属性,provider 401 回显的 key 就会漏进服务端日志 —— 这条断言是防泄漏的门闩。"""
    wrapped = meter_client(_FakeClient(_Completions(), api_key="sk-live-123"), TokenMeter())
    assert wrapped.api_key == "sk-live-123"


# ── 流式:静默少算的重灾区 ───────────────────────────────────────────────────

def test_stream_injects_include_usage_and_captures_final_chunk():
    """writer 生成洞察走 stream_chat(stream=True)。SDK 流式响应本身没有 .usage,
    必须请厂商在末 chunk 附带;不这么做整个洞察生成会被静默少算成 0 token。"""
    chunks = [_chunk(content="你"), _chunk(content="好"), _chunk(usage=_usage(8000, 420))]
    comp = _Completions(chunks=chunks)
    m = TokenMeter()
    stream = meter_client(_FakeClient(comp), m).chat.completions.create(
        model="m", messages=[], stream=True)
    got = [c for c in stream]

    assert comp.calls[0]["stream_options"] == {"include_usage": True}  # 自动注入
    assert len(got) == 3                                # chunk 原样透传,不吞不改
    assert m.trace_fields()["tokens"] == 8420           # 末 chunk 的 usage 被截获
    assert m.unmeasured_calls == 0


def test_stream_falls_back_when_provider_rejects_stream_options():
    """BYOK 下厂商各异:不认 stream_options 的会回 400。此时退回普通流,内容照常送达,
    但**必须**记为未计量 —— 宁可诚实报「有 1 次没算到」,也绝不假装算准了。"""
    comp = _Completions(chunks=[_chunk(content="hi")], stream_err=_bad_request())
    m = TokenMeter()
    stream = meter_client(_FakeClient(comp), m).chat.completions.create(
        model="m", messages=[], stream=True)
    got = [c for c in stream]

    assert len(comp.calls) == 2                          # 第一次带参 400 → 第二次不带参重试
    assert "stream_options" not in comp.calls[1]
    assert len(got) == 1                                 # 内容不受影响,用户无感
    assert m.calls == 1 and m.unmeasured_calls == 1 and m.total_tokens == 0
    assert "未计量" in m.note()


def test_stream_unrelated_400_propagates_without_second_call():
    """400 必须**点名 stream_options/include_usage** 才回退。别的 400(如 max_tokens
    超上限)与该参数无关 —— 盲目重发一次注定同样失败的请求纯属浪费(对抗评审)。"""
    comp = _Completions(chunks=[], stream_err=_bad_request())
    comp._stream_err = BadRequestError(
        "max_tokens must be <= 8192",
        response=httpx.Response(400, request=httpx.Request(
            "POST", "https://provider.example/v1/chat/completions")),
        body=None)
    m = TokenMeter()
    with pytest.raises(BadRequestError):
        meter_client(_FakeClient(comp), m).chat.completions.create(
            model="m", messages=[], stream=True)
    assert len(comp.calls) == 1                          # 不点名该参数的 400:不重发


def test_stream_non_400_error_propagates_without_retry():
    """只有 400(厂商不认参数)才回退。网络/鉴权错误照常上抛 —— 若也重试,一次失败调用
    会被变成两次真实计费。"""
    comp = _Completions(chunks=[], stream_err=APITimeoutError(request=httpx.Request(
        "POST", "https://provider.example/v1/chat/completions")))
    m = TokenMeter()
    with pytest.raises(APITimeoutError):
        meter_client(_FakeClient(comp), m).chat.completions.create(
            model="m", messages=[], stream=True)
    assert len(comp.calls) == 1                          # 没有第二次调用 = 没有重复计费
    assert m.calls == 0


def test_stream_respects_caller_supplied_stream_options():
    """调用方显式传了 stream_options 就不覆盖(尊重调用方意图),该次记为未计量。"""
    comp = _Completions(chunks=[_chunk(content="x")])
    m = TokenMeter()
    stream = meter_client(_FakeClient(comp), m).chat.completions.create(
        model="m", messages=[], stream=True, stream_options={"include_usage": False})
    list(stream)
    assert comp.calls[0]["stream_options"] == {"include_usage": False}
    assert len(comp.calls) == 1
    assert m.unmeasured_calls == 1


# ── 与取消控制的组合 ─────────────────────────────────────────────────────────

def test_cancelled_call_never_counted_as_cost():
    """包装顺序 meter(外)→ cancellable(内):取消检查先于 HTTP 也先于计量。
    被 /cancel 掐掉的调用根本没发出去,绝不能进成本账。"""
    comp = _Completions(usage=_usage(999, 999))
    control = RunControl()
    control.cancel()
    m = TokenMeter()
    client = meter_client(wrap_client(_FakeClient(comp), control), m)

    with pytest.raises(RunAborted):
        client.chat.completions.create(model="m", messages=[])
    assert comp.calls == []                              # HTTP 根本没发
    assert m.calls == 0 and m.total_tokens == 0          # 也没进账


# ── 落库 + API schema ────────────────────────────────────────────────────────

def test_append_trace_persists_token_quadruple(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.append_trace(conn, "r1", "analyze", tokens=1500, prompt_tokens=1200,
                      completion_tokens=300, llm_calls=7, latency_ms=42)
    row = repo.list_trace(conn, "r1")[0]
    assert (row["tokens"], row["prompt_tokens"], row["completion_tokens"],
            row["llm_calls"]) == (1500, 1200, 300, 7)
    TraceEntry.model_validate(row)          # GET /trace/:run 能原样吐出去


def test_append_trace_defaults_to_zero_for_llm_free_nodes(conn):
    """collect(走 Tavily)/ finalize(纯本地)不调 LLM → 全 0。这是真实的 0,不是缺数据。"""
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.append_trace(conn, "r1", "collect", latency_ms=10)
    row = repo.list_trace(conn, "r1")[0]
    assert (row["tokens"], row["prompt_tokens"], row["completion_tokens"],
            row["llm_calls"]) == (0, 0, 0, 0)


def test_ensure_columns_adds_token_columns_to_legacy_trace(tmp_path):
    """老 db 的 trace 表没有这三列。CREATE TABLE IF NOT EXISTS **不会**给既有表加列 ——
    不做 ALTER,新代码第一次 INSERT 就炸。老行 DEFAULT 0 = 未计量,不回填、不假装有数据。
    """
    db = tmp_path / "legacy_trace.db"
    c = connect(str(db))
    c.executescript("""
        CREATE TABLE trace (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         TEXT NOT NULL,
            node           TEXT NOT NULL,
            prompt         TEXT,
            input_summary  TEXT,
            output_summary TEXT,
            tokens         INTEGER,
            latency_ms     INTEGER,
            ts             TEXT NOT NULL
        );
        INSERT INTO trace (run_id, node, tokens, latency_ms, ts)
        VALUES ('old_run', 'analyze', 0, 100, 't0');
    """)
    c.commit()

    init_db(c)      # 自适应迁移

    cols = {r[1] for r in c.execute("PRAGMA table_info(trace)").fetchall()}
    assert {"prompt_tokens", "completion_tokens", "llm_calls"} <= cols
    old = c.execute("SELECT * FROM trace WHERE run_id='old_run'").fetchone()
    assert (old["prompt_tokens"], old["completion_tokens"], old["llm_calls"]) == (0, 0, 0)

    init_db(c)      # 幂等:再跑一次不炸
    repo.create_run(c, "r2", ["N"], ["pricing"])
    repo.append_trace(c, "r2", "analyze", tokens=9, prompt_tokens=7, completion_tokens=2,
                      llm_calls=1)
    assert repo.list_trace(c, "r2")[0]["llm_calls"] == 1


class _FakePg:
    dialect = "pg"

    def __init__(self):
        self.statements: list[str] = []
        self.committed = False

    def execute(self, sql, params=()):  # noqa: ANN001
        self.statements.append(" ".join(sql.split()))

    def commit(self):
        self.committed = True


def test_init_db_pg_branch_runs_schema_and_trace_migrations(monkeypatch):
    """Postgres 分支:CREATE TABLE IF NOT EXISTS 对**既有表不加列**,三个 token 列必须
    靠 PG_MIGRATIONS 的 ALTER(ADD COLUMN IF NOT EXISTS,幂等)在首次 init 时跑。
    本地测试全走 SQLite 路径 —— 漏跑 PG 迁移不会有任何测试变红,只会在生产 Supabase
    首次 INSERT 时以 UndefinedColumn 暴露。这条用假 pg 连接把 PG 分支行为钉死。"""
    import rivalradar.storage.db as db_mod
    from rivalradar.storage.db import PG_MIGRATIONS

    monkeypatch.setattr(db_mod, "_PG_SCHEMA_READY", False)
    conn = _FakePg()
    init_db(conn)

    for stmt in PG_MIGRATIONS:                       # 三条 ALTER 一条不少
        assert stmt in conn.statements
    joined = " ".join(conn.statements)
    for col in ("prompt_tokens", "completion_tokens", "llm_calls"):
        assert f"ADD COLUMN IF NOT EXISTS {col}" in joined   # 幂等形态,非裸 ADD COLUMN
    assert any(s.startswith("CREATE TABLE IF NOT EXISTS trace") for s in conn.statements)
    assert conn.committed


def test_init_db_pg_ddl_runs_once_per_process(monkeypatch):
    """PG 的 ALTER TABLE 即使 no-op 也拿 ACCESS EXCLUSIVE 锁,而 init_db 每个请求都被
    get_db_conn 调一次 —— 不加进程级闸,每个请求都对最热的 trace 表拿排它锁,遇上
    SSE 回放的长事务就是锁车队(ship 前评审 CRITICAL)。失败必须**不**置位,下个请求重试。"""
    import rivalradar.storage.db as db_mod

    monkeypatch.setattr(db_mod, "_PG_SCHEMA_READY", False)

    first = _FakePg()
    init_db(first)
    assert first.statements                       # 首次:DDL 全跑

    second = _FakePg()
    init_db(second)
    assert second.statements == []                # 第二个请求(新连接):一条 DDL 都不发

    # 失败路径:commit 前抛异常 → 闸不置位 → 下一次照常重试
    monkeypatch.setattr(db_mod, "_PG_SCHEMA_READY", False)

    class _BoomPg(_FakePg):
        def commit(self):
            raise RuntimeError("network blip")

    with pytest.raises(RuntimeError):
        init_db(_BoomPg())
    retry = _FakePg()
    init_db(retry)
    assert retry.statements                       # 重试成功,DDL 重新跑齐


# ── 端到端:节点真的把 usage 写进了 trace ────────────────────────────────────

def test_run_client_shared_meter_accumulates_across_call_sites(conn):
    """qc/decide 各有**两个 LLM 调用点**,每个调用点单独过一次 _run_client 包装。
    不变量(nodes.py 注释声明,这里钉死):传同一个 meter 实例时,两处的 usage 必须
    合并累加成一份账。若未来有人在第二个调用点新建 meter,本测试变红。"""
    from rivalradar.graph.nodes import _run_client

    meter = TokenMeter()
    raw = _FakeClient(_Completions(usage=_usage(100, 10)))
    config: dict = {"configurable": {}}   # 无 RunControl:单测形态,只包计量层
    site_a = _run_client(raw, config, meter)
    site_b = _run_client(raw, config, meter)

    site_a.chat.completions.create(model="m", messages=[])
    site_b.chat.completions.create(model="m", messages=[])

    assert meter.calls == 2
    assert (meter.prompt_tokens, meter.completion_tokens) == (200, 20)
    assert meter.unmeasured_calls == 0


def test_write_node_writes_real_token_usage_to_trace(conn, monkeypatch):
    """write 节点同一条接线(meter → _run_client → agent → trace 行)的独立验证 ——
    analyze 的 e2e 挡不住有人只改 write 节点的接线。"""
    import rivalradar.graph.nodes as nodes_mod
    from rivalradar.schema.models import ReportInsight

    def _fake_write(analysis, evidence, *, as_of, client, model, emit=None):
        client.chat.completions.create(model=model, messages=[])
        return "报告正文", ReportInsight(
            market_context="c", differentiation_thesis="d", actionable_takeaway="a")

    monkeypatch.setattr(nodes_mod, "write_report_with_insight", _fake_write)
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    client = _FakeClient(_Completions(usage=_usage(500, 40)))
    node = nodes_mod.make_write_node(conn=conn, client=client, model="m", as_of="2026-07-14")

    node({"analysis": {"competitors": [], "comparison": []}, "evidence": []},
         {"configurable": {"thread_id": "r1"}})

    row = [r for r in repo.list_trace(conn, "r1") if r["node"] == "write"][0]
    assert row["llm_calls"] == 1
    assert (row["prompt_tokens"], row["completion_tokens"]) == (500, 40)
    assert row["tokens"] == 540
    assert "未计量" not in row["output_summary"]


def test_analyze_node_writes_real_token_usage_to_trace(conn, monkeypatch):
    """钉死整条接线:节点建 meter → _run_client 把它包进 client → agent 拿到的就是这个
    被计量的 client → 调用后的 usage 落进本节点的 trace 行。任一环断掉,tokens 就是 0。"""
    import rivalradar.graph.nodes as nodes_mod
    from rivalradar.schema.models import CompetitorAnalysis, CompetitorProfile, PricingModel, SWOT

    fake = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())], comparison=[])

    def _fake_analyze(evidence, competitors, *, dimensions=None, degraded_sink=None,
                      on_progress=None, on_cell_row=None, client, model):
        # 模拟 agent 内部的两次 LLM 调用 —— 走的必须是被计量的那个 client
        client.chat.completions.create(model=model, messages=[])
        client.chat.completions.create(model=model, messages=[])
        return fake

    monkeypatch.setattr(nodes_mod, "analyze", _fake_analyze)
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    client = _FakeClient(_Completions(usage=_usage(1000, 250)))
    node = make_analyze_node(conn=conn, client=client, model="m")
    ev = [{"id": "e1", "competitor": "Notion", "dimension": "pricing", "content": "c",
           "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]

    node({"competitors": ["Notion"], "evidence": ev}, {"configurable": {"thread_id": "r1"}})

    row = [r for r in repo.list_trace(conn, "r1") if r["node"] == "analyze"][0]
    assert row["llm_calls"] == 2                    # 两次调用都记到了
    assert row["prompt_tokens"] == 2000             # 1000 × 2
    assert row["completion_tokens"] == 500          # 250 × 2
    assert row["tokens"] == 2500
    assert "未计量" not in row["output_summary"]    # 全算准了,无尾注
