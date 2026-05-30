import hashlib

import pytest

from rivalradar.agents import qc
from rivalradar.graph.build import run_research
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, CompetitorProfile, PricingModel,
    SWOT, ComparisonRow, ComparisonCell, EvidenceRef, ReportInsight,
)
from rivalradar.search.base import SearchResult
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


class _ImprovingProvider:
    """首遍只对 pricing 返回源(缺其余 5 维);broaden 时对任意维度返回新 url → 补足缺口。"""
    name = "improving"

    def search(self, query, *, max_results=5):
        is_broaden = ("comparison" in query) or ("替代方案" in query)
        is_pricing = ("pricing" in query) or ("价格" in query)
        if not is_broaden and not is_pricing:
            return []
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="snippet",
                             raw_content="evidence body for " + query)]


class _StuckProvider:
    """只有 pricing 能采到、其余维度 broaden 也补不到 → 策展人模型:pricing 矩阵非空 →
    done(部分覆盖,缺维度显「—」),不再因缺 5 维盖 insufficient 章(真 run 暴露的修复)。"""
    name = "stuck"

    def search(self, query, *, max_results=5):
        if ("pricing" in query) or ("价格" in query):
            url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
            return [SearchResult(url=url, title="t", content="s", raw_content="pricing body")]
        return []


class _DeadProvider:
    """任何 query 都采不到 → 策展后矩阵全空 + 无决策 → 真·insufficient_evidence。"""
    name = "dead"

    def search(self, query, *, max_results=5):
        return []


def _fake_analyze(evidence, competitors, *, dimensions=None, degraded_sink=None, client, model):
    """按证据已覆盖的维度产出分析:覆盖 dims_present 的对比行,引用真实证据 id。
    pricing profile 挂合法引用 → 确定性 traceability 过;无 features/personas/swot(空,不被遍历)。"""
    dims_present = {e.dimension for e in evidence}
    profiles = []
    for c in competitors:
        price_ev = next((e for e in evidence if e.competitor == c and e.dimension == "pricing"), None)
        refs = [EvidenceRef(evidence_id=price_ev.id, quote="q")] if price_ev else []
        profiles.append(CompetitorProfile(
            name=c, pricing=PricingModel(model_type="freemium", evidence_refs=refs), swot=SWOT()))
    rows = []
    for dim in CONTROLLED_DIMENSIONS:
        if dim not in dims_present:
            continue
        cells = []
        for c in competitors:
            ev = next((e for e in evidence if e.competitor == c and e.dimension == dim), None)
            if ev:
                cells.append(ComparisonCell(competitor=c, value_type="enum", value="x",
                                            evidence_refs=[EvidenceRef(evidence_id=ev.id, quote="q")]))
        rows.append(ComparisonRow(dimension=dim, cells=cells))
    return CompetitorAnalysis(competitors=profiles, comparison=rows)


@pytest.fixture(autouse=True)
def _stub_agents(monkeypatch):
    # 假 analyze / 假 write(报告内容与闭环断言无关,返 (md, insight))/ 假蕴含(返回无问题)。
    # decide 节点用真 generate_decisions:client=None → 优雅降级(空决策),不影响闭环断言。
    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _fake_analyze)
    monkeypatch.setattr(
        "rivalradar.graph.nodes.write_report_with_insight",
        lambda *a, **k: ("# 竞品分析报告\n正文",
                         ReportInsight(market_context="m", differentiation_thesis="d",
                                       actionable_takeaway="a")))
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])


def test_real_feedback_loop_improves_to_pass(conn):
    run_id, final = run_research(
        ["Notion"], list(CONTROLLED_DIMENSIONS),
        conn=conn, client=None, model="m", provider=_ImprovingProvider(),
        as_of="2026-05-26", max_retries=2)

    trace = repo.list_trace(conn, run_id)
    collects = [t for t in trace if t["node"] == "collect"]
    qcs = [t for t in trace if t["node"] == "qc"]

    # 1) 恰好打回重采一次(collect 跑 2 次:首遍全量 + 一次补缺口),pass 后无多余循环
    assert len(collects) == 2
    assert collects[0]["input_summary"] == "targets=all"        # 首遍全量
    assert collects[1]["input_summary"] == "targets=5 gaps"     # retry 只补 5 个缺口维(白盒锁死)

    # 2) 第一遍确实因覆盖不足被打回(可证伪:证明不是碰巧两次 collect)
    assert "verdict=retry_collect" in qcs[0]["output_summary"]

    # 3) 第二版证据精确增加:首遍 pricing en+zh=2 + broaden 5 维×2 语=10 → 共 12
    assert len(repo.list_evidence(conn, run_id)) == 12

    # 4) 最终 qc=pass(覆盖补齐 + 引用合法 + 蕴含无问题)
    assert final["qc_result"]["verdict"] == "pass"
    assert final["status"] == "done"


def test_bounded_retry_partial_coverage_becomes_done(conn):
    """策展人模型(真 run 暴露的修复):只有 pricing 能采到、其余 5 维补不到 → 有界重试
    耗尽,但 pricing 矩阵非空 → done(缺维度显「—」+ 轻量覆盖说明),绝不盖数据不足章。"""
    run_id, final = run_research(
        ["Notion"], list(CONTROLLED_DIMENSIONS),
        conn=conn, client=None, model="m", provider=_StuckProvider(),
        as_of="2026-05-26", max_retries=2)

    assert final["status"] == "done"                      # 有 pricing 产出 → done
    assert final["qc_result"]["verdict"] == "pass"        # 可交付
    assert "覆盖说明" in final["report"]                  # 轻量诚实说明
    assert "数据不足" not in final["report"]
    assert final["retry_count"] == 2                      # 仍跑满有界重试(broaden 环不变)


def test_bounded_retry_truly_empty_becomes_insufficient(conn):
    """真·空手(任何维度都采不到)→ 策展后矩阵全空 + 无决策 → insufficient_evidence + 诚实 banner。"""
    run_id, final = run_research(
        ["Notion"], list(CONTROLLED_DIMENSIONS),
        conn=conn, client=None, model="m", provider=_DeadProvider(),
        as_of="2026-05-26", max_retries=2)

    assert final["qc_result"]["verdict"] == "insufficient_evidence"
    assert final["status"] == "insufficient_evidence"
    assert "未找到公开数据" in final["report"]
    assert final["retry_count"] == 2                      # retry_count 封顶,无限循环防护
