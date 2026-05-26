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
    assert {"runs", "evidence", "analysis", "report", "trace"} <= names


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
