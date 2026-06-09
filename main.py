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
    # WSL2 + Clash 兜底:启动即清代理 env,确保 Doubao(ark.cn-beijing.volces.com)/ Tavily 走直连,
    # 不被 Clash fake-ip 路由海外卡死(60-120s);localhost 自调用也不过代理。无论 Clash 开/关、
    # 无论走 scripts/dev-backend.sh 还是裸 `python main.py` 都成立(client 在下面 create_app 时才建,
    # 此时 env 已清)。codex / DiceBear 那类需代理的是独立 CLI/一次性抓取,不在后端进程内。
    for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        os.environ.pop(_k, None)
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,ark.cn-beijing.volces.com,api.tavily.com")
    os.environ.setdefault("no_proxy", os.environ["NO_PROXY"])

    if not cfg.ark_api_key():
        raise RuntimeError("ARK_API_KEY 未设置(放进 .env)")
    app = create_app(
        db_path=cfg.db_path(),
        doubao_client=cfg.get_doubao_client(),
        provider=_build_provider(),
    )
    # 云平台(Render/Railway 等)注入 $PORT;本地无 $PORT 时回退 RIVALRADAR_PORT。
    _cloud_port = os.getenv("PORT")
    port = int(_cloud_port or os.getenv("RIVALRADAR_PORT", "8000"))
    # 本地默认绑 127.0.0.1 防 LAN 暴露(POST /run 无 auth + 无上限会被烧 API 配额);
    # 云平台注入 $PORT 时必须绑 0.0.0.0 平台才路由得进来,据此切默认值。仍可被 RIVALRADAR_HOST 覆盖。
    host = os.getenv("RIVALRADAR_HOST", "0.0.0.0" if _cloud_port else "127.0.0.1")
    print(f"[RivalRadar] starting on http://{host}:{port}  (key configured: {bool(cfg.ark_api_key())})")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
