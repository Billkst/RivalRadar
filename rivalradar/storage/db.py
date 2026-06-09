from __future__ import annotations

import os
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
-- full-C 决策管道持久化(Epic 2.4)。新表靠 CREATE IF NOT EXISTS 在 init_db
-- 自动建(老 db 也建,老 run 无行 → GET 优雅 404 = 天然 null 态,无需 ALTER)。
CREATE TABLE IF NOT EXISTS decisions (
    run_id     TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS qc_result (
    run_id     TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS insight (
    run_id     TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- 真实查询词(Plan A:研究员检索台「看得见的活儿」)。CREATE IF NOT EXISTS 自动
-- 在 init_db 建(老 db 也建,老 run 无行 → 天然空态);round=retry 轮次(0=首轮)。
CREATE TABLE IF NOT EXISTS queries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    competitor  TEXT NOT NULL,
    dimension   TEXT NOT NULL,
    language    TEXT NOT NULL,
    query_text  TEXT NOT NULL,
    round       INTEGER NOT NULL DEFAULT 0,
    hit_count   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
-- 策展剔除清单(Plan B:support_verdict 真算后被丢弃的 cell/decision)。结构化列(codex #5,
-- 不拼接 label)供 replay/刷新还原矩阵「—」与 StatusBar 红○计数(spec §7.3);scope=cell|decision。
-- 写入用 REPLACE per (run_id, scope) 语义(codex #2:qc 多轮重试每轮覆盖,绝不留幽灵剔除)。
CREATE TABLE IF NOT EXISTS curation_drops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    scope       TEXT NOT NULL,
    competitor  TEXT NOT NULL DEFAULT '',
    dimension   TEXT NOT NULL DEFAULT '',
    detail      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
-- agent 技能持久化(Plan C:run 无关的 agent 配置,spec §6.3/§7.3)。
-- CREATE IF NOT EXISTS 自动在 init_db 建;PK (agent_id, skill_id) 让 upsert 幂等覆盖。
CREATE TABLE IF NOT EXISTS agent_skills (
    agent_id     TEXT NOT NULL,
    skill_id     TEXT NOT NULL,
    version      TEXT NOT NULL DEFAULT 'v1',
    enabled      INTEGER NOT NULL DEFAULT 1,
    installed_at TEXT NOT NULL,
    PRIMARY KEY (agent_id, skill_id)
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
CREATE INDEX IF NOT EXISTS idx_queries_run ON queries(run_id);
CREATE INDEX IF NOT EXISTS idx_curation_drops_run ON curation_drops(run_id);
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


# Postgres 版 schema(仅 DATABASE_URL=postgres:// 时用,如 Supabase)。与 SQLite 版差异:
#   - AUTOINCREMENT → BIGSERIAL(PG 自增主键);
#   - runs 表内联 degraded + decision_context(PG 是全新库,不走 SQLite 的 _ensure_columns
#     在线 ALTER 迁移,故初始 schema 必须含全列);
#   - 布尔仍存 INTEGER 0/1、时间戳/JSON 仍存 TEXT —— 读写代码与 SQLite 完全一致,零分叉。
PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id           TEXT PRIMARY KEY,
    competitors      TEXT NOT NULL,
    dimensions       TEXT NOT NULL,
    status           TEXT NOT NULL,
    degraded         INTEGER NOT NULL DEFAULT 0,
    decision_context TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
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
    PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS analysis (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report (run_id TEXT PRIMARY KEY, markdown TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS qc_result (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS insight (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS queries (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    competitor  TEXT NOT NULL,
    dimension   TEXT NOT NULL,
    language    TEXT NOT NULL,
    query_text  TEXT NOT NULL,
    round       INTEGER NOT NULL DEFAULT 0,
    hit_count   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS curation_drops (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    scope       TEXT NOT NULL,
    competitor  TEXT NOT NULL DEFAULT '',
    dimension   TEXT NOT NULL DEFAULT '',
    detail      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_skills (
    agent_id     TEXT NOT NULL,
    skill_id     TEXT NOT NULL,
    version      TEXT NOT NULL DEFAULT 'v1',
    enabled      INTEGER NOT NULL DEFAULT 1,
    installed_at TEXT NOT NULL,
    PRIMARY KEY (agent_id, skill_id)
);
CREATE TABLE IF NOT EXISTS trace (
    id             BIGSERIAL PRIMARY KEY,
    run_id         TEXT NOT NULL,
    node           TEXT NOT NULL,
    prompt         TEXT,
    input_summary  TEXT,
    output_summary TEXT,
    tokens         INTEGER,
    latency_ms     INTEGER,
    ts             TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS annotations (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    evidence_id     TEXT,
    conclusion_path TEXT,
    note            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_queries_run ON queries(run_id);
CREATE INDEX IF NOT EXISTS idx_curation_drops_run ON curation_drops(run_id);
CREATE INDEX IF NOT EXISTS idx_trace_run ON trace(run_id);
CREATE INDEX IF NOT EXISTS idx_annotations_run ON annotations(run_id);
"""


def _database_url() -> str | None:
    """读 DATABASE_URL;仅当是 postgres:// 连接串时返回(否则 None → 走本地 SQLite)。"""
    url = os.getenv("DATABASE_URL", "").strip()
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        return url
    return None


class _PgConnection:
    """psycopg3 连接的薄封装,让 repository 的 SQLite 风格调用在 Postgres 上原样工作:
      - `?` 占位符 → `%s`(本仓库 SQL 无字面 ? 或 %,纯文本替换安全);
      - conn.execute / executemany / commit / close;
      - 返回 psycopg cursor(rowcount / fetchone / fetchall 与 sqlite 同形)。
    仅 DATABASE_URL=postgres:// 时使用;SQLite 路径不经过这里,行为零变化。
    repository 用 getattr(conn, "dialect", "") == "pg" 识别极少数方言分叉点。"""

    dialect = "pg"

    def __init__(self, raw) -> None:
        self._raw = raw

    @staticmethod
    def _q(sql: str) -> str:
        # 纯文本把 `?` 占位符换 `%s`(psycopg paramstyle)。前提:repository SQL 里
        # 无字面 `?`、无字面 `%`。⚠️ 未来若写 `LIKE '%x%'` 之类,psycopg 会把 `%` 当占位符
        # 解析报错(需转义成 `%%`),而 SQLite 测试抓不到 —— 新增 SQL 务必避开字面 `%`。
        return sql.replace("?", "%s")

    def execute(self, sql: str, params=()):  # noqa: ANN001
        try:
            return self._raw.execute(self._q(sql), params)
        except Exception:
            # PG autocommit=False:失败语句会 abort 整个事务,此后所有语句(含 SELECT 与
            # mark_run_failed)都报 InFailedSqlTransaction 直到 rollback。本仓库每次写都紧跟
            # commit(=单语句事务),故 rollback 只丢弃这条失败语句、不碰已 commit 的数据,
            # 恰好对齐 SQLite「失败语句不污染连接」语义,防 run 卡死 running(/review HIGH#1)。
            # 多语句事务(delete_run / replace_curation_drops)中途失败时,rollback 整条 →
            # 全有或全无的原子性也由此保住。
            self._raw.rollback()
            raise

    def executemany(self, sql: str, seq_of_params):  # noqa: ANN001
        cur = self._raw.cursor()
        try:
            cur.executemany(self._q(sql), list(seq_of_params))
        except Exception:
            self._raw.rollback()  # 同 execute:失败即 rollback,保原子 + 不污染连接
            raise
        return cur

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


def connect(path: str):
    """DATABASE_URL=postgres:// → psycopg3(Supabase 等托管 Postgres);
    否则 → 本地 SQLite(默认;本地开发 + 全部单测零变化、无需安装 psycopg)。"""
    url = _database_url()
    if url is not None:
        import psycopg  # 懒加载:仅 Postgres 部署需要;SQLite/测试不导入
        from psycopg.rows import dict_row

        # prepare_threshold=None 关 server-side prepared statements,兼容 Supabase
        # pgBouncer transaction 模式;dict_row 让 row["col"] / dict(row) 与 sqlite3.Row 同形。
        raw = psycopg.connect(
            url, autocommit=False, row_factory=dict_row, prepare_threshold=None
        )
        return _PgConnection(raw)
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

    仅 SQLite 路径调用;Postgres 是全新库,PG_SCHEMA 已含全列,不需要在线迁移。
    """
    runs_cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "degraded" not in runs_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN degraded INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    # decision_context 列(Epic 2.4 full-C:用户决策处境,decide 节点 grounding 用)。
    # 老 run 默认 '' = 通用浏览语气(向后兼容,无须回填)。
    if "decision_context" not in runs_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN decision_context TEXT NOT NULL DEFAULT ''")
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


def init_db(conn) -> None:  # noqa: ANN001
    """建表(幂等)。Postgres:逐条跑 PG_SCHEMA(psycopg3 单 execute 不支持多语句),
    跳过 WAL pragma 与 SQLite 在线迁移。SQLite:原行为(WAL + executescript + _ensure_columns)。"""
    if getattr(conn, "dialect", "") == "pg":
        for stmt in PG_SCHEMA.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(s)
        conn.commit()
        return
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    conn.commit()
