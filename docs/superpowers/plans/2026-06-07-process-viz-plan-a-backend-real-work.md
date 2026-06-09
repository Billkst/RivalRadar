# Plan A — 后端「看得见真实活儿」+ Doubao 两步化 spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让后端把「采集员真实在干的活」(真实查询词、命中数、新来源卡、retry 增量)通过 SSE 实时发出来并持久化,并先用 spike 验证 insight 两步化字符流在 Doubao 上可行。

**Architecture:** 沿用现有「SSE 发轻量事件 + 节点经 `config["configurable"]["emit"]` 注入回调」架构(`sse.py:143-166`)。新增 4 类 SSE 事件(`query`/`query_hit`/`source`/`evidence_delta`),由 `collect_node` 在采集时发出;真实查询词新增 `queries` 表持久化 + REST。**本 Plan 只动后端**,前端消费这些事件在 Plan C。Doubao 两步化字符流先做 spike(Epic 0),实现留 Plan B。

**Tech Stack:** Python 3 · LangGraph(sync 节点)· sqlite3(WAL)· FastAPI · pydantic · pytest(monkeypatch + tmp_path)· OpenAI 兼容 Doubao SDK。

**来源 spec:** `docs/superpowers/specs/2026-06-07-process-viz-redesign-design.md`(§5.1 / §5.2 / §5.4 / §5.6 / §7.1 / §7.3)。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `spikes/spike_insight_two_step.py` | 验证 stream_chat 流式 + 两步抽取 ReportInsight 在 Doubao 可行 | Create |
| `rivalradar/storage/db.py` | 加 `queries` 表 schema | Modify(`SCHEMA` 串)|
| `rivalradar/storage/repository.py` | `insert_queries` / `list_queries` CRUD | Modify |
| `rivalradar/collect/pipeline.py` | `collect()` 加 `on_query` 回调(每 query 完成报 Query+evidence)| Modify |
| `rivalradar/agents/collector.py` | `collect_evidence()` 透传 `on_query` | Modify |
| `rivalradar/graph/nodes.py` | `collect_node` 发 query/query_hit/source/evidence_delta + round 推导 + 持久化 queries | Modify |
| `rivalradar/api/schemas.py` | `SSEQueryData` / `SSEQueryHitData` / `SSESourceData` / `SSEEvidenceDeltaData` | Modify |
| `rivalradar/api/reads.py` | `GET /runs/{run_id}/queries` | Modify |
| `tests/test_queries_repo.py` | queries 表 CRUD 测试 | Create |
| `tests/test_collect_pipeline.py` | `on_query` 回调测试 | Modify |
| `tests/test_collect_node_emit.py` | collect_node 发 4 类事件 + round + 持久化测试 | Create |
| `tests/test_api_reads.py` | `GET /runs/{id}/queries` 测试 | Modify |

---

## Epic 0: Doubao 两步化字符流可行性 spike

> 这是全 plan 链最高风险(spec §5.6 / §11)。spike 不进 pytest(真打 LLM,放 `spikes/`)。**先跑通再继续后续 Epic**——若 spike 证明 stream 不稳,Plan B 的 insight 两步化回落一次性(数据仍真,只是无 typing)。

### Task 0: 写 + 跑 insight 两步化 spike

**Files:**
- Create: `spikes/spike_insight_two_step.py`

- [ ] **Step 1: 写 spike 脚本**

