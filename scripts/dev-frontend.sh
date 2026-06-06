#!/usr/bin/env bash
# 启动前端 Vite dev server(http://localhost:3000),/api/* 自动代理到后端 :8000。
# HMR 自动热更;需后端 :8000 已在运行。从仓库任意目录运行均可。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

# 清代理:前端只走 localhost(代理到后端),Clash 代理会干扰本地回环。
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY="localhost,127.0.0.1"
export no_proxy="$NO_PROXY"

[ -d node_modules ] || { echo "✗ 缺 node_modules:先 cd frontend && npm install"; exit 1; }

echo "[frontend] http://localhost:3000   (HMR 热更;确保后端 :8000 已启动)"
exec npm run dev
