import hashlib

from rivalradar.agents import qc
from rivalradar.graph.nodes import make_collect_node, make_analyze_node, make_write_node, make_qc_node
from rivalradar.llm.structured import StructuredCallError
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, PricingModel, SWOT,
    ComparisonRow, ComparisonCell, EvidenceRef,
)
from rivalradar.search.base import SearchResult
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db
import pytest


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


class _FakeProvider:
    """首遍只对 pricing 返回源;broaden 时对任意维度返回新 url(模拟换源采到新证据)。"""
    name = "fake"

    def search(self, query, *, max_results=5):
        is_broaden = ("comparison" in query) or ("替代方案" in query)
        is_pricing = ("pricing" in query) or ("价格" in query)
        if not is_broaden and not is_pricing:
            return []
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="snippet",
                             raw_content="evidence body for " + query)]


_CFG = {"configurable": {"thread_id": "r1"}}


def test_collect_node_first_pass_collects_and_persists(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_collect_node(conn=conn, provider=_FakeProvider(), official_domains={})
    out = node({"competitors": ["Notion"], "dimensions": ["pricing"], "evidence": [],
                "retry_count": 0}, _CFG)
    assert len(out["evidence"]) >= 1                       # 采到 pricing 证据
    assert len(repo.list_evidence(conn, "r1")) == len(out["evidence"])  # 落库


def test_collect_node_retry_only_fills_gap_with_broaden(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing", "core_workflows"])
    node = make_collect_node(conn=conn, provider=_FakeProvider(), official_domains={})
    # 模拟:已有 pricing 证据;qc 报 core_workflows low_coverage → 只补该缺口
    existing = [{"id": "old1", "competitor": "Notion", "dimension": "pricing", "content": "c",
                 "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    qc_result = {"verdict": "retry_collect", "issues": [
        {"competitor": "Notion", "dimension": "core_workflows",
         "problem_type": "low_coverage", "detail": ""}]}
    out = node({"competitors": ["Notion"], "dimensions": ["pricing", "core_workflows"],
                "evidence": existing, "retry_count": 0, "qc_result": qc_result}, _CFG)
    dims = {e["dimension"] for e in out["evidence"]}
    assert dims == {"core_workflows"}        # 只补缺口维度,不重采 pricing
    assert all(e["id"] != "old1" for e in out["evidence"])  # 只返回新增


def test_collect_node_dedups_against_existing(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_collect_node(conn=conn, provider=_FakeProvider(), official_domains={})
    first = node({"competitors": ["Notion"], "dimensions": ["pricing"], "evidence": [],
                  "retry_count": 0}, _CFG)
    # 再以 first 的结果作为 existing 首遍重跑:相同 url → 相同 id → 全去重 → 0 新增
    again = node({"competitors": ["Notion"], "dimensions": ["pricing"],
                  "evidence": first["evidence"], "retry_count": 0}, _CFG)
    assert again["evidence"] == []


def test_collect_node_retry_dedups_same_source(conn):
    # retry 路径同源去重:同 (comp,dim) broaden → 同 url → 同 id → 不重复 insert(防 PRIMARY KEY 冲突)
    repo.create_run(conn, "r1", ["Notion"], ["pricing", "core_workflows"])
    node = make_collect_node(conn=conn, provider=_FakeProvider(), official_domains={})
    qc_result = {"verdict": "retry_collect", "issues": [
        {"competitor": "Notion", "dimension": "core_workflows",
         "problem_type": "low_coverage", "detail": ""}]}
    base = {"competitors": ["Notion"], "dimensions": ["pricing", "core_workflows"],
            "evidence": [], "retry_count": 0, "qc_result": qc_result}
    first = node(base, _CFG)
    assert len(first["evidence"]) >= 1                            # retry 补到 core_workflows
    again = node({**base, "evidence": first["evidence"]}, _CFG)   # 同源重采
    assert again["evidence"] == []                               # 全去重,0 新增,不抛 UNIQUE


def test_analyze_node_converts_evidence_and_persists(conn, monkeypatch):
    import rivalradar.graph.nodes as nodes_mod
    from rivalradar.schema.models import (
        CompetitorAnalysis, CompetitorProfile, PricingModel, SWOT,
    )
    fake = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())], comparison=[])
    seen = {}

    def _fake_analyze(evidence, competitors, *, client, model):
        seen["n"] = len(evidence)                  # 验证 dict→Evidence 转换后传入
        return fake
    monkeypatch.setattr(nodes_mod, "analyze", _fake_analyze)
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_analyze_node(conn=conn, client=None, model="m")
    ev = [{"id": "e1", "competitor": "Notion", "dimension": "pricing", "content": "c",
           "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    out = node({"competitors": ["Notion"], "evidence": ev}, _CFG)
    assert seen["n"] == 1                                          # 证据 dict 已转 Evidence
    assert out["analysis"]["competitors"][0]["name"] == "Notion"  # 返回 model_dump
    assert repo.get_analysis(conn, "r1") is not None              # 落库


def test_write_node_renders_and_persists(conn, monkeypatch):
    import rivalradar.graph.nodes as nodes_mod
    monkeypatch.setattr(nodes_mod, "write_report",
                        lambda analysis, evidence, *, as_of, client, model: "# 竞品分析报告\nX")
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_write_node(conn=conn, client=None, model="m", as_of="2026-05-26")
    out = node({"analysis": {"competitors": [], "comparison": []}, "evidence": []}, _CFG)
    assert out["report"].startswith("# 竞品分析报告")              # 渲染产出
    assert repo.get_report(conn, "r1") == out["report"]           # 落库


_CONTROLLED = ("pricing", "deployment", "integrations", "target_users",
               "core_workflows", "review_sentiment")


def _full_clean_analysis(eid="g1"):
    """覆盖全 6 维、引用合法的干净分析 → 确定性闸应全过。"""
    ref = [EvidenceRef(evidence_id=eid, quote="q")]
    rows = [ComparisonRow(dimension=d, cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="x", evidence_refs=ref)])
        for d in _CONTROLLED]
    return CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=ref), swot=SWOT())],
        comparison=rows)


