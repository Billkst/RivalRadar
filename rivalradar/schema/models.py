from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Language = Literal["zh", "en"]
SupportVerdict = Literal["supported", "partial", "unsupported"]
ValueType = Literal["bool", "enum", "number", "quote_text"]
ProblemType = Literal[
    "missing_evidence", "schema_incomplete", "hallucination", "low_coverage"
]
QCVerdict = Literal["pass", "retry_collect", "retry_analyze", "insufficient_evidence"]

# 受控本体(spec §6 / Codex #3):对比维度只在这几个轴上展开,避免语义漂移
CONTROLLED_DIMENSIONS: tuple[str, ...] = (
    "pricing",
    "deployment",
    "integrations",
    "target_users",
    "core_workflows",
    "review_sentiment",
)


class Evidence(BaseModel):
    """证据块(采集产出)。"""

    id: str
    competitor: str
    dimension: str
    content: str
    source_url: str
    source_title: str
    language: Language
    fetched_at: str  # ISO 8601


class EvidenceRef(BaseModel):
    """句级引用:结论 → 证据的最小单元(spec §6 / Codex #2)。"""

    evidence_id: str
    quote: str
    start: Optional[int] = None
    end: Optional[int] = None
    support_verdict: SupportVerdict = "supported"


class FeatureItem(BaseModel):
    """功能项(扁平邻接表,parent_id 表达层级,D11)。"""

    id: str
    name: str
    description: str
    category: str
    parent_id: Optional[str] = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class PricingTier(BaseModel):
    name: str
    price: str
    billing_cycle: str
    features_included: list[str] = Field(default_factory=list)
    limits: str = ""


class PricingModel(BaseModel):
    model_type: str
    tiers: list[PricingTier] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class UserPersona(BaseModel):
    segment: str
    needs: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    praise: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SWOTPoint(BaseModel):
    text: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SWOT(BaseModel):
    strengths: list[SWOTPoint] = Field(default_factory=list)
    weaknesses: list[SWOTPoint] = Field(default_factory=list)
    opportunities: list[SWOTPoint] = Field(default_factory=list)
    threats: list[SWOTPoint] = Field(default_factory=list)


class CompetitorProfile(BaseModel):
    name: str
    features: list[FeatureItem] = Field(default_factory=list)
    pricing: PricingModel
    personas: list[UserPersona] = Field(default_factory=list)
    swot: SWOT


class ComparisonCell(BaseModel):
    """类型化对比值,避免鸡同鸭比(spec §6 / Codex #3)。value 一律存字符串,由 value_type 决定解读。"""

    competitor: str
    value_type: ValueType
    value: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    dimension: str  # 受控本体之一
    cells: list[ComparisonCell] = Field(default_factory=list)


class CompetitorAnalysis(BaseModel):
    competitors: list[CompetitorProfile] = Field(default_factory=list)
    comparison: list[ComparisonRow] = Field(default_factory=list)


class QCIssue(BaseModel):
    competitor: str
    dimension: str
    problem_type: ProblemType
    detail: str


class QCResult(BaseModel):
    verdict: QCVerdict
    issues: list[QCIssue] = Field(default_factory=list)


# ── Decision pipeline(full-C / D7 全扩展,Epic 2.1)─────────────────────────
# 术语锁定:stance 自解释标签,取代旧稿 下注/防守/观察。backend enum、frontend
# TS mirror、UI 用同一字面值,不加中间映射层(design-review 设计系统对齐 critical)。
Stance = Literal["建议采用", "需要警惕", "持续观察"]
Horizon = Literal["短期", "中期", "长期"]
Reversibility = Literal["可逆", "不可逆"]
RiskCost = Literal["低", "中", "高"]


class Watch(BaseModel):
    """`持续观察` 决策的监控触发器:盯什么指标、阈值多少、越线做什么。

    存在意义 = 反套话:一条没有可监控指标的"持续观察"就是"保持关注"型空话,
    schema 层强制三字段齐备,缺则拒绝(见 Decision._watch_required_for_observe)。
    """

    metric: str
    threshold: str
    trigger: str


class Decision(BaseModel):
    """单条决策建议(D7 全扩展)。

    - stance:自解释立场标签(建议采用/需要警惕/持续观察)。
    - action:命令式动作句(告诉 PM 下一步具体做什么,不是"评估"类 hedge)。
    - horizon:行动时间窗(短/中/长期)。
    - risk_reversibility / risk_cost:决策**后果**(可逆性 / 成本)——与证据支持度
      (EvidenceRef.support_verdict)是两个正交维度,勿混。
    - why:为什么这么判断的 reasoning。
    - evidence_refs:句级溯源(每条决策必须挂证据,QC 校验)。
    - watch:仅 stance=持续观察 时 REQUIRED(否则 None);防套话强约束。
    """

    stance: Stance
    action: str
    horizon: Horizon
    risk_reversibility: Reversibility
    risk_cost: RiskCost
    why: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    watch: Optional[Watch] = None

    @model_validator(mode="after")
    def _watch_required_for_observe(self) -> "Decision":
        if self.stance == "持续观察":
            w = self.watch
            if w is None or not (w.metric.strip() and w.threshold.strip() and w.trigger.strip()):
                raise ValueError(
                    "stance=持续观察 必须提供完整 watch{metric, threshold, trigger}"
                )
        return self


class DecisionSet(BaseModel):
    """决策集合 —— LLM function-calling 产出的顶层对象(structured_call 需 BaseModel,
    list[Decision] 不是 BaseModel 无法作 tool parameters)。"""

    decisions: list[Decision] = Field(default_factory=list)