```python
"""insight 两步化 spike:验证 (1) stream_chat 在 Doubao 真流 delta;(2) 草稿可被
structured_call 抽成合法 ReportInsight。需 ARK_API_KEY。不进 pytest(真打 LLM)。

跑法(WSL2 Clash:codex 走海外要代理,但 Doubao 是国内端点,务必 unset 代理 + NO_PROXY):
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
  NO_PROXY=localhost,127.0.0.1 .venv/bin/python spikes/spike_insight_two_step.py
"""
from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.agents.writer import generate_insight, render_body
from rivalradar.llm.streaming import stream_chat
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, ComparisonRow, ComparisonCell,
    Evidence, EvidenceRef, PricingModel, PricingTier, SWOT, SWOTPoint,
)

# production-size 近似:3 竞品 × 多维 body(真实 run body ~数 KB)。若要真·production
# size,把 BODY 换成某真实 run 的 GET /analysis 渲染结果(render_body 输出)。
_EV = [
    Evidence(id=f"e{i}", competitor=c, dimension=d,
             content=f"{c} 在 {d} 维度的公开资料正文片段。" * 8,
             source_url=f"https://example.com/{c}/{d}", source_title=f"{c} {d}",
             language="zh", fetched_at="2026-06-01T00:00:00Z")
    for i, (c, d) in enumerate(
        [(c, d) for c in ("飞书", "钉钉", "企业微信")
         for d in ("pricing", "deployment", "integrations")], start=1)
]


def _profile(name: str) -> CompetitorProfile:
    ref = [EvidenceRef(evidence_id="e1", quote="公开资料")]
    return CompetitorProfile(
        name=name,
        pricing=PricingModel(model_type="tiered",
                             tiers=[PricingTier(name="企业版", price="询价", billing_cycle="annual")],
                             evidence_refs=ref),
        swot=SWOT(strengths=[SWOTPoint(text="生态完整", evidence_refs=ref)]),
    )


_ANALYSIS = CompetitorAnalysis(
    competitors=[_profile(c) for c in ("飞书", "钉钉", "企业微信")],
    comparison=[
        ComparisonRow(dimension=d, cells=[
            ComparisonCell(competitor=c, value_type="enum", value="tiered",
                           evidence_refs=[EvidenceRef(evidence_id="e1", quote="公开资料")])
            for c in ("飞书", "钉钉", "企业微信")])
        for d in ("pricing", "deployment", "integrations")],
)


def main() -> None:
    client = config.get_doubao_client()
    model = config.doubao_model()
    body = render_body(_ANALYSIS, _EV, as_of="2026-06-01")
    print(f"=== body size: {len(body)} chars ===")

    # Step 1:流式草稿(测 typing 可行性)。emit 计数 + 计时。
    chunks = {"n": 0}
    t0 = time.monotonic()
    t_first = {"v": None}

    def emit(ev_type: str, data: dict) -> None:
        if ev_type == "chunk" and data.get("delta"):
            chunks["n"] += 1
            if t_first["v"] is None:
                t_first["v"] = time.monotonic() - t0

    draft_msgs = [{"role": "user", "content":
        "你是竞品战略分析师。基于下面的对比正文,写一段三部分的自由文本草稿:"
        "①市场格局 ②战略路径分歧 ③短/中/长期可执行建议。只写散文,不要 JSON。\n\n" + body}]
    draft = stream_chat(draft_msgs, client=client, model=model, emit=emit,
                        agent_id="writer", step="drafting")
    t_stream = time.monotonic() - t0
    print(f"=== stream: {chunks['n']} chunks | TTFB {t_first['v']}s | total {t_stream:.1f}s "
          f"| draft {len(draft)} chars ===")
    assert chunks["n"] > 5, "stream 没有真流 delta(chunks 太少)→ 两步化不可行,Plan B 回落一次性"

    # Step 2:把草稿抽成结构化 ReportInsight(契约不破)。
    t1 = time.monotonic()
    insight = generate_insight(draft, client=client, model=model)
    print(f"=== extract: {time.monotonic() - t1:.1f}s ===")
    assert insight.market_context and insight.differentiation_thesis and insight.actionable_takeaway, \
        "两步抽取产物字段缺失 → 两步化不忠实"
    print("=== ReportInsight (head) ===")
    print(f"market_context: {insight.market_context[:120]}")
    print(f"differentiation_thesis: {insight.differentiation_thesis[:120]}")
    print(f"actionable_takeaway: {insight.actionable_takeaway[:120]}")
    print("SPIKE OK: stream_chat 真流 + 两步抽取产出合法 ReportInsight")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑 spike,记录结论**

Run:
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
NO_PROXY=localhost,127.0.0.1 .venv/bin/python spikes/spike_insight_two_step.py
```
Expected: 打印 `chunks > 5` + `TTFB` + `ReportInsight` 三字段非空 + `SPIKE OK`。
- 若 `chunks` 太少 / stream 抛错 → 在 Plan B 把 insight 两步化标「回落一次性 + 前端揭示」(数据真、无 typing)。
- 记录 TTFB / total 进 `spikes/SPIKE_RESULTS.md`(若存在)或本 plan 此处勾注,供 Plan B 决策。

- [ ] **Step 3: 不提交 spike 产物**(spike 不进 pytest,不影响 CI;按需保留脚本)。

