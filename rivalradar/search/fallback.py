from __future__ import annotations

import logging

from rivalradar.search.base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)


class AllProvidersFailedError(RuntimeError):
    """所有搜索 provider 都失败 —— 显式抛出,不静默返回空。"""


class FallbackSearch:
    """按顺序尝试 provider,某个抛错(额度耗尽/网络)就切下一个(spec D8 / SPIKE 决策)。"""

    name = "fallback"

    def __init__(self, providers: list[SearchProvider]):
        if not providers:
            raise ValueError("FallbackSearch 至少需要一个 provider")
        self._providers = providers

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        errors: list[str] = []
        for p in self._providers:
            try:
                return p.search(query, max_results=max_results)
            except Exception as e:  # noqa: BLE001 — 故意兜所有 provider 异常以切换
                # logger 写完整(server 内审计用);errors list 只存 type 不带 raw msg,
                # 防 OpenAI/Tavily APIStatusError str() 含 Authorization header → 被
                # AllProvidersFailedError 透传到 SSE 流泄露 key(Codex Critical #1)
                logger.warning("search provider %s failed: %s", getattr(p, "name", "?"), e)
                errors.append(f"{getattr(p, 'name', '?')}: {type(e).__name__}")
        raise AllProvidersFailedError("; ".join(errors))
