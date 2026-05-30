import hashlib
import json
import threading
from types import SimpleNamespace

from rivalradar.agents import qc
from rivalradar.graph.nodes import (
    make_collect_node, make_analyze_node, make_write_node, make_qc_node, make_decide_node,
    _make_ticker,
)
from rivalradar.llm.structured import StructuredCallError
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, PricingModel, SWOT,
    ComparisonRow, ComparisonCell, EvidenceRef, ReportInsight,
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

    def _fake_analyze(evidence, competitors, *, dimensions=None, degraded_sink=None, on_progress=None, client, model):
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


def test_analyze_node_sets_degraded_when_extraction_degrades(conn, monkeypatch):
    # silent-failure 修复端到端:analyze 把降级 label 填进 degraded_sink → 节点置 run 级
    # degraded(out["degraded"]=True)+ trace output_summary 含降级 marker(降级必可见)。
    import rivalradar.graph.nodes as nodes_mod
    from rivalradar.schema.models import (
        CompetitorAnalysis, CompetitorProfile, PricingModel, SWOT,
    )
    fake = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="未知"), swot=SWOT())], comparison=[])

    def _degrading_analyze(evidence, competitors, *, dimensions=None, degraded_sink=None, on_progress=None, client, model):
        if degraded_sink is not None:
            degraded_sink.append("Notion.features")  # 模拟单项抽取降级
        return fake
    monkeypatch.setattr(nodes_mod, "analyze", _degrading_analyze)
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_analyze_node(conn=conn, client=None, model="m")
    ev = [{"id": "e1", "competitor": "Notion", "dimension": "pricing", "content": "c",
           "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    out = node({"competitors": ["Notion"], "evidence": ev}, _CFG)
    assert out.get("degraded") is True                               # run 级 degraded 置位
    traces = repo.list_trace(conn, "r1")
    analyze_trace = [t for t in traces if t["node"] == "analyze"][-1]
    assert "降级" in analyze_trace["output_summary"]                # trace 含降级 marker(可见)


def test_write_node_renders_and_persists(conn, monkeypatch):
    import rivalradar.graph.nodes as nodes_mod
    monkeypatch.setattr(
        nodes_mod, "write_report_with_insight",
        lambda analysis, evidence, *, as_of, client, model: (
            "# 竞品分析报告\nX",
            ReportInsight(market_context="m", differentiation_thesis="d",
                          actionable_takeaway="a")))
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    node = make_write_node(conn=conn, client=None, model="m", as_of="2026-05-26")
    out = node({"analysis": {"competitors": [], "comparison": []}, "evidence": []}, _CFG)
    assert out["report"].startswith("# 竞品分析报告")              # 渲染产出
    assert repo.get_report(conn, "r1") == out["report"]           # 落库
    assert repo.get_insight(conn, "r1").market_context == "m"     # Epic 2.4:insight 持久化


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


from rivalradar.graph.nodes import make_finalize_node


def test_finalize_pass_marks_done(conn):
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _full_clean_analysis().model_dump(), "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "pass", "issues": []}, "retry_count": 0}
    out = node(state, _CFG)
    assert out["status"] == "done"
    assert out["report"] == "# 竞品分析报告\n正文"          # pass 不加 banner
    assert repo.get_run(conn, "r1")["status"] == "done"


def test_finalize_pass_but_empty_becomes_insufficient(conn):
    """ship-time 双模型评审 MAJOR(Claude+Codex 共识):verdict=pass 但策展后空手
    (每个请求维度都有证据 → coverage 无缺口 → pass,但所有 cell 被蕴含判不支撑全丢 + 无决策)
    → 绝不出"看似通过实则空白"的 done,必须诚实 insufficient_evidence。
    旧 finalize 的 `if verdict=="pass": done` 先于 substantive 闸命中 → 空 done(本测试钉死)。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _empty_analysis(), "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "pass", "issues": []}, "retry_count": 0}
    out = node(state, _CFG)
    assert out["status"] == "insufficient_evidence"                  # 空手不出 done
    assert out["qc_result"]["verdict"] == "insufficient_evidence"    # 终态 verdict 改写
    assert "数据不足" in out["report"]                               # 诚实 banner
    assert repo.get_run(conn, "r1")["status"] == "insufficient_evidence"


def test_finalize_persists_qc_result(conn):
    """Epic 2.4:finalize 持久化终态 QCResult(/qc 端点 serve)。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _full_clean_analysis().model_dump(), "report": "# 报告",
             "qc_result": {"verdict": "pass", "issues": []}, "retry_count": 0}
    node(state, _CFG)
    saved = repo.get_qc_result(conn, "r1")
    assert saved is not None and saved.verdict == "pass"


def test_finalize_persists_terminal_verdict_in_qc_result(conn):
    """retry_collect 耗尽 + 策展后空手 → finalize 改写 verdict=insufficient_evidence,
    持久化的 qc_result 必须反映终态 verdict(不是中途的 retry_collect)。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    empty = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
        comparison=[]).model_dump()
    state = {"analysis": empty, "report": "# 报告",
             "qc_result": {"verdict": "retry_collect", "issues": []}, "retry_count": 2}
    node(state, _CFG)
    assert repo.get_qc_result(conn, "r1").verdict == "insufficient_evidence"


def _empty_analysis():
    """策展后几乎空手:无对比 cell(coverage 全缺)→ 真·insufficient 路径。"""
    return CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
        comparison=[]).model_dump()


def test_finalize_exhausted_collect_empty_becomes_insufficient(conn):
    # 重试耗尽 + 策展后几乎空手(无矩阵 cell + 无决策)→ 真·insufficient_evidence
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _empty_analysis(), "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "retry_collect", "issues": []}, "retry_count": 2}
    out = node(state, _CFG)
    assert out["qc_result"]["verdict"] == "insufficient_evidence"   # 真空手 → 一等结论
    assert "未找到公开数据" in out["report"]                        # 诚实 banner
    assert out["status"] == "insufficient_evidence"


def test_finalize_exhausted_with_substantive_output_becomes_done(conn):
    """策展人模型核心(真 run 暴露):重试耗尽但策展后矩阵非空 / 有决策 → done,
    缺维度矩阵显「—」+ 轻量覆盖说明,绝不给 89% 满的报告盖「数据不足」章。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _full_clean_analysis().model_dump(),  # 矩阵有 cell
             "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "retry_collect",
                           "issues": [{"competitor": "Notion", "dimension": "deployment",
                                       "problem_type": "low_coverage", "detail": ""}]},
             "retry_count": 2}
    out = node(state, _CFG)
    assert out["status"] == "done"                       # 有产出 → done(不盖数据不足章)
    assert out["qc_result"]["verdict"] == "pass"         # verdict 记可交付
    assert "覆盖说明" in out["report"]                   # 轻量诚实说明(非 ⚠️ 数据不足)
    assert "数据不足" not in out["report"]
    assert repo.get_run(conn, "r1")["status"] == "done"


