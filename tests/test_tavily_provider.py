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
