# RivalRadar Lane C-2b:撰写 Agent + 质检 Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现后两个 Agent —— **撰写 Agent**(混合:确定性骨架把 `CompetitorAnalysis` 渲染成带内联引用、标 `as of {date}` 的 Markdown 报告 + 一段 LLM 导语摘要)与 **质检 Agent**(确定性硬闸:evidence_refs 非空/有效 + 受控本体校验 + 覆盖度;LLM 辅助:引语蕴含判定;最后据 issues 给出 `QCVerdict`)。

**Architecture:** 续写 `rivalradar/agents/`。撰写 Agent 的正文 100% 确定性渲染(每个数字/结论直接来自 schema + `evidence_refs`,引用零幻觉),LLM 只生成一段框架性"导语摘要"(经 `structured_call`,只许概括正文已有事实);确定性渲染离线可测,LLM 段用 FakeClient 离线测。质检 Agent 的硬闸全确定性(§17.3:确定性是主角,量化拦截),LLM 蕴含为辅(§5:尽力);`decide_verdict` 是纯逻辑映射;`insufficient_evidence` 留给 Lane D 路由在有界重试耗尽后赋予。对应 spec §5 / §8 / §13 / §17.3,并落实 C-2a 遗留④(`Evidence.dimension` 受控本体校验)。

**Tech Stack:** Python 3.11+ · Pydantic v2 · 复用 `rivalradar/llm/structured.py`(tools)、`rivalradar/schema/models.py`、`rivalradar/schema/feature_tree.py`(`assemble_tree`)、`rivalradar/storage/repository.py`(`save_report`)。

---

## 前置:依赖与既有件

- 复用(只导入,不改动):
  - `schema/models.py`:`CompetitorAnalysis, CompetitorProfile, FeatureItem, PricingModel, PricingTier, UserPersona, SWOT, SWOTPoint, ComparisonRow, ComparisonCell, EvidenceRef, Evidence, QCIssue, QCResult, QCVerdict, ProblemType, CONTROLLED_DIMENSIONS`。
  - `schema/feature_tree.py`:`assemble_tree(items) -> list[dict]`,节点形如 `{"item": FeatureItem, "children": [...]}`。
  - `llm/structured.py`:`structured_call(model_cls, messages, *, client, model, max_retries=2) -> model_cls`。
  - `storage/repository.py`:`save_report(conn, run_id, markdown)`、`get_report(conn, run_id)`(报告以 Markdown 字符串入库;本 Lane 不直接落库,产出供 Lane D/E 落库)。
- **关于 QC 的 `report` 输入(对 §5 的有据偏离)**:spec §5 列 QC 输入为 `analysis+report+evidence`。因撰写 Agent 对**所有被引事实**是确定性渲染,"报告是否保留引用"在渲染时已被保证,故 QC 聚焦审计 `analysis`(错误真正的来源)+ `evidence`。LLM 导语摘要的忠实度(summary-蕴含/异源交叉)按 §17.3 列为 TODO(非 2.5 周必须),不在本 Lane。
- **`QCVerdict` 取值范围**:本 Lane 的 `check()` 只产出 `pass / retry_collect / retry_analyze`(单遍质检的纯逻辑);`insufficient_evidence` 是 Lane D 路由在 `retry_count` 封顶后据"查无公开数据"赋予的降级结论(spec §8 有界重试)。

## 文件结构

```
rivalradar/
  agents/
    writer.py    # 撰写 Agent:_fmt_refs + render_competitor/comparison/sources/body + generate_summary + write_report
    qc.py        # 质检 Agent:_iter_conclusions + check_traceability/ontology/coverage + check_entailment + decide_verdict + check
tests/
  test_writer_agent.py
  test_qc_agent.py
spikes/
  spike_e_report_qc_real.py   # 真实 Doubao:write_report(导语)+ qc.check(蕴含)over canned analysis(待 ARK key)
```

---

### Task 1:撰写 Agent —— 确定性渲染单竞品(功能/定价/画像/SWOT + 内联引用)

**Files:**
- Create: `rivalradar/agents/writer.py`
- Test: `tests/test_writer_agent.py`

> 撰写 Agent 的正文是确定性的:每条结论后挂 `[evidence_id]` 内联标记(引用零幻觉)。功能层级用既有 `assemble_tree` 拼树后缩进渲染。本任务先做内联引用格式化 `_fmt_refs` 与单竞品渲染 `render_competitor`。

- [ ] **Step 1: 写失败测试 `tests/test_writer_agent.py`**

