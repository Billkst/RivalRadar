#!/usr/bin/env bash
# 启动后端 FastAPI 服务(默认 http://127.0.0.1:8000)。从仓库任意目录运行均可。
#
# 注意:无 --reload —— 改了后端代码(rivalradar/** 或 main.py)后必须重启本进程才生效。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# WSL2 + Clash 兜底:清掉代理环境变量,避免
#   (1) localhost 自调用被代理拦截;
#   (2) Doubao(ark.cn-beijing.volces.com)被 Clash fake-ip 路由到海外慢路径而卡死。
# Doubao / Tavily 走直连最稳,故一并列入 NO_PROXY。
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY="localhost,127.0.0.1,ark.cn-beijing.volces.com,api.tavily.com"
export no_proxy="$NO_PROXY"

[ -x .venv/bin/python ] || { echo "✗ 缺 .venv/bin/python:先 python -m venv .venv && .venv/bin/pip install -e ."; exit 1; }
[ -f .env ] || echo "⚠ 未发现 .env(后端需要 ARK_API_KEY / TAVILY_API_KEY,否则启动即报错)"

echo "[backend] http://127.0.0.1:${RIVALRADAR_PORT:-8000}   (无 --reload:改后端代码后请重启本进程)"
exec .venv/bin/python main.py
