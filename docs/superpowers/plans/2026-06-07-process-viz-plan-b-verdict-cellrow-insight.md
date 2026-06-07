# Plan B — support_verdict 真算三级 + 逐格 cell_row + insight 两步化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把后端三件「产物边生成边长 + 反幻觉真收口」做真:① 撰写员报告台 insight 两步化(流式草稿喂 typing → 抽成结构化 ReportInsight,契约不破);② support_verdict 三级真算并回写到 cell/decision(unsupported 仍策展丢弃,partial 保留标黄,与重试路由解耦);③ analyze 逐维 emit `cell_row` 让矩阵边算边填。

**Architecture:** 沿用 Plan A 的「节点经 `config["configurable"]["emit"]` 注入回调发轻量 SSE 事件 + 落库」架构。**核心设计:三级 verdict 回写到 curated 的 cell/decision 字段上 → 随 `save_analysis`/`save_decisions` 落库 → `curate_*` 二元组签名不变(零调用点破坏)**;三级判定独立于 `qc_result.issues`(不进 `decide_verdict`,守策展人模型);剔除清单(dropped)新表结构化持久化(replay 平价)。insight 两步化 Doubao 流式已由 Plan A Spike H 验证 GO(`spikes/SPIKE_RESULTS.md` Spike H)。

**Tech Stack:** Python 3 · LangGraph(sync 节点)· sqlite3(WAL)· FastAPI · pydantic · pytest(monkeypatch + tmp_path + 线程安全 _FakeClient)· OpenAI 兼容 Doubao SDK(structured_call function-calling + stream_chat 流式)。

**来源 spec:** `docs/superpowers/specs/2026-06-07-process-viz-redesign-design.md`(§5.3 / §5.5 / §5.6 / §7.1 / §7.2 / §7.3)。
**前置:** Plan A 已 ship 到分支 `feat/process-viz-redesign`(后端真实活儿 emit + Spike H GO)。本 Plan 在同分支续作。**只动后端**(前端消费在 Plan C,replay 事件生成 + DESIGN v5 + demo 平价在 Plan D)。

---

## Codex 裁决(plan 阶段 outside-voice,2026-06-07,逐条)

跨模型对真实代码 grep 后 8 findings(2 P1 + 6 P2),逐条裁决:

| # | 级别 | finding | 裁决 | 落点 |
|---|------|---------|------|------|
| 1 | P1 | `qc.check()`(qc.py:432)经 check_entailment→decide_verdict 把 unsupported→retry_analyze,plan「三级不进 issues」断言过宽 | **采纳**:精确化——活路径=qc_node 走 curate(Task 5 后用 `_judge_comparison_verdicts`,不经 check_entailment);**partial 永不成 issue**(Task 6);unsupported→issue 仅遗留 `qc.check()`(无生产节点调用,非回归) | Epic B 不变量精确化 + Task 5 加「partial 不触发 retry_analyze」测试 |
| 2 | P1 | `curation_drops` append-only,qc_node 多轮重试 + save_analysis 是 INSERT OR REPLACE → replay 幽灵剔除 | **采纳**(真 bug) | Task 9/10:改 **REPLACE per (run_id, scope)**(每轮删后插)|
| 3 | P2 | cell_row 漏「无证据维」(row None 无异常)→ 前端分不清 pending/空 | **采纳** | Task 7/8:无证据维 emit `status="empty"` |
| 4 | P2 | verdict_recheck 漏 decision_verdicts(spec §7.1 列了) | **部分采纳**:decision 在 decide_node(晚于 qc)才 curate,qc 时不存在 → 显式标注为 spec 偏差;decision verdict 随 `Decision.support_verdict` + save_decisions 落库,decide_node 也持久化 decision 剔除 | Task 10 偏差说明 + decide_node 持久化 |
| 5 | P2 | drop label 拼接 "comp/dim" 有损(名字含 `/` 不可还原) | **采纳** | Task 5/9:`dropped` 改 `list[dict]` 结构化 + curation_drops 存结构化列 |
| 6 | P2 | insight 回落后已 emit 的草稿 chunk 留在 typing 流无 reset | **部分采纳**:草稿非权威,结构化产物始终经 save_insight + REST 落定;前端 done 时以 REST 为准(reconcile 归 Plan C)| Task 1 文档化 |
| 7 | P2 | Task 3 测试 Decision 枚举字面量错(真值中文) | **采纳** | Task 3/6:用真实 `Stance=建议采用` / `Horizon=短期` / `Reversibility=可逆` / `RiskCost=低` |
| 8 | P2 | 残留旧行号 273/391 | **驳回**:plan grep 无 273/391,已用真实 316/326/434(codex 看的是 spec 的旧引用) | 无需改 |

净结论:无虚构签名;核心设计(verdict 回写 cell/decision 字段、curate 二元组不破、partial 永不路由)成立但**不变量陈述需精确到 qc_node 活路径**;两处真 bug(append-only 剔除清单、有损 label)已转为「REPLACE 语义 + 结构化列 + dropped→list[dict]」。

## Spike H 结论(Plan A 已验,本 Plan 据此实现 insight 两步)

`spikes/SPIKE_RESULTS.md` Spike H:Doubao `stream_chat` 真能流式(729-871 chunks,~80-90 chunk/s),两步抽取 ReportInsight 三字段稳定 → **insight 走真 typing**。硬约束:**TTFB 37-40s**(复杂 prompt 首 token 思考延迟,非网络)→ **首块前必须有「起草中」占位**(write_node 现有 `_emit_progress(emit, "writer", "drafting", ...)` 已在 LLM 调用前发出,正好接住这 38s,本 Plan 复用它,不空屏)。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `rivalradar/agents/writer.py` | 加 `generate_insight_streamed`(两步+回落);`write_report_with_insight` 加 `emit` 参数透传 | Modify |
| `rivalradar/graph/nodes.py` | `write_node` 传 emit;`qc_node` emit `verdict_recheck` + 持久化 cell 剔除;`decide_node` 持久化 decision 剔除;`analyze_node` 传 `on_cell_row` | Modify |
| `rivalradar/schema/models.py` | `ComparisonCell` / `Decision` 加 `support_verdict` 字段 | Modify |
| `rivalradar/agents/qc.py` | `EntailmentVerdict` 升三级;新 `_judge_comparison_verdicts`;`check_entailment`/`check_decision_entailment`/`curate_analysis`/`curate_decisions` 改用三级 + 回写 cell/decision | Modify |
| `rivalradar/agents/analyst.py` | `build_comparison` / `analyze` 加 `on_cell_row` 回调 | Modify |
| `rivalradar/storage/db.py` | 加 `curation_drops` 表(结构化列)| Modify(SCHEMA)|
| `rivalradar/storage/repository.py` | `replace_curation_drops`(REPLACE per scope)/ `list_curation_drops` | Modify |
| `rivalradar/api/schemas.py` | `SSECellRowData` / `SSEVerdictRecheckData` | Modify |
| `rivalradar/api/reads.py` | `GET /runs/{id}/curation-drops` | Modify |
| `tests/test_writer_agent.py` | insight 两步 + 回落测试 | Modify |
| `tests/test_qc_agent.py` | 三级 entailment + 回写 + 不进路由(测病因不变量)+ 既有 payload 迁移 | Modify |
| `tests/test_analyst_agent.py` | `on_cell_row` 逐维回调(含失败维)测试 | Modify |
| `tests/test_graph_nodes.py` | write_node 两步 / qc_node verdict_recheck + 剔除持久化 / analyze_node cell_row 测试 | Modify |
| `tests/test_curation_drops_repo.py` | curation_drops 表 CRUD | Create |
| `tests/test_api_reads.py` | `GET /runs/:id/curation-drops` 测试 | Modify |

---

## Epic A — insight 两步化真字符流(§5.6,Spike H 已 GO)

### Task 1: `generate_insight_streamed`(两步 + 回落)

**Files:**
- Modify: `rivalradar/agents/writer.py`
- Test: `tests/test_writer_agent.py`

- [ ] **Step 1: 写失败测试(两步流式 + 回落)**

追加到 `tests/test_writer_agent.py`(顶部确认已 `import json`、`from types import SimpleNamespace`、`from rivalradar.schema.models import ReportInsight`;`from rivalradar.agents.writer import generate_insight_streamed` 放测试函数内或顶部):

```python
class _StreamThenStructured:
    """create(stream=True) → 逐 delta 吐流;create(无 stream,structured_call) → tool_call(ReportInsight JSON)。"""
    def __init__(self, deltas, insight_json, raise_on_stream=False):
        self.deltas = deltas; self.insight_json = insight_json
        self.raise_on_stream = raise_on_stream
    def create(self, **kw):
        if kw.get("stream"):
            if self.raise_on_stream:
                raise RuntimeError("stream boom")
            def gen():
                for d in self.deltas:
                    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=d))])
            return gen()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=self.insight_json))]))],
            usage=SimpleNamespace(total_tokens=10))


class _StreamClient:
    def __init__(self, deltas, insight_json, raise_on_stream=False):
        self.chat = SimpleNamespace(completions=_StreamThenStructured(deltas, insight_json, raise_on_stream))


_INSIGHT_JSON = json.dumps({"market_context": "m", "differentiation_thesis": "d",
                            "actionable_takeaway": "a"})


def test_generate_insight_streamed_emits_chunks_then_extracts():
    from rivalradar.agents.writer import generate_insight_streamed
    client = _StreamClient(["市场", "格局", "三足"], _INSIGHT_JSON)
    chunks = []
    def emit(ev_type, data):
        if ev_type == "chunk":
            chunks.append(data["delta"])
    insight = generate_insight_streamed("BODY", client=client, model="m", emit=emit)
    assert chunks == ["市场", "格局", "三足"]            # Step1 真流 delta
    assert insight.market_context == "m" and insight.actionable_takeaway == "a"  # Step2 抽取契约不破


def test_generate_insight_streamed_falls_back_when_stream_fails():
    from rivalradar.agents.writer import generate_insight_streamed
    client = _StreamClient([], _INSIGHT_JSON, raise_on_stream=True)
    chunks = []
    def emit(ev_type, data):
        chunks.append(data)
    insight = generate_insight_streamed("BODY", client=client, model="m", emit=emit)
    assert chunks == []                                  # stream 抛错 → 无 chunk
    assert insight.market_context == "m"                 # 回落一次性,数据仍真


def test_generate_insight_streamed_emit_none_is_oneshot():
    from rivalradar.agents.writer import generate_insight_streamed
    client = _StreamClient(["x"], _INSIGHT_JSON)
    insight = generate_insight_streamed("BODY", client=client, model="m", emit=None)
    assert insight.differentiation_thesis == "d"         # emit=None → 直接一次性,不走 stream
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py::test_generate_insight_streamed_emits_chunks_then_extracts -v`
Expected: FAIL(`ImportError: cannot import name 'generate_insight_streamed'`)。

