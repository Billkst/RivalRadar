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
