import json
from types import SimpleNamespace

from rivalradar.agents.qc import (
    check_traceability, check_ontology, check_coverage, EntailmentVerdict, check_entailment,
    decide_verdict, check, check_decision_traceability, check_decision_entailment,
    sanitize_qc_result,
)
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, FeatureItem, PricingModel,
    SWOT, SWOTPoint, ComparisonRow, ComparisonCell, EvidenceRef, Evidence,
    QCIssue, QCResult, Decision,
)


def _ref(eid):
    return EvidenceRef(evidence_id=eid, quote="q")


def _ev(eid, dimension="pricing"):
    return Evidence(id=eid, competitor="Notion", dimension=dimension, content="c",
                    source_url="u", source_title="t", language="en",
                    fetched_at="2026-05-25T00:00:00Z")


def test_check_traceability_flags_empty_refs():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        features=[FeatureItem(id="f1", name="db", description="", category="core_workflows",
                              evidence_refs=[])],  # 空引用
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    issues = check_traceability(analysis, [_ev("e1")])
    assert any(i.problem_type == "missing_evidence" for i in issues)


def test_check_traceability_flags_dangling_evidence_id():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e_ghost")]),  # 不存在
        swot=SWOT())])
    issues = check_traceability(analysis, [_ev("e1")])
    assert any("e_ghost" in i.detail for i in issues)


def test_check_traceability_clean_when_all_valid():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="x", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    assert check_traceability(analysis, [_ev("e1")]) == []


def test_check_ontology_flags_bad_comparison_and_evidence_dimension():
    analysis = CompetitorAnalysis(
        competitors=[],
        comparison=[ComparisonRow(dimension="天气", cells=[])])  # 非受控维度
    issues = check_ontology(analysis, [_ev("e1", dimension="八卦")])  # 证据维度也非受控
    kinds = [i.detail for i in issues]
    assert any("天气" in d for d in kinds)
    assert any("八卦" in d for d in kinds)
    assert all(i.problem_type == "schema_incomplete" for i in issues)


def test_check_coverage_flags_missing_dimension():
    # Notion 只在 pricing 有对比 cell,缺其余 5 个受控维度
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium")])])
    issues = check_coverage(analysis)
    missing_dims = {i.dimension for i in issues if i.problem_type == "low_coverage"}
    assert "deployment" in missing_dims and "pricing" not in missing_dims


def test_check_coverage_only_checks_requested_dimensions():
    """真 run 暴露的 bug 回归:只查请求的维度,不要求未请求的维度(如 review_sentiment)。

    原先 qc_node 用默认 required=全 6 受控本体 → 用户只请求 pricing 时,review_sentiment
    永远 low_coverage → retry_collect 死循环 → insufficient_evidence(再多采集也补不上)。
    """
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium")])])
    # 只请求 pricing(已覆盖)→ 0 low_coverage;绝不因 review_sentiment 等未请求维度报缺。
    issues = check_coverage(analysis, required=("pricing",))
    assert issues == []


class _Completions:
    def __init__(self, payloads):
        self.payloads = list(payloads); self.calls = 0

    def create(self, **kwargs):
        p = self.payloads[self.calls]; self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=p))]))],
            usage=SimpleNamespace(total_tokens=10))


class _FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=_Completions(payloads))


def test_check_entailment_flags_unsupported():
    # 单结论(pricing 挂 e1),模型判 not supported → hallucination
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    client = _FakeClient([json.dumps({"supported": False, "reason": "证据未提定价"})])
    issues = check_entailment(analysis, [_ev("e1")], client=client, model="m")
    assert len(issues) == 1 and issues[0].problem_type == "hallucination"


def test_check_entailment_passes_supported():
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
        swot=SWOT())])
    client = _FakeClient([json.dumps({"supported": True, "reason": ""})])
    assert check_entailment(analysis, [_ev("e1")], client=client, model="m") == []


def test_check_entailment_skips_empty_refs():
    # 空引用归 traceability 管,蕴含不调用 LLM(payloads 给空也不该被取用)
    analysis = CompetitorAnalysis(competitors=[CompetitorProfile(
        name="Notion", pricing=PricingModel(model_type="x", evidence_refs=[]), swot=SWOT())])
    client = _FakeClient([])
    assert check_entailment(analysis, [_ev("e1")], client=client, model="m") == []


