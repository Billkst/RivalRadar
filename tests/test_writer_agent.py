import json
from types import SimpleNamespace

from rivalradar.agents.writer import (
    _fmt_refs, render_competitor, render_comparison, render_sources, render_body,
    ReportInsight, generate_insight, write_report, generate_decisions, PLATITUDE_TERMS,
)
from rivalradar.schema.models import DecisionSet
from rivalradar.schema.models import (
    CompetitorProfile, FeatureItem, PricingModel, PricingTier,
    UserPersona, SWOT, SWOTPoint, EvidenceRef,
    CompetitorAnalysis, ComparisonRow, ComparisonCell, Evidence,
)


def _ref(eid):
    return EvidenceRef(evidence_id=eid, quote="q")


def test_fmt_refs_joins_ids_in_brackets():
    assert _fmt_refs([_ref("e1"), _ref("e2")]) == " [e1, e2]"
    assert _fmt_refs([]) == ""


def test_render_competitor_includes_facts_and_inline_citations():
    prof = CompetitorProfile(
        name="Notion",
        features=[
            FeatureItem(id="f1", name="数据库", description="多视图", category="core_workflows",
                        evidence_refs=[_ref("e1")]),
            FeatureItem(id="f2", name="表格视图", description="", category="core_workflows",
                        parent_id="f1", evidence_refs=[_ref("e2")]),
        ],
        pricing=PricingModel(model_type="freemium",
                             tiers=[PricingTier(name="Free", price="$0", billing_cycle="monthly")],
                             evidence_refs=[_ref("e3")]),
        personas=[UserPersona(segment="团队", needs=["协作"], evidence_refs=[_ref("e4")])],
        swot=SWOT(strengths=[SWOTPoint(text="生态强", evidence_refs=[_ref("e5")])]),
    )
    md = render_competitor(prof)
    assert "## Notion" in md
    assert "数据库" in md and "[e1]" in md
    assert "表格视图" in md and "[e2]" in md       # 子功能也渲染
    assert "freemium" in md and "[e3]" in md
    assert "Free" in md
    assert "团队" in md and "[e4]" in md
    assert "生态强" in md and "[e5]" in md


def test_render_competitor_handles_empty_sections():
    prof = CompetitorProfile(name="空", pricing=PricingModel(model_type="unknown"), swot=SWOT())
    md = render_competitor(prof)
    assert "## 空" in md
    assert "_(无)_" in md  # 空功能/定价/画像不崩


def _ev(eid):
    return Evidence(id=eid, competitor="Notion", dimension="pricing", content="c",
                    source_url="https://notion.so/pricing", source_title="Pricing",
                    language="en", fetched_at="2026-05-25T00:00:00Z")


def test_render_comparison_table_has_competitor_columns_and_refs():
    rows = [ComparisonRow(dimension="pricing", cells=[
        ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                       evidence_refs=[_ref("e3")]),
        ComparisonCell(competitor="飞书", value_type="enum", value="freemium"),
    ])]
    md = render_comparison(rows, ["Notion", "飞书"])
    assert "| 维度 | Notion | 飞书 |" in md
    assert "pricing" in md and "freemium" in md and "[e3]" in md


def test_render_comparison_empty():
    assert "无对比数据" in render_comparison([], ["Notion"])


def test_render_sources_resolves_and_marks_missing():
    analysis = CompetitorAnalysis(
        competitors=[],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                           evidence_refs=[_ref("e3"), _ref("e_missing")])])],
    )
    md = render_sources(analysis, [_ev("e3")])
    assert "[e3]" in md and "Pricing" in md and "notion.so/pricing" in md
    assert "as of 2026-05-25T00:00:00Z" in md
    assert "e_missing" in md and "missing" in md  # 不在证据集 → 标 missing


def test_render_body_stamps_as_of_and_preserves_all_cited_ids():
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(
            name="Notion",
            features=[FeatureItem(id="f1", name="数据库", description="", category="core_workflows",
                                  evidence_refs=[_ref("e1")])],
            pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e3")]),
            swot=SWOT(),
        )],
        comparison=[ComparisonRow(dimension="pricing", cells=[
            ComparisonCell(competitor="Notion", value_type="enum", value="freemium",
                           evidence_refs=[_ref("e3")])])],
    )
    body = render_body(analysis, [_ev("e1"), _ev("e3")], as_of="2026-05-25")
    assert "as of 2026-05-25" in body
    # 引用忠实度:analysis 里每个被引 id 都出现在正文
    for eid in ("e1", "e3"):
        assert f"[{eid}]" in body or f"[{eid}," in body or f", {eid}]" in body


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


