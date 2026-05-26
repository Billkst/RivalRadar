# RivalRadar Lane E: Backend API + SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 FastAPI + sse-starlette 把 RivalRadar 多 Agent 图研究系统暴露成 9 端点后端 API,核心 SSE 实时进度流让前端做出 spec §11.4 的「实时动画 DAG money shot」,兑现评分表 25% 工程可观测大头并解锁 Lane F 前端。

**Architecture:** 单进程 FastAPI app + 每请求 SQLite 连接(WAL 模式)+ LangGraph `graph.astream(stream_mode="updates")` 同步流式接驳 `sse_starlette.EventSourceResponse`(FastAPI 官方权威 pattern,无后台任务/Queue 复杂度)。Lane D 的 `rivalradar/graph/build.py:run_research` / `build_research_graph` 与 `rivalradar/storage/repository.py` 完整复用,Lane E 只做 HTTP 暴露层 + SSE 序列化。

**Tech Stack:** FastAPI ≥0.115 · sse-starlette ≥2.1 · uvicorn[standard] ≥0.30 · LangGraph 1.2.1(astream)· SQLite WAL · Pydantic 2.x · pytest + `fastapi.testclient.TestClient`

**Already locked(不要再问)**:
- 框架:FastAPI(spec §12 已定)
- SSE 库:sse-starlette(context7 权威:内建 `ping=15s` keep-alive、`_listen_for_disconnect`、`shutdown_event`、`X-Accel-Buffering: no`)
- SSE 模式:**同步流式** — `POST /run` 直接返 `EventSourceResponse`(FastAPI 官方权威 pattern)
- LangGraph stream:`graph.astream(stream_mode="updates")`,chunk = `{node_name: state_delta}`,**不**用 `BackgroundTasks`(语义是"响应发完后跑",接不上同一条流)
- 端点 9 个(spec §11 反推完整集):`POST /run` · `GET /runs` · `GET /run/:id` · `GET /stream/:run` · `GET /evidence/:id` · `GET /analysis/:run` · `GET /report/:run` · `GET /trace/:run` · `POST /annotations`
- 并发安全:per-request connection + SQLite WAL(并发读 + 单写,LangGraph 官方对 SqliteSaver 多 writer 未承诺安全,本 Lane 不绑 checkpointer 走 trace 持久化即可)

---

## File Structure

**新增 `rivalradar/api/`**:

| 文件 | 单一责任 |
|---|---|
| `__init__.py` | 模块标记(空) |
| `app.py` | `create_app(...) → FastAPI` 工厂 + lifespan + CORS + healthcheck + 异常处理 |
| `deps.py` | DI 注入:`get_db_conn`(per-request)、`get_doubao_client`、`get_provider`、`get_as_of`、`get_max_retries` |
| `schemas.py` | API 请求/响应 Pydantic 模型 |
| `runs.py` | `POST /run` · `GET /runs` · `GET /run/:id` · `GET /stream/:run` |
| `reads.py` | `GET /evidence/:id` · `GET /analysis/:run` · `GET /report/:run` · `GET /trace/:run` |
| `annotations.py` | `POST /annotations` |
| `sse.py` | `graph_event_stream` · `_summarize_delta` · `_replay_from_trace` |

**修改**:
- `rivalradar/storage/db.py`:加 `annotations` 表 + `PRAGMA journal_mode=WAL`
- `rivalradar/storage/repository.py`:加 `list_runs`、`insert_annotation`、`list_annotations`
- `pyproject.toml`:加 `fastapi`、`sse-starlette`、`uvicorn[standard]`

**新增**:
- `main.py`(项目根):`uvicorn` 入口,`python main.py`
- `spikes/spike_g_api_real_doubao.py`:真实 Doubao 跑 1 个竞品 + TestClient 消费 SSE
- `spikes/SPIKE_RESULTS.md`:追加 Spike G 条目

**测试**(`tests/` 扁平,沿用项目惯例):

| 文件 | 覆盖 |
|---|---|
| `tests/test_db.py`(扩展) | annotations 表 schema + WAL 模式生效 |
| `tests/test_repository.py`(扩展) | `list_runs` / annotations CRUD |
| `tests/test_api_app.py` | app 工厂 + healthcheck + CORS + 404 异常 |
| `tests/test_api_sse.py` | `_summarize_delta` 各节点 + `graph_event_stream` 用 stub graph |
| `tests/test_api_reads.py` | 4 个读端点 200/404 |
| `tests/test_api_runs.py` | POST /run SSE 完整流 + GET /runs + GET /run/:id 三态 + GET /stream/:run 回放 |
| `tests/test_api_annotations.py` | POST /annotations 写入 + 字段校验 |
| `tests/test_api_concurrent.py` | ★ 并发写 spike:API GET + graph 跑 POST 同 db 不死锁 |

---

## Task 1: 依赖 + 项目脚手架

**Files:**
- Modify: `pyproject.toml`
- Create: `rivalradar/api/__init__.py`
- Test: `tests/test_api_app.py`(导入烟雾测试占位)

- [ ] **Step 1: Add API server dependencies to `pyproject.toml`**

在 `dependencies = [...]` 列表里追加(保持现有 8 条不动):

```toml
    "fastapi>=0.115",
    "sse-starlette>=2.1",
    "uvicorn[standard]>=0.30",
```

- [ ] **Step 2: Install**

```bash
.venv/bin/pip install -e .
```

Expected: 三个新依赖安装,无错误。

- [ ] **Step 3: Create empty `rivalradar/api/__init__.py`**

```python
"""RivalRadar 后端 API(Lane E)。"""
```

- [ ] **Step 4: Write smoke import test**

`tests/test_api_app.py`:

```python
def test_api_module_imports():
    import rivalradar.api  # noqa: F401
```

- [ ] **Step 5: Run test**

```bash
.venv/bin/python -m pytest tests/test_api_app.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml rivalradar/api/__init__.py tests/test_api_app.py
git commit -m "feat: Lane E scaffolding (api module + fastapi/sse-starlette/uvicorn deps)"
```

---

## Task 2: Schema 迁移 — annotations 表 + WAL + list_runs

**Files:**
- Modify: `rivalradar/storage/db.py`(加 annotations 表 + WAL pragma)
- Modify: `rivalradar/storage/repository.py`(加 `list_runs`、`insert_annotation`、`list_annotations`)
- Modify: `tests/test_db.py`(annotations + WAL 单测)
- Modify: `tests/test_repository.py`(新函数单测)

- [ ] **Step 1: Write failing test for annotations table + WAL**

在 `tests/test_db.py` 末尾追加:

```python
def test_annotations_table_exists(conn):
    # 写入应不抛
    conn.execute(
        "INSERT INTO annotations (run_id, evidence_id, conclusion_path, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("r1", "ev_abc", "competitors[0].swot.strengths[0]", "可疑", "2026-05-26T00:00:00Z"),
    )
    conn.commit()
    row = conn.execute("SELECT note FROM annotations WHERE run_id=?", ("r1",)).fetchone()
    assert row["note"] == "可疑"


def test_wal_mode_enabled(conn):
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
```

注意 `tests/test_db.py` 的 fixture 用 `:memory:`,内存库 WAL 会回 `memory` —— 改 fixture 用 tempfile,或者添加专用 fixture。为避免动到既有测试,在 `test_wal_mode_enabled` 内自建 file-backed conn:

```python
def test_wal_mode_enabled(tmp_path):
    from rivalradar.storage.db import connect, init_db
    db = tmp_path / "wal.db"
    c = connect(str(db))
    init_db(c)
    mode = c.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    c.close()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_db.py -v -k "annotations or wal"
```

Expected: `no such table: annotations` + WAL 测失败(默认是 delete 模式)。

- [ ] **Step 3: Edit `rivalradar/storage/db.py`**

在 `SCHEMA` 字符串末尾(`CREATE INDEX...trace_run` 后)追加 annotations 表:

```sql
CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    evidence_id     TEXT,
    conclusion_path TEXT,
    note            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_annotations_run ON annotations(run_id);
```

修改 `init_db`(开 WAL,放在 `executescript` 之前;`:memory:` 库会自动回退,不报错):