- [ ] **Step 3: 实现 `generate_insight_streamed`(`writer.py`)**

在 `writer.py` 顶部 import 区补 `stream_chat` 与 `Callable`:

```python
from collections.abc import Callable

from rivalradar.llm.streaming import stream_chat
```

在 `generate_insight`(行 143-182)之后加:

```python
_INSIGHT_DRAFT_PROMPT = (
    "你是竞品战略分析师。基于下面的对比正文,写一段三部分的自由文本草稿:"
    "①市场格局 ②战略路径分歧 ③短/中/长期可执行建议。只写散文,不要 JSON。\n\n"
)


def generate_insight_streamed(
    body: str, *, client, model,
    emit: Callable[[str, dict], None] | None = None,
    agent_id: str = "writer", step: str = "drafting",
) -> ReportInsight:
    """insight 两步化(spec §5.6,Spike H GO):Step1 stream_chat 出三段自由文本草稿,逐 delta
    emit chunk 供前端报告台 typing;Step2 generate_insight 把草稿抽成结构化 ReportInsight(契约不破)。
    emit=None → 直接一次性 generate_insight(body)(tests/CLI,无 typing)。
    stream 或抽取抛错(Exception)→ 回落一次性 generate_insight(body):数据有保证,typing best-effort。
    RunAborted(BaseException)不在此捕获,取消信号照常上抛。"""
    if emit is None:
        return generate_insight(body, client=client, model=model)
    try:
        draft = stream_chat([{"role": "user", "content": _INSIGHT_DRAFT_PROMPT + body}],
                            client=client, model=model, emit=emit, agent_id=agent_id, step=step)
        if not draft.strip():
            raise ValueError("empty draft")
        return generate_insight(draft, client=client, model=model)
    except Exception:  # noqa: BLE001 — stream/抽取失败回落一次性,数据真;RunAborted 是 BaseException 不入此分支
        return generate_insight(body, client=client, model=model)
```

> **回落 reconcile 契约(codex [P2] #6):** 回落前可能已 emit 部分草稿 `chunk`,前端 typing 流里会留草稿文本。**结构化 insight 始终经 `save_insight` + REST 落定为权威**;前端在 `done`/拉 `GET /report`+`/insight` 时以 REST 结构化产物为准、覆盖 typing 草稿区(前端 reconcile = Plan C)。本期后端契约:草稿是 best-effort 展示,结构化产物是唯一权威,二者最终一致由 Plan C 收口。

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py -v`
Expected: 3 新测试 passed + 既有不破。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/agents/writer.py tests/test_writer_agent.py
git commit -m "feat(writer): generate_insight_streamed two-step (stream draft -> structured), fallback to one-shot (Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 2: `write_report_with_insight` 透传 emit + write_node 接线

**Files:**
- Modify: `rivalradar/agents/writer.py`
- Modify: `rivalradar/graph/nodes.py`(`write_node`)
- Test: `tests/test_graph_nodes.py`

- [ ] **Step 1: 写失败测试(write_node 走两步,真 run 路径 emit chunk)**

追加到 `tests/test_graph_nodes.py`(沿用该文件 `repo`/`make_write_node`/`ReportInsight` 既有 import;若无 `_StreamClient` 复用 Task 1 的同款,或在本文件定义同款 fake):

```python
def test_write_node_streams_insight_chunks(conn):
    import json
    from types import SimpleNamespace
    from rivalradar.graph.nodes import make_write_node

    class _STS:
        def create(self, **kw):
            if kw.get("stream"):
                return (SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=c))])
                        for c in ["草", "稿"])
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(
                    {"market_context": "m", "differentiation_thesis": "d", "actionable_takeaway": "a"})))]))],
                usage=SimpleNamespace(total_tokens=10))
    client = SimpleNamespace(chat=SimpleNamespace(completions=_STS()))

    repo.create_run(conn, "rw1", ["Notion"], ["pricing"])
    node = make_write_node(conn=conn, client=client, model="m", as_of="2026-06-07")
    chunks = []
    def emit(ev_type, data):
        if ev_type == "chunk":
            chunks.append(data["delta"])
    cfg = {"configurable": {"thread_id": "rw1", "emit": emit}}
    out = node({"analysis": {"competitors": [], "comparison": []}, "evidence": []}, cfg)
    assert chunks == ["草", "稿"]                          # write_node 真 run 路径走两步流式
    assert out["insight"]["market_context"] == "m"        # 结构化产物落库契约不破
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_graph_nodes.py::test_write_node_streams_insight_chunks -v`
Expected: FAIL(无 chunk:write_node 现走一次性 `write_report_with_insight` 不 emit chunk)。

- [ ] **Step 3: `write_report_with_insight` 加 `emit` 参数(`writer.py`)**

把 `write_report_with_insight`(行 239-257)改为:

```python
def write_report_with_insight(
    analysis: CompetitorAnalysis, evidence: list[Evidence], *,
    as_of: str, client, model,
    emit: Callable[[str, dict], None] | None = None,
) -> tuple[str, ReportInsight]:
    """确定性正文 + insight。emit 提供时 insight 走两步化流式(§5.6),否则一次性。"""
    body = render_body(analysis, evidence, as_of=as_of)
    insight = generate_insight_streamed(body, client=client, model=model, emit=emit)
    return stitch_report(insight, body), insight
```

(注:`generate_insight_streamed(emit=None)` 内部即一次性,故 emit 缺省时行为与改造前完全一致,向后兼容。)

- [ ] **Step 4: `write_node` 传 emit(`nodes.py`)**

把 `write_node`(nodes.py 行 269-270)的调用改为传 emit:

```python
        report, insight = write_report_with_insight(
            analysis, evidence, as_of=as_of, client=_run_client(client, config), model=model,
            emit=emit)
```

(`emit` 已在 `write_node` 行 261 由 `_get_emit(config)` 取得;step="drafting" 占位事件在行 265-268 已先发,接住 Spike H 的 TTFB。)

- [ ] **Step 5: 修既有 write_node stub 测试(签名加 emit)**

既有 `test_write_node_renders_and_persists`(`tests/test_graph_nodes.py` 约行 265)用 `monkeypatch.setattr(nodes_mod, "write_report_with_insight", lambda analysis, evidence, *, as_of, client, model: (...))` 桩掉。write_node 现在传 `emit=...`,stub 缺 emit 形参会 TypeError。把 stub 的 lambda 改为接受 emit:

```python
    monkeypatch.setattr(
        nodes_mod, "write_report_with_insight",
        lambda analysis, evidence, *, as_of, client, model, emit=None: (
            "# 竞品分析报告\nX",
            ReportInsight(market_context="m", differentiation_thesis="d",
                          actionable_takeaway="a")))
```

- [ ] **Step 6: 跑测试确认 PASS + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_graph_nodes.py tests/test_writer_agent.py -v`
Expected: 全 passed。
Run: `.venv/bin/python -m pytest`
Expected: 全绿(新增 4 测)。

- [ ] **Step 7: Commit**

```bash
git add rivalradar/agents/writer.py rivalradar/graph/nodes.py tests/test_graph_nodes.py
git commit -m "feat(write): write_node streams insight draft via two-step (emit threaded), fallback intact (Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Epic B — support_verdict 真算三级 + 回写(§5.5/§7.2,反幻觉核心)

> **核心设计(写死,codex [P1] 应对):** 三级 verdict **回写到 curated 的 cell/decision 字段**(随 `save_analysis`/`save_decisions` 落库)→ `curate_analysis`/`curate_decisions` 保持 `(curated, dropped)` 二元组签名 → **nodes.py:316/326/434 二元解包零破坏**。unsupported 仍丢弃(策展人不回退);partial 保留+标黄;判定挂 cell/decision 级,**不挂 ref**。
>
> **不变量(codex [P1] #1 精确化):** 生产质检路径是 **`qc_node`**,它走 `curate_analysis`(Task 5 后内部用 `_judge_comparison_verdicts`,**不经 `check_entailment`**)+ 确定性闸(traceability/ontology/coverage)→ `decide_verdict`。三级 verdict 在 qc_node **只回写 cell + 进 verdict_recheck 事件,绝不进 `qc_result.issues`** → 不影响路由。**partial 永不成为任何 issue**(Task 6:`check_entailment` 只把 `unsupported` 映射为 hallucination issue)→ partial 在任何路径都不触发 retry_analyze。遗留的 `qc.check()`(qc.py:432,经 check_entailment→decide_verdict)**无生产节点调用**(qc_node 不调它);其 unsupported→issue→retry 是改造前既有行为,非本 Plan 引入的回退。Task 5 加测试锁死「qc_node 遇 partial cell 不产 retry_analyze」。

### Task 3: `ComparisonCell` / `Decision` 加 cell/decision 级 `support_verdict`

**Files:**
- Modify: `rivalradar/schema/models.py`
- Test: `tests/test_doubao_schema.py`(或 `tests/test_models.py`,沿用项目放 model 测试的文件)

- [ ] **Step 1: 写失败测试(cell/decision 有 support_verdict 字段,默认 supported)**

追加到 `tests/test_doubao_schema.py`(确认顶部 `from rivalradar.schema.models import ComparisonCell, Decision`;Decision 必填字段见下方构造):

```python
def test_comparison_cell_has_support_verdict_default_supported():
    from rivalradar.schema.models import ComparisonCell
    c = ComparisonCell(competitor="Notion", value_type="enum", value="v")
    assert c.support_verdict == "supported"
    c2 = ComparisonCell(competitor="Notion", value_type="enum", value="v", support_verdict="partial")
    assert c2.support_verdict == "partial"