---

## Epic 1: queries 表 + repository CRUD

### Task 1: 加 `queries` 表 schema

**Files:**
- Modify: `rivalradar/storage/db.py`(`SCHEMA` 串)
- Test: `tests/test_queries_repo.py`

- [ ] **Step 1: 写失败测试(表存在 + 可建)**

`tests/test_queries_repo.py`:

```python
import sqlite3

from rivalradar.storage.db import connect, init_db


def _conn() -> sqlite3.Connection:
    c = connect(":memory:")
    init_db(c)
    return c


def test_queries_table_exists():
    conn = _conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(queries)").fetchall()}
    assert {"run_id", "competitor", "dimension", "language",
            "query_text", "round", "hit_count", "created_at"} <= cols
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_queries_repo.py::test_queries_table_exists -v`
Expected: FAIL(PRAGMA 返回空,cols 为空集)。

- [ ] **Step 3: 在 `SCHEMA` 串加表(`db.py`,decisions 表定义之后)**

在 `rivalradar/storage/db.py` 的 `SCHEMA` 三引号串里,`CREATE TABLE IF NOT EXISTS trace (...)` 之前插入:

```sql
-- 真实查询词(Plan A:研究员检索台「看得见的活儿」)。CREATE IF NOT EXISTS 自动
-- 在 init_db 建(老 db 也建,老 run 无行 → 天然空态);round=retry 轮次(0=首轮)。
CREATE TABLE IF NOT EXISTS queries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    competitor  TEXT NOT NULL,
    dimension   TEXT NOT NULL,
    language    TEXT NOT NULL,
    query_text  TEXT NOT NULL,
    round       INTEGER NOT NULL DEFAULT 0,
    hit_count   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
```

并在 `SCHEMA` 末尾的索引区(`idx_trace_run` 旁)加:

```sql
CREATE INDEX IF NOT EXISTS idx_queries_run ON queries(run_id);
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_queries_repo.py::test_queries_table_exists -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/storage/db.py tests/test_queries_repo.py
git commit -m "feat(db): add queries table for real query-word persistence (Plan A)"
```

### Task 2: `insert_queries` / `list_queries` CRUD

**Files:**
- Modify: `rivalradar/storage/repository.py`
- Test: `tests/test_queries_repo.py`

- [ ] **Step 1: 写失败测试(批量写 + 读回)**

追加到 `tests/test_queries_repo.py`:

```python
from rivalradar.storage.repository import insert_queries, list_queries


def test_insert_and_list_queries():
    conn = _conn()
    records = [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 价格 套餐 收费", "round": 0, "hit_count": 3},
        {"competitor": "飞书", "dimension": "pricing", "language": "en",
         "query_text": "飞书 pricing plans cost", "round": 0, "hit_count": 0},
    ]
    insert_queries(conn, "run1", records)
    rows = list_queries(conn, "run1")
    assert len(rows) == 2
    assert rows[0]["query_text"] == "飞书 价格 套餐 收费"
    assert rows[0]["hit_count"] == 3
    assert rows[1]["hit_count"] == 0
    assert list_queries(conn, "missing") == []
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_queries_repo.py::test_insert_and_list_queries -v`
Expected: FAIL(`ImportError: cannot import name 'insert_queries'`)。

- [ ] **Step 3: 实现 CRUD(`repository.py`,trace 区块之后)**

在 `rivalradar/storage/repository.py` 的 `list_trace` 之后加:

```python
# ---- queries(Plan A:真实查询词检索台)----
def insert_queries(conn: sqlite3.Connection, run_id: str,
                   records: list[dict]) -> None:
    """批量插入真实查询词记录。records 每项:
    {competitor, dimension, language, query_text, round, hit_count}。
    在 collect_node 主线程一次性写(worker 线程只 emit + 收集,不并发写 sqlite)。"""
    if not records:
        return
    now = _now()
    conn.executemany(
        "INSERT INTO queries (run_id, competitor, dimension, language, "
        "query_text, round, hit_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(run_id, r["competitor"], r["dimension"], r["language"],
          r["query_text"], int(r.get("round", 0)), int(r.get("hit_count", 0)), now)
         for r in records],
    )
    conn.commit()


def list_queries(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT competitor, dimension, language, query_text, round, hit_count, created_at "
        "FROM queries WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_queries_repo.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/storage/repository.py tests/test_queries_repo.py
git commit -m "feat(repo): insert_queries/list_queries CRUD (Plan A)"
```

