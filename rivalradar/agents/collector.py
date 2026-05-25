from __future__ import annotations

import re

from rivalradar.collect.pipeline import collect
from rivalradar.schema.models import Evidence
from rivalradar.search.base import SearchProvider

# 已知可达评价平台(spec §7 / SPIKE 决策):优先级次于官方、高于杂源
_REVIEW_PLATFORMS = (
    "g2.com", "capterra.com", "apps.apple.com", "play.google.com",
    "coolapk.com", "v2ex.com", "36kr.com", "huxiu.com",
)

_IMG_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")        # markdown 图片
_LINK_MD = re.compile(r"\[([^\]]*)\]\([^)]*\)")       # markdown 链接 → 留文字
_MULTISPACE = re.compile(r"[ \t]+")
_MULTINL = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """去掉抓取正文里的 markdown 图片/链接壳与多余空白(C-1 终审遗留①)。"""
    if not text:
        return ""
    t = _IMG_MD.sub("", text)
    t = _LINK_MD.sub(r"\1", t)
    t = _MULTINL.sub("\n\n", t)
    # 逐行去除行首行尾水平空白,再压缩行内连续空格
    lines = [_MULTISPACE.sub(" ", line.strip()) for line in t.split("\n")]
    return "\n".join(lines).strip()


def source_priority(url: str, official_domains: list[str]) -> int:
    """来源优先级(数字越小越优先):官方=0 > 评价平台=1 > 其他=2(spec §7 / 终审遗留②)。"""
    host = url.lower()
    if any(d in host for d in official_domains):
        return 0
    if any(p in host for p in _REVIEW_PLATFORMS):
        return 1
    return 2


def collect_evidence(
    competitors: list[str],
    dimensions: list[str],
    *,
    provider: SearchProvider,
    official_domains: dict[str, list[str]] | None = None,
    languages: tuple[str, ...] = ("en", "zh"),
    max_results: int = 5,
    max_workers: int = 4,
) -> list[Evidence]:
    """采集 Agent:C-1 collect() → 清洗正文 → 按来源优先级排序。"""
    official_domains = official_domains or {}
    raw = collect(competitors, dimensions, provider=provider, languages=languages,
                  max_results=max_results, max_workers=max_workers)
    cleaned: list[Evidence] = []
    for ev in raw:
        body = clean_text(ev.content)
        if not body:
            continue
        cleaned.append(ev.model_copy(update={"content": body}))
    cleaned.sort(key=lambda e: source_priority(e.source_url, official_domains.get(e.competitor, [])))
    return cleaned
