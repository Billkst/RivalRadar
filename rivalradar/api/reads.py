"""只读端点:evidence / analysis / report / trace(spec §13 测试覆盖 + §11 前端需求)。"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from rivalradar.agents.qc import sanitize_qc_result
from rivalradar.api.deps import get_db_conn
from rivalradar.api.schemas import SanitizedQCResult, TraceEntry
from rivalradar.schema.models import (
    CompetitorAnalysis, DecisionSet, Evidence, ReportInsight,
)
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


# ── full-C 决策管道只读端点(Epic 2.4)。老 run 无对应表行 → 404(天然 null 态)。──
@router.get("/qc/{run_id}", response_model=SanitizedQCResult)
def get_qc(run_id: str,
           conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    """质检结果(**SANITIZED** — Codex #9:公开端点绝不暴露 detail 原文/模型文本/异常)。"""
    qc_result = repo.get_qc_result(conn, run_id)
    if qc_result is None:
        raise HTTPException(404, "qc result not found")
    return sanitize_qc_result(qc_result)


@router.get("/insight/{run_id}", response_model=ReportInsight)
def get_insight(run_id: str,
                conn: sqlite3.Connection = Depends(get_db_conn)) -> ReportInsight:
    insight = repo.get_insight(conn, run_id)
    if insight is None:
        raise HTTPException(404, "insight not found")
    return insight


@router.get("/decisions/{run_id}", response_model=DecisionSet)
def get_decisions(run_id: str,
                  conn: sqlite3.Connection = Depends(get_db_conn)) -> DecisionSet:
    ds = repo.get_decisions(conn, run_id)
    if ds is None:
        raise HTTPException(404, "decisions not found")
    return ds


@router.get("/runs/{run_id}/evidence", response_model=list[Evidence])
def list_run_evidence(run_id: str,
                      conn: sqlite3.Connection = Depends(get_db_conn)) -> list[Evidence]:
    """批量证据列表(Epic 2.4:暴露 repo.list_evidence,前端 evidenceStore 一次性 seed
    防 per-pill N+1)。run 不存在 → 404;run 存在但无证据 → 空列表。"""
    if repo.get_run(conn, run_id) is None:
        raise HTTPException(404, "run not found")
    return repo.list_evidence(conn, run_id)
