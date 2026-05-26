# RivalRadar Lane D 实现计划:LangGraph 图编排 + 路由 + 真闭环

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已建成的四个 Agent(采集/分析/撰写/质检)用 LangGraph 状态图串成**真闭环**:质检打回 → 按缺口只补采(广搜换查询,证据累加不覆盖)→ 重新分析 → 第二遍因证据更多而真改善;有界重试耗尽则诚实降级。这是评分 35% 的命门。

**Architecture:** `StateGraph(ResearchState)`,拓扑 `START→collect→analyze→write→qc→[条件边]`。`qc` 的条件边读 `decide_route(verdict, retry_count, max_retries)`:`pass`/超限→`finalize`;`retry_collect`→`collect`;`retry_analyze`→`analyze`。共享状态用 **dict 原语**(checkpoint 零序列化风险);`evidence` 用自定义 reducer 按 id 去重累加。节点依赖(conn/client/model/provider)用**闭包工厂**注入,`run_id` 取自 `config` 的 `thread_id`。质检节点捕获 `StructuredCallError` 把 LLM 蕴含降级为「仅确定性闸」。

**Tech Stack:** LangGraph 1.2.1(`StateGraph`/`START`/`END`/`add_conditional_edges`/`compile`)、langgraph-checkpoint-sqlite 3.1.0(`SqliteSaver`,经 `rivalradar/storage/checkpointer.py:make_checkpointer`)、Pydantic v2、SQLite(`rivalradar/storage/repository.py`)、pytest。

---

## 关键设计决策(执行者必读)

这些决策已经过 spec 对齐 + context7(LangGraph 官方 + Corrective RAG 范式)+ 用户拍板,**不要在执行时擅自改动**:

1. **state 用 dict 原语,不放 Pydantic 对象。** 实测 LangGraph 1.2.1 的 `JsonPlusSerializer` 反序列化未注册 Pydantic 类型会打印 deprecation 警告且「未来版本会 block」。35% 命门不赌。所以 `ResearchState` 里 `evidence` 是 `list[dict]`(`Evidence.model_dump()`),`analysis`/`qc_result` 是 `dict`。节点边界做 `Evidence(**d)` / `.model_dump()` 转换。

2. **`evidence` 用自定义 reducer `merge_evidence` 按 id 去重累加(不是 `operator.add`)。** `_evidence_id = sha1(competitor|dimension|url)`,所以**换源(新 url)→ 新 id → 真累加**;**同源重采 → 同 id → 去重不增**。这把 spec §8「证据累加不覆盖」+「真改善 ⟺ 换源」做成机制保证,直接喂 §13 ★★★ 回归断言。

3. **`retry_count` 只在 qc 节点递增,且「带着上一轮 qc_result 进来才 +1」。** 若 collect 和 analyze 各自递增,一次 `retry_collect`(走 `collect→analyze`)会双重计数。qc 每轮恰好跑一次,是唯一安全的计数点。结果:`retry_count` 干净等于「已重试次数」(首遍 = 0),`decide_route` 用 `>=` 判超限。

4. **QC 节点在 Lane D 层组合 `qc.py` 的子函数 + 降级,不调 `qc.check`,不改 `qc.py`。** `qc.check` 会上抛 `StructuredCallError`(其 docstring 已写明「降级是 Lane D 的活」)。QC 节点:确定性三闸(traceability/ontology/coverage)始终跑;`check_entailment` 包在 `try/except StructuredCallError`,失败则 `degraded=True` + 记 trace,verdict 仅由确定性闸决定(必办项①)。

5. **广搜 = broaden 查询变体(CRAG `transform_query`)。** retry 时对缺口维度用 broaden 查询词(加「评测/对比/替代」后缀)。换 provider(Tavily↔Exa)作为增强**标 TODO**,不做进 Lane D 必做。

6. **`insufficient_evidence` 由 `finalize` 节点赋予,不由 `decide_verdict` 产出。** 重试耗尽时 `decide_route→finalize`;finalize 看最后 verdict:`retry_collect` 类耗尽 → 改写为 `insufficient_evidence` + report 加「未找到公开数据」banner;`retry_analyze` 类耗尽 → 降级 banner「未达质检标准」(必办项③)。

7. **trace 只写 SQLite(`append_trace`),state 不放 `trace[]`。** SQLite trace 表(带 ts 排序)覆盖 Lane E/F 的可观测/DAG 回放需求;checkpointer 已存每步 state 快照。state 不放 trace 让 checkpoint 更轻(对 spec §4 的 state 草图是有意简化)。

8. **★★★ 真闭环回归测 Lane D 编排本身,agents 作测试替身。** 用 `FakeProvider`(真走 collect 管线 → 证据累加是真的)+ monkeypatch 假 `analyze`/`write_report`/`qc.check_entailment`。确定性三闸(coverage 等,Lane C 已绿、快、确定)**真跑**,驱动路由。这样测的是 Lane D 的图/路由/累加/缺口提取,而不是重测 agents。

---

## File Structure

**新建** `rivalradar/graph/` 包:
- `rivalradar/graph/__init__.py` — 空包标记。
- `rivalradar/graph/state.py` — `ResearchState`(TypedDict)+ `merge_evidence` reducer。
- `rivalradar/graph/router.py` — `decide_route`(纯路由)+ `extract_collect_targets`(缺口提取)。两者纯逻辑,§13 ★必测。
- `rivalradar/graph/nodes.py` — 五个节点工厂 `make_collect_node/make_analyze_node/make_write_node/make_qc_node/make_finalize_node`。
- `rivalradar/graph/build.py` — `build_research_graph`(组装+编译)+ `run_research`(入口:create_run + invoke)。

**修改**(加一个 broaden 参数,逐层透传 + finalize 需要的状态更新):
- `rivalradar/collect/queries.py` — `generate_queries` 加 `broaden` 参数 + broaden 后缀表。
- `rivalradar/collect/pipeline.py` — `collect` 加 `broaden` 透传。
- `rivalradar/agents/collector.py` — `collect_evidence` 加 `broaden` 透传。
- `rivalradar/storage/repository.py` — 加 `update_run_status`。

**新建测试:**
- `tests/test_graph_state.py` — reducer 去重累加 + state dict 形态。
- `tests/test_graph_router.py` — `decide_route` 五分支 + `extract_collect_targets`(`*` fan-out / 去重 / 只取 missing+low_coverage)。
- `tests/test_graph_nodes.py` — collect 只补缺口+broaden+SQLite+去重;qc 降级;finalize 赋 insufficient/降级。
- `tests/test_graph_loop.py` — **★★★ 真闭环回归**(改善→pass)+ 耗尽→insufficient_evidence。

**追加测试**(到既有文件):
- `tests/test_queries.py` — broaden 后缀。
- `tests/test_collect_pipeline.py` — broaden 透传。

