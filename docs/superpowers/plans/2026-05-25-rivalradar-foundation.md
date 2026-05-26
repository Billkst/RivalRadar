# RivalRadar 地基实现计划(Spike + Lane A + Lane B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭好 RivalRadar 的可信地基——Pydantic 知识 Schema、Doubao 结构化输出层、SQLite 存储与 LangGraph checkpointer——并用 Day-1 双 spike 锁定 Doubao 扁平 Schema 可行性与搜索/抽取 API 选型。

**Architecture:** Python 包 `rivalradar`。纯逻辑(Schema 模型 / 拼树 / schema 派生 / structured_call 重试 / SQLite CRUD / checkpointer)全部离线 TDD,用 FakeClient 与内存 SQLite 验证,无需任何 API key。两个 spike 是 go/no-go 闸门,分别真打 Doubao(火山方舟)与搜索 API(Tavily),把结论写进 `spikes/SPIKE_RESULTS.md`。本计划只覆盖泳道 A(LLM 层 + Schema)与 B(存储);Lane C→F 待 spike 锁定 API/Schema/竞品名单后再各出跟进计划。

**Tech Stack:** Python 3.11+ · Pydantic v2 · openai SDK(走 Doubao OpenAI 兼容端点)· langgraph + langgraph-checkpoint-sqlite · tavily-python · pytest。

---

## 范围对照(本计划覆盖 spec 的哪些条)

| spec 条目 | 本计划任务 |
|---|---|
| §6 知识 Schema(扁平邻接表 + EvidenceRef 句级引用) | Task 2 |
| §6 / D11 功能树扁平→拼树 | Task 3 |
| §9 结构化输出层 `structured_call`(校验+重试+显式报错) | Task 4(schema 派生)+ Task 6 |
| §15 Day-1 spike A(Doubao 扁平 Schema 实测) | Task 5 |
| §7/§14 Day-1 spike B(搜索/抽取可达性+质量) | Task 7 |
| §10 / D4 存储 SQLite(evidence/analysis/report/trace/runs) | Task 8 + Task 9 |
| §10 LangGraph SqliteSaver checkpointer | Task 10 |
| §13 `[单测] structured_call`、`[单测] backend API 数据层` | Task 6、Task 9 |

**不在本计划内**(等 spike 后再规划):Lane C 四个 Agent、Lane D 图编排+路由+真闭环、Lane E 后端 API+SSE、Lane F 前端。

---

## 文件结构(先定边界,再拆任务)

```
rivalradar/
  __init__.py
  config.py                 # env 读取 + get_doubao_client()
  schema/
    __init__.py
    models.py               # 全部 Pydantic 模型 + 受控本体常量
    feature_tree.py         # 扁平邻接表 → 嵌套树(D11)
    doubao_schema.py        # Pydantic 模型 → 无 $ref/$defs 的扁平 JSON Schema
  llm/
    __init__.py
    structured.py           # structured_call() + StructuredCallError
  storage/
    __init__.py
    db.py                   # SQLite 表结构 + 连接
    repository.py           # evidence/analysis/report/trace/runs 的 CRUD
    checkpointer.py         # SqliteSaver 工厂
spikes/
  spike_a_doubao_schema.py  # Day-1 spike A
  spike_b_search_extract.py # Day-1 spike B
  SPIKE_RESULTS.md          # spike 结论记录(go/no-go + 选型)
tests/
  test_models.py
  test_feature_tree.py
  test_doubao_schema.py
  test_structured_call.py
  test_config.py
  test_db.py
  test_repository.py
  test_checkpointer.py
pyproject.toml
.env.example
```

每个文件单一职责:`models.py` 只放数据形状,`doubao_schema.py` 只管"把 Pydantic schema 摊平成 Doubao 能吃的形状",`structured.py` 只管"调用+校验+重试",存储三件套按职责切开。

---

### Task 1: 项目脚手架 + 依赖 + 配置

**Files:**
- Create: `pyproject.toml`
- Create: `rivalradar/__init__.py`(空)
- Create: `rivalradar/schema/__init__.py`(空)
- Create: `rivalradar/llm/__init__.py`(空)
- Create: `rivalradar/storage/__init__.py`(空)
- Create: `rivalradar/config.py`
- Create: `.env.example`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写 `pyproject.toml`**

```toml
[project]
name = "rivalradar"
version = "0.1.0"
description = "AI 多 Agent 竞品分析协作系统"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.7",
    "openai>=1.40",
    "langgraph>=0.2",
    "langgraph-checkpoint-sqlite>=2.0",
    "python-dotenv>=1.0",
    "tavily-python>=0.5",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: 建空包文件**

`rivalradar/__init__.py`、`rivalradar/schema/__init__.py`、`rivalradar/llm/__init__.py`、`rivalradar/storage/__init__.py` 均写入单行注释即可:

```python
# RivalRadar package
```

- [ ] **Step 3: 写 `.env.example`**

```bash
# 火山方舟 Doubao(OpenAI 兼容端点)
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=${DOUBAO_MODEL}

# 搜索 API(spike B 选型,默认 Tavily)
TAVILY_API_KEY=

# 本地 SQLite
RIVALRADAR_DB=rivalradar.db
```

> `.env` / `.env.*` 已被仓库根 `.gitignore` 忽略,只有 `.env.example` 入库。

- [ ] **Step 4: 写失败测试 `tests/test_config.py`**

```python
from rivalradar import config


def test_default_doubao_model():
    assert config.DEFAULT_DOUBAO_MODEL == "${DOUBAO_MODEL}"


