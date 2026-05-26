# RivalRadar Lane C-1:采集基础设施 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭好"真实采集"的基础设施——可切换的搜索 provider(Tavily 主 + Exa 备)、合规的安全自抓(黑名单 + robots + 限速)、查询生成、证据构建、并行采集管线——产出带溯源字段的 `Evidence` 列表,供 Lane C-2 的采集 Agent 调度。

**Architecture:** 两个子包。`rivalradar/search/`:`SearchProvider` 协议 + Tavily/Exa adapter + fallback 链。`rivalradar/collect/`:source policy(黑名单+robots)、限速、安全自抓、查询模板、证据构建、`collect()` 并行管线。全部纯逻辑用 mock provider/mock client 离线 TDD;真实 Tavily 集成冒烟单列、需 key。对应 Day-1 锁定决策(见 `spikes/SPIKE_RESULTS.md`)与 spec §7/§8/D6/D8。

**Tech Stack:** Python 3.11+ · Pydantic v2 · tavily-python · exa-py(适配层,真集成待 key)· httpx(自抓)· urllib.robotparser(robots)· concurrent.futures(限并发)· pytest。

---

## 前置:依赖与既有件

- 依赖既有地基:`rivalradar/schema/models.py`(`Evidence`、`CONTROLLED_DIMENSIONS`)、`rivalradar/config.py`(`tavily_api_key()` 等)。
- 需要新增依赖:`exa-py`(adapter)、`httpx` 已随 openai 传递安装但 pyproject 要显式声明。Task 1 顺手补 pyproject。
- 锁定决策(来自 SPIKE_RESULTS.md):Tavily 主 + Exa 备 + 适配层;黑名单采集(默认收任意公开源,红名单只经搜索 API 摘要,不自抓);demo 竞品 Notion + 飞书。

## 文件结构

```
rivalradar/
  search/
    __init__.py
    base.py              # SearchResult 模型 + SearchProvider 协议
    tavily_provider.py   # TavilyProvider
    exa_provider.py      # ExaProvider(适配层,真集成待 key)
    fallback.py          # FallbackSearch(主→备 故障转移)
  collect/
    __init__.py
    policy.py            # RED_DENYLIST + USER_AGENT + is_self_fetch_allowed(robots)
    fetch.py             # safe_fetch(策略 + 每域限速 + httpx)
    queries.py           # generate_queries(按维度×语言模板)
    evidence.py          # to_evidence(SearchResult → Evidence)
    pipeline.py          # collect(并行 + 限并发)
DATA_SOURCES.md          # 合规数据源声明
tests/
  test_search_base.py  test_tavily_provider.py  test_exa_provider.py
  test_fallback.py  test_policy.py  test_fetch.py
  test_queries.py  test_evidence_builder.py  test_collect_pipeline.py
spikes/
  spike_c_collect_integration.py   # 真实 Tavily→Evidence 冒烟(待 key)
```

---

### Task 1:SearchResult 模型 + SearchProvider 协议

**Files:**
- Create: `rivalradar/search/__init__.py`(`# RivalRadar package`)
- Create: `rivalradar/search/base.py`
- Modify: `pyproject.toml`(dependencies 增加 `exa-py>=1.0` 和 `httpx>=0.27`)
- Test: `tests/test_search_base.py`

- [ ] **Step 1: pyproject 增依赖**

在 `pyproject.toml` 的 `dependencies` 列表追加两行(保持其余不动):
```toml
    "exa-py>=1.0",
    "httpx>=0.27",
```
然后 `.venv/bin/pip install -e . >/dev/null 2>&1 || .venv/bin/pip install "exa-py>=1.0" "httpx>=0.27"`(确保 venv 有 exa-py/httpx)。

- [ ] **Step 2: 写失败测试 `tests/test_search_base.py`**

```python
from rivalradar.search.base import SearchResult


def test_search_result_defaults():
    r = SearchResult(url="https://notion.so/pricing", title="Pricing",
                     content="snippet", provider="tavily")
    assert r.raw_content is None
    assert r.published_date is None
    assert r.score is None
    assert r.provider == "tavily"


def test_search_result_full():
    r = SearchResult(url="u", title="t", content="c", raw_content="full",
                     published_date="2026-01-01", score=0.9, provider="exa")
    assert r.raw_content == "full" and r.score == 0.9
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_search_base.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 4: 写 `rivalradar/search/base.py`**

```python
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """统一的搜索结果(各 provider 适配到这一形状)。"""

    url: str
    title: str
    content: str  # 摘要/片段
    raw_content: Optional[str] = None  # 清洗后的页面正文(若 provider 提供)
    published_date: Optional[str] = None
    score: Optional[float] = None
    provider: str = ""


