from pathlib import Path

from rivalradar.evals import (
    decision_traceability_violations, platitude_violations,
    decision_platitude_violations, insight_platitude_violations,
    report_structural_violations,
)
from rivalradar.schema.models import Decision, DecisionSet, EvidenceRef, ReportInsight


def _decision(action="本周评估飞书审批接入", why="飞书审批生态成熟", refs=("e1",)):
    return Decision(stance="建议采用", action=action, horizon="短期",
                    risk_reversibility="可逆", risk_cost="低", why=why,
                    evidence_refs=[EvidenceRef(evidence_id=r, quote="q") for r in refs])


# ── (b) 决策可溯源机械门 ─────────────────────────────────────────────────────
def test_decision_traceability_clean_passes():
    assert decision_traceability_violations(DecisionSet(decisions=[_decision()])) == []


def test_decision_traceability_flags_empty_refs():
    d = Decision(stance="建议采用", action="x", horizon="短期", risk_reversibility="可逆",
                 risk_cost="低", why="y", evidence_refs=[])
    assert decision_traceability_violations(DecisionSet(decisions=[d]))


def test_decision_traceability_flags_dangling_id():
    ds = DecisionSet(decisions=[_decision(refs=("ghost",))])
    assert decision_traceability_violations(ds, valid_evidence_ids={"e1"})


def test_decision_traceability_clean_with_valid_ids():
    ds = DecisionSet(decisions=[_decision(refs=("e1",))])
    assert decision_traceability_violations(ds, valid_evidence_ids={"e1"}) == []


# ── (c) 套话黑名单 ───────────────────────────────────────────────────────────
def test_platitude_flags_banned_term():
    assert platitude_violations(["我们应当持续关注该赛道"])


def test_platitude_clean_for_actionable_text():
    assert platitude_violations(["本周完成飞书审批接入评估并出选型结论"]) == []


def test_decision_platitude_clean_for_actionable():
    assert decision_platitude_violations(DecisionSet(decisions=[_decision()])) == []


def test_decision_platitude_flags_hedge_action():
    ds = DecisionSet(decisions=[_decision(action="持续关注钉钉动向")])
    assert decision_platitude_violations(ds)


def test_insight_platitude_flags_hedge():
    ins = ReportInsight(market_context="赛道", differentiation_thesis="因为X所以Y",
                        actionable_takeaway="保持观察,深入研究")
    assert insight_platitude_violations(ins)


# ── (a) 报告结构回归(rubric 24/30 机械代理)──────────────────────────────────
def test_report_structural_gate_passes_on_24_30_baseline():
    """回归锚点:committed run-002(24/30 baseline)报告必须通过结构门。
    若有人改坏报告结构(删执行洞察段 / 引入套话),此门立刻红。"""
    path = (Path(__file__).parent.parent
            / "references/rivalradar-output/run-002-writer-v2/report.md")
    md = path.read_text(encoding="utf-8")
    assert report_structural_violations(md) == []


def test_report_structural_gate_flags_missing_insight():
    assert report_structural_violations("# 竞品分析报告\n\n## 来源\n- [e1]")


def test_report_structural_gate_flags_platitude_in_insight():
    md = ("# 竞品分析报告\n\n## 执行洞察(AI)\n\n### 市场格局\n\n持续关注该赛道\n\n"
          "### 战略路径分歧\n\nX\n\n### 给企业产品团队的 takeaway\n\nY\n\n## 来源\n- [e1]")
    violations = report_structural_violations(md)
    assert any("套话" in v for v in violations)


def test_report_structural_ignores_platitude_in_body_quotes():
    """正文引语含套话词不算违规(只扫 insight 段)。"""
    md = ("# 竞品分析报告\n\n## 执行洞察(AI)\n\n### 市场格局\n\nM\n\n"
          "### 战略路径分歧\n\nX\n\n### 给企业产品团队的 takeaway\n\nY\n\n"
          "## 飞书\n\n该产品值得关注的功能\n\n## 来源\n- [e1]")
    assert report_structural_violations(md) == []