def test_decide_verdict_pass_when_no_issues():
    assert decide_verdict([]) == "pass"


def test_decide_verdict_retry_collect_for_missing_or_coverage():
    miss = [QCIssue(competitor="N", dimension="pricing", problem_type="missing_evidence", detail="")]
    cov = [QCIssue(competitor="N", dimension="deployment", problem_type="low_coverage", detail="")]
    assert decide_verdict(miss) == "retry_collect"
    assert decide_verdict(cov) == "retry_collect"


def test_decide_verdict_retry_analyze_for_hallucination_or_schema():
    hall = [QCIssue(competitor="N", dimension="pricing", problem_type="hallucination", detail="")]
    schema = [QCIssue(competitor="*", dimension="天气", problem_type="schema_incomplete", detail="")]
    assert decide_verdict(hall) == "retry_analyze"
    assert decide_verdict(schema) == "retry_analyze"


def test_decide_verdict_collect_takes_priority_over_analyze():
    mixed = [
        QCIssue(competitor="N", dimension="pricing", problem_type="hallucination", detail=""),
        QCIssue(competitor="N", dimension="pricing", problem_type="missing_evidence", detail=""),
    ]
    assert decide_verdict(mixed) == "retry_collect"  # 缺证据优先于重分析


def test_check_end_to_end_clean_passes():
    # 全受控维度都覆盖 + 所有结论引用有效(含 pricing 结论)+ 蕴含 supported → pass
    dims = ("pricing", "deployment", "integrations", "target_users", "core_workflows", "review_sentiment")
    rows = [ComparisonRow(dimension=d, cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="v", evidence_refs=[_ref("e1")])])
        for d in dims]
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(
            name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e1")]),
            swot=SWOT())],
        comparison=rows)
    # 结论数 = pricing 1 条 + 6 个对比 cell = 7 → 蕴含 7 次 supported(空引用结论会被跳过,此处无)
    client = _FakeClient([json.dumps({"supported": True, "reason": ""}) for _ in range(7)])
    result = check(analysis, [_ev("e1")], client=client, model="m")
    assert isinstance(result, QCResult)
    assert result.verdict == "pass" and result.issues == []


# ── QC-on-decisions(Epic 2.3)───────────────────────────────────────────────
def _decision(action="本周评估飞书审批接入", refs=("e1",)):
    return Decision(stance="建议采用", action=action, horizon="短期",
                    risk_reversibility="可逆", risk_cost="低", why="飞书审批生态成熟",
                    evidence_refs=[EvidenceRef(evidence_id=r, quote="q") for r in refs])


def test_check_decision_traceability_flags_empty_refs():
    d = Decision(stance="建议采用", action="x", horizon="短期", risk_reversibility="可逆",
                 risk_cost="低", why="y", evidence_refs=[])
    issues = check_decision_traceability([d], [_ev("e1")])
    assert any(i.problem_type == "missing_evidence" and i.dimension == "decision" for i in issues)


def test_check_decision_traceability_flags_dangling_id():
    issues = check_decision_traceability([_decision(refs=("ghost",))], [_ev("e1")])
    assert any("ghost" in i.detail for i in issues)


def test_check_decision_traceability_clean_when_valid():
    assert check_decision_traceability([_decision(refs=("e1",))], [_ev("e1")]) == []


def test_check_decision_entailment_flags_unsupported():
    client = _FakeClient([json.dumps({"supported": False, "reason": "证据与该建议无关"})])
    issues = check_decision_entailment([_decision(refs=("e1",))], [_ev("e1")], client=client, model="m")
    assert len(issues) == 1 and issues[0].problem_type == "hallucination"
    assert issues[0].dimension == "decision"


def test_check_decision_entailment_clean_when_supported():
    client = _FakeClient([json.dumps({"supported": True, "reason": ""})])
    assert check_decision_entailment([_decision(refs=("e1",))], [_ev("e1")],
                                     client=client, model="m") == []


