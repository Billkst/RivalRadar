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


def test_source_priority_matches_host_not_substring():
    # 子域算官方;但 host 不等于官方域时,即便 path 含官方域名也不误判
    assert source_priority("https://www.notion.so/pricing", ["notion.so"]) == 0
    assert source_priority("https://evil.com/notion.so-phishing", ["notion.so"]) == 2


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