@runtime_checkable
class SearchProvider(Protocol):
    """搜索后端统一接口。Tavily/Exa/Firecrawl 各实现一个。"""

    name: str

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        ...
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_search_base.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 提交**

```bash
git add rivalradar/search/__init__.py rivalradar/search/base.py pyproject.toml tests/test_search_base.py
git commit -m "feat: SearchResult model + SearchProvider protocol"
```

---

### Task 2:TavilyProvider(adapter)

**Files:**
- Create: `rivalradar/search/tavily_provider.py`
- Test: `tests/test_tavily_provider.py`

> Tavily 返回字段已在 spike B 实测:`search(query, max_results, include_raw_content=True)` → `{"results": [{"url","title","content","raw_content","score","published_date"}]}`。适配层用注入的 client 离线测,不打网络。

- [ ] **Step 1: 写失败测试 `tests/test_tavily_provider.py`**

```python
from rivalradar.search.tavily_provider import TavilyProvider


class _FakeTavily:
    def __init__(self, payload):
        self.payload = payload
        self.last_kwargs = None

    def search(self, **kwargs):
        self.last_kwargs = kwargs
        return self.payload


def test_maps_tavily_results_to_search_results():
    fake = _FakeTavily({"results": [
        {"url": "https://notion.so/pricing", "title": "Pricing", "content": "snip",
         "raw_content": "full text", "score": 0.9, "published_date": "2026-01-01"},
        {"url": "https://g2.com/notion", "title": "G2", "content": "review"},
    ]})
    provider = TavilyProvider(client=fake)
    out = provider.search("Notion pricing", max_results=5)
    assert provider.name == "tavily"
    assert [r.url for r in out] == ["https://notion.so/pricing", "https://g2.com/notion"]
    assert out[0].raw_content == "full text" and out[0].score == 0.9
    assert out[1].raw_content is None  # 缺字段安全降级
    assert out[0].provider == "tavily"
    assert fake.last_kwargs["max_results"] == 5
    assert fake.last_kwargs["include_raw_content"] is True


def test_empty_results():
    provider = TavilyProvider(client=_FakeTavily({"results": []}))
    assert provider.search("x") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_tavily_provider.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/search/tavily_provider.py`**

```python
from __future__ import annotations

from rivalradar.search.base import SearchResult


class TavilyProvider:
    """Tavily 搜索后端。client 可注入(测试);默认懒构造 TavilyClient。"""

    name = "tavily"

    def __init__(self, *, api_key: str | None = None, client=None):
        self._client = client
        self._api_key = api_key

    def _get_client(self):
        if self._client is None:
            from tavily import TavilyClient

            self._client = TavilyClient(api_key=self._api_key)
        return self._client

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        resp = self._get_client().search(
            query=query, max_results=max_results, include_raw_content=True
        )
        out: list[SearchResult] = []
        for r in resp.get("results", []):
            out.append(SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                content=r.get("content", ""),
                raw_content=r.get("raw_content"),
                published_date=r.get("published_date"),
                score=r.get("score"),
                provider=self.name,
            ))
        return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_tavily_provider.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/search/tavily_provider.py tests/test_tavily_provider.py
git commit -m "feat: TavilyProvider adapter"
```

---

### Task 3:ExaProvider(adapter,真集成待 key)

**Files:**
- Create: `rivalradar/search/exa_provider.py`
- Test: `tests/test_exa_provider.py`

> Exa SDK:`Exa(api_key).search_and_contents(query, text=True, num_results=n)` → 响应对象 `.results`,每条有 `.url/.title/.text/.highlights/.published_date/.score`。client 注入离线测;真实 Exa 集成等有 key 再验。

- [ ] **Step 1: 写失败测试 `tests/test_exa_provider.py`**

```python
from types import SimpleNamespace

from rivalradar.search.exa_provider import ExaProvider


class _FakeExa:
    def __init__(self, results):
        self._results = results
        self.last_kwargs = None

    def search_and_contents(self, query, **kwargs):
        self.last_kwargs = {"query": query, **kwargs}
        return SimpleNamespace(results=self._results)


def _r(url, title, text, date=None, score=None):
    return SimpleNamespace(url=url, title=title, text=text,
                           published_date=date, score=score)


def test_maps_exa_results():
    fake = _FakeExa([_r("https://notion.so", "Notion", "full body text", "2026-02-02", 0.7)])
    provider = ExaProvider(client=fake)
    out = provider.search("Notion", max_results=3)
    assert provider.name == "exa"
    assert out[0].url == "https://notion.so"
    assert out[0].raw_content == "full body text"
    assert out[0].content  # 由正文截出的摘要,非空
    assert out[0].published_date == "2026-02-02"
    assert out[0].provider == "exa"
    assert fake.last_kwargs["num_results"] == 3


def test_handles_missing_optional_fields():
    fake = _FakeExa([_r("u", "t", "body")])
    out = ExaProvider(client=fake).search("q")
    assert out[0].published_date is None and out[0].score is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_exa_provider.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/search/exa_provider.py`**

