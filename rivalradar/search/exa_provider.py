from __future__ import annotations

from rivalradar.search.base import SearchResult

_SNIPPET_CHARS = 300


class ExaProvider:
    """Exa 搜索后端(语义检索,作 Tavily 备用)。client 可注入(测试)。

    Exa 只回正文 text,无独立摘要字段 → 摘要取正文前 N 字。
    """

    name = "exa"

    def __init__(self, *, api_key: str | None = None, client=None):
        self._client = client
        self._api_key = api_key

    def _get_client(self):
        if self._client is None:
            from exa_py import Exa

            self._client = Exa(self._api_key)
        return self._client

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        resp = self._get_client().search_and_contents(
            query, text=True, num_results=max_results
        )
        out: list[SearchResult] = []
        for r in resp.results:
            text = getattr(r, "text", "") or ""
            out.append(SearchResult(
                url=getattr(r, "url", "") or "",
                title=getattr(r, "title", "") or "",
                content=text[:_SNIPPET_CHARS],
                raw_content=text or None,
                published_date=getattr(r, "published_date", None),
                score=getattr(r, "score", None),
                provider=self.name,
            ))
        return out
