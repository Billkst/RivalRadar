from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlparse

from rivalradar.collect.policy import USER_AGENT, is_self_fetch_allowed


class RateLimiter:
    """每域最小间隔限速(spec D8)。clock/sleep 可注入以便测试。"""

    def __init__(self, *, min_interval: float = 1.0,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self._min = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}

    def wait(self, domain: str) -> None:
        now = self._clock()
        last = self._last.get(domain)
        if last is not None:
            gap = self._min - (now - last)
            if gap > 0:
                self._sleep(gap)
                now = now + gap
        self._last[domain] = now


def safe_fetch(
    url: str,
    *,
    http=None,
    allowed: Callable[[str], bool] = is_self_fetch_allowed,
    limiter: RateLimiter | None = None,
    timeout: float = 10.0,
) -> str | None:
    """合规自抓:被策略拒 → None(不抛);否则限速后 httpx GET 返回正文文本,失败 → None。"""
    if not allowed(url):
        return None
    limiter = limiter or RateLimiter()
    limiter.wait(urlparse(url).netloc.lower())
    if http is None:
        import httpx

        http = httpx.Client(follow_redirects=True)
    try:
        resp = http.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None