```python
from __future__ import annotations

from rivalradar.search.base import SearchResult

_SNIPPET_CHARS = 300


class ExaProvider:
    """Exa 搜索后端(语义检索,作 Tavily 备用)。client 可注入(测试)。

    Exa 只回正文 text,无独立摘要字段 → 摘要取正文前 N 字。
    """

    name = "exa"

    def __init__(self, *, api_key: str | None = None, client=None):
        self._client = client
        self._api_key = api_key

    def _get_client(self):
        if self._client is None:
            from exa_py import Exa

            self._client = Exa(self._api_key)
        return self._client

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        resp = self._get_client().search_and_contents(
            query, text=True, num_results=max_results
        )
        out: list[SearchResult] = []
        for r in resp.results:
            text = getattr(r, "text", "") or ""
            out.append(SearchResult(
                url=getattr(r, "url", "") or "",
                title=getattr(r, "title", "") or "",
                content=text[:_SNIPPET_CHARS],
                raw_content=text or None,
                published_date=getattr(r, "published_date", None),
                score=getattr(r, "score", None),
                provider=self.name,
            ))
        return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_exa_provider.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/search/exa_provider.py tests/test_exa_provider.py
git commit -m "feat: ExaProvider adapter (fallback; real integration awaits key)"
```

---

### Task 4:FallbackSearch(主→备 故障转移)

**Files:**
- Create: `rivalradar/search/fallback.py`
- Test: `tests/test_fallback.py`

- [ ] **Step 1: 写失败测试 `tests/test_fallback.py`**

```python
import pytest

from rivalradar.search.base import SearchResult
from rivalradar.search.fallback import FallbackSearch, AllProvidersFailedError


class _StubProvider:
    def __init__(self, name, *, results=None, error=None):
        self.name = name
        self._results = results or []
        self._error = error
        self.calls = 0

    def search(self, query, *, max_results=5):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._results


def _res(url):
    return [SearchResult(url=url, title="t", content="c", provider="x")]


def test_uses_primary_when_it_succeeds():
    primary = _StubProvider("tavily", results=_res("p"))
    backup = _StubProvider("exa", results=_res("b"))
    fb = FallbackSearch([primary, backup])
    out = fb.search("q")
    assert out[0].url == "p"
    assert backup.calls == 0  # 没轮到备用


def test_falls_back_on_primary_error():
    primary = _StubProvider("tavily", error=RuntimeError("quota exhausted"))
    backup = _StubProvider("exa", results=_res("b"))
    fb = FallbackSearch([primary, backup])
    out = fb.search("q")
    assert out[0].url == "b"
    assert primary.calls == 1 and backup.calls == 1


def test_raises_when_all_fail():
    p1 = _StubProvider("tavily", error=RuntimeError("x"))
    p2 = _StubProvider("exa", error=RuntimeError("y"))
    with pytest.raises(AllProvidersFailedError):
        FallbackSearch([p1, p2]).search("q")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_fallback.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/search/fallback.py`**

```python
from __future__ import annotations

import logging

from rivalradar.search.base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)


class AllProvidersFailedError(RuntimeError):
    """所有搜索 provider 都失败 —— 显式抛出,不静默返回空。"""


class FallbackSearch:
    """按顺序尝试 provider,某个抛错(额度耗尽/网络)就切下一个(spec D8 / SPIKE 决策)。"""

    name = "fallback"

    def __init__(self, providers: list[SearchProvider]):
        if not providers:
            raise ValueError("FallbackSearch 至少需要一个 provider")
        self._providers = providers

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        errors: list[str] = []
        for p in self._providers:
            try:
                return p.search(query, max_results=max_results)
            except Exception as e:  # noqa: BLE001 — 故意兜所有 provider 异常以切换
                logger.warning("search provider %s failed: %s", getattr(p, "name", "?"), e)
                errors.append(f"{getattr(p, 'name', '?')}: {e}")
        raise AllProvidersFailedError("; ".join(errors))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_fallback.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/search/fallback.py tests/test_fallback.py
git commit -m "feat: FallbackSearch with provider failover"
```

---

### Task 5:Source policy(红名单 + robots)

**Files:**
- Create: `rivalradar/collect/__init__.py`(`# RivalRadar package`)
- Create: `rivalradar/collect/policy.py`
- Test: `tests/test_policy.py`