def test_decision_has_support_verdict_default_supported():
    from rivalradar.schema.models import Decision
    d = Decision(stance="建议采用", action="A", horizon="短期", risk_reversibility="可逆",
                 risk_cost="低", why="w")
    assert d.support_verdict == "supported"
```

> 真实 Literal(models.py:148-151,codex [P2] #7 已核):`Stance=["建议采用","需要警惕","持续观察"]`、`Horizon=["短期","中期","长期"]`、`Reversibility=["可逆","不可逆"]`、`RiskCost=["低","中","高"]`。`watch` 仅 stance=`"持续观察"`(observe)时必填,这里用 `"建议采用"` 规避。

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_doubao_schema.py::test_comparison_cell_has_support_verdict_default_supported -v`
Expected: FAIL(`'ComparisonCell' object has no attribute 'support_verdict'`)。

- [ ] **Step 3: 加字段(`models.py`)**

`ComparisonCell`(行 114-120)加字段(放 `evidence_refs` 之后):

```python
class ComparisonCell(BaseModel):
    """类型化对比值,避免鸡同鸭比(spec §6 / Codex #3)。value 一律存字符串,由 value_type 决定解读。"""

    competitor: str
    value_type: ValueType
    value: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    # cell 级三色信任信号(spec §5.5):由 QC 蕴含三级判定回写;分析阶段默认 supported,
    # 真值在 qc curate 后落定。ref 级 support_verdict 不作信任信号(LLM 自报不可信)。
    support_verdict: SupportVerdict = "supported"
```

`Decision`(行 166-176)加字段(放 `watch` 之前或之后,在 `evidence_refs` 之后):

```python
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    # decision 级三色(spec §5.5):由 QC curate_decisions 蕴含三级回写。
    support_verdict: SupportVerdict = "supported"
    watch: Optional[Watch] = None
```

(`SupportVerdict` 已在 `models.py:8` 定义为 `Literal["supported","partial","unsupported"]`,无需新增。)

- [ ] **Step 4: 跑测试确认 PASS + 排查 model_dump 精确比对回归**

Run: `.venv/bin/python -m pytest tests/test_doubao_schema.py -v`
Expected: 2 新 passed。
Run: `.venv/bin/python -m pytest`
Expected: 全绿。**若有测试因 `ComparisonCell`/`Decision` 的 `model_dump()` 精确 dict 相等断言而失败**(新增字段改变 dump 输出),把那些断言的期望 dict 补上 `"support_verdict": "supported"`(意图不变,仅随新字段对齐)。逐个修到绿。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/schema/models.py tests/test_doubao_schema.py
git commit -m "feat(models): cell/decision-level support_verdict field (Plan B, spec 7.2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 4: `EntailmentVerdict` 升三级 + `_judge_comparison_verdicts`

**Files:**
- Modify: `rivalradar/agents/qc.py`
- Test: `tests/test_qc_agent.py`

- [ ] **Step 1: 写失败测试(三级 verdict + 每 cell 判定 map)**

追加到 `tests/test_qc_agent.py`(沿用该文件 `_FakeClient`/`_analysis_with_cell`/`_ev` helper;`from rivalradar.agents.qc import EntailmentVerdict, _judge_comparison_verdicts`):

```python
def test_entailment_verdict_is_three_level():
    from rivalradar.agents.qc import EntailmentVerdict
    v = EntailmentVerdict(verdict="partial", reason="单一来源")
    assert v.verdict == "partial"
    assert EntailmentVerdict().verdict == "supported"   # 默认 supported


def test_judge_comparison_verdicts_returns_per_cell_three_level():
    import json
    from rivalradar.agents.qc import _judge_comparison_verdicts
    analysis = _analysis_with_cell(dim="pricing")        # 1 竞品 Notion / pricing / 挂 e1
    client = _FakeClient([json.dumps({"verdict": "partial", "reason": "旁证"})])
    verdicts = _judge_comparison_verdicts(
        analysis, [_ev("e1", "pricing")], dimensions=("pricing",),
        client=client, model="m")
    assert verdicts[("Notion", "pricing")].verdict == "partial"
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py::test_entailment_verdict_is_three_level -v`
Expected: FAIL(`EntailmentVerdict` 无 `verdict` 字段 / `_judge_comparison_verdicts` 不存在)。

- [ ] **Step 3: 升级 `EntailmentVerdict` + 加 `_judge_comparison_verdicts`(`qc.py`)**

顶部 import 区把 `SupportVerdict` 加入 models import:

```python
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, Decision, Evidence, EvidenceRef,
    QCIssue, QCResult, QCVerdict, SupportVerdict,
)
```

把 `EntailmentVerdict`(行 148-150)改为:

```python
class EntailmentVerdict(BaseModel):
    verdict: SupportVerdict = "supported"
    reason: str = ""
```

在 `check_entailment` 之前(或之后,模块级)加三级 prompt 常量 + 判定 map 函数:

```python
_ENTAIL_PROMPT = (
    "判断下列证据对结论的支撑程度,三选一:\n"
    "- supported:证据直接、充分支撑结论。\n"
    "- partial:证据相关但不充分(单一来源/旁证/只支撑部分)。\n"
    "- unsupported:证据不支撑或与结论无关。\n\n"
    "结论:{text}\n\n证据:\n{quotes}"
)


def _judge_comparison_verdicts(
    analysis: CompetitorAnalysis, evidence: list[Evidence],
    *, dimensions: tuple[str, ...] | None = None, comparison_only: bool = True,
    on_progress: Callable[[str], None] | None = None, client, model,
) -> dict[tuple[str, str], EntailmentVerdict]:
    """对每个有引用的 comparison cell 判三级蕴含,返回 {(competitor, dimension): EntailmentVerdict}。
    每 cell 一次 LLM 调用(合并该 cell 全部 refs 一起判,不逐 ref),并行(GIL 下不同 key 写 dict 安全)。"""
    idx = {e.id: e for e in evidence}
    conclusions = [
        (comp, dim, text, refs)
        for comp, dim, text, refs in _iter_conclusions(
            analysis, dimensions=dimensions, comparison_only=comparison_only)
        if refs
    ]
    if not conclusions:
        return {}

    def _judge(item: tuple[str, str, str, list[EvidenceRef]]) -> tuple[tuple[str, str], EntailmentVerdict]:
        comp, dim, text, refs = item
        quotes = []
        for r in refs:
            src = idx[r.evidence_id].content if r.evidence_id in idx else ""
            quotes.append(f"- 引语:{r.quote}\n  证据原文:{src[:600]}")
        msgs = [{"role": "user", "content": _ENTAIL_PROMPT.format(text=text, quotes="\n".join(quotes))}]
        v = structured_call(EntailmentVerdict, msgs, client=client, model=model)
        if on_progress is not None:
            on_progress(f"质检校验 {comp}·{dim}")
        return (comp, dim), v

    with cf.ThreadPoolExecutor(max_workers=min(_MAX_ENTAIL_WORKERS, len(conclusions))) as ex:
        results = list(ex.map(_judge, conclusions))
    return dict(results)
```

> 注:`_iter_conclusions` 是 qc.py 现有 helper(`check_entailment` 已在用);保持同样调用形式。

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py::test_entailment_verdict_is_three_level tests/test_qc_agent.py::test_judge_comparison_verdicts_returns_per_cell_three_level -v`
Expected: 2 passed。

- [ ] **Step 5: 迁移既有 `EntailmentVerdict` payload 断言(schema 改了)**

`EntailmentVerdict` 从 `{supported: bool}` 改为 `{verdict: 三级}`,所有 mock payload 与断言要迁移。在 `tests/test_qc_agent.py` 里把所有 `json.dumps({"supported": True, ...})` → `json.dumps({"verdict": "supported", ...})`、`json.dumps({"supported": False, ...})` → `json.dumps({"verdict": "unsupported", ...})`。具体跑一次定位:

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
对每个 FAIL,把该用例里的 `"supported": true/false` payload 改成对应 `"verdict": "supported"/"unsupported"`(false→unsupported,因旧 false=不支撑=丢弃);断言「unsupported → 产 issue / 被丢」语义保持。改到全绿。**注意:此步只迁移 payload 键名 + 对应断言,不改测试意图。** check_entailment / curate 的行为改动在 Task 5 验证。

- [ ] **Step 6: Commit**

```bash
git add rivalradar/agents/qc.py tests/test_qc_agent.py
git commit -m "feat(qc): EntailmentVerdict three-level + _judge_comparison_verdicts per-cell map (Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 5: `curate_analysis` 回写 cell 级 verdict + 丢 unsupported(测病因不变量)

