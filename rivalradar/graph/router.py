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
    issues: list[dict], competitors: list[str]
) -> list[tuple[str, str]]:
    """从 QC issues 提「只补缺口」清单(spec §8 + 必办项②)。

    只取 problem_type ∈ {missing_evidence, low_coverage} 的 (competitor, dimension);
    competitor='*' fan 到全竞品;去重保序。hallucination/schema_incomplete 走重分析,不补采。
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for it in issues:
        if it.get("problem_type") not in ("missing_evidence", "low_coverage"):
            continue
        comps = competitors if it.get("competitor") == "*" else [it["competitor"]]
        for c in comps:
            key = (c, it["dimension"])
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out
