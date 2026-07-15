from __future__ import annotations

import os
import sqlite3
import threading

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
-- token 计量三列(成本埋点):tokens 保留为总数(向后兼容既有读方),新增输入/输出拆分
-- 与调用次数。拆分是必须的 —— 成本 = 输入×输入单价 + 输出×输出单价,两者单价不同,
-- 只存总数算不出钱;llm_calls 才能区分「单次贵」与「调用次数多」(二者对应相反的路由决策)。
CREATE TABLE IF NOT EXISTS trace (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    node              TEXT NOT NULL,
    prompt            TEXT,
    input_summary     TEXT,
    output_summary    TEXT,
    tokens            INTEGER,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    llm_calls         INTEGER NOT NULL DEFAULT 0,
    latency_ms        INTEGER,
    ts                TEXT NOT NULL
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
    id                BIGSERIAL PRIMARY KEY,
    run_id            TEXT NOT NULL,
    node              TEXT NOT NULL,
    prompt            TEXT,
    input_summary     TEXT,
    output_summary    TEXT,
    tokens            INTEGER,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    llm_calls         INTEGER NOT NULL DEFAULT 0,
    latency_ms        INTEGER,
    ts                TEXT NOT NULL
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


# Postgres 在线迁移。**原假设已失效**:此前 _ensure_columns 的注释写着「Postgres 是全新库,
# PG_SCHEMA 已含全列,不需要在线迁移」—— 那在 v0.6.1.0 首次建 Supabase 库时成立,但库一旦
# 有了生产数据,`CREATE TABLE IF NOT EXISTS` 对**既有表不加列**,新列不会凭空出现 → 下次部署
# 第一次 INSERT 就 UndefinedColumn 炸。而本地测试全走 SQLite 路径,**没有任何测试会失败**。
# PG 支持 ADD COLUMN IF NOT EXISTS(幂等),故 init_db 每次无条件跑一遍,已存在即空操作。
PG_MIGRATIONS = (
    "ALTER TABLE trace ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE trace ADD COLUMN IF NOT EXISTS completion_tokens INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE trace ADD COLUMN IF NOT EXISTS llm_calls INTEGER NOT NULL DEFAULT 0",
)


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

    3. trace 的 token 计量三列(成本埋点)— ALTER 加列

    仅 SQLite 路径调用。Postgres 的在线迁移见 PG_MIGRATIONS(**两边都要加**:PG 库一旦有
    生产数据,只改 PG_SCHEMA 常量是不生效的)。
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

    # trace token 计量三列。SQLite 不支持 ADD COLUMN IF NOT EXISTS,须先查列。
    # DEFAULT 0 让老 run 的 trace 行读出来是 0 —— 与「本节点确实没调 LLM」(collect/finalize)
    # 的真实 0 语义一致,不需要回填,也不会假装老 run 有成本数据。
    trace_cols = {row[1] for row in conn.execute("PRAGMA table_info(trace)").fetchall()}
    for col in ("prompt_tokens", "completion_tokens", "llm_calls"):
        if col not in trace_cols:
            conn.execute(f"ALTER TABLE trace ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
    conn.commit()


# PG 的 DDL 进程内只跑一次:init_db 被 get_db_conn 每个请求调用,而 Postgres 的
# ALTER TABLE(即使 ADD COLUMN IF NOT EXISTS 是 no-op)也要先拿表的 ACCESS EXCLUSIVE 锁
# —— 每个请求都对 trace(最热的写表)拿排它锁,一旦有长事务(如 SSE 回放的分页 SELECT)
# 持有 ACCESS SHARE,排队的排它锁会把后续所有读写全堵在它身后(锁车队,ship 前评审抓出)。
# 双检锁而非裸布尔:冷启动时前端会并发扇出请求(fetchRuns + healthz),check-then-act
# 无锁会让多个首请求各自跑 DDL —— PG 的并发 CREATE TABLE IF NOT EXISTS 有目录插入竞态,
# 会以 duplicate key(pg_type_typname_nsp_index)炸出瞬时 500(红队)。
# 失败不置位:首次迁移抛异常时下个请求重试。SQLite 无此问题(无服务器锁队列),保持原行为。
_PG_SCHEMA_READY = False
_PG_INIT_LOCK = threading.Lock()


def init_db(conn) -> None:  # noqa: ANN001
    """建表(幂等)。Postgres:逐条跑 PG_SCHEMA(psycopg3 单 execute 不支持多语句),
    跳过 WAL pragma 与 SQLite 在线迁移,且**进程内只跑一次**(见 _PG_SCHEMA_READY)。
    SQLite:原行为(WAL + executescript + _ensure_columns)。"""
    global _PG_SCHEMA_READY
    if getattr(conn, "dialect", "") == "pg":
        if _PG_SCHEMA_READY:
            return
        with _PG_INIT_LOCK:
            if _PG_SCHEMA_READY:   # 双检:等锁期间别的请求可能已完成初始化
                return
            for stmt in PG_SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(s)
            for stmt in PG_MIGRATIONS:  # 既有生产表加列(CREATE TABLE IF NOT EXISTS 管不到)
                conn.execute(stmt)
            conn.commit()
            _PG_SCHEMA_READY = True
        return
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    conn.commit()