---

## Epic 2: pipeline `on_query` 回调

### Task 3: `collect()` + `collect_evidence()` 加 `on_query`

**Files:**
- Modify: `rivalradar/collect/pipeline.py`
- Modify: `rivalradar/agents/collector.py`
- Test: `tests/test_collect_pipeline.py`

- [ ] **Step 1: 写失败测试(每 query 完成回调一次,带 Query + evidence)**

追加到 `tests/test_collect_pipeline.py`:

```python
def test_collect_on_query_callback():
    """on_query 每 query 完成报一次,带 Query 对象 + 该 query 产出的 evidence。
    worker 线程并发调,用锁汇聚。"""
    provider = _MockProvider()
    seen = []
    lock = threading.Lock()

    def on_q(q, evs):
        with lock:
            seen.append((q.competitor, q.dimension, q.language, q.query_text, len(evs)))

    collect(["Notion"], ["pricing", "integrations"], provider=provider,
            languages=("en",), max_workers=4, on_query=on_q)
    assert len(seen) == 2  # 1 竞品 × 2 维 × 1 语
    dims = {s[1] for s in seen}
    assert dims == {"pricing", "integrations"}
    assert all(s[4] == 1 for s in seen)        # _MockProvider 每 query 回 1 条
    assert all(s[3] for s in seen)             # query_text 非空
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_collect_pipeline.py::test_collect_on_query_callback -v`
Expected: FAIL(`collect() got an unexpected keyword argument 'on_query'`)。

- [ ] **Step 3: 给 `collect()` 加 `on_query`(`pipeline.py`)**

修改 `rivalradar/collect/pipeline.py` 的 `collect` 签名与 `_one`:

签名加一行参数(放 `on_progress` 之后):

```python
    on_progress: Callable[[str], None] | None = None,
    on_query: Callable[["Query", list[Evidence]], None] | None = None,
```

`_one` 改为(在 `on_progress` 之后调 `on_query`):

```python
    def _one(q: Query) -> list[Evidence]:
        evs = _run_query_safe(provider, q, max_results)
        if on_progress is not None:
            on_progress(f"采集 {q.competitor}·{q.dimension}")
        if on_query is not None:
            on_query(q, evs)
        return evs
```

(docstring 可补一句:`on_query:每 query 完成报 (Query, 该 query 产出的原始 evidence);None=不报。`)

- [ ] **Step 4: 给 `collect_evidence()` 透传 `on_query`(`collector.py`)**

修改 `rivalradar/agents/collector.py` 的 `collect_evidence` 签名(加参数,放 `on_progress` 之后):

```python
    on_progress: Callable[[str], None] | None = None,
    on_query: Callable | None = None,
```

并把 `collect(...)` 调用补上 `on_query=on_query`:

```python
    raw = collect(competitors, dimensions, provider=provider, languages=languages,
                  max_results=max_results, max_workers=max_workers, broaden=broaden,
                  on_progress=on_progress, on_query=on_query)
```

- [ ] **Step 5: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_collect_pipeline.py -v`
Expected: 全 passed(含新 test + 既有 4 个不破)。

- [ ] **Step 6: Commit**

```bash
git add rivalradar/collect/pipeline.py rivalradar/agents/collector.py tests/test_collect_pipeline.py
git commit -m "feat(collect): on_query callback threads Query+evidence per query (Plan A)"
```

---

## Epic 3: collect_node 发 4 类事件 + round 推导 + 持久化

### Task 4: round 推导 helper

**Files:**
- Modify: `rivalradar/graph/nodes.py`
- Test: `tests/test_collect_node_emit.py`

- [ ] **Step 1: 写失败测试(round 推导)**

`tests/test_collect_node_emit.py`:

```python
from rivalradar.graph.nodes import _collect_round


def test_collect_round_first_pass_is_zero():
    # 首轮:无 qc_result → round 0
    assert _collect_round({"qc_result": None, "retry_count": 0}) == 0
    assert _collect_round({"retry_count": 0}) == 0