> 黑名单模型(SPIKE 决策):自抓某 URL 前,先查红名单(知乎/小红书/微博/脉脉/即刻 — 这些只经搜索 API 摘要,不自抓),再按诚实 UA 查 robots。robots 解析器可注入,离线测不打网络。

- [ ] **Step 1: 写失败测试 `tests/test_policy.py`**

```python
from rivalradar.collect.policy import (
    RED_DENYLIST, USER_AGENT, is_denylisted, is_self_fetch_allowed,
)


def test_denylist_blocks_red_domains():
    assert is_denylisted("https://www.zhihu.com/question/123")
    assert is_denylisted("https://xiaohongshu.com/x")
    assert not is_denylisted("https://notion.so/pricing")
    assert "zhihu.com" in RED_DENYLIST


class _FakeRobots:
    def __init__(self, allow):
        self._allow = allow

    def can_fetch(self, ua, url):
        return self._allow


def test_self_fetch_blocked_for_denylisted_even_if_robots_ok():
    allowed = is_self_fetch_allowed(
        "https://zhihu.com/x", robots_for=lambda d: _FakeRobots(True))
    assert allowed is False


def test_self_fetch_respects_robots_for_normal_site():
    assert is_self_fetch_allowed(
        "https://example.com/a", robots_for=lambda d: _FakeRobots(True)) is True
    assert is_self_fetch_allowed(
        "https://example.com/b", robots_for=lambda d: _FakeRobots(False)) is False


def test_user_agent_is_honest_identifier():
    assert "RivalRadar" in USER_AGENT
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_policy.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/collect/policy.py`**

```python
from __future__ import annotations

import urllib.robotparser
from collections.abc import Callable
from urllib.parse import urlparse

# 诚实 UA(spec D6:不冒充,标明身份)
USER_AGENT = "RivalRadarBot/0.1 (+competitive research; respects robots.txt)"

# 红名单:只经搜索 API 公开摘要间接用,绝不自抓原站
# 理由见 spikes/SPIKE_RESULTS.md(robots 全站禁 + 2025 反不正当竞争法 + PIPL + ToS)
RED_DENYLIST: frozenset[str] = frozenset({
    "zhihu.com", "xiaohongshu.com", "xhslink.com",
    "weibo.com", "maimai.cn", "okjike.com",
})


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def is_denylisted(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) or host.removeprefix("www.") == d
               for d in RED_DENYLIST)


def _default_robots_for(domain: str):
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"https://{domain}/robots.txt")
    try:
        rp.read()
    except Exception:
        # 取不到 robots.txt → 保守起见视为可读(标准爬虫惯例),但仍受限速约束
        return None
    return rp


def is_self_fetch_allowed(
    url: str,
    *,
    robots_for: Callable[[str], object] | None = None,
    user_agent: str = USER_AGENT,
) -> bool:
    """能否自抓该 URL:红名单一律 False;否则按诚实 UA 查 robots。robots_for 可注入(测试)。"""
    if is_denylisted(url):
        return False
    fetch_robots = robots_for or _default_robots_for
    rp = fetch_robots(_domain(url))
    if rp is None:
        return True
    return rp.can_fetch(user_agent, url)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_policy.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/collect/__init__.py rivalradar/collect/policy.py tests/test_policy.py
git commit -m "feat: source policy (red denylist + robots check, honest UA)"
```

---

### Task 6:safe_fetch(策略 + 每域限速 + httpx)

**Files:**
- Create: `rivalradar/collect/fetch.py`
- Test: `tests/test_fetch.py`

> safe_fetch 把 policy + 限速 + HTTP 取页串起来。限速用每域最小间隔 + 可注入时钟/sleep;HTTP client 可注入。被策略拒的 URL 返回 None(不抛),让上层降级到只用搜索 API 摘要。

- [ ] **Step 1: 写失败测试 `tests/test_fetch.py`**

```python
from rivalradar.collect.fetch import RateLimiter, safe_fetch


def test_rate_limiter_waits_per_domain():
    now = [0.0]
    slept = []
    rl = RateLimiter(min_interval=2.0, clock=lambda: now[0], sleep=slept.append)
    rl.wait("example.com")          # 首次不等
    assert slept == []
    rl.wait("example.com")          # 立刻再来 → 等 2s
    assert slept == [2.0]
    rl.wait("other.com")            # 不同域 → 不等
    assert slept == [2.0]


class _FakeResp:
    def __init__(self, text): self.text = text
    def raise_for_status(self): pass


class _FakeHTTP:
    def __init__(self, text): self._text = text; self.got = None
    def get(self, url, headers=None, timeout=None):
        self.got = url
        return _FakeResp(self._text)


def test_safe_fetch_blocked_returns_none():
    http = _FakeHTTP("body")
    out = safe_fetch("https://zhihu.com/x", http=http,
                     allowed=lambda u: False, limiter=_NoWait())
    assert out is None and http.got is None  # 被拒,根本没发请求


def test_safe_fetch_allowed_returns_text():
    http = _FakeHTTP("<p>hello</p>")
    out = safe_fetch("https://example.com/a", http=http,
                     allowed=lambda u: True, limiter=_NoWait())
    assert out == "<p>hello</p>" and http.got == "https://example.com/a"


class _NoWait:
    def wait(self, domain): pass
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_fetch.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/collect/fetch.py`**