def test_get_doubao_client_uses_base_url(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "dummy-key")
    monkeypatch.setenv("ARK_BASE_URL", "https://example.test/api/v3")
    client = config.get_doubao_client()
    assert str(client.base_url).rstrip("/") == "https://example.test/api/v3"
```

- [ ] **Step 5: 跑测试确认失败**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError: module 'rivalradar.config' has no attribute ...`

- [ ] **Step 6: 写 `rivalradar/config.py`**

```python
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DOUBAO_MODEL = "${DOUBAO_MODEL}"


def ark_api_key() -> str | None:
    return os.getenv("ARK_API_KEY")


def ark_base_url() -> str:
    return os.getenv("ARK_BASE_URL", DEFAULT_BASE_URL)


def doubao_model() -> str:
    return os.getenv("DOUBAO_MODEL", DEFAULT_DOUBAO_MODEL)


def tavily_api_key() -> str | None:
    return os.getenv("TAVILY_API_KEY")


def db_path() -> str:
    return os.getenv("RIVALRADAR_DB", "rivalradar.db")


def get_doubao_client():
    from openai import OpenAI

    return OpenAI(api_key=ark_api_key(), base_url=ark_base_url())
```

- [ ] **Step 7: 跑测试确认通过**

Run: `pytest tests/test_config.py -v`
Expected: PASS(2 passed)

- [ ] **Step 8: 提交**

```bash
git add pyproject.toml rivalradar/__init__.py rivalradar/schema/__init__.py rivalradar/llm/__init__.py rivalradar/storage/__init__.py rivalradar/config.py .env.example tests/test_config.py
git commit -m "feat: project scaffold + config layer"
```

---

### Task 2: 知识 Schema 模型(Lane A 核心,spec §6)

**Files:**
- Create: `rivalradar/schema/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败测试 `tests/test_models.py`**

```python
import pytest
from pydantic import ValidationError

from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS,
    CompetitorAnalysis,
    CompetitorProfile,
    Evidence,
    EvidenceRef,
    FeatureItem,
    PricingModel,
    PricingTier,
    SWOT,
    SWOTPoint,
    UserPersona,
    ComparisonCell,
    ComparisonRow,
    QCIssue,
    QCResult,
)


def test_evidence_ref_defaults_to_supported():
    ref = EvidenceRef(evidence_id="e1", quote="支持每月 $10 起")
    assert ref.support_verdict == "supported"
    assert ref.start is None and ref.end is None


def test_evidence_rejects_unknown_language():
    with pytest.raises(ValidationError):
        Evidence(
            id="e1", competitor="Notion", dimension="pricing", content="...",
            source_url="https://notion.so/pricing", source_title="Pricing",
            language="fr", fetched_at="2026-05-25T00:00:00Z",
        )


def test_controlled_dimensions_has_six_axes():
    assert {
        "pricing", "deployment", "integrations",
        "target_users", "core_workflows", "review_sentiment",
    } <= set(CONTROLLED_DIMENSIONS)


def test_full_analysis_roundtrips_json():
    ref = EvidenceRef(evidence_id="e1", quote="免费版含无限页面", support_verdict="supported")
    profile = CompetitorProfile(
        name="Notion",
        features=[FeatureItem(id="f1", name="数据库", description="表格视图",
                              category="core_workflows", evidence_refs=[ref])],
        pricing=PricingModel(
            model_type="freemium",
            tiers=[PricingTier(name="Free", price="$0", billing_cycle="monthly")],
            evidence_refs=[ref],
        ),
        personas=[UserPersona(segment="个人用户", needs=["笔记"], evidence_refs=[ref])],
        swot=SWOT(strengths=[SWOTPoint(text="灵活", evidence_refs=[ref])]),
    )
    analysis = CompetitorAnalysis(
        competitors=[profile],
        comparison=[ComparisonRow(
            dimension="pricing",
            cells=[ComparisonCell(competitor="Notion", value_type="number",
                                  value="0", evidence_refs=[ref])],
        )],
    )
    restored = CompetitorAnalysis.model_validate_json(analysis.model_dump_json())
    assert restored == analysis


def test_qc_result_defaults_empty_issues():
    result = QCResult(verdict="pass")
    assert result.issues == []
    issue = QCIssue(competitor="Notion", dimension="pricing",
                    problem_type="missing_evidence", detail="无定价证据")
    assert issue.problem_type == "missing_evidence"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rivalradar.schema.models'`

- [ ] **Step 3: 写 `rivalradar/schema/models.py`**

