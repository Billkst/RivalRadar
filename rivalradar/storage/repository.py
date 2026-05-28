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
        "degraded": bool(row["degraded"]),
        "created_at": row["created_at"],
    }


def update_run_status(conn: sqlite3.Connection, run_id: str, status: str) -> None:
    conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
    conn.commit()


def mark_run_failed(conn: sqlite3.Connection, run_id: str) -> bool:
    """把 'running' 状态的 run 标 'failed'(CAS 防覆盖已 finalize 的状态)。

    场景:SSE graph 主流 except 分支调此函数标 failed,但若 finalize 节点已
    update_run_status(done) 成功后,后续步骤(update_run_degraded 等)又抛,
    sse.py except 不应该把 'done' 覆盖成 'failed' — 否则前端拒绝渲染已存好的报告。
    返回 True if 真的改了一行(原 status='running'),False 表示已是终态没动。

    Reviewer 揪到的 ship round-2 race(adversarial 9/10:fix made it worse)。
    """
    cursor = conn.execute(
        "UPDATE runs SET status='failed' WHERE run_id=? AND status='running'",
        (run_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def mark_run_cancelled(conn: sqlite3.Connection, run_id: str) -> bool:
    """把 'running' 状态的 run 标 'cancelled'(CAS 同 mark_run_failed,F4 修订)。

    场景:user POST /run/:id/cancel,backend task.cancel() 中断 in-flight LLM 同时
    此函数持久化 status='cancelled' — 后续 GET /run/:id / GET /stream/:id 返回
    cancelled 让前端切 cancelled UI(也供 partial 状态聚合用)。

    CAS 防覆盖:已 finalize 到 done / insufficient_evidence / failed 的 run 不被
    cancelled 覆盖(timing race:user 点 cancel 时 run 刚好 finalize 完;CAS 只
    在 status='running' 时更新)。
    """
    cursor = conn.execute(
        "UPDATE runs SET status='cancelled' WHERE run_id=? AND status='running'",
        (run_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def mark_run_finalized(conn: sqlite3.Connection, run_id: str, status: str) -> bool:
    """finalize_node 用 CAS 写终态(post-ship review:对称 mark_run_failed/cancelled
    的窄窗 race 保护)。

    场景:user 点 cancel 进入 mark_run_cancelled CAS 成功(status='cancelled'),
    但 task.cancel() 在 LangGraph 节点边界才能落地;若 cancel 恰好在 finalize 节点
    sync 执行的 ~50ms 内到达,CancelledError 不能 preempt sync code,finalize 跑完
    用非 CAS update_run_status('done') 把 'cancelled' 覆盖 → DB 状态损坏(user UI
    显示已停止,GET /run 看到 done)。

    用 CAS 守 expected='running' 阻止 finalize 覆盖任何已 finalize 状态。
    """
    cursor = conn.execute(
        "UPDATE runs SET status=? WHERE run_id=? AND status='running'",
        (status, run_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def update_run_degraded(conn: sqlite3.Connection, run_id: str, degraded: bool) -> None:
    """持久化「蕴含降级」标志(Lane D state["degraded"] → 落 SQLite,spec §11.5 横幅依赖)。"""
    conn.execute("UPDATE runs SET degraded=? WHERE run_id=?",
                 (1 if degraded else 0, run_id))
    conn.commit()


# ---- evidence ----
def insert_evidence(conn: sqlite3.Connection, run_id: str, ev: Evidence) -> None:
    # OR IGNORE:同 run 内重复 (id) 被 reducer 防过,这里是双保险防止意外
    # IntegrityError 让 SSE 流崩(Codex 实测:重跑同 competitor+dim+url 会触发)
    conn.execute(
        "INSERT OR IGNORE INTO evidence (id, run_id, competitor, dimension, content, "
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
            "degraded": bool(r["degraded"]),
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