```python
from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlparse

from rivalradar.collect.policy import USER_AGENT, is_self_fetch_allowed


class RateLimiter:
    """每域最小间隔限速(spec D8)。clock/sleep 可注入以便测试。"""

    def __init__(self, *, min_interval: float = 1.0,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self._min = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}

    def wait(self, domain: str) -> None:
        now = self._clock()
        last = self._last.get(domain)
        if last is not None:
            gap = self._min - (now - last)
            if gap > 0:
                self._sleep(gap)
                now = now + gap
        self._last[domain] = now


def safe_fetch(
    url: str,
    *,
    http=None,
    allowed: Callable[[str], bool] = is_self_fetch_allowed,
    limiter: RateLimiter | None = None,
    timeout: float = 10.0,
) -> str | None:
    """合规自抓:被策略拒 → None(不抛);否则限速后 httpx GET 返回正文文本,失败 → None。"""
    if not allowed(url):
        return None
    limiter = limiter or RateLimiter()
    limiter.wait(urlparse(url).netloc.lower())
    if http is None:
        import httpx

        http = httpx.Client(follow_redirects=True)
    try:
        resp = http.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_fetch.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/collect/fetch.py tests/test_fetch.py
git commit -m "feat: safe_fetch with per-domain rate limit and policy gate"
```

---

### Task 7:查询生成(按维度×语言模板)

**Files:**
- Create: `rivalradar/collect/queries.py`
- Test: `tests/test_queries.py`

> spec §7:按竞品×维度生成中/英检索词。先用确定性模板(简单、可测、零成本);LLM 精炼留给 C-2 采集 Agent。维度用受控本体 `CONTROLLED_DIMENSIONS`。

- [ ] **Step 1: 写失败测试 `tests/test_queries.py`**

```python
from rivalradar.collect.queries import Query, generate_queries
from rivalradar.schema.models import CONTROLLED_DIMENSIONS


def test_generates_query_per_dimension_and_language():
    qs = generate_queries("Notion", ["pricing", "integrations"], languages=("en", "zh"))
    # 2 维度 × 2 语言 = 4 条
    assert len(qs) == 4
    assert all(isinstance(q, Query) for q in qs)
    assert all(q.competitor == "Notion" for q in qs)
    langs = {(q.dimension, q.language) for q in qs}
    assert ("pricing", "en") in langs and ("pricing", "zh") in langs


def test_query_text_includes_competitor_and_is_language_appropriate():
    [en] = [q for q in generate_queries("Notion", ["pricing"], languages=("en",))]
    assert "Notion" in en.query_text and "pricing" in en.query_text.lower()
    [zh] = [q for q in generate_queries("飞书", ["pricing"], languages=("zh",))]
    assert "飞书" in zh.query_text and "价格" in zh.query_text


def test_unknown_dimension_falls_back_to_generic_template():
    [q] = generate_queries("X", ["made_up_dim"], languages=("en",))
    assert "X" in q.query_text and "made_up_dim" in q.query_text


def test_all_controlled_dimensions_have_templates():
    qs = generate_queries("X", list(CONTROLLED_DIMENSIONS), languages=("en", "zh"))
    assert len(qs) == len(CONTROLLED_DIMENSIONS) * 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_queries.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/collect/queries.py`**

