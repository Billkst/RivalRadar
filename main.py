"""RivalRadar API server entry. 启动:.venv/bin/python main.py

环境变量:
  ARK_API_KEY=...        可选,Doubao key(未设时走 BYOK:请求自带 X-LLM-* 三头)
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


def _ensure_localhost_bypasses_proxy() -> None:
    """只做一件事:保证**自调用**(localhost)不过代理。代理策略本身交给环境变量。

    **曾经的做法是启动即清空所有代理 env**,理由是让豆包端点(ark.cn-beijing.volces.com,
    境内地址)直连,不被 Clash fake-ip 路由到海外卡死 60-120s。那在「只有豆包一个厂商」的
    年代是对的,注释也言之成理 —— 但它把「哪些主机走代理」这个**运维决策焊死进了应用代码**。

    BYOK 之后 LLM 端点变成任意厂商,这个硬编码立刻反噬:
      - api.deepseek.com 在本机**直连不通**(实测 12s 超时),走代理 0.14s 就通 —— 清了代理
        它就永远连不上,SDK 还默认重试 2 次,一次连通性测试要卡 46s 才报 timeout,
        看起来像「厂商挂了」;
      - 更讽刺的是,**豆包自己现在也直连不通了**(实测同样超时,走代理 0.28s 通)——
        网络环境早变了,而这行「网络常识」还留在代码里,因为它当初是对的,没人会去质疑。

    结论:应用不该假装自己懂网络拓扑。尊重 http_proxy / https_proxy / NO_PROXY 的标准契约,
    由开发机 / Render / Docker 各自决定。唯一必须由应用兜底的是 localhost —— 自调用走代理
    必然 502,且这跟部署在哪无关。
    """
    hosts = ["localhost", "127.0.0.1"]
    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    # merge 而非 setdefault:环境已设了 NO_PROXY 时 setdefault 是空操作,localhost 就漏了。
    merged = ",".join(dict.fromkeys(
        [h for h in (p.strip() for p in existing.split(",")) if h] + hosts))
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


def main():
    _ensure_localhost_bypasses_proxy()

    # BYOK:env key 可选。未配 ARK_API_KEY 时 doubao_client=None,
    # 请求必须自带 X-LLM-* 三头(否则 503 指引前端「模型设置」)。
    app = create_app(
        db_path=cfg.db_path(),
        doubao_client=cfg.get_doubao_client() if cfg.ark_api_key() else None,
        provider=_build_provider(),
    )
    # 云平台(Render/Railway 等)注入 $PORT;本地无 $PORT 时回退 RIVALRADAR_PORT。
    _cloud_port = os.getenv("PORT")
    port = int(_cloud_port or os.getenv("RIVALRADAR_PORT", "8000"))
    # 本地默认绑 127.0.0.1 防 LAN 暴露(POST /run 无 auth + 无上限会被烧 API 配额);
    # 云平台注入 $PORT 时必须绑 0.0.0.0 平台才路由得进来,据此切默认值。仍可被 RIVALRADAR_HOST 覆盖。
    host = os.getenv("RIVALRADAR_HOST", "0.0.0.0" if _cloud_port else "127.0.0.1")
    print(f"[RivalRadar] starting on http://{host}:{port}  (key configured: {bool(cfg.ark_api_key())})")
    print("[RivalRadar] BYOK 已启用:请求可自带 X-LLM-Base-URL / X-LLM-API-Key / X-LLM-Model 三头覆盖模型配置")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
