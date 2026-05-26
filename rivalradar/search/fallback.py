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
                # 双 sanitize:errors list 走 SSE error event 给客户端(已 sanitize);
                # logger.warning 走 server log,如果 log 被 ops 之外的人读到也防泄露
                # (Tavily/Exa APIStatusError str() 可能含 Authorization header)。
                # debug 用 logger.exception(stack trace 含完整 e 的 attrs)。
                provider_name = getattr(p, "name", "?")
                logger.warning("search provider %s failed: %s", provider_name, type(e).__name__)
                logger.exception("provider %s exception detail", provider_name)
                errors.append(f"{provider_name}: {type(e).__name__}")
        raise AllProvidersFailedError("; ".join(errors))
