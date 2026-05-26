"""标记质疑桩(spec §11.6 D10,§17 人工质疑率)。

只接收、只写一行 annotations 表,**不**写回 state、**不**重跑、**不**触发任何
图节点 —— 是个纯日志通道,前端拿到 201 即可显示「已记录」toast(§11.5)。
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, status

from rivalradar.api.deps import get_db_conn
from rivalradar.api.schemas import AnnotationCreate, AnnotationOut
from rivalradar.storage import repository as repo

router = APIRouter(tags=["annotations"])


@router.post("/annotations", response_model=AnnotationOut,
             status_code=status.HTTP_201_CREATED)
def post_annotation(
    body: AnnotationCreate,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> dict:
    aid = repo.insert_annotation(
        conn,
        run_id=body.run_id,
        evidence_id=body.evidence_id,
        conclusion_path=body.conclusion_path,
        note=body.note,
    )
    # 回读以获取 created_at(避免重复 _now 计算)
    rows = repo.list_annotations(conn, body.run_id)
    row = next(r for r in rows if r["id"] == aid)
    return row