```python
from rivalradar.agents.writer import _fmt_refs, render_competitor
from rivalradar.schema.models import (
    CompetitorProfile, FeatureItem, PricingModel, PricingTier,
    UserPersona, SWOT, SWOTPoint, EvidenceRef,
)


def _ref(eid):
    return EvidenceRef(evidence_id=eid, quote="q")


def test_fmt_refs_joins_ids_in_brackets():
    assert _fmt_refs([_ref("e1"), _ref("e2")]) == " [e1, e2]"
    assert _fmt_refs([]) == ""


def test_render_competitor_includes_facts_and_inline_citations():
    prof = CompetitorProfile(
        name="Notion",
        features=[
            FeatureItem(id="f1", name="数据库", description="多视图", category="core_workflows",
                        evidence_refs=[_ref("e1")]),
            FeatureItem(id="f2", name="表格视图", description="", category="core_workflows",
                        parent_id="f1", evidence_refs=[_ref("e2")]),
        ],
        pricing=PricingModel(model_type="freemium",
                             tiers=[PricingTier(name="Free", price="$0", billing_cycle="monthly")],
                             evidence_refs=[_ref("e3")]),
        personas=[UserPersona(segment="团队", needs=["协作"], evidence_refs=[_ref("e4")])],
        swot=SWOT(strengths=[SWOTPoint(text="生态强", evidence_refs=[_ref("e5")])]),
    )
    md = render_competitor(prof)
    assert "## Notion" in md
    assert "数据库" in md and "[e1]" in md
    assert "表格视图" in md and "[e2]" in md       # 子功能也渲染
    assert "freemium" in md and "[e3]" in md
    assert "Free" in md
    assert "团队" in md and "[e4]" in md
    assert "生态强" in md and "[e5]" in md


def test_render_competitor_handles_empty_sections():
    prof = CompetitorProfile(name="空", pricing=PricingModel(model_type="unknown"), swot=SWOT())
    md = render_competitor(prof)
    assert "## 空" in md
    assert "_(无)_" in md  # 空功能/定价/画像不崩
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py -v`
Expected: FAIL（ModuleNotFoundError:rivalradar.agents.writer）

- [ ] **Step 3: 写 `rivalradar/agents/writer.py`**

```python
from __future__ import annotations

from rivalradar.schema.feature_tree import assemble_tree
from rivalradar.schema.models import CompetitorProfile, EvidenceRef, FeatureItem


def _fmt_refs(refs: list[EvidenceRef]) -> str:
    """把 evidence_refs 渲染成内联引用标记,如 ' [e1, e2]';无引用则空串。"""
    ids = [r.evidence_id for r in refs]
    return f" [{', '.join(ids)}]" if ids else ""


def _render_features(features: list[FeatureItem]) -> str:
    """按 assemble_tree 的层级缩进渲染功能项,每项挂内联引用。"""
    lines: list[str] = []

    def walk(nodes: list[dict], depth: int) -> None:
        for n in nodes:
            it = n["item"]
            indent = "  " * depth
            desc = f":{it.description}" if it.description else ""
            lines.append(f"{indent}- {it.name}{desc}{_fmt_refs(it.evidence_refs)}")
            walk(n["children"], depth + 1)

    walk(assemble_tree(features), 0)
    return "\n".join(lines)


def render_competitor(profile: CompetitorProfile) -> str:
    """确定性渲染单个竞品 Profile 为 Markdown,每条结论挂内联引用。"""
    parts = [f"## {profile.name}", "### 功能"]
    parts.append(_render_features(profile.features) if profile.features else "_(无)_")

    parts.append(f"### 定价({profile.pricing.model_type}){_fmt_refs(profile.pricing.evidence_refs)}")
    if profile.pricing.tiers:
        for t in profile.pricing.tiers:
            tail = f" — {t.limits}" if t.limits else ""
            parts.append(f"- {t.name}:{t.price} / {t.billing_cycle}{tail}")
    else:
        parts.append("_(无)_")

    parts.append("### 用户画像")
    if profile.personas:
        for p in profile.personas:
            needs = "、".join(p.needs) or "—"
            pains = "、".join(p.pain_points) or "—"
            praise = "、".join(p.praise) or "—"
            parts.append(f"- {p.segment}:需求 {needs};痛点 {pains};好评 {praise}{_fmt_refs(p.evidence_refs)}")
    else:
        parts.append("_(无)_")

    parts.append("### SWOT")
    quads = (("优势", profile.swot.strengths), ("劣势", profile.swot.weaknesses),
             ("机会", profile.swot.opportunities), ("威胁", profile.swot.threats))
    swot_lines = [f"- {label}:{pt.text}{_fmt_refs(pt.evidence_refs)}"
                  for label, points in quads for pt in points]
    parts.append("\n".join(swot_lines) if swot_lines else "_(无)_")

    return "\n".join(parts)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/writer.py tests/test_writer_agent.py
git commit -m "feat: writer deterministic per-competitor rendering with inline citations"
```

---

### Task 2:撰写 Agent —— 对比矩阵 + 来源清单 + 正文组装(引用忠实度)

**Files:**
- Modify: `rivalradar/agents/writer.py`(追加)
- Test: `tests/test_writer_agent.py`(追加)

> 续写确定性正文:跨竞品对比表(列=竞品,行=维度,cell 标 value + 引用)、来源清单(被引 evidence_id → 标题/URL/`as of {fetched_at}`,缺失的标 missing)、`render_body` 组装(顶部标报告级 `as of {as_of}`)。关键验证:**报告里出现 analysis 中所有被引的 evidence_id(引用忠实度)**。

- [ ] **Step 1: 追加失败测试到 `tests/test_writer_agent.py`**

