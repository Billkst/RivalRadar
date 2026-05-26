from rivalradar.collect.fetch import RateLimiter, safe_fetch


def test_rate_limiter_waits_per_domain():
    now = [0.0]
    slept = []
    rl = RateLimiter(min_interval=2.0, clock=lambda: now[0], sleep=slept.append)
    rl.wait("example.com")          # 首次不等
    assert slept == []
    rl.wait("example.com")          # 立刻再来 → 等 2s
    assert slept == [2.0]
    rl.wait("other.com")            # 不同域 → 不等
    assert slept == [2.0]


class _FakeResp:
    def __init__(self, text): self.text = text
    def raise_for_status(self): pass


class _FakeHTTP:
    def __init__(self, text): self._text = text; self.got = None
    def get(self, url, headers=None, timeout=None):
        self.got = url
        return _FakeResp(self._text)


def test_safe_fetch_blocked_returns_none():
    http = _FakeHTTP("body")
    out = safe_fetch("https://zhihu.com/x", http=http,
                     allowed=lambda u: False, limiter=_NoWait())
    assert out is None and http.got is None  # 被拒,根本没发请求


def test_safe_fetch_allowed_returns_text():
    http = _FakeHTTP("<p>hello</p>")
    out = safe_fetch("https://example.com/a", http=http,
                     allowed=lambda u: True, limiter=_NoWait())
    assert out == "<p>hello</p>" and http.got == "https://example.com/a"


class _NoWait:
    def wait(self, domain): pass


class _ErrorResp:
    def raise_for_status(self):
        raise RuntimeError("HTTP 403")
    text = "forbidden"


class _ErrorHTTP:
    def __init__(self): self.got = None
    def get(self, url, headers=None, timeout=None):
        self.got = url
        return _ErrorResp()


def test_safe_fetch_http_error_returns_none():
    """raise_for_status 抛错 → safe_fetch 返 None 而非上抛(合规自抓 silent fallback)。"""
    http = _ErrorHTTP()
    out = safe_fetch("https://example.com/b", http=http,
                     allowed=lambda u: True, limiter=_NoWait())
    assert out is None
