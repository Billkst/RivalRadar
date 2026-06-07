import sqlite3

from rivalradar.storage.db import connect, init_db


def _conn() -> sqlite3.Connection:
    c = connect(":memory:")
    init_db(c)
    return c


def test_queries_table_exists():
    conn = _conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(queries)").fetchall()}
    assert {"run_id", "competitor", "dimension", "language",
            "query_text", "round", "hit_count", "created_at"} <= cols
