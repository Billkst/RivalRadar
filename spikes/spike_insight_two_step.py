"""insight 两步化 spike:验证 (1) stream_chat 在 Doubao 真流 delta;(2) 草稿可被
structured_call 抽成合法 ReportInsight。需 ARK_API_KEY。不进 pytest(真打 LLM)。

跑法(WSL2 Clash:codex 走海外要代理,但 Doubao 是国内端点,务必 unset 代理 + NO_PROXY):
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
  NO_PROXY=localhost,127.0.0.1 .venv/bin/python spikes/spike_insight_two_step.py
"""
from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.agents.writer import generate_insight, render_body
from rivalradar.llm.streaming import stream_chat
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, ComparisonRow, ComparisonCell,
    Evidence, EvidenceRef, PricingModel, PricingTier, SWOT, SWOTPoint,
)

# production-size 近似:3 竞品 × 多维 body(真实 run body ~数 KB)。
_EV = [
    Evidence(id=f"e{i}", competitor=c, dimension=d,
             content=f"{c} 在 {d} 维度的公开资料正文片段。" * 8,
             source_url=f"https://example.com/{c}/{d}", source_title=f"{c} {d}",
             language="zh", fetched_at="2026-06-01T00:00:00Z")
    for i, (c, d) in enumerate(
        [(c, d) for c in ("飞书", "钉钉", "企业微信")
         for d in ("pricing", "deployment", "integrations")], start=1)
]


def _profile(name: str) -> CompetitorProfile:
    ref = [EvidenceRef(evidence_id="e1", quote="公开资料")]
    return CompetitorProfile(
        name=name,
        pricing=PricingModel(model_type="tiered",
                             tiers=[PricingTier(name="企业版", price="询价", billing_cycle="annual")],
                             evidence_refs=ref),
        swot=SWOT(strengths=[SWOTPoint(text="生态完整", evidence_refs=ref)]),
    )


_ANALYSIS = CompetitorAnalysis(
    competitors=[_profile(c) for c in ("飞书", "钉钉", "企业微信")],
    comparison=[
        ComparisonRow(dimension=d, cells=[
            ComparisonCell(competitor=c, value_type="enum", value="tiered",
                           evidence_refs=[EvidenceRef(evidence_id="e1", quote="公开资料")])
            for c in ("飞书", "钉钉", "企业微信")])
        for d in ("pricing", "deployment", "integrations")],
)


def main() -> None:
    client = config.get_doubao_client()
    model = config.doubao_model()
    body = render_body(_ANALYSIS, _EV, as_of="2026-06-01")
    print(f"=== body size: {len(body)} chars ===")

    # Step 1:流式草稿(测 typing 可行性)。emit 计数 + 计时。
    chunks = {"n": 0}
    t0 = time.monotonic()
    t_first = {"v": None}

    def emit(ev_type: str, data: dict) -> None:
        if ev_type == "chunk" and data.get("delta"):
            chunks["n"] += 1
            if t_first["v"] is None:
                t_first["v"] = time.monotonic() - t0

    draft_msgs = [{"role": "user", "content":
        "你是竞品战略分析师。基于下面的对比正文,写一段三部分的自由文本草稿:"
        "①市场格局 ②战略路径分歧 ③短/中/长期可执行建议。只写散文,不要 JSON。\n\n" + body}]
    draft = stream_chat(draft_msgs, client=client, model=model, emit=emit,
                        agent_id="writer", step="drafting")
    t_stream = time.monotonic() - t0
    print(f"=== stream: {chunks['n']} chunks | TTFB {t_first['v']}s | total {t_stream:.1f}s "
          f"| draft {len(draft)} chars ===")
    assert chunks["n"] > 5, "stream 没有真流 delta(chunks 太少)→ 两步化不可行,Plan B 回落一次性"

    # Step 2:把草稿抽成结构化 ReportInsight(契约不破)。
    t1 = time.monotonic()
    insight = generate_insight(draft, client=client, model=model)
    print(f"=== extract: {time.monotonic() - t1:.1f}s ===")
    assert insight.market_context and insight.differentiation_thesis and insight.actionable_takeaway, \
        "两步抽取产物字段缺失 → 两步化不忠实"
    print("=== ReportInsight (head) ===")
    print(f"market_context: {insight.market_context[:120]}")
    print(f"differentiation_thesis: {insight.differentiation_thesis[:120]}")
    print(f"actionable_takeaway: {insight.actionable_takeaway[:120]}")
    print("SPIKE OK: stream_chat 真流 + 两步抽取产出合法 ReportInsight")


if __name__ == "__main__":
    main()