def test_collect_round_retry_derives_from_qc_presence():
    # 第一次 retry collect:qc_result 已存在但 retry_count 仍 0(qc 节点首轮不 +1)→ round 1
    assert _collect_round({"qc_result": {"verdict": "retry_collect"}, "retry_count": 0}) == 1
    # 第二次 retry:retry_count=1 → round 2
    assert _collect_round({"qc_result": {"verdict": "retry_collect"}, "retry_count": 1}) == 2
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_collect_node_emit.py::test_collect_round_first_pass_is_zero -v`
Expected: FAIL(`ImportError: cannot import name '_collect_round'`)。

- [ ] **Step 3: 实现 `_collect_round`(`nodes.py`,`make_collect_node` 之前)**

在 `rivalradar/graph/nodes.py` 的 `_make_ticker` 之后加:

```python
def _collect_round(state: dict) -> int:
    """采集轮次(spec §5.1 codex [P1] 防造假):首轮 qc_result 为 None → 0;retry 轮由
    qc_result 存在性推导(第一次 retry 时 retry_count 仍为 0,qc 节点首轮不 +1),故
    round = retry_count + 1。不能直接用 retry_count(会把第一次 retry 误标 round 0)。"""
    if state.get("qc_result") is None:
        return 0
    return int(state.get("retry_count", 0)) + 1
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_collect_node_emit.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/graph/nodes.py tests/test_collect_node_emit.py
git commit -m "feat(nodes): _collect_round derives retry round from qc presence (Plan A)"
```

### Task 5: collect_node 发 query/query_hit/source/evidence_delta + 持久化 queries

**Files:**
- Modify: `rivalradar/graph/nodes.py`(`make_collect_node`)
- Test: `tests/test_collect_node_emit.py`

- [ ] **Step 1: 写失败测试(首轮采集发 4 类事件 + 落库)**

追加到 `tests/test_collect_node_emit.py`:

```python
import threading

from rivalradar.graph.nodes import make_collect_node
from rivalradar.search.base import SearchResult
from rivalradar.storage.db import connect, init_db
from rivalradar.storage.repository import create_run, list_queries


class _OneHitProvider:
    name = "mock"
    def search(self, query, *, max_results=5):
        return [SearchResult(url=f"https://x/{query}", title=f"T:{query}",
                             content="c", raw_content="body", provider="mock")]


def _capture_emit():
    events, lock = [], threading.Lock()
    def emit(ev_type, data):
        with lock:
            events.append((ev_type, data))
    return events, emit


