# RivalRadar Lane C-2a:采集 Agent + 分析 Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现前两个 Agent —— **采集 Agent**(包装 C-1 采集器,加来源优先级排序 + 轻量正文清洗,产出干净排序的 `Evidence`)与 **分析 Agent**(把证据按竞品×维度结构化成 `CompetitorAnalysis`,每条结论挂 `EvidenceRef{evidence_id, quote, support_verdict}` 句级引用,收尾产出跨竞品对比)。

**Architecture:** 新增 `rivalradar/agents/`。采集 Agent 纯确定性(C-1 `collect()` + 清洗 + 排序),离线可测。分析 Agent 用 `structured_call`(tools 路径)做小 schema 的逐项抽取(features/pricing/personas/swot 各一次,避免大 schema),再确定性拼装 `CompetitorProfile`,最后一次 `structured_call` 产出受控本体下的类型化对比。所有 LLM 路径用注入的 FakeClient 离线 TDD;真实 Doubao E2E 单列(需 ARK key,已配)。对应 spec §5 / §6 / §7 / D5,并落实 C-1 终审遗留项①②。

**Tech Stack:** Python 3.11+ · Pydantic v2 · 复用 `rivalradar/llm/structured.py`(tools)、`rivalradar/collect/pipeline.py`、`rivalradar/schema/models.py`。

---

## 前置:依赖与既有件

- 复用:`schema/models.py`(Evidence, EvidenceRef, FeatureItem, PricingModel, PricingTier, UserPersona, SWOT, SWOTPoint, CompetitorProfile, ComparisonCell, ComparisonRow, CompetitorAnalysis, CONTROLLED_DIMENSIONS)、`llm/structured.py`(structured_call)、`collect/pipeline.py`(collect)、`search/base.py`(SearchProvider)。
- C-1 终审遗留项本计划处理:① 正文噪声 → 采集 Agent 加 `clean_text`;② 来源优先级 → 采集 Agent 加 `rank`。遗留项③(接 safe_fetch)④(dimension 校验)留给后续(③自抓深挖、④ QC Agent)。

## 文件结构

```
rivalradar/
  agents/
    __init__.py
    collector.py      # 采集 Agent:clean_text + source_priority + collect_evidence()
    analyst.py        # 分析 Agent:evidence_for + 逐项抽取 + 拼装 + 对比 + analyze()
tests/
  test_collector_agent.py
  test_analyst_agent.py
spikes/
  spike_d_analyze_real.py   # 真实 Doubao 对 canned 证据跑 analyze()(待 ARK key)
```

---

### Task 1:采集 Agent —— 正文清洗 + 来源优先级

**Files:**
- Create: `rivalradar/agents/__init__.py`(`# RivalRadar package`)
- Create: `rivalradar/agents/collector.py`
- Test: `tests/test_collector_agent.py`

> 采集 Agent 是确定性包装:调 C-1 `collect()` 拿原始 Evidence → `clean_text` 去噪 → 按 `source_priority` 排序(官方域名 > 评价平台 > 其他)。落实 C-1 终审遗留①②。official_domains 按竞品给(demo:Notion→notion.so/notion.com,飞书→feishu.cn/larksuite.com)。

- [ ] **Step 1: 写失败测试 `tests/test_collector_agent.py`**

