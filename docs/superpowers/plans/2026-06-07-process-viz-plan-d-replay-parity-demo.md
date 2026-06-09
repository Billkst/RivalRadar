# Plan D — 调研进行时过程可视化 · replay/刷新平价 + demo 端到端 + DESIGN.md v5 校验 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让刷新/深链进入一个已结束的 run 时不丢「看得见的真实活儿」—— 后端 `GET /stream/{id}` replay 从持久化状态重建全部富过程事件(`query`/`query_hit`/`source`/`cell_row`/`verdict_recheck`),前端研究员工作台 + 矩阵三色 + StatusBar「充分/部分/已剔除」完整还原;并端到端验证 demo URL 25s 无 dead-loop、校验 DESIGN.md v5 已写,收口整条「调研进行时」链。

**Architecture:** 本项目从不持久化 SSE 事件流本身,而是持久化**最终状态**(`queries`/`evidence`/`analysis`(cell 带真 `support_verdict`)/`curation_drops` 各表),replay 时从状态**重建**事件(承现有 `_replay_from_trace` 的「从 trace 重建」模式)。Plan D 把 `_replay_from_trace`(`sse.py:305`)从「只发 start+trace+done」升级为「start → query/query_hit → source → cell_row → verdict_recheck → trace → done」。前端 reducer(`runStore.handleEvent`,Plan C 已接全部事件、order-independent)与 `useSSE.parseSSE`(已认全部事件串)**无需改动**,只做端到端验证。诚实降级(D-D2):`evidence_delta`(evidence 表无 round 列,精确轮次不可还原)+ `chunk`(瞬态打字)replay **不重建** —— 重试环/报告台打字在 replay 静态,但矩阵/检索台/来源卡/三色这些「数据真」的核心活儿完整还原。

**Tech Stack:** 后端 FastAPI + SQLite(WAL)+ sse-starlette。后端验证 = `.venv/bin/python -m pytest`(~387 测试 ~10s)。前端无测试框架,验证 = `cd frontend && pnpm build`(`tsc -b && vite build`,记忆 [[verify-with-real-project-script]],**不是** `tsc --noEmit`;增量缓存假绿用 `tsc -b --force`)+ `/browse`(gstack,强制;**禁止** `mcp__claude-in-chrome__*`)。WSL2 Clash:pytest/pnpm build 本地不需代理;Doubao/Tavily/git push 要 `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy` + `NO_PROXY=localhost,127.0.0.1`。

---

## 0. 上下文:已完成 vs 本计划范围

**已 SHIP_READY(Plan A + B + C,勿重做)**:
- 后端真实化(Plan A+B):全部新 SSE 事件 **live 已 emit**;`ComparisonCell.support_verdict` + `Decision.support_verdict` 真算三级回写;持久化齐全:`queries` 表(`list_queries`,带 round/hit_count)、`curation_drops` 表(`list_curation_drops`,scope=cell/decision + competitor/dimension/detail)、`analysis`(cell 带真 verdict)、`evidence`(`list_evidence`)、`decisions`(decision 带真 verdict);REST `GET /runs/{id}/queries`、`GET /runs/{id}/curation-drops` 已存在(`reads.py:92-107`)。
- 前端消费(Plan C):`types/api.ts` 全部新事件类型 + `useSSE.parseSSE`(`useSSE.ts:48-86`,认全部新事件串)+ `runStore.handleEvent`(if-chain,新事件早 return,order-independent)+ 研究员工作台 + 矩阵三色 + StatusBar 三色 + navStack 抽屉,全部 ship-ready 并 /browse 验过。
- `fakeSSEPlayer`(`frontend/src/dev/fakeSSEPlayer.ts`):**已是完整 25s 同形状版本**(start → 4-agent cycle + retry 轮 + verdict_recheck supported×4/partial×2/dropped×1 + decide + done),非 checkpoint 旧描述的「最小版」。

**本计划范围(整链收尾,4 Epic)**:
- Epic 1:后端富 replay 重建(核心)—— 升级 `_replay_from_trace`,从持久化状态重建 query/query_hit/source/cell_row/verdict_recheck,+ pytest 成功/失败两路。
- Epic 2:replay 端到端验证 —— seed 一个完整 run 到 SQLite(无 LLM),起后端,`/browse` 深链 `/run/{id}` 触发真 replay,验证工作台 + 三色 + 矩阵完整还原(contract mismatch 只有真打 replay 才暴露,build 抓不到)。
- Epic 3:demo URL 端到端 spike —— `/browse` 跑 demo `/run/run_demo01` 完整 25s,验证新事件全产出 + 无 dead-loop(记忆 [[demo bullet-proof]]:ship demo path 必须真 URL 端到端验证)。
- Epic 4:DESIGN.md v5 已写校验 —— 核对 spec §8 的 5 项增量都在 DESIGN.md;缺则补(条件写)。