**Files:**
- Modify: `rivalradar/agents/qc.py`
- Test: `tests/test_qc_agent.py`

- [ ] **Step 1: 写失败测试(病因不变量:回写发生 / partial 保留标黄 / unsupported 丢 / 二元组签名不破)**

追加到 `tests/test_qc_agent.py`(用 monkeypatch 桩 `_judge_comparison_verdicts` 控制 verdict,避免真打):

```python
def test_curate_writes_back_partial_and_keeps_cell(monkeypatch):
    """病因不变量:partial cell 被保留且 cell.support_verdict 被回写 'partial'(不是丢)。"""
    import rivalradar.agents.qc as qcmod
    analysis = _analysis_with_cell(dim="pricing")
    monkeypatch.setattr(qcmod, "_judge_comparison_verdicts",
                        lambda *a, **k: {("Notion", "pricing"): qcmod.EntailmentVerdict(verdict="partial")})
    curated, dropped = qcmod.curate_analysis(
        analysis, [_ev("e1", "pricing")], dimensions=("pricing",), client=None, model="m")
    cell = curated.comparison[0].cells[0]
    assert cell.support_verdict == "partial"     # 回写发生(测病因:回写,不是断言某颜色)
    assert dropped == []                          # partial 不丢


def test_curate_drops_unsupported_and_records(monkeypatch):
    import rivalradar.agents.qc as qcmod
    analysis = _analysis_with_cell(dim="pricing")
    monkeypatch.setattr(qcmod, "_judge_comparison_verdicts",
                        lambda *a, **k: {("Notion", "pricing"): qcmod.EntailmentVerdict(verdict="unsupported")})
    curated, dropped = qcmod.curate_analysis(
        analysis, [_ev("e1", "pricing")], dimensions=("pricing",), client=None, model="m")
    assert curated.comparison == [] or curated.comparison[0].cells == []   # unsupported 被剔
    assert {"competitor": "Notion", "dimension": "pricing"} in dropped     # 剔除清单结构化记录(codex #5)


def test_curate_returns_two_tuple_unchanged_signature(monkeypatch):
    """病因不变量:curate_analysis 仍返二元组(verdict 骑在 cell 上,不改签名 → nodes.py 解包不破)。"""
    import rivalradar.agents.qc as qcmod
    monkeypatch.setattr(qcmod, "_judge_comparison_verdicts",
                        lambda *a, **k: {("Notion", "pricing"): qcmod.EntailmentVerdict(verdict="supported")})
    res = qcmod.curate_analysis(_analysis_with_cell(dim="pricing"), [_ev("e1", "pricing")],
                                dimensions=("pricing",), client=None, model="m")
    curated, dropped = res                        # 二元解包不抛
    assert isinstance(dropped, list)
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py::test_curate_writes_back_partial_and_keeps_cell -v`
Expected: FAIL(`cell.support_verdict` 仍是默认,未回写 partial)。

- [ ] **Step 3: 重写 `curate_analysis` 用三级判定 + 回写(`qc.py`)**

把 `curate_analysis`(行 208-245)的 Phase 2/3 改为(保留 Phase 1 机械门 + 二元组返回;`from rivalradar.schema.models import ComparisonRow` 若 qc.py 未 import 则补):

```python
def curate_analysis(
    analysis: CompetitorAnalysis, evidence: list[Evidence],
    *, dimensions: tuple[str, ...] | None = None,
    on_progress: Callable[[str], None] | None = None, client, model,
) -> tuple[CompetitorAnalysis, list[str]]:
    """策展对比矩阵:机械门(无引用/悬空引用)+ 三级蕴含判定(LLM)。
    unsupported → 丢弃(策展人,矩阵显「—」);supported/partial → 保留并把三级 verdict
    回写到 cell.support_verdict(随 save_analysis 落库)。返回 (curated, dropped),
    dropped 为结构化 list[dict{"competitor","dimension"}](codex #5,非拼接字符串)。
    三级判定**不进** qc_result.issues(守策展人路由,§5.5)。"""
    # Phase 1 机械门(_curate_mechanical 也产结构化 dropped,见下)
    mech_analysis, dropped = _curate_mechanical(analysis, evidence, dimensions)

    # Phase 2 三级蕴含判定(per-cell verdict map)
    verdicts = _judge_comparison_verdicts(
        mech_analysis, evidence, dimensions=dimensions, comparison_only=True,
        on_progress=on_progress, client=client, model=model)

    # Phase 3 组装:unsupported 丢,其余回写 verdict
    final_rows: list[ComparisonRow] = []
    for row in mech_analysis.comparison:
        in_scope = dimensions is None or row.dimension in dimensions
        if not in_scope:
            final_rows.append(row)
            continue
        kept = []
        for cell in row.cells:
            v = verdicts.get((cell.competitor, row.dimension))
            verdict = v.verdict if v is not None else "supported"  # 无判定(已过机械门)→ 默认 supported
            if verdict == "unsupported":
                dropped.append({"competitor": cell.competitor, "dimension": row.dimension})
                continue
            kept.append(cell.model_copy(update={"support_verdict": verdict}))
        if kept:
            final_rows.append(row.model_copy(update={"cells": kept}))
    curated = analysis.model_copy(update={"comparison": final_rows})
    return curated, dropped
```

