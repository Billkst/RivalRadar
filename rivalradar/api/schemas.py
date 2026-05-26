"""Lane E 的 HTTP 边界模型。响应实体复用 rivalradar.schema.models 的 Pydantic 类型,
本文件只定义 API 边界特有的请求/响应/错误形状(避免与领域模型耦合)。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """POST /run 请求体。"""
    competitors: list[str] = Field(min_length=1)
    dimensions: list[str] = Field(min_length=1)


class RunSummary(BaseModel):
    """GET /runs 列表项(简版,不含详情)。"""
    run_id: str
    competitors: list[str]
    dimensions: list[str]
    status: str  # running / done / insufficient_evidence / degraded
    created_at: str


class RunDetail(RunSummary):
    """GET /run/:id 详情(加 degraded 标记;前端按它显示降级横幅 §11.5)。"""
    degraded: bool = False


class AnnotationCreate(BaseModel):
    """POST /annotations 请求体(§11.6 D10 标记质疑桩)。"""
    run_id: str
    evidence_id: Optional[str] = None
    conclusion_path: Optional[str] = None
    note: str = Field(min_length=1)


class AnnotationOut(AnnotationCreate):
    id: int
    created_at: str


class TraceEntry(BaseModel):
    """GET /trace/:run 单条 trace。"""
    id: int
    run_id: str
    node: str
    prompt: str = ""
    input_summary: str = ""
    output_summary: str = ""
    tokens: int = 0
    latency_ms: int = 0
    ts: str


class ErrorOut(BaseModel):
    """404/422 等错误统一形状。"""
    detail: str
