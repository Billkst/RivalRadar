"""Lane E 的 HTTP 边界模型。响应实体复用 rivalradar.schema.models 的 Pydantic 类型,
本文件只定义 API 边界特有的请求/响应/错误形状(避免与领域模型耦合)。
"""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints


# 复用类型别名:per-item 字符串长度上限,放 prompt + DB 都安全
_BoundedStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class RunRequest(BaseModel):
    """POST /run 请求体。

    上限保护(防恶意/误用打爆 LLM + 搜索 API 配额):
    - competitors 最多 5 个(spec §3 "1-5 个竞品")
    - dimensions 最多 6 个(覆盖 CONTROLLED_DIMENSIONS 全集)
    - 每项字符串 1-200 字符(防超长 prompt 注入面 + 空白字符串)
    """
    competitors: list[_BoundedStr] = Field(min_length=1, max_length=5)
    dimensions: list[_BoundedStr] = Field(min_length=1, max_length=6)


class RunSummary(BaseModel):
    """GET /runs 列表项(简版,不含详情)。

    包含 degraded:前端 §11.5 列表页降级横幅依赖它(不是 RunDetail 独占)。
    """
    run_id: str
    competitors: list[str]
    dimensions: list[str]
    status: str  # running / done / insufficient_evidence / degraded / failed
    created_at: str
    degraded: bool = False


class RunDetail(RunSummary):
    """GET /run/:id 详情(degraded 已在 RunSummary,本类暂无额外字段)。"""
    pass


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