def test_collect_node_emits_real_work_events():
    conn = connect(":memory:"); init_db(conn)
    create_run(conn, "run1", ["飞书"], ["pricing"])
    node = make_collect_node(conn=conn, provider=_OneHitProvider(), official_domains={})
    events, emit = _capture_emit()
    state = {"evidence": [], "competitors": ["飞书"], "dimensions": ["pricing"],
             "qc_result": None, "retry_count": 0}
    config = {"configurable": {"thread_id": "run1", "emit": emit}}

    out = node(state, config)

    kinds = [e[0] for e in events]
    assert "query" in kinds and "query_hit" in kinds and "source" in kinds and "evidence_delta" in kinds
    # 1 竞品 × 1 维 × 2 语 = 2 query
    assert kinds.count("query") == 2
    assert kinds.count("query_hit") == 2
    # query 事件带真实查询词 + round 0
    q_ev = [d for t, d in events if t == "query"]
    assert all(d["query_text"] and d["round"] == 0 for d in q_ev)
    assert {d["query_text"] for d in q_ev} == {"飞书 价格 套餐 收费", "飞书 pricing plans cost"}
    # source 事件带真实标题/url + 落库的 evidence_id
    src = [d for t, d in events if t == "source"]
    assert all(d["source_title"].startswith("T:") and d["evidence_id"].startswith("ev_") for d in src)
    # evidence_delta round 汇总
    delta = [d for t, d in events if t == "evidence_delta"][0]
    assert delta["round"] == 0 and delta["added_count"] == len(out["evidence"])
    # queries 落库
    rows = list_queries(conn, "run1")
    assert len(rows) == 2 and all(r["round"] == 0 for r in rows)
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_collect_node_emit.py::test_collect_node_emits_real_work_events -v`
Expected: FAIL(无 query/source 等事件;`kinds` 不含它们)。

- [ ] **Step 3: 改 `make_collect_node`(`nodes.py`)**

在 `rivalradar/graph/nodes.py` 顶部 import 区补 `insert_queries`:

```python
from rivalradar.storage.repository import (
    append_trace, insert_evidence, insert_queries, mark_run_finalized, save_analysis,
    save_decisions, save_insight, save_qc_result, save_report, update_run_degraded,
)
```

把 `collect_node` 改为(整体替换 `make_collect_node` 内的 `collect_node`):

```python
    def collect_node(state, config):
        run_id = config["configurable"]["thread_id"]
        emit = _get_emit(config)
        t0 = time.monotonic()
        existing = {e["id"] for e in state.get("evidence", [])}
        qc_result = state.get("qc_result")
        rnd = _collect_round(state)

        # 真实查询词检索台:每 query 完成发 query + query_hit 事件(worker 线程,emit 经
        # sse.py call_soon_threadsafe 线程安全),并收集 query 记录供主线程批量落库。
        q_records: list[dict] = []
        q_lock = threading.Lock()

        def on_query(q, evs):
            if emit is not None:
                emit("query", {"competitor": q.competitor, "dimension": q.dimension,
                               "query_text": q.query_text, "language": q.language, "round": rnd})
                emit("query_hit", {"query_text": q.query_text,
                                   "hit_count": len(evs), "round": rnd})
            with q_lock:
                q_records.append({"competitor": q.competitor, "dimension": q.dimension,
                                  "language": q.language, "query_text": q.query_text,
                                  "round": rnd, "hit_count": len(evs)})

        if qc_result is None:
            _emit_progress(
                emit, "collector", "search",
                f"开始搜索 {len(state['competitors'])} 个竞品 × {len(state['dimensions'])} 个维度",
            )
            tick = _make_ticker(emit, "collector", "search",
                                len(state["competitors"]) * len(state["dimensions"]) * 2)
            evs = collect_evidence(state["competitors"], state["dimensions"],
                                   provider=provider, official_domains=official_domains,
                                   max_results=max_results, on_progress=tick, on_query=on_query)
            tgt_desc = "all"
        else:
            targets = extract_collect_targets(
                qc_result["issues"], state["competitors"],
                allowed_dimensions=tuple(state.get("dimensions") or CONTROLLED_DIMENSIONS))
            _emit_progress(
                emit, "collector", "broaden",
                f"按质检反馈广搜 {len(targets)} 个证据缺口",
                metric={"current": 0, "total": len(targets)},
            )
            tick = _make_ticker(emit, "collector", "broaden", max(len(targets), 1) * 2)
            evs = []
            for comp, dim in targets:
                evs += collect_evidence([comp], [dim], provider=provider,
                                        official_domains=official_domains,
                                        max_results=max_results, broaden=True,
                                        on_progress=tick, on_query=on_query)
            tgt_desc = f"{len(targets)} gaps"

        fresh = [e for e in evs if e.id not in existing]
        for e in fresh:
            insert_evidence(conn, run_id, e)
            # 来源卡明细(spec §5.2):只发实际落库的新证据,不发 content 全文(点开走 REST)。
            if emit is not None:
                emit("source", {"evidence_id": e.id, "competitor": e.competitor,
                                "dimension": e.dimension, "source_title": e.source_title,
                                "source_url": e.source_url, "language": e.language, "round": rnd})
        # 真实查询词落库(主线程批量,worker 线程只收集,避免并发写 sqlite)。
        insert_queries(conn, run_id, q_records)
        # retry 增量(spec §5.4):本轮新增汇总,前端重试环显「第 N 轮 · 证据 X→Y」。
        total_after = len(existing) + len(fresh)
        if emit is not None:
            emit("evidence_delta", {"round": rnd, "added_count": len(fresh),
                                    "total_count": total_after,
                                    "new_evidence_ids": [e.id for e in fresh]})
        _emit_progress(
            emit, "collector", "done",
            f"找到 {len(fresh)} 条新证据,累计 {total_after} 条",
            metric={"current": len(fresh), "total": total_after},
        )
        append_trace(conn, run_id, "collect",
                     input_summary=f"targets={tgt_desc} round={rnd}",
                     output_summary=f"+{len(fresh)} (total {total_after})",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"evidence": [e.model_dump() for e in fresh]}
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_collect_node_emit.py -v`
Expected: 全 passed。

- [ ] **Step 5: 回归既有图测试**

Run: `.venv/bin/python -m pytest tests/test_graph_build.py tests/test_collect_pipeline.py -v`
Expected: 全 passed(emit=None 时 on_query 仍被调用但 emit 分支跳过,落库照常;既有调用不破)。

- [ ] **Step 6: Commit**

```bash
git add rivalradar/graph/nodes.py tests/test_collect_node_emit.py
git commit -m "feat(nodes): collect_node emits query/query_hit/source/evidence_delta + persists queries (Plan A)"
```

---

## Epic 4: SSE 事件 schema + REST

### Task 6: SSE 事件 Pydantic schema

**Files:**
- Modify: `rivalradar/api/schemas.py`
- Test: `tests/test_api_app.py`(或新建 `tests/test_sse_schemas.py`)

- [ ] **Step 1: 写失败测试(schema 校验事件 payload)**

`tests/test_sse_schemas.py`:

```python
from rivalradar.api.schemas import (
    SSEQueryData, SSEQueryHitData, SSESourceData, SSEEvidenceDeltaData,
)


