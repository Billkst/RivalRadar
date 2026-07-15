"""Run 触发 + 列表 + 详情 + SSE 流。"""
from __future__ import annotations

import sqlite3
import threading
import time
import uuid

import openai
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from rivalradar.agents.discover import DiscoverySet, discover_competitors
from rivalradar.api.deps import (
    LLMSettings, close_byok_client, get_db_conn, get_llm, get_provider, get_as_of,
    get_max_retries,
)
from rivalradar.api.schemas import DiscoverRequest, RunDetail, RunRequest, RunSummary
from rivalradar.api.sse import (
    _ACTIVE_RUN_CONTROLS, _ACTIVE_RUN_TASKS, _replay_from_trace, graph_event_stream,
)
from rivalradar.llm.redact import redact
from rivalradar.llm.structured import _DEFAULT_MAX_TOKENS, StructuredCallError
from rivalradar.graph.build import build_research_graph
from rivalradar.storage import repository as repo
from rivalradar.storage.repository import create_run
from rivalradar.storage.repository import get_run as _get_run

router = APIRouter(tags=["runs"])


@router.post("/run")
def post_run(
    req: RunRequest,
    conn: sqlite3.Connection = Depends(get_db_conn),
    llm: LLMSettings = Depends(get_llm),
    provider=Depends(get_provider),
    as_of: str = Depends(get_as_of),
    max_retries: int = Depends(get_max_retries),
) -> EventSourceResponse:
    """触发一次完整调研,SSE 流式回推每节点进度,直到 done/error。"""
    run_id = "run_" + uuid.uuid4().hex[:12]
    create_run(conn, run_id, req.competitors, req.dimensions,
               decision_context=req.decision_context)
    graph = build_research_graph(
        conn=conn, client=llm.client, model=llm.model, provider=provider,
        as_of=as_of, max_retries=max_retries,
    )
    initial = {
        "competitors": req.competitors,
        "dimensions": req.dimensions,
        "evidence": [],
        "retry_count": 0,
        "decision_context": req.decision_context,  # full-C:decide 节点 grounding(Epic 2)
    }
    config = {"configurable": {"thread_id": run_id}}
    return EventSourceResponse(
        graph_event_stream(graph, initial, config, run_id, conn=conn),
        ping=15,  # context7 验证的 keep-alive 默认,投影场景必备
    )


@router.post("/discover-competitors", response_model=DiscoverySet)
def post_discover(
    req: DiscoverRequest,
    llm: LLMSettings = Depends(get_llm),
) -> DiscoverySet:
    """引导式 setup 第①步(Epic 1.1):种子产品 → LLM 建议直接竞品 + 一句话理由。

    诚实(plan T4):只返建议,前端让用户勾选增删确认后才 POST /run。LLM 不通时
    返 503(非静默空列表)—— 前端据此提示"手动输入竞品名"兜底。
    """
    try:
        return discover_competitors(
            req.seed, req.industry_hint, client=llm.client, model=llm.model)
    except StructuredCallError as err:
        if llm.source == "byok":
            # BYOK:err 文本在 structured_call 内已按本次 client 的 key 脱敏,可回显。
            # 曾只回一句「检查 base_url / API Key / 模型名」—— 三样全对时(ping 通、
            # 真调被厂商 400 拒)用户被指去检查根本没错的东西,真实拒因被吞在这里。
            # 「竞品发现失败:」前缀由前端加(RunsPage),这里只回拒因本身,防双重前缀。
            raise HTTPException(503, str(err)[:300])
        # env fallback:err 可能含 DOUBAO_MODEL endpoint ID(视同 KEY 敏感),保持笼统。
        raise HTTPException(503, "竞品发现暂时不可用,请手动输入竞品名")
    finally:
        close_byok_client(llm)  # 一次性端点:BYOK client 用完即关(env 单例不关)


# ── BYOK 连通性测试 ─────────────────────────────────────────────────────────
def _llm_secrets(request: Request, llm: LLMSettings) -> tuple[str | None, ...]:
    """本次调用需从错误文本里打掉的敏感值:

    - BYOK 头里的 key + 实际 client 的 key(火山方舟 UUID 形态,sk- 正则打不到);
    - env fallback 时 model 即 DOUBAO_MODEL endpoint ID(项目纪律视同 KEY 敏感,
      见 [[api-key-no-leak]]);BYOK 用户自己的模型名不敏感,回显助排错,不打。
    """
    secrets = [request.headers.get("X-LLM-API-Key"),
               getattr(llm.client, "api_key", None)]
    if llm.source == "env":
        secrets.append(llm.model)
    return tuple(secrets)