**同步改 `_curate_mechanical`(codex #5):** 它现在 `dropped.append(f"{cell.competitor}/{row.dimension}")`(qc.py:~266)。改为结构化:`dropped.append({"competitor": cell.competitor, "dimension": row.dimension})`,使 `dropped` 全程为 `list[dict]`(qc_node 的 `len(dropped)` / `if dropped:` / trace 计数均兼容 list[dict];fallback 路径 `_curate_mechanical` 直接调也得结构化 dropped)。

- [ ] **Step 4: 跑测试确认 PASS + 既有 curate 测试**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: 新 3 测 + 既有 curate 测试全 passed。迁移两类既有断言(意图不变):
- 既有桩 `check_entailment` 的 → 改桩 `_judge_comparison_verdicts` 返回对应 verdict map。
- 既有断言 `dropped` 含拼接串(如 `"Notion/pricing" in dropped` 或悬空 ref 用例 `test_curate_drops_dangling_ref_cell_without_llm`)→ 改为结构化 `{"competitor": ..., "dimension": ...} in dropped`(因 `_curate_mechanical` + `curate_analysis` 现产 list[dict])。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/agents/qc.py tests/test_qc_agent.py
git commit -m "feat(qc): curate_analysis writes back 3-level support_verdict to cells, drops unsupported, 2-tuple intact (Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 6: `check_entailment` / `check_decision_entailment` / `curate_decisions` 收口三级

**Files:**
- Modify: `rivalradar/agents/qc.py`
- Test: `tests/test_qc_agent.py`

- [ ] **Step 1: 写失败测试(check_entailment 只对 unsupported 产 issue;partial 不产;curate_decisions 回写 decision verdict)**

追加到 `tests/test_qc_agent.py`:

```python
def test_check_entailment_partial_not_an_issue(monkeypatch):
    """partial 不再算 hallucination issue(只 unsupported 算);守策展人 + 不误触 retry。"""
    import rivalradar.agents.qc as qcmod
    monkeypatch.setattr(qcmod, "_judge_comparison_verdicts",
                        lambda *a, **k: {("Notion", "pricing"): qcmod.EntailmentVerdict(verdict="partial")})
    issues = qcmod.check_entailment(_analysis_with_cell(dim="pricing"), [_ev("e1", "pricing")],
                                    dimensions=("pricing",), comparison_only=True, client=None, model="m")
    assert issues == []                              # partial 不产 issue


def test_check_entailment_unsupported_is_issue(monkeypatch):
    import rivalradar.agents.qc as qcmod
    monkeypatch.setattr(qcmod, "_judge_comparison_verdicts",
                        lambda *a, **k: {("Notion", "pricing"): qcmod.EntailmentVerdict(verdict="unsupported")})
    issues = qcmod.check_entailment(_analysis_with_cell(dim="pricing"), [_ev("e1", "pricing")],
                                    dimensions=("pricing",), comparison_only=True, client=None, model="m")
    assert len(issues) == 1 and issues[0].problem_type == "hallucination"


def test_curate_decisions_writes_back_verdict(monkeypatch):
    import json
    import rivalradar.agents.qc as qcmod
    from rivalradar.schema.models import Decision, EvidenceRef
    d = Decision(stance="建议采用", action="A", horizon="短期", risk_reversibility="可逆",
                 risk_cost="低", why="w", evidence_refs=[EvidenceRef(evidence_id="e1", quote="q")])
    client = _FakeClient([json.dumps({"verdict": "partial", "reason": "旁证"})])
    kept, dropped = qcmod.curate_decisions([d], [_ev("e1", "pricing")], client=client, model="m")
    assert len(kept) == 1 and kept[0].support_verdict == "partial"
    assert dropped == []
```

> Decision Literal 真值(models.py:148-151):`Stance=建议采用/需要警惕/持续观察`、`Horizon=短期/中期/长期`、`Reversibility=可逆/不可逆`、`RiskCost=低/中/高`。

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py::test_check_entailment_partial_not_an_issue -v`
Expected: FAIL(check_entailment 现用 `verdict.supported` AttributeError / 行为不符)。

- [ ] **Step 3: 改 `check_entailment` / `check_decision_entailment` / `curate_decisions` 用三级(`qc.py`)**

`check_entailment`(行 153-200)改为基于 `_judge_comparison_verdicts` 派生 issue(只 unsupported → hallucination):

```python
def check_entailment(
    analysis: CompetitorAnalysis, evidence: list[Evidence],
    *, dimensions: tuple[str, ...] | None = None, comparison_only: bool = False,
    on_progress: Callable[[str], None] | None = None, client, model,
) -> list[QCIssue]:
    """LLM 三级蕴含 → 仅 unsupported 产 hallucination issue(partial 容忍,守策展人)。每 cell 一次调用。"""
    verdicts = _judge_comparison_verdicts(
        analysis, evidence, dimensions=dimensions, comparison_only=comparison_only,
        on_progress=on_progress, client=client, model=model)
    return [
        QCIssue(competitor=comp, dimension=dim, problem_type="hallucination",
                detail=f"证据不支撑结论:{v.reason}")
        for (comp, dim), v in verdicts.items() if v.verdict == "unsupported"
    ]
```

`check_decision_entailment`(行 297-337)把 `if not verdict.supported:`(行 322)改为三级:

```python
        verdict = structured_call(EntailmentVerdict, msgs, client=client, model=model)
        calls += 1
        if verdict.verdict == "unsupported":
            issues.append(QCIssue(competitor="*", dimension="decision",
                                  problem_type="hallucination",
                                  detail=f"证据不支撑决策({d.action}):{verdict.reason}"))
```

`curate_decisions`(行 340-385)把 `_supported`(返 `.supported`)改为返回 verdict,并回写到 decision:

```python
def curate_decisions(
    decisions: list[Decision], evidence: list[Evidence], *, client, model,
    max_calls: int = 8,
) -> tuple[list[Decision], list[str]]:
    """策展决策:unsupported 丢弃,supported/partial 保留并回写 decision.support_verdict。
    返回 (kept, dropped),dropped 为结构化 list[dict{"action"}](codex #5,replay 安全)。"""
    idx = {e.id: e for e in evidence}
    dropped: list[dict] = []
    candidates: list[Decision] = []
    for d in decisions:
        if not d.evidence_refs or any(r.evidence_id not in idx for r in d.evidence_refs):
            dropped.append({"action": d.action})
        else:
            candidates.append(d)
    to_judge = candidates[:max_calls]

    def _verdict(d: Decision) -> EntailmentVerdict:
        quotes = []
        for r in d.evidence_refs:
            src = idx[r.evidence_id].content if r.evidence_id in idx else ""
            quotes.append(f"- 引语:{r.quote}\n  证据原文:{src[:600]}")
        msgs = [{"role": "user", "content":
                 "判断下列证据对该决策建议的支撑程度,三选一:supported(直接充分支撑行动与理由)/"
                 "partial(相关但不充分)/unsupported(不支撑或无关)。\n\n"
                 f"决策(行动):{d.action}\n理由:{d.why}\n\n证据:\n" + "\n".join(quotes)}]
        return structured_call(EntailmentVerdict, msgs, client=client, model=model)

    verdicts: list[EntailmentVerdict] = []
    if to_judge:
        with cf.ThreadPoolExecutor(max_workers=min(_MAX_ENTAIL_WORKERS, len(to_judge))) as ex:
            verdicts = list(ex.map(_verdict, to_judge))

    kept: list[Decision] = []
    for j, d in enumerate(candidates):
        if j >= len(verdicts):
            kept.append(d.model_copy(update={"support_verdict": "supported"}))  # cost guard 超额:保留默认
            continue
        v = verdicts[j].verdict
        if v == "unsupported":
            dropped.append({"action": d.action})
        else:
            kept.append(d.model_copy(update={"support_verdict": v}))
    return kept, dropped
```

> 既有 `test_curate_decisions_drops_ungrounded` 若断言 `d.action in dropped`(字符串)→ 改 `{"action": d.action} in dropped`(结构化,意图不变)。

- [ ] **Step 4: 跑测试确认 PASS + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: 全 passed(含既有 decision 测试迁移后)。
Run: `.venv/bin/python -m pytest`
Expected: 全绿。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/agents/qc.py tests/test_qc_agent.py
git commit -m "feat(qc): three-level entailment for check_entailment/decisions/curate_decisions, write back decision verdict (Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Epic C — 逐格 cell_row emit(§5.3,矩阵边算边填)

### Task 7: `build_comparison` / `analyze` 加 `on_cell_row` 回调

**Files:**
- Modify: `rivalradar/agents/analyst.py`
- Test: `tests/test_analyst_agent.py`

- [ ] **Step 1: 写失败测试(逐维回调:成功维 ok + 失败维 failed)**

追加到 `tests/test_analyst_agent.py`(沿用 `_FakeClient` dict 模式 + `_ev`):

```python
def test_build_comparison_calls_on_cell_row_per_dimension(monkeypatch):
    import threading
    from rivalradar.agents import analyst as amod
    from rivalradar.schema.models import ComparisonRow, ComparisonCell, CompetitorProfile, PricingModel, SWOT

    seen = []
    lock = threading.Lock()
    def on_cell_row(dimension, row, status):
        with lock:
            seen.append((dimension, status, None if row is None else len(row.cells)))

    def fake_one(dimension, names, evidence, *, client, model):
        if dimension == "pricing":
            return ComparisonRow(dimension="pricing", cells=[
                ComparisonCell(competitor="Notion", value_type="enum", value="v")])
        raise ValueError("boom")     # core_workflows 维失败

    monkeypatch.setattr(amod, "_compare_one_dimension", fake_one)
    profiles = [CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())]
    sink = []
    amod.build_comparison(profiles, [_ev("e1", "Notion", "pricing")],
                          dimensions=("pricing", "core_workflows"),
                          degraded_sink=sink, on_cell_row=on_cell_row, client=None, model="m")
    by_dim = {d: (s, n) for d, s, n in seen}
    assert by_dim["pricing"] == ("ok", 1)            # 成功维带 cells
    assert by_dim["core_workflows"][0] == "failed"   # 失败维标 failed(乱序到达,按 dim 落位)
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py::test_build_comparison_calls_on_cell_row_per_dimension -v`
Expected: FAIL(`build_comparison() got an unexpected keyword argument 'on_cell_row'`)。

- [ ] **Step 3: 给 `build_comparison` 加 `on_cell_row`(`analyst.py`)**

`build_comparison`(行 223-267)签名加参数(放 `on_progress` 之后)+ `work()` 内回调:

```python
def build_comparison(
    profiles: list[CompetitorProfile], evidence: list[Evidence],
    *, dimensions: tuple[str, ...] = CONTROLLED_DIMENSIONS,
    degraded_sink: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_cell_row: Callable[[str, "ComparisonRow | None", str], None] | None = None,
    client, model,
) -> list[ComparisonRow]:
    """并行逐维对比。on_cell_row(dimension, row, status):每维算完报一次(worker 线程,乱序到达)。
    成功有 cells → status="ok";单维抛错 → status="failed";无证据(row None,无异常)→ status="empty"
    (codex #3:前端据此区分 pending / 已知空 / 失败,不会把无证据维误当还在跑)。"""
    names = ", ".join(p.name for p in profiles)
    results: dict[str, ComparisonRow] = {}

    def work(dimension: str) -> None:
        try:
            row = _compare_one_dimension(dimension, names, evidence, client=client, model=model)
            if row is not None:
                results[dimension] = row  # 不同 key 并发写,CPython 原子,无需锁
                if on_cell_row is not None:
                    on_cell_row(dimension, row, "ok")
            elif on_cell_row is not None:
                on_cell_row(dimension, None, "empty")   # 无证据维:已知空,非 pending(codex #3)
        except RunAborted:
            raise
        except Exception as e:
            logger.warning("build_comparison[%s] 维度对比降级(%s,跳过该维)",
                           dimension, type(e).__name__)
            if degraded_sink is not None:
                degraded_sink.append(f"comparison.{dimension}")
            if on_cell_row is not None:
                on_cell_row(dimension, None, "failed")
        finally:
            if on_progress is not None:
                on_progress(f"对比·{_DIM_ZH.get(dimension, dimension)}")

    with cf.ThreadPoolExecutor(
        max_workers=min(_MAX_COMPARISON_WORKERS, len(dimensions) or 1)
    ) as ex:
        list(ex.map(work, dimensions))

    return [results[d] for d in dimensions if d in results]
```

`analyze`(行 270 顶层)签名加 `on_cell_row` 并透传给 `build_comparison`。读 `analyst.py` 的 `analyze` 函数体,把它内部 `build_comparison(...)` 调用补 `on_cell_row=on_cell_row`,签名加(放 `on_progress` 之后):

```python
    on_cell_row: Callable[[str, "ComparisonRow | None", str], None] | None = None,
```

- [ ] **Step 4: 跑测试确认 PASS + 既有 analyst 测试**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py -v`
Expected: 新测 passed + 既有(`test_build_comparison_returns_rows` / `test_build_comparison_degrades_single_dimension_into_sink`)不破(on_cell_row 默认 None = no-op)。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/agents/analyst.py tests/test_analyst_agent.py
git commit -m "feat(analyst): build_comparison/analyze on_cell_row callback per dimension (ok/failed) (Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 8: `analyze_node` emit `cell_row` + `SSECellRowData` schema

**Files:**
- Modify: `rivalradar/graph/nodes.py`(`analyze_node`)
- Modify: `rivalradar/api/schemas.py`
- Test: `tests/test_graph_nodes.py`、`tests/test_sse_schemas.py`

- [ ] **Step 1: 写失败测试(analyze_node 逐维 emit cell_row + schema)**

追加到 `tests/test_sse_schemas.py`:

```python
def test_sse_cell_row_schema():
    from rivalradar.api.schemas import SSECellRowData
    d = SSECellRowData(dimension="pricing", status="ok", cells=[
        {"competitor": "Notion", "value_type": "enum", "value": "v",
         "evidence_refs": [{"evidence_id": "ev_1", "quote": "q"}]}], ts="t")
    assert d.dimension == "pricing" and d.status == "ok" and d.cells[0].competitor == "Notion"
```

