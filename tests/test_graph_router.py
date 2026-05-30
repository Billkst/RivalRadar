from rivalradar.graph.router import decide_route, extract_collect_targets


# ---- decide_route 五分支(max_retries=2) ----
def test_route_pass_goes_finalize():
    assert decide_route("pass", 0, 2) == "finalize"


def test_route_retry_collect_when_budget_left():
    assert decide_route("retry_collect", 0, 2) == "collect"
    assert decide_route("retry_collect", 1, 2) == "collect"


def test_route_retry_analyze_when_budget_left():
    assert decide_route("retry_analyze", 0, 2) == "analyze"


def test_route_exhausted_goes_finalize():
    # retry_count 达上限 → finalize(由 finalize 赋 insufficient/降级)
    assert decide_route("retry_collect", 2, 2) == "finalize"
    assert decide_route("retry_analyze", 2, 2) == "finalize"


def test_route_insufficient_or_unknown_goes_finalize():
    assert decide_route("insufficient_evidence", 0, 2) == "finalize"
    assert decide_route("???", 0, 2) == "finalize"


# ---- extract_collect_targets(只补缺口) ----
def test_targets_only_missing_and_low_coverage():
    issues = [
        {"competitor": "Notion", "dimension": "pricing", "problem_type": "missing_evidence", "detail": ""},
        {"competitor": "Notion", "dimension": "core_workflows", "problem_type": "low_coverage", "detail": ""},
        {"competitor": "Notion", "dimension": "swot", "problem_type": "hallucination", "detail": ""},  # 不补采
    ]
    targets = extract_collect_targets(issues, ["Notion"])
    assert ("Notion", "pricing") in targets
    assert ("Notion", "core_workflows") in targets
    assert all(d != "swot" for _, d in targets)


def test_targets_star_competitor_fans_out_to_all():
    # competitor='*' fan 到全竞品(必办项②)
    issues = [{"competitor": "*", "dimension": "pricing", "problem_type": "low_coverage", "detail": ""}]
    targets = extract_collect_targets(issues, ["Notion", "Lark"])
    assert ("Notion", "pricing") in targets and ("Lark", "pricing") in targets


def test_targets_dedup_preserves_order():
    issues = [
        {"competitor": "Notion", "dimension": "pricing", "problem_type": "low_coverage", "detail": ""},
        {"competitor": "Notion", "dimension": "pricing", "problem_type": "missing_evidence", "detail": ""},
    ]
    assert extract_collect_targets(issues, ["Notion"]) == [("Notion", "pricing")]


# ---- gap-fill 维度作用域(真 run 钓出:SWOT 空引用 → missing_evidence("swot")
#      → 搜 "swot" → 本体外证据污染 → check_ontology 死循环 → degraded) ----
def test_targets_filtered_to_allowed_dimensions():
    # 综合维度 "swot"(非可搜索本体)的 missing_evidence 不得变成搜索目标
    issues = [
        {"competitor": "飞书", "dimension": "pricing", "problem_type": "missing_evidence", "detail": ""},
        {"competitor": "飞书", "dimension": "swot", "problem_type": "missing_evidence", "detail": ""},
        {"competitor": "飞书", "dimension": "review_sentiment", "problem_type": "low_coverage", "detail": ""},
    ]
    targets = extract_collect_targets(
        issues, ["飞书"], allowed_dimensions=("pricing", "core_workflows", "integrations"))
    assert ("飞书", "pricing") in targets
    assert all(d not in ("swot", "review_sentiment") for _, d in targets)
    assert targets == [("飞书", "pricing")]


def test_targets_no_filter_when_allowed_dimensions_none():
    # 向后兼容:不传 allowed_dimensions → 不过滤(老行为)
    issues = [{"competitor": "飞书", "dimension": "swot", "problem_type": "missing_evidence", "detail": ""}]
    assert extract_collect_targets(issues, ["飞书"]) == [("飞书", "swot")]