```python
def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: Run db tests**

```bash
.venv/bin/python -m pytest tests/test_db.py -v
```

Expected: 全 pass(含新增 2 条)。

- [ ] **Step 5: Write failing tests for `list_runs` + annotations CRUD**

在 `tests/test_repository.py` 末尾追加:

```python
def test_list_runs_orders_newest_first(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.create_run(conn, "r2", ["Linear"], ["pricing"])
    runs = repo.list_runs(conn)
    assert [r["run_id"] for r in runs] == ["r2", "r1"]
    assert runs[0]["status"] == "running"


def test_annotation_roundtrip(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    aid = repo.insert_annotation(
        conn, run_id="r1", evidence_id="ev1",
        conclusion_path="competitors[0].swot.strengths[0]", note="此处存疑")
    assert isinstance(aid, int) and aid > 0
    rows = repo.list_annotations(conn, "r1")
    assert len(rows) == 1
    assert rows[0]["note"] == "此处存疑"
    assert rows[0]["evidence_id"] == "ev1"


def test_annotation_evidence_id_optional(conn):
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.insert_annotation(conn, run_id="r1", evidence_id=None,
                           conclusion_path="competitors[0]", note="整体可疑")
    rows = repo.list_annotations(conn, "r1")
    assert rows[0]["evidence_id"] is None
```

- [ ] **Step 6: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_repository.py -v -k "list_runs or annotation"
```

Expected: `AttributeError: module 'rivalradar.storage.repository' has no attribute 'list_runs'`。

- [ ] **Step 7: Implement in `rivalradar/storage/repository.py`**

在文件末尾追加(保持 `from __future__` 与 import 不动,_now 已存在可复用):

```python
# ---- runs list ----
def list_runs(conn: sqlite3.Connection, *, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [
        {
            "run_id": r["run_id"],
            "competitors": json.loads(r["competitors"]),
            "dimensions": json.loads(r["dimensions"]),
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---- annotations(spec §11.6 D10 桩,§17 人工质疑率)----
def insert_annotation(conn: sqlite3.Connection, *, run_id: str,
                      evidence_id: str | None, conclusion_path: str | None,
                      note: str) -> int:
    cur = conn.execute(
        "INSERT INTO annotations (run_id, evidence_id, conclusion_path, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, evidence_id, conclusion_path, note, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_annotations(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM annotations WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [
        {
            "id": r["id"],
            "run_id": r["run_id"],
            "evidence_id": r["evidence_id"],
            "conclusion_path": r["conclusion_path"],
            "note": r["note"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
```

- [ ] **Step 8: Run all storage tests**

```bash
.venv/bin/python -m pytest tests/test_db.py tests/test_repository.py -v
```

Expected: all pass。

- [ ] **Step 9: Commit**

```bash
git add rivalradar/storage/db.py rivalradar/storage/repository.py \
        tests/test_db.py tests/test_repository.py
git commit -m "feat(storage): add annotations table + WAL + list_runs / annotation CRUD (Lane E §11.6)"
```

---

## Task 3: API 请求/响应 Schemas

**Files:**
- Create: `rivalradar/api/schemas.py`
- Test: `tests/test_api_app.py`(扩展)

- [ ] **Step 1: Write failing tests for schemas**

在 `tests/test_api_app.py` 追加(保留 Task 1 的 import smoke):

```python
import pytest
from pydantic import ValidationError


def test_run_request_validates_non_empty():
    from rivalradar.api.schemas import RunRequest
    req = RunRequest(competitors=["Notion"], dimensions=["pricing"])
    assert req.competitors == ["Notion"]
    with pytest.raises(ValidationError):
        RunRequest(competitors=[], dimensions=["pricing"])  # 空竞品列表非法
    with pytest.raises(ValidationError):
        RunRequest(competitors=["X"], dimensions=[])        # 空维度非法


def test_annotation_create_requires_note():
    from rivalradar.api.schemas import AnnotationCreate
    a = AnnotationCreate(run_id="r1", evidence_id="ev1",
                         conclusion_path=None, note="可疑")
    assert a.note == "可疑"
    with pytest.raises(ValidationError):
        AnnotationCreate(run_id="r1", evidence_id=None,
                         conclusion_path=None, note="")  # 空 note 非法
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_app.py -v
```

Expected: `ModuleNotFoundError: rivalradar.api.schemas`。

- [ ] **Step 3: Create `rivalradar/api/schemas.py`**

```python
"""Lane E 的 HTTP 边界模型。响应实体复用 rivalradar.schema.models 的 Pydantic 类型,
本文件只定义 API 边界特有的请求/响应/错误形状(避免与领域模型耦合)。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """POST /run 请求体。"""
    competitors: list[str] = Field(min_length=1)
    dimensions: list[str] = Field(min_length=1)


class RunSummary(BaseModel):
    """GET /runs 列表项(简版,不含详情)。"""
    run_id: str
    competitors: list[str]
    dimensions: list[str]
    status: str  # running / done / insufficient_evidence / degraded
    created_at: str


class RunDetail(RunSummary):
    """GET /run/:id 详情(加 degraded 标记;前端按它显示降级横幅 §11.5)。"""
    degraded: bool = False


class AnnotationCreate(BaseModel):
    """POST /annotations 请求体(§11.6 D10 标记质疑桩)。"""
    run_id: str
    evidence_id: Optional[str] = None
    conclusion_path: Optional[str] = None
    note: str = Field(min_length=1)


class AnnotationOut(AnnotationCreate):
    id: int
    created_at: str


class TraceEntry(BaseModel):
    """GET /trace/:run 单条 trace。"""
    id: int
    run_id: str
    node: str
    prompt: str = ""
    input_summary: str = ""
    output_summary: str = ""
    tokens: int = 0
    latency_ms: int = 0
    ts: str


class ErrorOut(BaseModel):
    """404/422 等错误统一形状。"""
    detail: str
```

- [ ] **Step 4: Run, expect PASS**

```bash
.venv/bin/python -m pytest tests/test_api_app.py -v
```

Expected: 3 passed(import + 2 schema 测试)。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/schemas.py tests/test_api_app.py
git commit -m "feat(api): Lane E request/response schemas"
```

---

## Task 4: App 工厂 + lifespan + CORS + healthcheck + DI

**Files:**
- Create: `rivalradar/api/deps.py`
- Create: `rivalradar/api/app.py`
- Modify: `tests/test_api_app.py`(扩展)

- [ ] **Step 1: Write failing tests**

在 `tests/test_api_app.py` 追加:

```python
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    from rivalradar.api.app import create_app
    db = tmp_path / "test.db"
    app = create_app(db_path=str(db))
    return TestClient(app)


def test_healthcheck_returns_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_healthcheck_does_not_leak_api_key(client):
    """🔑 KEY 纪律:健康检查只返 bool,绝不返 key 值。"""
    r = client.get("/healthz")
    body = r.text
    # 即便 .env 里没 key,响应里也不应有 key/secret/ARK 字眼
    for s in ("sk-", "ARK_API_KEY", "secret", "Bearer "):
        assert s not in body


def test_cors_headers_present(client):
    r = client.options("/healthz",
                       headers={"origin": "http://localhost:3000",
                                "access-control-request-method": "GET"})
    # 允许任意源(Lane F 开发期 :3000 → :8000)
    assert r.headers.get("access-control-allow-origin") == "*"


def test_404_returns_json_error(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert "detail" in r.json()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_app.py -v
```

Expected: `ModuleNotFoundError: rivalradar.api.app`。

- [ ] **Step 3: Create `rivalradar/api/deps.py`**

```python
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
```

- [ ] **Step 4: Create `rivalradar/api/app.py`**

```python
"""FastAPI app 工厂。

测试用法:create_app(db_path=tmp.db, doubao_client=stub, provider=fake)
生产用法:create_app() 全部从 rivalradar.config + 环境默认值取
"""
from __future__ import annotations

import datetime as _dt
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rivalradar import config as cfg


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # 启动前已由 create_app 把 state 字段填好;这里只留位置给未来日志/预热
    yield


def create_app(
    *,
    db_path: str | None = None,
    doubao_client: Any | None = None,
    provider: Any | None = None,
    as_of: str | None = None,
    max_retries: int = 2,
) -> FastAPI:
    """构造并返回 FastAPI 实例。所有依赖通过参数注入,缺省走 rivalradar.config。

    🔑 KEY 纪律:绝不在响应/日志中暴露 ARK_API_KEY。健康检查只回 bool。
    """
    app = FastAPI(
        title="RivalRadar API",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # CORS(开发期 Lane F :3000 → 后端 :8000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 把进程级资源挂到 app.state(deps.py 从这里读)
    app.state.db_path = db_path or cfg.db_path()
    app.state.doubao_client = doubao_client  # 可为 None(只读端点不需要)
    app.state.provider = provider            # 可为 None(只读端点不需要)
    app.state.as_of = as_of or _dt.date.today().isoformat()
    app.state.max_retries = max_retries

    # 统一异常 → ErrorOut 形状
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_req, exc: StarletteHTTPException):
        return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code)

    @app.get("/healthz")
    def healthz() -> dict:
        # 只返 bool,绝不返 key 值(KEY 纪律)
        return {"ok": True}

    # 路由分组(后续 Task 5-10 各自挂载)
    from rivalradar.api.reads import router as reads_router
    from rivalradar.api.runs import router as runs_router
    from rivalradar.api.annotations import router as annotations_router
    app.include_router(reads_router)
    app.include_router(runs_router)
    app.include_router(annotations_router)

    return app
```

注意:上面 `include_router` 引用了三个还未创建的 router 文件。**这里的 import 在 Task 5/6/8/9/10 完成前会失败 —— 所以本 Task 不在最末导入,改为先各自创建空 router 占位**。

- [ ] **Step 5: Create empty router placeholders so app imports**

`rivalradar/api/reads.py`:
```python
from fastapi import APIRouter
router = APIRouter(tags=["reads"])
```

`rivalradar/api/runs.py`:
```python
from fastapi import APIRouter
router = APIRouter(tags=["runs"])
```

`rivalradar/api/annotations.py`:
```python
from fastapi import APIRouter
router = APIRouter(tags=["annotations"])
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/python -m pytest tests/test_api_app.py -v
```

Expected: 7 passed(import smoke + 2 schema + healthcheck + key-no-leak + CORS + 404)。

- [ ] **Step 7: Commit**

```bash
git add rivalradar/api/app.py rivalradar/api/deps.py \
        rivalradar/api/reads.py rivalradar/api/runs.py rivalradar/api/annotations.py \
        tests/test_api_app.py
git commit -m "feat(api): Lane E app factory + DI + CORS + healthcheck (key-safe)"
```

---

## Task 5: 读端点 — evidence / analysis / report / trace

**Files:**
- Modify: `rivalradar/api/reads.py`(填充实现)
- Create: `tests/test_api_reads.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api_reads.py`:

```python
import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, Evidence, PricingModel, SWOT,
)
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "reads.db")