追加到 `tests/test_graph_nodes.py`(用 dict 模式 `_FakeClient` 让 analyze 真跑 build_comparison;或 monkeypatch `analyze` 走最小路径——优先 monkeypatch `nodes` 模块的 `analyze` 让它调 on_cell_row):

```python
def test_analyze_node_emits_cell_row(conn, monkeypatch):
    import rivalradar.graph.nodes as nodes_mod
    from rivalradar.schema.models import CompetitorAnalysis, ComparisonRow, ComparisonCell

    def fake_analyze(evidence, competitors, *, dimensions, degraded_sink, on_progress,
                     on_cell_row=None, client, model):
        if on_cell_row is not None:
            on_cell_row("pricing", ComparisonRow(dimension="pricing", cells=[
                ComparisonCell(competitor="Notion", value_type="enum", value="v")]), "ok")
        return CompetitorAnalysis(competitors=[], comparison=[
            ComparisonRow(dimension="pricing", cells=[
                ComparisonCell(competitor="Notion", value_type="enum", value="v")])])

    monkeypatch.setattr(nodes_mod, "analyze", fake_analyze)
    repo.create_run(conn, "ra1", ["Notion"], ["pricing"])
    node = nodes_mod.make_analyze_node(conn=conn, client=None, model="m")
    events = []
    def emit(ev_type, data):
        events.append((ev_type, data))
    out = node({"evidence": [], "competitors": ["Notion"], "dimensions": ["pricing"]},
               {"configurable": {"thread_id": "ra1", "emit": emit}})
    cr = [d for t, d in events if t == "cell_row"]
    assert len(cr) == 1 and cr[0]["dimension"] == "pricing" and cr[0]["status"] == "ok"
    assert cr[0]["cells"][0]["competitor"] == "Notion"
```

> `make_analyze_node` 真实签名以 `nodes.py` 为准(读确认参数);`fake_analyze` 形参需与真实 `analyze` 调用点一致(含本 Plan 新加的 `on_cell_row`)。

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_sse_schemas.py::test_sse_cell_row_schema -v`
Expected: FAIL(`ImportError: SSECellRowData`)。

- [ ] **Step 3: 加 `SSECellRowData`(`api/schemas.py`)**

在 `SSEEvidenceDeltaData` 之后加:

```python
class SSECellRef(BaseModel):
    """cell_row 事件内的轻量 ref(只携 id + quote,信任信号在 verdict_recheck)。"""
    evidence_id: str
    quote: str


class SSECellRowCell(BaseModel):
    competitor: str
    value_type: str
    value: str
    evidence_refs: list[SSECellRef] = Field(default_factory=list)


class SSECellRowData(BaseModel):
    """cell_row event — analyze 逐维对比结果(spec §5.3,矩阵边算边填)。
    cell 不携可信 support_verdict(真三色在 qc verdict_recheck 回写)。
    status=ok(有 cells)| empty(无证据维,已知空非 pending)| failed(单维抽取抛错)。"""
    dimension: str
    status: str          # ok | empty | failed
    cells: list[SSECellRowCell] = Field(default_factory=list)
    ts: str
```

- [ ] **Step 4: `analyze_node` 接 `on_cell_row` → emit `cell_row`(`nodes.py`)**

在 `analyze_node`(行 190+)里 `emit = _get_emit(config)` 之后定义回调,并传给 `analyze` / `build_comparison`(reuse 路径与全量路径都传):

```python
        def on_cell_row(dimension, row, status):
            if emit is None:
                return
            cells = [] if row is None else [
                {"competitor": c.competitor, "value_type": c.value_type, "value": c.value,
                 "evidence_refs": [{"evidence_id": r.evidence_id, "quote": r.quote}
                                   for r in c.evidence_refs]}
                for c in row.cells]
            emit("cell_row", {"dimension": dimension, "status": status, "cells": cells})
```

并把 reuse 路径的 `build_comparison(...)`(行 214-216)与全量路径的 `analyze(...)`(行 224-226)调用各补 `on_cell_row=on_cell_row`:

```python
            comparison = build_comparison(profiles, evidence, dimensions=dims,
                                          degraded_sink=degraded_sink, on_progress=tick,
                                          on_cell_row=on_cell_row, client=rc_client, model=model)
```
```python
            analysis = analyze(evidence, state["competitors"], dimensions=dims,
                               degraded_sink=degraded_sink, on_progress=tick,
                               on_cell_row=on_cell_row, client=rc_client, model=model)
```

- [ ] **Step 5: 跑测试确认 PASS + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_sse_schemas.py tests/test_graph_nodes.py -v`
Expected: 全 passed。
Run: `.venv/bin/python -m pytest`
Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add rivalradar/graph/nodes.py rivalradar/api/schemas.py tests/test_sse_schemas.py tests/test_graph_nodes.py
git commit -m "feat(analyze): emit cell_row per dimension + SSECellRowData schema (Plan B, spec 5.3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Epic D — verdict_recheck 事件 + 剔除清单持久化(§5.5/§7.1/§7.3)

### Task 9: `curation_drops` 表 + repository CRUD

**Files:**
- Modify: `rivalradar/storage/db.py`(SCHEMA)
- Modify: `rivalradar/storage/repository.py`
- Test: `tests/test_curation_drops_repo.py`

- [ ] **Step 1: 写失败测试(表存在 + 批量写读)**

`tests/test_curation_drops_repo.py`:

```python
from rivalradar.storage.db import connect, init_db
from rivalradar.storage.repository import replace_curation_drops, list_curation_drops


def _conn():
    c = connect(":memory:"); init_db(c); return c


def test_curation_drops_structured_columns():
    conn = _conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(curation_drops)").fetchall()}
    assert {"run_id", "scope", "competitor", "dimension", "detail", "created_at"} <= cols
    replace_curation_drops(conn, "run1", "cell",
                           [{"competitor": "Notion", "dimension": "pricing"},
                            {"competitor": "Notion", "dimension": "deployment"}])
    replace_curation_drops(conn, "run1", "decision", [{"detail": "停止投入 X"}])
    rows = list_curation_drops(conn, "run1")
    assert len(rows) == 3
    cell = [r for r in rows if r["scope"] == "cell"]
    assert {(r["competitor"], r["dimension"]) for r in cell} == {("Notion", "pricing"), ("Notion", "deployment")}
    assert [r["detail"] for r in rows if r["scope"] == "decision"] == ["停止投入 X"]
    assert list_curation_drops(conn, "missing") == []


def test_curation_drops_replace_no_ghost_after_retry():
    """codex #2:多轮重试——后轮覆盖前轮(REPLACE per scope),deployment 证据补回后无幽灵剔除。"""
    conn = _conn()
    replace_curation_drops(conn, "run1", "cell",
                           [{"competitor": "Notion", "dimension": "pricing"},
                            {"competitor": "Notion", "dimension": "deployment"}])
    replace_curation_drops(conn, "run1", "decision", [{"detail": "停止投入 X"}])
    # 第二轮:deployment 补回,只剩 pricing 被剔
    replace_curation_drops(conn, "run1", "cell", [{"competitor": "Notion", "dimension": "pricing"}])
    rows = list_curation_drops(conn, "run1")
    cell = [r for r in rows if r["scope"] == "cell"]
    assert len(cell) == 1 and cell[0]["dimension"] == "pricing"   # deployment 幽灵已清
    assert any(r["scope"] == "decision" for r in rows)            # decision scope 不受 cell replace 影响
    # 空列表 = 清空该 scope
    replace_curation_drops(conn, "run1", "cell", [])
    assert [r for r in list_curation_drops(conn, "run1") if r["scope"] == "cell"] == []
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_curation_drops_repo.py -v`
Expected: FAIL(表不存在 / ImportError)。

- [ ] **Step 3: 加表(`db.py`)+ CRUD(`repository.py`)**

`db.py` 的 `SCHEMA` 串里(`queries` 表之后、`trace` 表之前)加:

```sql
-- 策展剔除清单(Plan B:support_verdict 真算后被丢弃的 cell/decision)。结构化列(codex #5,
-- 不拼接 label)供 replay/刷新还原矩阵「—」与 StatusBar 红○计数(spec §7.3);scope=cell|decision。
-- 写入用 REPLACE per (run_id, scope) 语义(codex #2:qc 多轮重试每轮覆盖,绝不留幽灵剔除)。
CREATE TABLE IF NOT EXISTS curation_drops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    scope       TEXT NOT NULL,
    competitor  TEXT NOT NULL DEFAULT '',
    dimension   TEXT NOT NULL DEFAULT '',
    detail      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
```

索引区加:

```sql
CREATE INDEX IF NOT EXISTS idx_curation_drops_run ON curation_drops(run_id);
```

`repository.py` 在 `list_queries` 之后加:

