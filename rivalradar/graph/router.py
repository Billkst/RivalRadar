from __future__ import annotations


def decide_route(verdict: str, retry_count: int, max_retries: int) -> str:
    """纯逻辑路由(spec §4/§13 ★必测),返回下一节点名。

    pass → finalize;重试耗尽(retry_count >= max_retries)→ finalize
    (由 finalize 赋 insufficient_evidence / 降级);
    retry_collect → collect;retry_analyze → analyze;
    其他(含 insufficient_evidence / 未知)→ finalize。
    """
    if verdict == "pass":
        return "finalize"
    if retry_count >= max_retries:
        return "finalize"
    if verdict == "retry_collect":
        return "collect"
    if verdict == "retry_analyze":
        return "analyze"
    return "finalize"


def extract_collect_targets(
    issues: list[dict], competitors: list[str],
    allowed_dimensions: tuple[str, ...] | None = None,
) -> list[tuple[str, str]]:
    """从 QC issues 提「只补缺口」清单(spec §8 + 必办项②)。

    只取 problem_type ∈ {missing_evidence, low_coverage} 的 (competitor, dimension);
    competitor='*' fan 到全竞品;去重保序。hallucination/schema_incomplete 走重分析,不补采。

    allowed_dimensions:gap-fill 只对「可搜索本体维度」补采(真 run 钓出 dimension-scoping
    bug 续集)。综合维度如 "swot" 不是可搜索本体——分析员的 SWOT 空引用会产
    missing_evidence("swot") → 若拿去搜 "swot" 则采来本体外证据 → check_ontology 死循环
    → degraded。传入请求维度即把这类越界目标挡在采集外(None = 不过滤,向后兼容老调用)。
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for it in issues:
        if it.get("problem_type") not in ("missing_evidence", "low_coverage"):
            continue
        if allowed_dimensions is not None and it["dimension"] not in allowed_dimensions:
            continue
        comps = competitors if it.get("competitor") == "*" else [it["competitor"]]
        for c in comps:
            key = (c, it["dimension"])
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out