```python
from rivalradar.agents.collector import clean_text, source_priority, collect_evidence
from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchResult


def test_clean_text_strips_markdown_noise():
    raw = "![](https://px.ads/collect.gif) # Notion\n\n[link](http://x)  real text here"
    out = clean_text(raw)
    assert "px.ads" not in out
    assert "real text here" in out
    assert "![]" not in out


def test_clean_text_collapses_whitespace():
    assert clean_text("a\n\n\n\n  b   c") == "a\n\nb c"


def test_source_priority_official_beats_review_beats_other():
    official = source_priority("https://notion.so/pricing", ["notion.so"])
    review = source_priority("https://www.g2.com/products/notion", ["notion.so"])
    other = source_priority("https://random.blog/notion", ["notion.so"])
    assert official < review < other  # 数字越小优先级越高


class _StubProvider:
    name = "stub"

    def __init__(self, by_query):
        self._by_query = by_query

    def search(self, query, *, max_results=5):
        # 简单按竞品名返回不同来源,顺序故意打乱
        return [
            SearchResult(url="https://random.blog/x", title="blog", content="noise ![](a.gif) body",
                         raw_content="![](a.gif) blog body text", provider="stub"),
            SearchResult(url="https://notion.so/pricing", title="Official", content="official",
                         raw_content="official pricing text", provider="stub"),
        ]


def test_collect_evidence_cleans_and_ranks_official_first():
    provider = _StubProvider({})
    evs = collect_evidence(["Notion"], ["pricing"], provider=provider,
                           official_domains={"Notion": ["notion.so"]},
                           languages=("en",), max_workers=2)
    assert all(isinstance(e, Evidence) for e in evs)
    # 官方源排在前
    assert evs[0].source_url == "https://notion.so/pricing"
    # 内容已清洗(无 markdown 图片)
    assert all("![](" not in e.content for e in evs)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_collector_agent.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/agents/collector.py`**

```python
from __future__ import annotations

import re

from rivalradar.collect.pipeline import collect
from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchProvider

# 已知可达评价平台(spec §7 / SPIKE 决策):优先级次于官方、高于杂源
_REVIEW_PLATFORMS = (
    "g2.com", "capterra.com", "apps.apple.com", "play.google.com",
    "coolapk.com", "v2ex.com", "36kr.com", "huxiu.com",
)

_IMG_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")        # markdown 图片
_LINK_MD = re.compile(r"\[([^\]]*)\]\([^)]*\)")       # markdown 链接 → 留文字
_MULTISPACE = re.compile(r"[ \t]+")
_MULTINL = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """去掉抓取正文里的 markdown 图片/链接壳与多余空白(C-1 终审遗留①)。"""
    if not text:
        return ""
    t = _IMG_MD.sub("", text)
    t = _LINK_MD.sub(r"\1", t)
    t = _MULTISPACE.sub(" ", t)
    t = _MULTINL.sub("\n\n", t)
    return t.strip()


def source_priority(url: str, official_domains: list[str]) -> int:
    """来源优先级(数字越小越优先):官方=0 > 评价平台=1 > 其他=2(spec §7 / 终审遗留②)。"""
    host = url.lower()
    if any(d in host for d in official_domains):
        return 0
    if any(p in host for p in _REVIEW_PLATFORMS):
        return 1
    return 2


def collect_evidence(
    competitors: list[str],
    dimensions: list[str],
    *,
    provider: SearchProvider,
    official_domains: dict[str, list[str]] | None = None,
    languages: tuple[str, ...] = ("en", "zh"),
    max_results: int = 5,
    max_workers: int = 4,
) -> list[Evidence]:
    """采集 Agent:C-1 collect() → 清洗正文 → 按来源优先级排序。"""
    official_domains = official_domains or {}
    raw = collect(competitors, dimensions, provider=provider, languages=languages,
                  max_results=max_results, max_workers=max_workers)
    cleaned: list[Evidence] = []
    for ev in raw:
        body = clean_text(ev.content)
        if not body:
            continue
        cleaned.append(ev.model_copy(update={"content": body}))
    cleaned.sort(key=lambda e: source_priority(e.source_url, official_domains.get(e.competitor, [])))
    return cleaned
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_collector_agent.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/__init__.py rivalradar/agents/collector.py tests/test_collector_agent.py
git commit -m "feat: collector agent (clean + source-priority ranking over C-1 collect)"
```

---

### Task 2:分析 Agent —— 证据过滤 + 抽取包装模型

**Files:**
- Create: `rivalradar/agents/analyst.py`(本任务先放 helper + 包装模型,后续任务续写)
- Test: `tests/test_analyst_agent.py`(本任务先测 helper)

> 分析 Agent 把大任务拆成小 schema 抽取(spike A 教训:schema 越小越稳越快)。本任务先做:按竞品/维度过滤证据的 `evidence_for`,以及 list 抽取需要的包装模型(structured_call 返回单个 BaseModel,list 用 wrapper)。

- [ ] **Step 1: 写失败测试 `tests/test_analyst_agent.py`**

