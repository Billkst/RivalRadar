from rivalradar.storage.db import connect, init_db


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
