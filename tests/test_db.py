import pytest

from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def conn():
    c = connect(":memory:")
    init_db(c)
    return c


def test_init_db_creates_all_tables():
    conn = connect(":memory:")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"runs", "evidence", "analysis", "report", "trace",
            "decisions", "qc_result", "insight"} <= names  # +full-C 3 表(Epic 2.4)


def test_connect_uses_row_factory():
    conn = connect(":memory:")
    init_db(conn)
    conn.execute(
        "INSERT INTO runs (run_id, competitors, dimensions, status, created_at) "
        "VALUES ('r1', '[]', '[]', 'running', '2026-05-25T00:00:00Z')"
    )
    row = conn.execute("SELECT run_id FROM runs WHERE run_id='r1'").fetchone()
    assert row["run_id"] == "r1"  # row_factory=Row 才能按列名取


def test_annotations_table_exists(conn):
    conn.execute(
        "INSERT INTO annotations (run_id, evidence_id, conclusion_path, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("r1", "ev_abc", "competitors[0].swot.strengths[0]", "可疑", "2026-05-26T00:00:00Z"),
    )
    conn.commit()
    row = conn.execute("SELECT note FROM annotations WHERE run_id=?", ("r1",)).fetchone()
    assert row["note"] == "可疑"


def test_wal_mode_enabled(tmp_path):
    from rivalradar.storage.db import connect, init_db
    db = tmp_path / "wal.db"
    c = connect(str(db))
    init_db(c)
    mode = c.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    c.close()


def test_ensure_columns_migrates_evidence_to_composite_pk_from_legacy(tmp_path):
    """/review fix(critical 10/10):reviewer adversarial 实测复现:
    旧 dev db 的 evidence 表是单列 PK (id),新代码 INSERT OR IGNORE 跨 run
    会静默丢 evidence(查不到 → analyze 拿空证据 → 报 insufficient_evidence
    而不是崩)。_ensure_columns 必须 detect 旧 PK + rebuild 表保留数据。"""
    from rivalradar.storage.db import connect, init_db
    db = tmp_path / "legacy_evidence.db"
    c = connect(str(db))
    # 模拟旧 schema:evidence 表单列 PK (id) + 1 行老数据
    c.executescript("""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY, competitors TEXT NOT NULL,
            dimensions TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE evidence (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL, competitor TEXT NOT NULL,
            dimension TEXT NOT NULL, content TEXT NOT NULL, source_url TEXT NOT NULL,
            source_title TEXT NOT NULL, language TEXT NOT NULL, fetched_at TEXT NOT NULL
        );
        INSERT INTO runs VALUES ('r_old', '[]', '[]', 'done', '2026-05-01');
        INSERT INTO evidence VALUES ('ev_old', 'r_old', 'Notion', 'pricing', 'c',
                                     'u', 't', 'en', 't0');
    """)
    c.commit()
    # 验证前提:旧 PK 是单列
    pk_before = [row[1] for row in c.execute("PRAGMA table_info(evidence)").fetchall()
                 if row[5] > 0]
    assert pk_before == ["id"], "test prerequisite: legacy db has single-column PK"

    init_db(c)  # 自适应迁移

    # 验证 PK 已迁移到 (run_id, id)
    pk_after = [row[1] for row in c.execute("PRAGMA table_info(evidence)").fetchall()
                if row[5] > 0]
    assert set(pk_after) == {"run_id", "id"}, f"PK not migrated: {pk_after}"
    # 老数据保留
    row = c.execute("SELECT * FROM evidence WHERE id='ev_old'").fetchone()
    assert row["run_id"] == "r_old"
    assert row["competitor"] == "Notion"
    # 关键:跨 run 同 id 现在能各持一份(不再 IntegrityError 也不再静默丢)
    c.execute(
        "INSERT INTO evidence VALUES ('ev_old', 'r_new', 'Notion', 'pricing', 'c',"
        " 'u', 't', 'en', 't0')"
    )
    c.commit()
    rows = c.execute("SELECT run_id FROM evidence WHERE id='ev_old' "
                     "ORDER BY run_id").fetchall()
    assert [r["run_id"] for r in rows] == ["r_new", "r_old"]
    c.close()


def test_ensure_columns_adds_degraded_to_legacy_runs(tmp_path):
    """老 db(无 degraded 列)init_db 自适应 ALTER 加列,既有数据 default 0。

    本项目无 alembic,Lane E 加 runs.degraded 列要保证既有 rivalradar.db 平滑升级。
    """
    from rivalradar.storage.db import connect, init_db
    db = tmp_path / "legacy.db"
    c = connect(str(db))
    # 模拟老 schema(无 degraded 列)+ 1 行老数据
    c.executescript("""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            competitors TEXT NOT NULL,
            dimensions TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO runs VALUES ('r_old', '[]', '[]', 'done', '2026-05-01');
    """)
    c.commit()
    cols_before = {row[1] for row in c.execute("PRAGMA table_info(runs)").fetchall()}
    assert "degraded" not in cols_before, "test prerequisite: legacy db has no degraded"

    init_db(c)  # 自适应 ALTER

    cols_after = {row[1] for row in c.execute("PRAGMA table_info(runs)").fetchall()}
    assert "degraded" in cols_after
    row = c.execute("SELECT degraded FROM runs WHERE run_id='r_old'").fetchone()
    assert row["degraded"] == 0, "old rows must get default 0"
    c.close()


def test_ensure_columns_adds_decision_context_to_legacy_runs(tmp_path):
    """Epic 2.4:老 db(无 decision_context 列)init_db ALTER 加列,既有数据 default ''。"""
    from rivalradar.storage.db import connect, init_db
    db = tmp_path / "legacy_dc.db"
    c = connect(str(db))
    c.executescript("""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY, competitors TEXT NOT NULL,
            dimensions TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO runs VALUES ('r_old', '[]', '[]', 'done', '2026-05-01');
    """)
    c.commit()
    cols_before = {row[1] for row in c.execute("PRAGMA table_info(runs)").fetchall()}
    assert "decision_context" not in cols_before, "test prerequisite: legacy db has no column"
    init_db(c)
    cols_after = {row[1] for row in c.execute("PRAGMA table_info(runs)").fetchall()}
    assert "decision_context" in cols_after
    row = c.execute("SELECT decision_context FROM runs WHERE run_id='r_old'").fetchone()
    assert row["decision_context"] == "", "old rows must get default ''"
    c.close()


def test_ensure_creates_decision_tables_on_legacy_db(tmp_path):
    """Epic 2.4:老 db 无 decisions/qc_result/insight 表 → init_db 补建;
    老 run 查无行 → repo get 返 None(天然 null 态,GET 据此 404)。"""
    from rivalradar.storage.db import connect, init_db
    from rivalradar.storage import repository as repo
    db = tmp_path / "legacy_tables.db"
    c = connect(str(db))
    c.executescript("""
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY, competitors TEXT NOT NULL,
            dimensions TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO runs VALUES ('r_old', '[]', '[]', 'done', '2026-05-01');
    """)
    c.commit()
    init_db(c)
    names = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"decisions", "qc_result", "insight"} <= names
    assert repo.get_decisions(c, "r_old") is None
    assert repo.get_qc_result(c, "r_old") is None
    assert repo.get_insight(c, "r_old") is None
    c.close()