```python
from rivalradar.agents.analyst import (
    evidence_for, FeatureExtraction, PersonaExtraction, ComparisonExtraction,
)
from rivalradar.schema.models import Evidence, FeatureItem


def _ev(eid, competitor, dimension):
    return Evidence(id=eid, competitor=competitor, dimension=dimension, content="c",
                    source_url="u", source_title="t", language="en", fetched_at="2026-05-25T00:00:00Z")


def test_evidence_for_filters_by_competitor():
    evs = [_ev("1", "Notion", "pricing"), _ev("2", "飞书", "pricing")]
    out = evidence_for(evs, "Notion")
    assert [e.id for e in out] == ["1"]


def test_evidence_for_filters_by_competitor_and_dimension():
    evs = [_ev("1", "Notion", "pricing"), _ev("2", "Notion", "core_workflows")]
    out = evidence_for(evs, "Notion", dimension="pricing")
    assert [e.id for e in out] == ["1"]


def test_wrapper_models_hold_lists():
    fe = FeatureExtraction(items=[FeatureItem(id="f1", name="db", description="", category="core_workflows")])
    assert fe.items[0].id == "f1"
    assert PersonaExtraction(personas=[]).personas == []
    assert ComparisonExtraction(rows=[]).rows == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/agents/analyst.py`(helper + 包装模型)**

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from rivalradar.schema.models import (
    ComparisonRow, Evidence, FeatureItem, UserPersona,
)


# structured_call 返回单个 BaseModel;抽取 list 用 wrapper 模型
class FeatureExtraction(BaseModel):
    items: list[FeatureItem] = Field(default_factory=list)


class PersonaExtraction(BaseModel):
    personas: list[UserPersona] = Field(default_factory=list)


class ComparisonExtraction(BaseModel):
    rows: list[ComparisonRow] = Field(default_factory=list)


def evidence_for(
    evidence: list[Evidence], competitor: str, *, dimension: str | None = None
) -> list[Evidence]:
    """过滤出某竞品(可选某维度)的证据,缩小喂给 LLM 的上下文。"""
    return [
        e for e in evidence
        if e.competitor == competitor and (dimension is None or e.dimension == dimension)
    ]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/analyst.py tests/test_analyst_agent.py
git commit -m "feat: analyst evidence filter + list extraction wrapper models"
```

---

### Task 3:分析 Agent —— 逐项结构化抽取(features/pricing/personas/swot)

**Files:**
- Modify: `rivalradar/agents/analyst.py`(追加抽取函数)
- Test: `tests/test_analyst_agent.py`(追加抽取测试,用 FakeClient)

> 每个抽取一次 `structured_call`(小 schema)。证据以编号清单注入 prompt,要求结论挂 `evidence_refs`(evidence_id 必须取自给定证据、quote 为被引原句)。FakeClient 返回 canned tool_call 参数,离线验证"把证据喂进去、把结构化结果拿出来"。

- [ ] **Step 1: 追加失败测试到 `tests/test_analyst_agent.py`**

```python
import json
from types import SimpleNamespace

from rivalradar.agents.analyst import (
    extract_features, extract_pricing, build_evidence_block,
)
from rivalradar.schema.models import PricingModel


class _Completions:
    def __init__(self, payloads):
        self.payloads = list(payloads); self.calls = 0; self.last_kwargs = None
    def create(self, **kwargs):
        self.last_kwargs = kwargs
        p = self.payloads[self.calls]; self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=p))]))],
            usage=SimpleNamespace(total_tokens=10))


class _FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=_Completions(payloads))


def test_build_evidence_block_numbers_and_ids():
    block = build_evidence_block([_ev("e1", "Notion", "pricing"), _ev("e2", "Notion", "pricing")])
    assert "e1" in block and "e2" in block  # evidence_id 出现,供模型引用


def test_extract_features_returns_feature_items():
    payload = json.dumps({"items": [
        {"id": "f1", "name": "数据库", "description": "表格", "category": "core_workflows",
         "evidence_refs": [{"evidence_id": "e1", "quote": "支持数据库", "support_verdict": "supported"}]}]})
    client = _FakeClient([payload])
    feats = extract_features([_ev("e1", "Notion", "core_workflows")], "Notion",
                             client=client, model="m")
    assert feats[0].name == "数据库"
    assert feats[0].evidence_refs[0].evidence_id == "e1"


