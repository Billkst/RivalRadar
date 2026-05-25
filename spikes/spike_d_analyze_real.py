"""分析 Agent 真实 E2E:canned 证据 → analyze() → CompetitorAnalysis。需 ARK_API_KEY。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.agents.analyst import analyze
from rivalradar.schema.models import Evidence

EVIDENCE = [
    Evidence(id="e1", competitor="Notion", dimension="pricing",
             content="Notion offers a Free plan, Plus at $10/user/month, and Business tiers.",
             source_url="https://notion.so/pricing", source_title="Pricing", language="en",
             fetched_at="2026-05-25T00:00:00Z"),
    Evidence(id="e2", competitor="Notion", dimension="core_workflows",
             content="Notion includes docs, wikis, projects, and databases with multiple views.",
             source_url="https://notion.so/product", source_title="Product", language="en",
             fetched_at="2026-05-25T00:00:00Z"),
]


def main() -> None:
    client = config.get_doubao_client()
    out = analyze(EVIDENCE, ["Notion"], client=client, model=config.doubao_model())
    prof = out.competitors[0]
    print(f"competitor: {prof.name}")
    print(f"features: {[f.name for f in prof.features]}")
    print(f"pricing: {prof.pricing.model_type}, tiers={[t.name for t in prof.pricing.tiers]}")
    print(f"comparison rows: {[r.dimension for r in out.comparison]}")
    # 至少有一条结论挂了取自给定证据的 evidence_ref
    ref_ids = {r.evidence_id for f in prof.features for r in f.evidence_refs}
    ref_ids |= {r.evidence_id for r in prof.pricing.evidence_refs}
    print(f"cited evidence_ids: {ref_ids}")
    assert ref_ids & {"e1", "e2"}, "no conclusion cited the provided evidence"
    print("SPIKE D OK: real analysis with evidence refs")


if __name__ == "__main__":
    main()