```python
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Language = Literal["zh", "en"]
SupportVerdict = Literal["supported", "partial", "unsupported"]
ValueType = Literal["bool", "enum", "number", "quote_text"]
ProblemType = Literal[
    "missing_evidence", "schema_incomplete", "hallucination", "low_coverage"
]
QCVerdict = Literal["pass", "retry_collect", "retry_analyze", "insufficient_evidence"]

# 受控本体(spec §6 / Codex #3):对比维度只在这几个轴上展开,避免语义漂移
CONTROLLED_DIMENSIONS: tuple[str, ...] = (
    "pricing",
    "deployment",
    "integrations",
    "target_users",
    "core_workflows",
    "review_sentiment",
)


class Evidence(BaseModel):
    """证据块(采集产出)。"""

    id: str
    competitor: str
    dimension: str
    content: str
    source_url: str
    source_title: str
    language: Language
    fetched_at: str  # ISO 8601


class EvidenceRef(BaseModel):
    """句级引用:结论 → 证据的最小单元(spec §6 / Codex #2)。"""

    evidence_id: str
    quote: str
    start: Optional[int] = None
    end: Optional[int] = None
    support_verdict: SupportVerdict = "supported"


class FeatureItem(BaseModel):
    """功能项(扁平邻接表,parent_id 表达层级,D11)。"""

    id: str
    name: str
    description: str
    category: str
    parent_id: Optional[str] = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class PricingTier(BaseModel):
    name: str
    price: str
    billing_cycle: str
    features_included: list[str] = Field(default_factory=list)
    limits: str = ""


class PricingModel(BaseModel):
    model_type: str
    tiers: list[PricingTier] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class UserPersona(BaseModel):
    segment: str
    needs: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    praise: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SWOTPoint(BaseModel):
    text: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SWOT(BaseModel):
    strengths: list[SWOTPoint] = Field(default_factory=list)
    weaknesses: list[SWOTPoint] = Field(default_factory=list)
    opportunities: list[SWOTPoint] = Field(default_factory=list)
    threats: list[SWOTPoint] = Field(default_factory=list)


class CompetitorProfile(BaseModel):
    name: str
    features: list[FeatureItem] = Field(default_factory=list)
    pricing: PricingModel
    personas: list[UserPersona] = Field(default_factory=list)
    swot: SWOT


class ComparisonCell(BaseModel):
    """类型化对比值,避免鸡同鸭比(spec §6 / Codex #3)。value 一律存字符串,由 value_type 决定解读。"""

    competitor: str
    value_type: ValueType
    value: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    dimension: str  # 受控本体之一
    cells: list[ComparisonCell] = Field(default_factory=list)


class CompetitorAnalysis(BaseModel):
    competitors: list[CompetitorProfile] = Field(default_factory=list)
    comparison: list[ComparisonRow] = Field(default_factory=list)


class QCIssue(BaseModel):
    competitor: str
    dimension: str
    problem_type: ProblemType
    detail: str


class QCResult(BaseModel):
    verdict: QCVerdict
    issues: list[QCIssue] = Field(default_factory=list)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_models.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: 提交**

```bash
git add rivalradar/schema/models.py tests/test_models.py
git commit -m "feat: knowledge schema pydantic models with evidence refs"
```

---

### Task 3: 功能树拼装(扁平邻接表 → 嵌套,D11)

**Files:**
- Create: `rivalradar/schema/feature_tree.py`
- Test: `tests/test_feature_tree.py`

- [ ] **Step 1: 写失败测试 `tests/test_feature_tree.py`**

```python
import pytest

from rivalradar.schema.feature_tree import assemble_tree
from rivalradar.schema.models import FeatureItem


def _item(id_, parent=None):
    return FeatureItem(id=id_, name=id_, description="", category="core_workflows", parent_id=parent)


def test_assemble_nests_children_under_parents():
    items = [_item("root"), _item("child", parent="root"), _item("root2")]
    tree = assemble_tree(items)
    assert [n["item"].id for n in tree] == ["root", "root2"]
    assert tree[0]["children"][0]["item"].id == "child"
    assert tree[0]["children"][0]["children"] == []


def test_orphan_parent_id_becomes_root():
    items = [_item("a", parent="does-not-exist")]
    tree = assemble_tree(items)
    assert [n["item"].id for n in tree] == ["a"]


def test_cycle_raises_value_error():
    items = [_item("a", parent="b"), _item("b", parent="a")]
    with pytest.raises(ValueError):
        assemble_tree(items)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_feature_tree.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rivalradar.schema.feature_tree'`

- [ ] **Step 3: 写 `rivalradar/schema/feature_tree.py`**

```python
from __future__ import annotations

from rivalradar.schema.models import FeatureItem


def assemble_tree(items: list[FeatureItem]) -> list[dict]:
    """把扁平 FeatureItem 列表拼成嵌套树。

    返回根节点列表,每个节点为 {"item": FeatureItem, "children": [...]}。
    - parent_id 指向不存在的项 → 视为根(防御 LLM 漏输出父项)。
    - 检测到环 → 抛 ValueError(LLM 可能产出 a->b->a)。
    """
    by_id = {it.id: {"item": it, "children": []} for it in items}
    roots: list[dict] = []
    for it in items:
        node = by_id[it.id]
        parent = by_id.get(it.parent_id) if it.parent_id else None
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)

    _assert_acyclic(roots)
    return roots


def _assert_acyclic(roots: list[dict]) -> None:
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node: dict) -> None:
        nid = node["item"].id
        if nid in visiting:
            raise ValueError(f"feature tree has a cycle at {nid!r}")
        if nid in done:
            return
        visiting.add(nid)
        for child in node["children"]:
            walk(child)
        visiting.discard(nid)
        done.add(nid)

    for root in roots:
        walk(root)
```

> 注意:`assemble_tree` 用单遍 by_id 建边,环不会在建边阶段无限循环;`_assert_acyclic` 用 DFS 三色检测显式拦环。对 `test_cycle_raises_value_error`,a 与 b 互为父,二者都不是根 → `roots` 为空 → 不报错。所以环检测必须在所有节点上跑,不能只从 roots 出发。修正见下一步。

- [ ] **Step 4: 跑测试,定位环检测漏洞**

Run: `pytest tests/test_feature_tree.py::test_cycle_raises_value_error -v`
Expected: FAIL —— a/b 互为父时都不是根,`roots=[]`,DFS 不会访问到它们,环漏检。

- [ ] **Step 5: 修正环检测,改为遍历全部节点**

把 `_assert_acyclic` 的入口从"只遍历 roots"改成"遍历所有节点",并用沿途路径判环:

```python
def _assert_acyclic(by_id: dict[str, dict]) -> None:
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node: dict) -> None:
        nid = node["item"].id
        if nid in visiting:
            raise ValueError(f"feature tree has a cycle at {nid!r}")
        if nid in done:
            return
        visiting.add(nid)
        for child in node["children"]:
            walk(child)
        visiting.discard(nid)
        done.add(nid)

    for node in by_id.values():
        walk(node)
```