def test_extract_pricing_returns_pricing_model():
    payload = json.dumps({"model_type": "freemium", "tiers": [
        {"name": "Free", "price": "$0", "billing_cycle": "monthly"}], "evidence_refs": []})
    client = _FakeClient([payload])
    pricing = extract_pricing([_ev("e1", "Notion", "pricing")], "Notion", client=client, model="m")
    assert isinstance(pricing, PricingModel) and pricing.model_type == "freemium"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py -v`
Expected: FAIL（ImportError:extract_features 等未定义）

- [ ] **Step 3: 追加到 `rivalradar/agents/analyst.py`**

```python
from rivalradar.llm.structured import structured_call
from rivalradar.schema.models import PricingModel, SWOT


def build_evidence_block(evidence: list[Evidence]) -> str:
    """把证据编号成清单注入 prompt,标出 evidence_id 供模型在 evidence_refs 里引用。"""
    lines = []
    for e in evidence:
        snippet = (e.content or "")[:1200]
        lines.append(f"[evidence_id={e.id}] ({e.source_title} | {e.source_url})\n{snippet}")
    return "\n\n".join(lines)


_REFS_RULE = (
    "只依据下面证据作答,不得编造。每条结论必须挂 evidence_refs,其中 evidence_id "
    "只能取自给定证据的 evidence_id,quote 为被引的原句。无证据支撑的结论不要输出。"
)


def extract_features(evidence: list[Evidence], competitor: str, *, client, model) -> list[FeatureItem]:
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。抽取其功能项(用 parent_id 表父子层级,"
             f"category 取功能类别)。\n\n证据:\n{block}"}]
    return structured_call(FeatureExtraction, msgs, client=client, model=model).items


def extract_pricing(evidence: list[Evidence], competitor: str, *, client, model) -> PricingModel:
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。抽取其定价模型(model_type 与各 tier)。\n\n证据:\n{block}"}]
    return structured_call(PricingModel, msgs, client=client, model=model)


def extract_personas(evidence: list[Evidence], competitor: str, *, client, model) -> list[UserPersona]:
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。从公开用户评价抽取用户画像(segment/needs/"
             f"pain_points/praise)。\n\n证据:\n{block}"}]
    return structured_call(PersonaExtraction, msgs, client=client, model=model).personas


def extract_swot(evidence: list[Evidence], competitor: str, *, client, model) -> SWOT:
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。基于证据给出 SWOT(每点挂 evidence_refs)。\n\n证据:\n{block}"}]
    return structured_call(SWOT, msgs, client=client, model=model)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/analyst.py tests/test_analyst_agent.py
git commit -m "feat: analyst per-dimension structured extraction with evidence refs"
```

---

### Task 4:分析 Agent —— 拼装 Profile + 跨竞品对比 + analyze()

**Files:**
- Modify: `rivalradar/agents/analyst.py`(追加 profile 拼装、对比、顶层 analyze)
- Test: `tests/test_analyst_agent.py`(追加)

> 逐竞品抽取后拼 `CompetitorProfile`;收尾用一次 `structured_call` 在受控本体下产出类型化对比(spec D5 / §6 Codex #3)。`analyze()` 是分析 Agent 入口:evidence → CompetitorAnalysis。

- [ ] **Step 1: 追加失败测试到 `tests/test_analyst_agent.py`**

```python
from rivalradar.agents.analyst import analyze_competitor, build_comparison, analyze
from rivalradar.schema.models import CompetitorAnalysis, CompetitorProfile


