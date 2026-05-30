"""竞品自动发现(Epic 1.1):discover_competitors 后处理 + POST /discover-competitors。

外部 LLM 一律 monkeypatch structured_call / discover_competitors,不真打。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rivalradar.agents import discover as discover_mod
from rivalradar.agents.discover import (
    DiscoveredCompetitor, DiscoverySet, discover_competitors,
)
from rivalradar.api.app import create_app
from rivalradar.llm.structured import StructuredCallError


def _set(*names: str) -> DiscoverySet:
    return DiscoverySet(competitors=[DiscoveredCompetitor(name=n, rationale="r") for n in names])


# ── schema ──────────────────────────────────────────────────────────────────
def test_schema_caps_at_8():
    """源头硬上限:>8 条建议 schema 直接拒绝(cost guard 第一道闸)。"""
    with pytest.raises(ValidationError):
        DiscoverySet(competitors=[DiscoveredCompetitor(name=f"c{i}", rationale="r") for i in range(9)])


def test_schema_roundtrip():
    s = _set("钉钉", "企业微信")
    assert DiscoverySet.model_validate(s.model_dump()).competitors[0].name == "钉钉"


# ── 后处理:去种子 + 去重 ──────────────────────────────────────────────────
def test_excludes_seed_and_dedups(monkeypatch):
    """LLM 把种子自身 + 同名(含空格写法)塞回来 → 后处理去种子 + 去重。"""
    monkeypatch.setattr(
        discover_mod, "structured_call",
        lambda *a, **k: _set("飞书", "钉钉", "钉钉 ", "企业微信"),
    )
    out = discover_competitors("飞书", None, client="stub", model="m")
    assert [c.name for c in out.competitors] == ["钉钉", "企业微信"]


def test_drops_blank_names(monkeypatch):
    monkeypatch.setattr(discover_mod, "structured_call", lambda *a, **k: _set("  ", "Slack"))
    out = discover_competitors("飞书", None, client="stub", model="m")
    assert [c.name for c in out.competitors] == ["Slack"]


def test_empty_suggestions_returns_empty(monkeypatch):
    """未知种子 / LLM 给空 → 返空集(前端引导用户手动输入),不报错。"""
    monkeypatch.setattr(discover_mod, "structured_call", lambda *a, **k: _set())
    out = discover_competitors("某不存在产品xyz", None, client="stub", model="m")
    assert out.competitors == []


def test_industry_hint_passed_into_prompt(monkeypatch):
    """industry_hint 非空时进入 prompt(帮 LLM 缩范围)。"""
    captured = {}

    def fake(model_cls, messages, **k):
        captured["content"] = messages[0]["content"]
        return _set("钉钉")

    monkeypatch.setattr(discover_mod, "structured_call", fake)
    discover_competitors("飞书", "企业协作办公", client="stub", model="m")
    assert "企业协作办公" in captured["content"]


# ── 端点 ────────────────────────────────────────────────────────────────────
@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(db_path=str(tmp_path / "d.db"), doubao_client="stub-client"))


def test_endpoint_happy(client, monkeypatch):
    monkeypatch.setattr("rivalradar.api.runs.discover_competitors",
                        lambda *a, **k: _set("钉钉", "企业微信"))
    r = client.post("/discover-competitors", json={"seed": "飞书"})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()["competitors"]]
    assert names == ["钉钉", "企业微信"]


def test_endpoint_503_on_llm_failure(client, monkeypatch):
    """LLM 不通 → 503(非静默空列表),前端据此提示手动输入。"""
    def boom(*a, **k):
        raise StructuredCallError("llm down")

    monkeypatch.setattr("rivalradar.api.runs.discover_competitors", boom)
    r = client.post("/discover-competitors", json={"seed": "飞书"})
    assert r.status_code == 503


def test_endpoint_rejects_empty_seed(client):
    """空 seed → 422(StringConstraints min_length=1),不打 LLM。"""
    r = client.post("/discover-competitors", json={"seed": ""})
    assert r.status_code == 422