```python
from rivalradar.agents.writer import render_comparison, render_sources, render_body
from rivalradar.schema.models import (
    CompetitorAnalysis, ComparisonRow, ComparisonCell, Evidence,
)


def _ev(eid):
    return Evidence(id=eid, competitor="Notion", dimension="pricing", content="c",
                    source_url="https://notion.so/pricing", source_title="Pricing",
                    language="en", fetched_at="2026-05-25T00:00:00Z")


def test_render_comparison_table_has_competitor_columns_and_refs():
    rows = [ComparisonRow(dimension="pricing", cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                       evidence_refs=[_ref("e3")]),
        ComparisonCell(competitor="飞书", value_type="enum", value="freemium"),
    ])]
    md = render_comparison(rows, ["Notion", "飞书"])
    assert "| 维度 | Notion | 飞书 |" in md
    assert "pricing" in md and "freemium" in md and "[e3]" in md


def test_render_comparison_empty():
    assert "无对比数据" in render_comparison([], ["Notion"])


def test_render_sources_resolves_and_marks_missing():
    analysis = CompetitorAnalysis(
        competitors=[],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                           evidence_refs=[_ref("e3"), _ref("e_missing")])])],
    )
    md = render_sources(analysis, [_ev("e3")])
    assert "[e3]" in md and "Pricing" in md and "notion.so/pricing" in md
    assert "as of 2026-05-25T00:00:00Z" in md
    assert "e_missing" in md and "missing" in md  # 不在证据集 → 标 missing


def test_render_body_stamps_as_of_and_preserves_all_cited_ids():
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(
            name="Notion",
            features=[FeatureItem(id="f1", name="数据库", description="", category="core_workflows",
                                  evidence_refs=[_ref("e1")])],
            pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e3")]),
            swot=SWOT(),
        )],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                           evidence_refs=[_ref("e3")])])],
    )
    body = render_body(analysis, [_ev("e1"), _ev("e3")], as_of="2026-05-25")
    assert "as of 2026-05-25" in body
    # 引用忠实度:analysis 里每个被引 id 都出现在正文
    for eid in ("e1", "e3"):
        assert f"[{eid}]" in body or f"[{eid}," in body or f", {eid}]" in body
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py -v`
Expected: FAIL（ImportError:render_comparison 等未定义）

- [ ] **Step 3: 追加到 `rivalradar/agents/writer.py`**

先扩展顶部 models import(加 `CompetitorAnalysis, ComparisonRow, Evidence`),变为:
`from rivalradar.schema.models import CompetitorAnalysis, CompetitorProfile, ComparisonRow, EvidenceRef, Evidence, FeatureItem`

然后追加:

```python
def render_comparison(rows: list[ComparisonRow], competitors: list[str]) -> str:
    """跨竞品对比表:行=维度,列=竞品,cell 标 value + 内联引用;缺 cell 标 '—'。"""
    if not rows:
        return "## 跨竞品对比\n\n_(无对比数据)_"
    header = "| 维度 | " + " | ".join(competitors) + " |"
    sep = "|" + "---|" * (len(competitors) + 1)
    lines = ["## 跨竞品对比", "", header, sep]
    for row in rows:
        by_comp = {c.competitor: c for c in row.cells}
        cells = []
        for name in competitors:
            cell = by_comp.get(name)
            cells.append(f"{cell.value}{_fmt_refs(cell.evidence_refs)}" if cell else "—")
        lines.append(f"| {row.dimension} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _cited_ids(analysis: CompetitorAnalysis) -> list[str]:
    """按出现顺序收集 analysis 中所有被引的 evidence_id(去重)。"""
    ids: list[str] = []
    seen: set[str] = set()

    def add(refs: list[EvidenceRef]) -> None:
        for r in refs:
            if r.evidence_id not in seen:
                seen.add(r.evidence_id)
                ids.append(r.evidence_id)

    for prof in analysis.competitors:
        for f in prof.features:
            add(f.evidence_refs)
        add(prof.pricing.evidence_refs)
        for p in prof.personas:
            add(p.evidence_refs)
        for points in (prof.swot.strengths, prof.swot.weaknesses,
                       prof.swot.opportunities, prof.swot.threats):
            for pt in points:
                add(pt.evidence_refs)
    for row in analysis.comparison:
        for cell in row.cells:
            add(cell.evidence_refs)
    return ids


def render_sources(analysis: CompetitorAnalysis, evidence: list[Evidence]) -> str:
    """被引证据清单:evidence_id → [标题](URL)(as of fetched_at);不在证据集的标 missing。"""
    idx = {e.id: e for e in evidence}
    cited = _cited_ids(analysis)
    lines = ["## 来源"]
    if not cited:
        lines.append("_(无引用)_")
        return "\n".join(lines)
    for eid in cited:
        e = idx.get(eid)
        if e is None:
            lines.append(f"- [{eid}] (missing:该 evidence_id 不在证据集)")
        else:
            lines.append(f"- [{eid}] [{e.source_title}]({e.source_url})(as of {e.fetched_at})")
    return "\n".join(lines)


def render_body(analysis: CompetitorAnalysis, evidence: list[Evidence], *, as_of: str) -> str:
    """确定性正文:as-of 时效 + 逐竞品 Profile + 对比表 + 来源清单。"""
    parts = [f"> 数据时效:as of {as_of}"]
    parts += [render_competitor(p) for p in analysis.competitors]
    parts.append(render_comparison(analysis.comparison, [p.name for p in analysis.competitors]))
    parts.append(render_sources(analysis, evidence))
    return "\n\n".join(parts)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/writer.py tests/test_writer_agent.py
git commit -m "feat: writer comparison table + sources + body assembly (citation fidelity)"
```

