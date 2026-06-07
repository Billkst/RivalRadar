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


from rivalradar.storage.repository import insert_queries, list_queries


def test_insert_and_list_queries():
    conn = _conn()
    records = [
        {"competitor": "飞书", "dimension": "pricing", "language": "zh",
         "query_text": "飞书 价格 套餐 收费", "round": 0, "hit_count": 3},
        {"competitor": "飞书", "dimension": "pricing", "language": "en",
         "query_text": "飞书 pricing plans cost", "round": 0, "hit_count": 0},
    ]
    insert_queries(conn, "run1", records)
    rows = list_queries(conn, "run1")
    assert len(rows) == 2
    assert rows[0]["query_text"] == "飞书 价格 套餐 收费"
    assert rows[0]["hit_count"] == 3
    assert rows[1]["hit_count"] == 0
    assert list_queries(conn, "missing") == []