def test_finalize_exhausted_analyze_empty_becomes_degraded(conn):
    # 重试耗尽 + 几乎空手 + retry_analyze → degraded(真·未消解 hallucination 且无产出)
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _empty_analysis(), "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "retry_analyze", "issues": []}, "retry_count": 2}
    out = node(state, _CFG)
    assert "未达质检标准" in out["report"]
    assert out["status"] == "degraded"


def test_qc_node_degraded_sticky_across_rounds(conn, monkeypatch):
    """ship 修复 — degraded 必须 sticky OR 累积:round 1 entailment 降级,
    round 2 entailment 成功,终态 state.degraded 必须仍为 True(不能被 round 2 overwrite)。
    否则 finalize 把 db.degraded 写 False,前端 §11.5 警示横幅消失、对用户隐瞒降级事实。"""
    # round 1: entailment boom → local degraded=True
    def _boom(*a, **k):
        raise RuntimeError("round 1 rate limit")
    monkeypatch.setattr(qc, "check_entailment", _boom)
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_qc_node(conn=conn, client=None, model="m")
    base = {"analysis": _full_clean_analysis().model_dump(),
            "evidence": _evidence_all_dims(), "retry_count": 0}
    r1 = node(base, _CFG)
    assert r1["degraded"] is True  # round 1 降级 ✓

    # round 2: entailment 成功 — 但 prior state.degraded=True 必须 sticky
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])
    r2 = node({**base, "degraded": True, "qc_result": r1["qc_result"]}, _CFG)
    assert r2["degraded"] is True, \
        "BUG: degraded 被 round 2 成功 overwrite 为 False → 前端横幅消失"


