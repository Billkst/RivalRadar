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


def test_skips_empty_content_results():
    class _EmptyProvider:
        name = "empty"
        def search(self, query, *, max_results=5):
            return [SearchResult(url="https://x/empty", title="t", content="",
                                 raw_content=None, provider="empty")]
    evs = collect(["Notion"], ["pricing"], provider=_EmptyProvider(),
                  languages=("en",), max_workers=2)
    assert evs == []  # 空内容证据被过滤


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


def test_collect_graceful_skip_on_single_query_failure(caplog):
    """单个 query 失败(provider 抛异常)→ graceful skip,继续返回成功 query 的 evidence。

    踩到的真实场景:WSL2 Clash fake-ip 偶发 Tavily timeout,18 query 中 1 个抛
    AllProvidersFailedError 把整个 pipeline crash。修法:_run_query_safe wrap
    try/except。本测验证修后行为。
    """
    class _PartialFailProvider:
        name = "partial"
        def __init__(self):
            self.call_count = 0
        def search(self, query, *, max_results=5):
            self.call_count += 1
            # 第 2 个 query 抛(模拟 Tavily timeout)
            if self.call_count == 2:
                raise TimeoutError("simulated upstream timeout")
            return [SearchResult(url=f"https://x/{query}", title=query,
                                 content="c", raw_content="body", provider="partial")]

    import logging
    p = _PartialFailProvider()
    with caplog.at_level(logging.WARNING):
        evs = collect(["A"], ["pricing", "integrations", "deployment"],
                      provider=p, languages=("en",), max_workers=2)

    # 3 维度 × 1 lang = 3 query,1 个失败 → 2 个成功 → 2 条 evidence
    assert len(evs) == 2
    assert {e.dimension for e in evs} != {"pricing", "integrations", "deployment"}  # 缺 1 维
    # warning 日志记录失败 query 上下文
    assert any("query failed" in r.message for r in caplog.records)
