from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from rivalradar.schema.models import CompetitorAnalysis, Evidence


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- runs ----
def create_run(conn: sqlite3.Connection, run_id: str,
               competitors: list[str], dimensions: list[str]) -> None:
    conn.execute(
        "INSERT INTO runs (run_id, competitors, dimensions, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, json.dumps(competitors), json.dumps(dimensions), "running", _now()),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "competitors": json.loads(row["competitors"]),
        "dimensions": json.loads(row["dimensions"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def update_run_status(conn: sqlite3.Connection, run_id: str, status: str) -> None:
    conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
    conn.commit()


# ---- evidence ----
def insert_evidence(conn: sqlite3.Connection, run_id: str, ev: Evidence) -> None:
    conn.execute(
        "INSERT INTO evidence (id, run_id, competitor, dimension, content, "
        "source_url, source_title, language, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ev.id, run_id, ev.competitor, ev.dimension, ev.content,
         ev.source_url, ev.source_title, ev.language, ev.fetched_at),
    )
    conn.commit()


def get_evidence(conn: sqlite3.Connection, evidence_id: str) -> Evidence | None:
    row = conn.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
    if row is None:
        return None
    return Evidence(
        id=row["id"], competitor=row["competitor"], dimension=row["dimension"],
        content=row["content"], source_url=row["source_url"],
        source_title=row["source_title"], language=row["language"],
        fetched_at=row["fetched_at"],
    )


def list_evidence(conn: sqlite3.Connection, run_id: str) -> list[Evidence]:
    rows = conn.execute("SELECT * FROM evidence WHERE run_id=? ORDER BY rowid", (run_id,))
    return [
        Evidence(
            id=r["id"], competitor=r["competitor"], dimension=r["dimension"],
            content=r["content"], source_url=r["source_url"],
            source_title=r["source_title"], language=r["language"],
            fetched_at=r["fetched_at"],
        )
        for r in rows
    ]


# ---- analysis ----
def save_analysis(conn: sqlite3.Connection, run_id: str,
                  analysis: CompetitorAnalysis) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO analysis (run_id, payload, created_at) VALUES (?, ?, ?)",
        (run_id, analysis.model_dump_json(), _now()),
    )
    conn.commit()


def get_analysis(conn: sqlite3.Connection, run_id: str) -> CompetitorAnalysis | None:
    row = conn.execute("SELECT payload FROM analysis WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return CompetitorAnalysis.model_validate_json(row["payload"])


# ---- report ----
def save_report(conn: sqlite3.Connection, run_id: str, markdown: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO report (run_id, markdown, created_at) VALUES (?, ?, ?)",
        (run_id, markdown, _now()),
    )
    conn.commit()


def get_report(conn: sqlite3.Connection, run_id: str) -> str | None:
    row = conn.execute("SELECT markdown FROM report WHERE run_id=?", (run_id,)).fetchone()
    return row["markdown"] if row else None


# ---- trace ----
def append_trace(conn: sqlite3.Connection, run_id: str, node: str, *,
                 prompt: str = "", input_summary: str = "", output_summary: str = "",
                 tokens: int = 0, latency_ms: int = 0) -> None:
    conn.execute(
        "INSERT INTO trace (run_id, node, prompt, input_summary, output_summary, "
        "tokens, latency_ms, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, node, prompt, input_summary, output_summary, tokens, latency_ms, _now()),
    )
    conn.commit()


def list_trace(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM trace WHERE run_id=? ORDER BY id", (run_id,))
    return [dict(r) for r in rows]


# ---- runs list ----
def list_runs(conn: sqlite3.Connection, *, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [
        {
            "run_id": r["run_id"],
            "competitors": json.loads(r["competitors"]),
            "dimensions": json.loads(r["dimensions"]),
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---- annotations(spec §11.6 D10 桩,§17 人工质疑率)----
def insert_annotation(conn: sqlite3.Connection, *, run_id: str,
                      evidence_id: str | None, conclusion_path: str | None,
                      note: str) -> int:
    cur = conn.execute(
        "INSERT INTO annotations (run_id, evidence_id, conclusion_path, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, evidence_id, conclusion_path, note, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_annotations(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM annotations WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [
        {
            "id": r["id"],
            "run_id": r["run_id"],
            "evidence_id": r["evidence_id"],
            "conclusion_path": r["conclusion_path"],
            "note": r["note"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