def test_sse_query_schema():
    d = SSEQueryData(competitor="飞书", dimension="pricing",
                     query_text="飞书 价格", language="zh", round=0, ts="t")
    assert d.query_text == "飞书 价格" and d.round == 0


def test_sse_source_and_delta_schema():
    s = SSESourceData(evidence_id="ev_1", competitor="飞书", dimension="pricing",
                      source_title="T", source_url="https://x", language="zh", round=0, ts="t")
    assert s.evidence_id == "ev_1"
    e = SSEEvidenceDeltaData(round=1, added_count=3, total_count=12,
                             new_evidence_ids=["ev_1"], ts="t")
    assert e.added_count == 3 and e.new_evidence_ids == ["ev_1"]
    SSEQueryHitData(query_text="飞书 价格", hit_count=3, round=0, ts="t")
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_sse_schemas.py -v`
Expected: FAIL(`ImportError`)。

- [ ] **Step 3: 加 schema(`api/schemas.py`,`SSEChunkData` 之后)**

在 `rivalradar/api/schemas.py` 末尾(`SSEChunkData` 之后)加:

```python
class SSEQueryData(BaseModel):
    """query event — 采集员发起的真实查询词(spec §5.1,检索台逐字)。"""
    competitor: str
    dimension: str
    query_text: str
    language: str
    round: int = 0
    ts: str


class SSEQueryHitData(BaseModel):
    """query_hit event — 某查询词命中的证据条数(spec §5.1)。"""
    query_text: str
    hit_count: int
    round: int = 0
    ts: str


class SSESourceData(BaseModel):
    """source event — 新落库证据的来源卡明细(spec §5.2,不含正文,点开走 REST)。
    无 provider / confidence(反幻觉,spec §1.5)。"""
    evidence_id: str
    competitor: str
    dimension: str
    source_title: str
    source_url: str
    language: str
    round: int = 0
    ts: str