def _profile_payloads():
    # 顺序:features, pricing, personas, swot
    return [
        json.dumps({"items": [{"id": "f1", "name": "db", "description": "", "category": "core_workflows", "evidence_refs": []}]}),
        json.dumps({"model_type": "freemium", "tiers": [], "evidence_refs": []}),
        json.dumps({"personas": []}),
        json.dumps({"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}),
    ]


def test_analyze_competitor_assembles_profile():
    client = _FakeClient(_profile_payloads())
    prof = analyze_competitor([_ev("e1", "Notion", "core_workflows")], "Notion", client=client, model="m")
    assert isinstance(prof, CompetitorProfile)
    assert prof.name == "Notion" and prof.features[0].name == "db"
    assert prof.pricing.model_type == "freemium"


def test_build_comparison_returns_rows():
    payload = json.dumps({"rows": [{"dimension": "pricing", "cells": [
        {"competitor": "Notion", "value_type": "number", "value": "0", "evidence_refs": []}]}]})
    client = _FakeClient([payload])
    rows = build_comparison([CompetitorProfile(name="Notion",
                             pricing=PricingModel(model_type="freemium"), swot=SWOT())],
                            [_ev("e1", "Notion", "pricing")], client=client, model="m")
    assert rows[0].dimension == "pricing"


def test_analyze_end_to_end_with_fake_client():
    # 1 竞品:4 次抽取 + 1 次对比 = 5 次调用
    payloads = _profile_payloads() + [json.dumps({"rows": []})]
    client = _FakeClient(payloads)
    out = analyze([_ev("e1", "Notion", "core_workflows")], ["Notion"], client=client, model="m")
    assert isinstance(out, CompetitorAnalysis)
    assert out.competitors[0].name == "Notion"
    assert client.chat.completions.calls == 5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py -v`
Expected: FAIL（ImportError:analyze 等未定义）

- [ ] **Step 3: 追加到 `rivalradar/agents/analyst.py`**

```python
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, CONTROLLED_DIMENSIONS,
)


def analyze_competitor(evidence: list[Evidence], competitor: str, *, client, model) -> CompetitorProfile:
    """对单个竞品做四项抽取并拼成 CompetitorProfile。"""
    ev = evidence_for(evidence, competitor)
    return CompetitorProfile(
        name=competitor,
        features=extract_features(evidence_for(ev, competitor, dimension="core_workflows") or ev, competitor, client=client, model=model),
        pricing=extract_pricing(evidence_for(ev, competitor, dimension="pricing") or ev, competitor, client=client, model=model),
        personas=extract_personas(evidence_for(ev, competitor, dimension="review_sentiment") or ev, competitor, client=client, model=model),
        swot=extract_swot(ev, competitor, client=client, model=model),
    )


def build_comparison(profiles: list[CompetitorProfile], evidence: list[Evidence], *, client, model) -> list[ComparisonRow]:
    """收尾产出跨竞品对比(受控本体 + 类型化值 + evidence_refs,spec D5 / §6)。"""
    names = ", ".join(p.name for p in profiles)
    dims = ", ".join(CONTROLLED_DIMENSIONS)
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n对竞品 [{names}] 在这些维度做横向对比:{dims}。"
             f"每个 cell 标 value_type(bool/enum/number/quote_text)与 value,并挂 evidence_refs。"
             f"\n\n证据:\n{block}"}]
    return structured_call(ComparisonExtraction, msgs, client=client, model=model).rows


def analyze(evidence: list[Evidence], competitors: list[str], *, client, model) -> CompetitorAnalysis:
    """分析 Agent 入口:证据 → 结构化分析(逐竞品 profile + 跨竞品对比)。"""
    profiles = [analyze_competitor(evidence, c, client=client, model=model) for c in competitors]
    comparison = build_comparison(profiles, evidence, client=client, model=model)
    return CompetitorAnalysis(competitors=profiles, comparison=comparison)
```

> 注:`analyze_competitor` 里 `evidence_for(ev, competitor, dimension=...) or ev` 表示"优先用该维度证据,没有就退回全部该竞品证据",保证小 schema 抽取仍有上下文。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_analyst_agent.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/agents/analyst.py tests/test_analyst_agent.py
git commit -m "feat: analyst profile assembly + typed comparison + analyze() entry"
```

---

### Task 5:🚧 真实分析 E2E(待 ARK key,GATE-lite)

**Files:**
- Create: `spikes/spike_d_analyze_real.py`

> 用真实 Doubao 对一组 canned 证据跑 `analyze()`,确认逐项抽取 + 对比能在真实模型上拿到合法 `CompetitorAnalysis` 且结论挂上了 evidence_refs。需 `ARK_API_KEY`(已配)。

- [ ] **Step 1: 写 `spikes/spike_d_analyze_real.py`**