def test_finalize_persists_state_degraded_with_pass_verdict(conn):
    """state.degraded=True 但 verdict=pass:db.runs.degraded 必须被持久化为 True。

    Lane D 遗留收口(spec §11.5 前端横幅依赖):蕴含闸跑挂被降级、但确定性闸 pass 时,
    status=done 但 db.degraded=1,Lane E GET /run/:id.degraded 据此暴露给前端。
    """
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_finalize_node(conn=conn, max_retries=2)
    state = {"analysis": _full_clean_analysis().model_dump(),
             "report": "# 竞品分析报告\n正文",
             "qc_result": {"verdict": "pass", "issues": []},
             "retry_count": 0,
             "degraded": True}
    out = node(state, _CFG)
    assert out["status"] == "done"  # verdict=pass → status=done
    run = repo.get_run(conn, "r1")
    assert run["degraded"] is True  # 关键:state.degraded → db.degraded 持久化


# ── decide 节点(full-C / Epic 2.2-2.3)──────────────────────────────────────
def _dec_wrap(p):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=p))]))],
        usage=SimpleNamespace(total_tokens=10))


class _DecCompletions:
    """decide 节点桩。curate_decisions 现在**并行**判蕴含 → entailment 调用顺序不确定,
    不能再按 call-order 派发 verdict(否则"留我/丢我"会随机错配)。entail_map 给定时,
    蕴含调用按 prompt 里的决策 action 内容键匹配(顺序无关、线程安全);generate 调用仍走
    order-index。entail_map=None 时退回纯 order-index(0/1 个蕴含调用的老测试不受影响)。"""
    _ENTAIL_MARK = "判断下列证据是否支撑该决策建议"

    def __init__(self, payloads, entail_map=None):
        self.payloads = list(payloads); self.calls = 0
        self.entail_map = entail_map  # {action_substr: supported_bool}
        self._lock = threading.Lock()

    def create(self, **kwargs):
        content = ""
        try:
            content = kwargs.get("messages", [{}])[0].get("content", "") or ""
        except Exception:  # noqa: BLE001 — 桩防御,内容取不到就走 order-index
            content = ""
        if self.entail_map is not None and self._ENTAIL_MARK in content:
            ok = next((v for a, v in self.entail_map.items() if a in content), True)
            return _dec_wrap(json.dumps({"supported": bool(ok), "reason": ""}))
        with self._lock:
            p = self.payloads[self.calls]; self.calls += 1
        return _dec_wrap(p)


class _DecClient:
    def __init__(self, payloads, entail_map=None):
        self.chat = SimpleNamespace(completions=_DecCompletions(payloads, entail_map))


def _decision_payload(eid="g1"):
    return json.dumps({"decisions": [{
        "stance": "建议采用", "action": "本周评估接入", "horizon": "短期",
        "risk_reversibility": "可逆", "risk_cost": "低", "why": "生态成熟",
        "evidence_refs": [{"evidence_id": eid, "quote": "q"}], "watch": None}]})


_SUPPORTED = json.dumps({"supported": True, "reason": ""})


def test_decide_node_generates_qcs_and_persists(conn):
    """happy:gen 出 1 条挂合法引用的决策 + 蕴含 supported → 无 issue,持久化,不降级。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    client = _DecClient([_decision_payload("g1"), _SUPPORTED])
    node = make_decide_node(conn=conn, client=client, model="m", as_of="2026-05-26")
    state = {"analysis": _full_clean_analysis("g1").model_dump(),
             "evidence": _evidence_all_dims("g1")}
    out = node(state, _CFG)
    assert out["decision_degraded"] is False
    assert len(out["decisions"]["decisions"]) == 1
    assert repo.get_decisions(conn, "r1").decisions[0].action == "本周评估接入"


def test_decide_node_degrades_on_generate_failure(conn):
    """生成失败(LLM 抛)→ 优雅降级:空决策 + decision_degraded,绝不崩图。"""
    class _Boom:
        def create(self, **k):
            raise RuntimeError("llm down")
    client = SimpleNamespace(chat=SimpleNamespace(completions=_Boom()))
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    node = make_decide_node(conn=conn, client=client, model="m", as_of="2026-05-26")
    out = node({"analysis": _full_clean_analysis().model_dump(),
                "evidence": _evidence_all_dims()}, _CFG)
    assert out["decision_degraded"] is True
    assert out["decisions"]["decisions"] == []
    assert repo.get_decisions(conn, "r1").decisions == []  # 空决策也持久化(非 None)


_DANGLING = json.dumps({"decisions": [{
    "stance": "建议采用", "action": "x", "horizon": "短期",
    "risk_reversibility": "可逆", "risk_cost": "低", "why": "y",
    "evidence_refs": [{"evidence_id": "ghost", "quote": "q"}], "watch": None}]})


def test_decide_node_curates_out_dangling(conn):
    """策展人模型:ungrounded(引用悬空)决策被丢弃(机械门,免 LLM),不重生、不降级。
    丢弃≠降级——decision_degraded 只为真·LLM 失败保留。calls=1(只 generate)。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    client = _DecClient([_DANGLING])
    node = make_decide_node(conn=conn, client=client, model="m", as_of="2026-05-26")
    out = node({"analysis": _full_clean_analysis("g1").model_dump(),
                "evidence": _evidence_all_dims("g1")}, _CFG)
    assert out["decision_degraded"] is False              # 策展丢弃不是降级
    assert out["decisions"]["decisions"] == []            # 悬空决策被丢
    assert client.chat.completions.calls == 1             # 只 generate,悬空免 LLM
    assert repo.get_decisions(conn, "r1").decisions == []  # 空决策也持久化


