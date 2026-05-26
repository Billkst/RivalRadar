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
