"""Lane E 的 HTTP 边界模型。响应实体复用 rivalradar.schema.models 的 Pydantic 类型,
本文件只定义 API 边界特有的请求/响应/错误形状(避免与领域模型耦合)。
"""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

from rivalradar.schema.models import CONTROLLED_DIMENSIONS as _CONTROLLED


# 复用类型别名:per-item 字符串长度上限,放 prompt + DB 都安全
_BoundedStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class RunRequest(BaseModel):
    """POST /run 请求体。

    上限保护(防恶意/误用打爆 LLM + 搜索 API 配额):
    - competitors 最多 5 个(spec §3 "1-5 个竞品")
    - dimensions 最多 len(CONTROLLED_DIMENSIONS)= 6(动态;未来加 dim 自动跟上,
      reviewer 揪到原 hardcoded 6 是 brittle)
    - 每项字符串 1-200 字符(防超长 prompt 注入面 + 空白字符串)
    """
    competitors: list[_BoundedStr] = Field(min_length=1, max_length=5)
    dimensions: list[_BoundedStr] = Field(min_length=1, max_length=len(_CONTROLLED))
    # full-C 用户决策处境(Epic 2.4 backend 接口;Epic 1.2/1.3 前端引导流填充)。
    # optional 默认 ""(老 client / 通用浏览),decide 节点据空/非空切语气(D8)。
    decision_context: str = Field(default="", max_length=500)


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
    """GET /run/:id 详情。decision_context:cockpit 回访时显示用户当初的决策处境。"""
    decision_context: str = ""


class SanitizedQCIssue(BaseModel):
    """GET /qc/:run 的单条问题(sanitized:detail 是罐装文案,无模型文本/异常)。"""
    competitor: str
    dimension: str
    problem_type: str
    detail: str


class SanitizedQCResult(BaseModel):
    """GET /qc/:run 响应(Epic 2.4 / Codex #9 公开端点 sanitized)。"""
    verdict: str
    issues: list[SanitizedQCIssue] = Field(default_factory=list)


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


# ── SSE event v2 schema(plan v3.2 §5 — Epic 0.7)─────────────────────────
# v2 6 类 event:start / node / progress(NEW)/ chunk(NEW)/ error / done。
# start / node / error / done / cancelled 已在 sse.py 直接 yield dict;本节
# 给出 progress + chunk 的 type-safe schema 让 Epic 2 backend agent 发时
# 校验 payload 形状,sse.py forward 时直接 model_dump_json()。
#
# Frontend mirror 在 frontend/src/types/api.ts(Epic 1.7,Day-1 下午加)。


class SSEProgressData(BaseModel):
    """progress event payload — 节点内 step-level 进度(plan v3.2 §5)。

    场景:agent 在一个节点内多步推进("正在搜索 Notion pricing" → "已抽取
    3/7 feature"),评委 5 秒看到 agent 在做什么具体动作。Backend agent 通过
    emit("progress", {...}) yield,sse.py forward 到 SSE 流给前端 LiveFeedPanel。
    """
    agent_id: str                    # AGENTS hardcode id: collector/analyst/writer/qc
    step: str                        # 节点内 step 名:search/extract/write/validate
    summary: str                     # 用户可见 narrative(中文已 i18n):"夜枭正在搜索 Notion"
    metric: dict[str, int] | None = None  # 可选进度 metric:{"current":3,"total":7}
    ts: str                          # ISO8601


class SSEChunkData(BaseModel):
    """chunk event payload — LLM 字符 stream(plan v3.2 §5,reasoning typing 效果)。

    场景:reasoning step / narrative writing 时 LLM stream=True,sse.py forward
    每个 delta chunk 给前端,前端 typingStore(D7 throttle window 50 + 16ms batch
    防爆炸)累积渲染 SpeechBubble + LiveFeedPanel typing 光标动画。

    Forward 不限速,~30-50 chunk/s 是典型 LLM 输出节奏。
    """
    agent_id: str                    # AGENTS hardcode id
    step: str                        # thinking / drafting / reasoning
    delta: str                       # LLM 增量 token(几个字符)
    ts: str                          # ISO8601
