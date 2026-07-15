"""FastAPI 依赖注入(per-request 资源 + 全局工厂)。

每请求一个 SQLite 连接(WAL 模式下并发读 + 单写安全);Doubao client 与
Provider 由 app.state 持有(进程级),通过 Depends 拿到 request.app.state。
"""
from __future__ import annotations

import ipaddress
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request
from openai import OpenAI

# IDNA 三个替代标签分隔符(RFC 3490):表意句号 / 全角句号 / 半角表意句号 → ASCII '.'
_IDNA_SEPARATORS = {ord("。"): ".", ord("．"): ".", ord("｡"): "."}

from rivalradar.config import doubao_model
from rivalradar.llm.limits import cap_client
from rivalradar.storage.db import connect, init_db


def get_db_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """每请求一条连接;请求结束关闭。db_path 由 app.state.db_path 注入。"""
    conn = connect(request.app.state.db_path)
    try:
        init_db(conn)  # idempotent;PRAGMA WAL 也在这里施加。放 try 内:PG 上 init_db
        # 若抛错(DDL 权限/网络抖动)也会经 finally 关连接,防 Supabase pooler 连接泄漏耗尽。
        yield conn
    finally:
        conn.close()


# ── BYOK(Bring Your Own Key):X-LLM-* 三请求头,全有或全无 ─────────────────
_BYOK_HEADER_NAMES = ("X-LLM-Base-URL", "X-LLM-API-Key", "X-LLM-Model")
_BAD_BASE_URL_DETAIL = "base_url 不合法:仅支持域名形式的 https 端点(明文 http / IP 直连一律拒)"

# 第 4 个头:**可选**,不进「全有或全无」契约(缺它只是不钳上限,不是配置不全)。
# 声明本厂商的输出 token 上限 —— structured.py 的 131072 是方舟端点的硬上限,对别家一律
# 过大会 400。详见 rivalradar/llm/limits.py。
_BYOK_MAX_TOKENS_HEADER = "X-LLM-Max-Tokens"
_MAX_TOKENS_CEILING = 1_048_576  # 上界只防手滑/恶意的荒谬值,不代表任何厂商的真实能力


def _parse_max_tokens(raw: str | None) -> int | None:
    """解析可选的输出上限头。缺省 → None(不钳);非法 → 422(而非静默忽略:静默会让用户
    以为设了上限,真 run 却仍按 131072 发出去被厂商 400,排查成本极高)。"""
    if raw is None or raw == "":
        return None
    try:
        n = int(raw)
    except ValueError:
        raise HTTPException(422, f"{_BYOK_MAX_TOKENS_HEADER} 必须是正整数")
    if not 1 <= n <= _MAX_TOKENS_CEILING:
        raise HTTPException(422, f"{_BYOK_MAX_TOKENS_HEADER} 超出范围(1–{_MAX_TOKENS_CEILING})")
    return n


@dataclass
class LLMSettings:
    """一次请求实际使用的 LLM 配置。source:env=进程级 Doubao 单例;byok=请求头自带。

    没有 max_output_tokens 字段 —— 上限**已经钳进 client 里了**(cap_client),
    下游拿到的 client 直接就是安全的,不需要也不应该再各自去读上限值。
    """
    client: Any
    model: str
    source: str = "env"  # "env" | "byok"