**replay 的真正增量价值(codex finding #4 厘清)**:矩阵最终态**已有 REST 兜底**(`CompetitorComparison` 回落 `GET /analysis` 的 `analysisCell.support_verdict`,`CompetitorComparison.tsx:298`)—— replay 重建 `cell_row` 只是让逐维过程 + 剔除态更早/更一致,**不是**矩阵能显的前提。replay **真正不可替代**的是这些无 REST 消费路径的工作台件:① 检索台查询词(`SearchStation` 只读 SSE store)② 来源卡(`SourceCards` 只读 SSE store)③ StatusBar「充分 X·部分 Y」(`verdictSummary` 只来自 `verdict_recheck`,只有「已剔除」走 `/curation-drops` 兜底)④ PlanRail 逐维 done + 步骤抽屉。

**不在本计划(承认的诚实降级 + 留对话外)**:
- replay 不重建 `evidence_delta`(D-D2)→ **重试环动画(RetryLoop)replay 不显**(它只读 `evidenceDeltas` 且只渲染 round>0;`RetryLoop.tsx:17`)。但「自我纠错 N 次 / N 轮」计数 **会**正确(D-D3 从 `max(queries.round)` 真值重建 retryCount)。trace 时间轴仍显 collect 多次。
- replay 不重建 `chunk`(D-D2)→ 报告台 replay 无打字(insight/report 经 REST 显终态)。
- replay 不重建完整 `node`/`progress` 序列(D-D3)→ agent roster 动画 / DAG 逐节点进度 replay 静态;**仅合成一个终态 qc `node` 事件**注入真 retryCount + verdict(修 codex finding #2)。live 流不受影响。
- 真 run support_verdict 三级门槛最终校准(需真打 Doubao,留对话外,记忆:真 run 校准是唯一路径)。

---

## 1. 范围决策(写死,实现据此,勿临场二选一)

| # | 决策点 | 锁定选择 | 理由 |
|---|--------|---------|------|
| D-D1 | replay 重建机制 | **从持久化状态重建**(承 `_replay_from_trace` 模式),**不**引入 SSE 事件日志表 | 所有数据已持久化(queries/evidence/analysis/curation_drops);新增事件日志表是 over-engineering(YAGNI,CLAUDE.md §2)。 |
| D-D2 | `evidence_delta` + `chunk` replay 处理 | **不重建**(诚实降级) | evidence 表无 round 列(`db.py:14-27`),精确轮次增量不可还原;造一个假 round 违反反幻觉文化(记忆 [[qc-curator-not-judge]] 宁缺勿造假)。`chunk` 瞬态、报告/insight 经 REST 已显终态。后果:RetryLoop 动画 replay 不显(只读 evidenceDeltas round>0,`RetryLoop.tsx:17`)。 |
| D-D3 | `node`/`progress` replay 处理 | **不重建完整序列**,但**合成 1 个终态 qc `node` 事件**(真 retry_count + verdict)+ 保留 `trace` | codex finding #2:retryCount 只从 live `node` qc summary 更新,trace 被置 `summary=null`(`runStore.ts:363`)→ 不补则「自我纠错 N 次」replay 恒显 0(错数,违反反幻觉)。修法:replay 末尾合成一个 qc `node` 事件,`retry_count = max(q["round"] for q in queries)`(queries.round 是持久化真值)+ `verdict` from `get_qc_result`;**仅当 qc_result 存在才发**(空/早失败 run 不发,保既有空-run 测试)。agent 逐节点动画仍 live-only。 |
| D-D2b | `verdict_recheck.downgraded` replay 取值 | **= partial cell 子集**(对齐 live) | codex finding #3:live `downgraded` 是 partial cell 子集(`nodes.py:349,355` + `schemas.py:213`),不是 `[]`;replay 发 `[]` 是契约漂移(前端暂未消费但防将来)。replay 用 `[cv for cv in cell_verdicts if cv["support_verdict"]=="partial"]`。 |
| D-D4 | `source.round` replay 取值 | **默认 0**(evidence 无 round 列);`query`/`query_hit` round 用 `queries` 表真值 | queries 有 round 真值;source round 退化可接受(来源卡仍渲染;按轮分组失真,无 consumer 强依赖 source.round)。 |
| D-D5 | `verdict_recheck` replay 形状 | 只发 `cell_verdicts`(从 curated analysis)+ `dropped`(curation_drops scope=cell)+ `summary`,**无 `decision_verdicts`**(同 live C-D6 契约) | 决策三色经 `GET /decisions`(decision.support_verdict)兜底,不依赖事件(与 Plan C C-D6 一致);`summary.supported/partial` 从 analysis cell 计数,`dropped` 从 curation_drops 计数。 |
| D-D6 | 函数命名 | **保留 `_replay_from_trace` 名**(就地 enrich),不重命名 | `runs.py:16,85` 与 `test_api_sse.py:5` 都 import 此名;重命名是无收益 churn(CLAUDE.md §3 surgical)。 |
| D-D7 | `fakeSSEPlayer` | **不重写**(已完整 25s),仅 Epic 3 端到端验证;若 /browse 抓到问题才微调 | Plan C `a522a57` 已是 demo 级;重写违反 YAGNI。 |
| D-D8 | DESIGN.md v5 | **校验为主**,缺项才补(条件写) | checkpoint 记「DESIGN.md v5 已写」;Plan D 核对 spec §8 五项是否真在文档,防「以为写了其实没写」。 |

---

## 2. 文件结构(决策锁定处)

### 修改(后端)
- `rivalradar/api/sse.py` — 就地 enrich `_replay_from_trace`(`sse.py:305-340`):start 之后、trace loop 之前,插入「从持久化状态重建 query/query_hit/source/cell_row/verdict_recheck」段。**唯一实现改动文件。**

### 新建(后端测试)
- `tests/test_replay_parity.py` — replay 富事件重建测试(成功 + 边界两路;seed via `repo.*` 直接造数据,`tmp_path` 隔离 SQLite,承 `test_api_sse.py` 的 `_collect` drain 风格)。

### 验证(不改源,除非验证抓到问题)
- `frontend/src/dev/fakeSSEPlayer.ts` — Epic 3 端到端验证对象。
- `DESIGN.md` — Epic 4 校验对象(缺 spec §8 增量才补)。

### 不动
- `rivalradar/api/runs.py`(`get_stream` 仍调 `_replay_from_trace`,名不变 D-D6)。
- `frontend/src/hooks/useSSE.ts` / `frontend/src/stores/runStore.ts`(Plan C 已接全部事件,order-independent,replay 复用 live 解析路径)。

---

## 3. 关键真实代码锚点(实现据此,勿虚构)

- **replay 入口**:`runs.py:76-87` `get_stream` → `EventSourceResponse(_replay_from_trace(conn, run_id), ping=15)`;`run` 不存在已 404。
- **待 enrich 函数**:`sse.py:305-340` `_replay_from_trace(conn, run_id, *, pacing=0.02)`;现发 `start{replay:true}` → 每 trace 行 `trace{node,summary:{input,output,latency_ms},ts}` → `done{status}`。
- **重建数据源(repository,均已存在)**:
  - `repo.list_queries(conn, run_id)`(`repository.py:290`)→ `list[dict]`,键 `competitor/dimension/language/query_text/round/hit_count/created_at`。
  - `repo.list_evidence(conn, run_id)`(`repository.py:159`)→ `list[Evidence]`,属性 `id/competitor/dimension/content/source_url/source_title/language/fetched_at`(**无 round**)。
  - `repo.get_analysis(conn, run_id)`(`repository.py:182`)→ `CompetitorAnalysis | None`;`.comparison: list[ComparisonRow]`;`ComparisonRow.dimension/.cells`;`ComparisonCell.competitor/.value_type/.value/.evidence_refs/.support_verdict`;`EvidenceRef.evidence_id/.quote`(`models.py:39-128`)。**curated analysis 已丢弃 unsupported cell**(curate_analysis),故 `analysis` 只含 supported/partial cell。
  - `repo.list_curation_drops(conn, run_id)`(`repository.py:315`)→ `list[dict]`,键 `scope/competitor/dimension/detail/created_at`;scope ∈ {cell, decision}。
- **事件契约形状(与 live emit + `fakeSSEPlayer` 一致,前端据此解析)**:
  - `query`:`{competitor,dimension,query_text,language,round,ts}`
  - `query_hit`:`{query_text,hit_count,round,ts}`
  - `source`:`{evidence_id,competitor,dimension,source_title,source_url,language,fetched_at,round,ts}`
  - `cell_row`:`{dimension,status,cells:[{competitor,value_type,value,evidence_refs:[{evidence_id,quote}]}],ts}`(status replay 固定 `"ok"`,curated cell 都是保留格)
  - `verdict_recheck`:`{cell_verdicts:[{dimension,competitor,support_verdict}],dropped:[{dimension,competitor,detail}],downgraded:[],summary:{supported,partial,dropped},ts}`
- **emit 不经此路径**:replay 直接 `yield {"event":..., "data": json.dumps({...})}`(承 `_replay_from_trace` 既有风格),**不**走 live 的 `emit()`(那是 queue-driven live 专用)。
- **`_now()`**:`sse.py:56-57`(replay 重建事件的 ts 用它,或用记录的 `created_at`/`fetched_at` 真值,见各 task)。
- **测试 drain helper**:`test_api_sse.py:82-86` `_collect(gen)` async 收集 + `asyncio.run(...)`;seed 用 `repo.create_run` + `repo.insert_queries` / `repo.insert_evidence` / `repo.save_analysis` / `repo.replace_curation_drops` + `repo.update_run_status`。

---

## Epic 1 — 后端富 replay 重建(核心)

### Task 1: replay 重建 `query` + `query_hit`(检索台)

**Files:**
- Create: `tests/test_replay_parity.py`
- Modify: `rivalradar/api/sse.py:305-340`(`_replay_from_trace` 内,start yield 之后)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_replay_parity.py
import asyncio
import json

from rivalradar.api.sse import _replay_from_trace
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


async def _collect(gen):
    out = []
    async for ev in gen:
        out.append(ev)
    return out


def _replay(conn, run_id):
    return asyncio.run(_collect(_replay_from_trace(conn, run_id, pacing=0.0)))


def test_replay_reconstructs_query_and_query_hit(tmp_path):
    """刷新/深链:检索台从 queries 表重建,带真实 query_text/hit_count/round。"""
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_queries(c, "r1", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 定价 套餐", "round": 0, "hit_count": 4},
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 商业版 价格", "round": 1, "hit_count": 0},
    ])
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    queries = [json.loads(e["data"]) for e in events if e["event"] == "query"]
    hits = [json.loads(e["data"]) for e in events if e["event"] == "query_hit"]
    assert [q["query_text"] for q in queries] == ["飞书 定价 套餐", "飞书 商业版 价格"]
    assert [q["round"] for q in queries] == [0, 1]  # round 用 queries 表真值,非造假
    assert [h["hit_count"] for h in hits] == [4, 0]
    # 0 命中也要重建 query_hit(检索台标「该查询无结果」),失败路径覆盖
    assert hits[1]["hit_count"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py::test_replay_reconstructs_query_and_query_hit -v`
Expected: FAIL(无 query/query_hit 事件,只有 start+done)

- [ ] **Step 3: 实现 — 在 `_replay_from_trace` start yield 后插入 query 重建段**

`sse.py`:在 `_replay_from_trace` 的 `yield {"event": "start", ...}`(约 `sse.py:317-318`)之后、`for t in repo.list_trace(...)`(约 `sse.py:319`)之前,插入:

```python
    # ── Plan D 富 replay 重建:从持久化状态还原过程事件,刷新/深链进入不丢「看得见的活儿」。──
    # 不重建 evidence_delta(evidence 无 round 列)+ chunk/node/progress(瞬态 / summary 不可还原),
    # 见 plan D-D2/D-D3 诚实降级;矩阵/检索台/来源卡/三色这些「数据真」的核心活儿完整还原。

    # (1) query + query_hit(检索台):queries 表带真 round / hit_count;0 命中也重建(标「无结果」)。
    #     存局部变量 `queries`:Task 4 的 retryCount = max(queries.round) 复用,避免二次查表。
    queries = repo.list_queries(conn, run_id)
    for q in queries:
        yield {"event": "query", "data": json.dumps({
            "competitor": q["competitor"], "dimension": q["dimension"],
            "query_text": q["query_text"], "language": q["language"],
            "round": q["round"], "ts": q["created_at"]})}
        yield {"event": "query_hit", "data": json.dumps({
            "query_text": q["query_text"], "hit_count": q["hit_count"],
            "round": q["round"], "ts": q["created_at"]})}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py::test_replay_reconstructs_query_and_query_hit -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_replay_parity.py rivalradar/api/sse.py
git commit -m "feat(replay): reconstruct query/query_hit from queries table on replay"
```

---

### Task 2: replay 重建 `source`(来源卡)

**Files:**
- Modify: `tests/test_replay_parity.py`
- Modify: `rivalradar/api/sse.py`(query 段之后)

- [ ] **Step 1: 写失败测试**

```python
def test_replay_reconstructs_source_cards(tmp_path):
    """刷新/深链:来源卡从 evidence 表重建,带真实标题/域名/采集日期;round 默认 0(evidence 无 round 列,D-D4)。"""
    from rivalradar.schema.models import Evidence
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_evidence(c, "r1", Evidence(
        id="ev_1", competitor="飞书", dimension="pricing",
        content="商业版按人/月计费", source_url="https://www.feishu.cn/price",
        source_title="飞书定价 - 官网", language="zh", fetched_at="2026-05-28T10:00:03Z"))
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    sources = [json.loads(e["data"]) for e in events if e["event"] == "source"]
    assert len(sources) == 1
    s = sources[0]
    assert s["evidence_id"] == "ev_1"
    assert s["source_title"] == "飞书定价 - 官网"
    assert s["source_url"] == "https://www.feishu.cn/price"
    assert s["fetched_at"] == "2026-05-28T10:00:03Z"  # 前端 freshness 从 fetched_at 派生 stale
    assert s["round"] == 0  # evidence 无 round 列 → 退化默认 0,不造假
    # source 不含 provider/confidence(反幻觉 §1.5)
    assert "provider" not in s and "confidence" not in s
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py::test_replay_reconstructs_source_cards -v`
Expected: FAIL(无 source 事件)

- [ ] **Step 3: 实现 — query 段之后插入 source 重建段**

```python
    # (2) source(来源卡):evidence 无 round 列 → round 默认 0(D-D4);只发卡片字段,不发 content 全文
    #     (前端点击仍走 GET /evidence/{id} 拉全文);不含 provider/confidence(反幻觉 §1.5)。
    for ev in repo.list_evidence(conn, run_id):
        yield {"event": "source", "data": json.dumps({
            "evidence_id": ev.id, "competitor": ev.competitor, "dimension": ev.dimension,
            "source_title": ev.source_title, "source_url": ev.source_url,
            "language": ev.language, "fetched_at": ev.fetched_at,
            "round": 0, "ts": ev.fetched_at})}
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py::test_replay_reconstructs_source_cards -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_replay_parity.py rivalradar/api/sse.py
git commit -m "feat(replay): reconstruct source cards from evidence on replay"
```

---

### Task 3: replay 重建 `cell_row`(矩阵逐维)

**Files:**
- Modify: `tests/test_replay_parity.py`
- Modify: `rivalradar/api/sse.py`(source 段之后)

- [ ] **Step 1: 写失败测试**

```python
def _seed_analysis(c, run_id):
    """造一个含 2 维 × 真 support_verdict 的 curated analysis(unsupported 已被 curate 丢弃,
    故这里只放 supported/partial,模拟落库后形态)。"""
    from rivalradar.schema.models import (
        CompetitorAnalysis, ComparisonRow, ComparisonCell, EvidenceRef)
    analysis = CompetitorAnalysis(comparison=[
        ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="飞书", value_type="quote_text",
                           value="商业版按人/月", support_verdict="supported",
                           evidence_refs=[EvidenceRef(evidence_id="ev_1", quote="¥/人/月")]),
            ComparisonCell(competitor="钉钉", value_type="quote_text",
                           value="专业版年付", support_verdict="partial"),
        ]),
        ComparisonRow(dimension="core_workflows", cells=[
            ComparisonCell(competitor="飞书", value_type="quote_text",
                           value="一体化协作", support_verdict="supported"),
        ]),
    ])
    repo.save_analysis(c, run_id, analysis)


