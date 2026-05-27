"""Run 触发 + 列表 + 详情 + SSE 流。"""
from __future__ import annotations

import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from rivalradar.api.deps import (
    get_db_conn, get_doubao_client, get_provider, get_as_of, get_max_retries,
)
from rivalradar.api.schemas import RunDetail, RunRequest, RunSummary
from rivalradar.api.sse import _ACTIVE_RUN_TASKS, _replay_from_trace, graph_event_stream
from rivalradar.config import doubao_model
from rivalradar.graph.build import build_research_graph
from rivalradar.storage import repository as repo
from rivalradar.storage.repository import create_run
from rivalradar.storage.repository import get_run as _get_run

router = APIRouter(tags=["runs"])


@router.post("/run")
def post_run(
    req: RunRequest,
    conn: sqlite3.Connection = Depends(get_db_conn),
    client=Depends(get_doubao_client),
    provider=Depends(get_provider),
    as_of: str = Depends(get_as_of),
    max_retries: int = Depends(get_max_retries),
) -> EventSourceResponse:
    """触发一次完整调研,SSE 流式回推每节点进度,直到 done/error。"""
    run_id = "run_" + uuid.uuid4().hex[:12]
    create_run(conn, run_id, req.competitors, req.dimensions)
    graph = build_research_graph(
        conn=conn, client=client, model=doubao_model(), provider=provider,
        as_of=as_of, max_retries=max_retries,
    )
    initial = {
        "competitors": req.competitors,
        "dimensions": req.dimensions,
        "evidence": [],
        "retry_count": 0,
    }
    config = {"configurable": {"thread_id": run_id}}
    return EventSourceResponse(
        graph_event_stream(graph, initial, config, run_id, conn=conn),
        ping=15,  # context7 验证的 keep-alive 默认,投影场景必备
    )


@router.get("/stream/{run_id}")
def get_stream(
    run_id: str,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> EventSourceResponse:
    """从 trace 表回放已结束 run 的事件流(§11.4 'Play 回放')。"""
    if _get_run(conn, run_id) is None:
        raise HTTPException(404, "run not found")
    return EventSourceResponse(
        _replay_from_trace(conn, run_id),
        ping=15,
    )


@router.get("/runs", response_model=list[RunSummary])
def list_runs(conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    return repo.list_runs(conn)


@router.get("/run/{run_id}", response_model=RunDetail)
def get_run(run_id: str,
            conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    r = repo.get_run(conn, run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    # degraded:repo.get_run 已返 db 持久化的「蕴含降级」标志,再 OR status==degraded
    # 兼容种数据(只 update_run_status 没经 finalize 的路径,如 fixture 直接造的)
    r["degraded"] = r["degraded"] or r["status"] == "degraded"
    return r


@router.post("/run/{run_id}/cancel")
def cancel_run(
    run_id: str,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> dict:
    """F4 修订:真中断 in-flight LLM stream + 持久化 cancelled 状态。

    实施:
      1. 从 _ACTIVE_RUN_TASKS 查 SSE 生成器 task,call task.cancel() 抛 CancelledError
         到生成器执行栈,顺着 await 链中断 in-flight `await llm.chat.create(...)` /
         `await provider.search(...)`(sqlite flag 只在 step 间生效,无法切网络层 await)
      2. DB CAS `mark_run_cancelled('running' → 'cancelled')`,即使 task 已结束也尝试
         (timing race:user 点 cancel 时 run 刚好 finalize 完;CAS 保证不覆盖终态)
      3. 返回 {run_id, cancelled, db_cancelled} — 前端 F4 mitigation 不等此响应即切 UI
         cancelled state,响应仅作 source of truth 让后续 GET /run/:id 一致

    无需 404:已结束的 run cancel 是 no-op,语义清晰返 cancelled=False / db_cancelled=False。
    """
    task = _ACTIVE_RUN_TASKS.get(run_id)
    cancelled = False
    if task is not None and not task.done():
        task.cancel()
        cancelled = True
    db_cancelled = repo.mark_run_cancelled(conn, run_id)
    return {
        "run_id": run_id,
        "cancelled": cancelled,        # 是否实际 cancel 了 in-flight task
        "db_cancelled": db_cancelled,  # 是否实际写了 cancelled 状态(CAS)
    }