def _validate_base_url(base_url: str) -> None:
    """SSRF 校验(云端防打内网 metadata):只放行域名形式的 **https** 端点。

    host 是 IP 字面量(IPv4/IPv6)、localhost、或数字型 IP 编码一律拒;scheme 必须 https
    (明文 http 会让 BYOK key 在网线上裸奔,评审 P1)。

    **为什么不做「本地 DNS 解析 + 私有段判断」**(标准 SSRF 手法,评审建议过):本项目外网
    强制走代理(Clash / 部署侧 egress),DNS 解析发生在**代理端**,本地 getaddrinfo 拿到的是
    fake-ip(实测 api.deepseek.com → 198.18.3.41,is_reserved=True)。拿它做私有段判断会把
    每个合法厂商端点误判成内网拒掉,且真正的连接目标由代理另行解析 —— 这个检查在代理拓扑下
    既误杀又无效。真正的 egress 管控属于部署层(代理白名单),不该焊进应用。
    **已知残余**:A 记录指向内网的域名(无代理直连部署时)/ DNS rebinding —— 见 TODOS。
    重定向到内网这一路已由 client 的 follow_redirects=False 堵死(见 get_llm)。
    """
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname  # 恶意构造(如未闭合的 [::1)会抛 ValueError
    except ValueError:
        raise HTTPException(422, _BAD_BASE_URL_DETAIL)
    if parsed.scheme != "https" or not host:
        raise HTTPException(422, _BAD_BASE_URL_DETAIL)
    # Unicode/IDNA 归一化:'169。254。169。254'(表意句号 U+3002)、全角 '０x７f' 等在
    # ASCII split('.') 下不被识破,但按 IDNA(NFKC + 替代分隔符)会还原成 169.254.169.254 /
    # 127.0.0.1(评审 F1)。**纵深防御**:HTTP 头值是 latin-1,原始 Unicode 经头传不进来
    # (会被 mojibake),此归一化防的是将来 base_url 改从 JSON/query(UTF-8 原样)传入的情形。
    host = unicodedata.normalize("NFKC", host).translate(_IDNA_SEPARATORS)
    # FQDN 根点归一:'169.254.169.254.' 在 ipaddress 眼里不是字面量,但 OS 解析器
    # 照样把它送到 169.254.169.254(尾点绕过)。去尾点再校验。
    host = host.rstrip(".")
    if not host or host == "localhost":
        raise HTTPException(422, _BAD_BASE_URL_DETAIL)
    # 数字型 IP 编码绕过:十进制(2852039166)/ 十六进制(0xA9FEA9FE)/ 点分变体
    # ('127.1' / '0177.0.0.1' / '0x7f.0.0.1')都会被 ipaddress.ip_address(str) 判为
    # "非字面量"而放行,但 inet_aton 语义的 OS 解析器把它们映射到真 IP
    # (2852039166 → 169.254.169.254 云 metadata;'127.1' → 127.0.0.1)。合法公网域名
    # 的 TLD 必含字母 —— **每个点分段**都是纯数字 / 0x 十六进制的 host 一律拒。
    if all(re.fullmatch(r"\d+|0[xX][0-9a-fA-F]*", label) for label in host.split(".")):
        raise HTTPException(422, _BAD_BASE_URL_DETAIL)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return  # 解析失败 = 不是 IP 字面量 = 域名,放行
    raise HTTPException(422, _BAD_BASE_URL_DETAIL)


def get_llm(request: Request) -> LLMSettings:
    """解析 BYOK 三请求头 → per-request client;无头则 fallback 到 env 单例。

    契约(前后端共守):三头齐全走 BYOK;只给 1-2 个 → 422(防静默 fallback
    让用户以为在用自己配的模型);全无 → app.state.doubao_client,None → 503。
    🔑 KEY 纪律:key 只活在本次请求内存里,绝不落库 / 日志 / SSE / 响应。
    """
    base_url, api_key, model = (request.headers.get(h) for h in _BYOK_HEADER_NAMES)
    present = sum(1 for v in (base_url, api_key, model) if v)
    if present == 3:
        _validate_base_url(base_url)
        cap = _parse_max_tokens(request.headers.get(_BYOK_MAX_TOKENS_HEADER))
        # 上限在这里就钳进 client —— 下游(structured_call / ping / 各 agent)拿到的
        # client 天然安全,无需逐处传参,厂商差异不外溢。
        # max_retries=0:重试策略已经活在 structured_call 里(3 次应用层尝试)——SDK 默认
        # 再自带 2 次 HTTP 重试会叠成最坏 9 次真请求,三倍烧 BYOK 用户的钱;且 /llm/ping
        # 是无鉴权同步端点,默认重试让一次指向黑洞域名的 ping 占线程池工人 ~46s(红队)。
        # follow_redirects=False:OpenAI SDK 默认跟随重定向(实测 True),否则「域名过校验 →
        # 302 跳内网 169.254.169.254」可绕过 _validate_base_url(评审)。自带 httpx client
        # 仍 trust_env=True → 照常读代理环境变量,不打断 BYOK 依赖的代理链路。
        http_client = httpx.Client(follow_redirects=False)
        return LLMSettings(
            client=cap_client(
                OpenAI(api_key=api_key, base_url=base_url, max_retries=0,
                       http_client=http_client), cap),
            model=model, source="byok")
    if present:
        raise HTTPException(
            422,
            "BYOK 模式需同时提供 X-LLM-Base-URL / X-LLM-API-Key / X-LLM-Model 三个请求头")
    env_client = request.app.state.doubao_client
    if env_client is None:
        raise HTTPException(503, "未配置模型:请点击右上角「模型设置」配置你的 API Key")
    try:
        model = doubao_model()
    except ValueError:
        # 配了 ARK client 却漏设 DOUBAO_MODEL:也视为"未配置",返 503 而非让
        # ValueError 穿透成 500(保 /llm/ping 恒 200 契约、与 post_run 返 503 一致)。
        raise HTTPException(503, "未配置模型:请点击右上角「模型设置」配置你的 API Key")
    return LLMSettings(client=env_client, model=model, source="env")


def get_provider(request: Request):
    """复用 app.state 上的搜索 provider。"""
    return request.app.state.provider


def get_as_of(request: Request) -> str:
    return request.app.state.as_of


def get_max_retries(request: Request) -> int:
    return request.app.state.max_retries