```python
from __future__ import annotations

from pydantic import BaseModel

# 每(维度, 语言)一个查询模板;{c} 处插竞品名。受控本体见 schema.models.CONTROLLED_DIMENSIONS。
_TEMPLATES: dict[tuple[str, str], str] = {
    ("pricing", "en"): "{c} pricing plans cost",
    ("pricing", "zh"): "{c} 价格 套餐 收费",
    ("deployment", "en"): "{c} deployment self-hosted SSO enterprise",
    ("deployment", "zh"): "{c} 部署 私有化 企业版 SSO",
    ("integrations", "en"): "{c} integrations API supported apps",
    ("integrations", "zh"): "{c} 集成 API 支持的应用",
    ("target_users", "en"): "{c} who is it for target users use cases",
    ("target_users", "zh"): "{c} 适合谁 目标用户 使用场景",
    ("core_workflows", "en"): "{c} key features core workflows",
    ("core_workflows", "zh"): "{c} 核心功能 主要特性",
    ("review_sentiment", "en"): "{c} reviews pros cons user feedback",
    ("review_sentiment", "zh"): "{c} 用户评价 优缺点 测评",
}


class Query(BaseModel):
    competitor: str
    dimension: str
    language: str
    query_text: str


def generate_queries(
    competitor: str,
    dimensions: list[str],
    *,
    languages: tuple[str, ...] = ("en", "zh"),
) -> list[Query]:
    out: list[Query] = []
    for dim in dimensions:
        for lang in languages:
            template = _TEMPLATES.get((dim, lang)) or _generic(lang)
            out.append(Query(
                competitor=competitor, dimension=dim, language=lang,
                query_text=template.format(c=competitor, dim=dim),
            ))
    return out


def _generic(lang: str) -> str:
    return "{c} {dim}" if lang == "en" else "{c} {dim} 介绍"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_queries.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/collect/queries.py tests/test_queries.py
git commit -m "feat: per-dimension/language search query templates"
```

---

### Task 8:证据构建(SearchResult → Evidence)

**Files:**
- Create: `rivalradar/collect/evidence.py`
- Test: `tests/test_evidence_builder.py`

> 把 SearchResult 转成带溯源字段的 `Evidence`。content 优先用 raw_content(更全),无则用摘要;id 用稳定哈希(竞品+维度+url),fetched_at 用当前 UTC。

- [ ] **Step 1: 写失败测试 `tests/test_evidence_builder.py`**

```python
from rivalradar.collect.evidence import to_evidence
from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchResult


def _sr(url="https://notion.so/pricing", raw="full body", content="snip"):
    return SearchResult(url=url, title="Pricing", content=content,
                        raw_content=raw, provider="tavily")


def test_builds_evidence_with_source_fields():
    ev = to_evidence(_sr(), competitor="Notion", dimension="pricing", language="en")
    assert isinstance(ev, Evidence)
    assert ev.competitor == "Notion" and ev.dimension == "pricing"
    assert ev.source_url == "https://notion.so/pricing"
    assert ev.source_title == "Pricing"
    assert ev.language == "en"
    assert ev.content == "full body"   # 优先 raw_content
    assert ev.fetched_at  # 非空 ISO 时间
    assert ev.id  # 非空稳定 id


def test_falls_back_to_snippet_when_no_raw():
    ev = to_evidence(_sr(raw=None), competitor="Notion", dimension="pricing", language="en")
    assert ev.content == "snip"


def test_id_is_stable_for_same_inputs():
    a = to_evidence(_sr(), competitor="Notion", dimension="pricing", language="en")
    b = to_evidence(_sr(), competitor="Notion", dimension="pricing", language="en")
    assert a.id == b.id  # 同竞品+维度+url → 同 id(去重友好)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_evidence_builder.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/collect/evidence.py`**

```python
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchResult


def _evidence_id(competitor: str, dimension: str, url: str) -> str:
    raw = f"{competitor}|{dimension}|{url}".encode()
    return "ev_" + hashlib.sha1(raw).hexdigest()[:12]


def to_evidence(
    result: SearchResult,
    *,
    competitor: str,
    dimension: str,
    language: str,
) -> Evidence:
    """SearchResult → Evidence(带溯源)。content 优先正文,无则摘要。id 稳定可去重。"""
    content = result.raw_content or result.content
    return Evidence(
        id=_evidence_id(competitor, dimension, result.url),
        competitor=competitor,
        dimension=dimension,
        content=content,
        source_url=result.url,
        source_title=result.title,
        language=language,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_evidence_builder.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/collect/evidence.py tests/test_evidence_builder.py
git commit -m "feat: evidence builder from search results with stable id"
```

---

### Task 9:采集管线 collect()(并行 + 限并发)

**Files:**
- Create: `rivalradar/collect/pipeline.py`
- Test: `tests/test_collect_pipeline.py`

> 把 查询生成 → 搜索 → 证据构建 串起来,用 `ThreadPoolExecutor` 限并发并行(spec D8;Tavily/Exa 是同步 I/O,线程池合适)。provider 注入(mock)离线测,断言并行产出 + 限并发。去重:同 id 证据只留一条。

- [ ] **Step 1: 写失败测试 `tests/test_collect_pipeline.py`**

