#!/usr/bin/env bash
# 启动后端 FastAPI 服务(默认 http://127.0.0.1:8000)。从仓库任意目录运行均可。
#
# 注意:无 --reload —— 改了后端代码(rivalradar/** 或 main.py)后必须重启本进程才生效。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ── 代理策略(开发机专用;生产不跑这个脚本)───────────────────────────────────
#
# 曾经这里是 `unset` 掉所有代理 + 把 ark/tavily 写死进 NO_PROXY,理由是让豆包端点直连、
# 别被 Clash 路由到海外卡死。那在「只有豆包一个厂商」时是对的,但 BYOK 之后 LLM 端点变成
# 任意厂商 —— 而本机 **api.deepseek.com 直连根本不通,只有走代理才通**(实测:直连 12s 超时,
# 走代理 0.14s)。清掉代理 = DeepSeek 永远连不上,SDK 还默认重试 2 次 → 一次连通性测试卡 46s
# 才报 timeout,看起来像「厂商挂了」。更讽刺的是**豆包如今自己也直连不通了** —— 网络环境早变了,
# 那行「网络常识」却因为当初是对的而没人再质疑。
#
# 现在的分工:
#   - 应用(main.py)**不猜网络拓扑**,只保证 localhost 自调用不过代理,其余尊重环境变量。
#     它不去嗅探代理 —— 「某端口有人监听」推不出「这是我信任的代理」,而猜错意味着把用户的
#     BYOK API Key 送进一个未经声明的中间人。代理是信任决策,必须显式声明。
#   - 本脚本(仅开发机)做那个显式声明:**探测代理端口是否真的活着,活着才用**,并且
#     **把选择打印出来**。猜错只影响本地、一眼可见、随手可覆盖,不会焊进部署到生产的代码。
#
# 覆盖方式:
#   RIVALRADAR_DEV_PROXY=http://127.0.0.1:1080  指定别的代理
#   RIVALRADAR_DEV_PROXY=off                    强制直连
#   或者自己先 export http_proxy=... (已显式设置的一律尊重,本脚本不覆盖)
_DEV_PROXY="${RIVALRADAR_DEV_PROXY:-http://127.0.0.1:7897}"

# 探测**所有**标准代理变量:只设 HTTPS_PROXY / ALL_PROXY(对这些 HTTPS 厂商 API 完全够用)
# 也算显式声明,不能当没设 —— 否则若默认端口恰好有人监听,脚本会 export 一套指向别处的
# 值,悄悄覆盖开发者的显式代理(评审 P2)。
_EXISTING_PROXY="${http_proxy:-${HTTP_PROXY:-${https_proxy:-${HTTPS_PROXY:-${ALL_PROXY:-${all_proxy:-}}}}}}"
if [ -n "$_EXISTING_PROXY" ]; then
  echo "[proxy] 沿用你已设置的代理变量(显式声明优先,不覆盖)"
elif [ "$_DEV_PROXY" = "off" ]; then
  echo "[proxy] 直连(RIVALRADAR_DEV_PROXY=off)"
else
  # 只探 TCP 端口,不发真请求 —— 快,且不依赖任何外部站点可达
  _host="${_DEV_PROXY#*://}"; _port="${_host##*:}"; _host="${_host%%:*}"
  if timeout 1 bash -c "exec 3<>/dev/tcp/${_host}/${_port}" 2>/dev/null; then
    export http_proxy="$_DEV_PROXY" https_proxy="$_DEV_PROXY" ALL_PROXY="$_DEV_PROXY"
    echo "[proxy] 检测到代理存活 → 外网走 $_DEV_PROXY(localhost 自动绕过)"
  else
    echo "[proxy] ${_DEV_PROXY} 未监听 → 直连。若 LLM 连不上,先确认代理是否开着"
  fi
fi
# localhost 永远绕过代理(自调用走代理必 502)。main.py 里也会兜底 merge 一次。
export NO_PROXY="localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
# ─────────────────────────────────────────────────────────────────────────────

[ -x .venv/bin/python ] || { echo "✗ 缺 .venv/bin/python:先 python -m venv .venv && .venv/bin/pip install -e ."; exit 1; }
# BYOK 之后 ARK_API_KEY 不再必填:没配就由前端「模型设置」自带 X-LLM-* 头。TAVILY 仍必填。
[ -f .env ] || echo "⚠ 未发现 .env(后端需要 TAVILY_API_KEY;ARK_API_KEY 可选,BYOK 模式由前端自带 key)"

echo "[backend] http://127.0.0.1:${RIVALRADAR_PORT:-8000}   (无 --reload:改后端代码后请重启本进程)"
exec .venv/bin/python main.py
