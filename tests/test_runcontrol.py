"""协作式取消 + 墙钟预算(post-real-run-7)。锁住不变量:取消后不再发起 LLM 调用、
RunAborted 穿透所有 except Exception 降级、build_comparison 取消后整轮停而非逐维降级。"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from rivalradar.llm.runcontrol import RunAborted, RunControl, wrap_client
from rivalradar.llm.structured import structured_call, StructuredCallError
from rivalradar.agents.analyst import (
    build_comparison, _safe_extract, ComparisonExtraction,
)
from rivalradar.schema.models import CompetitorProfile, PricingModel, SWOT, Evidence


# ── RunControl.check ─────────────────────────────────────────────────────────
def test_check_noop_when_not_cancelled_no_deadline():
    RunControl().check()  # 不抛即通过


def test_check_raises_cancelled():
    c = RunControl()
    c.cancel()
    with pytest.raises(RunAborted) as ei:
        c.check()
    assert ei.value.reason == "cancelled"


def test_check_raises_timeout_when_past_deadline():
    c = RunControl(deadline=time.monotonic() - 1)  # 已过期
    with pytest.raises(RunAborted) as ei:
        c.check()
    assert ei.value.reason == "timeout"


def test_check_passes_before_deadline():
    RunControl(deadline=time.monotonic() + 100).check()


def test_run_aborted_is_baseexception_not_caught_by_except_exception():
    # 关键不变量:RunAborted 必须穿透 `except Exception`(否则取消被降级咽掉)
    assert issubclass(RunAborted, BaseException)
    assert not issubclass(RunAborted, Exception)
    caught = False
    try:
        try:
            raise RunAborted("cancelled")
        except Exception:  # noqa: BLE001 — 故意:验证它【穿透】
            caught = True
    except RunAborted:
        pass
    assert caught is False  # except Exception 没接住


# ── wrap_client ──────────────────────────────────────────────────────────────
class _CountingClient:
    """记录 chat.completions.create 调用次数的假 client;返回一个合法 tool_call。"""
    def __init__(self, arguments: str):
        self.calls = 0
        self._args = arguments
        outer = self

        class _Completions:
            @staticmethod
            def create(**kwargs):
                outer.calls += 1
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                    tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=outer._args))]))],
                    usage=SimpleNamespace(total_tokens=10))
        self.chat = SimpleNamespace(completions=_Completions())


def test_wrap_client_none_returns_original():
    c = _CountingClient("{}")
    assert wrap_client(c, None) is c


def test_wrapped_client_passthrough_when_not_cancelled():
    inner = _CountingClient(json.dumps({"items": []}))
    wrapped = wrap_client(inner, RunControl())
    wrapped.chat.completions.create(model="m", messages=[], tools=[], tool_choice={})
    assert inner.calls == 1  # 正常透传


def test_wrapped_client_raises_before_create_when_cancelled():
    inner = _CountingClient("{}")
    ctl = RunControl()
    ctl.cancel()
    wrapped = wrap_client(inner, ctl)
    with pytest.raises(RunAborted):
        wrapped.chat.completions.create(model="m", messages=[])
    assert inner.calls == 0  # 取消后【根本没发起】HTTP


# ── structured_call:取消 → 不重试、直接抛 RunAborted(非 StructuredCallError)────
def test_structured_call_aborts_immediately_when_cancelled_no_retries():
    inner = _CountingClient(json.dumps({"items": []}))
    ctl = RunControl()
    ctl.cancel()
    wrapped = wrap_client(inner, ctl)
    from rivalradar.agents.analyst import FeatureExtraction
    with pytest.raises(RunAborted):
        structured_call(FeatureExtraction, [{"role": "user", "content": "x"}],
                        client=wrapped, model="m", max_retries=2)
    assert inner.calls == 0  # 5×90s 重试环被取消斩断:0 次调用


# ── _safe_extract:RunAborted 穿透降级(不当空默认咽下)──────────────────────
def test_safe_extract_propagates_run_aborted_not_degrade():
    sink: list[str] = []

    def boom():
        raise RunAborted("cancelled")

    with pytest.raises(RunAborted):
        _safe_extract("pricing", "钉钉", boom, PricingModel(model_type="未知"), sink=sink)
    assert sink == []  # 没被记成降级


# ── build_comparison:取消 → 整轮停、不逐维降级、0 LLM 调用 ───────────────────
def _ev(eid, comp, dim):
    return Evidence(id=eid, competitor=comp, dimension=dim, content="c",
                    source_url="u", source_title="t", language="zh", fetched_at="2026-05-25T00:00:00Z")


def test_build_comparison_aborts_whole_round_on_cancel():
    inner = _CountingClient(json.dumps({"rows": []}))
    ctl = RunControl()
    ctl.cancel()
    wrapped = wrap_client(inner, ctl)
    evidence = [_ev("e1", "Notion", "pricing"), _ev("e2", "Notion", "core_workflows")]
    sink: list[str] = []
    with pytest.raises(RunAborted):
        build_comparison(
            [CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
            evidence, dimensions=("pricing", "core_workflows"), degraded_sink=sink,
            client=wrapped, model="m")
    assert inner.calls == 0      # 取消后没发起任何对比 LLM 调用
    assert sink == []            # 不是"逐维降级",是整轮停
