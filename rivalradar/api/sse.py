"""LangGraph astream → SSE chunk 序列化。

设计原则(必读):
- 事件本身只携带「前端动画必需的轻量摘要」(node + 计数/verdict/status),不
  传整张 state(几 KB → 几十 B),给 §11.4 实时 DAG 用。前端需要详情时另调
  GET /evidence/:id / /analysis/:run / /report/:run / /trace/:run。
- 任何 astream 异常先发 'error' 事件给前端,然后 **clean exit**(不 re-raise)——
  前端能显示「失败原因」而非「连接突然断了」;sse-starlette task group 因
  body_iterator 自然完成走优雅关停,error chunk 已 flush 给客户端。
- **绝不 re-raise**:会让 ASGI 错误路径介入(TestClient 直接抛回调用方,
  uvicorn log + abort 连接),既无收益又把 e2e 路径搞乱;CancelledError 是
  BaseException 不入此分支,客户端断连仍由 task_group cancel_on_finish 清理。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from rivalradar.storage import repository as repo
from rivalradar.llm.runcontrol import RunAborted, RunControl

logger = logging.getLogger(__name__)


# ── F4 修订:cancel 真中断 ─────────────────────────────────────────────────
# 全局 SSE 生成器 task 注册表,key = run_id。POST /run/{id}/cancel 通过这查找
# task 并调 task.cancel(),抛 CancelledError 到生成器执行栈,中断 in-flight
# `await llm_client.chat.create(...)` / `await provider.search(...)` —— sqlite
# flag 只在 step 之间生效(等 60-120s),无法切断网络层 await。
#
# in-memory 不持久化(进程崩了 task 也没了 OK);cancelled 状态由
# storage.repository.mark_run_cancelled CAS 写入 sqlite,供 GET /run/:id 取。
_ACTIVE_RUN_TASKS: dict[str, asyncio.Task] = {}

# post-real-run-7:协作式取消 + 全局墙钟预算的 per-run 控制注册表。POST /cancel 通过这查到
# RunControl 并 .cancel() 置位 → 包装后的 client 在下一次 LLM 调用前抛 RunAborted,真正停掉
# worker 线程里的 5×90s 重试环(asyncio.task.cancel() 穿不透同步 LLM 阻塞调用,见 runcontrol)。
_ACTIVE_RUN_CONTROLS: dict[str, RunControl] = {}

# run 级墙钟预算(秒)。超出 → 包装 client 抛 RunAborted('timeout') → 标 failed,防病态 run
# 无上限磨下去。默认 900s(15min)是"肯定卡死"的兜底,典型 run 2-4min,不误伤慢但在跑的 run。
# 0 或负 = 关闭预算(无 deadline)。可经 RIVALRADAR_RUN_BUDGET_S 调。
def _run_budget_s() -> float:
    try:
        return float(os.getenv("RIVALRADAR_RUN_BUDGET_S", "900"))
    except ValueError:
        return 900.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize_delta(node: str, delta: dict[str, Any]) -> dict[str, Any]:
    """把 state delta 压成前端动画用的小事件。未识别节点透传 node 名。"""
    if node == "collect":
        return {"node": "collect",
                "evidence_added": len(delta.get("evidence", []))}
    if node == "analyze":
        a = delta.get("analysis", {})
        return {"node": "analyze",
                "competitors": len(a.get("competitors", [])),
                "comparison_rows": len(a.get("comparison", []))}
    if node == "write":
        return {"node": "write", "report_chars": len(delta.get("report", ""))}
    if node == "qc":
        qcr = delta.get("qc_result", {})
        issues = qcr.get("issues", [])
        # 35% money shot 关键:不同 problem_type 在 DAG 上视觉不同
        # (缺证据 vs 假说支撑失败 vs 受控本体不符),前端据此差别可视化
        issue_types: dict[str, int] = {}
        for it in issues:
            pt = it.get("problem_type", "unknown")
            issue_types[pt] = issue_types.get(pt, 0) + 1
        return {"node": "qc",
                "verdict": qcr.get("verdict"),
                "issues": len(issues),
                "issue_types": issue_types,
                "retry_count": delta.get("retry_count"),
                "degraded": delta.get("degraded")}
    if node == "decide":
        # full-C 决策节点(Epic 2):前端 cockpit DecisionBoard 据此显示决策数 + 降级态
        ds = delta.get("decisions", {})
        return {"node": "decide",
                "decisions": len(ds.get("decisions", [])),
                "decision_degraded": delta.get("decision_degraded")}
    if node == "finalize":
        return {"node": "finalize",
                "status": delta.get("status"),
                "verdict": delta.get("qc_result", {}).get("verdict")}
    # TODO(Lane E 后续/Day-4):新增 graph node 时需同步在这里加 summary,否则
    # 前端 DAG 动画对应节点只会拿到裸 node 名、缺帧。
    return {"node": node}


async def graph_event_stream(
    graph,
    initial: dict,
    config: dict,
    run_id: str,
    *,
    conn: sqlite3.Connection,
) -> AsyncIterator[dict]:
    """SSE 主流:start → node/progress/chunk events → done(或 error → clean exit)。

    yield 出的 dict 给 sse-starlette EventSourceResponse,字段 'event'/'data'。

    `conn` 用于 (1) graph 崩溃时把 run.status 置为 "failed" 防 zombie run
    永久卡在 "running",以及 (2) done event 携带终态 status 与 replay 路径对称。

    ⚠️ LangGraph **stream_mode="updates"**(默认 v1 行为)契约:chunk 形状是
    `{node_name: state_delta}`(逐 task 直接 yield),与 stream_events(version="v3")
    的 `{"params":{...},"method":...}` 协议层包装**完全不同**。Lane D 的 nodes
    返回值与本实现都按 v1 updates 契约对齐。**切勿改成 stream_events 或 v2/v3
    包装**(会让前端 DAG 整套节点-名 → 动画的对应关系断裂)。

    ── v2 改造(plan v3.2 §5 + Epic 2.2) ────────────────────────────────────
    Queue-driven architecture:
      1. 创建 asyncio.Queue + sync emit() callback
      2. 把 emit 注入 config["configurable"]["emit"],节点可通过 config 取用
         emit("progress",{...}) / emit("chunk",{...}) 实时推 events 进 queue
         (节点不传 emit → 节点 .get("emit") = None,backward compat 测试不破)
      3. Background task 跑 graph.astream(),每个 chunk emit('node', ...) 进 queue
      4. Main task drain queue + yield events 给 SSE,见 DONE_SENTINEL 退出
      5. F4 _ACTIVE_RUN_TASKS[run_id] = graph_task(背景 task),POST /cancel
         调 task.cancel() 顺 await 链中断 in-flight LLM
    """
    queue: asyncio.Queue = asyncio.Queue()
    _DONE_SENTINEL: object = object()
    # emit 来自 worker 线程(analyze/collect 的并行抽取在线程池里调 tick)。asyncio.Queue
    # 不是线程安全的:从非事件循环线程直接 put_nowait,唤醒走 loop.call_soon(非 threadsafe),
    # **唤不醒阻塞在 select() 的事件循环** → 进度事件全憋到循环因别的原因(节点完成/15s 心跳)
    # 醒来才一次性吐出(实测 analyze 161s 期间 10 个事件全延迟到 161s 才送达,UI 看着死机)。
    # 修法:统一经 loop.call_soon_threadsafe 投递——它会主动唤醒事件循环,事件实时送达。
    loop = asyncio.get_running_loop()

    def emit(ev_type: str, data: dict) -> None:
        """Sync emit —— graph nodes 是 sync function,emit 不能 await。
        put_nowait 不 block(asyncio.Queue 无 maxsize 时永不满)。

        Auto-add ts:若 data 未带 ts(node 通常不带),自动注 _now()。reduces
        每个 emit caller 写 `"ts": _now()` 的样板;'node' event 在 run_graph
        内显式给 ts 保持原行为(已带的不覆盖)。
        """
        if "ts" not in data:
            data = {**data, "ts": _now()}
        item = {"event": ev_type, "data": json.dumps(data)}
        # call_soon_threadsafe:从 worker 线程也能唤醒事件循环 → drain 实时收到。
        # 从事件循环线程自身调用同样安全(排进下一拍,FIFO 不乱)。
        loop.call_soon_threadsafe(queue.put_nowait, item)

    # 把 emit 注入 config["configurable"],节点通过 config 取用(non-destructive 浅复制)。
    # per-run 中止控制(协作式取消 + 墙钟预算)。注入 config → 节点把 client 包一层 →
    # 每次 LLM 调用前查取消/超时(见 graph/nodes._run_client + llm/runcontrol)。
    budget = _run_budget_s()
    control = RunControl(deadline=time.monotonic() + budget if budget > 0 else None)
    _ACTIVE_RUN_CONTROLS[run_id] = control

    cfg: dict = dict(config)
    cfg["configurable"] = {**cfg.get("configurable", {}), "emit": emit, "run_control": control}

    async def run_graph() -> None:
        """Background task:跑 graph.astream,每 chunk emit 'node' event 进 queue。
        finally put DONE_SENTINEL 让 main task 退出 drain loop(无论正常 / Exception /
        CancelledError 都 put SENTINEL,保 main task 不死锁在 await queue.get())。"""
        try:
            async for chunk in graph.astream(initial, config=cfg, stream_mode="updates"):
                for node_name, delta in chunk.items():
                    emit("node", {
                        "node": node_name,
                        "summary": _summarize_delta(node_name, delta),
                        "ts": _now(),
                    })
        finally:
            # DONE 也走 call_soon_threadsafe,与上面所有 emit 同一条调度路径 → 保持 FIFO,
            # 不会抢在延后投递的 'node'/'progress' 事件前面(否则 drain 见 DONE 即 break,丢事件)。
            loop.call_soon_threadsafe(queue.put_nowait, _DONE_SENTINEL)

    graph_task: asyncio.Task = asyncio.create_task(run_graph())
    # F4: _ACTIVE_RUN_TASKS 存的是 graph_task(背景 task),POST /cancel 调
    # graph_task.cancel() 抛 CancelledError 到 graph.astream() 内部的 await,
    # 顺着 await 链中断 in-flight LLM/network call。比 current_task(ASGI 生成器
    # task)更精准 —— cancel ASGI task 会关 connection,cancel graph_task 只停 graph。
    _ACTIVE_RUN_TASKS[run_id] = graph_task

    try:
        yield {"event": "start",
               "data": json.dumps({"run_id": run_id, "ts": _now()})}
        try:
            # Drain queue → 收到 _DONE_SENTINEL 就 break。graph 出的 node /
            # progress / chunk events 都通过 queue forward 给 SSE,顺序保持
            # FIFO(asyncio.Queue 保证)。
            while True:
                ev = await queue.get()
                if ev is _DONE_SENTINEL:
                    break
                yield ev
            # Graph task done(可能 raise 了)—— 这里 await propagate 任何 exception
            # 让下面 except 接住。正常完则 await 立即返回 None,继续 yield done event。
            await graph_task
        # 注意:**不**捕获 asyncio.CancelledError(BaseException 子类,不入 Exception
        # 分支)—— sse-starlette task group 在客户端断连 + F4 POST /cancel 触发的中断
        # 路径都通过 CancelledError 直接退出生成器。但 cancel 来时我们仍要清理 graph_task
        # + emit 一个 'cancelled' event 给前端看;见下面 except CancelledError。
        except asyncio.CancelledError:
            # 主 task 被 cancel:POST /cancel(task.cancel)或**客户端断连**(sse-starlette
            # anyio task group 把 CancelledError 注入 drain loop 的 await queue.get())。
            control.cancel()  # 协作式:停掉 worker 线程在飞的 LLM 重试环(断连也不再空磨烧配额)
            if not graph_task.done():
                graph_task.cancel()
            # **断连路径(非 POST /cancel)下,这是唯一的 DB 标记入口** —— 幂等 CAS(已 cancelled/
            # 终态则 no-op)。否则客户端断连后 run 永久停在 running 成僵尸(对抗审查 confirmed)。
            try:
                repo.mark_run_cancelled(conn, run_id)
            except Exception:  # noqa: BLE001 — DB 写失败不能阻止 re-raise CancelledError
                pass
            try:
                yield {"event": "cancelled",
                       "data": json.dumps({"run_id": run_id, "ts": _now()})}
            except Exception:  # noqa: BLE001 — yield 失败也要 raise CancelledError
                pass
            raise
        except RunAborted as e:
            # 协作式取消 / 墙钟超时:包装 client 在 LLM 调用前抛出,顺线程池 future 一路传到这。
            # RunAborted 是 BaseException,已自动穿透所有 except Exception 降级处理器。
            if not graph_task.done():
                graph_task.cancel()
            if e.reason == "cancelled":
                # 幂等 CAS 标 cancelled(POST /cancel 通常已标;若取消信号来自断连兜底
                # control.cancel() 则这里补标),再 emit 'cancelled' 给前端 confirm。
                try:
                    repo.mark_run_cancelled(conn, run_id)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    yield {"event": "cancelled",
                           "data": json.dumps({"run_id": run_id, "ts": _now()})}
                except Exception:  # noqa: BLE001
                    pass
                return
            # timeout:run 还是 running,标 failed(诚实告知"超时中止",而非把残缺降级数据当结果)。
            try:
                repo.mark_run_failed(conn, run_id)
            except Exception as db_err:  # noqa: BLE001
                logger.warning("failed to mark run %s as failed after timeout: %s",
                               run_id, type(db_err).__name__)
            try:
                yield {"event": "error",
                       "data": json.dumps({
                           "error": "分析超时:超过墙钟预算已中止,请重试或减少竞品/维度",
                           "ts": _now()})}
            except Exception:  # noqa: BLE001 — 连接可能已断,yield 失败也照常 return(与 cancelled 对称)
                pass
            return
        except Exception as e:  # noqa: BLE001 — yield error 给客户端后 clean exit(不 re-raise)
            # 先把完整 traceback 写 server log(运维必须能 debug,与下面 sanitize 配对)
            logger.exception("graph pipeline error for run %s", run_id)
            # 关键 1:用 mark_run_failed CAS 把 'running' 标 'failed',但**绝不覆盖**已 finalize
            # 的 done/insufficient_evidence/degraded — 防 finalize 部分完成后被覆盖(reviewer
            # adversarial 9/10 揪到的 ship round-2 引入的 race)
            try:
                if not repo.mark_run_failed(conn, run_id):
                    logger.info("run %s already in terminal state, not overwriting", run_id)
            except Exception as db_err:  # noqa: BLE001 — DB 写失败不能再 raise(SSE 必须 clean exit)
                logger.warning("failed to mark run %s as failed: %s",
                               run_id, type(db_err).__name__)
            # 关键 2:只暴露 type(e).__name__ 给客户端,**绝不**透传 str(e):
            # OpenAI/Tavily SDK 的 APIStatusError str() 可能含 Authorization: Bearer <key>
            # header(Codex Critical #1 + FastAPI 官方 handling-errors 强调"不直接转 exception
            # str 给客户端,会泄露内部细节")。完整 traceback 已上面 logger.exception 落 server log。
            yield {"event": "error",
                   "data": json.dumps({"error": f"pipeline error: {type(e).__name__}",
                                       "ts": _now()})}
            return
        # done 携带终态 status,与 replay 路径对称(前端可用 onDone 一处取终态)
        run = repo.get_run(conn, run_id)
        yield {"event": "done",
               "data": json.dumps({
                   "run_id": run_id,
                   "status": run["status"] if run else "unknown",
                   "ts": _now()})}
    finally:
        # 兜底:任何退出路径(正常 / error / cancelled / timeout / 断连)都置取消标志,
        # 确保 worker 线程在飞的 LLM 在下一次 create() 前停掉,绝不留后台空磨烧配额的孤儿。
        control.cancel()
        # 清理 _ACTIVE_RUN_TASKS 防 leak —— 无论 graph 正常结束 / Exception clean exit /
        # CancelledError bubble out 都执行(F4)。同时确保 graph_task 也 cleanup
        # 不留孤儿 task(D8 修订:graph crash 后 listener 应识别 + drain on exit)。
        _ACTIVE_RUN_TASKS.pop(run_id, None)
        _ACTIVE_RUN_CONTROLS.pop(run_id, None)
        if not graph_task.done():
            graph_task.cancel()
            try:
                await graph_task
            except (Exception, asyncio.CancelledError, RunAborted):
                pass  # 静默 cleanup,异常已上面 handled / cancel|abort 是预期


async def _replay_from_trace(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    pacing: float = 0.02,
) -> AsyncIterator[dict]:
    """从 trace 表回放 SSE 事件(§11.4 'Play 回放' 用)。

    pacing = 每两条 trace 事件之间的节流间隔(秒)。默认 0.02(20ms),
    ~100 行 trace ≈ 2s 流畅回放,与 §11.4 演示节奏匹配;pacing=0 关闭节流
    (单元测试用)。长 trace 觉得太快可在调用方传 0.05+。
    """
    yield {"event": "start",
           "data": json.dumps({"run_id": run_id, "replay": True, "ts": _now()})}

    # ── Plan D 富 replay 重建:从持久化状态还原过程事件,刷新/深链进入不丢「看得见的活儿」。──
    # 不重建 evidence_delta(evidence 无 round 列)+ chunk(瞬态);RetryLoop 动画 replay 不显,
    # 但 retryCount 从 queries.round 真值重建(见末尾合成 qc node)。详见 plan D-D2/D-D3。

    # (1) query + query_hit(检索台):queries 表带真 round / hit_count;0 命中也重建(标「无结果」)。
    #     存局部变量 queries:末尾 retryCount = max(queries.round) 复用。
    queries = repo.list_queries(conn, run_id)
    for q in queries:
        yield {"event": "query", "data": json.dumps({
            "competitor": q["competitor"], "dimension": q["dimension"],
            "query_text": q["query_text"], "language": q["language"],
            "round": q["round"], "ts": q["created_at"]})}
        yield {"event": "query_hit", "data": json.dumps({
            "query_text": q["query_text"], "hit_count": q["hit_count"],
            "round": q["round"], "ts": q["created_at"]})}

    # (2) source(来源卡):evidence 无 round 列 → round 默认 0;只发卡片字段,不发 content 全文;
    #     不含 provider/confidence(反幻觉 §1.5)。
    for ev in repo.list_evidence(conn, run_id):
        yield {"event": "source", "data": json.dumps({
            "evidence_id": ev.id, "competitor": ev.competitor, "dimension": ev.dimension,
            "source_title": ev.source_title, "source_url": ev.source_url,
            "language": ev.language, "fetched_at": ev.fetched_at,
            "round": 0, "ts": ev.fetched_at})}

    # (3) cell_row(矩阵逐维)+ (4) verdict_recheck(三色):从 curated analysis 重建。
    analysis = repo.get_analysis(conn, run_id)
    if analysis is not None:
        present_dims: set[str] = set()
        cell_verdicts: list[dict] = []
        n_supported = 0
        n_partial = 0
        for row in analysis.comparison:
            present_dims.add(row.dimension)
            yield {"event": "cell_row", "data": json.dumps({
                "dimension": row.dimension, "status": "ok",
                "cells": [{
                    "competitor": cell.competitor,
                    "value_type": cell.value_type,
                    "value": cell.value,
                    "evidence_refs": [{"evidence_id": r.evidence_id, "quote": r.quote}
                                      for r in cell.evidence_refs],
                } for cell in row.cells],
                "ts": _now()})}
            for cell in row.cells:
                cell_verdicts.append({
                    "dimension": row.dimension, "competitor": cell.competitor,
                    "support_verdict": cell.support_verdict})
                if cell.support_verdict == "supported":
                    n_supported += 1
                elif cell.support_verdict == "partial":
                    n_partial += 1
        # 请求维度但 analysis 无 row(无证据/失败)→ 发 status="empty",让 PlanRail 刷新后显
        # 「已知空」而非永远 todo。不可区分 empty/failed → 统一 empty(不伪造 failed)。
        run = repo.get_run(conn, run_id)
        for dim in (run["dimensions"] if run else []):
            if dim not in present_dims:
                yield {"event": "cell_row", "data": json.dumps({
                    "dimension": dim, "status": "empty", "cells": [], "ts": _now()})}
        dropped = [{"dimension": d["dimension"], "competitor": d["competitor"],
                    "detail": d["detail"]}
                   for d in repo.list_curation_drops(conn, run_id)
                   if d["scope"] == "cell"]
        # downgraded = partial cell 子集(对齐 live 契约);C-D6:无 decision_verdicts。
        downgraded = [cv for cv in cell_verdicts if cv["support_verdict"] == "partial"]
        yield {"event": "verdict_recheck", "data": json.dumps({
            "cell_verdicts": cell_verdicts,
            "dropped": dropped,
            "downgraded": downgraded,
            "summary": {"supported": n_supported, "partial": n_partial,
                        "dropped": len(dropped)},
            "ts": _now()})}

    # (5) 合成终态 qc node 注入真 retryCount(让「自我纠错 N 次 / N 轮」replay 显真值而非恒 0)。
    #     仅当 qc_result 存在才发(空 / 早失败 run 不发,保既有空-run 测试)。
    qc_res = repo.get_qc_result(conn, run_id)
    if qc_res is not None:
        max_round = max((q["round"] for q in queries), default=0)
        run_row = repo.get_run(conn, run_id)
        yield {"event": "node", "data": json.dumps({
            "node": "qc",
            "summary": {"node": "qc", "verdict": qc_res.verdict,
                        "issues": len(qc_res.issues), "issue_types": {},
                        "retry_count": max_round,
                        "degraded": bool(run_row["degraded"]) if run_row else False},
            "ts": _now()})}

    for t in repo.list_trace(conn, run_id):
        # 与 live 流 'node' event 同形状 `{node, summary:{...}, ts}`,前端可用同一
        # 解析路径处理 live + replay(context7 调研:sse-starlette 不强 opinion event
        # shape,application 级决策由 Lane F 消费便利度决定 → 统一更简)
        yield {"event": "trace",
               "data": json.dumps({
                   "node": t["node"],
                   "summary": {
                       "input": t.get("input_summary", ""),
                       "output": t.get("output_summary", ""),
                       "latency_ms": t.get("latency_ms", 0),
                   },
                   "ts": t["ts"],
               })}
        if pacing > 0:
            await asyncio.sleep(pacing)
    run = repo.get_run(conn, run_id)
    yield {"event": "done",
           "data": json.dumps({
               "run_id": run_id,
               "status": run["status"] if run else "unknown",
               "ts": _now()})}