def test_replay_reconstructs_cell_row_per_dimension(tmp_path):
    """刷新/深链:矩阵从 curated analysis 逐维重建;cell 含真 value + evidence_refs。"""
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书", "钉钉"], ["pricing", "core_workflows"])
    _seed_analysis(c, "r1")
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    rows = [json.loads(e["data"]) for e in events if e["event"] == "cell_row"]
    ok_rows = [r for r in rows if r["status"] == "ok"]
    assert [r["dimension"] for r in ok_rows] == ["pricing", "core_workflows"]
    pricing = ok_rows[0]
    assert [cell["competitor"] for cell in pricing["cells"]] == ["飞书", "钉钉"]
    assert pricing["cells"][0]["evidence_refs"] == [{"evidence_id": "ev_1", "quote": "¥/人/月"}]
    # cell_row 本身不带 support_verdict(三色由 verdict_recheck 刷,Task 4)
    assert "support_verdict" not in pricing["cells"][0]


def test_replay_emits_empty_cell_row_for_dimension_absent_from_analysis(tmp_path):
    """codex finding #1/#5:请求维度但 analysis 无 row(无证据/失败)→ replay 发 status=empty,
    让 PlanRail 刷新后该维显「已知空」而非永远停在 todo(伪 pending)。不可区分 empty/failed
    时统一 empty(不伪造 failed,需 per-dim status 持久化才能真区分,超本计划)。"""
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    # 请求 3 维,但 analysis 只有 pricing + core_workflows(review_sentiment 缺)
    repo.create_run(c, "r1", ["飞书", "钉钉"],
                    ["pricing", "core_workflows", "review_sentiment"])
    _seed_analysis(c, "r1")
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    rows = [json.loads(e["data"]) for e in events if e["event"] == "cell_row"]
    by_dim = {r["dimension"]: r for r in rows}
    assert by_dim["review_sentiment"]["status"] == "empty"
    assert by_dim["review_sentiment"]["cells"] == []
    assert by_dim["pricing"]["status"] == "ok"
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py::test_replay_reconstructs_cell_row_per_dimension tests/test_replay_parity.py::test_replay_emits_empty_cell_row_for_dimension_absent_from_analysis -v`
Expected: 两条都 FAIL(无 cell_row 事件)

- [ ] **Step 3: 实现 — source 段之后插入 analysis 重建(cell_row + 缺维 empty)**

```python
    # (3) cell_row(矩阵逐维)+ (4) verdict_recheck(三色):从 curated analysis 重建。
    #     curated analysis 已丢弃 unsupported cell(curate_analysis),故只含 supported/partial。
    analysis = repo.get_analysis(conn, run_id)
    if analysis is not None:
        present_dims = set()
        for row in analysis.comparison:
            present_dims.add(row.dimension)
            yield {"event": "cell_row", "data": json.dumps({
                "dimension": row.dimension, "status": "ok",
                "cells": [{
                    "competitor": cell.competitor,
                    "value_type": cell.value_type,
                    "value": cell.value,
                    "evidence_refs": [{"evidence_id": r.evidence_id, "quote": r.quote}
                                      for r in cell.evidence_refs],
                } for cell in row.cells],
                "ts": _now()})}
        # codex finding #1:请求维度但 analysis 无 row(无证据/失败)→ 发 status="empty",
        # 让 PlanRail 刷新后显「已知空」而非永远 todo。不可区分 empty/failed → 统一 empty
        # (不伪造 failed;真区分需 per-dim status 持久化,超本计划,见 D-D3 注)。
        run = repo.get_run(conn, run_id)
        for dim in (run["dimensions"] if run else []):
            if dim not in present_dims:
                yield {"event": "cell_row", "data": json.dumps({
                    "dimension": dim, "status": "empty", "cells": [], "ts": _now()})}
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py::test_replay_reconstructs_cell_row_per_dimension tests/test_replay_parity.py::test_replay_emits_empty_cell_row_for_dimension_absent_from_analysis -v`
Expected: 两条都 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_replay_parity.py rivalradar/api/sse.py
git commit -m "feat(replay): reconstruct cell_row per dimension from curated analysis"
```