@pytest.fixture()
def seeded(db_path):
    """种入 1 个 run + 1 条 evidence + analysis + report + 2 条 trace。"""
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    ev = Evidence(id="ev1", competitor="Notion", dimension="pricing",
                  content="$10/mo", source_url="https://notion.so/pricing",
                  source_title="Pricing", language="en",
                  fetched_at="2026-05-25T00:00:00Z")
    repo.insert_evidence(c, "r1", ev)
    repo.save_analysis(c, "r1", CompetitorAnalysis(competitors=[
        CompetitorProfile(name="Notion",
                          pricing=PricingModel(model_type="freemium"),
                          swot=SWOT())]))
    repo.save_report(c, "r1", "# 报告\n正文")
    repo.append_trace(c, "r1", "collect", input_summary="targets=all",
                      output_summary="+1", latency_ms=12)
    repo.append_trace(c, "r1", "analyze", input_summary="1 evidence",
                      output_summary="1 profiles", latency_ms=34)
    c.close()


@pytest.fixture()
def client(db_path, seeded):
    return TestClient(create_app(db_path=db_path))


def test_get_evidence_returns_pydantic(client):
    r = client.get("/evidence/ev1")
    assert r.status_code == 200
    body = r.json()
    assert body["competitor"] == "Notion"
    assert body["source_url"] == "https://notion.so/pricing"


def test_get_evidence_404_when_missing(client):
    r = client.get("/evidence/nonexistent")
    assert r.status_code == 404


