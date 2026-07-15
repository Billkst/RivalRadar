"""启动时的代理环境处理(main._ensure_localhost_bypasses_proxy)。

这批测试钉死一个真实事故:后端曾在启动时**清空所有代理 env**(为了让豆包端点直连,
躲开 Clash fake-ip 的海外绕路)。BYOK 上线后,LLM 端点变成任意厂商 —— 而本机
api.deepseek.com **直连不通、只有走代理才通**。清了代理 → 连不上 → SDK 默认重试 2 次
→ 一次连通性测试卡 46s 才报 timeout,看起来像「厂商挂了」。

应用不该假装自己懂网络拓扑。唯一该由应用兜底的是 localhost 自调用(走代理必 502)。
"""
from __future__ import annotations

import os

import pytest

from main import _ensure_localhost_bypasses_proxy

_PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
               "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """前置清空 + 后置恢复。只 delenv 不够:被测函数会直接写 os.environ["NO_PROXY"],
    而测试前该变量若本就不存在,monkeypatch 没有记录可回滚 —— 写入的值会泄漏进
    同一 pytest 进程后续所有测试(评审抓出)。快照-恢复兜住。"""
    snapshot = {k: os.environ.get(k) for k in _PROXY_KEYS}
    for k in _PROXY_KEYS:
        monkeypatch.delenv(k, raising=False)
    yield
    for k, v in snapshot.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _no_proxy_hosts() -> set[str]:
    return {h.strip() for h in os.environ["NO_PROXY"].split(",") if h.strip()}


@pytest.mark.parametrize("key", ["http_proxy", "https_proxy", "HTTP_PROXY",
                                 "HTTPS_PROXY", "ALL_PROXY", "all_proxy"])
def test_proxy_vars_are_preserved_not_stripped(monkeypatch, key):
    """核心回归:代理变量**必须原样保留**。曾经在这里 pop 掉它们,导致 BYOK 下
    「直连不通、只走代理通」的厂商(api.deepseek.com,乃至今天的豆包自己)彻底连不上。"""
    monkeypatch.setenv(key, "http://127.0.0.1:7897")

    _ensure_localhost_bypasses_proxy()

    assert os.environ[key] == "http://127.0.0.1:7897"


def test_localhost_always_bypasses_proxy():
    """自调用走代理必 502,且与部署环境无关 —— 这是唯一该由应用兜底的一条。"""
    _ensure_localhost_bypasses_proxy()
    assert {"localhost", "127.0.0.1"} <= _no_proxy_hosts()


def test_merges_into_existing_no_proxy_instead_of_setdefault(monkeypatch):
    """曾用 setdefault:环境已设 NO_PROXY 时它是**空操作**,localhost 就漏掉了(自调用走代理
    → 502)。必须 merge。既有条目也不能被覆盖掉 —— 那是运维的决定,应用无权丢弃。"""
    monkeypatch.setenv("NO_PROXY", "internal.corp,10.0.0.5")

    _ensure_localhost_bypasses_proxy()

    hosts = _no_proxy_hosts()
    assert {"internal.corp", "10.0.0.5"} <= hosts   # 运维设的照单保留
    assert {"localhost", "127.0.0.1"} <= hosts      # 自调用兜底照样加上


def test_no_proxy_lowercase_and_uppercase_kept_in_sync():
    """httpx / requests 读哪个大小写取决于库和版本 —— 两个都写,免得只在某个库里生效。"""
    _ensure_localhost_bypasses_proxy()
    assert os.environ["NO_PROXY"] == os.environ["no_proxy"]


def test_is_idempotent():
    """reload / 多次调用不该把 localhost 重复堆进去(NO_PROXY 会越滚越长)。"""
    _ensure_localhost_bypasses_proxy()
    first = os.environ["NO_PROXY"]
    _ensure_localhost_bypasses_proxy()
    assert os.environ["NO_PROXY"] == first


def test_no_hardcoded_provider_hosts_in_bypass_list():
    """**不得**再把厂商域名写进直连名单。那是把运维决策焊进应用代码 —— 网络环境一变就烂,
    而且烂得无声(注释还言之成理,没人会去质疑)。ark / tavily / deepseek 一个都不许出现。"""
    _ensure_localhost_bypasses_proxy()
    hosts = _no_proxy_hosts()
    assert hosts == {"localhost", "127.0.0.1"}
    for vendor in ("ark.cn-beijing.volces.com", "api.tavily.com", "api.deepseek.com"):
        assert vendor not in hosts