def test_check_decision_entailment_cost_guard_caps_calls():
    """COST GUARD(Codex #4):决策数 > max_calls 时封顶,防 retry-storm 撞 90s timeout。"""
    decisions = [_decision(action=f"动作{i}", refs=("e1",)) for i in range(10)]
    client = _FakeClient([json.dumps({"supported": True, "reason": ""}) for _ in range(10)])
    check_decision_entailment(decisions, [_ev("e1")], client=client, model="m", max_calls=3)
    assert client.chat.completions.calls == 3  # 只调 3 次,其余 7 条不验证(机械门仍覆盖)


def test_check_decision_entailment_skips_empty_refs():
    d = Decision(stance="建议采用", action="x", horizon="短期", risk_reversibility="可逆",
                 risk_cost="低", why="y", evidence_refs=[])
    client = _FakeClient([])  # 不应触发任何调用
    assert check_decision_entailment([d], [_ev("e1")], client=client, model="m") == []
    assert client.chat.completions.calls == 0


def test_check_decision_entailment_skips_dangling_refs():
    """悬空引用决策归 traceability,蕴含预过滤跳过,不耗 cost guard 预算(adversarial M3)。"""
    client = _FakeClient([])  # 悬空 → 0 调用
    assert check_decision_entailment([_decision(refs=("ghost",))], [_ev("e1")],
                                     client=client, model="m") == []
    assert client.chat.completions.calls == 0


def test_sanitize_qc_result_strips_model_text_to_canned_detail():
    """Epic 2.4 / Codex #9:/qc 公开端点 sanitize —— detail 含模型文本必须被罐装文案替换,
    保留 competitor/dimension/problem_type 供前端;原始模型片段绝不泄漏。"""
    result = QCResult(verdict="retry_analyze", issues=[QCIssue(
        competitor="飞书", dimension="decision", problem_type="hallucination",
        detail="证据不支撑决策(采购飞书):模型原话含敏感片段 SECRET_xyz")])
    out = sanitize_qc_result(result)
    assert out["verdict"] == "retry_analyze"
    issue = out["issues"][0]
    assert issue["competitor"] == "飞书" and issue["problem_type"] == "hallucination"
    assert "SECRET_xyz" not in issue["detail"]           # 模型文本不泄漏
    assert issue["detail"] == "证据未能支撑该结论"        # 罐装文案


def test_sanitize_qc_result_whitelists_out_of_ontology_dimension():
    """schema_incomplete issue 的 dimension 是 LLM 越界文本 → sanitize 替占位,
    绝不经公开 /qc 回吐模型产出的任意维度名(adversarial M1)。"""
    result = QCResult(verdict="retry_analyze", issues=[QCIssue(
        competitor="*", dimension="模型乱吐的越界维度SECRET", problem_type="schema_incomplete",
        detail="维度不在受控本体")])
    out = sanitize_qc_result(result)
    assert out["issues"][0]["dimension"] == "out_of_ontology"  # 越界维度替占位
    assert "SECRET" not in out["issues"][0]["dimension"]


def test_sanitize_qc_result_keeps_controlled_dimension():
    """受控维度 / decision 维度原样保留(供前端定位)。"""
    result = QCResult(verdict="retry_collect", issues=[
        QCIssue(competitor="飞书", dimension="pricing", problem_type="low_coverage", detail="x"),
        QCIssue(competitor="*", dimension="decision", problem_type="missing_evidence", detail="y")])
    out = sanitize_qc_result(result)
    assert out["issues"][0]["dimension"] == "pricing"
    assert out["issues"][1]["dimension"] == "decision"


def test_check_end_to_end_retry_collect_with_issues_flowing_through():
    # pricing 空引用(traceability→missing_evidence)+ 无对比(coverage→6×low_coverage)
    # 空引用结论被 entailment 跳过 → 0 次 LLM 调用 → verdict=retry_collect
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(name="Notion", pricing=PricingModel(model_type="x"), swot=SWOT())],
        comparison=[])
    client = _FakeClient([])  # 不应触发任何蕴含调用
    result = check(analysis, [_ev("e1")], client=client, model="m")
    assert result.verdict == "retry_collect"
    assert any(i.problem_type == "missing_evidence" for i in result.issues)
    assert client.chat.completions.calls == 0  # 空引用结论不调 LLM
