from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver


def make_checkpointer(path: str) -> SqliteSaver:
    """建一个长驻的 SqliteSaver(打回重跑可恢复,spec §10)。

    持久化场景不用 from_conn_string 上下文管理器(那会随 with 结束关连接),
    而是直接把一个 check_same_thread=False 的连接交给 SqliteSaver,再 setup() 建表。
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver
