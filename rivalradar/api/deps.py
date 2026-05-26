"""FastAPI 依赖注入(per-request 资源 + 全局工厂)。

每请求一个 SQLite 连接(WAL 模式下并发读 + 单写安全);Doubao client 与
Provider 由 app.state 持有(进程级),通过 Depends 拿到 request.app.state。
"""
from __future__ import annotations

import sqlite3
from typing import Iterator

from fastapi import Request

from rivalradar.storage.db import connect, init_db


def get_db_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """每请求一条连接;请求结束关闭。db_path 由 app.state.db_path 注入。"""
    conn = connect(request.app.state.db_path)
    init_db(conn)  # idempotent;PRAGMA WAL 也在这里施加
    try:
        yield conn
    finally:
        conn.close()


def get_doubao_client(request: Request):
    """复用 app.state 上的 Doubao client(进程内单例)。"""
    return request.app.state.doubao_client


def get_provider(request: Request):
    """复用 app.state 上的搜索 provider。"""
    return request.app.state.provider


def get_as_of(request: Request) -> str:
    return request.app.state.as_of


def get_max_retries(request: Request) -> int:
    return request.app.state.max_retries