---

### Task 3:撰写 Agent —— LLM 导语摘要 + write_report 入口(混合)

**Files:**
- Modify: `rivalradar/agents/writer.py`(追加)
- Test: `tests/test_writer_agent.py`(追加,用 FakeClient)

> 混合的"LLM"那一半:用一次 `structured_call` 让模型基于**已成稿正文**写一段导语摘要(只许概括正文已有事实)。`write_report` = 摘要(框架性,不挂引用)+ 确定性正文(所有引用都在这里)。FakeClient 返回 canned `{"summary": ...}`,离线验证接线。

- [ ] **Step 1: 追加失败测试到 `tests/test_writer_agent.py`**

```python
import json
from types import SimpleNamespace

from rivalradar.agents.writer import ReportSummary, generate_summary, write_report


class _Completions:
    def __init__(self, payloads):
        self.payloads = list(payloads); self.calls = 0
    def create(self, **kwargs):
        p = self.payloads[self.calls]; self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=p))]))],
            usage=SimpleNamespace(total_tokens=10))


class _FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=_Completions(payloads))


def test_generate_summary_returns_text():
    client = _FakeClient([json.dumps({"summary": "Notion 提供 freemium 定价。"})])
    out = generate_summary("正文……", client=client, model="m")
    assert out == "Notion 提供 freemium 定价。"


def test_write_report_combines_summary_and_deterministic_body():
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(
            name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e3")]),
            swot=SWOT())],
        comparison=[],
    )
    client = _FakeClient([json.dumps({"summary": "导语:Notion 走 freemium。"})])
    report = write_report(analysis, [_ev("e3")], as_of="2026-05-25", client=client, model="m")
    assert report.startswith("# 竞品分析报告")
    assert "导语:Notion 走 freemium。" in report   # LLM 摘要
    assert "## Notion" in report                    # 确定性正文
    assert "[e3]" in report                         # 引用在正文
    assert "as of 2026-05-25" in report
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py -v`
Expected: FAIL（ImportError:ReportSummary 等未定义）

- [ ] **Step 3: 追加到 `rivalradar/agents/writer.py`**

顶部 import 追加(与现有 import 同组,置于文件顶部):

```python
from pydantic import BaseModel

from rivalradar.llm.structured import structured_call
```

文件尾部追加:

```python
class ReportSummary(BaseModel):
    summary: str


def generate_summary(body: str, *, client, model) -> str:
    """LLM 导语:基于已成稿正文写 3-5 句中文摘要,只许概括正文已有事实,不得引入新数字/结论。"""
    msgs = [{"role": "user", "content":
             "下面是一份已成稿的竞品分析报告正文(含数据与引用)。请写一段 3-5 句中文执行摘要(导语),"
             "只能概括正文已经出现的事实,不得引入正文没有的数字、结论或竞品。\n\n正文:\n" + body}]
    return structured_call(ReportSummary, msgs, client=client, model=model).summary


def write_report(analysis: CompetitorAnalysis, evidence: list[Evidence], *,
                 as_of: str, client, model) -> str:
    """撰写 Agent 入口(混合):LLM 导语摘要 + 确定性正文(所有引用在正文)。"""
    body = render_body(analysis, evidence, as_of=as_of)
    summary = generate_summary(body, client=client, model=model)
    return f"# 竞品分析报告\n\n## 摘要(AI 生成,仅概括下方结论)\n\n{summary}\n\n{body}"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_writer_agent.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/writer.py tests/test_writer_agent.py
git commit -m "feat: writer LLM summary (grounded) + write_report hybrid entry"
```

---

### Task 4:质检 Agent —— 确定性硬闸(溯源 + 受控本体 + 覆盖度)

**Files:**
- Create: `rivalradar/agents/qc.py`
- Test: `tests/test_qc_agent.py`

> 确定性闸是质检主角(§17.3,量化拦截)。`_iter_conclusions` 遍历每条挂引用的结论;`check_traceability`:空引用或引用了不存在的 evidence_id → `missing_evidence`;`check_ontology`:对比维度/证据维度不在 `CONTROLLED_DIMENSIONS` → `schema_incomplete`(收 C-2a 遗留④);`check_coverage`:某竞品缺某受控维度的对比 cell → `low_coverage`。全部离线可测。

- [ ] **Step 1: 写失败测试 `tests/test_qc_agent.py`**

