#!/usr/bin/env bash
# 停掉本地开发服务:后端 :8000 与前端 :3000。
# 按端口取监听 PID 精确 kill —— 绝不用 pkill -f(会误杀当前 shell / 其它 python/node 进程)。
set -uo pipefail

for port in 8000 3000; do
  pids=$(ss -ltnp 2>/dev/null | grep ":$port " | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
  if [ -n "$pids" ]; then
    echo "停 :$port → PID $(echo "$pids" | tr '\n' ' ')"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
  else
    echo ":$port 未在监听"
  fi
done
