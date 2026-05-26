"""RivalRadar API server entry. 启动:.venv/bin/python main.py

环境变量:
  ARK_API_KEY=...        必填,Doubao key
  TAVILY_API_KEY=...     必填(或 EXA_API_KEY)
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