```python
from rivalradar.agents.qc import (
    check_traceability, check_ontology, check_coverage,
)
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, FeatureItem, PricingModel,
    SWOT, SWOTPoint, ComparisonRow, ComparisonCell, EvidenceRef, Evidence,
)


def _ref(eid):
    return EvidenceRef(evidence_id=eid, quote="q")


def _ev(eid, dimension="pricing"):
    return Evidence(id=eid, competitor="Notion", dimension=dimension, content="c",
                    source_url="u", source_title="t", language="en",
                    fetched_at="2026-05-25T00:00:00Z")


def test_check_traceability_flags_empty_refs():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        features=[FeatureItem(id="f1", name="db", description="", category="core_workflows",
                              evidence_refs=[])],  # 空引用
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    issues = check_traceability(analysis, [_ev("e1")])
    assert any(i.problem_type == "missing_evidence" for i in issues)


def test_check_traceability_flags_dangling_evidence_id():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e_ghost")]),  # 不存在
        swot=SWOT())])
    issues = check_traceability(analysis, [_ev("e1")])
    assert any("e_ghost" in i.detail for i in issues)


def test_check_traceability_clean_when_all_valid():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    assert check_traceability(analysis, [_ev("e1")]) == []


def test_check_ontology_flags_bad_comparison_and_evidence_dimension():
    analysis = CompetitorAnalysis(
        competitors=[],
        comparison=[ComparisonRow(dimension="天气", cells=[])])  # 非受控维度
    issues = check_ontology(analysis, [_ev("e1", dimension="八卦")])  # 证据维度也非受控
    kinds = [i.detail for i in issues]
    assert any("天气" in d for d in kinds)
    assert any("八卦" in d for d in kinds)
    assert all(i.problem_type == "schema_incomplete" for i in issues)


def test_check_coverage_flags_missing_dimension():
    # Notion 只在 pricing 有对比 cell,缺其余 5 个受控维度
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium")])])
    issues = check_coverage(analysis)
    missing_dims = {i.dimension for i in issues if i.problem_type == "low_coverage"}
    assert "deployment" in missing_dims and "pricing" not in missing_dims
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: FAIL（ModuleNotFoundError:rivalradar.agents.qc）

- [ ] **Step 3: 写 `rivalradar/agents/qc.py`**

```python
from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel

from rivalradar.llm.structured import structured_call
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, Evidence, EvidenceRef,
    QCIssue, QCResult, QCVerdict,
)


def _iter_conclusions(
    analysis: CompetitorAnalysis,
) -> Iterator[tuple[str, str, str, list[EvidenceRef]]]:
    """遍历每条挂引用的结论 → (competitor, dimension, 结论文本, evidence_refs)。"""
    for prof in analysis.competitors:
        for f in prof.features:
            yield prof.name, "core_workflows", f"功能:{f.name}", f.evidence_refs
        yield prof.name, "pricing", f"定价:{prof.pricing.model_type}", prof.pricing.evidence_refs
        for p in prof.personas:
            yield prof.name, "review_sentiment", f"画像:{p.segment}", p.evidence_refs
        quads = (("优势", prof.swot.strengths), ("劣势", prof.swot.weaknesses),
                 ("机会", prof.swot.opportunities), ("威胁", prof.swot.threats))
        for label, points in quads:
            for pt in points:
                yield prof.name, "swot", f"SWOT-{label}:{pt.text}", pt.evidence_refs
    for row in analysis.comparison:
        for cell in row.cells:
            yield cell.competitor, row.dimension, f"对比:{cell.value}", cell.evidence_refs


def check_traceability(analysis: CompetitorAnalysis, evidence: list[Evidence]) -> list[QCIssue]:
    """硬闸:每条结论必须挂非空、且 evidence_id 存在于证据集的 evidence_refs。"""
    valid = {e.id for e in evidence}
    issues: list[QCIssue] = []
    for comp, dim, text, refs in _iter_conclusions(analysis):
        if not refs:
            issues.append(QCIssue(competitor=comp, dimension=dim,
                                  problem_type="missing_evidence", detail=f"无引用:{text}"))
            continue
        for r in refs:
            if r.evidence_id not in valid:
                issues.append(QCIssue(competitor=comp, dimension=dim,
                                      problem_type="missing_evidence",
                                      detail=f"引用了不存在的 evidence_id={r.evidence_id}:{text}"))
    return issues


def check_ontology(analysis: CompetitorAnalysis, evidence: list[Evidence]) -> list[QCIssue]:
    """硬闸:对比维度与证据维度必须落在受控本体内(收 C-2a 遗留④)。"""
    allowed = set(CONTROLLED_DIMENSIONS)
    issues: list[QCIssue] = []
    for row in analysis.comparison:
        if row.dimension not in allowed:
            issues.append(QCIssue(competitor="*", dimension=row.dimension,
                                  problem_type="schema_incomplete",
                                  detail=f"对比维度不在受控本体:{row.dimension}"))
    for e in evidence:
        if e.dimension not in allowed:
            issues.append(QCIssue(competitor=e.competitor, dimension=e.dimension,
                                  problem_type="schema_incomplete",
                                  detail=f"证据维度不在受控本体:{e.dimension}"))
    return issues