def test_decide_node_drops_unsupported_keeps_grounded(conn):
    """两条 grounded 决策,蕴含判一条支撑一条不支撑 → 只留支撑的(策展人筛而非否决整批)。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))
    two = json.dumps({"decisions": [
        {"stance": "建议采用", "action": "留我", "horizon": "短期", "risk_reversibility": "可逆",
         "risk_cost": "低", "why": "y", "evidence_refs": [{"evidence_id": "g1", "quote": "q"}], "watch": None},
        {"stance": "建议采用", "action": "丢我", "horizon": "短期", "risk_reversibility": "可逆",
         "risk_cost": "低", "why": "y", "evidence_refs": [{"evidence_id": "g1", "quote": "q"}], "watch": None}]})
    # 并行蕴含:verdict 按决策 action 内容键派发(顺序无关),不再靠 call-order(会随机错配)。
    client = _DecClient([two], entail_map={"留我": True, "丢我": False})
    node = make_decide_node(conn=conn, client=client, model="m", as_of="2026-05-26")
    out = node({"analysis": _full_clean_analysis("g1").model_dump(),
                "evidence": _evidence_all_dims("g1")}, _CFG)
    assert [d["action"] for d in out["decisions"]["decisions"]] == ["留我"]
    assert out["decision_degraded"] is False


def test_make_ticker_emits_incrementing_progress_threadsafe():
    """增量进度 ticker:并发 worker 调 tick(detail)→ 锁内自增 + emit progress(current/total),
    并发也不丢不重(锁串行化 put_nowait,从 worker 线程安全 emit 的关键)。emit None → None。"""
    events = []

    def emit(ev_type, data):
        events.append((ev_type, data))

    tick = _make_ticker(emit, "analyst", "thinking", total=3)
    threads = [threading.Thread(target=tick, args=(f"d{i}",)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(events) == 3
    assert all(ev == "progress" for ev, _ in events)
    assert all(d["agent_id"] == "analyst" and d["step"] == "thinking" for _, d in events)
    assert sorted(d["metric"]["current"] for _, d in events) == [1, 2, 3]  # 无丢失/无重复
    assert all(d["metric"]["total"] == 3 for _, d in events)
    assert _make_ticker(None, "x", "y", 1) is None  # emit 缺省(单测/CLI)→ no-op


def test_decide_node_degrades_on_entailment_failure(conn):
    """gen 成功但 entailment 抛 → 保机械门结果 + 降级 + break(防 storm),绝不崩图(M7)。"""
    repo.create_run(conn, "r1", ["Notion"], list(_CONTROLLED))

    class _GenOkEntailBoom:
        def __init__(self, gen_payload):
            self.gen_payload = gen_payload
            self.calls = 0
        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:  # generate_decisions
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                    tool_calls=[SimpleNamespace(function=SimpleNamespace(
                        arguments=self.gen_payload))]))], usage=SimpleNamespace(total_tokens=10))
            raise RuntimeError("entailment boom")  # check_decision_entailment 内 SDK 抛

    completions = _GenOkEntailBoom(_decision_payload("g1"))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    node = make_decide_node(conn=conn, client=client, model="m", as_of="2026-05-26")
    out = node({"analysis": _full_clean_analysis("g1").model_dump(),
                "evidence": _evidence_all_dims("g1")}, _CFG)
    assert out["decision_degraded"] is True               # 蕴含失败 → 降级
    assert completions.calls == 2                          # gen + 1 次 entail(抛即 break,不 storm)
    assert repo.get_decisions(conn, "r1").decisions[0].action == "本周评估接入"  # 机械门通过的决策仍落库