---

### Task 4: replay 重建 `verdict_recheck`(三色 + 剔除清单)

**Files:**
- Modify: `tests/test_replay_parity.py`
- Modify: `rivalradar/api/sse.py`(cell_row 重建之后,仍在 `if analysis is not None:` 块内)

- [ ] **Step 1: 写失败测试**

```python
def test_replay_reconstructs_verdict_recheck(tmp_path):
    """刷新/深链:StatusBar 三色 + 矩阵三色 + 已剔除清单从 analysis + curation_drops 重建。"""
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书", "钉钉"], ["pricing", "core_workflows"])
    _seed_analysis(c, "r1")  # supported×2(飞书 pricing/cw)+ partial×1(钉钉 pricing)
    repo.replace_curation_drops(c, "r1", "cell", [
        {"competitor": "钉钉", "dimension": "review_sentiment",
         "detail": "引用证据不支撑结论,策展剔除"},
    ])
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    vr = [json.loads(e["data"]) for e in events if e["event"] == "verdict_recheck"]
    assert len(vr) == 1
    v = vr[0]
    # cell_verdicts 从 curated analysis 逐 cell 取真 support_verdict(不复制到 ref,§7.2)
    verdicts = {(cv["dimension"], cv["competitor"]): cv["support_verdict"]
                for cv in v["cell_verdicts"]}
    assert verdicts[("pricing", "飞书")] == "supported"
    assert verdicts[("pricing", "钉钉")] == "partial"
    # dropped 从 curation_drops scope=cell 重建
    assert v["dropped"] == [{"dimension": "review_sentiment", "competitor": "钉钉",
                             "detail": "引用证据不支撑结论,策展剔除"}]
    # summary cell 级真算:supported 2 / partial 1 / dropped 1
    assert v["summary"] == {"supported": 2, "partial": 1, "dropped": 1}
    # codex finding #3:downgraded = partial cell 子集(对齐 live 契约,非 [])
    assert v["downgraded"] == [{"dimension": "pricing", "competitor": "钉钉",
                                "support_verdict": "partial"}]
    # C-D6/D-D5:replay verdict_recheck 无 decision_verdicts(决策三色经 GET /decisions)
    assert "decision_verdicts" not in v


def test_replay_reconstructs_retry_count_from_query_rounds(tmp_path):
    """codex finding #2:replay 从 max(queries.round) 重建 retryCount,经合成 qc node 事件注入,
    让「自我纠错 N 次 / N 轮」replay 显真值而非恒 0。仅当 qc_result 存在才发 node 事件。"""
    from rivalradar.schema.models import QCResult
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_queries(c, "r1", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "q0", "round": 0, "hit_count": 1},
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "q1 broaden", "round": 1, "hit_count": 2},  # retry 轮
    ])
    _seed_analysis(c, "r1")
    repo.save_qc_result(c, "r1", QCResult(verdict="pass", issues=[]))
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    qc_nodes = [json.loads(e["data"]) for e in events
                if e["event"] == "node" and json.loads(e["data"]).get("node") == "qc"]
    assert len(qc_nodes) == 1
    assert qc_nodes[0]["summary"]["retry_count"] == 1  # max(queries.round) 真值
    assert qc_nodes[0]["summary"]["verdict"] == "pass"


def test_replay_no_analysis_emits_no_cell_or_verdict(tmp_path):
    """边界:run 无 analysis(早失败 / cancelled)→ 不发 cell_row / verdict_recheck,只 start+trace+done。"""
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r2", ["飞书"], ["pricing"])
    repo.update_run_status(c, "r2", "failed")
    events = _replay(c, "r2")
    assert not any(e["event"] in ("cell_row", "verdict_recheck") for e in events)
    assert events[0]["event"] == "start"
    assert events[-1]["event"] == "done"
    assert json.loads(events[-1]["data"])["status"] == "failed"
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py::test_replay_reconstructs_verdict_recheck tests/test_replay_parity.py::test_replay_reconstructs_retry_count_from_query_rounds tests/test_replay_parity.py::test_replay_no_analysis_emits_no_cell_or_verdict -v`
Expected: 前两条 FAIL(无 verdict_recheck / 无 qc node);`test_replay_no_analysis...` 应已 PASS(无 analysis → 无 cell_row,Task 3 的 `if analysis is not None` 守住;无 qc_result → 不发 qc node)