```python
import threading

from rivalradar.collect.pipeline import collect
from rivalradar.search.base import SearchResult


class _MockProvider:
    """每个 query 回 1 条结果;记录并发峰值以验限并发。"""

    name = "mock"

    def __init__(self, max_workers_seen=None):
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def search(self, query, *, max_results=5):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            return [SearchResult(url=f"https://x/{query}", title=query,
                                 content="c", raw_content="body", provider="mock")]
        finally:
            with self._lock:
                self.active -= 1


def test_collect_produces_evidence_per_query():
    provider = _MockProvider()
    evs = collect(["Notion"], ["pricing", "integrations"], provider=provider,
                  languages=("en",), max_workers=4)
    # 1 竞品 × 2 维度 × 1 语言 = 2 条证据
    assert len(evs) == 2
    assert {e.dimension for e in evs} == {"pricing", "integrations"}
    assert all(e.competitor == "Notion" and e.content == "body" for e in evs)


def test_bounded_concurrency_respected():
    provider = _MockProvider()
    collect(["A", "B", "C"], list("pqrs"), provider=provider,
            languages=("en", "zh"), max_workers=3)
    assert provider.peak <= 3  # 限并发生效


def test_dedupes_same_evidence_id():
    class _DupProvider:
        name = "dup"
        def search(self, query, *, max_results=5):
            return [SearchResult(url="https://same", title="t", content="c",
                                 raw_content="b", provider="dup")]
    evs = collect(["Notion"], ["pricing"], provider=_DupProvider(),
                  languages=("en", "zh"), max_workers=2)
    # 同 competitor+dimension+url → 同 id;en/zh 两查询命中同 url → 去重留 1
    assert len(evs) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_collect_pipeline.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `rivalradar/collect/pipeline.py`**

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from rivalradar.collect.evidence import to_evidence
from rivalradar.collect.queries import Query, generate_queries
from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchProvider


def _run_query(provider: SearchProvider, q: Query, max_results: int) -> list[Evidence]:
    results = provider.search(q.query_text, max_results=max_results)
    return [to_evidence(r, competitor=q.competitor, dimension=q.dimension,
                        language=q.language) for r in results]


def collect(
    competitors: list[str],
    dimensions: list[str],
    *,
    provider: SearchProvider,
    languages: tuple[str, ...] = ("en", "zh"),
    max_results: int = 5,
    max_workers: int = 4,
) -> list[Evidence]:
    """并行采集:竞品×维度×语言 → 查询 → 搜索 → 证据,限并发 max_workers,按 id 去重(spec §7/D8)。"""
    queries: list[Query] = []
    for c in competitors:
        queries.extend(generate_queries(c, dimensions, languages=languages))

    by_id: dict[str, Evidence] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for evs in pool.map(lambda q: _run_query(provider, q, max_results), queries):
            for ev in evs:
                by_id.setdefault(ev.id, ev)
    return list(by_id.values())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_collect_pipeline.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add rivalradar/collect/pipeline.py tests/test_collect_pipeline.py
git commit -m "feat: parallel collect pipeline with bounded concurrency and dedupe"
```

---

### Task 10:DATA_SOURCES.md(合规声明)

**Files:**
- Create: `DATA_SOURCES.md`

> 不是 TDD;是 spec D6 / 10% 合规分要求的数据源声明。按 绿/灰/红 三级,内容对齐 policy.py 的红名单与 SPIKE_RESULTS 的决策。

- [ ] **Step 1: 写 `DATA_SOURCES.md`**

```markdown
# 数据来源与合规声明(RivalRadar)

RivalRadar 仅采集**公开**竞品信息,遵守 robots.txt、限速、诚实 UA(`RivalRadarBot/0.1`),
并对每次运行记录实际访问的来源以备审计。

## 绿色(直接采集)
- 搜索 API(Tavily 主 / Exa 备)返回的公开搜索结果与摘要 —— 合规义务由 API 方承担
- 竞品官方网站 / 文档 / 定价页(robots 允许路径)
- Apple App Store 公开评论
- V2EX 公开帖子(robots 最宽松)
- 36氪 / 虎嗅 文章页(经搜索 API 取 URL 后 fetch,robots 允许)
- 酷安 应用详情与公开评论
- 其他公开站点(含长尾小站):按诚实 UA 查 robots 并遵守 + 限速

## 灰色(谨慎 / 间接)
- 掘金等:优先经搜索 API 或 RSS 间接获取
- linux.do:robots 通用允许但 disallow AI 爬虫并标 `ai-train=no` → 优先用搜索 API 摘要

## 红色(不自抓;仅经搜索 API 公开摘要间接引用)
- 知乎、小红书、微博、脉脉、即刻,以及一切登录墙站点
- 理由:robots 明确封锁 + 2025 年《反不正当竞争法》(2025.10.15 生效)禁止绕过技术措施获取数据
  + PIPL 个人信息合规义务 + 平台 ToS 禁止自动化访问
- 实现:见 `rivalradar/collect/policy.py` 的 `RED_DENYLIST`,自抓一律拒绝;这些来源只通过
  Tavily/Exa 返回的公开摘要间接呈现,并在报告中标注出处

## 不使用的手段
- 不使用任何反爬绕过工具(如 MediaCrawler 等),不使用他人账号 cookie 模拟登录
```