并把 `assemble_tree` 里的调用改为 `_assert_acyclic(by_id)`(传整个 map,而非 roots)。

- [ ] **Step 6: 跑全部测试确认通过**

Run: `pytest tests/test_feature_tree.py -v`
Expected: PASS(3 passed)

- [ ] **Step 7: 提交**

```bash
git add rivalradar/schema/feature_tree.py tests/test_feature_tree.py
git commit -m "feat: flat adjacency-list feature tree assembly with cycle guard"
```

---

### Task 4: Doubao schema 派生(摊平 $ref/$defs)

**Files:**
- Create: `rivalradar/schema/doubao_schema.py`
- Test: `tests/test_doubao_schema.py`

- [ ] **Step 1: 写失败测试 `tests/test_doubao_schema.py`**

```python
import json

from rivalradar.schema.doubao_schema import to_doubao_schema
from rivalradar.schema.models import CompetitorProfile, EvidenceRef


def test_evidence_ref_schema_has_properties():
    schema = to_doubao_schema(EvidenceRef)
    assert schema["type"] == "object"
    assert "evidence_id" in schema["properties"]
    assert "quote" in schema["properties"]


def test_nested_schema_has_no_refs_or_defs():
    schema = to_doubao_schema(CompetitorProfile)
    blob = json.dumps(schema)
    assert "$ref" not in blob
    assert "$defs" not in schema
    # 嵌套子模型被内联展开:features 的 item 仍带 evidence_refs 结构
    features = schema["properties"]["features"]
    assert features["type"] == "array"
    item_props = features["items"]["properties"]
    assert "parent_id" in item_props
    assert "evidence_refs" in item_props
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_doubao_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rivalradar.schema.doubao_schema'`

- [ ] **Step 3: 写 `rivalradar/schema/doubao_schema.py`**

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any


def to_doubao_schema(model_cls) -> dict[str, Any]:
    """把 Pydantic 模型转成 Doubao json_schema 能稳定消费的形状。

    Pydantic 默认把嵌套子模型抽成 $defs + $ref。我们的 Schema 是扁平的
    (FeatureItem 用 parent_id 表层级,而非自引用),所以非递归,可以安全地
    把所有 $ref 内联展开,送一份自包含、无 $ref/$defs 的 schema(spec §9 / D11)。
    """
    schema = model_cls.model_json_schema()
    defs = schema.get("$defs", {})
    inlined = _inline(schema, defs)
    inlined.pop("$defs", None)
    return inlined


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            return _inline(deepcopy(defs[name]), defs)
        return {k: _inline(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline(x, defs) for x in node]
    return node
```

> 前提:我们的模型**无递归引用**(已由 D11 扁平化保证)。若未来引入自引用模型,`_inline` 会无限递归,需改为有限深度展开。这是 spike A 的验证点之一。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_doubao_schema.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 提交**

```bash
git add rivalradar/schema/doubao_schema.py tests/test_doubao_schema.py
git commit -m "feat: inline pydantic schema to ref-free shape for doubao"
```

---

### Task 5: 🚧 GATE — Spike A:Doubao 扁平 Schema 结构化输出实测(spec §15)

**这是 go/no-go 闸门,不是 TDD。** 需要真实 `ARK_API_KEY`。验证 Doubao 能否对我们真正要用的扁平 Schema 稳定吐出合法结构化输出。

**Files:**
- Create: `spikes/spike_a_doubao_schema.py`
- Create: `spikes/SPIKE_RESULTS.md`

- [ ] **Step 1: 确认 key 就绪**

Run: `python -c "from rivalradar import config; assert config.ark_api_key(), 'set ARK_API_KEY in .env'; print('ARK key OK')"`
Expected: 打印 `ARK key OK`。若报错,先在 `.env` 填 `ARK_API_KEY`(火山方舟控制台获取)。

- [ ] **Step 2: 写 `spikes/spike_a_doubao_schema.py`**

```python
"""Spike A:实测 Doubao 能否对扁平 Schema 稳定吐合法结构化输出。

跑 N 次,统计成功解析率、平均耗时、平均 token。决策规则见 SPIKE_RESULTS.md。
"""
from __future__ import annotations

import json
import time

from pydantic import BaseModel, ValidationError

from rivalradar import config
from rivalradar.schema.doubao_schema import to_doubao_schema
from rivalradar.schema.models import FeatureItem

N_RUNS = 5

# 真实证据片段(Notion 功能页节选,英文),让 Doubao 抽成扁平 FeatureItem
EVIDENCE = (
    "Notion combines notes, docs, wikis, and projects. Databases support table, "
    "board, calendar, gallery, and timeline views. Sub-items let you nest tasks "
    "under a parent task. AI features include writing assistance and Q&A."
)


class FeatureList(BaseModel):
    items: list[FeatureItem]


def run_once() -> tuple[bool, float, int]:
    client = config.get_doubao_client()
    schema = to_doubao_schema(FeatureList)
    messages = [
        {"role": "system", "content": "你是竞品功能抽取器。只输出 JSON,符合给定 schema。"
                                       "用 parent_id 表达功能的父子层级,顶层功能 parent_id 为 null。"},
        {"role": "user", "content": f"从下面文本抽取功能项(category 用 core_workflows):\n{EVIDENCE}"},
    ]
    t0 = time.time()
    resp = client.chat.completions.create(
        model=config.doubao_model(),
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "FeatureList", "schema": schema},
        },
    )
    latency = time.time() - t0
    tokens = getattr(resp.usage, "total_tokens", 0) if resp.usage else 0
    raw = resp.choices[0].message.content
    try:
        parsed = FeatureList.model_validate(json.loads(raw))
        ok = len(parsed.items) >= 1
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"  parse failed: {e}\n  raw: {raw[:300]}")
        ok = False
    return ok, latency, tokens