def test_get_analysis_returns_competitor_analysis(client):
    r = client.get("/analysis/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["competitors"][0]["name"] == "Notion"


def test_get_analysis_404_when_missing(client):
    r = client.get("/analysis/no_run")
    assert r.status_code == 404


def test_get_report_returns_markdown(client):
    r = client.get("/report/r1")
    assert r.status_code == 200
    body = r.json()
    assert body["markdown"].startswith("# 报告")


def test_get_report_404(client):
    r = client.get("/report/no_run")
    assert r.status_code == 404


def test_get_trace_returns_entries(client):
    r = client.get("/trace/r1")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert items[0]["node"] == "collect"
    assert items[1]["node"] == "analyze"
    assert items[1]["latency_ms"] == 34


def test_get_trace_empty_list_for_unknown_run(client):
    r = client.get("/trace/no_run")
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_reads.py -v
```

Expected: 404 on all real endpoints(reads.py 还是空 router)。

- [ ] **Step 3: Implement `rivalradar/api/reads.py`**

```python
"""只读端点:evidence / analysis / report / trace(spec §13 测试覆盖 + §11 前端需求)。"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from rivalradar.api.deps import get_db_conn
from rivalradar.api.schemas import TraceEntry
from rivalradar.schema.models import CompetitorAnalysis, Evidence
from rivalradar.storage import repository as repo

router = APIRouter(tags=["reads"])


@router.get("/evidence/{evidence_id}", response_model=Evidence)
def get_evidence(evidence_id: str,
                 conn: sqlite3.Connection = Depends(get_db_conn)) -> Evidence:
    ev = repo.get_evidence(conn, evidence_id)
    if ev is None:
        raise HTTPException(404, "evidence not found")
    return ev


@router.get("/analysis/{run_id}", response_model=CompetitorAnalysis)
def get_analysis(run_id: str,
                 conn: sqlite3.Connection = Depends(get_db_conn)) -> CompetitorAnalysis:
    a = repo.get_analysis(conn, run_id)
    if a is None:
        raise HTTPException(404, "analysis not found")
    return a


@router.get("/report/{run_id}")
def get_report(run_id: str,
               conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    md = repo.get_report(conn, run_id)
    if md is None:
        raise HTTPException(404, "report not found")
    # 仍包成 JSON({markdown: "..."})保持响应类型一致,前端 Lane F 一次性
    # JSON 反序列化即可;§11.1 用结构化卡片渲染,markdown 是兜底
    return {"run_id": run_id, "markdown": md}


@router.get("/trace/{run_id}", response_model=list[TraceEntry])
def get_trace(run_id: str,
              conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    # repo.list_trace 已返 dict 列表(含 id/run_id/node/...);Pydantic 自动校验
    return repo.list_trace(conn, run_id)
```

- [ ] **Step 4: Run reads tests**

```bash
.venv/bin/python -m pytest tests/test_api_reads.py -v
```

Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/reads.py tests/test_api_reads.py
git commit -m "feat(api): read endpoints — evidence/analysis/report/trace (spec §13)"
```

---

## Task 6: Runs 列表 + Run 详情

**Files:**
- Modify: `rivalradar/api/runs.py`(加 GET /runs + GET /run/:id)
- Create/Modify: `tests/test_api_runs.py`(本任务先加列表/详情用例,POST/Stream 留给后面)

- [ ] **Step 1: Write failing tests**

`tests/test_api_runs.py`:

```python
import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "runs.db")


@pytest.fixture()
def client(db_path):
    return TestClient(create_app(db_path=db_path))


def _seed_three_runs(db_path):
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r_done", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r_done", "done")
    repo.create_run(c, "r_insuf", ["Linear"], ["pricing"])
    repo.update_run_status(c, "r_insuf", "insufficient_evidence")
    repo.create_run(c, "r_degr", ["Asana"], ["pricing"])
    repo.update_run_status(c, "r_degr", "degraded")
    c.close()


def test_list_runs_returns_summary(db_path, client):
    _seed_three_runs(db_path)
    r = client.get("/runs")
    assert r.status_code == 200
    items = r.json()
    assert {x["run_id"] for x in items} == {"r_done", "r_insuf", "r_degr"}
    statuses = {x["status"] for x in items}
    assert statuses == {"done", "insufficient_evidence", "degraded"}


def test_get_run_done_state(db_path, client):
    _seed_three_runs(db_path)
    r = client.get("/run/r_done")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["degraded"] is False


def test_get_run_insufficient_state(db_path, client):
    _seed_three_runs(db_path)
    r = client.get("/run/r_insuf")
    assert r.status_code == 200
    assert r.json()["status"] == "insufficient_evidence"


def test_get_run_degraded_state_sets_degraded_flag(db_path, client):
    """status=degraded 时 degraded 标记必须 True,前端 §11.5 据此显示告警横幅。"""
    _seed_three_runs(db_path)
    r = client.get("/run/r_degr")
    body = r.json()
    assert body["status"] == "degraded"
    assert body["degraded"] is True


def test_get_run_404(client):
    r = client.get("/run/no_such")
    assert r.status_code == 404
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_runs.py -v
```

Expected: 404 on /runs, /run/r_done(空 router)。

- [ ] **Step 3: Replace `rivalradar/api/runs.py`** with:

```python
"""Run 触发 + 列表 + 详情 + SSE 流。本 Task 实现列表与详情;POST/Stream 在后续任务。"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from rivalradar.api.deps import get_db_conn
from rivalradar.api.schemas import RunDetail, RunSummary
from rivalradar.storage import repository as repo

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunSummary])
def list_runs(conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    return repo.list_runs(conn)


@router.get("/run/{run_id}", response_model=RunDetail)
def get_run(run_id: str,
            conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    r = repo.get_run(conn, run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    # degraded 状态在 repo 层没单字段,从 status 反推(spec §8 + Lane D 遗留)
    r["degraded"] = (r["status"] == "degraded")
    return r
```

- [ ] **Step 4: Run runs tests**

```bash
.venv/bin/python -m pytest tests/test_api_runs.py -v
```

Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/runs.py tests/test_api_runs.py
git commit -m "feat(api): GET /runs + GET /run/:id with 3-state degraded mapping"
```

---

## Task 7: SSE 序列化 helper(graph_event_stream + summarizer + replay)

**Files:**
- Create: `rivalradar/api/sse.py`
- Create: `tests/test_api_sse.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api_sse.py`:

```python
import asyncio
import json
import pytest

from rivalradar.api.sse import _summarize_delta, graph_event_stream, _replay_from_trace
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


def test_summarize_collect_returns_evidence_count():
    s = _summarize_delta("collect", {"evidence": [{"id": "e1"}, {"id": "e2"}]})
    assert s == {"node": "collect", "evidence_added": 2}


def test_summarize_analyze_returns_competitor_count():
    s = _summarize_delta("analyze",
                         {"analysis": {"competitors": [{"name": "A"}, {"name": "B"}],
                                       "comparison": [{"dimension": "pricing"}]}})
    assert s == {"node": "analyze", "competitors": 2, "comparison_rows": 1}


def test_summarize_write_returns_chars():
    s = _summarize_delta("write", {"report": "abcdef"})
    assert s == {"node": "write", "report_chars": 6}


def test_summarize_qc_returns_verdict_and_retry():
    s = _summarize_delta("qc", {
        "qc_result": {"verdict": "retry_collect",
                      "issues": [{"problem_type": "missing_evidence"}]},
        "retry_count": 1,
        "degraded": False,
    })
    assert s == {"node": "qc", "verdict": "retry_collect", "issues": 1,
                 "retry_count": 1, "degraded": False}


def test_summarize_finalize_returns_status():
    s = _summarize_delta("finalize", {"status": "done",
                                       "qc_result": {"verdict": "pass"}})
    assert s == {"node": "finalize", "status": "done", "verdict": "pass"}


class _StubGraph:
    """模拟 LangGraph 的 astream 行为:逐步 yield {node_name: delta}。"""
    def astream(self, _input, *, config, stream_mode):
        assert stream_mode == "updates"
        async def gen():
            yield {"collect": {"evidence": [{"id": "e1"}, {"id": "e2"}]}}
            yield {"analyze": {"analysis": {"competitors": [{"name": "A"}],
                                            "comparison": []}}}
            yield {"write": {"report": "hi"}}
            yield {"qc": {"qc_result": {"verdict": "pass", "issues": []},
                          "retry_count": 0, "degraded": False}}
            yield {"finalize": {"status": "done",
                                "qc_result": {"verdict": "pass"}}}
        return gen()


async def _collect(gen):
    out = []
    async for ev in gen:
        out.append(ev)
    return out


def test_graph_event_stream_yields_start_node_done():
    events = asyncio.run(_collect(graph_event_stream(
        _StubGraph(), initial={}, config={"configurable": {"thread_id": "r1"}},
        run_id="r1")))
    # 期望:start + 5 node events + done = 7 条
    assert events[0]["event"] == "start"
    assert json.loads(events[0]["data"])["run_id"] == "r1"
    node_events = [e for e in events if e["event"] == "node"]
    assert [json.loads(e["data"])["node"] for e in node_events] == \
        ["collect", "analyze", "write", "qc", "finalize"]
    assert events[-1]["event"] == "done"


def test_graph_event_stream_emits_error_on_exception():
    class _BoomGraph:
        def astream(self, _input, *, config, stream_mode):
            async def gen():
                yield {"collect": {"evidence": []}}
                raise RuntimeError("upstream LLM down")
                yield  # unreachable
            return gen()

    async def _run():
        events = []
        with pytest.raises(RuntimeError):
            async for ev in graph_event_stream(_BoomGraph(), {}, {}, "r1"):
                events.append(ev)
        return events

    events = asyncio.run(_run())
    # 应当先有 start + collect node,然后 error,再让异常上抛
    assert events[0]["event"] == "start"
    assert any(e["event"] == "error" and "upstream LLM down" in e["data"]
               for e in events)


def test_replay_from_trace_yields_trace_events(tmp_path):
    c = connect(str(tmp_path / "replay.db"))
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r1", "done")
    repo.append_trace(c, "r1", "collect", input_summary="targets=all",
                      output_summary="+2", latency_ms=10)
    repo.append_trace(c, "r1", "qc", output_summary="verdict=pass", latency_ms=20)

    events = asyncio.run(_collect(_replay_from_trace(c, "r1", pacing=0.0)))
    assert events[0]["event"] == "start"
    trace_events = [e for e in events if e["event"] == "trace"]
    assert [json.loads(e["data"])["node"] for e in trace_events] == ["collect", "qc"]
    assert events[-1]["event"] == "done"
    assert json.loads(events[-1]["data"])["status"] == "done"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_sse.py -v
```

Expected: `ModuleNotFoundError: rivalradar.api.sse`。

- [ ] **Step 3: Implement `rivalradar/api/sse.py`**

```python
"""LangGraph astream → SSE chunk 序列化。

设计原则(必读):
- 事件本身只携带「前端动画必需的轻量摘要」(node + 计数/verdict/status),不
  传整张 state(几 KB → 几十 B),给 §11.4 实时 DAG 用。前端需要详情时另调
  GET /evidence/:id / /analysis/:run / /report/:run / /trace/:run。
- 任何 astream 异常先发 'error' 事件给前端,**再上抛** —— 前端能显示「失败原因」
  而非「连接突然断了」,且 sse-starlette 的 _listen_for_disconnect 仍能正常清理。
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from rivalradar.storage import repository as repo


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize_delta(node: str, delta: dict[str, Any]) -> dict[str, Any]:
    """把 state delta 压成前端动画用的小事件。未识别节点透传 node 名。"""
    if node == "collect":
        return {"node": "collect",
                "evidence_added": len(delta.get("evidence", []))}
    if node == "analyze":
        a = delta.get("analysis", {})
        return {"node": "analyze",
                "competitors": len(a.get("competitors", [])),
                "comparison_rows": len(a.get("comparison", []))}
    if node == "write":
        return {"node": "write", "report_chars": len(delta.get("report", ""))}
    if node == "qc":
        qcr = delta.get("qc_result", {})
        return {"node": "qc",
                "verdict": qcr.get("verdict"),
                "issues": len(qcr.get("issues", [])),
                "retry_count": delta.get("retry_count"),
                "degraded": delta.get("degraded")}
    if node == "finalize":
        return {"node": "finalize",
                "status": delta.get("status"),
                "verdict": delta.get("qc_result", {}).get("verdict")}
    return {"node": node}


async def graph_event_stream(
    graph,
    initial: dict,
    config: dict,
    run_id: str,
) -> AsyncIterator[dict]:
    """SSE 主流:start → 每节点 update → done(或 error → 上抛)。

    yield 出的 dict 给 sse-starlette EventSourceResponse,字段 'event'/'data'。
    """
    yield {"event": "start",
           "data": json.dumps({"run_id": run_id, "ts": _now()})}
    try:
        async for chunk in graph.astream(initial, config=config,
                                          stream_mode="updates"):
            for node_name, delta in chunk.items():
                yield {"event": "node",
                       "data": json.dumps({
                           "node": node_name,
                           "summary": _summarize_delta(node_name, delta),
                           "ts": _now(),
                       })}
    except Exception as e:  # noqa: BLE001 — 上抛前先让前端拿到 error 事件
        yield {"event": "error",
               "data": json.dumps({"error": str(e), "ts": _now()})}
        raise
    yield {"event": "done",
           "data": json.dumps({"run_id": run_id, "ts": _now()})}


async def _replay_from_trace(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    pacing: float = 0.05,
) -> AsyncIterator[dict]:
    """从 trace 表回放 SSE 事件(§11.4 'Play 回放' 用)。pacing=0 关闭节流(测试用)。"""
    yield {"event": "start",
           "data": json.dumps({"run_id": run_id, "replay": True, "ts": _now()})}
    for t in repo.list_trace(conn, run_id):
        yield {"event": "trace",
               "data": json.dumps({
                   "node": t["node"],
                   "input": t.get("input_summary", ""),
                   "output": t.get("output_summary", ""),
                   "latency_ms": t.get("latency_ms", 0),
                   "ts": t["ts"],
               })}
        if pacing > 0:
            await asyncio.sleep(pacing)
    run = repo.get_run(conn, run_id)
    yield {"event": "done",
           "data": json.dumps({
               "run_id": run_id,
               "status": run["status"] if run else "unknown",
               "ts": _now()})}
```

- [ ] **Step 4: Run sse tests**

```bash
.venv/bin/python -m pytest tests/test_api_sse.py -v
```

Expected: 9 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/sse.py tests/test_api_sse.py
git commit -m "feat(api): SSE event stream + delta summarizer + trace replay"
```

---

## Task 8: POST /run(SSE 流式触发,Lane E 命门)

**Files:**
- Modify: `rivalradar/api/runs.py`(加 POST /run)
- Modify: `tests/test_api_runs.py`(加 POST/SSE 用例)

- [ ] **Step 1: Write failing tests**

在 `tests/test_api_runs.py` 追加:

```python
import hashlib
import json

from rivalradar.agents import qc
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, CompetitorProfile, PricingModel,
    SWOT, ComparisonRow, ComparisonCell, EvidenceRef,
)
from rivalradar.search.base import SearchResult


class _OneShotProvider:
    """采集 1 条假证据立刻够本,无需 retry。"""
    name = "oneshot"
    def search(self, query, *, max_results=5):
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="s",
                             raw_content="body for " + query)]


