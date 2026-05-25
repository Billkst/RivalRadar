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
