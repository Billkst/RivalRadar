"""Run 触发 + 列表 + 详情 + SSE 流。本 Task 实现列表与详情;POST/Stream 在后续任务。"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from rivalradar.api.deps import get_db_conn
from rivalradar.api.schemas import RunDetail, RunSummary
from rivalradar.storage import repository as repo

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunSummary])
def list_runs(conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    return repo.list_runs(conn)


@router.get("/run/{run_id}", response_model=RunDetail)
def get_run(run_id: str,
            conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    r = repo.get_run(conn, run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    # degraded 状态在 repo 层没单字段,从 status 反推(spec §8 + Lane D 遗留)
    r["degraded"] = (r["status"] == "degraded")
    return r
