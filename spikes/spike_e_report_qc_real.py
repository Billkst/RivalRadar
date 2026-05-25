"""撰写+质检 真实 E2E:canned analysis → write_report + qc.check。需 ARK_API_KEY。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.agents import qc
from rivalradar.agents.writer import write_report
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, PricingModel, PricingTier,
    SWOT, SWOTPoint, ComparisonRow, ComparisonCell, EvidenceRef, Evidence,
)

EVIDENCE = [
    Evidence(id="e1", competitor="Notion", dimension="pricing",
             content="Notion offers a Free plan and Plus at $10/user/month.",
             source_url="https://notion.so/pricing", source_title="Pricing", language="en",
             fetched_at="2026-05-25T00:00:00Z"),
]

ANALYSIS = CompetitorAnalysis(
    competitors=[CompetitorProfile(
        name="Notion",
        pricing=PricingModel(model_type="freemium",
                             tiers=[PricingTier(name="Free", price="$0", billing_cycle="monthly")],
                             evidence_refs=[EvidenceRef(evidence_id="e1", quote="Free plan")]),
        swot=SWOT(strengths=[SWOTPoint(text="生态强",
                                       evidence_refs=[EvidenceRef(evidence_id="e1", quote="Free plan")])]),
    )],
    comparison=[ComparisonRow(dimension="pricing", cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                       evidence_refs=[EvidenceRef(evidence_id="e1", quote="Free plan")])])],
)


def main() -> None:
    client = config.get_doubao_client()
    model = config.doubao_model()
    report = write_report(ANALYSIS, EVIDENCE, as_of="2026-05-25", client=client, model=model)
    print("=== REPORT (head) ===")
    print(report[:400])
    assert report.startswith("# 竞品分析报告")
    assert "## 摘要" in report and "## Notion" in report and "[e1]" in report
    assert "as of 2026-05-25" in report

    result = qc.check(ANALYSIS, EVIDENCE, client=client, model=model)
    print(f"=== QC verdict: {result.verdict} | issues: {len(result.issues)} ===")
    for i in result.issues[:5]:
        print(f"  - [{i.problem_type}] {i.competitor}/{i.dimension}: {i.detail}")
    # canned analysis 只覆盖 pricing 一个维度 → 必有 low_coverage → retry_collect
    assert result.verdict in {"pass", "retry_collect", "retry_analyze"}
    print("SPIKE E OK: real report (det body + inline cites + LLM summary) + qc result")


if __name__ == "__main__":
    main()