def main() -> None:
    results = []
    for i in range(N_RUNS):
        print(f"run {i + 1}/{N_RUNS} ...")
        results.append(run_once())
    oks = sum(1 for ok, _, _ in results if ok)
    avg_latency = sum(l for _, l, _ in results) / len(results)
    avg_tokens = sum(t for _, _, t in results) / len(results)
    print("\n=== SPIKE A RESULT ===")
    print(f"parse success: {oks}/{N_RUNS}")
    print(f"avg latency:   {avg_latency:.2f}s")
    print(f"avg tokens:    {avg_tokens:.0f}")
    print("decision: GO if >=4/5 parse cleanly; else investigate strict/additionalProperties/flatten")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 跑 spike**

Run: `python spikes/spike_a_doubao_schema.py`
Expected: 打印 `parse success: X/5` + 平均耗时/token。

- [ ] **Step 4: 判定并记录**

判定规则:
- **GO**(≥4/5 成功):扁平 Schema + `response_format=json_schema` 路线成立,Task 6 的 `structured_call` 默认参数就用这套。
- **NO-GO / 部分**(<4/5):依次尝试 ① 给 `json_schema` 加 `"strict": True` 并让 `to_doubao_schema` 补 `additionalProperties: false` + 把可选字段并入 `required`;② 退化到 `response_format={"type":"json_object"}` + 在 prompt 内贴 schema;③ 进一步摊平模型。把实测结论回填到 Task 6。

把结论写进 `spikes/SPIKE_RESULTS.md`:

```markdown
# SPIKE RESULTS

## Spike A — Doubao 扁平 Schema 结构化输出(2026-05-2X)
- 解析成功率:X/5
- 平均耗时:X.Xs / 平均 token:XXX
- 判定:GO / NO-GO
- 采用的 response_format:json_schema(非 strict) / json_schema strict / json_object
- 备注:<是否需要 strict、是否需要 additionalProperties、踩到的坑>
```

- [ ] **Step 5: 提交**

```bash
git add spikes/spike_a_doubao_schema.py spikes/SPIKE_RESULTS.md
git commit -m "spike: doubao flat-schema structured output reachability (go/no-go)"
```

---

### Task 6: `structured_call` 封装(校验+重试+显式报错,spec §9 ★关键)

**Files:**
- Create: `rivalradar/llm/structured.py`
- Test: `tests/test_structured_call.py`

> response_format 的具体参数以 Task 5 spike A 的判定为准;下方默认走 `json_schema`(非 strict),与 spike A 的 GO 分支一致。重试逻辑本身用 FakeClient 离线测,不碰网络。

- [ ] **Step 1: 写失败测试 `tests/test_structured_call.py`**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_structured_call.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rivalradar.llm.structured'`

- [ ] **Step 3: 写 `rivalradar/llm/structured.py`**

```python
from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from rivalradar.schema.doubao_schema import to_doubao_schema

T = TypeVar("T", bound=BaseModel)


class StructuredCallError(RuntimeError):
    """结构化调用在重试封顶后仍失败 —— 显式抛出,绝不静默吞掉(spec §9)。"""


def structured_call(
    model_cls: type[T],
    messages: list[dict],
    *,
    client,
    model: str,
    max_retries: int = 2,
) -> T:
    """调 Doubao 吐结构化输出 → Pydantic 校验 → 不合格带错重试 → 封顶显式报错。

    被 4 个 Agent 复用(DRY)。max_retries=2 表示最多 3 次尝试。
    """
    schema = to_doubao_schema(model_cls)
    convo = list(messages)
    last_err: Exception | None = None

    for _ in range(max_retries + 1):
        resp = client.chat.completions.create(
            model=model,
            messages=convo,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": model_cls.__name__, "schema": schema},
            },
        )
        raw = resp.choices[0].message.content
        try:
            return model_cls.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as err:
            last_err = err
            convo = convo + [
                {"role": "assistant", "content": raw or ""},
                {
                    "role": "user",
                    "content": (
                        f"上次输出未通过校验:{err}\n"
                        "只返回符合 schema 的合法 JSON,不要任何额外文字。"
                    ),
                },
            ]

    raise StructuredCallError(
        f"structured_call({model_cls.__name__}) 在 {max_retries + 1} 次尝试后仍失败:{last_err}"
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_structured_call.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add rivalradar/llm/structured.py tests/test_structured_call.py
git commit -m "feat: structured_call wrapper with validate-retry and explicit failure"
```

---

### Task 7: 🚧 GATE — Spike B:搜索/抽取 API 可达性 + 质量(spec §7/§14)