def _fake_analyze(evidence, competitors, *, client, model):
    """与 test_graph_loop.py 同款:覆盖已有维度的对比,引用真实 id;无 features/personas/swot。"""
    dims_present = {e.dimension for e in evidence}
    profiles = []
    for c in competitors:
        price_ev = next((e for e in evidence if e.competitor == c and e.dimension == "pricing"), None)
        refs = [EvidenceRef(evidence_id=price_ev.id, quote="q")] if price_ev else []
        profiles.append(CompetitorProfile(
            name=c, pricing=PricingModel(model_type="freemium", evidence_refs=refs),
            swot=SWOT()))
    rows = []
    for dim in CONTROLLED_DIMENSIONS:
        if dim not in dims_present:
            continue
        cells = []
        for c in competitors:
            ev = next((e for e in evidence if e.competitor == c and e.dimension == dim), None)
            if ev:
                cells.append(ComparisonCell(competitor=c, value_type="enum",
                                            value="x",
                                            evidence_refs=[EvidenceRef(evidence_id=ev.id, quote="q")]))
        rows.append(ComparisonRow(dimension=dim, cells=cells))
    return CompetitorAnalysis(competitors=profiles, comparison=rows)


@pytest.fixture()
def stubbed_client(db_path, monkeypatch):
    # 用与 test_graph_loop.py 同款 stub:跳过真实 LLM,但跑完整图
    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _fake_analyze)
    monkeypatch.setattr("rivalradar.graph.nodes.write_report",
                        lambda *a, **k: "# 竞品分析报告\n正文")
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])
    app = create_app(db_path=db_path, doubao_client="stub-client",
                     provider=_OneShotProvider(), as_of="2026-05-26")
    return TestClient(app)


def _parse_sse(raw_bytes: bytes) -> list[dict]:
    """把原始 SSE 响应字节解析成 [{event, data}] 列表。"""
    events, current = [], {}
    for line in raw_bytes.decode("utf-8").splitlines():
        if line == "":
            if current:
                events.append(current)
                current = {}
        elif line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = line[6:]
    if current:
        events.append(current)
    return events


def test_post_run_streams_sse_with_start_nodes_done(stubbed_client):
    """POST /run 应当返 EventSourceResponse,先 start、过程节点事件、最后 done。"""
    r = stubbed_client.post("/run",
                            json={"competitors": ["Notion"],
                                  "dimensions": list(CONTROLLED_DIMENSIONS)})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.content)
    assert events[0]["event"] == "start"
    node_events = [e for e in events if e["event"] == "node"]
    nodes_hit = [json.loads(e["data"])["node"] for e in node_events]
    # 至少跑过 collect/analyze/write/qc/finalize
    for n in ("collect", "analyze", "write", "qc", "finalize"):
        assert n in nodes_hit
    assert events[-1]["event"] == "done"
    done_data = json.loads(events[-1]["data"])
    assert done_data["run_id"].startswith("run_")


def test_post_run_persists_state_after_stream(stubbed_client, db_path):
    """SSE 流跑完后,数据库里应有 run/evidence/analysis/report。"""
    r = stubbed_client.post("/run",
                            json={"competitors": ["Notion"],
                                  "dimensions": list(CONTROLLED_DIMENSIONS)})
    assert r.status_code == 200
    events = _parse_sse(r.content)
    done = json.loads(events[-1]["data"])
    run_id = done["run_id"]

    c = connect(db_path)
    init_db(c)
    run = repo.get_run(c, run_id)
    assert run is not None
    assert run["status"] in ("done", "insufficient_evidence", "degraded")
    assert len(repo.list_evidence(c, run_id)) > 0
    assert repo.get_report(c, run_id) is not None
    c.close()


def test_post_run_rejects_empty_competitors(stubbed_client):
    r = stubbed_client.post("/run", json={"competitors": [], "dimensions": ["pricing"]})
    assert r.status_code == 422
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_runs.py -v -k "post_run or rejects"
```

Expected: 404(POST /run 路由不存在)。

- [ ] **Step 3: Add POST /run to `rivalradar/api/runs.py`**

在 `runs.py` 顶部 import 段加入:

```python
import sqlite3
import uuid

from sse_starlette.sse import EventSourceResponse

