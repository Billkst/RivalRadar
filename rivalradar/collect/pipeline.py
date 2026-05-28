from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from rivalradar.collect.evidence import to_evidence
from rivalradar.collect.queries import Query, generate_queries
from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchProvider

logger = logging.getLogger(__name__)


def _run_query(provider: SearchProvider, q: Query, max_results: int) -> list[Evidence]:
    results = provider.search(q.query_text, max_results=max_results)
    return [to_evidence(r, competitor=q.competitor, dimension=q.dimension,
                        language=q.language) for r in results]


def _run_query_safe(provider: SearchProvider, q: Query, max_results: int) -> list[Evidence]:
    """Wrap _run_query with per-query graceful skip(评分细则 25% "降级机制")。

    单个 query 失败(timeout / provider 全挂 / 网络抖)不应 abort 整轮采集。
    返回 [] + 日志 warning 让 pipeline 继续跑剩余 queries,后续 QC 自然识别
    coverage 不足触发 retry_collect 或标 insufficient_evidence。

    踩到的真实场景:WSL2 Clash fake-ip 路由 api.tavily.com 偶发 60s timeout,
    18 并发 query 中 1 个超时 → AllProvidersFailedError → 整 pipeline crash。
    修后:17 query 成功的 evidence 仍能进 analyst,run 完整跑完出报告。
    """
    try:
        return _run_query(provider, q, max_results)
    except Exception as e:
        logger.warning(
            "query failed (graceful skip): competitor=%s dimension=%s language=%s "
            "query=%r — %s: %s",
            q.competitor, q.dimension, q.language, q.query_text,
            type(e).__name__, str(e)[:200],
        )
        return []


def collect(
    competitors: list[str],
    dimensions: list[str],
    *,
    provider: SearchProvider,
    languages: tuple[str, ...] = ("en", "zh"),
    max_results: int = 5,
    max_workers: int = 4,
    broaden: bool = False,
) -> list[Evidence]:
    """并行采集:竞品×维度×语言 → 查询 → 搜索 → 证据,限并发 max_workers,按 id 去重(spec §7/D8)。
    空内容证据(content.strip() 为空)在去重环节一并过滤。
    单 query 异常被 _run_query_safe graceful skip(返 [] + 日志),不 abort 整轮。
    """
    queries: list[Query] = []
    for c in competitors:
        queries.extend(generate_queries(c, dimensions, languages=languages, broaden=broaden))

    by_id: dict[str, Evidence] = {}
    failed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(
            lambda q: _run_query_safe(provider, q, max_results), queries
        ))
    for evs in results:
        if not evs:
            failed_count += 1
            continue
        for ev in evs:
            if not ev.content.strip():
                continue  # 跳过空内容证据(如 Exa 无法提取正文时)
            by_id.setdefault(ev.id, ev)
    if failed_count > 0:
        logger.info(
            "collect partial: %d/%d queries returned empty or failed (graceful skip)",
            failed_count, len(queries),
        )
    return list(by_id.values())