**这是 go/no-go 闸门,不是 TDD。** 需要真实 `TAVILY_API_KEY`。对 1 中 1 英竞品各 5 查询,验"能否抓到" + "是否权威/最新/可比/可抽取"(Codex #4),并据此锁定搜索/抽取 API 选型、来源优先级、demo 竞品名单。

**Files:**
- Create: `spikes/spike_b_search_extract.py`
- Modify: `spikes/SPIKE_RESULTS.md`(追加 Spike B 段)

- [ ] **Step 1: 确认 key 就绪**

Run: `python -c "from rivalradar import config; assert config.tavily_api_key(), 'set TAVILY_API_KEY in .env'; print('Tavily key OK')"`
Expected: 打印 `Tavily key OK`。若无 key,去 tavily.com 注册(有免费额度)后填入 `.env`。

- [ ] **Step 2: 写 `spikes/spike_b_search_extract.py`**

```python
"""Spike B:搜索/抽取 API 对真实竞品的可达性 + 质量实测。

对 1 英(Notion)+ 1 中(飞书)竞品各跑 5 个维度查询,记录:
命中数 / 是否拿到正文(可抽取) / 是否命中官方域名(权威) / 是否有发布日期(新鲜度)。
默认用 Tavily(search + include_raw_content 一次拿到正文,省一个独立抽取层)。
"""
from __future__ import annotations

from tavily import TavilyClient

from rivalradar import config

PROBES = {
    "Notion (en)": [
        "Notion pricing plans 2026",
        "Notion features database views",
        "Notion integrations list",
        "Notion reviews G2",
        "Notion enterprise deployment SSO",
    ],
    "飞书 Lark (zh)": [
        "飞书 价格 套餐 2026",
        "飞书 功能 多维表格",
        "飞书 集成 应用",
        "飞书 用户评价 知乎",
        "飞书 企业版 部署 SSO",
    ],
}
OFFICIAL_DOMAINS = ("notion.so", "notion.com", "feishu.cn", "larksuite.com")


def run_probe(client: TavilyClient, query: str) -> dict:
    resp = client.search(query=query, max_results=5, include_raw_content=True)
    results = resp.get("results", [])
    return {
        "query": query,
        "hits": len(results),
        "extractable": sum(1 for r in results if r.get("raw_content")),
        "official": sum(1 for r in results if any(d in r.get("url", "") for d in OFFICIAL_DOMAINS)),
        "dated": sum(1 for r in results if r.get("published_date")),
        "top_url": results[0]["url"] if results else "—",
    }


def main() -> None:
    client = TavilyClient(api_key=config.tavily_api_key())
    for competitor, queries in PROBES.items():
        print(f"\n=== {competitor} ===")
        for q in queries:
            r = run_probe(client, q)
            print(f"  [{r['hits']}h {r['extractable']}ext {r['official']}off {r['dated']}dated] "
                  f"{r['query']}  ->  {r['top_url']}")
    print("\ndecision: GO if 每个竞品都拿到 >=1 官方权威源 + 评价面可抽取正文")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 跑 spike**

Run: `python spikes/spike_b_search_extract.py`
Expected: 两个竞品各 5 行,每行带 `[命中数 可抽取数 官方源数 带日期数]`。

- [ ] **Step 4: 判定并记录**

判定规则(对照 spec §7 来源优先级:官方定价/功能页 > 评价平台 > 搜索结果):
- **GO**:每个竞品至少 1 个官方权威源(命中 OFFICIAL_DOMAINS)+ 评价面能拿到可抽取正文。
- **关注点**:中文评价站(知乎/小红书)很可能命中少或无正文(登录墙/反爬)——按 spec §7,这是**预期**,改用 App Store/Google Play/G2 等可达评价面,知乎/小红书作尽力而为,不强制纳入覆盖度。
- **NO-GO**:若 Tavily 对中文竞品几乎全空,切 Exa(`exa-py`)或 Firecrawl 再跑一遍同一组 PROBES 对比。

把结论追加进 `spikes/SPIKE_RESULTS.md`:

```markdown
## Spike B — 搜索/抽取 API 可达性+质量(2026-05-2X)
- 选定搜索/抽取 API:Tavily / Exa / Firecrawl
- Notion:官方源命中 X/5,可抽取 X/5
- 飞书:官方源命中 X/5,可抽取 X/5;中文评价站可达性:<结论>
- 来源优先级(确认):官方页 > <可达评价面> > 搜索结果
- 新鲜度:<是否普遍有 published_date>
- demo 竞品名单(锁定):<最终选哪几个>
- 受控本体覆盖(锁定):pricing/deployment/integrations/target_users/core_workflows/review_sentiment 各能否取到源
```

- [ ] **Step 5: 提交**

```bash
git add spikes/spike_b_search_extract.py spikes/SPIKE_RESULTS.md
git commit -m "spike: search/extract API reachability + quality (go/no-go)"
```

---

### Task 8: SQLite 表结构与连接(Lane B,spec §10)

**Files:**
- Create: `rivalradar/storage/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: 写失败测试 `tests/test_db.py`**

```python
from rivalradar.storage.db import connect, init_db


def test_init_db_creates_all_tables():
    conn = connect(":memory:")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"runs", "evidence", "analysis", "report", "trace"} <= names


def test_connect_uses_row_factory():
    conn = connect(":memory:")
    init_db(conn)
    conn.execute(
        "INSERT INTO runs (run_id, competitors, dimensions, status, created_at) "
        "VALUES ('r1', '[]', '[]', 'running', '2026-05-25T00:00:00Z')"
    )
    row = conn.execute("SELECT run_id FROM runs WHERE run_id='r1'").fetchone()
    assert row["run_id"] == "r1"  # row_factory=Row 才能按列名取
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rivalradar.storage.db'`

- [ ] **Step 3: 写 `rivalradar/storage/db.py`**

```python
from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    competitors TEXT NOT NULL,
    dimensions  TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    competitor   TEXT NOT NULL,
    dimension    TEXT NOT NULL,
    content      TEXT NOT NULL,
    source_url   TEXT NOT NULL,
    source_title TEXT NOT NULL,
    language     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analysis (
    run_id     TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report (
    run_id     TEXT PRIMARY KEY,
    markdown   TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trace (
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
CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_trace_run ON trace(run_id);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_db.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 提交**

```bash
git add rivalradar/storage/db.py tests/test_db.py
git commit -m "feat: sqlite schema for evidence/analysis/report/trace/runs"
```

---

### Task 9: 存储仓库 CRUD(Lane B,spec §10 + §13 数据层)

**Files:**
- Create: `rivalradar/storage/repository.py`
- Test: `tests/test_repository.py`

- [ ] **Step 1: 写失败测试 `tests/test_repository.py`**

```python
import pytest

from rivalradar.schema.models import (
    CompetitorAnalysis,
    CompetitorProfile,
    Evidence,
    PricingModel,
    SWOT,
)
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


def _evidence(eid="e1"):
    return Evidence(
        id=eid, competitor="Notion", dimension="pricing", content="$10/mo",
        source_url="https://notion.so/pricing", source_title="Pricing",
        language="en", fetched_at="2026-05-25T00:00:00Z",
    )


def test_evidence_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.insert_evidence(conn, "r1", _evidence("e1"))
    repo.insert_evidence(conn, "r1", _evidence("e2"))
    got = repo.get_evidence(conn, "e1")
    assert got == _evidence("e1")
    assert {e.id for e in repo.list_evidence(conn, "r1")} == {"e1", "e2"}


def test_get_missing_evidence_returns_none(conn):
    assert repo.get_evidence(conn, "nope") is None


def test_analysis_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="freemium"), swot=SWOT(),
    )])
    repo.save_analysis(conn, "r1", analysis)
    assert repo.get_analysis(conn, "r1") == analysis


