from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

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
