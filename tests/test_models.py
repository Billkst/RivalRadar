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