def check_coverage(
    analysis: CompetitorAnalysis, *, required: tuple[str, ...] = CONTROLLED_DIMENSIONS
) -> list[QCIssue]:
    """覆盖度:每个竞品在每个受控维度上都应有对比 cell,缺则 low_coverage。"""
    covered: dict[str, set[str]] = {}
    for row in analysis.comparison:
        if row.dimension in required:
            for cell in row.cells:
                covered.setdefault(cell.competitor, set()).add(row.dimension)
    issues: list[QCIssue] = []
    for prof in analysis.competitors:
        have = covered.get(prof.name, set())
        for dim in required:
            if dim not in have:
                issues.append(QCIssue(competitor=prof.name, dimension=dim,
                                      problem_type="low_coverage",
                                      detail=f"{prof.name} 缺少维度 {dim} 的对比"))
    return issues
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/qc.py tests/test_qc_agent.py
git commit -m "feat: qc deterministic gate (traceability + ontology + coverage)"
```

---

### Task 5:质检 Agent —— LLM 蕴含判定(引语是否支撑结论)

**Files:**
- Modify: `rivalradar/agents/qc.py`(追加)
- Test: `tests/test_qc_agent.py`(追加,用 FakeClient)

> 辅助判定(§5 尽力):对每条挂引用的结论,把"结论 + 被引原句 + 证据原文"喂模型,判 supported。不支撑 → `hallucination`。每条结论一次 `structured_call`(小 schema)。FakeClient 按结论数返回 canned 判定。

- [ ] **Step 1: 追加失败测试到 `tests/test_qc_agent.py`**

```python
import json
from types import SimpleNamespace

from rivalradar.agents.qc import EntailmentVerdict, check_entailment


class _Completions:
    def __init__(self, payloads):
        self.payloads = list(payloads); self.calls = 0
    def create(self, **kwargs):
        p = self.payloads[self.calls]; self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=p))]))],
            usage=SimpleNamespace(total_tokens=10))


class _FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=_Completions(payloads))


def test_check_entailment_flags_unsupported():
    # 单结论(pricing 挂 e1),模型判 not supported → hallucination
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    client = _FakeClient([json.dumps({"supported": False, "reason": "证据未提定价"})])
    issues = check_entailment(analysis, [_ev("e1")], client=client, model="m")
    assert len(issues) == 1 and issues[0].problem_type == "hallucination"


def test_check_entailment_passes_supported():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    client = _FakeClient([json.dumps({"supported": True, "reason": ""})])
    assert check_entailment(analysis, [_ev("e1")], client=client, model="m") == []


def test_check_entailment_skips_empty_refs():
    # 空引用归 traceability 管,蕴含不调用 LLM(payloads 给空也不该被取用)
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="x", evidence_refs=[]), swot=SWOT())])
    client = _FakeClient([])
    assert check_entailment(analysis, [_ev("e1")], client=client, model="m") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: FAIL（ImportError:EntailmentVerdict / check_entailment 未定义）

- [ ] **Step 3: 追加到 `rivalradar/agents/qc.py`**

```python
class EntailmentVerdict(BaseModel):
    supported: bool
    reason: str = ""


def check_entailment(
    analysis: CompetitorAnalysis, evidence: list[Evidence], *, client, model
) -> list[QCIssue]:
    """LLM 蕴含(尽力):被引证据是否真支撑结论;不支撑 → hallucination。每条结论一次调用。"""
    idx = {e.id: e for e in evidence}
    issues: list[QCIssue] = []
    for comp, dim, text, refs in _iter_conclusions(analysis):
        if not refs:
            continue  # 空引用由 check_traceability 负责
        quotes = []
        for r in refs:
            src = idx[r.evidence_id].content if r.evidence_id in idx else ""
            quotes.append(f"- 引语:{r.quote}\n  证据原文:{src[:600]}")
        msgs = [{"role": "user", "content":
                 "判断下列证据是否支撑该结论。supported=true 表示证据确实支撑该结论;"
                 "false 表示不支撑或无关。\n\n"
                 f"结论:{text}\n\n证据:\n" + "\n".join(quotes)}]
        verdict = structured_call(EntailmentVerdict, msgs, client=client, model=model)
        if not verdict.supported:
            issues.append(QCIssue(competitor=comp, dimension=dim,
                                  problem_type="hallucination",
                                  detail=f"证据不支撑结论({text}):{verdict.reason}"))
    return issues
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/qc.py tests/test_qc_agent.py
git commit -m "feat: qc LLM entailment check (unsupported conclusion -> hallucination)"
```

---

### Task 6:质检 Agent —— verdict 逻辑 + check() 入口

**Files:**
- Modify: `rivalradar/agents/qc.py`(追加)
- Test: `tests/test_qc_agent.py`(追加)

> `decide_verdict` 是纯逻辑(spec §13 ★纯逻辑必测):无 issue→pass;有 missing_evidence/low_coverage→retry_collect(先补采集);否则(hallucination/schema_incomplete)→retry_analyze。`insufficient_evidence` 由 Lane D 路由赋予,不在此。`check()` 串起确定性闸 + 蕴含 → `QCResult`。

- [ ] **Step 1: 追加失败测试到 `tests/test_qc_agent.py`**

