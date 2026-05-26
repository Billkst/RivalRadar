"""LangGraph astream → SSE chunk 序列化。

设计原则(必读):
- 事件本身只携带「前端动画必需的轻量摘要」(node + 计数/verdict/status),不
  传整张 state(几 KB → 几十 B),给 §11.4 实时 DAG 用。前端需要详情时另调
  GET /evidence/:id / /analysis/:run / /report/:run / /trace/:run。
- 任何 astream 异常先发 'error' 事件给前端,**再上抛** —— 前端能显示「失败原因」
  而非「连接突然断了」,且 sse-starlette 的 _listen_for_disconnect 仍能正常清理。
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
        return {"node": "qc",
                "verdict": qcr.get("verdict"),
                "issues": len(qcr.get("issues", [])),
                "retry_count": delta.get("retry_count"),
                "degraded": delta.get("degraded")}
    if node == "finalize":
        return {"node": "finalize",
                "status": delta.get("status"),
                "verdict": delta.get("qc_result", {}).get("verdict")}
    return {"node": node}


async def graph_event_stream(
    graph,
    initial: dict,
    config: dict,
    run_id: str,
) -> AsyncIterator[dict]:
    """SSE 主流:start → 每节点 update → done(或 error → 上抛)。

    yield 出的 dict 给 sse-starlette EventSourceResponse,字段 'event'/'data'。
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
    except Exception as e:  # noqa: BLE001 — 上抛前先让前端拿到 error 事件
        yield {"event": "error",
               "data": json.dumps({"error": str(e), "ts": _now()})}
        raise
    yield {"event": "done",
           "data": json.dumps({"run_id": run_id, "ts": _now()})}


async def _replay_from_trace(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    pacing: float = 0.05,
) -> AsyncIterator[dict]:
    """从 trace 表回放 SSE 事件(§11.4 'Play 回放' 用)。pacing=0 关闭节流(测试用)。"""
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
