from rivalradar.collect.policy import (
    RED_DENYLIST, USER_AGENT, is_denylisted, is_self_fetch_allowed,
)


def test_denylist_blocks_red_domains():
    assert is_denylisted("https://www.zhihu.com/question/123")
    assert is_denylisted("https://xiaohongshu.com/x")
    assert not is_denylisted("https://notion.so/pricing")
    assert "zhihu.com" in RED_DENYLIST


class _FakeRobots:
    def __init__(self, allow):
        self._allow = allow

    def can_fetch(self, ua, url):
        return self._allow


def test_self_fetch_blocked_for_denylisted_even_if_robots_ok():
    allowed = is_self_fetch_allowed(
        "https://zhihu.com/x", robots_for=lambda d: _FakeRobots(True))
    assert allowed is False


def test_self_fetch_respects_robots_for_normal_site():
    assert is_self_fetch_allowed(
        "https://example.com/a", robots_for=lambda d: _FakeRobots(True)) is True
    assert is_self_fetch_allowed(
        "https://example.com/b", robots_for=lambda d: _FakeRobots(False)) is False


def test_user_agent_is_honest_identifier():
    assert "RivalRadar" in USER_AGENT


def test_self_fetch_allowed_when_robots_fetch_fails():
    """robots.txt 取不到(网络/SSL 异常)→ _default_robots_for 返 None → 保守视为可读。"""
    def _failing_robots(domain):
        return None  # 模拟 _default_robots_for 的异常分支返回 None
    assert is_self_fetch_allowed(
        "https://example.com/c", robots_for=_failing_robots) is True
