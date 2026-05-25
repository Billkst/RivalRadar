from __future__ import annotations

import urllib.robotparser
from collections.abc import Callable
from urllib.parse import urlparse

# 诚实 UA(spec D6:不冒充,标明身份)
USER_AGENT = "RivalRadarBot/0.1 (+competitive research; respects robots.txt)"

# 红名单:只经搜索 API 公开摘要间接用,绝不自抓原站
# 理由见 spikes/SPIKE_RESULTS.md(robots 全站禁 + 2025 反不正当竞争法 + PIPL + ToS)
RED_DENYLIST: frozenset[str] = frozenset({
    "zhihu.com", "xiaohongshu.com", "xhslink.com",
    "weibo.com", "maimai.cn", "okjike.com",
})


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def is_denylisted(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) or host.removeprefix("www.") == d
               for d in RED_DENYLIST)


def _default_robots_for(domain: str):
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"https://{domain}/robots.txt")
    try:
        rp.read()
    except Exception:
        # 取不到 robots.txt → 保守起见视为可读(标准爬虫惯例),但仍受限速约束
        return None
    return rp


def is_self_fetch_allowed(
    url: str,
    *,
    robots_for: Callable[[str], object] | None = None,
    user_agent: str = USER_AGENT,
) -> bool:
    """能否自抓该 URL:红名单一律 False;否则按诚实 UA 查 robots。robots_for 可注入(测试)。"""
    if is_denylisted(url):
        return False
    fetch_robots = robots_for or _default_robots_for
    rp = fetch_robots(_domain(url))
    if rp is None:
        return True
    return rp.can_fetch(user_agent, url)
