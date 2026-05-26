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
    """老 db 自适应迁移:CREATE TABLE IF NOT EXISTS 不会对既有表加列/改 PK,需独立 ALTER。

    本项目无 alembic;两类迁移:
    1. runs.degraded 列(Lane E 蕴含降级标志,spec §11.5 横幅用)— ALTER 加列
    2. evidence 表 PK:旧 (id) → 新 (run_id, id)(ship round-2 修 Codex 实测复现的
       collision)。SQLite 不支持改 PK,必须 CREATE-COPY-DROP-RENAME 重建表。
       关键:不做这步,旧 dev db 跑新代码会让 INSERT OR IGNORE 静默丢 evidence,
       analyze node 拿到空证据 → 报 insufficient_evidence(reviewer 实测复现 +
       confirmation:critical pass 自核 + security + adversarial 三方 confirmed)。
    """
    runs_cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "degraded" not in runs_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN degraded INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    # evidence PK 迁移:检测旧单列 PK,重建表
    ev_pk = [row[1] for row in conn.execute("PRAGMA table_info(evidence)").fetchall()
             if row[5] > 0]  # row[5] = pk index (0 = not PK, 1+ = PK column order)
    if ev_pk == ["id"]:
        # 旧 schema 单列 PK,rebuild 表保留数据
        conn.execute("ALTER TABLE evidence RENAME TO _evidence_old")
        conn.executescript("""
            CREATE TABLE evidence (
                id           TEXT NOT NULL,
                run_id       TEXT NOT NULL,
                competitor   TEXT NOT NULL,
                dimension    TEXT NOT NULL,
                content      TEXT NOT NULL,
                source_url   TEXT NOT NULL,
                source_title TEXT NOT NULL,
                language     TEXT NOT NULL,
                fetched_at   TEXT NOT NULL,
                PRIMARY KEY (run_id, id)
            );
        """)
        conn.execute(
            "INSERT OR IGNORE INTO evidence "
            "SELECT id, run_id, competitor, dimension, content, "
            "source_url, source_title, language, fetched_at FROM _evidence_old"
        )
        conn.execute("DROP TABLE _evidence_old")
        # 重建 evidence run_id 索引(被 DROP 一起带走了)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id)")
        conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    conn.commit()
