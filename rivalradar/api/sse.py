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
import sqlite3
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from rivalradar.storage import repository as repo

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
    """SSE 主流:start → 每节点 update → done(或 error → clean exit)。

    yield 出的 dict 给 sse-starlette EventSourceResponse,字段 'event'/'data'。

    `conn` 用于 (1) graph 崩溃时把 run.status 置为 "failed" 防 zombie run
    永久卡在 "running",以及 (2) done event 携带终态 status 与 replay 路径对称。

    ⚠️ LangGraph **stream_mode="updates"**(默认 v1 行为)契约:chunk 形状是
    `{node_name: state_delta}`(逐 task 直接 yield),与 stream_events(version="v3")
    的 `{"params":{...},"method":...}` 协议层包装**完全不同**。Lane D 的 nodes
    返回值与本实现都按 v1 updates 契约对齐。**切勿改成 stream_events 或 v2/v3
    包装**(会让前端 DAG 整套节点-名 → 动画的对应关系断裂)。
    """
    # F4 修订:注册当前 ASGI generator task 到 _ACTIVE_RUN_TASKS,让
    # POST /run/{id}/cancel 能 task.cancel() 中断 in-flight LLM。
    # `asyncio.current_task()` 在 async generator 内拿到的是 sse-starlette
    # 拉这个 body_iterator 的那个 ASGI task—— cancel 它会顺着 await 链中断
    # `graph.astream(...)` 内部正在 await 的 LLM/network call。
    current = asyncio.current_task()
    if current is not None:
        _ACTIVE_RUN_TASKS[run_id] = current
    try:
        yield {"event": "start",
               "data": json.dumps({"run_id": run_id, "ts": _now()})}
        try:
            async for chunk in graph.astream(initial, config=config,
                                              stream_mode="updates"):
                for node_name, delta in chunk.items():
                    yield {"event": "node",
                           "data": json.dumps({
                               "node": node_name,
                               "summary": _summarize_delta(node_name, delta),
                               "ts": _now(),
                           })}
        # 注意:**不**捕获 asyncio.CancelledError(BaseException 子类,不入 Exception
        # 分支)—— 这是 sse-starlette task group 在客户端断连时通过 _listen_for_disconnect
        # cancel_on_finish 触发的清理路径,也是 F4 POST /cancel 通过 _ACTIVE_RUN_TASKS
        # task.cancel() 触发的中断路径——两者都必须让 cancel 直接退出生成器、不被
        # yield "error" 拦截。**切勿改成 except BaseException** 会吞掉 cancel、导致
        # 孤儿任务堆积 + cancel 反馈丢失。
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
        # F4: 清理 _ACTIVE_RUN_TASKS 防 leak —— 无论 graph 正常结束 / Exception
        # clean exit / CancelledError bubble out 都执行。pop with default 防 KeyError。
        _ACTIVE_RUN_TASKS.pop(run_id, None)


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
