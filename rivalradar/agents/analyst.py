from __future__ import annotations

from pydantic import BaseModel, Field

from rivalradar.llm.structured import structured_call
from rivalradar.schema.models import (
    ComparisonRow, CompetitorAnalysis, CompetitorProfile, CONTROLLED_DIMENSIONS,
    Evidence, FeatureItem, PricingModel, SWOT, UserPersona,
)


# structured_call 返回单个 BaseModel;抽取 list 用 wrapper 模型
class FeatureExtraction(BaseModel):
    items: list[FeatureItem] = Field(default_factory=list)


class PersonaExtraction(BaseModel):
    personas: list[UserPersona] = Field(default_factory=list)


class ComparisonExtraction(BaseModel):
    rows: list[ComparisonRow] = Field(default_factory=list)


def evidence_for(
    evidence: list[Evidence], competitor: str, *, dimension: str | None = None
) -> list[Evidence]:
    """过滤出某竞品(可选某维度)的证据,缩小喂给 LLM 的上下文。"""
    return [
        e for e in evidence
        if e.competitor == competitor and (dimension is None or e.dimension == dimension)
    ]


def build_evidence_block(evidence: list[Evidence]) -> str:
    """把证据编号成清单注入 prompt,标出 evidence_id 供模型在 evidence_refs 里引用。"""
    lines = []
    for e in evidence:
        snippet = (e.content or "")[:1200]
        lines.append(f"[evidence_id={e.id}] ({e.source_title} | {e.source_url})\n{snippet}")
    return "\n\n".join(lines)


_REFS_RULE = (
    "只依据下面证据作答,不得编造。每条结论必须挂 evidence_refs,其中 evidence_id "
    "只能取自给定证据的 evidence_id,quote 为被引的原句。无证据支撑的结论不要输出。"
)


def extract_features(evidence: list[Evidence], competitor: str, *, client, model) -> list[FeatureItem]:
    """从证据抽取竞品功能项,每条挂 evidence_refs。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。抽取其功能项(用 parent_id 表父子层级,"
             f"category 取功能类别)。\n\n证据:\n{block}"}]
    return structured_call(FeatureExtraction, msgs, client=client, model=model).items


def extract_pricing(evidence: list[Evidence], competitor: str, *, client, model) -> PricingModel:
    """从证据抽取竞品定价模型。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。抽取其定价模型(model_type 与各 tier)。\n\n证据:\n{block}"}]
    return structured_call(PricingModel, msgs, client=client, model=model)


def extract_personas(evidence: list[Evidence], competitor: str, *, client, model) -> list[UserPersona]:
    """从证据抽取竞品用户画像。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。从公开用户评价抽取用户画像(segment/needs/"
             f"pain_points/praise)。\n\n证据:\n{block}"}]
    return structured_call(PersonaExtraction, msgs, client=client, model=model).personas


def extract_swot(evidence: list[Evidence], competitor: str, *, client, model) -> SWOT:
    """从证据抽取竞品 SWOT(每点挂 evidence_refs)。"""
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n竞品:{competitor}。基于证据给出 SWOT(每点挂 evidence_refs)。\n\n证据:\n{block}"}]
    return structured_call(SWOT, msgs, client=client, model=model)


def analyze_competitor(evidence: list[Evidence], competitor: str, *, client, model) -> CompetitorProfile:
    """对单个竞品做四项抽取并拼成 CompetitorProfile。"""
    ev = evidence_for(evidence, competitor)  # 已按竞品过滤;下面按维度取子集,缺则回退全量
    feat_ev = evidence_for(ev, competitor, dimension="core_workflows") or ev
    price_ev = evidence_for(ev, competitor, dimension="pricing") or ev
    pers_ev = evidence_for(ev, competitor, dimension="review_sentiment") or ev
    return CompetitorProfile(
        name=competitor,
        features=extract_features(feat_ev, competitor, client=client, model=model),
        pricing=extract_pricing(price_ev, competitor, client=client, model=model),
        personas=extract_personas(pers_ev, competitor, client=client, model=model),
        swot=extract_swot(ev, competitor, client=client, model=model),
    )


def build_comparison(profiles: list[CompetitorProfile], evidence: list[Evidence], *, client, model) -> list[ComparisonRow]:
    """收尾产出跨竞品对比(受控本体 + 类型化值 + evidence_refs,spec D5 / §6)。"""
    names = ", ".join(p.name for p in profiles)
    dims = ", ".join(CONTROLLED_DIMENSIONS)
    block = build_evidence_block(evidence)
    msgs = [{"role": "user", "content":
             f"{_REFS_RULE}\n\n对竞品 [{names}] 在这些维度做横向对比:{dims}。"
             f"每个 cell 标 value_type(bool/enum/number/quote_text)与 value,并挂 evidence_refs。"
             f"\n\n证据:\n{block}"}]
    return structured_call(ComparisonExtraction, msgs, client=client, model=model).rows


def analyze(evidence: list[Evidence], competitors: list[str], *, client, model) -> CompetitorAnalysis:
    """分析 Agent 入口:证据 → 结构化分析(逐竞品 profile + 跨竞品对比)。"""
    profiles = [analyze_competitor(evidence, c, client=client, model=model) for c in competitors]
    comparison = build_comparison(profiles, evidence, client=client, model=model)
    return CompetitorAnalysis(competitors=profiles, comparison=comparison)