```python
# ---- curation_drops(Plan B:策展剔除清单,REPLACE per scope)----
def replace_curation_drops(conn: sqlite3.Connection, run_id: str, scope: str,
                           items: list[dict]) -> None:
    """替换某 run+scope 的策展剔除清单(codex #2:qc/decide 每轮调,先删后插,绝不 append →
    多轮重试后被补回的 cell/decision 不留幽灵)。items:cell → {"competitor","dimension"};
    decision → {"detail"}。空列表 = 清空该 scope。在 qc_node(cell)/decide_node(decision)主线程调。"""
    now = _now()
    conn.execute("DELETE FROM curation_drops WHERE run_id=? AND scope=?", (run_id, scope))
    if items:
        conn.executemany(
            "INSERT INTO curation_drops (run_id, scope, competitor, dimension, detail, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(run_id, scope, it.get("competitor", ""), it.get("dimension", ""),
              it.get("detail", ""), now) for it in items],
        )
    conn.commit()


def list_curation_drops(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT scope, competitor, dimension, detail, created_at FROM curation_drops "
        "WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `.venv/bin/python -m pytest tests/test_curation_drops_repo.py -v`
Expected: passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/storage/db.py rivalradar/storage/repository.py tests/test_curation_drops_repo.py
git commit -m "feat(db): curation_drops table + replace_curation_drops (structured, REPLACE per scope) (Plan B, spec 7.3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 10: `qc_node` emit `verdict_recheck` + 持久化 cell 剔除;`decide_node` 持久化 decision 剔除

**Files:**
- Modify: `rivalradar/graph/nodes.py`(`qc_node`、`decide_node`)
- Modify: `rivalradar/api/schemas.py`(`SSEVerdictRecheckData`)
- Test: `tests/test_graph_nodes.py`、`tests/test_sse_schemas.py`

- [ ] **Step 1: 写失败测试(verdict_recheck 事件 + cell 剔除落库 + schema)**

追加到 `tests/test_sse_schemas.py`:

```python
def test_sse_verdict_recheck_schema():
    from rivalradar.api.schemas import SSEVerdictRecheckData
    d = SSEVerdictRecheckData(
        cell_verdicts=[{"dimension": "pricing", "competitor": "Notion", "support_verdict": "partial"}],
        dropped=[{"competitor": "Notion", "dimension": "deployment"}],
        downgraded=[{"dimension": "pricing", "competitor": "Notion"}],
        summary={"supported": 2, "partial": 1, "dropped": 1}, ts="t")
    assert d.summary["dropped"] == 1 and d.cell_verdicts[0].support_verdict == "partial"
```

追加到 `tests/test_graph_nodes.py`(qc_node 测试:monkeypatch `qc.curate_analysis` 返回带 partial cell 的 curated + dropped,验证 emit verdict_recheck + curation_drops 落库):

```python
def test_qc_node_emits_verdict_recheck_and_persists_drops(conn, monkeypatch):
    import rivalradar.graph.nodes as nodes_mod
    from rivalradar.agents import qc as qcmod
    from rivalradar.schema.models import CompetitorAnalysis, ComparisonRow, ComparisonCell
    from rivalradar.storage.repository import create_run, list_curation_drops

    curated = CompetitorAnalysis(competitors=[], comparison=[
        ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="v", support_verdict="partial")])])
    monkeypatch.setattr(qcmod, "curate_analysis",
                        lambda *a, **k: (curated, [{"competitor": "Notion", "dimension": "deployment"}]))
    # 防真打:其余确定性门返空 issue
    monkeypatch.setattr(qcmod, "check_traceability", lambda *a, **k: [])
    monkeypatch.setattr(qcmod, "check_ontology", lambda *a, **k: [])
    monkeypatch.setattr(qcmod, "check_coverage", lambda *a, **k: [])

    create_run(conn, "rq1", ["Notion"], ["pricing"])
    node = nodes_mod.make_qc_node(conn=conn, client=None, model="m", as_of="2026-06-07")
    events = []
    state = {"analysis": {"competitors": [], "comparison": [
        {"dimension": "pricing", "cells": [
            {"competitor": "Notion", "value_type": "enum", "value": "v", "evidence_refs": []}]}]},
        "evidence": [], "competitors": ["Notion"], "dimensions": ["pricing"], "retry_count": 0}
    out = node(state, {"configurable": {"thread_id": "rq1", "emit": lambda t, d: events.append((t, d))}})

    vr = [d for t, d in events if t == "verdict_recheck"]
    assert len(vr) == 1
    assert vr[0]["summary"]["partial"] == 1 and vr[0]["summary"]["dropped"] == 1
    assert vr[0]["dropped"] == [{"competitor": "Notion", "dimension": "deployment"}]
    # 病因不变量(codex #1):curated 含 partial cell,但 verdict 不路由 → 不是 retry_analyze
    assert out["qc_result"]["verdict"] != "retry_analyze"
    # cell 剔除结构化落库(replay 平价,codex #2/#5)
    rows = list_curation_drops(conn, "rq1")
    assert [(r["scope"], r["competitor"], r["dimension"]) for r in rows] == [("cell", "Notion", "deployment")]
```

> `make_qc_node` 真实签名以 `nodes.py` 为准;若 qc_node 内还调了 insight 重生成(`generate_insight`),monkeypatch `nodes_mod.generate_insight` 返个固定 ReportInsight 防真打(参照该文件既有 qc_node 测试两侧桩法)。

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_sse_schemas.py::test_sse_verdict_recheck_schema -v`
Expected: FAIL(`ImportError: SSEVerdictRecheckData`)。

- [ ] **Step 3: 加 `SSEVerdictRecheckData`(`api/schemas.py`)**

在 `SSECellRowData` 之后加:

```python
class SSEVerdictRecheckCell(BaseModel):
    dimension: str
    competitor: str
    support_verdict: str   # supported | partial | unsupported


class SSEVerdictRecheckData(BaseModel):
    """verdict_recheck event — qc 三级真算后回写矩阵三色 + StatusBar(spec §5.5)。
    cell_verdicts=保留 cell 的三级;dropped=被剔除 cell 的结构化 {competitor,dimension}(codex #5);
    downgraded=partial 子集;summary=计数。decision verdict 不在此(见 Step 5 偏差说明)。"""
    cell_verdicts: list[SSEVerdictRecheckCell] = Field(default_factory=list)
    dropped: list[dict] = Field(default_factory=list)
    downgraded: list[dict] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    ts: str
```

- [ ] **Step 4: `qc_node` emit verdict_recheck + 持久化 cell 剔除(`nodes.py`)**

顶部 import 区把 `replace_curation_drops` 加入 repository import。在 `qc_node` 的 `save_analysis(conn, run_id, curated)`(行 329)之后加:

```python
        # 三级真算结果:回写在 curated 的 cell.support_verdict 上(已随 save_analysis 落库);
        # 这里派生 verdict_recheck 事件 + 结构化持久化剔除清单(replay 平价,§7.3)。
        cell_verdicts = [
            {"dimension": row.dimension, "competitor": cell.competitor,
             "support_verdict": cell.support_verdict}
            for row in curated.comparison for cell in row.cells]
        downgraded = [cv for cv in cell_verdicts if cv["support_verdict"] == "partial"]
        supported_n = sum(1 for cv in cell_verdicts if cv["support_verdict"] == "supported")
        # dropped 已是 list[dict{competitor,dimension}](Task 5),直接作 replace items;
        # REPLACE per (run_id,"cell") → qc 多轮重试每轮覆盖,无幽灵剔除(codex #2)。
        replace_curation_drops(conn, run_id, "cell", dropped)
        if emit is not None:
            emit("verdict_recheck", {
                "cell_verdicts": cell_verdicts,
                "dropped": dropped,
                "downgraded": downgraded,
                "summary": {"supported": supported_n, "partial": len(downgraded),
                            "dropped": len(dropped)},
            })
```

- [ ] **Step 5: `decide_node` 持久化 decision 剔除(`nodes.py`)**

**先归一 decide_node 的 dropped 形状(Task 6 连带,必做)**:Task 6 后 `curate_decisions` 正常路径返 `list[dict{"action"}]`,但 `decide_node` 的 fallback 路径仍是 list[str](nodes.py:422 `dropped: list[str] = []` 初始化 + :445 `dropped = [d.action for d in ...]`)。两种形状混用 → 下面 `d["action"]` 在 list[str] 上 TypeError。**把 decide_node 这两处归一为 list[dict{"action"}]**:
- nodes.py:422 `dropped: list[str] = []` → `dropped: list[dict] = []`
- nodes.py:445 `dropped = [d.action for d in decision_set.decisions if d not in kept]` → `dropped = [{"action": d.action} for d in decision_set.decisions if d not in kept]`

(`len(dropped)` 用法 nodes.py:456/464 对 list[dict] 兼容,不受影响。)

然后在 `kept, dropped = qc.curate_decisions(...)`(行 435 附近)/ `save_decisions(...)`(行 448 附近)旁加(`dropped` 现统一 list[dict{"action"}]):

```python
        replace_curation_drops(conn, run_id, "decision",
                               [{"detail": d["action"]} for d in dropped])
```

(顶部 import 已含 `replace_curation_drops`;REPLACE per (run_id,"decision") 同样防多轮幽灵。)