def test_generate_insight_returns_three_fields():
    """post-rubric-v1 重构:summary 单段 → insight 3 段(market/thesis/takeaway)。"""
    payload = json.dumps({
        "market_context": "中国企业级 SaaS 协同办公赛道格局。",
        "differentiation_thesis": "飞书走互联网协作工具路径,因为 X,所以 Y。",
        "actionable_takeaway": "短期:做 X。中期:看 Y。长期:Z 会变。",
    })
    client = _FakeClient([payload])
    insight = generate_insight("正文……", client=client, model="m")
    assert isinstance(insight, ReportInsight)
    assert "赛道" in insight.market_context
    assert "因为" in insight.differentiation_thesis and "所以" in insight.differentiation_thesis
    assert "短期" in insight.actionable_takeaway
    assert client.chat.completions.calls == 1  # 单次 LLM 调用(预算锁)


def test_write_report_combines_insight_and_deterministic_body():
    analysis = CompetitorAnalysis(
        competitors=[CompetitorProfile(
            name="Notion",
            pricing=PricingModel(model_type="freemium", evidence_refs=[_ref("e3")]),
            swot=SWOT())],
        comparison=[],
    )
    payload = json.dumps({
        "market_context": "Notion 在 productivity 类工具赛道。",
        "differentiation_thesis": "Notion 走 all-in-one 路径,因为 schema-flex,所以个人 + 团队都可用。",
        "actionable_takeaway": "短期:做模板。中期:看 AI 集成。长期:格局往垂直分化。",
    })
    client = _FakeClient([payload])
    report = write_report(analysis, [_ev("e3")], as_of="2026-05-25", client=client, model="m")
    assert report.startswith("# 竞品分析报告")
    # 3 段执行洞察都在
    assert "## 执行洞察" in report
    assert "### 市场格局" in report
    assert "### 战略路径分歧" in report
    assert "### 给企业产品团队的 takeaway" in report
    assert "Notion 在 productivity" in report
    assert "Notion 走 all-in-one" in report
    assert "短期:做模板" in report
    # 确定性正文未受影响
    assert "## Notion" in report
    assert "[e3]" in report
    assert "as of 2026-05-25" in report


# ── generate_decisions(Epic 2.2)────────────────────────────────────────────
class _CaptureCompletions:
    """记录最后一次 create 的 kwargs,用于断言 prompt 语气分支。"""
    def __init__(self, payload):
        self.payload = payload; self.calls = 0; self.last_kwargs = None
    def create(self, **kwargs):
        self.calls += 1; self.last_kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=self.payload))]))],
            usage=SimpleNamespace(total_tokens=10))


class _CaptureClient:
    def __init__(self, payload):
        self.chat = SimpleNamespace(completions=_CaptureCompletions(payload))


_DEC_PAYLOAD = json.dumps({"decisions": [{
    "stance": "建议采用", "action": "本周评估飞书审批接入", "horizon": "短期",
    "risk_reversibility": "可逆", "risk_cost": "低", "why": "飞书审批生态成熟",
    "evidence_refs": [{"evidence_id": "e3", "quote": "审批模块上线"}], "watch": None,
}]})


def test_generate_decisions_returns_decision_set_single_call():
    client = _CaptureClient(_DEC_PAYLOAD)
    ds = generate_decisions("正文…[来源] [e3]", "选型PM:要不要采购飞书",
                            client=client, model="m")
    assert isinstance(ds, DecisionSet)
    assert ds.decisions[0].action == "本周评估飞书审批接入"
    assert client.chat.completions.calls == 1  # 单次 LLM 调用(成本锁)


def test_generate_decisions_specific_context_uses_imperative_framing():
    client = _CaptureClient(_DEC_PAYLOAD)
    generate_decisions("正文", "选型PM:要不要采购飞书", client=client, model="m")
    prompt = client.chat.completions.last_kwargs["messages"][0]["content"]
    assert "选型PM:要不要采购飞书" in prompt
    assert "命令式" in prompt


def test_generate_decisions_generic_context_converges_to_market_observation():
    """D8:无处境(通用浏览)→ prompt 收敛为「市场观察」语气 + 标通用判断。"""
    client = _CaptureClient(_DEC_PAYLOAD)
    generate_decisions("正文", "", client=client, model="m")
    prompt = client.chat.completions.last_kwargs["messages"][0]["content"]
    assert "市场观察" in prompt and "通用判断" in prompt


def test_generate_decisions_prompt_bans_platitudes():
    client = _CaptureClient(_DEC_PAYLOAD)
    generate_decisions("正文", None, client=client, model="m")
    prompt = client.chat.completions.last_kwargs["messages"][0]["content"]
    assert "持续关注" in prompt  # 黑名单词出现在「严禁」约束里
    assert all(term in PLATITUDE_TERMS for term in ("持续关注", "深入研究"))
