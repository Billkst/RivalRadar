import pytest
from pydantic import ValidationError

from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS,
    CompetitorAnalysis,
    CompetitorProfile,
    Evidence,
    EvidenceRef,
    FeatureItem,
    PricingModel,
    PricingTier,
    SWOT,
    SWOTPoint,
    UserPersona,
    ComparisonCell,
    ComparisonRow,
    QCIssue,
    QCResult,
    Decision,
    DecisionSet,
    Watch,
)


def test_evidence_ref_defaults_to_supported():
    ref = EvidenceRef(evidence_id="e1", quote="支持每月 $10 起")
    assert ref.support_verdict == "supported"
    assert ref.start is None and ref.end is None


def test_evidence_rejects_unknown_language():
    with pytest.raises(ValidationError):
        Evidence(
            id="e1", competitor="Notion", dimension="pricing", content="...",
            source_url="https://notion.so/pricing", source_title="Pricing",
            language="fr", fetched_at="2026-05-25T00:00:00Z",
        )


def test_controlled_dimensions_has_six_axes():
    assert {
        "pricing", "deployment", "integrations",
        "target_users", "core_workflows", "review_sentiment",
    } <= set(CONTROLLED_DIMENSIONS)


def test_full_analysis_roundtrips_json():
    ref = EvidenceRef(evidence_id="e1", quote="免费版含无限页面", support_verdict="supported")
    profile = CompetitorProfile(
        name="Notion",
        features=[FeatureItem(id="f1", name="数据库", description="表格视图",
                              category="core_workflows", evidence_refs=[ref])],
        pricing=PricingModel(
            model_type="freemium",
            tiers=[PricingTier(name="Free", price="$0", billing_cycle="monthly")],
            evidence_refs=[ref],
        ),
        personas=[UserPersona(segment="个人用户", needs=["笔记"], evidence_refs=[ref])],
        swot=SWOT(strengths=[SWOTPoint(text="灵活", evidence_refs=[ref])]),
    )
    analysis = CompetitorAnalysis(
        competitors=[profile],
        comparison=[ComparisonRow(
            dimension="pricing",
            cells=[ComparisonCell(competitor="Notion", value_type="number",
                                  value="0", evidence_refs=[ref])],
        )],
    )
    restored = CompetitorAnalysis.model_validate_json(analysis.model_dump_json())
    assert restored == analysis


def test_qc_result_defaults_empty_issues():
    result = QCResult(verdict="pass")
    assert result.issues == []
    issue = QCIssue(competitor="Notion", dimension="pricing",
                    problem_type="missing_evidence", detail="无定价证据")
    assert issue.problem_type == "missing_evidence"


# ── Decision pipeline(Epic 2.1)─────────────────────────────────────────────
def _dref():
    return EvidenceRef(evidence_id="e1", quote="飞书 2024 年审批模块上线")


def test_decision_adopt_valid_without_watch():
    """建议采用/需要警惕 不要求 watch,可逆性 + 成本 + 命令式 action 齐备即合法。"""
    d = Decision(
        stance="建议采用", action="本周评估飞书审批接入", horizon="短期",
        risk_reversibility="可逆", risk_cost="低", why="飞书审批生态成熟",
        evidence_refs=[_dref()],
    )
    assert d.stance == "建议采用" and d.watch is None


def test_decision_observe_requires_full_watch():
    """持续观察 必须带完整 watch{metric,threshold,trigger},缺则 schema 拒绝(反套话)。"""
    base = dict(stance="持续观察", action="跟踪钉钉 AI 渗透率", horizon="中期",
                risk_reversibility="可逆", risk_cost="低", why="趋势未定",
                evidence_refs=[_dref()])
    with pytest.raises(ValidationError):
        Decision(**base)  # watch 缺失
    # 三字段任一空都必须拒绝(锁死 metric/threshold/trigger 全必填,防 and→or 改坏)
    with pytest.raises(ValidationError):
        Decision(**base, watch=Watch(metric="", threshold=">30%", trigger="复评"))
    with pytest.raises(ValidationError):
        Decision(**base, watch=Watch(metric="渗透率", threshold="", trigger="复评"))
    with pytest.raises(ValidationError):
        Decision(**base, watch=Watch(metric="渗透率", threshold=">30%", trigger=""))
    ok = Decision(**base, watch=Watch(metric="AI 渗透率", threshold=">30%", trigger="复评接入"))
    assert ok.watch.threshold == ">30%"


def test_decision_rejects_legacy_stance_terms():
    """术语锁定:旧稿 下注/防守/观察 不再合法(backend↔frontend↔UI 同字面值)。"""
    with pytest.raises(ValidationError):
        Decision(stance="下注", action="x", horizon="短期", risk_reversibility="可逆",
                 risk_cost="低", why="y", evidence_refs=[_dref()])


def test_decision_set_roundtrips_json():
    ds = DecisionSet(decisions=[Decision(
        stance="需要警惕", action="盯紧企业微信免费策略", horizon="中期",
        risk_reversibility="不可逆", risk_cost="高", why="价格战风险",
        evidence_refs=[_dref()])])
    assert DecisionSet.model_validate_json(ds.model_dump_json()) == ds
