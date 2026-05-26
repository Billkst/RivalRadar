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
import sqlite3
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from rivalradar.storage import repository as repo


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
) -> AsyncIterator[dict]:
    """SSE 主流:start → 每节点 update → done(或 error → clean exit)。

    yield 出的 dict 给 sse-starlette EventSourceResponse,字段 'event'/'data'。

    ⚠️ done event 只含 run_id + ts,**不含**终态 status(done/insufficient_evidence/degraded)。
    前端 onDone 后应 GET /run/:id 拉详情,而非靠 done event 本身判定终态(动画与详情分离)。

    ⚠️ LangGraph **stream_mode="updates"**(默认 v1 行为)契约:chunk 形状是
    `{node_name: state_delta}`(逐 task 直接 yield),与 stream_events(version="v3")
    的 `{"params":{...},"method":...}` 协议层包装**完全不同**。Lane D 的 nodes
    返回值与本实现都按 v1 updates 契约对齐。**切勿改成 stream_events 或 v2/v3
    包装**(会让前端 DAG 整套节点-名 → 动画的对应关系断裂)。
    """
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
    # cancel_on_finish 触发的清理路径,必须让 cancel 直接退出生成器、不被 yield "error"
    # 拦截。**切勿改成 except BaseException** 会吞掉 cancel、导致孤儿任务堆积。
    except Exception as e:  # noqa: BLE001 — yield error 给客户端后 clean exit(不 re-raise)
        yield {"event": "error",
               "data": json.dumps({"error": str(e), "ts": _now()})}
        return
    yield {"event": "done",
           "data": json.dumps({"run_id": run_id, "ts": _now()})}


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
        yield {"event": "trace",
               "data": json.dumps({
                   "node": t["node"],
                   "input": t.get("input_summary", ""),
                   "output": t.get("output_summary", ""),
                   "latency_ms": t.get("latency_ms", 0),
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