**新建 spike:**
- `spikes/spike_f_graph_real.py` — 真打 Doubao 跑通整图(FakeProvider 喂源,真实 LLM 驱动 analyze/write/qc)。
- `spikes/SPIKE_RESULTS.md` — 追加 Spike F 结论。

---

## Task 1: broaden 查询变体(CRAG transform_query)

**Files:**
- Modify: `rivalradar/collect/queries.py`
- Modify: `rivalradar/collect/pipeline.py:17-40`
- Modify: `rivalradar/agents/collector.py:49-70`
- Test: `tests/test_queries.py`(追加)、`tests/test_collect_pipeline.py`(追加)

- [ ] **Step 1: 写失败测试 — broaden 后缀 + 透传**

追加到 `tests/test_queries.py` 末尾:

```python
from rivalradar.collect.queries import generate_queries


def test_generate_queries_broaden_appends_suffix():
    qs = generate_queries("Notion", ["pricing"], languages=("en",), broaden=True)
    assert qs[0].query_text == "Notion pricing plans cost review comparison alternative"


def test_generate_queries_default_has_no_suffix():
    qs = generate_queries("Notion", ["pricing"], languages=("en",))
    assert qs[0].query_text == "Notion pricing plans cost"


def test_generate_queries_broaden_zh_suffix():
    qs = generate_queries("飞书", ["pricing"], languages=("zh",), broaden=True)
    assert qs[0].query_text.endswith("评测 对比 替代方案")
```

追加到 `tests/test_collect_pipeline.py` 末尾:

```python
from rivalradar.collect.pipeline import collect as _collect_for_broaden


class _CaptureProvider:
    name = "capture"

    def __init__(self):
        self.queries: list[str] = []

    def search(self, query, *, max_results=5):
        self.queries.append(query)
        return []


def test_collect_passes_broaden_into_queries():
    p = _CaptureProvider()
    _collect_for_broaden(["Notion"], ["pricing"], provider=p, languages=("en",), broaden=True)
    assert any("comparison" in q for q in p.queries)


def test_collect_default_no_broaden():
    p = _CaptureProvider()
    _collect_for_broaden(["Notion"], ["pricing"], provider=p, languages=("en",))
    assert all("comparison" not in q for q in p.queries)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_queries.py -k broaden -v`
Expected: FAIL — `generate_queries() got an unexpected keyword argument 'broaden'`

- [ ] **Step 3: 改 queries.py**

把 `rivalradar/collect/queries.py` 的 `generate_queries` 替换为带 broaden 的版本,并在模板表后加后缀表。完整新内容(替换第 22-47 行的 `Query` 之后部分;`_TEMPLATES` 与 `Query` 类不变):

```python
# broaden 后缀(retry 时换查询词 = Corrective RAG 的 transform_query;spec §8 不死磕同一缺口)
_BROADEN_SUFFIX: dict[str, str] = {
    "en": "review comparison alternative",
    "zh": "评测 对比 替代方案",
}


def generate_queries(
    competitor: str,
    dimensions: list[str],
    *,
    languages: tuple[str, ...] = ("en", "zh"),
    broaden: bool = False,
) -> list[Query]:
    out: list[Query] = []
    for dim in dimensions:
        for lang in languages:
            template = _TEMPLATES.get((dim, lang)) or _generic(lang)
            text = template.format(c=competitor, dim=dim)
            if broaden:
                text = f"{text} {_BROADEN_SUFFIX.get(lang, '')}".strip()
            out.append(Query(
                competitor=competitor, dimension=dim, language=lang, query_text=text,
            ))
    return out


def _generic(lang: str) -> str:
    return "{c} {dim}" if lang == "en" else "{c} {dim} 介绍"
```

- [ ] **Step 4: 改 pipeline.py 透传 broaden**

`rivalradar/collect/pipeline.py`:给 `collect` 加 `broaden` 参数并透传给 `generate_queries`。改两处:

函数签名(第 17-25 行)加一行参数:

```python
def collect(
    competitors: list[str],
    dimensions: list[str],
    *,
    provider: SearchProvider,
    languages: tuple[str, ...] = ("en", "zh"),
    max_results: int = 5,
    max_workers: int = 4,
    broaden: bool = False,
) -> list[Evidence]:
```

查询生成处(第 30-31 行):

```python
    for c in competitors:
        queries.extend(generate_queries(c, dimensions, languages=languages, broaden=broaden))
```

- [ ] **Step 5: 改 collector.py 透传 broaden**

`rivalradar/agents/collector.py`:`collect_evidence` 加 `broaden` 参数(第 49-58 行签名加 `broaden: bool = False`),并把它传给 `collect`(第 61-62 行):

签名加参数:

```python
def collect_evidence(
    competitors: list[str],
    dimensions: list[str],
    *,
    provider: SearchProvider,
    official_domains: dict[str, list[str]] | None = None,
    languages: tuple[str, ...] = ("en", "zh"),
    max_results: int = 5,
    max_workers: int = 4,
    broaden: bool = False,
) -> list[Evidence]:
```

调用 collect 处:

```python
    raw = collect(competitors, dimensions, provider=provider, languages=languages,
                  max_results=max_results, max_workers=max_workers, broaden=broaden)
```

- [ ] **Step 6: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_queries.py tests/test_collect_pipeline.py -v`
Expected: PASS（含新增 5 个 broaden 测试,且既有测试不破）

- [ ] **Step 7: Commit**

```bash
git add rivalradar/collect/queries.py rivalradar/collect/pipeline.py rivalradar/agents/collector.py tests/test_queries.py tests/test_collect_pipeline.py
git commit -m "feat: broaden query variant for corrective re-collection (CRAG transform_query)"
```

---

## Task 2: ResearchState + 证据累加去重 reducer

**Files:**
- Create: `rivalradar/graph/__init__.py`
- Create: `rivalradar/graph/state.py`
- Test: `tests/test_graph_state.py`

- [ ] **Step 1: 写失败测试**

`tests/test_graph_state.py`:

```python
from rivalradar.graph.state import ResearchState, merge_evidence