```python
from rivalradar.agents.qc import decide_verdict, check
from rivalradar.schema.models import QCIssue, QCResult


def test_decide_verdict_pass_when_no_issues():
    assert decide_verdict([]) == "pass"


def test_decide_verdict_retry_collect_for_missing_or_coverage():
    miss = [QCIssue(competitor="N", dimension="pricing", problem_type="missing_evidence", detail="")]
    cov = [QCIssue(competitor="N", dimension="deployment", problem_type="low_coverage", detail="")]
    assert decide_verdict(miss) == "retry_collect"
    assert decide_verdict(cov) == "retry_collect"


def test_decide_verdict_retry_analyze_for_hallucination_or_schema():
    hall = [QCIssue(competitor="N", dimension="pricing", problem_type="hallucination", detail="")]
    schema = [QCIssue(competitor="*", dimension="天气", problem_type="schema_incomplete", detail="")]
    assert decide_verdict(hall) == "retry_analyze"
    assert decide_verdict(schema) == "retry_analyze"


def test_decide_verdict_collect_takes_priority_over_analyze():
    mixed = [
        QCIssue(competitor="N", dimension="pricing", problem_type="hallucination", detail=""),
        QCIssue(competitor="N", dimension="pricing", problem_type="missing_evidence", detail=""),
    ]
    assert decide_verdict(mixed) == "retry_collect"  # 缺证据优先于重分析


def test_check_end_to_end_clean_passes():
    # 全受控维度都覆盖 + 所有结论引用有效(含 pricing 结论)+ 蕴含 supported → pass
    dims = ("pricing", "deployment", "integrations", "target_users", "core_workflows", "review_sentiment")
    rows = [ComparisonRow(dimension=d, cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="v", evidence_refs=[_ref("e1")])])
        for d in dims]
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(
            name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
            swot=SWOT())],
        comparison=rows)
    # 结论数 = pricing 1 条 + 6 个对比 cell = 7 → 蕴含 7 次 supported(空引用结论会被跳过,此处无)
    client = _FakeClient([json.dumps({"supported": True, "reason": ""}) for _ in range(7)])
    result = check(analysis, [_ev("e1")], client=client, model="m")
    assert isinstance(result, QCResult)
    assert result.verdict == "pass" and result.issues == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: FAIL（ImportError:decide_verdict / check 未定义）

- [ ] **Step 3: 追加到 `rivalradar/agents/qc.py`**

```python
def decide_verdict(issues: list[QCIssue]) -> QCVerdict:
    """单遍质检 issues → verdict(纯逻辑)。
    insufficient_evidence 由 Lane D 路由在有界重试耗尽后赋予,不在此产出。"""
    if not issues:
        return "pass"
    kinds = {i.problem_type for i in issues}
    if "missing_evidence" in kinds or "low_coverage" in kinds:
        return "retry_collect"   # 缺证据/覆盖不足 → 先补采集(优先于重分析)
    return "retry_analyze"        # hallucination / schema_incomplete → 重新分析现有证据


def check(analysis: CompetitorAnalysis, evidence: list[Evidence], *, client, model) -> QCResult:
    """质检入口:确定性硬闸(溯源+本体+覆盖)+ LLM 蕴含 → QCResult。"""
    issues: list[QCIssue] = []
    issues += check_traceability(analysis, evidence)
    issues += check_ontology(analysis, evidence)
    issues += check_coverage(analysis)
    issues += check_entailment(analysis, evidence, client=client, model=model)
    return QCResult(verdict=decide_verdict(issues), issues=issues)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_qc_agent.py -v`
Expected: PASS（13 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/qc.py tests/test_qc_agent.py
git commit -m "feat: qc verdict logic + check() entry (deterministic gate + entailment)"
```

---

### Task 7:🚧 真实 E2E(撰写 + 质检,待 ARK key,GATE-lite)

**Files:**
- Create: `spikes/spike_e_report_qc_real.py`

> 用真实 Doubao 对一份 canned `CompetitorAnalysis` 跑 `write_report`(LLM 导语)+ `qc.check`(LLM 蕴含),确认:报告含确定性正文 + 内联引用 + LLM 摘要;质检产出合法 `QCResult`。需 `ARK_API_KEY`(已配)。

- [ ] **Step 1: 写 `spikes/spike_e_report_qc_real.py`**

