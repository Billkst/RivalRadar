"""FastAPI app 工厂。

测试用法:create_app(db_path=tmp.db, doubao_client=stub, provider=fake)
生产用法:create_app() 全部从 rivalradar.config + 环境默认值取

🔑 KEY 纪律:绝不在响应/日志中暴露 ARK_API_KEY。健康检查只回 bool。
"""
from __future__ import annotations

import datetime as _dt
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rivalradar import config as cfg


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield


def create_app(
    *,
    db_path: str | None = None,
    doubao_client: Any | None = None,
    provider: Any | None = None,
    as_of: str | None = None,
    max_retries: int = 2,
) -> FastAPI:
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

    # 进程级资源挂到 app.state
    app.state.db_path = db_path or cfg.db_path()
    app.state.doubao_client = doubao_client
    app.state.provider = provider
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

    # 路由分组挂载(Task 5/6/8/9/10 各自填充内部端点)
    from rivalradar.api.reads import router as reads_router
    from rivalradar.api.runs import router as runs_router
    from rivalradar.api.annotations import router as annotations_router
    app.include_router(reads_router)
    app.include_router(runs_router)
    app.include_router(annotations_router)

    return app
