from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    competitors TEXT NOT NULL,
    dimensions  TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    competitor   TEXT NOT NULL,
    dimension    TEXT NOT NULL,
    content      TEXT NOT NULL,
    source_url   TEXT NOT NULL,
    source_title TEXT NOT NULL,
    language     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
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


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
