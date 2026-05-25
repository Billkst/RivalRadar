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