from rivalradar.api.deps import (
    get_db_conn, get_doubao_client, get_provider, get_as_of, get_max_retries,
)
from rivalradar.api.schemas import RunRequest
from rivalradar.api.sse import graph_event_stream
from rivalradar.config import doubao_model
from rivalradar.graph.build import build_research_graph
from rivalradar.storage.repository import create_run
```

在 router 上加端点(放在 GET /runs 之前或之后均可):

```python
@router.post("/run")
def post_run(
    req: RunRequest,
    conn: sqlite3.Connection = Depends(get_db_conn),
    client=Depends(get_doubao_client),
    provider=Depends(get_provider),
    as_of: str = Depends(get_as_of),
    max_retries: int = Depends(get_max_retries),
) -> EventSourceResponse:
    """触发一次完整调研,SSE 流式回推每节点进度,直到 done/error。"""
    run_id = "run_" + uuid.uuid4().hex[:12]
    create_run(conn, run_id, req.competitors, req.dimensions)
    graph = build_research_graph(
        conn=conn, client=client, model=doubao_model(), provider=provider,
        as_of=as_of, max_retries=max_retries,
    )
    initial = {
        "competitors": req.competitors,
        "dimensions": req.dimensions,
        "evidence": [],
        "retry_count": 0,
    }
    config = {"configurable": {"thread_id": run_id}}
    return EventSourceResponse(
        graph_event_stream(graph, initial, config, run_id),
        ping=15,  # context7 验证的 keep-alive 默认,投影场景必备
    )
```

- [ ] **Step 4: Run POST/SSE tests**

```bash
.venv/bin/python -m pytest tests/test_api_runs.py -v
```

Expected: all pass(原 5 个 + 新 3 个 = 8 个)。

注意:`TestClient` 的 `.post()` 对 SSE 端点是阻塞的(等到流结束才返回),所以 `r.content` 拿到的就是全部字节。这是 starlette TestClient 的预期行为。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/runs.py tests/test_api_runs.py
git commit -m "feat(api): POST /run with sync streaming SSE + ping=15 keep-alive"
```

---

## Task 9: GET /stream/:run(回放完成的 run)

**Files:**
- Modify: `rivalradar/api/runs.py`(加 GET /stream/:run)
- Modify: `tests/test_api_runs.py`(加回放用例)

- [ ] **Step 1: Write failing test**

在 `tests/test_api_runs.py` 追加:

```python
def test_get_stream_replays_finished_run(stubbed_client, db_path):
    # 先跑一次 POST /run 让 trace 落库
    r = stubbed_client.post("/run",
                            json={"competitors": ["Notion"],
                                  "dimensions": list(CONTROLLED_DIMENSIONS)})
    events = _parse_sse(r.content)
    run_id = json.loads(events[-1]["data"])["run_id"]

    # 再 GET /stream/:run 应当从 trace 表回放
    r2 = stubbed_client.get(f"/stream/{run_id}")
    assert r2.status_code == 200
    replay = _parse_sse(r2.content)
    assert replay[0]["event"] == "start"
    assert json.loads(replay[0]["data"])["replay"] is True
    trace_events = [e for e in replay if e["event"] == "trace"]
    assert len(trace_events) > 0
    nodes = [json.loads(e["data"])["node"] for e in trace_events]
    for n in ("collect", "analyze", "write", "qc", "finalize"):
        assert n in nodes
    assert replay[-1]["event"] == "done"


def test_get_stream_404_for_unknown_run(client):
    # client 是非 stubbed 的纯空 db
    r = client.get("/stream/no_such_run")
    assert r.status_code == 404
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_runs.py -v -k "get_stream"
```

Expected: 404 on POST(SSE endpoint 不存在但 404 不是 from HTTPException);或 500 from invalid route。

- [ ] **Step 3: Add GET /stream/:run to `runs.py`**

加 import:

```python
from rivalradar.api.sse import _replay_from_trace
from rivalradar.storage.repository import get_run as _get_run
```

加端点:

```python
@router.get("/stream/{run_id}")
def get_stream(
    run_id: str,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> EventSourceResponse:
    """从 trace 表回放已结束 run 的事件流(§11.4 'Play 回放')。"""
    if _get_run(conn, run_id) is None:
        raise HTTPException(404, "run not found")
    return EventSourceResponse(
        _replay_from_trace(conn, run_id),
        ping=15,
    )
```

- [ ] **Step 4: Run runs tests全部**

```bash
.venv/bin/python -m pytest tests/test_api_runs.py -v
```

Expected: 10 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/runs.py tests/test_api_runs.py
git commit -m "feat(api): GET /stream/:run replays finished run from trace table"
```

---

## Task 10: POST /annotations(§11.6 D10 桩)

**Files:**
- Modify: `rivalradar/api/annotations.py`(填充实现)
- Create: `tests/test_api_annotations.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api_annotations.py`:

```python
import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "anno.db")


@pytest.fixture()
def client(db_path):
    return TestClient(create_app(db_path=db_path))


def _seed_run(db_path):
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    c.close()


