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
