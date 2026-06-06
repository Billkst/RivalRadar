"""决定性实证:复刻 sse.py 的 emit→asyncio.Queue→drain 机制,用 run_in_executor 跑真
analyze_node + 注入 emit,记录每个 progress 事件【发出→被 drain 收到】的延迟。

验两件事:
  (1) analyze_node 在生产异步/executor 路径下是否真能跑完(还是会 hang);
  (2) worker 线程 put_nowait 到 asyncio.Queue 的事件是【实时送达】还是【批量拖到节点结束】
      —— 若批量,则执行流 UI 在 analyze 全程冻住,用户以为卡死。

真打 Doubao(放 spikes/)。
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time

from rivalradar.config import db_path, doubao_model, get_doubao_client
from rivalradar.storage.repository import list_evidence
from rivalradar.graph.nodes import make_analyze_node

RID = "run_2dfd75424fd0"
COMPS = ["钉钉", "企业微信"]
DIMS = ("pricing", "core_workflows", "deployment", "integrations",
        "target_users", "review_sentiment")


async def main():
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    evidence = list_evidence(conn, RID)
    client = get_doubao_client()
    model = doubao_model()
    analyze_node = make_analyze_node(conn=conn, client=client, model=model)

    queue: asyncio.Queue = asyncio.Queue()
    DONE = object()
    t_start = time.monotonic()
    loop = asyncio.get_running_loop()

    # 镜像【修复后】sse.py:emit 经 call_soon_threadsafe 投递,worker 线程也能唤醒事件循环
    def emit(ev_type, data):
        item = {"t": time.monotonic() - t_start, "event": ev_type,
                "data": data.get("step") or data.get("node") or ev_type}
        loop.call_soon_threadsafe(queue.put_nowait, item)

    cfg = {"configurable": {"thread_id": RID, "emit": emit}}
    state = {"evidence": [e.model_dump() for e in evidence],
             "competitors": COMPS, "dimensions": DIMS}

    recv = []

    async def drain():
        while True:
            ev = await queue.get()
            if ev is DONE:
                break
            recv.append((time.monotonic() - t_start, ev))

    drain_task = asyncio.create_task(drain())
    loop = asyncio.get_running_loop()
    print(f"[起] 用 run_in_executor 跑 analyze_node,证据 {len(evidence)} 条…", flush=True)
    try:
        # 与 LangGraph 跑 sync 节点同路径:在 executor 线程跑,事件循环 await 它
        await loop.run_in_executor(None, lambda: analyze_node(state, cfg))
        elapsed = time.monotonic() - t_start
        print(f"[完成] analyze_node 跑完,耗时 {elapsed:.1f}s（{elapsed/60:.1f} 分钟）", flush=True)
    finally:
        queue.put_nowait(DONE)
        await drain_task

    print(f"\n收到 {len(recv)} 个进度事件,各自【被 drain 收到】的时刻(秒):")
    for emit_info in recv:
        recv_t, ev = emit_info
        print(f"  收到@{recv_t:6.1f}s  emit@{ev['t']:6.1f}s  延迟 {recv_t-ev['t']:5.1f}s  | {ev['event']}:{ev['data']}")
    if recv:
        delays = [rt - ev['t'] for rt, ev in recv]
        print(f"\n事件投递延迟:最大 {max(delays):.1f}s / 平均 {sum(delays)/len(delays):.1f}s")
        print("→ 若延迟接近节点总耗时 = 事件全被拖到结束才到 = UI 全程冻住(坐实 emit 桥 bug)")
        print("→ 若延迟都很小 = 实时送达 = UI 不会看着卡死(UX 非主因)")


asyncio.run(main())
