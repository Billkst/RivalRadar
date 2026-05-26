from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchResult


def _evidence_id(competitor: str, dimension: str, url: str) -> str:
    raw = f"{competitor}|{dimension}|{url}".encode()
    return "ev_" + hashlib.sha1(raw).hexdigest()[:12]


def to_evidence(
    result: SearchResult,
    *,
    competitor: str,
    dimension: str,
    language: str,
) -> Evidence:
    """SearchResult → Evidence(带溯源)。content 优先正文,无则摘要。id 稳定可去重。"""
    content = result.raw_content or result.content
    return Evidence(
        id=_evidence_id(competitor, dimension, result.url),
        competitor=competitor,
        dimension=dimension,
        content=content,
        source_url=result.url,
        source_title=result.title,
        language=language,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
