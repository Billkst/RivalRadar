from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urlparse

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


def _host_matches(url: str, domains) -> bool:
    """按 host 精确或子域匹配(与 policy.is_denylisted 同口径),避免 URL 子串误判。"""
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def source_priority(url: str, official_domains: list[str]) -> int:
    """来源优先级(数字越小越优先):官方=0 > 评价平台=1 > 其他=2(spec §7 / 终审遗留②)。"""
    if _host_matches(url, official_domains):
        return 0
    if _host_matches(url, _REVIEW_PLATFORMS):
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
    broaden: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> list[Evidence]:
    """采集 Agent:C-1 collect() → 清洗正文 → 按来源优先级排序。
    on_progress 透传给 collect(每 query 完成报一次);None = 不报(向后兼容/单测)。"""
    official_domains = official_domains or {}
    raw = collect(competitors, dimensions, provider=provider, languages=languages,
                  max_results=max_results, max_workers=max_workers, broaden=broaden,
                  on_progress=on_progress)
    cleaned: list[Evidence] = []
    for ev in raw:
        body = clean_text(ev.content)
        if not body:
            continue
        cleaned.append(ev.model_copy(update={"content": body}))
    cleaned.sort(key=lambda e: source_priority(e.source_url, official_domains.get(e.competitor, [])))
    return cleaned
