from __future__ import annotations

from pydantic import BaseModel, Field

from rivalradar.schema.models import (
    ComparisonRow, Evidence, FeatureItem, UserPersona,
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
