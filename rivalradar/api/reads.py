"""只读端点:evidence / analysis / report / trace(spec §13 测试覆盖 + §11 前端需求)。"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from rivalradar.api.deps import get_db_conn
from rivalradar.api.schemas import TraceEntry
from rivalradar.schema.models import CompetitorAnalysis, Evidence
from rivalradar.storage import repository as repo

router = APIRouter(tags=["reads"])


@router.get("/evidence/{evidence_id}", response_model=Evidence)
def get_evidence(evidence_id: str,
                 conn: sqlite3.Connection = Depends(get_db_conn)) -> Evidence:
    ev = repo.get_evidence(conn, evidence_id)
    if ev is None:
        raise HTTPException(404, "evidence not found")
    return ev


@router.get("/analysis/{run_id}", response_model=CompetitorAnalysis)
def get_analysis(run_id: str,
                 conn: sqlite3.Connection = Depends(get_db_conn)) -> CompetitorAnalysis:
    a = repo.get_analysis(conn, run_id)
    if a is None:
        raise HTTPException(404, "analysis not found")
    return a


@router.get("/report/{run_id}")
def get_report(run_id: str,
               conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    md = repo.get_report(conn, run_id)
    if md is None:
        raise HTTPException(404, "report not found")
    return {"run_id": run_id, "markdown": md}


@router.get("/trace/{run_id}", response_model=list[TraceEntry])
def get_trace(run_id: str,
              conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    # repo.list_trace 已返 dict 列表;Pydantic 自动校验
    return repo.list_trace(conn, run_id)
