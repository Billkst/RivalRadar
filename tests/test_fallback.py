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


def test_raises_value_error_when_no_providers():
    """FallbackSearch 构造无 provider → ValueError(快速失败,防配置错误静默)。"""
    with pytest.raises(ValueError):
        FallbackSearch([])