```python
"""撰写+质检 真实 E2E:canned analysis → write_report + qc.check。需 ARK_API_KEY。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.agents import qc
from rivalradar.agents.writer import write_report
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, PricingModel, PricingTier,
    SWOT, SWOTPoint, ComparisonRow, ComparisonCell, EvidenceRef, Evidence,
)

EVIDENCE = [
    Evidence(id="e1", competitor="Notion", dimension="pricing",
             content="Notion offers a Free plan and Plus at $10/user/month.",
             source_url="https://notion.so/pricing", source_title="Pricing", language="en",
             fetched_at="2026-05-25T00:00:00Z"),
]

ANALYSIS = CompetitorAnalysis(
    competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium",
                             tiers=[PricingTier(name="Free", price="$0", billing_cycle="monthly")],
                             evidence_refs=[EvidenceRef(evidence_id="e1", quote="Free plan")]),
        swot=SWOT(strengths=[SWOTPoint(text="生态强",
                                       evidence_refs=[EvidenceRef(evidence_id="e1", quote="Free plan")])]),
    )],
    comparison=[ComparisonRow(dimension="pricing", cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                       evidence_refs=[EvidenceRef(evidence_id="e1", quote="Free plan")])])],
)


def main() -> None:
    client = config.get_doubao_client()
    model = config.doubao_model()
    report = write_report(ANALYSIS, EVIDENCE, as_of="2026-05-25", client=client, model=model)
    print("=== REPORT (head) ===")
    print(report[:400])
    assert report.startswith("# 竞品分析报告")
    assert "## 摘要" in report and "## Notion" in report and "[e1]" in report
    assert "as of 2026-05-25" in report

    result = qc.check(ANALYSIS, EVIDENCE, client=client, model=model)
    print(f"=== QC verdict: {result.verdict} | issues: {len(result.issues)} ===")
    for i in result.issues[:5]:
        print(f"  - [{i.problem_type}] {i.competitor}/{i.dimension}: {i.detail}")
    # canned analysis 只覆盖 pricing 一个维度 → 必有 low_coverage → retry_collect
    assert result.verdict in {"pass", "retry_collect", "retry_analyze"}
    print("SPIKE E OK: real report (det body + inline cites + LLM summary) + qc result")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑(需 key)**

Run: `.venv/bin/python spikes/spike_e_report_qc_real.py`
Expected: 打印报告头部(含 `# 竞品分析报告`/`## 摘要`/`## Notion`/`[e1]`/`as of 2026-05-25`)+ QC verdict 与 issues;末行 `SPIKE E OK`。
若无 key:GATE-lite,交用户带 key 跑。

- [ ] **Step 3: 提交**

```bash
git add spikes/spike_e_report_qc_real.py
git commit -m "spike: real writer+qc E2E over canned analysis (det body + LLM summary/entailment)"
```

---

## Self-Review(写完计划后自查)

**1. Spec / 决策覆盖**
- 撰写 Agent:analysis → 人类可读 report、保留内联引用、标 as-of → Task 1-3 ✅(§5 撰写)。混合(确定性骨架 + LLM 导语)按用户决策 → Task 1-2 确定性正文 + Task 3 LLM 摘要 ✅。
- 质检 Agent:Schema 完整/覆盖度/evidence_refs 有效性(确定性硬闸)→ Task 4 ✅(§5/§17.3);引语支持判定(LLM 蕴含)→ Task 5 ✅(§5);verdict 四态中的单遍三态 → Task 6 ✅(§8/§13 ★纯逻辑)。
- C-2a 遗留④(`Evidence.dimension` 受控本体校验)→ Task 4 `check_ontology` ✅。
- 真实 E2E → Task 7 ✅(§13)。
- **范围外(Lane D)**:LangGraph 图编排、`router.route`、真闭环重试(retry_collect/retry_analyze 累加证据)、`insufficient_evidence` 赋值、真闭环回归测试(§13 ★★★)。**范围外(§17.3 TODO)**:LLM 导语摘要的 summary-蕴含/异源交叉判定。

**2. 占位符扫描**:无 TBD。所有 LLM 路径复用已验证的 `structured_call`(tools);FakeClient 与 `tests/test_analyst_agent.py` 同构。

**3. 类型一致性**:
- `structured_call(model_cls, messages, *, client, model)` 签名与既有一致。
- 撰写:`_fmt_refs(list[EvidenceRef])`、`render_competitor(CompetitorProfile)`、`render_comparison(list[ComparisonRow], list[str])`、`render_sources(CompetitorAnalysis, list[Evidence])`、`render_body(..., *, as_of)`、`generate_summary(str, *, client, model)`、`write_report(CompetitorAnalysis, list[Evidence], *, as_of, client, model)` —— 字段名 `EvidenceRef.evidence_id`、`SWOTPoint.text`、`PricingTier.{name,price,billing_cycle,limits}`、`ComparisonCell.{competitor,value,evidence_refs}`、`assemble_tree` 节点 `{"item","children"}` 均与 schema 一致。
- 质检:`QCIssue(competitor, dimension, problem_type, detail)`、`QCResult(verdict, issues)`、`ProblemType` 四值、`QCVerdict` 三态(单遍)与 schema Literal 一致。`_iter_conclusions` 产出的 refs 字段与各模型 `evidence_refs` 一致。
- `check()` 产出 `QCResult` 可直接供 Lane D 路由消费;`write_report` 产出 `str` 可直接 `repository.save_report` 落库。

**4. 注意 / 待 Lane D**
- `check_entailment` 每条结论一次 LLM 调用(N 条结论 = N 次);Lane D 可采样/并行/缓存提速,本计划先求正确 + 离线可测。
- `check()` 让 `check_entailment` 的 `StructuredCallError` 直接上抛(与 analyst 一致,不静默);Lane D 若要"LLM 判定尽力、失败降级"可在编排层包 try/except 并记 trace(§5 尽力)。
- `decide_verdict` 的优先级(collect > analyze)是真闭环语义关键:缺证据必须先补采集,否则重分析无米下锅(§8)。