- [ ] **Step 2: 校验红名单与代码一致**

Run: `.venv/bin/python -c "from rivalradar.collect.policy import RED_DENYLIST; print(sorted(RED_DENYLIST))"`
Expected: 打印的域名与 DATA_SOURCES.md 红色段一致(zhihu/xiaohongshu/weibo/maimai/okjike 等)。

- [ ] **Step 3: 提交**

```bash
git add DATA_SOURCES.md
git commit -m "docs: DATA_SOURCES.md compliance disclosure (green/gray/red tiers)"
```

---

### Task 11:🚧 真实采集集成冒烟(待 Tavily key,GATE-lite)

**Files:**
- Create: `spikes/spike_c_collect_integration.py`

> 用真实 Tavily 对 1 竞品 2 维度跑通 `collect()`,确认能产出带 source_url/fetched_at 的真实 Evidence。需 `TAVILY_API_KEY`(已配)。这条把 C-1 端到端在真实数据上验一次(spec §13 E2E 精神)。

- [ ] **Step 1: 写 `spikes/spike_c_collect_integration.py`**

```python
"""C-1 集成冒烟:真实 Tavily → collect() → Evidence。需 TAVILY_API_KEY。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.collect.pipeline import collect
from rivalradar.search.tavily_provider import TavilyProvider


def main() -> None:
    provider = TavilyProvider(api_key=config.tavily_api_key())
    evs = collect(["Notion"], ["pricing", "core_workflows"], provider=provider,
                  languages=("en",), max_results=3, max_workers=3)
    print(f"collected {len(evs)} evidence")
    for e in evs[:6]:
        body = (e.content or "")[:80].replace("\n", " ")
        print(f"  [{e.dimension}] {e.source_url}  | {body}")
    assert evs, "no evidence collected"
    assert all(e.source_url and e.fetched_at for e in evs), "missing source/fetched_at"
    print("SPIKE C OK: real evidence with source + timestamp")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑集成冒烟(需 key)**

Run: `.venv/bin/python spikes/spike_c_collect_integration.py`
Expected: 打印 collected N evidence(N≥1),每条带 source_url;末行 `SPIKE C OK`。
若无 key 或被限流:记录现象,这是 GATE-lite,可交用户带 key 跑。

- [ ] **Step 3: 提交**

```bash
git add spikes/spike_c_collect_integration.py
git commit -m "spike: real Tavily->collect()->Evidence integration smoke"
```

---

## 环境准备

```bash
.venv/bin/pip install "exa-py>=1.0" "httpx>=0.27"   # Task 1 也会做
```

## Self-Review(写完计划后自查)

**1. Spec / 决策覆盖**
- Tavily 主 + Exa 备 + 适配层 → Task 1-4 ✅(SPIKE 决策)
- 黑名单 + robots + 诚实 UA + 限速 → Task 5-6 ✅(D6 / SPIKE)
- 中/英按维度查询 → Task 7 ✅(§7)
- 证据带 source_url + fetched_at(溯源)→ Task 8 ✅(§5/§6)
- 并行 + 限并发 → Task 9 ✅(D8)
- DATA_SOURCES.md → Task 10 ✅(D6 / 10% 合规)
- 真实 E2E → Task 11 ✅(§13)
- **范围外(C-2 再做)**:4 个 Agent(采集/分析/撰写/质检)、LLM 精炼查询、抽取层深度清洗、把 Evidence 落库(repository 已具备,C-2 接线)。

**2. 占位符扫描**:无 TBD。各 provider adapter 的真实 SDK 形状已核(Tavily 经 spike B 实测;Exa 经文档核实);httpx/robotparser/ThreadPoolExecutor 均标准用法。

**3. 类型一致性**:`SearchResult`(Task 1)被所有 provider/evidence/pipeline 使用,字段名一致;`SearchProvider` 协议的 `search(query, *, max_results)` 签名在 Tavily/Exa/Fallback/Mock 全一致;`to_evidence(result, *, competitor, dimension, language)` 在 Task 8 定义、Task 9 调用一致;`Query` 模型(Task 7)被 pipeline 消费一致;`Evidence` 复用既有 schema。

**4. 注意**:Exa adapter 的真实集成待 key(单测用 mock,逻辑已覆盖);safe_fetch 的真实网络路径在单测中用 mock http(真实抓取在 C-2/集成时自然覆盖)。