- [ ] **Step 3: 实现 — 完成 `if analysis is not None:` 块(累计 verdict + emit verdict_recheck)+ 块外合成 qc node**

把 Task 3 的循环改造为同时累计 verdict 统计;循环 + 缺维 empty 之后 emit verdict_recheck(downgraded = partial 子集,codex #3);最后(块外)合成 qc node 注入真 retryCount(codex #2)。**注意 `queries` 需在 Task 1 起就存成局部变量复用**(改 Task 1 的 `for q in repo.list_queries(...)` 为先 `queries = repo.list_queries(conn, run_id)` 再 `for q in queries:`)。完整最终形态:

```python
    # (1) query/query_hit —— Task 1,改为先存局部变量供 retryCount 复用
    queries = repo.list_queries(conn, run_id)
    for q in queries:
        ...  # (Task 1 的 query + query_hit yield 不变)

    # (2) source —— Task 2 不变

    # (3)+(4) cell_row + verdict_recheck —— Task 3/4
    analysis = repo.get_analysis(conn, run_id)
    if analysis is not None:
        present_dims: set[str] = set()
        cell_verdicts: list[dict] = []
        n_supported = 0
        n_partial = 0
        for row in analysis.comparison:
            present_dims.add(row.dimension)
            yield {"event": "cell_row", "data": json.dumps({
                "dimension": row.dimension, "status": "ok",
                "cells": [{
                    "competitor": cell.competitor,
                    "value_type": cell.value_type,
                    "value": cell.value,
                    "evidence_refs": [{"evidence_id": r.evidence_id, "quote": r.quote}
                                      for r in cell.evidence_refs],
                } for cell in row.cells],
                "ts": _now()})}
            for cell in row.cells:
                cell_verdicts.append({
                    "dimension": row.dimension, "competitor": cell.competitor,
                    "support_verdict": cell.support_verdict})
                if cell.support_verdict == "supported":
                    n_supported += 1
                elif cell.support_verdict == "partial":
                    n_partial += 1
        # codex #1:请求维度但无 analysis row → 发 empty(见 Task 3 注)
        run = repo.get_run(conn, run_id)
        for dim in (run["dimensions"] if run else []):
            if dim not in present_dims:
                yield {"event": "cell_row", "data": json.dumps({
                    "dimension": dim, "status": "empty", "cells": [], "ts": _now()})}
        dropped = [{"dimension": d["dimension"], "competitor": d["competitor"],
                    "detail": d["detail"]}
                   for d in repo.list_curation_drops(conn, run_id)
                   if d["scope"] == "cell"]
        # codex #3:downgraded = partial cell 子集(对齐 live 契约);C-D6:无 decision_verdicts。
        downgraded = [cv for cv in cell_verdicts if cv["support_verdict"] == "partial"]
        yield {"event": "verdict_recheck", "data": json.dumps({
            "cell_verdicts": cell_verdicts,
            "dropped": dropped,
            "downgraded": downgraded,
            "summary": {"supported": n_supported, "partial": n_partial,
                        "dropped": len(dropped)},
            "ts": _now()})}

    # (5) codex #2:合成终态 qc node 注入真 retryCount,让「自我纠错 N 次/N 轮」replay 显真值。
    #     仅当 qc_result 存在才发(空/早失败 run 不发,保既有空-run 测试 + test_replay_no_analysis)。
    qc_res = repo.get_qc_result(conn, run_id)
    if qc_res is not None:
        max_round = max((q["round"] for q in queries), default=0)
        run_row = repo.get_run(conn, run_id)
        yield {"event": "node", "data": json.dumps({
            "node": "qc",
            "summary": {"node": "qc", "verdict": qc_res.verdict,
                        "issues": len(qc_res.issues), "issue_types": {},
                        "retry_count": max_round,
                        "degraded": bool(run_row["degraded"]) if run_row else False},
            "ts": _now()})}
```

> **实现者必读**(codex #2 注入安全性):合成 qc `node` 事件前,读 `frontend/src/stores/runStore.ts` 的 `handleEvent` node 分支(约 `runStore.ts:360-380`),确认对一个 replay 终态 run 发 qc node 只更新 `retryCount` + qc node 状态、**不**重置其他切片(queries/sources/cellRows)。Epic 2 的 `/browse` 验证 WorkbenchSummary「自我纠错 N 次」显真值且无副作用。若发现有害副作用 → 回落 D-D3 fallback:只改文案声明 retryCount replay 不还原(不发 node 事件),并在本计划记录。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_replay_parity.py rivalradar/api/sse.py
git commit -m "feat(replay): verdict_recheck (cell verdicts/drops/downgraded) + retry_count via synthetic qc node"
```

---

### Task 5: 回归 + 顺序契约 + 既有 replay 测试不破

**Files:**
- Modify: `tests/test_replay_parity.py`(加顺序断言)

- [ ] **Step 1: 写顺序契约测试**

```python
def test_replay_event_order_and_trace_preserved(tmp_path):
    """整流顺序:start → query/query_hit/source → cell_row → verdict_recheck → trace → done;
    且既有 trace 事件不破(§11.4 Play)。前端 reducer order-independent,此测试锁后端可读顺序。"""
    from rivalradar.schema.models import Evidence
    c = connect(str(tmp_path / "rp.db"))
    init_db(c)
    repo.create_run(c, "r1", ["飞书"], ["pricing"])
    repo.insert_queries(c, "r1", [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 定价", "round": 0, "hit_count": 1}])
    repo.insert_evidence(c, "r1", Evidence(
        id="ev_1", competitor="飞书", dimension="pricing", content="x",
        source_url="https://feishu.cn", source_title="官网", language="zh",
        fetched_at="2026-05-28T10:00:03Z"))
    _seed_analysis(c, "r1")
    repo.append_trace(c, "r1", "collect", output_summary="+1", latency_ms=10)
    repo.update_run_status(c, "r1", "done")

    events = _replay(c, "r1")
    order = [e["event"] for e in events]
    assert order[0] == "start" and order[-1] == "done"
    # 富事件在 trace 之前(D-D3),trace 保留(既有 Play 不破)
    assert order.index("query") < order.index("cell_row") < order.index("verdict_recheck")
    assert order.index("verdict_recheck") < order.index("trace")
    assert "trace" in order  # §11.4 Play 仍有 trace
```

- [ ] **Step 2: 运行新测试 + 既有 replay 回归**

Run: `.venv/bin/python -m pytest tests/test_replay_parity.py tests/test_api_sse.py -v`
Expected: 全 PASS —— 特别确认 `test_api_sse.py` 既有 `test_replay_from_trace_yields_trace_events` / `test_replay_trace_event_uses_unified_summary_shape` / `test_replay_from_trace_no_trace_yields_only_start_done` **不破**(它们 seed 无 queries/evidence/analysis → 富段空发,只剩 start+trace+done;过滤式断言不受影响)。

- [ ] **Step 3: 全量回归**

Run: `.venv/bin/python -m pytest`
Expected: 全 PASS(~387+5 新测试)。**若 `test_replay_from_trace_no_trace_yields_only_start_done` 红** → 说明富段对空数据误发事件,回 Task 1-4 加空守卫(`list_*` 空 → 不进循环;`get_analysis` None → 跳过,已守)。

- [ ] **Step 4: Commit**

```bash
git add tests/test_replay_parity.py
git commit -m "test(replay): lock event order contract + assert legacy trace replay intact"
```

---

## Epic 2 — replay 端到端验证(无 LLM,seed 真 run → 真 replay)

> 记忆 [[real-run-surfaces-pipeline-scoping-bugs]] / [[silent CSS / type-domain 混淆]]:单测全绿 ≠ 真打对;contract mismatch(后端 replay 事件形状 vs 前端 reducer 期待)只有真打 replay 才暴露。本 Epic 用 seed-db(无 LLM,绕开 Doubao/Clash)起真后端,`/browse` 深链触发真 `GET /stream/{id}`。

### Task 6: seed 脚本 + 端到端 replay /browse 验证

**Files:**
- Create: `spikes/seed_replay_run.py`(spike 目录,不进 pytest,CLAUDE.md 测试纪律)

- [ ] **Step 1: 写 seed 脚本**(造一个完整 done run 到指定 db,数据形态同 Task 1-4)

```python
# spikes/seed_replay_run.py — seed 一个完整 done run 供 replay 端到端验证(无 LLM)。
# 用法:.venv/bin/python spikes/seed_replay_run.py /tmp/rivalradar_replay.db run_seed01
import sys
from rivalradar.storage.db import connect, init_db
from rivalradar.storage import repository as repo
from rivalradar.schema.models import (
    CompetitorAnalysis, ComparisonRow, ComparisonCell, EvidenceRef, Evidence)

db_path, run_id = sys.argv[1], sys.argv[2]
c = connect(db_path); init_db(c)
repo.create_run(c, run_id, ["飞书", "钉钉", "企业微信"], ["pricing", "core_workflows"])
repo.insert_queries(c, run_id, [
    {"competitor": "飞书", "dimension": "pricing", "language": "zh",
     "query_text": "飞书 定价 套餐 价格", "round": 0, "hit_count": 4},
    {"competitor": "企业微信", "dimension": "core_workflows", "language": "en",
     "query_text": "WeCom workflow review english", "round": 0, "hit_count": 0},
])
repo.insert_evidence(c, run_id, Evidence(
    id="ev_1", competitor="飞书", dimension="pricing", content="商业版按人/月计费",
    source_url="https://www.feishu.cn/price", source_title="飞书定价 - 官网",
    language="zh", fetched_at="2026-05-28T10:00:03Z"))
repo.save_analysis(c, run_id, CompetitorAnalysis(comparison=[
    ComparisonRow(dimension="pricing", cells=[
        ComparisonCell(competitor="飞书", value_type="quote_text", value="商业版按人/月",
                       support_verdict="supported",
                       evidence_refs=[EvidenceRef(evidence_id="ev_1", quote="¥/人/月")]),
        ComparisonCell(competitor="钉钉", value_type="quote_text", value="专业版年付",
                       support_verdict="partial"),
    ]),
    ComparisonRow(dimension="core_workflows", cells=[
        ComparisonCell(competitor="飞书", value_type="quote_text", value="一体化协作",
                       support_verdict="supported"),
    ]),
]))
repo.replace_curation_drops(c, run_id, "cell", [
    {"competitor": "企业微信", "dimension": "core_workflows", "detail": "证据不支撑,策展剔除"}])
repo.append_trace(c, run_id, "collect", output_summary="+1", latency_ms=10)
repo.append_trace(c, run_id, "qc", output_summary="verdict=pass", latency_ms=20)
repo.update_run_status(c, run_id, "done")
print(f"seeded {run_id} into {db_path}")
```

- [ ] **Step 2: seed + 起后端指向该 db**

Run(每条新 bash 必 unset 代理,记忆 WSL2 Clash):
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1
.venv/bin/python spikes/seed_replay_run.py /tmp/rivalradar_replay.db run_seed01
# 起后端(确认后端用哪个 env var 指定 db path:读 rivalradar/api/deps.py 的 get_db_conn / config;
# 通常 RIVALRADAR_DB_PATH 或同名)。示例:
RIVALRADAR_DB_PATH=/tmp/rivalradar_replay.db .venv/bin/python -m uvicorn rivalradar.api.app:app --port 8787
```
> 实现前先 `grep -rn "DB_PATH\|db_path\|getenv" rivalradar/api/deps.py rivalradar/config.py` 确认真实 env var 名,**勿虚构**。前端 dev server 的 `/api` 代理目标端口对齐(读 `frontend/vite.config.*` 的 proxy)。

- [ ] **Step 3: `/browse` 深链验证 replay**

用 gstack `/browse`(强制,**禁** `mcp__claude-in-chrome__*`)打开 `http://localhost:5173/run/run_seed01`(前端 dev port),验证(深链 → `useSSE` replay → 真 `GET /stream/run_seed01`):
- 检索台显示真查询词「飞书 定价 套餐 价格」+ 命中 4;英文 query 0 命中标「该查询无结果」。
- 来源卡显示「飞书定价 - 官网」+ 域名 feishu.cn + 采集日期。
- 矩阵逐维填(pricing / core_workflows),飞书 pricing = supported(绿●),钉钉 pricing = partial(琥珀◐)。
- StatusBar:充分 2 · 部分 1 · 已剔除 1;点「已剔除」弹出清单含「企业微信 · core_workflows」。
- **无 dead-loop / 无 zustand 崩溃 / 无白屏**(记忆 [[zustand selector infinite loop]]:replay 终态 storeStatus 走 `!== 'idle'` guard,RunPage:80)。
- 截图存证。

- [ ] **Step 4: 修复 + 复验(若 Step 3 抓到 contract mismatch)**

若某面板空/错位 → 多半是后端 replay 事件形状与前端 reducer 期待不符。回 Epic 1 对应 task 修事件形状(对照 §3「事件契约形状」),`pytest` 复跑 + 重 `/browse`。**不改前端 reducer**(Plan C 已与 live 契约对齐;replay 必须发同形状)。

- [ ] **Step 5: 收尾(spike 不 commit 进产物或按需保留)**

`spikes/seed_replay_run.py` 是验证工具(`spikes/` 不进 pytest)。可 commit 留作回归工具:
```bash
git add spikes/seed_replay_run.py
git commit -m "test(replay): add seed-db spike for end-to-end replay /browse verification"
```

---

## Epic 3 — demo URL 端到端 spike(整链 demo bullet-proof 复核)

> 记忆 [[demo bullet-proof]]:ship demo path 后必须用真 URL 端到端验证完整 25s 无循环,不能假设 path 自洽(Epic 7.1 曾因没自跑 demo URL 漏 run_id mismatch dead loop)。

### Task 7: demo `/run/run_demo01` 完整 25s /browse spike

**Files:** 无源改动(验证 only;除非抓到问题)

- [ ] **Step 1: 起前端 dev server(不需后端,demo 走 fakeSSEPlayer)**

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
cd frontend && pnpm dev
```

- [ ] **Step 2: `/browse` 跑 demo 完整 25s**

`/browse` 打开 `http://localhost:5173/run/run_demo01`,完整观察 25s(speed=1.0 真节奏):
- 4-agent cycle 全跑:collector 检索 → analyst 逐维矩阵 → writer 报告台打字 → qc 三色 + 剔除 → decide 决策。
- 新事件全产出:检索台逐查询 + 命中、来源卡、矩阵逐维三色(含 ◐ partial)、重试环「证据 12→19」、StatusBar 充分 4·部分 2·已剔除 1、决策卡三色。
- **关键:全程无 dead-loop**(记忆:`isDemoRun` guard + `runId` 对齐 + `storeStatus !== 'idle'`,RunPage:70-88);终态稳定不重播。
- 截图存证(running 中 + done 后各一)。

- [ ] **Step 3: 修复 + 复验(若抓到)**

若 dead-loop / 事件缺失 / 时序错 → 定位 `fakeSSEPlayer.ts`(D-D7 仅在抓到才动)或 RunPage guard,修后重 spike。

- [ ] **Step 4: Commit(仅当有源改动)**

```bash
git add frontend/src/dev/fakeSSEPlayer.ts  # 若 Step 3 改了
git commit -m "fix(demo): <具体修复> surfaced by end-to-end demo URL spike"
```

---

## Epic 4 — DESIGN.md v5 已写校验

### Task 8: 核对 spec §8 五项增量在 DESIGN.md

**Files:**
- Verify: `DESIGN.md`(缺项才补)

- [ ] **Step 1: 读 DESIGN.md + 核对 spec §8 五项**

Run: `grep -n "v5\|融合主轴\|工牌\|技能\|支持度\|充分\|部分\|已剔除\|审计\|绝对日期\|YYYY-MM-DD" DESIGN.md`
逐项核对 spec §8(`docs/superpowers/specs/2026-06-07-process-viz-redesign-design.md:270-280`):
1. 融合主轴 v5(右栏「研究员工作台」规格 + done 态收窄)。
2. agent 人格层(工牌规格:头像/身份色/工号/状态灯/当前任务;机构级持证专家立场,非 office 拟物;头像可换占位)。
3. 技能子系统(技能卡 UI:name+描述+版本+开关+删除,无 why/boundary;skillState 模型;「行为接入二期」诚实标注)。
4. support_verdict 真算三色语义(supported●/partial◐ 回写矩阵/决策;unsupported○ = StatusBar 策展剔除计数;移除「原型态」概念)。
5. 审计化文案 + 绝对日期(无渐变、阴影仅浮层、YYYY-MM-DD / HH:MM)+ Decisions Log 加「v5 增量来源 = 本 spec」。

- [ ] **Step 2: 缺项才补**(全在 → 跳过,标 skipped)

若某项缺,按 spec §8 对应条补进 DESIGN.md(surgical,只补缺项,不重写既有节)。

- [ ] **Step 3: Commit(仅当有改动)**

```bash
git add DESIGN.md
git commit -m "docs(design): backfill DESIGN.md v5 increments missing vs spec §8"
```

---

## 最终验收(全 Epic 完成后)

- [ ] **后端全量回归**:`.venv/bin/python -m pytest` 全绿(~387 + 6 新 replay parity 测试)。
- [ ] **前端 clean build**:`cd frontend && pnpm build`(必要时 `rm -rf node_modules/.tmp && pnpm exec tsc -b --force && pnpm build`)exit 0。
- [ ] **replay 端到端**(Epic 2):seed-db + `/browse` 深链 → 工作台 + 三色 + 矩阵完整还原,无 dead-loop。
- [ ] **demo 端到端**(Epic 3):`/browse` demo URL 完整 25s 无 dead-loop。
- [ ] **DESIGN.md v5**(Epic 4):spec §8 五项全在。
- [ ] **ship 前 codex outside-voice**(记忆 confidence 10/10:ship-time outside voice 必跑,抓 plan-time 不同类 bug):`/codex review` 本计划全链 diff,逐条裁决进 commit body([[outside-voice 必逐条裁决]])。
- [ ] **整链 push / PR**:`feat/process-viz-redesign`(基线 `b7c3234` + Plan A 9 + Plan B 14 + Plan C doc + 31 + Plan D)→ 远端 PR(WSL2 Clash:unset 代理 + `NO_PROXY=github.com`,或用户手动 push,记忆 [[WSL2 Clash 也卡 git push]])。

---

## Self-Review(写完计划自核,对照 spec)

- **spec 覆盖**:§9「demo/replay 平价」→ Epic 1(replay)+ Epic 2/3(端到端);§7.3「verdict_recheck 结构化持久化…否则 replay 丢」→ Task 4 从 curation_drops + analysis 重建已兑现持久化的设计意图;§8 DESIGN.md v5 → Epic 4。
- **placeholder 扫描**:每个 code step 给完整可运行代码(测试 + 实现 + seed 脚本);Epic 2 Step 2 的 env var 名标「实现前 grep 确认勿虚构」(因 deps.py 未在本计划读到,显式留确认动作而非假装知道,符合 CLAUDE.md §1 不假设)。
- **类型一致**:`_replay_from_trace` 名贯穿(D-D6);事件形状(query/source/cell_row/verdict_recheck)与 §3 契约 + `fakeSSEPlayer` + 前端 `SSE*Data` 类型一致;`ComparisonCell.value_type/.value/.evidence_refs/.support_verdict`、`EvidenceRef.evidence_id/.quote` 对齐 `models.py:39-128`;`list_curation_drops` 键 `scope/competitor/dimension/detail` 对齐 `repository.py:315`。
- **诚实降级显式**:D-D2/D-D3(evidence_delta/chunk/node/progress replay 不重建)在「不在本计划」+ 决策表写死,Epic 1 注释也写明 —— 交 codex 裁决是否可接受。

---

## Codex 裁决(2026-06-07 plan-phase,gpt-5.5,逐条采纳)

> codex 真读仓库交叉验证:**核心字段/表列/返回键零虚构**(grounding 到位)。抓 3 个真 replay 保真度缺口(P2)+ 2 个文档/测试(P3)。逐条裁决([[outside-voice 必逐条裁决]]):

- **#1 [P2] cell_row 缺维平价 → 采纳**:live 对每个请求维 emit `cell_row(ok|empty|failed)`(`analyst.py:231`,`nodes.py:198`),但持久化 analysis 只存有结果的 row(`analyst.py:267`);replay 只遍历 `analysis.comparison` → 缺维刷新后 PlanRail 停 `todo`(伪 pending,`PlanRail.tsx:100`)。修:请求维缺 row → 发 `status="empty"`(不可区分 empty/failed 统一 empty,不伪造 failed,真区分需 per-dim status 持久化超本计划)。落 Task 3 + 新测试。
- **#2 [P2] retry/纠错次数 replay 归零 → 采纳**:RetryLoop 只读 `evidenceDeltas`(round>0,`RetryLoop.tsx:17`);「自我纠错 N 次」读 `retryCount`,只从 live `node` qc summary 更新,trace 置 `summary=null` 不更新(`runStore.ts:363`)→ replay 恒显 0(错数,违反反幻觉)。修:`max(queries.round)`(持久化真值)经合成终态 qc `node` 事件注入 retryCount;RetryLoop 动画仍 live-only(文案改准)。落 D-D3 + Task 4 + 新测试 + 实现者读 node 分支确认无副作用。
- **#3 [P2] downgraded 契约漂移 → 采纳**:live `downgraded` 是 partial cell 子集(`nodes.py:349,355`,`schemas.py:213`),计划发 `[]`(前端暂未消费但防漂移)。修:replay `downgraded = [cv for cv in cell_verdicts if cv["support_verdict"]=="partial"]`。落 D-D2b + Task 4。
- **#4 [P3] replay 增量价值厘清 → 采纳**:矩阵有 REST `/analysis` 兜底(`CompetitorComparison.tsx:298`),replay cell_row 非矩阵前提;真不可替代 = 检索台/来源卡(只读 SSE store,无 REST)+ StatusBar 充分·部分(`verdictSummary` 只来自 SSE)。落 §0 价值陈述。
- **#5 [P3] 无虚构 + 测试盲区 → 采纳**:字段/列全核对真实代码无误;加「请求维无 analysis row → empty」测试。落 Task 3 `test_replay_emits_empty_cell_row_for_dimension_absent_from_analysis`。

**裁决后状态**:3 P2 全在计划修订到位(Task 3/4 + D-D2b/D-D3 + 3 条新测试),可进实现。