> **decision_verdicts spec 偏差说明(codex [P2] #4,显式记录):** spec §7.1 的 `verdict_recheck` payload 列了 `decision_verdicts`,但 decision 在 **decide_node**(晚于 qc_node)才 `curate_decisions`,qc 发 `verdict_recheck` 时决策尚不存在 → 本期 `verdict_recheck` 只携 cell。**decision 的三级 verdict 经 `Decision.support_verdict` 字段随 `save_decisions` 落库**(Task 3/6),前端 Plan C 经 `GET /decisions/:run` REST 读取决策三色;decision 剔除经本步 `curation_drops`(scope="decision")持久化。这是有意的本期边界,非遗漏。

- [ ] **Step 6: 跑测试确认 PASS + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_sse_schemas.py tests/test_graph_nodes.py -v`
Expected: 全 passed。
Run: `.venv/bin/python -m pytest`
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
git add rivalradar/graph/nodes.py rivalradar/api/schemas.py tests/test_sse_schemas.py tests/test_graph_nodes.py
git commit -m "feat(qc/decide): emit verdict_recheck + persist curation drops structurally (Plan B, spec 5.5/7.3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 11: `GET /runs/{id}/curation-drops` REST

**Files:**
- Modify: `rivalradar/api/reads.py`
- Test: `tests/test_api_reads.py`

- [ ] **Step 1: 写失败测试(端点返回剔除清单 / run 不存在 404)**

追加到 `tests/test_api_reads.py`(沿用该文件 `db_path`/`seeded` fixture + `repo` + `TestClient(create_app(...))` 模式,与 Plan A 的 queries 端点测试同款):

```python
def test_get_curation_drops(db_path, seeded):
    from rivalradar.storage.db import connect
    c = connect(db_path)
    repo.create_run(c, "rd1", ["Notion"], ["pricing"])
    repo.replace_curation_drops(c, "rd1", "cell", [{"competitor": "Notion", "dimension": "pricing"}])
    c.close()
    client = TestClient(create_app(db_path=db_path))
    r = client.get("/runs/rd1/curation-drops")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and body[0]["scope"] == "cell"
    assert body[0]["competitor"] == "Notion" and body[0]["dimension"] == "pricing"


def test_get_curation_drops_404_when_run_missing(db_path, seeded):
    client = TestClient(create_app(db_path=db_path))
    assert client.get("/runs/nope/curation-drops").status_code == 404
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `.venv/bin/python -m pytest tests/test_api_reads.py::test_get_curation_drops -v`
Expected: FAIL(404 路由不存在 → 实际返 404 但期望 200,assert 失败)。

- [ ] **Step 3: 加端点(`reads.py`,`list_run_queries` 之后)**

```python
@router.get("/runs/{run_id}/curation-drops")
def list_run_curation_drops(run_id: str,
                            conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    """策展剔除清单(Plan B:replay/事后还原矩阵「—」+ StatusBar 红○)。run 不存在 → 404;无剔除 → 空。"""
    if repo.get_run(conn, run_id) is None:
        raise HTTPException(404, "run not found")
    return repo.list_curation_drops(conn, run_id)
```

- [ ] **Step 4: 跑测试确认 PASS + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_api_reads.py -v`
Expected: 全 passed。
Run: `.venv/bin/python -m pytest`
Expected: 全绿。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/reads.py tests/test_api_reads.py
git commit -m "feat(api): GET /runs/:id/curation-drops endpoint (Plan B, spec 7.3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Epic E — 全量回归 + 真 run 校准(spec §5.5 验收:三级不误伤)

### Task 12: 全量回归 + 真 run support_verdict / insight typing 校准

- [ ] **Step 1: 全量单测**

Run: `.venv/bin/python -m pytest`
Expected: 全绿(~370+)。任一红先修到绿。

- [ ] **Step 2: 真 run 抽查 spike(真打,放 spikes/,不进 pytest)**

写 `spikes/spike_planB_verdict_insight.py`:真打 1-2 竞品 × 2-3 维,用 TestClient POST /run 消费 SSE,断言:
- `chunk` 事件出现(insight 两步化真流字符)。
- `cell_row` 事件逐维出现(status=ok/failed)。
- `verdict_recheck` 事件出现,`summary` 含真实 supported/partial/dropped 计数;**校准:partial/dropped 不全为 0 也不离谱全剔**(真打看三级是否误伤——把充分判成不足=假降级,记忆 [[same-disease-new-symptom-fools-tests]] / 真 run 抓 scoping bug)。
- `GET /runs/{id}/analysis` 的 cell 带真实 `support_verdict`(三色非全 supported)。
- `GET /runs/{id}/curation-drops` 返回结构化剔除(若有 unsupported)。

骨架(参照 `spikes/spike_planA_real_events.py` + `spike_g_api_real_doubao.py`):

```python
from fastapi.testclient import TestClient
from rivalradar import config as cfg
from rivalradar.api.app import create_app
from rivalradar.search.tavily_provider import TavilyProvider

app = create_app(db_path="/tmp/spike_planB.db", doubao_client=cfg.get_doubao_client(),
                 provider=TavilyProvider(api_key=cfg.tavily_api_key()), max_retries=1)
client = TestClient(app)
r = client.post("/run", json={"competitors": ["Notion"], "dimensions": ["pricing", "integrations"]})
# 解析 SSE，断言 chunk / cell_row / verdict_recheck 出现 + 三级计数合理（参照 spike_planA 的 _parse_sse）
```

Run(WSL2 Clash:Doubao/Tavily 国内,unset 代理):
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
NO_PROXY=localhost,127.0.0.1 .venv/bin/python spikes/spike_planB_verdict_insight.py
```
Expected:打印 chunk 数 > 5、cell_row 逐维、verdict_recheck 三级计数(supported/partial/dropped)、analysis cell 三色非全 supported。**若三级全 supported(疑似没真判)或全 dropped(误伤)→ 调 `_ENTAIL_PROMPT`(few-shot)再跑,门槛在真 run 校准。**

- [ ] **Step 3: 记录 spike 结论 + commit**

把校准结论追加到 `spikes/SPIKE_RESULTS.md`(Spike I:Plan B 三级真算 + insight 两步真 run 校准),按仓库惯例提交 spike 脚本 + 结果:

```bash
git add spikes/spike_planB_verdict_insight.py spikes/SPIKE_RESULTS.md
git commit -m "test(plan-b): real-run verdict three-level + insight typing calibration spike (Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec 覆盖(Plan B 范围 = §5.3 / §5.5 / §5.6 / §7.1 部分 / §7.2 / §7.3 部分):**
- §5.6 insight 两步化 → Task 1/2(generate_insight_streamed + write_node 接线 + 回落)✓;Spike H 已 GO,首块前 drafting 占位复用现有 _emit_progress ✓。
- §5.5 support_verdict 真算三级 + 回写 → Task 3(cell/decision 字段)、Task 4(EntailmentVerdict 三级 + judge map)、Task 5(curate_analysis 回写 + 丢 unsupported,二元组不破)、Task 6(check_entailment/decision/curate_decisions 收口)✓。
- §5.5 recheck 不进路由(codex [P1])→ Task 5/6:partial 不产 issue、三级判定不入 qc_result.issues,decide_verdict 仍只看 problem_type;Task 5 病因不变量测试锁死 ✓。
- §5.5 curate 返回值不破调用点(codex [P1])→ verdict 回写到 cell/decision 字段,`(curated, dropped)` 二元组签名不变 ✓(比 spec 二选一更优:第三条路)。
- §5.3 逐格 cell_row + 乱序 + 失败契约 → Task 7(build_comparison/analyze on_cell_row,ok/failed)、Task 8(analyze_node emit + SSECellRowData)✓。
- §7.2 cell/decision 级 support_verdict 字段 + 不挂 ref → Task 3(字段)、Task 5/6(只回写 cell/decision,ref 不动)✓。
- §7.1 新事件 schema:cell_row(Task 8)、verdict_recheck(Task 10)✓;chunk 复活(Task 1/2,schema 已存在)✓。
- §7.3 dropped 结构化持久化 + REST → Task 9(curation_drops 表+CRUD)、Task 10(qc/decide 落库)、Task 11(REST)✓;cell/decision verdict 随 analysis/decisions 落库 ✓。
- §5.5 真 run 校准(三级不误伤,反幻觉关键)→ Task 12 spike ✓。

**2. 占位扫描:** 无 TBD/TODO;每步含真实代码/命令/期望。Task 6/8/10 对真实文件签名/行号的「以 nodes.py 为准调整」是对既有代码的对齐指令(读真实代码后落地),非占位——每处都给了完整改造代码 + 精确插入位置。

**3. 类型一致性:**
- `EntailmentVerdict.verdict: SupportVerdict` 贯穿 Task 4(定义)→ Task 5(curate_analysis 读 `.verdict`)→ Task 6(check_entailment/decision/curate_decisions 读 `.verdict`)一致。
- `_judge_comparison_verdicts(...) -> dict[(comp,dim), EntailmentVerdict]` 在 Task 4 定义,Task 5(curate_analysis)+ Task 6(check_entailment)使用,签名一致。
- `support_verdict` cell/decision 级字段 Task 3 定义 → Task 5/6 回写 → Task 10 派生 verdict_recheck 读 `cell.support_verdict` 一致。
- `on_cell_row(dimension, row, status)` 三参签名 Task 7(build_comparison/analyze 定义)→ Task 8(analyze_node 提供回调)一致。
- `replace_curation_drops(conn, run_id, scope, items)` / `list_curation_drops(conn, run_id)` Task 9 定义 → Task 10(qc/decide 调 replace,REPLACE per scope 防多轮幽灵 codex #2)→ Task 11(REST 调 list)一致;`dropped` 全程结构化 list[dict](codex #5):curate cell→`{competitor,dimension}`、curate decision→`{action}`→decide_node 映射 `{detail}`。
- `generate_insight_streamed(body, *, client, model, emit, ...)` Task 1 定义 → Task 2(write_report_with_insight 调,透传 emit)一致;`write_report_with_insight(..., emit=None)` Task 2 扩展 → write_node 传 emit 一致。
- SSE 事件名 cell_row / verdict_recheck 在节点 emit(Task 8/10)与 schema 类名(SSECellRowData/SSEVerdictRecheckData)对应。

**4. 边界:** 本 Plan 只动后端。前端消费 chunk/cell_row/verdict_recheck/curation-drops、矩阵三色刷新、工牌、技能子系统 = Plan C;replay 事件生成(把 cell_row/verdict_recheck 并入 replay)、demo fakeSSEPlayer 平价、DESIGN.md v5 已写、状态覆盖/a11y、删 proto-tag = Plan C/D。decision_verdicts 不单独 emit(decision.support_verdict 随 save_decisions 落库,前端经 /decisions REST 读)——verdict_recheck 事件聚焦 cell,这是有意的本期边界(Plan C 接 decision 三色时读 decisions REST)。