# /llm/ping 是无鉴权公开端点,且是 sync 路由(跑在共享 AnyIO 线程池里):攻击者填一个
# 只接受 TCP 连接、永不响应的黑洞域名(能过 SSRF 域名校验),并发打就能以 15s/请求占满
# 线程池、拖停全站(对抗评审)。并发闸:满了立即 429 分类,不排队、不占线程。
_PING_GATE = threading.BoundedSemaphore(4)


@router.post("/llm/ping")
def llm_ping(request: Request) -> dict:
    """BYOK 连通性测试:恒 HTTP 200,ok/error_type 给前端「模型设置」测试按钮消费。

    头解析与其他端点一致(缺头/坏 base_url 照常 422);唯独"完全未配置"
    返 200 分类结果 unconfigured 而非 503,前端测试按钮统一按分类渲染。

    **max_tokens 必须发真 run 会发的那个值,而不是 1。** 原先发 1 → 任何厂商都必过 →
    「测试通过、真跑就死」:真 run 的 structured_call 按 131072 要额度(方舟端点的实测硬
    上限),换到 DeepSeek/OpenAI 一律 400。一个不测真参数的连通性测试只是自我安慰。
    经 cap_client 钳制后这里实际发出的是 min(131072, 用户声明的厂商上限) —— 与真 run
    逐字节一致。上限填错了,点一下按钮当场 400,而不是花几分钟跑一个必死的 run。
    """
    try:
        llm = get_llm(request)
    except HTTPException as e:
        if e.status_code == 503:  # 无头 + 无 env fallback → 分类结果而非报错
            return {"ok": False, "error_type": "unconfigured",
                    "detail": str(e.detail)[:200]}
        raise
    if not _PING_GATE.acquire(blocking=False):
        # 不排队:排队本身就占线程池,正是要防的资源占用形态。
        # 提前 return 走不到下方 finally —— BYOK client 在这里就得关,否则 busy 风暴期间
        # 每个被拒请求都漏一个连接池。
        close_byok_client(llm)
        return {"ok": False, "error_type": "busy",
                "detail": "连通性测试并发已满,稍候几秒再点"}
    try:
        secrets = _llm_secrets(request, llm)
        t0 = time.perf_counter()
        try:
            resp = llm.client.chat.completions.create(
                model=llm.model,
                messages=[{"role": "user", "content": "ping"}],
                # 只是上限;但「prompt 短 = 只吐几个 token」对默认开 thinking 的模型(如
                # DeepSeek V4 系)不成立 —— 思考 token 计入输出、是延迟主因。所以成功时把
                # completion_tokens 一并返回,让「XXXms」可归因(慢在思考,还是慢在网络)。
                max_tokens=_DEFAULT_MAX_TOKENS,
                timeout=15,
            )
        except openai.AuthenticationError as e:
            return {"ok": False, "error_type": "auth", "detail": redact(str(e), *secrets)[:200]}
        except openai.NotFoundError as e:
            return {"ok": False, "error_type": "not_found", "detail": redact(str(e), *secrets)[:200]}
        except openai.BadRequestError as e:
            # 400:参数被厂商拒。BYOK 换厂商时最常见的一条 —— 多半是输出上限没声明/填太大。
            return {"ok": False, "error_type": "bad_request",
                    "detail": redact(str(e), *secrets)[:200]}
        except openai.APITimeoutError as e:  # 必须先于 APIConnectionError(是其子类)
            return {"ok": False, "error_type": "timeout", "detail": redact(str(e), *secrets)[:200]}
        except openai.APIConnectionError as e:
            return {"ok": False, "error_type": "connection", "detail": redact(str(e), *secrets)[:200]}
        except Exception as e:  # noqa: BLE001 — 分类兜底,detail 已脱敏
            return {"ok": False, "error_type": "other", "detail": redact(str(e), *secrets)[:200]}
        out: dict = {"ok": True, "latency_ms": int((time.perf_counter() - t0) * 1000)}
        usage = getattr(resp, "usage", None)
        if usage is not None and getattr(usage, "completion_tokens", None) is not None:
            out["completion_tokens"] = usage.completion_tokens
        choices = getattr(resp, "choices", None)
        if choices and getattr(choices[0].message, "reasoning_content", None):
            out["thinking"] = True  # 只回布尔,不回思考内容(KEY 纪律:响应体不带模型输出)
        return out
    finally:
        _PING_GATE.release()
        close_byok_client(llm)  # 一次性端点:BYOK client 用完即关(env 单例不关)