```python
"""分析 Agent 真实 E2E:canned 证据 → analyze() → CompetitorAnalysis。需 ARK_API_KEY。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.agents.analyst import analyze
from rivalradar.schema.models import Evidence

EVIDENCE = [
    Evidence(id="e1", competitor="Notion", dimension="pricing",
             content="Notion offers a Free plan, Plus at $10/user/month, and Business tiers.",
             source_url="https://notion.so/pricing", source_title="Pricing", language="en",
             fetched_at="2026-05-25T00:00:00Z"),
    Evidence(id="e2", competitor="Notion", dimension="core_workflows",
             content="Notion includes docs, wikis, projects, and databases with multiple views.",
             source_url="https://notion.so/product", source_title="Product", language="en",
             fetched_at="2026-05-25T00:00:00Z"),
]


def main() -> None:
    client = config.get_doubao_client()
    out = analyze(EVIDENCE, ["Notion"], client=client, model=config.doubao_model())
    prof = out.competitors[0]
    print(f"competitor: {prof.name}")
    print(f"features: {[f.name for f in prof.features]}")
    print(f"pricing: {prof.pricing.model_type}, tiers={[t.name for t in prof.pricing.tiers]}")
    print(f"comparison rows: {[r.dimension for r in out.comparison]}")
    # 至少有一条结论挂了取自给定证据的 evidence_ref
    ref_ids = {r.evidence_id for f in prof.features for r in f.evidence_refs}
    ref_ids |= {r.evidence_id for r in prof.pricing.evidence_refs}
    print(f"cited evidence_ids: {ref_ids}")
    assert ref_ids & {"e1", "e2"}, "no conclusion cited the provided evidence"
    print("SPIKE D OK: real analysis with evidence refs")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑(需 key)**

Run: `.venv/bin/python spikes/spike_d_analyze_real.py`
Expected: 打印竞品/功能/定价/对比 + cited evidence_ids 含 e1/e2;末行 `SPIKE D OK`。
若无 key:GATE-lite,交用户带 key 跑。

- [ ] **Step 3: 提交**

```bash
git add spikes/spike_d_analyze_real.py
git commit -m "spike: real analyst analyze() over canned evidence (evidence refs)"
```

---

## Self-Review(写完计划后自查)

**1. Spec / 决策覆盖**
- 采集 Agent(包装 C-1 + 清洗 + 来源优先级)→ Task 1 ✅(§5 采集;终审遗留①②)
- 分析 Agent 逐项结构化 + 句级 evidence_refs → Task 2-3 ✅(§5/§6,Codex #2)
- 拼装 Profile + 受控本体类型化对比 → Task 4 ✅(D5 / §6 Codex #3)
- 只引用证据、无证据不写 → `_REFS_RULE` 注入(§5 约束)✅
- 真实 E2E → Task 5 ✅(§13)
- **范围外(C-2b)**:撰写 Agent(确定性渲染,待定夺)、质检 Agent(确定性闸 + LLM 蕴含 + verdict)、`Evidence.dimension` 受控本体校验(放 QC)。**范围外(Lane D)**:图编排、路由、真闭环重试(retry_collect/retry_analyze)。

**2. 占位符扫描**:无 TBD。所有 LLM 路径复用已验证的 `structured_call`(tools);FakeClient 模拟 tool_call 参数(与 `tests/test_structured_call.py` 同构)。

**3. 类型一致性**:`structured_call(model_cls, messages, *, client, model)` 签名与既有实现一致;`FeatureExtraction/PersonaExtraction/ComparisonExtraction` wrapper 的 `.items/.personas/.rows` 在抽取函数中取用一致;`analyze()` 产出 `CompetitorAnalysis`(competitors+comparison)与 schema 一致,可直接 `repository.save_analysis` 落库。FakeClient 调用计数(单竞品 5 次)与 `analyze` 调用序列一致。

**4. 注意 / 待定夺**
- analyst 对单竞品做 5 次 LLM 调用(~5s/次 → ~25s);Lane D 可按竞品并行(线程池)提速,本计划先求正确。
- `analyze_competitor` 目前串行;并行化留给 Lane D 编排。
- 真实抽取质量(evidence_refs 是否真支撑)由 C-2b 的 QC Agent + §13 结论支持度 eval 把关,本计划只保证"结构正确 + 接线正确"。