def _evidence_all_dims(eid="g1"):
    return [{"id": eid, "competitor": "Notion", "dimension": d, "content": "c",
             "source_url": "u" + d, "source_title": "t", "language": "en", "fetched_at": "t0"}
            for d in _CONTROLLED]


def test_qc_node_degrades_on_entailment_failure(conn, monkeypatch):
    # check_entailment 上抛 → 节点捕获降级为仅确定性闸(必办项①)
    def _boom(*a, **k):
        raise StructuredCallError("entailment boom")
    monkeypatch.setattr(qc, "check_entailment", _boom)
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    state = {"analysis": _full_clean_analysis().model_dump(),
             "evidence": _evidence_all_dims(), "retry_count": 0}
    out = node(state, _CFG)
    assert out["degraded"] is True
    assert out["qc_result"]["verdict"] == "pass"   # 确定性闸全过 → pass,蕴含降级不阻断
    traces = [t for t in repo.list_trace(conn, "r1") if "degraded" in (t["output_summary"] or "")]
    assert traces                                   # 降级写了 trace


def test_qc_node_retry_count_bumps_only_with_prior_result(conn, monkeypatch):
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    base = {"analysis": _full_clean_analysis().model_dump(), "evidence": _evidence_all_dims()}
    first = node({**base, "retry_count": 0}, _CFG)          # 首遍无 qc_result
    assert first["retry_count"] == 0
    second = node({**base, "retry_count": 0, "qc_result": first["qc_result"]}, _CFG)  # 带上轮
    assert second["retry_count"] == 1


def test_qc_node_low_coverage_triggers_retry_collect(conn, monkeypatch):
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    # 只覆盖 pricing 的分析 → coverage 缺 5 维 → retry_collect
    ref = [EvidenceRef(evidence_id="g1", quote="q")]
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=ref), swot=SWOT())],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="x", evidence_refs=ref)])])
    evidence = [{"id": "g1", "competitor": "Notion", "dimension": "pricing", "content": "c",
                 "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    out = node({"analysis": analysis.model_dump(), "evidence": evidence, "retry_count": 0}, _CFG)
    assert out["qc_result"]["verdict"] == "retry_collect"


def test_qc_node_degrades_on_non_structured_error(conn, monkeypatch):
    # 网络/限流类原生异常(非 StructuredCallError)也必须降级,不崩整图(必办项①,opus 评审 C1)
    def _boom(*a, **k):
        raise RuntimeError("rate limit / network blip")
    monkeypatch.setattr(qc, "check_entailment", _boom)
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    state = {"analysis": _full_clean_analysis().model_dump(),
             "evidence": _evidence_all_dims(), "retry_count": 0}
    out = node(state, _CFG)
    assert out["degraded"] is True
    assert out["qc_result"]["verdict"] == "pass"   # 网络错降级 → 仅确定性闸 → pass,不崩整图
