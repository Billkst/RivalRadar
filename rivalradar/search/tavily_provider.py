from __future__ import annotations

from rivalradar.search.base import SearchResult


class TavilyProvider:
    """Tavily 搜索后端。client 可注入(测试);默认懒构造 TavilyClient。"""

    name = "tavily"

    def __init__(self, *, api_key: str | None = None, client=None):
        self._client = client
        self._api_key = api_key

    def _get_client(self):
        if self._client is None:
            from tavily import TavilyClient

            self._client = TavilyClient(api_key=self._api_key)
        return self._client

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        resp = self._get_client().search(
            query=query, max_results=max_results, include_raw_content=True
        )
        out: list[SearchResult] = []
        for r in resp.get("results", []):
            out.append(SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                content=r.get("content", ""),
                raw_content=r.get("raw_content"),
                published_date=r.get("published_date"),
                score=r.get("score"),
                provider=self.name,
            ))
        return out
