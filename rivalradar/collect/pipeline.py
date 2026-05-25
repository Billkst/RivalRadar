from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from rivalradar.collect.evidence import to_evidence
from rivalradar.collect.queries import Query, generate_queries
from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchProvider


def _run_query(provider: SearchProvider, q: Query, max_results: int) -> list[Evidence]:
    results = provider.search(q.query_text, max_results=max_results)
    return [to_evidence(r, competitor=q.competitor, dimension=q.dimension,
                        language=q.language) for r in results]


def collect(
    competitors: list[str],
    dimensions: list[str],
    *,
    provider: SearchProvider,
    languages: tuple[str, ...] = ("en", "zh"),
    max_results: int = 5,
    max_workers: int = 4,
) -> list[Evidence]:
    """并行采集:竞品×维度×语言 → 查询 → 搜索 → 证据,限并发 max_workers,按 id 去重(spec §7/D8)。
    空内容证据(content.strip() 为空)在去重环节一并过滤。
    """
    queries: list[Query] = []
    for c in competitors:
        queries.extend(generate_queries(c, dimensions, languages=languages))

    by_id: dict[str, Evidence] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for evs in pool.map(lambda q: _run_query(provider, q, max_results), queries):
            for ev in evs:
                if not ev.content.strip():
                    continue  # 跳过空内容证据(如 Exa 无法提取正文时)
                by_id.setdefault(ev.id, ev)
    return list(by_id.values())
