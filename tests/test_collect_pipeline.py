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