class SSEEvidenceDeltaData(BaseModel):
    """evidence_delta event — retry 轮证据增量汇总(spec §5.4,重试环 X→Y)。"""
    round: int
    added_count: int
    total_count: int
    new_evidence_ids: list[str] = Field(default_factory=list)
    ts: str
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_sse_schemas.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/schemas.py tests/test_sse_schemas.py
git commit -m "feat(api): SSE schemas for query/query_hit/source/evidence_delta (Plan A)"
```

### Task 7: `GET /runs/{run_id}/queries` REST

**Files:**
- Modify: `rivalradar/api/reads.py`
- Test: `tests/test_api_reads.py`

- [ ] **Step 1: 写失败测试(端点返回 queries / run 不存在 404)**

追加到 `tests/test_api_reads.py`(沿用该文件已有的 app/client fixture;若无则参照下方自建):

```python
def test_get_run_queries(client, conn):
    from rivalradar.storage.repository import create_run, insert_queries
    create_run(conn, "runq", ["飞书"], ["pricing"])
    insert_queries(conn, "runq", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 价格", "round": 0, "hit_count": 3}])
    r = client.get("/runs/runq/queries")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and body[0]["query_text"] == "飞书 价格" and body[0]["hit_count"] == 3


def test_get_run_queries_404_when_run_missing(client):
    r = client.get("/runs/nope/queries")
    assert r.status_code == 404
```

> 若 `tests/test_api_reads.py` 还没有 `client`/`conn` fixture,复用本文件已有 app 工厂 fixture 模式(与 `test_api_reads.py` 既有用例同款);本步只新增两个用例,不改 fixture。

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_api_reads.py::test_get_run_queries -v`
Expected: FAIL(404 路由不存在 → 实际 404,但 `test_get_run_queries` 期望 200 → assert 失败)。

- [ ] **Step 3: 加端点(`reads.py`,`list_run_evidence` 之后)**

在 `rivalradar/api/reads.py` 末尾加:

```python
@router.get("/runs/{run_id}/queries")
def list_run_queries(run_id: str,
                     conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    """真实查询词列表(Plan A:replay/事后查看检索台)。run 不存在 → 404;无查询 → 空列表。"""
    if repo.get_run(conn, run_id) is None:
        raise HTTPException(404, "run not found")
    return repo.list_queries(conn, run_id)
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_api_reads.py -v`
Expected: 全 passed(含 2 个新用例)。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/reads.py tests/test_api_reads.py
git commit -m "feat(api): GET /runs/:id/queries endpoint (Plan A)"
```

---

## Epic 5: 全量回归 + 真 run 验证

### Task 8: 回归 + 真 run 抽查

- [ ] **Step 1: 全量单测**

Run: `.venv/bin/python -m pytest`
Expected: 全绿(~350 + 新增,约 10s)。任一红 → 修到绿再继续(记忆:单测全绿 ≠ 真 run 对,但红必先修)。

- [ ] **Step 2: 真 run 抽查(emit 真实活儿)**

真打一个小 run(1 竞品 × 1 维),确认 SSE 流里出现 `query`/`query_hit`/`source`/`evidence_delta` 事件且查询词是真实模板词、来源卡有真实标题/url。
Run(WSL2 Clash:Doubao/Tavily 国内,unset 代理):
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
NO_PROXY=localhost,127.0.0.1 .venv/bin/python -m rivalradar.api  # 或既有启动入口
# 另开 shell:POST /run {competitors:["飞书"], dimensions:["pricing"]},curl -N SSE 看事件
```
Expected: 看到真实查询词(如「飞书 价格 套餐 收费」)+ 命中数 + 来源卡 + `GET /runs/<id>/queries` 返回真实查询词。

- [ ] **Step 3: Commit(若有真 run 触发的修)**

```bash
git add -A
git commit -m "test(plan-a): real-run verified query/source/delta emit"
```

---

## Self-Review

**1. Spec 覆盖(Plan A 范围 = §5.1/§5.2/§5.4/§5.6 spike/§7.1 部分/§7.3 部分):**
- §5.1 真实查询词 emit + 持久化 → Task 1/2(表+CRUD)、Task 3(pipeline 回调)、Task 5(节点 emit+落库)、Task 7(REST)✓
- §5.2 来源卡明细 emit → Task 5(source 事件,post-dedup 只发落库的)✓
- §5.4 retry 增量 emit → Task 4(round 推导)、Task 5(evidence_delta)✓
- §5.6 spike → Task 0 ✓(实现留 Plan B)
- §7.1 SSE schema → Task 6 ✓(`chunk` 复活留 Plan B insight 两步)
- round 防造假(codex [P1])→ Task 4 `_collect_round` + 测试 ✓
- emit 回调签名改动(codex [P2])→ Task 3 ✓
- 不发 provider/confidence(反幻觉 §1.5)→ Task 6 `SSESourceData` 无此字段 ✓

**2. 占位扫描:** 无 TBD/TODO;每步含真实代码/命令/期望。Task 7 Step 1 对 fixture 的「若无则参照」是对既有测试文件约定的引用,不是占位(端点代码本身完整)。

**3. 类型一致性:** `on_query(q, evs)` 签名贯穿 pipeline→collector→node 一致;`q_records` 字段(competitor/dimension/language/query_text/round/hit_count)与 `insert_queries` 读取键、`queries` 表列、`list_queries` SELECT 列全一致;`_collect_round` 在 Task 4 定义、Task 5 使用;SSE 事件名(query/query_hit/source/evidence_delta)在节点 emit 与 schema 类名一致。

**4. 边界:** 本 Plan 不动前端(Plan C 消费这些事件);不动 analyze/qc/writer(逐格 cell_row + support_verdict 真算 + insight 两步实现在 Plan B);demo/replay 平价在 Plan D(replay 需把这些事件并入 trace 或新结构,Plan D 处理)。