def _e(eid):
    return {"id": eid, "competitor": "Notion", "dimension": "pricing", "content": "c",
            "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}


def test_merge_evidence_accumulates_new_ids():
    merged = merge_evidence([_e("a")], [_e("b")])
    assert [e["id"] for e in merged] == ["a", "b"]


def test_merge_evidence_dedups_same_id():
    # 同 id(同源重采)被丢弃 → 不增加(spec §8 不死磕)
    merged = merge_evidence([_e("a")], [_e("a"), _e("c")])
    assert [e["id"] for e in merged] == ["a", "c"]


def test_merge_evidence_keeps_left_on_conflict():
    left = [{"id": "a", "content": "first", "competitor": "Notion", "dimension": "pricing",
             "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    right = [{"id": "a", "content": "second", "competitor": "Notion", "dimension": "pricing",
              "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    merged = merge_evidence(left, right)
    assert len(merged) == 1 and merged[0]["content"] == "first"  # 累加不覆盖


def test_research_state_is_typeddict_with_reducer():
    # evidence 字段带 reducer 注解(Annotated),其余字段存在
    ann = ResearchState.__annotations__
    assert "evidence" in ann and "analysis" in ann and "qc_result" in ann
    assert "retry_count" in ann and "report" in ann
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_graph_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rivalradar.graph'`

- [ ] **Step 3: 建包 + 实现 state.py**

`rivalradar/graph/__init__.py`:

```python
```

(空文件)

`rivalradar/graph/state.py`:

```python
from __future__ import annotations

from typing import Annotated, TypedDict


def merge_evidence(left: list[dict], right: list[dict]) -> list[dict]:
    """证据累加去重 reducer(spec §8「累加不覆盖」)。

    按 evidence id 合并、先到先留:id = sha1(competitor|dimension|url),所以同源重采
    (同 url)→ 同 id → 丢弃;换源(新 url)→ 新 id → 追加。这让「第二版证据真增加」
    等价于「采到了新源」,正是真闭环要的不变量。
    """
    seen = {e["id"] for e in left}
    out = list(left)
    for e in right:
        if e["id"] not in seen:
            out.append(e)
            seen.add(e["id"])
    return out


class ResearchState(TypedDict, total=False):
    """LangGraph 共享状态(spec §4)。

    证据/分析/质检以 **dict 原语** 存(不是 Pydantic 对象):LangGraph 1.2.1 的
    JsonPlusSerializer 反序列化未注册 Pydantic 类型会告警且未来会 block,dict 原语
    则 checkpoint 零风险。节点边界做 Evidence(**d) / .model_dump() 转换。
    """
    competitors: list[str]            # 目标竞品
    dimensions: list[str]             # 受控维度(首遍采集用)
    evidence: Annotated[list[dict], merge_evidence]  # Evidence.model_dump() 列表,append-only 去重
    analysis: dict                    # CompetitorAnalysis.model_dump()
    report: str                       # markdown 报告
    qc_result: dict                   # QCResult.model_dump()
    retry_count: int                  # 已重试次数(仅 qc 节点递增;首遍=0)
    degraded: bool                    # 本轮 LLM 蕴含是否降级
    status: str                       # 终态:done / insufficient_evidence / degraded
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_graph_state.py -v`
Expected: PASS（4 个测试）

- [ ] **Step 5: Commit**

```bash
git add rivalradar/graph/__init__.py rivalradar/graph/state.py tests/test_graph_state.py
git commit -m "feat: ResearchState (dict primitives) + evidence dedup-accumulate reducer"
```

---

## Task 3: 路由纯逻辑(decide_route + extract_collect_targets)

**Files:**
- Create: `rivalradar/graph/router.py`
- Test: `tests/test_graph_router.py`

- [ ] **Step 1: 写失败测试(spec §13 ★必测:五分支 + 缺口提取)**

`tests/test_graph_router.py`:

```python
from rivalradar.graph.router import decide_route, extract_collect_targets


# ---- decide_route 五分支(max_retries=2) ----
def test_route_pass_goes_finalize():
    assert decide_route("pass", 0, 2) == "finalize"


def test_route_retry_collect_when_budget_left():
    assert decide_route("retry_collect", 0, 2) == "collect"
    assert decide_route("retry_collect", 1, 2) == "collect"


def test_route_retry_analyze_when_budget_left():
    assert decide_route("retry_analyze", 0, 2) == "analyze"


def test_route_exhausted_goes_finalize():
    # retry_count 达上限 → finalize(由 finalize 赋 insufficient/降级)
    assert decide_route("retry_collect", 2, 2) == "finalize"
    assert decide_route("retry_analyze", 2, 2) == "finalize"


def test_route_insufficient_or_unknown_goes_finalize():
    assert decide_route("insufficient_evidence", 0, 2) == "finalize"
    assert decide_route("???", 0, 2) == "finalize"


# ---- extract_collect_targets(只补缺口) ----
def test_targets_only_missing_and_low_coverage():
    issues = [
        {"competitor": "Notion", "dimension": "pricing", "problem_type": "missing_evidence", "detail": ""},
        {"competitor": "Notion", "dimension": "core_workflows", "problem_type": "low_coverage", "detail": ""},
        {"competitor": "Notion", "dimension": "swot", "problem_type": "hallucination", "detail": ""},  # 不补采
    ]
    targets = extract_collect_targets(issues, ["Notion"])
    assert ("Notion", "pricing") in targets
    assert ("Notion", "core_workflows") in targets
    assert all(d != "swot" for _, d in targets)


def test_targets_star_competitor_fans_out_to_all():
    # competitor='*' fan 到全竞品(必办项②)
    issues = [{"competitor": "*", "dimension": "pricing", "problem_type": "low_coverage", "detail": ""}]
    targets = extract_collect_targets(issues, ["Notion", "Lark"])
    assert ("Notion", "pricing") in targets and ("Lark", "pricing") in targets


def test_targets_dedup_preserves_order():
    issues = [
        {"competitor": "Notion", "dimension": "pricing", "problem_type": "low_coverage", "detail": ""},
        {"competitor": "Notion", "dimension": "pricing", "problem_type": "missing_evidence", "detail": ""},
    ]
    assert extract_collect_targets(issues, ["Notion"]) == [("Notion", "pricing")]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_graph_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rivalradar.graph.router'`

- [ ] **Step 3: 实现 router.py**

`rivalradar/graph/router.py`:

```python
from __future__ import annotations


def decide_route(verdict: str, retry_count: int, max_retries: int) -> str:
    """纯逻辑路由(spec §4/§13 ★必测),返回下一节点名。

    pass → finalize;重试耗尽(retry_count >= max_retries)→ finalize
    (由 finalize 赋 insufficient_evidence / 降级);
    retry_collect → collect;retry_analyze → analyze;
    其他(含 insufficient_evidence / 未知)→ finalize。
    """
    if verdict == "pass":
        return "finalize"
    if retry_count >= max_retries:
        return "finalize"
    if verdict == "retry_collect":
        return "collect"
    if verdict == "retry_analyze":
        return "analyze"
    return "finalize"


def extract_collect_targets(
    issues: list[dict], competitors: list[str]
) -> list[tuple[str, str]]:
    """从 QC issues 提「只补缺口」清单(spec §8 + 必办项②)。

    只取 problem_type ∈ {missing_evidence, low_coverage} 的 (competitor, dimension);
    competitor='*' fan 到全竞品;去重保序。hallucination/schema_incomplete 走重分析,不补采。
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for it in issues:
        if it.get("problem_type") not in ("missing_evidence", "low_coverage"):
            continue
        comps = competitors if it.get("competitor") == "*" else [it["competitor"]]
        for c in comps:
            key = (c, it["dimension"])
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_graph_router.py -v`
Expected: PASS（8 个测试）

- [ ] **Step 5: Commit**

```bash
git add rivalradar/graph/router.py tests/test_graph_router.py
git commit -m "feat: graph router (decide_route 5-branch + gap extraction with '*' fan-out)"
```

---

## Task 4: 直通节点(collect / analyze / write)

**Files:**
- Create: `rivalradar/graph/nodes.py`
- Test: `tests/test_graph_nodes.py`

- [ ] **Step 1: 写失败测试 — collect 首遍/补缺口/去重/SQLite**

`tests/test_graph_nodes.py`:

```python
import hashlib

from rivalradar.graph.nodes import make_collect_node, make_analyze_node, make_write_node
from rivalradar.search.base import SearchResult
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db
import pytest


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


class _FakeProvider:
    """首遍只对 pricing 返回源;broaden 时对任意维度返回新 url(模拟换源采到新证据)。"""
    name = "fake"

    def search(self, query, *, max_results=5):
        is_broaden = ("comparison" in query) or ("替代方案" in query)
        is_pricing = ("pricing" in query) or ("价格" in query)
        if not is_broaden and not is_pricing:
            return []
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="snippet",
                             raw_content="evidence body for " + query)]


_CFG = {"configurable": {"thread_id": "r1"}}


def test_collect_node_first_pass_collects_and_persists(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_collect_node(conn=conn, provider=_FakeProvider(), official_domains={})
    out = node({"competitors": ["Notion"], "dimensions": ["pricing"], "evidence": [],
                "retry_count": 0}, _CFG)
    assert len(out["evidence"]) >= 1                       # 采到 pricing 证据
    assert len(repo.list_evidence(conn, "r1")) == len(out["evidence"])  # 落库


def test_collect_node_retry_only_fills_gap_with_broaden(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing", "core_workflows"])
    node = make_collect_node(conn=conn, provider=_FakeProvider(), official_domains={})
    # 模拟:已有 pricing 证据;qc 报 core_workflows low_coverage → 只补该缺口
    existing = [{"id": "old1", "competitor": "Notion", "dimension": "pricing", "content": "c",
                 "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    qc_result = {"verdict": "retry_collect", "issues": [
        {"competitor": "Notion", "dimension": "core_workflows",
         "problem_type": "low_coverage", "detail": ""}]}
    out = node({"competitors": ["Notion"], "dimensions": ["pricing", "core_workflows"],
                "evidence": existing, "retry_count": 0, "qc_result": qc_result}, _CFG)
    dims = {e["dimension"] for e in out["evidence"]}
    assert dims == {"core_workflows"}        # 只补缺口维度,不重采 pricing
    assert all(e["id"] != "old1" for e in out["evidence"])  # 只返回新增


def test_collect_node_dedups_against_existing(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_collect_node(conn=conn, provider=_FakeProvider(), official_domains={})
    first = node({"competitors": ["Notion"], "dimensions": ["pricing"], "evidence": [],
                  "retry_count": 0}, _CFG)
    # 再以 first 的结果作为 existing 首遍重跑:相同 url → 相同 id → 全去重 → 0 新增
    again = node({"competitors": ["Notion"], "dimensions": ["pricing"],
                  "evidence": first["evidence"], "retry_count": 0}, _CFG)
    assert again["evidence"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_graph_nodes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rivalradar.graph.nodes'`

- [ ] **Step 3: 实现 nodes.py(三个直通节点)**

`rivalradar/graph/nodes.py`:

```python
from __future__ import annotations

import time

from rivalradar.agents.analyst import analyze
from rivalradar.agents.collector import collect_evidence
from rivalradar.agents.writer import write_report
from rivalradar.graph.router import extract_collect_targets
from rivalradar.schema.models import CompetitorAnalysis, Evidence
from rivalradar.storage.repository import (
    append_trace, insert_evidence, save_analysis, save_report,
)


def make_collect_node(*, conn, provider, official_domains, max_results: int = 5):
    """采集节点:首遍全量采;retry 时按 qc issues 只补缺口 + broaden 广搜。
    只 insert 真新增(对 state 已有 id 去重),证据 dict 由 reducer 累加去重。"""
    def collect_node(state, config):
        run_id = config["configurable"]["thread_id"]
        t0 = time.monotonic()
        existing = {e["id"] for e in state.get("evidence", [])}
        qc_result = state.get("qc_result")
        if qc_result is None:
            evs = collect_evidence(state["competitors"], state["dimensions"],
                                   provider=provider, official_domains=official_domains,
                                   max_results=max_results)
            tgt_desc = "all"
        else:
            targets = extract_collect_targets(qc_result["issues"], state["competitors"])
            evs = []
            for comp, dim in targets:
                evs += collect_evidence([comp], [dim], provider=provider,
                                        official_domains=official_domains,
                                        max_results=max_results, broaden=True)
            tgt_desc = f"{len(targets)} gaps"
        fresh = [e for e in evs if e.id not in existing]
        for e in fresh:
            insert_evidence(conn, run_id, e)
        append_trace(conn, run_id, "collect",
                     input_summary=f"targets={tgt_desc}",
                     output_summary=f"+{len(fresh)} (total {len(existing) + len(fresh)})",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"evidence": [e.model_dump() for e in fresh]}
    return collect_node


def make_analyze_node(*, conn, client, model):
    """分析节点:state 证据 dict → Evidence → analyze() → CompetitorAnalysis → 落库。"""
    def analyze_node(state, config):
        run_id = config["configurable"]["thread_id"]
        t0 = time.monotonic()
        evidence = [Evidence(**d) for d in state["evidence"]]
        analysis = analyze(evidence, state["competitors"], client=client, model=model)
        save_analysis(conn, run_id, analysis)
        append_trace(conn, run_id, "analyze",
                     input_summary=f"{len(evidence)} evidence",
                     output_summary=f"{len(analysis.competitors)} profiles, "
                                    f"{len(analysis.comparison)} rows",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"analysis": analysis.model_dump()}
    return analyze_node


def make_write_node(*, conn, client, model, as_of):
    """撰写节点:CompetitorAnalysis + 证据 → 混合报告 → 落库。"""
    def write_node(state, config):
        run_id = config["configurable"]["thread_id"]
        t0 = time.monotonic()
        analysis = CompetitorAnalysis(**state["analysis"])
        evidence = [Evidence(**d) for d in state["evidence"]]
        report = write_report(analysis, evidence, as_of=as_of, client=client, model=model)
        save_report(conn, run_id, report)
        append_trace(conn, run_id, "write",
                     output_summary=f"report {len(report)} chars",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"report": report}
    return write_node
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_graph_nodes.py -v`
Expected: PASS（3 个 collect 测试）

- [ ] **Step 5: Commit**

```bash
git add rivalradar/graph/nodes.py tests/test_graph_nodes.py
git commit -m "feat: graph collect/analyze/write nodes (gap-only re-collect, dedup persist)"
```

---

## Task 5: 质检节点(确定性闸 + LLM 蕴含降级 + 重试计数)

**Files:**
- Modify: `rivalradar/graph/nodes.py`(加 `make_qc_node` + 导入)
- Test: `tests/test_graph_nodes.py`(追加)

- [ ] **Step 1: 写失败测试 — 降级 + 计数(必办项①)**

追加到 `tests/test_graph_nodes.py`:

```python
from rivalradar.agents import qc
from rivalradar.graph.nodes import make_qc_node
from rivalradar.llm.structured import StructuredCallError
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, PricingModel, SWOT,
    ComparisonRow, ComparisonCell, EvidenceRef,
)

_CONTROLLED = ("pricing", "deployment", "integrations", "target_users",
               "core_workflows", "review_sentiment")


def _full_clean_analysis(eid="g1"):
    """覆盖全 6 维、引用合法的干净分析 → 确定性闸应全过。"""
    ref = [EvidenceRef(evidence_id=eid, quote="q")]
    rows = [ComparisonRow(dimension=d, cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="x", evidence_refs=ref)])
        for d in _CONTROLLED]
    return CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=ref), swot=SWOT())],
        comparison=rows)


def _evidence_all_dims(eid="g1"):
    return [{"id": eid, "competitor": "Notion", "dimension": d, "content": "c",
             "source_url": "u" + d, "source_title": "t", "language": "en", "fetched_at": "t0"}
            for d in _CONTROLLED]


def test_qc_node_degrades_on_entailment_failure(conn, monkeypatch):
    # check_entailment 上抛 → 节点捕获降级为仅确定性闸(必办项①)
    def _boom(*a, **k):
        raise StructuredCallError("entailment boom")
    monkeypatch.setattr(qc, "check_entailment", _boom)
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    state = {"analysis": _full_clean_analysis().model_dump(),
             "evidence": _evidence_all_dims(), "retry_count": 0}
    out = node(state, _CFG)
    assert out["degraded"] is True
    assert out["qc_result"]["verdict"] == "pass"   # 确定性闸全过 → pass,蕴含降级不阻断
    traces = [t for t in repo.list_trace(conn, "r1") if "degraded" in (t["output_summary"] or "")]
    assert traces                                   # 降级写了 trace


def test_qc_node_retry_count_bumps_only_with_prior_result(conn, monkeypatch):
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    base = {"analysis": _full_clean_analysis().model_dump(), "evidence": _evidence_all_dims()}
    first = node({**base, "retry_count": 0}, _CFG)          # 首遍无 qc_result
    assert first["retry_count"] == 0
    second = node({**base, "retry_count": 0, "qc_result": first["qc_result"]}, _CFG)  # 带上轮
    assert second["retry_count"] == 1


def test_qc_node_low_coverage_triggers_retry_collect(conn, monkeypatch):
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    # 只覆盖 pricing 的分析 → coverage 缺 5 维 → retry_collect
    ref = [EvidenceRef(evidence_id="g1", quote="q")]
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=ref), swot=SWOT())],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="x", evidence_refs=ref)])])
    evidence = [{"id": "g1", "competitor": "Notion", "dimension": "pricing", "content": "c",
                 "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    out = node({"analysis": analysis.model_dump(), "evidence": evidence, "retry_count": 0}, _CFG)
    assert out["qc_result"]["verdict"] == "retry_collect"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_graph_nodes.py -k qc_node -v`
Expected: FAIL — `cannot import name 'make_qc_node'`

- [ ] **Step 3: 实现 make_qc_node**

在 `rivalradar/graph/nodes.py` 顶部导入区**追加**:

```python
from rivalradar.agents import qc
from rivalradar.llm.structured import StructuredCallError
from rivalradar.schema.models import QCResult
```

(把 `from rivalradar.schema.models import CompetitorAnalysis, Evidence` 改为
`from rivalradar.schema.models import CompetitorAnalysis, Evidence, QCResult`,即合并导入。)

在文件末尾追加 `make_qc_node`:

```python
def make_qc_node(*, conn, client, model):
    """质检节点:确定性三闸(始终跑)+ LLM 蕴含(失败则降级,必办项①)。

    不调 qc.check(它会上抛),而是在本层组合子函数:traceability/ontology/coverage
    决定 verdict 主体;check_entailment 包在 try/except StructuredCallError,失败则
    degraded=True、记 trace,verdict 仅由确定性闸决定。
    retry_count 仅在「带着上一轮 qc_result 进来」时 +1(每轮唯一计数点,避免双重计数)。
    """
    def qc_node(state, config):
        run_id = config["configurable"]["thread_id"]
        t0 = time.monotonic()
        analysis = CompetitorAnalysis(**state["analysis"])
        evidence = [Evidence(**d) for d in state["evidence"]]
        issues = qc.check_traceability(analysis, evidence)
        issues += qc.check_ontology(analysis, evidence)
        issues += qc.check_coverage(analysis)
        degraded = False
        try:
            issues += qc.check_entailment(analysis, evidence, client=client, model=model)
        except StructuredCallError as e:
            degraded = True
            append_trace(conn, run_id, "qc",
                         output_summary=f"entailment degraded: {e}")
        verdict = qc.decide_verdict(issues)
        result = QCResult(verdict=verdict, issues=issues)
        prior = state.get("qc_result")
        new_rc = state["retry_count"] + (1 if prior is not None else 0)
        append_trace(conn, run_id, "qc",
                     input_summary=f"{len(evidence)} evidence",
                     output_summary=f"verdict={verdict} issues={len(issues)} "
                                    f"degraded={degraded} retry={new_rc}",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"qc_result": result.model_dump(), "retry_count": new_rc, "degraded": degraded}
    return qc_node
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_graph_nodes.py -v`
Expected: PASS（含 collect 3 + qc 3）

- [ ] **Step 5: Commit**

```bash
git add rivalradar/graph/nodes.py tests/test_graph_nodes.py
git commit -m "feat: qc node with entailment degrade-on-failure + single-point retry counting"
```

---

## Task 6: finalize 节点 + run status 更新

**Files:**
- Modify: `rivalradar/storage/repository.py`(加 `update_run_status`)
- Modify: `rivalradar/graph/nodes.py`(加 `make_finalize_node` + 导入)
- Test: `tests/test_repository.py`(追加)、`tests/test_graph_nodes.py`(追加)

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_repository.py`:

```python
def test_update_run_status(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(conn, "r1", "done")
    assert repo.get_run(conn, "r1")["status"] == "done"
```

追加到 `tests/test_graph_nodes.py`:

```python
from rivalradar.graph.nodes import make_finalize_node


def test_finalize_pass_marks_done(conn):
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _full_clean_analysis().model_dump(), "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "pass", "issues": []}, "retry_count": 0}
    out = node(state, _CFG)
    assert out["status"] == "done"
    assert out["report"] == "# 竞品分析报告\n正文"          # pass 不加 banner
    assert repo.get_run(conn, "r1")["status"] == "done"


def test_finalize_exhausted_collect_becomes_insufficient(conn):
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _full_clean_analysis().model_dump(), "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "retry_collect", "issues": []}, "retry_count": 2}
    out = node(state, _CFG)
    assert out["qc_result"]["verdict"] == "insufficient_evidence"   # 缺证据耗尽 → 一等结论
    assert "未找到公开数据" in out["report"]                        # 诚实 banner
    assert out["status"] == "insufficient_evidence"


def test_finalize_exhausted_analyze_becomes_degraded(conn):
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _full_clean_analysis().model_dump(), "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "retry_analyze", "issues": []}, "retry_count": 2}
    out = node(state, _CFG)
    assert "未达质检标准" in out["report"]
    assert out["status"] == "degraded"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_repository.py -k update_run_status tests/test_graph_nodes.py -k finalize -v`
Expected: FAIL — `module 'repository' has no attribute 'update_run_status'` / `cannot import name 'make_finalize_node'`

- [ ] **Step 3: 加 repository.update_run_status**

在 `rivalradar/storage/repository.py` 的 `# ---- runs ----` 区(`get_run` 之后)追加:

```python
def update_run_status(conn: sqlite3.Connection, run_id: str, status: str) -> None:
    conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
    conn.commit()
```

- [ ] **Step 4: 实现 make_finalize_node**

在 `rivalradar/graph/nodes.py` 导入区把 repository 导入扩展为含 `update_run_status`:

```python
from rivalradar.storage.repository import (
    append_trace, insert_evidence, save_analysis, save_report, update_run_status,
)
```

文件末尾追加:

```python
_BANNER_INSUFFICIENT = (
    "> ⚠️ **数据不足**:部分维度在有界广搜后仍未找到公开数据。"
    "以下为现有证据下的结论(诚实标注优于编造)。\n\n"
)
_BANNER_DEGRADED = (
    "> ⚠️ **未达质检标准**:存在未消解的质检问题,以下结论请谨慎参考。\n\n"
)


def make_finalize_node(*, conn, max_retries):
    """终态节点:pass → done;重试耗尽则按最后 verdict 赋 insufficient/降级 + 加 banner。

    route 保证只有 pass 或耗尽才进来(spec §4/§8 + 必办项③)。insufficient_evidence
    是一等质检结论(§8):缺证据耗尽 → 报告如实写「未找到公开数据」。
    """
    def finalize_node(state, config):
        run_id = config["configurable"]["thread_id"]
        result = dict(state["qc_result"])
        verdict = result["verdict"]
        report = state["report"]
        if verdict == "pass":
            status = "done"
        elif verdict == "retry_collect":
            result["verdict"] = "insufficient_evidence"
            report = _BANNER_INSUFFICIENT + report
            status = "insufficient_evidence"
        else:  # retry_analyze 或其他耗尽
            report = _BANNER_DEGRADED + report
            status = "degraded"
        save_report(conn, run_id, report)
        update_run_status(conn, run_id, status)
        append_trace(conn, run_id, "finalize",
                     output_summary=f"status={status} verdict={result['verdict']}")
        return {"report": report, "qc_result": result, "status": status}
    return finalize_node
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_repository.py tests/test_graph_nodes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add rivalradar/storage/repository.py rivalradar/graph/nodes.py tests/test_repository.py tests/test_graph_nodes.py
git commit -m "feat: finalize node (insufficient_evidence/degrade banners) + update_run_status"
```

---

## Task 7: 组装图 + run_research 入口

**Files:**
- Create: `rivalradar/graph/build.py`
- Test: `tests/test_graph_build.py`

- [ ] **Step 1: 写失败测试 — 图能编译且含五节点**

`tests/test_graph_build.py`:

```python
from rivalradar.graph.build import build_research_graph
from rivalradar.storage.db import connect, init_db
import pytest


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


class _NoopProvider:
    name = "noop"

    def search(self, query, *, max_results=5):
        return []


def test_build_compiles_with_five_nodes(conn):
    graph = build_research_graph(conn=conn, client=None, model="m",
                                 provider=_NoopProvider(), as_of="2026-05-26")
    names = set(graph.get_graph().nodes)
    assert {"collect", "analyze", "write", "qc", "finalize"} <= names
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_graph_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rivalradar.graph.build'`

- [ ] **Step 3: 实现 build.py**

`rivalradar/graph/build.py`:

```python
from __future__ import annotations

import uuid

from langgraph.graph import END, START, StateGraph

from rivalradar.graph.nodes import (
    make_analyze_node, make_collect_node, make_finalize_node,
    make_qc_node, make_write_node,
)
from rivalradar.graph.router import decide_route
from rivalradar.graph.state import ResearchState
from rivalradar.storage.repository import create_run


def build_research_graph(*, conn, client, model, provider, as_of,
                         official_domains=None, max_retries: int = 2, checkpointer=None):
    """组装 RivalRadar 状态图(spec §4)。节点依赖经闭包注入;run_id 取自 config thread_id。

    拓扑:START→collect→analyze→write→qc→[decide_route]。qc 的条件边:
    collect(retry_collect)/analyze(retry_analyze)/finalize(pass 或超限)。finalize→END。
    """
    g = StateGraph(ResearchState)
    g.add_node("collect", make_collect_node(
        conn=conn, provider=provider, official_domains=official_domains or {}))
    g.add_node("analyze", make_analyze_node(conn=conn, client=client, model=model))
    g.add_node("write", make_write_node(conn=conn, client=client, model=model, as_of=as_of))
    g.add_node("qc", make_qc_node(conn=conn, client=client, model=model))
    g.add_node("finalize", make_finalize_node(conn=conn, max_retries=max_retries))

    g.add_edge(START, "collect")
    g.add_edge("collect", "analyze")
    g.add_edge("analyze", "write")
    g.add_edge("write", "qc")
    g.add_conditional_edges(
        "qc",
        lambda s: decide_route(s["qc_result"]["verdict"], s["retry_count"], max_retries),
        {"collect": "collect", "analyze": "analyze", "finalize": "finalize"},
    )
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


def run_research(competitors, dimensions, *, conn, client, model, provider, as_of,
                 official_domains=None, max_retries: int = 2,
                 checkpointer=None, run_id=None):
    """一次完整调研:建 run → 编译图 → invoke。返回 (run_id, 终态 state dict)。"""
    run_id = run_id or "run_" + uuid.uuid4().hex[:12]
    create_run(conn, run_id, competitors, dimensions)
    graph = build_research_graph(
        conn=conn, client=client, model=model, provider=provider, as_of=as_of,
        official_domains=official_domains, max_retries=max_retries, checkpointer=checkpointer)
    final = graph.invoke(
        {"competitors": competitors, "dimensions": dimensions, "evidence": [], "retry_count": 0},
        config={"configurable": {"thread_id": run_id}},
    )
    return run_id, final
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_graph_build.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rivalradar/graph/build.py tests/test_graph_build.py
git commit -m "feat: assemble research StateGraph + run_research entry point"
```

---

## Task 8: ★★★ 真闭环回归(35% 的机器可验证铁证)

**Files:**
- Test: `tests/test_graph_loop.py`

这是 spec §13 的 ★★★。测 Lane D 编排本身:`FakeProvider` 让 collect 真累加证据,monkeypatch 假 `analyze`/`write_report`/`qc.check_entailment`,确定性三闸真跑驱动路由。

- [ ] **Step 1: 写失败测试 — 注入缺证据 → 跑图 → 二版证据增加且 qc=pass**

`tests/test_graph_loop.py`:

```python
import hashlib

import pytest

from rivalradar.agents import qc
from rivalradar.graph.build import run_research
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, CompetitorProfile, PricingModel,
    SWOT, ComparisonRow, ComparisonCell, EvidenceRef,
)
from rivalradar.search.base import SearchResult
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


class _ImprovingProvider:
    """首遍只对 pricing 返回源(缺其余 5 维);broaden 时对任意维度返回新 url → 补足缺口。"""
    name = "improving"

    def search(self, query, *, max_results=5):
        is_broaden = ("comparison" in query) or ("替代方案" in query)
        is_pricing = ("pricing" in query) or ("价格" in query)
        if not is_broaden and not is_pricing:
            return []
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="snippet",
                             raw_content="evidence body for " + query)]


class _StuckProvider:
    """broaden 也补不到(模拟源头本就无该数据)→ 必然耗尽 → insufficient_evidence。"""
    name = "stuck"

    def search(self, query, *, max_results=5):
        if ("pricing" in query) or ("价格" in query):
            url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
            return [SearchResult(url=url, title="t", content="s", raw_content="pricing body")]
        return []


def _fake_analyze(evidence, competitors, *, client, model):
    """按证据已覆盖的维度产出分析:覆盖 dims_present 的对比行,引用真实证据 id。
    pricing profile 挂合法引用 → 确定性 traceability 过;无 features/personas/swot(空,不被遍历)。"""
    dims_present = {e.dimension for e in evidence}
    profiles = []
    for c in competitors:
        price_ev = next((e for e in evidence if e.competitor == c and e.dimension == "pricing"), None)
        refs = [EvidenceRef(evidence_id=price_ev.id, quote="q")] if price_ev else []
        profiles.append(CompetitorProfile(
            name=c, pricing=PricingModel(model_type="freemium", evidence_refs=refs), swot=SWOT()))
    rows = []
    for dim in CONTROLLED_DIMENSIONS:
        if dim not in dims_present:
            continue
        cells = []
        for c in competitors:
            ev = next((e for e in evidence if e.competitor == c and e.dimension == dim), None)
            if ev:
                cells.append(ComparisonCell(competitor=c, value_type="enum", value="x",
                                            evidence_refs=[EvidenceRef(evidence_id=ev.id, quote="q")]))
        rows.append(ComparisonRow(dimension=dim, cells=cells))
    return CompetitorAnalysis(competitors=profiles, comparison=rows)


@pytest.fixture(autouse=True)
def _stub_agents(monkeypatch):
    # 假 analyze / 假 write(报告内容与闭环断言无关)/ 假蕴含(返回无问题)
    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _fake_analyze)
    monkeypatch.setattr("rivalradar.graph.nodes.write_report", lambda *a, **k: "# 竞品分析报告\n正文")
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])


def test_real_feedback_loop_improves_to_pass(conn):
    run_id, final = run_research(
        ["Notion"], list(CONTROLLED_DIMENSIONS),
        conn=conn, client=None, model="m", provider=_ImprovingProvider(),
        as_of="2026-05-26", max_retries=2)

    # 1) 真发生了打回重采(collect 至少 2 次)
    collects = [t for t in repo.list_trace(conn, run_id) if t["node"] == "collect"]
    assert len(collects) >= 2

    # 2) 第二版证据增加(首遍只有 pricing en+zh = 2 条;broaden 补足 5 维)
    assert len(repo.list_evidence(conn, run_id)) > 2

    # 3) 最终 qc=pass(覆盖补齐 + 引用合法 + 蕴含无问题)
    assert final["qc_result"]["verdict"] == "pass"
    assert final["status"] == "done"


def test_bounded_retry_exhausts_to_insufficient(conn):
    run_id, final = run_research(
        ["Notion"], list(CONTROLLED_DIMENSIONS),
        conn=conn, client=None, model="m", provider=_StuckProvider(),
        as_of="2026-05-26", max_retries=2)

    # 补不到缺口 → 有界重试耗尽 → 一等结论 insufficient_evidence + 诚实 banner
    assert final["qc_result"]["verdict"] == "insufficient_evidence"
    assert final["status"] == "insufficient_evidence"
    assert "未找到公开数据" in final["report"]
    # retry_count 封顶 = max_retries(没有无限循环)
    assert final["retry_count"] == 2
```

- [ ] **Step 2: 跑测试确认失败 → 然后通过**

Run: `.venv/bin/python -m pytest tests/test_graph_loop.py -v`

先确认失败(若前序 Task 未全绿)。本任务**不写新生产代码** —— 它验证 Task 1-7 组装出的图真的闭环。若断言失败,按失败信息回到对应节点修正(常见:`extract_collect_targets` 未 fan、reducer 未去重、retry 计数错位)。修到 PASS。
Expected(最终): PASS（2 个测试)

- [ ] **Step 3: 跑全量回归**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS（Lane A-D 全套;Lane C 的 91 + Lane D 新增,无回归)

- [ ] **Step 4: Commit**

```bash
git add tests/test_graph_loop.py
git commit -m "test: real feedback-loop regression (improve->pass, exhaust->insufficient) [spec §13 ★★★]"
```

---

## Task 9: 真打 Doubao 整图 spike(spike_f)

**Files:**
- Create: `spikes/spike_f_graph_real.py`
- Modify: `spikes/SPIKE_RESULTS.md`(追加 Spike F)

延续每 Lane 真打传统:真实 Doubao client 驱动 analyze/write/qc,`FakeProvider` 喂可控源(避免网络抖动 + 控成本),证明整图在真模型上端到端跑通并产出 verdict。

- [ ] **Step 1: 写 spike_f**

`spikes/spike_f_graph_real.py`:

```python
"""Lane D 整图真打:FakeProvider 喂源 + 真实 Doubao 驱动 analyze/write/qc。需 ARK_API_KEY。

验证整图在真模型上端到端跑通:采集(累加)→分析→撰写→质检→路由→终态,
并落 evidence/analysis/report/trace。真实 LLM 不确定 → 断言放宽到「跑通 + 合法 verdict」。
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.graph.build import run_research
from rivalradar.schema.models import CONTROLLED_DIMENSIONS
from rivalradar.search.base import SearchResult
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


class _SeededProvider:
    """对每个查询返回一条带正文的源(url 随查询变),让真实 analyze 有据可依。"""
    name = "seeded"

    def search(self, query, *, max_results=5):
        url = "https://example.com/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        body = (f"This is reference content addressing: {query}. "
                "It describes pricing tiers, core features, integrations and user feedback.")
        return [SearchResult(url=url, title="ref", content=body[:120], raw_content=body)]


def main() -> None:
    client = config.get_doubao_client()
    model = config.doubao_model()
    conn = connect(":memory:")
    init_db(conn)

    run_id, final = run_research(
        ["Notion"], list(CONTROLLED_DIMENSIONS),
        conn=conn, client=client, model=model, provider=_SeededProvider(),
        as_of="2026-05-26", max_retries=2)

    report = final.get("report", "")
    verdict = final["qc_result"]["verdict"]
    n_ev = len(repo.list_evidence(conn, run_id))
    trace = repo.list_trace(conn, run_id)
    nodes_hit = [t["node"] for t in trace]

    print("=== REPORT (head) ===")
    print(report[:400])
    print(f"=== run_id={run_id} verdict={verdict} evidence={n_ev} status={final.get('status')} ===")
    print(f"=== trace nodes: {nodes_hit} ===")

    assert report.startswith("# 竞品分析报告") or report.lstrip().startswith(">")
    assert verdict in {"pass", "insufficient_evidence", "retry_collect", "retry_analyze"}
    assert n_ev > 0
    assert "collect" in nodes_hit and "analyze" in nodes_hit and "qc" in nodes_hit
    print("SPIKE F OK: real Doubao drove the full graph end-to-end")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑 spike_f(需 ARK_API_KEY 在 .env)**

Run: `.venv/bin/python spikes/spike_f_graph_real.py`
Expected: 打印 REPORT head + verdict + trace nodes,末行 `SPIKE F OK`。

> 🔑 KEY 纪律:spike 通过 `config.get_doubao_client()` 读 `.env`,**绝不**打印 key;只看布尔/业务输出。

- [ ] **Step 3: 记录结论到 SPIKE_RESULTS.md**

在 `spikes/SPIKE_RESULTS.md` 末尾追加(用实际跑出的 verdict / evidence 数 / trace 节点填写):

```markdown

## Spike F — Lane D 整图真打 ✅ GO(2026-05-26,Lane D)

运行:`.venv/bin/python spikes/spike_f_graph_real.py`(FakeProvider 喂源 + 真实 Doubao 驱动 analyze/write/qc)

验证目标:LangGraph 整图(采集累加→分析→撰写→质检→路由→终态)在**真实 Doubao** 上端到端跑通,
落 evidence/analysis/report/trace,产出合法 verdict。

**实测输出**(填实际值):
- trace 节点序列:<collect, analyze, write, qc, ...>
- verdict=<...>;evidence=<N> 条;status=<...>
- 报告:`# 竞品分析报告` + 混合正文(确定性 + LLM 导语)

**结论:GO**。Lane D 编排在真模型上成立;真闭环回归(§13 ★★★)由 `tests/test_graph_loop.py` 机器可验证
(改善→pass、耗尽→insufficient_evidence,retry_count 封顶)。
```

- [ ] **Step 4: Commit**

```bash
git add spikes/spike_f_graph_real.py spikes/SPIKE_RESULTS.md
git commit -m "spike: real Doubao end-to-end graph run (Lane D) + SPIKE_RESULTS"
```

---

## Self-Review(执行完成后由控制器跑)

**1. spec 覆盖核对:**
- §4 状态图 + ResearchState → Task 2(state)+ Task 7(build 拓扑)✅
- §4 route(pass/retry_collect/retry_analyze/insufficient/超限)→ Task 3(decide_route)+ Task 6(finalize 赋 insufficient)✅
- §8 只补缺口 + 证据累加不覆盖 → Task 2(reducer)+ Task 4(collect 缺口)+ Task 3(extract_collect_targets)✅
- §8 广搜换查询不死磕 → Task 1(broaden)✅
- §8 insufficient_evidence 一等结论 + 有界重试 → Task 5(计数)+ Task 6(finalize)+ Task 8(耗尽测试)✅
- §10 trace 可观测 → 各节点 append_trace ✅;status → Task 6 update_run_status ✅
- §13 router 五分支单测 → Task 3 ✅;★★★ 真闭环回归 → Task 8 ✅
- §17.3 确定性闸为主、蕴含降级 → Task 5(必办项①)✅

**2. 必办项核对(来自 C-2b 终审):**
- ① 捕获 check_entailment 异常降级 + trace → Task 5 ✅
- ② 只补缺口 / 证据累加 / `*` fan 全竞品 → Task 2+3+4 ✅
- ③ insufficient_evidence + 重试封顶 → Task 5+6 ✅
- ④ 真闭环回归测试 → Task 8 ✅
- ⑤ 蕴含每结论一次调用 / 多竞品成本 → 现状每结论一次(qc.check_entailment 不变);并行/采样标 **TODO**(见下)

**3. 收尾全局终审(opus):** 跑 `git log --oneline` 看 9 个提交;跑 `.venv/bin/python -m pytest -q` 全绿;人工核对真闭环回归断言确实覆盖「二版证据增加 且 qc=pass」与「耗尽→insufficient + 封顶」。

**遗留 TODO(非阻断,标注备查):**
- 广搜增强:retry 轮换 provider(Tavily↔Exa)= CRAG web_search fallback,需双额度,留 Day-4 真打按额度启用。
- 蕴含并行/采样:多竞品时 check_entailment 调用数 = 结论数,可并行或抽样降本(spec §13 ⑤)。
- checkpointer 与 repository 同 db 文件的并发写锁:spike_f 用内存库未触发;真实持久化跑 Day-4 切片门时验证(必要时 checkpointer 用独立文件)。
- finalize banner 置于报告最顶(H1 之上),渲染为标题前的提示块;若要置于标题后,后续按需调整。
