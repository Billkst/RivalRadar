from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    competitors TEXT NOT NULL,
    dimensions  TEXT NOT NULL,
    status      TEXT NOT NULL,
    degraded    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id           TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    competitor   TEXT NOT NULL,
    dimension    TEXT NOT NULL,
    content      TEXT NOT NULL,
    source_url   TEXT NOT NULL,
    source_title TEXT NOT NULL,
    language     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL,
    -- 复合 PK:同 (competitor|dim|url) 派生的 id 在多个 run 中各持一份(per-run snapshot)。
    -- Codex 实测:旧 schema (id) 单列 PK + 重跑同 url → IntegrityError 让 SSE 流崩。
    PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS analysis (
    run_id     TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report (
    run_id     TEXT PRIMARY KEY,
    markdown   TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trace (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    node           TEXT NOT NULL,
    prompt         TEXT,
    input_summary  TEXT,
    output_summary TEXT,
    tokens         INTEGER,
    latency_ms     INTEGER,
    ts             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_trace_run ON trace(run_id);
CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    evidence_id     TEXT,
    conclusion_path TEXT,
    note            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_annotations_run ON annotations(run_id);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """老 db 自适应迁移:CREATE TABLE IF NOT EXISTS 不会对既有表加列,需独立 ALTER。

    本项目无 alembic;Lane E 加 runs.degraded 列(蕴含降级标志,spec §11.5 横幅用)
    需向后兼容已有的 rivalradar.db。检查 PRAGMA table_info,缺列就 ALTER。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "degraded" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN degraded INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    conn.commit()