def test_post_annotation_creates_and_returns_id(db_path, client):
    _seed_run(db_path)
    r = client.post("/annotations", json={
        "run_id": "r1", "evidence_id": "ev1",
        "conclusion_path": "competitors[0].swot.strengths[0]",
        "note": "此处存疑,缺直接证据",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["id"] > 0
    assert body["note"] == "此处存疑,缺直接证据"
    assert body["evidence_id"] == "ev1"


def test_post_annotation_evidence_id_optional(db_path, client):
    _seed_run(db_path)
    r = client.post("/annotations", json={
        "run_id": "r1", "evidence_id": None,
        "conclusion_path": "competitors[0]", "note": "整体可疑",
    })
    assert r.status_code == 201
    assert r.json()["evidence_id"] is None


def test_post_annotation_rejects_empty_note(db_path, client):
    _seed_run(db_path)
    r = client.post("/annotations", json={
        "run_id": "r1", "evidence_id": None,
        "conclusion_path": None, "note": "",
    })
    assert r.status_code == 422


def test_post_annotation_does_not_mutate_run_state(db_path, client):
    """§11.6 桩:只记日志、不写回 state、不重跑。"""
    _seed_run(db_path)
    client.post("/annotations", json={
        "run_id": "r1", "evidence_id": "ev1",
        "conclusion_path": "x", "note": "y"})
    c = connect(db_path)
    init_db(c)
    run = repo.get_run(c, "r1")
    assert run["status"] == "running"  # 未被任何方式改动
    c.close()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_api_annotations.py -v
```

Expected: 404 / 405(POST /annotations 不存在)。

- [ ] **Step 3: Replace `rivalradar/api/annotations.py`** with:

```python
"""标记质疑桩(spec §11.6 D10,§17 人工质疑率)。

只接收、只写一行 annotations 表,**不**写回 state、**不**重跑、**不**触发任何
图节点 —— 是个纯日志通道,前端拿到 201 即可显示「已记录」toast(§11.5)。
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, status

from rivalradar.api.deps import get_db_conn
from rivalradar.api.schemas import AnnotationCreate, AnnotationOut
from rivalradar.storage import repository as repo

router = APIRouter(tags=["annotations"])


@router.post("/annotations", response_model=AnnotationOut,
             status_code=status.HTTP_201_CREATED)
def post_annotation(
    body: AnnotationCreate,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> dict:
    aid = repo.insert_annotation(
        conn,
        run_id=body.run_id,
        evidence_id=body.evidence_id,
        conclusion_path=body.conclusion_path,
        note=body.note,
    )
    # 回读以获取 created_at(避免重复 _now 计算)
    rows = repo.list_annotations(conn, body.run_id)
    row = next(r for r in rows if r["id"] == aid)
    return row
```

- [ ] **Step 4: Run annotation tests**

```bash
.venv/bin/python -m pytest tests/test_api_annotations.py -v
```

Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/api/annotations.py tests/test_api_annotations.py
git commit -m "feat(api): POST /annotations stub (§11.6 D10, §17 人工质疑率)"
```

---

## Task 11: 并发写 spike — API 与 graph 同 db 不死锁

**Files:**
- Create: `tests/test_api_concurrent.py`

**Why this exists:** Lane D 遗留中 "checkpointer 与 repository 同 db 并发写锁未在真实持久化下验证" 是非阻断遗留。Lane E 让 API server + graph runner 都写同一个 SQLite。即便 Lane E **不绑 checkpointer**,POST /run 跑图过程中节点会 `append_trace/insert_evidence`,前端可能同时 GET `/trace/:run` 拉取最新进度。需要验证 WAL 模式下并发安全。

- [ ] **Step 1: Write failing test**

`tests/test_api_concurrent.py`:

```python
"""并发安全 spike:WAL 下 POST /run 写 + 并发 GET /trace 读不应死锁、不应 SQLITE_BUSY。

注意:TestClient 是同步的,真正"并行"用线程池开两路。"""
import hashlib
import json
import threading
import time
import pytest

from fastapi.testclient import TestClient

from rivalradar.agents import qc
from rivalradar.api.app import create_app
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, CompetitorProfile,
    PricingModel, SWOT, ComparisonRow, ComparisonCell, EvidenceRef,
)
from rivalradar.search.base import SearchResult
from rivalradar.storage.db import connect, init_db


class _SlowProvider:
    """每次 search 故意 sleep 80ms,模拟真实网络延迟,拉长写窗口让并发读必然撞上。"""
    name = "slow"
    def search(self, query, *, max_results=5):
        time.sleep(0.08)
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="s",
                             raw_content="body for " + query)]


def _fake_analyze(evidence, competitors, *, client, model):
    profiles = []
    for c in competitors:
        ev = next((e for e in evidence if e.competitor == c
                   and e.dimension == "pricing"), None)
        refs = [EvidenceRef(evidence_id=ev.id, quote="q")] if ev else []
        profiles.append(CompetitorProfile(
            name=c, pricing=PricingModel(model_type="freemium", evidence_refs=refs),
            swot=SWOT()))
    return CompetitorAnalysis(competitors=profiles, comparison=[])


def test_concurrent_post_and_get_trace_no_busy(tmp_path, monkeypatch):
    db_path = str(tmp_path / "concurrent.db")
    # 初始化(让 WAL 模式落到磁盘 + 表就绪)
    c = connect(db_path); init_db(c); c.close()

    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _fake_analyze)
    monkeypatch.setattr("rivalradar.graph.nodes.write_report",
                        lambda *a, **k: "# 报告")
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])

    app = create_app(db_path=db_path, doubao_client="stub",
                     provider=_SlowProvider(), as_of="2026-05-26")
    client = TestClient(app)

    # 后台并发拉 /trace/(POST 进行中)
    errors = []
    def _poll_traces(run_id_ref):
        for _ in range(20):  # 20 * 30ms = 600ms,覆盖 POST 跑图时长
            time.sleep(0.03)
            rid = run_id_ref.get("v")
            if not rid:
                continue
            try:
                r = client.get(f"/trace/{rid}")
                assert r.status_code == 200
                # 读出来的 trace 必须是合法 JSON 列表
                assert isinstance(r.json(), list)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

    run_id_ref = {"v": None}
    poller = threading.Thread(target=_poll_traces, args=(run_id_ref,))
    poller.start()

    r = client.post("/run", json={"competitors": ["Notion"],
                                   "dimensions": list(CONTROLLED_DIMENSIONS)})
    assert r.status_code == 200
    # 拿到 run_id 后让 poller 锁定
    events = []
    for line in r.content.decode().splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    rid = next((d["run_id"] for d in events if "run_id" in d), None)
    assert rid
    run_id_ref["v"] = rid
    poller.join(timeout=3.0)

    assert errors == [], f"concurrent reads failed: {errors}"
```

- [ ] **Step 2: Run**

```bash
.venv/bin/python -m pytest tests/test_api_concurrent.py -v -s
```

Expected outcome (一次性 PASS,因 Task 2 已开 WAL):若失败,说明 WAL 未生效或 connection 设置漏了 `check_same_thread=False` —— 回 Task 2 复核。

如果出现 `database is locked` / SQLITE_BUSY:
1. 确认 `db.py:init_db` 已加 `PRAGMA journal_mode=WAL`
2. 确认 `db.py:connect` 已有 `check_same_thread=False`(本就有)
3. 必要时在 `init_db` 后再加 `conn.execute("PRAGMA busy_timeout=5000")`

- [ ] **Step 3: Commit**

```bash
git add tests/test_api_concurrent.py
git commit -m "test(api): concurrent POST/GET trace spike — WAL safety under fan-out reads"
```

---

## Task 12: uvicorn 入口 + 集成 smoke + 真实 Doubao Spike G

**Files:**
- Create: `main.py`(项目根 uvicorn 入口)
- Create: `spikes/spike_g_api_real_doubao.py`
- Modify: `spikes/SPIKE_RESULTS.md`(追加 Spike G 条目)

- [ ] **Step 1: Create uvicorn entry `main.py`**

```python
"""RivalRadar API server entry. 启动:.venv/bin/python main.py

环境变量:
  ARK_API_KEY=...        必填,Doubao key
  RIVALRADAR_DB=...      可选,默认 rivalradar.db
  RIVALRADAR_PORT=8000   可选

🔑 KEY 纪律:绝不在 print/log 里展开 key 值;app.py 的 /healthz 只回 bool。
"""
from __future__ import annotations

import os

import uvicorn

from rivalradar import config as cfg
from rivalradar.api.app import create_app
from rivalradar.search.fallback import FallbackSearch
from rivalradar.search.tavily_provider import TavilyProvider
from rivalradar.search.exa_provider import ExaProvider


def _build_provider():
    """优先 Tavily,Exa 兜底(spec §3 Day-1 决议)。"""
    providers = []
    if cfg.tavily_api_key():
        providers.append(TavilyProvider(api_key=cfg.tavily_api_key()))
    if os.getenv("EXA_API_KEY"):
        providers.append(ExaProvider(api_key=os.getenv("EXA_API_KEY")))
    if not providers:
        raise RuntimeError("至少配置 TAVILY_API_KEY 或 EXA_API_KEY")
    return FallbackSearch(providers)


def main():
    if not cfg.ark_api_key():
        raise RuntimeError("ARK_API_KEY 未设置(放进 .env)")
    app = create_app(
        db_path=cfg.db_path(),
        doubao_client=cfg.get_doubao_client(),
        provider=_build_provider(),
    )
    port = int(os.getenv("RIVALRADAR_PORT", "8000"))
    print(f"[RivalRadar] starting on http://0.0.0.0:{port}  (key configured: {bool(cfg.ark_api_key())})")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
```

**注意:** Provider 构造引用了 `rivalradar/search/fallback.py:FallbackSearch` 与 `tavily_provider.TavilyProvider(api_key=...)`、`exa_provider.ExaProvider(api_key=...)`。先用 `grep` 验证这些类与构造签名真存在,如果签名不同(比如 `__init__` 拿 `client=` 不是 `api_key=`)就改成实际签名,**不要**编造。

```bash
grep -n "^class " rivalradar/search/*.py
```

- [ ] **Step 2: Manually smoke (无需真实 LLM)**

跑一次空 db、空 provider 的健康检查路径:

```bash
.venv/bin/python -c "
from rivalradar.api.app import create_app
from fastapi.testclient import TestClient
c = TestClient(create_app(db_path=':memory:'))
print(c.get('/healthz').json())
"
```

Expected: `{'ok': True}`。

- [ ] **Step 3: Create real-Doubao spike**

`spikes/spike_g_api_real_doubao.py`:

```python
"""Spike G: 真实 Doubao + Tavily 跑 1 个竞品 + 真实 API 服务器(TestClient 消费 SSE)。

跑通的硬证据:
- POST /run 返 SSE,事件序列包含 start/collect/analyze/write/qc/finalize/done
- 结束后 GET /run/:id 返 status,GET /report/:run 返非空 markdown,
  GET /trace/:run 返 ≥5 条节点 trace,GET /analysis/:run 返 ≥1 competitor

⚠️  消耗真实 Doubao token,只在 ARK_API_KEY + TAVILY_API_KEY 双就绪时跑。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from rivalradar import config as cfg
from rivalradar.api.app import create_app
from rivalradar.search.tavily_provider import TavilyProvider


def main():
    if not cfg.ark_api_key():
        print("[SKIP] ARK_API_KEY 未设置"); return
    if not cfg.tavily_api_key():
        print("[SKIP] TAVILY_API_KEY 未设置"); return

    db = "/tmp/spike_g.db"
    if os.path.exists(db):
        os.remove(db)

    app = create_app(
        db_path=db,
        doubao_client=cfg.get_doubao_client(),
        provider=TavilyProvider(api_key=cfg.tavily_api_key()),
        max_retries=1,  # 加快 spike
    )
    client = TestClient(app)

    print("[1/4] POST /run …")
    r = client.post("/run", json={
        "competitors": ["Notion"],
        "dimensions": ["pricing", "deployment", "integrations"],
    })
    assert r.status_code == 200, r.text
    print(f"     SSE bytes={len(r.content)}")

    events = []
    for line in r.content.decode().splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    run_id = next((d["run_id"] for d in events if "run_id" in d), None)
    assert run_id, "未拿到 run_id"
    print(f"     run_id={run_id}")

    nodes_hit = []
    for line in r.content.decode().splitlines():
        if line.startswith("event: "):
            nodes_hit.append(line[7:])
    print(f"     events seen: {set(nodes_hit)}")
    for n in ("start", "node", "done"):
        assert n in nodes_hit, f"missing event {n}"

    print("[2/4] GET /run/:id …")
    r = client.get(f"/run/{run_id}")
    assert r.status_code == 200
    print(f"     status={r.json()['status']}  degraded={r.json()['degraded']}")

    print("[3/4] GET /trace/:run …")
    r = client.get(f"/trace/{run_id}")
    assert r.status_code == 200
    print(f"     trace entries={len(r.json())}")

    print("[4/4] GET /report/:run + /analysis/:run …")
    r = client.get(f"/report/{run_id}")
    assert r.status_code == 200
    print(f"     report chars={len(r.json()['markdown'])}")
    r = client.get(f"/analysis/{run_id}")
    assert r.status_code == 200
    print(f"     competitors={len(r.json()['competitors'])}")

    print("\n[Spike G] ALL CHECKS PASSED  ✅")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run spike (如果 key 双就绪)**

```bash
.venv/bin/python spikes/spike_g_api_real_doubao.py
```

Expected: `[Spike G] ALL CHECKS PASSED  ✅`

若 ARK_API_KEY 或 TAVILY_API_KEY 缺失,会看到 `[SKIP]`(可控降级,不算失败)。

- [ ] **Step 5: Append result to `spikes/SPIKE_RESULTS.md`**

在文件末尾追加(保留前面所有 Spike A-F 条目不动):

```markdown

## Spike G — Lane E 真实 API + Doubao 集成(2026-05-26)

**目的:** 验证 Lane E 后端 API + SSE 在真实 Doubao + Tavily 上跑通端到端单竞品调研。

**做法:** `spikes/spike_g_api_real_doubao.py` 用 TestClient 调 POST /run,消费 SSE,
然后逐一 GET /run/:id、/trace/:run、/report/:run、/analysis/:run。

**结论:** GO。SSE 事件 start/node/done 齐全;run 终态合法;trace ≥5 条;
report 非空 markdown;analysis 含 ≥1 competitor。Lane E 与 Lane D 接驳通了,
为 Lane F 前端铺好可消费 API。
```

- [ ] **Step 6: Final full test sweep**

```bash
.venv/bin/python -m pytest -v
```

Expected: 全部 pass(Lane D 已有 125 + Lane E 新增 ~40 = ~165 全绿)。

- [ ] **Step 7: Commit**

```bash
git add main.py spikes/spike_g_api_real_doubao.py spikes/SPIKE_RESULTS.md
git commit -m "feat: uvicorn entry + Spike G (real Doubao + API server end-to-end)"
```

---

## Self-Review

### Spec 覆盖检查

| Spec 要求 | 实现位置 |
|---|---|
| §11.1 顶层 IA(run 列表 → 竞品列表 → 单 run 详情) | GET /runs · GET /run/:id |
| §11.2 证据面板就地对照(GET evidence 单条) | GET /evidence/:id(Task 5) |
| §11.3 跨竞品对比矩阵(结构化数据) | GET /analysis/:run(Task 5) |
| §11.4 money shot 实时动画 DAG + 节点抽屉 | POST /run SSE + GET /trace/:run(Task 5+7+8) |
| §11.5 状态设计(done / insufficient / degraded) | GET /run/:id 的 degraded 字段(Task 6) |
| §11.6 D10 标记质疑桩 | POST /annotations(Task 10) |
| §12 后端 Python + LangGraph + FastAPI | Tech Stack + Task 4 |
| §13 单测 GET /evidence/:id /report/:run /trace/:run | tests/test_api_reads.py(Task 5) |
| §17 人工质疑率指标(可算) | annotations 表 + POST /annotations 已落库(Task 2+10) |
| Money shot 演示分歧→解决 | spike_g 真实跑通,SSE 含 retry_collect→pass 路径(Task 12) |

### Placeholder scan

✅ 全部任务步骤含真实代码,无 "TODO/TBD/implement later/handle edge cases" 占位。
✅ 全部测试含具体 assertion,无 "Write tests for the above"。
✅ 全部 file path 是绝对、可定位的(`rivalradar/api/*.py` / `tests/test_api_*.py`)。

### Type consistency

| 跨任务符号 | 出处 | 使用方 |
|---|---|---|
| `RunRequest(competitors,dimensions)` | Task 3 schemas.py | Task 8 POST /run |
| `RunSummary` / `RunDetail` | Task 3 | Task 6 GET /runs · /run/:id |
| `AnnotationCreate` / `AnnotationOut` | Task 3 | Task 10 POST /annotations |
| `TraceEntry` | Task 3 | Task 5 GET /trace/:run |
| `get_db_conn` / `get_doubao_client` / `get_provider` / `get_as_of` / `get_max_retries` | Task 4 deps.py | Task 5-10 各路由 |
| `create_app(db_path=, doubao_client=, provider=, as_of=, max_retries=)` | Task 4 app.py | 所有测试 fixture · Task 12 main.py |
| `graph_event_stream(graph, initial, config, run_id)` | Task 7 sse.py | Task 8 POST /run |
| `_replay_from_trace(conn, run_id, pacing=)` | Task 7 sse.py | Task 9 GET /stream/:run |
| `insert_annotation(conn, *, run_id, evidence_id, conclusion_path, note)` → int | Task 2 repository | Task 10 POST /annotations |
| `list_runs(conn, *, limit=50)` → list[dict] | Task 2 repository | Task 6 GET /runs |

**全部一致。** 符号 / kwargs / 返回类型在所有引用点对齐。

### 工程纪律自检

- 🔑 KEY 纪律:`/healthz` 只回 `{"ok": True}`(Task 4 test_healthcheck_does_not_leak_api_key 显式断言);`main.py:main()` 只 print `bool(cfg.ark_api_key())`,绝不展开 key 值。
- CLAUDE.md 第 2 条 YAGNI:同步流式 ~30 行胜异步 ~80 行;9 端点 spec 全集胜"完整集 + DELETE/分页/比对"YAGNI 项;`_summarize_delta` 只压 5 个节点,无 future-proof 抽象。
- CLAUDE.md 第 3 条 Surgical:db.py 只加 annotations 表 + WAL pragma(不动既有 5 表);repository.py 只加 3 个函数(不改既有 11 个);`init_db` 加一行 `PRAGMA journal_mode=WAL` —— 边界明确。
- TDD 频率:每任务 ~3-5 commits,失败测试在前,实现在后,verify 在后。

### 已知遗留(非阻断,记入 Lane F/Day-4 考虑)

1. **SqliteSaver 未绑入 Lane E**:本 Lane 用 trace 表持久化已足够(回放走 trace),checkpointer 的并发写锁问题被绕开。Day-4 若加"中断恢复"功能再启用并发安全方案(独立 checkpointer.db 或换 Postgres)。
2. **`POST /annotations` 无认证**:比赛 demo 走 localhost,前端是受信客户端;生产化需加 token。
3. **SSE `X-Accel-Buffering: no` 默认 sse-starlette 不自动设**:Lane F 部署若过 nginx,需在 nginx 配 `proxy_buffering off`,或在 EventSourceResponse 加 `headers={"X-Accel-Buffering": "no"}`。比赛本地 demo 不必。
4. **多 run 比对、取消、分页**:D3 决策已弃,留给"万一前端需要时"。

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-26-rivalradar-lane-e-backend-sse.md`.**
