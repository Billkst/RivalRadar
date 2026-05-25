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


def test_generate_queries_broaden_appends_suffix():
    qs = generate_queries("Notion", ["pricing"], languages=("en",), broaden=True)
    assert qs[0].query_text == "Notion pricing plans cost review comparison alternative"


def test_generate_queries_default_has_no_suffix():
    qs = generate_queries("Notion", ["pricing"], languages=("en",))
    assert qs[0].query_text == "Notion pricing plans cost"


def test_generate_queries_broaden_zh_suffix():
    qs = generate_queries("飞书", ["pricing"], languages=("zh",), broaden=True)
    assert qs[0].query_text.endswith("评测 对比 替代方案")
