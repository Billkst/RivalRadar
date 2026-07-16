#!/usr/bin/env bash
# RivalRadar 统一验证入口。默认执行后端与前端全部可用门禁。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-all}"

usage() {
  echo "用法: ./scripts/verify.sh [backend|frontend|all]" >&2
}

resolve_python() {
  if [ -n "${RIVALRADAR_PYTHON:-}" ]; then
    echo "$RIVALRADAR_PYTHON"
  elif [ -x "$ROOT/.venv/bin/python" ]; then
    echo "$ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    echo "找不到 Python。请创建 .venv，或设置 RIVALRADAR_PYTHON。" >&2
    return 1
  fi
}

check_asyncio_runtime() {
  local python_bin="$1"
  "$python_bin" - <<'PY'
import socket
import sys

reader, writer = socket.socketpair()
try:
    try:
        writer.send(b"\0")
    except PermissionError:
        print(
            "当前运行环境禁止本地 socketpair 写入，AnyIO/TestClient 会永久等待。"
            "请在正常终端或允许本地进程间 socket 通信的 CI 中重跑后端验证。",
            file=sys.stderr,
        )
        raise SystemExit(78)
    if reader.recv(1) != b"\0":
        raise SystemExit("socketpair preflight 返回了意外数据")
finally:
    reader.close()
    writer.close()
PY
}

run_backend() {
  local python_bin
  local test_db
  python_bin="$(resolve_python)"
  test_db="${TMPDIR:-/tmp}/rivalradar-verify-$$.db"

  local -a clean_env=(
    env
    PYTHONDONTWRITEBYTECODE=1
    PYTHON_DOTENV_DISABLED=1
    ARK_API_KEY=
    ARK_BASE_URL=https://example.invalid/v1
    DOUBAO_MODEL=ep-test-dummy-placeholder
    TAVILY_API_KEY=
    EXA_API_KEY=
    DATABASE_URL=
    "RIVALRADAR_DB=$test_db"
    "RIVALRADAR_TEST_DB=$test_db"
  )

  echo "==> version consistency"
  (
    cd "$ROOT"
    "${clean_env[@]}" "$python_bin" scripts/check-version.py
  )

  check_asyncio_runtime "$python_bin"

  echo "==> backend pytest"
  (
    cd "$ROOT"
    "${clean_env[@]}" "$python_bin" -m pytest tests -p no:cacheprovider
  )
}

run_frontend() {
  local pnpm_bin="${RIVALRADAR_PNPM:-pnpm}"
  if [[ "$pnpm_bin" != */* ]]; then
    pnpm_bin="$(command -v "$pnpm_bin")" || {
      echo "找不到 pnpm。请安装 package.json 声明的版本，或设置 RIVALRADAR_PNPM。" >&2
      return 1
    }
  elif [ ! -x "$pnpm_bin" ]; then
    echo "RIVALRADAR_PNPM 不可执行: $pnpm_bin" >&2
    return 1
  fi

  echo "==> frontend typecheck"
  (cd "$ROOT/frontend" && "$pnpm_bin" typecheck)
  echo "==> frontend lint"
  (cd "$ROOT/frontend" && "$pnpm_bin" lint)
  echo "==> frontend build"
  (cd "$ROOT/frontend" && "$pnpm_bin" build)
}

case "$MODE" in
  backend)
    run_backend
    ;;
  frontend)
    run_frontend
    ;;
  all)
    run_backend
    run_frontend
    ;;
  *)
    usage
    exit 2
    ;;
esac