def test_report_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.save_report(conn, "r1", "# Notion\n...")
    assert repo.get_report(conn, "r1") == "# Notion\n..."


def test_trace_append_preserves_order(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.append_trace(conn, "r1", "collect", prompt="p1", input_summary="i1",
                      output_summary="o1", tokens=100, latency_ms=1200)
    repo.append_trace(conn, "r1", "analyze", prompt="p2", input_summary="i2",
                      output_summary="o2", tokens=200, latency_ms=2400)
    rows = repo.list_trace(conn, "r1")
    assert [t["node"] for t in rows] == ["collect", "analyze"]
    assert rows[0]["tokens"] == 100


def test_run_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion", "飞书"], ["pricing", "features"])
    run = repo.get_run(conn, "r1")
    assert run["competitors"] == ["Notion", "飞书"]
    assert run["status"] == "running"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rivalradar.storage.repository'`

- [ ] **Step 3: 写 `rivalradar/storage/repository.py`**

```python
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from rivalradar.schema.models import CompetitorAnalysis, Evidence


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- runs ----
def create_run(conn: sqlite3.Connection, run_id: str,
               competitors: list[str], dimensions: list[str]) -> None:
    conn.execute(
        "INSERT INTO runs (run_id, competitors, dimensions, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, json.dumps(competitors), json.dumps(dimensions), "running", _now()),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "competitors": json.loads(row["competitors"]),
        "dimensions": json.loads(row["dimensions"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }


# ---- evidence ----
def insert_evidence(conn: sqlite3.Connection, run_id: str, ev: Evidence) -> None:
    conn.execute(
        "INSERT INTO evidence (id, run_id, competitor, dimension, content, "
        "source_url, source_title, language, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ev.id, run_id, ev.competitor, ev.dimension, ev.content,
         ev.source_url, ev.source_title, ev.language, ev.fetched_at),
    )
    conn.commit()


def get_evidence(conn: sqlite3.Connection, evidence_id: str) -> Evidence | None:
    row = conn.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
    if row is None:
        return None
    return Evidence(
        id=row["id"], competitor=row["competitor"], dimension=row["dimension"],
        content=row["content"], source_url=row["source_url"],
        source_title=row["source_title"], language=row["language"],
        fetched_at=row["fetched_at"],
    )


def list_evidence(conn: sqlite3.Connection, run_id: str) -> list[Evidence]:
    rows = conn.execute("SELECT * FROM evidence WHERE run_id=? ORDER BY id", (run_id,))
    return [
        Evidence(
            id=r["id"], competitor=r["competitor"], dimension=r["dimension"],
            content=r["content"], source_url=r["source_url"],
            source_title=r["source_title"], language=r["language"],
            fetched_at=r["fetched_at"],
        )
        for r in rows
    ]


# ---- analysis ----
def save_analysis(conn: sqlite3.Connection, run_id: str,
                  analysis: CompetitorAnalysis) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO analysis (run_id, payload, created_at) VALUES (?, ?, ?)",
        (run_id, analysis.model_dump_json(), _now()),
    )
    conn.commit()


def get_analysis(conn: sqlite3.Connection, run_id: str) -> CompetitorAnalysis | None:
    row = conn.execute("SELECT payload FROM analysis WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return CompetitorAnalysis.model_validate_json(row["payload"])


# ---- report ----
def save_report(conn: sqlite3.Connection, run_id: str, markdown: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO report (run_id, markdown, created_at) VALUES (?, ?, ?)",
        (run_id, markdown, _now()),
    )
    conn.commit()


def get_report(conn: sqlite3.Connection, run_id: str) -> str | None:
    row = conn.execute("SELECT markdown FROM report WHERE run_id=?", (run_id,)).fetchone()
    return row["markdown"] if row else None


# ---- trace ----
def append_trace(conn: sqlite3.Connection, run_id: str, node: str, *,
                 prompt: str = "", input_summary: str = "", output_summary: str = "",
                 tokens: int = 0, latency_ms: int = 0) -> None:
    conn.execute(
        "INSERT INTO trace (run_id, node, prompt, input_summary, output_summary, "
        "tokens, latency_ms, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, node, prompt, input_summary, output_summary, tokens, latency_ms, _now()),
    )
    conn.commit()


def list_trace(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM trace WHERE run_id=? ORDER BY id", (run_id,))
    return [dict(r) for r in rows]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_repository.py -v`
Expected: PASS(6 passed)

- [ ] **Step 5: 提交**

```bash
git add rivalradar/storage/repository.py tests/test_repository.py
git commit -m "feat: storage repository CRUD for all tables"
```

---

### Task 10: LangGraph SqliteSaver checkpointer 工厂(Lane B,spec §10)

**Files:**
- Create: `rivalradar/storage/checkpointer.py`
- Test: `tests/test_checkpointer.py`

- [ ] **Step 1: 写失败测试 `tests/test_checkpointer.py`**

```python
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from rivalradar.storage.checkpointer import make_checkpointer


class _State(TypedDict):
    count: Annotated[int, operator.add]


def _inc(state: _State) -> dict:
    return {"count": 1}


def test_checkpointer_persists_state_across_invokes():
    saver = make_checkpointer(":memory:")
    builder = StateGraph(_State)
    builder.add_node("inc", _inc)
    builder.add_edge(START, "inc")
    builder.add_edge("inc", END)
    app = builder.compile(checkpointer=saver)

    cfg = {"configurable": {"thread_id": "t1"}}
    app.invoke({"count": 0}, cfg)
    app.invoke({"count": 0}, cfg)

    # 同 thread_id 二次 invoke,count 通过 checkpoint + reducer 累加证明状态被持久化
    assert app.get_state(cfg).values["count"] == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_checkpointer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rivalradar.storage.checkpointer'`

- [ ] **Step 3: 写 `rivalradar/storage/checkpointer.py`**

```python
from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver


def make_checkpointer(path: str) -> SqliteSaver:
    """建一个长驻的 SqliteSaver(打回重跑可恢复,spec §10)。

    持久化场景不用 from_conn_string 上下文管理器(那会随 with 结束关连接),
    而是直接把一个 check_same_thread=False 的连接交给 SqliteSaver,再 setup() 建表。
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_checkpointer.py -v`
Expected: PASS(1 passed)

> 若 `from langgraph.checkpoint.sqlite import SqliteSaver` 报 ImportError:确认 `langgraph-checkpoint-sqlite` 已随 Task 1 的 `pip install -e ".[dev]"` 装上(`pip show langgraph-checkpoint-sqlite`)。

- [ ] **Step 5: 全量回归 + 提交**

Run: `pytest -v`
Expected: 全部 PASS(config 2 + models 5 + feature_tree 3 + doubao_schema 2 + structured_call 3 + db 2 + repository 6 + checkpointer 1 = 24 passed)

```bash
git add rivalradar/storage/checkpointer.py tests/test_checkpointer.py
git commit -m "feat: langgraph sqlite checkpointer factory"
```

---

## 环境准备(执行本计划前一次性)

```bash
# 在仓库根
python -m venv .venv && source .venv/bin/activate   # 或你惯用的环境
pip install -e ".[dev]"                              # Task 1 的 pyproject 落地后
cp .env.example .env                                 # 填 ARK_API_KEY / TAVILY_API_KEY(spike 才需要)
```

> `.venv/` 建议加进 `.gitignore`(当前只忽略 `.gstack/` 和 `.env*`)。这一条改动很小,执行 Task 1 时顺手加上。

---

## Self-Review(写完计划后的自查)

**1. Spec 覆盖**
- §6 Schema → Task 2 ✅;EvidenceRef 句级引用 → Task 2 ✅;扁平功能树拼装(D11)→ Task 3 ✅
- §9 structured_call(校验/重试/显式报错)→ Task 6 ✅;schema 摊平 → Task 4 ✅
- §10 存储五表 → Task 8/9 ✅;SqliteSaver → Task 10 ✅
- §13 `[单测] structured_call`→ Task 6 ✅;数据层 GET evidence/report/trace → Task 9 ✅
- §15 Day-1 spike A → Task 5 ✅;§7/§14 spike B → Task 7 ✅
- **本计划范围外(已声明)**:Lane C 四 Agent、Lane D 图编排+路由+真闭环、Lane E API+SSE、Lane F 前端、§13 真闭环回归测试、§17 指标面板。等 spike 结论锁定后另出计划——这是"地基优先分阶段"的有意取舍。

**2. 占位符扫描**:无 TBD / "appropriate error handling" / "similar to Task N"。每个改代码的步骤都给了完整代码。spike 的 response_format 调参显式指向 Task 5 的判定,不是占位。

**3. 类型一致性**(跨任务核对):
- `Evidence` / `EvidenceRef` / `CompetitorAnalysis` 字段在 Task 2 定义,Task 9 repository 按同名字段读写 ✅
- `structured_call(model_cls, messages, *, client, model, max_retries=2)` 签名在 Task 6 定义,测试调用一致 ✅
- `to_doubao_schema(model_cls)` 在 Task 4 定义,Task 5 spike 与 Task 6 structured_call 均按此调用 ✅
- `connect` / `init_db` 在 Task 8 定义,Task 9/10 测试 fixture 一致使用 ✅
- repository 函数名(`create_run`/`insert_evidence`/`get_evidence`/`list_evidence`/`save_analysis`/`get_analysis`/`save_report`/`get_report`/`append_trace`/`list_trace`/`get_run`)测试与实现逐一对齐 ✅
- `make_checkpointer(path)` 在 Task 10 定义,测试一致 ✅

**4. 已知风险**:Task 3 的环检测在 Step 3 故意先写一版有漏洞的实现,Step 4 跑测试暴露、Step 5 修正——这是真实 TDD 节奏,不是错误。