@router.get("/stream/{run_id}")
def get_stream(
    run_id: str,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> EventSourceResponse:
    """从 trace 表回放已结束 run 的事件流(§11.4 'Play 回放')。"""
    if _get_run(conn, run_id) is None:
        raise HTTPException(404, "run not found")
    return EventSourceResponse(
        _replay_from_trace(conn, run_id),
        ping=15,
    )


@router.get("/runs", response_model=list[RunSummary])
def list_runs(conn: sqlite3.Connection = Depends(get_db_conn)) -> list[dict]:
    return repo.list_runs(conn)


@router.get("/run/{run_id}", response_model=RunDetail)
def get_run(run_id: str,
            conn: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    r = repo.get_run(conn, run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    # degraded:repo.get_run 已返 db 持久化的「蕴含降级」标志,再 OR status==degraded
    # 兼容种数据(只 update_run_status 没经 finalize 的路径,如 fixture 直接造的)
    r["degraded"] = r["degraded"] or r["status"] == "degraded"
    return r


@router.delete("/run/{run_id}")
async def delete_run(
    run_id: str,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> dict:
    """整条删除一个 run 及其全部关联数据(用户在历史列表手动删除,带前端二次确认)。

    破坏性操作:级联删 evidence/analysis/report/qc/insight/decisions/trace/annotations。
    run 不存在 → 404。**运行中拒删 → 409**(对抗审查 P1,Claude+Codex 跨模型一致):协作式
    取消挡不住一个已过检查点、正在 sync 写库的 worker 线程,删除后它仍会写出无父 runs 行的
    孤儿 analysis/report/trace(schema 无 FK 级联)。故运行中不直接删,让用户先 POST /cancel
    (置 cancelled 终态 + SSE 收尾,所有 worker 停),再删 → 杜绝孤儿。非运行中(终态)的 run
    finalize 已跑完、无在飞 worker,删除安全。
    """
    run = _get_run(conn, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    if run["status"] == "running":
        raise HTTPException(409, "运行中不可删除,请先取消该调研再删除")
    if not repo.delete_run(conn, run_id):
        raise HTTPException(404, "run not found")  # get→delete 间被并发删:幂等返 404
    return {"run_id": run_id, "deleted": True}


@router.post("/run/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> dict:
    """F4 修订:真中断 in-flight LLM stream + 持久化 cancelled 状态。

    实施:
      1. 从 _ACTIVE_RUN_TASKS 查 SSE 生成器 task,call task.cancel() 抛 CancelledError
         到生成器执行栈,顺着 await 链中断 in-flight `await llm.chat.create(...)` /
         `await provider.search(...)`(sqlite flag 只在 step 间生效,无法切网络层 await)
      2. DB CAS `mark_run_cancelled('running' → 'cancelled')`,即使 task 已结束也尝试
         (timing race:user 点 cancel 时 run 刚好 finalize 完;CAS 保证不覆盖终态)
      3. 返回 {run_id, cancelled, db_cancelled} — 前端 F4 mitigation 不等此响应即切 UI
         cancelled state,响应仅作 source of truth 让后续 GET /run/:id 一致

    无需 404:已结束的 run cancel 是 no-op,语义清晰返 cancelled=False / db_cancelled=False。
    """
    # post-real-run-7:协作式取消才能真停在飞 LLM。置 RunControl → 包装后的 client 在下一次
    # create() 前抛 RunAborted('cancelled'),最多再等 1 个在飞的 90s 调用(而非旧版整轮 5×90s
    # 空磨)。task.cancel() 保留作 between-node await 边界的兜底(穿不透同步 LLM 阻塞,见 runcontrol)。
    ctl = _ACTIVE_RUN_CONTROLS.get(run_id)
    if ctl is not None:
        ctl.cancel()
    task = _ACTIVE_RUN_TASKS.get(run_id)
    cancelled = False
    if task is not None and not task.done():
        task.cancel()
        cancelled = True
    db_cancelled = repo.mark_run_cancelled(conn, run_id)
    return {
        "run_id": run_id,
        "cancelled": cancelled,        # 是否实际 cancel 了 in-flight task
        "db_cancelled": db_cancelled,  # 是否实际写了 cancelled 状态(CAS)
    }
