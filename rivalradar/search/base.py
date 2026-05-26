from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """统一的搜索结果(各 provider 适配到这一形状)。"""

    url: str
    title: str
    content: str  # 摘要/片段
    raw_content: Optional[str] = None  # 清洗后的页面正文(若 provider 提供)
    published_date: Optional[str] = None
    score: Optional[float] = None
    provider: str = ""


@runtime_checkable
class SearchProvider(Protocol):
    """搜索后端统一接口。Tavily/Exa/Firecrawl 各实现一个。"""

    name: str

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        ...
