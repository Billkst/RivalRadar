"""graph_event_stream emit queue drain tests(plan v3.2 §10 D5 Epic 7.5b + Epic 2.2)。

覆盖 3 个核心行为(emit-driven 改造):
  1. 最小路径:graph 一个 chunk → SSE 出 start + node + done(backward compat,
     节点不调 emit,只 yield chunk 形态,跟改造前一样 work)
  2. emit(progress,...) 在 yield chunk 之前调用 → SSE 顺序应为 start → progress →
     node → done(emit 进 queue,主 task FIFO drain)
  3. _ACTIVE_RUN_TASKS 在 graph 正常结束后被清干净 — 防 memory leak(finally
     里 pop)

mock FakeGraph 模拟 LangGraph.astream(初始 + config={configurable:{emit}} +
stream_mode='updates' yield {node_name: state_delta} 形态)。
"""
import json

import pytest

from rivalradar.api.sse import _ACTIVE_RUN_TASKS, graph_event_stream
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "sse_emit.db")


@pytest.fixture()
def conn(db_path):
    c = connect(db_path)
    init_db(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _clear_active_tasks():
    """每个 test 前后清 _ACTIVE_RUN_TASKS 防测试间污染。"""
    _ACTIVE_RUN_TASKS.clear()
    yield
    _ACTIVE_RUN_TASKS.clear()


class FakeGraph:
    """Mock LangGraph 实现 astream(initial, config, stream_mode)。

    emit_calls: list[(ev_type, data)] —— 在 yield chunks 之前先调用 emit(从
    config['configurable']['emit'] 取),模拟节点内 emit('progress',...) 行为。
    chunks: list[dict] —— astream 每次 yield 一个 {node_name: state_delta}。
    """
    def __init__(self, *, emit_calls=None, chunks=None):
        self.emit_calls = emit_calls or []
        self.chunks = chunks or []

    async def astream(self, initial, *, config, stream_mode):
        # 验 stream_mode='updates' 契约(sse.py 注释强调不能改 events / v3)
        assert stream_mode == "updates"
        emit = config.get("configurable", {}).get("emit")
        for ev_type, data in self.emit_calls:
            if emit is not None:
                emit(ev_type, data)
        for chunk in self.chunks:
            yield chunk


async def test_graph_event_stream_yields_start_node_done(conn):
    """最小路径(backward compat):graph 一个 chunk,SSE 出 start + node + done。

    旧节点不调 emit 也能 work —— 节点不传 emit → config['configurable'].get('emit')
    返 None → emit 不被节点调用,SSE 只出基础事件。
    """
    repo.create_run(conn, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(conn, "r1", "done")

    graph = FakeGraph(chunks=[{"collect": {"evidence": [{"id": "e1"}]}}])
    events = []
    async for ev in graph_event_stream(graph, {}, {}, "r1", conn=conn):
        events.append(ev)

    assert [e["event"] for e in events] == ["start", "node", "done"]
    node_data = json.loads(events[1]["data"])
    assert node_data["node"] == "collect"
    assert node_data["summary"]["evidence_added"] == 1
    done_data = json.loads(events[2]["data"])
    assert done_data["run_id"] == "r1"
    assert done_data["status"] == "done"


async def test_graph_event_stream_drains_emit_events_in_order(conn):
    """emit('progress',...) 与 'node' event FIFO 保持 — emit 进 queue 先,
    node event 后进 queue,drain 顺序对。auto ts 也注入 progress payload。
    """
    repo.create_run(conn, "r2", ["Notion"], ["pricing"])
    repo.update_run_status(conn, "r2", "done")

    graph = FakeGraph(
        emit_calls=[
            ("progress", {"agent_id": "collector", "step": "search", "summary": "x"}),
        ],
        chunks=[{"collect": {"evidence": []}}],
    )
    events = []
    async for ev in graph_event_stream(graph, {}, {}, "r2", conn=conn):
        events.append(ev)

    # Order: start → progress(drained 先 push)→ node(chunk 触发 emit 'node')→ done
    types = [e["event"] for e in events]
    assert types == ["start", "progress", "node", "done"]

    progress_data = json.loads(events[1]["data"])
    assert progress_data["agent_id"] == "collector"
    assert progress_data["summary"] == "x"
    assert "ts" in progress_data  # auto-injected by emit() 防 caller 漏写

    node_data = json.loads(events[2]["data"])
    assert node_data["node"] == "collect"


async def test_graph_event_stream_cleans_up_active_tasks(conn):
    """run_id 应该从 _ACTIVE_RUN_TASKS 清干净 — 防进程长跑后 dict 无限增长。

    finally 中 _ACTIVE_RUN_TASKS.pop(run_id, None) 兜底,不管 graph 正常结束 /
    Exception / cancel 都执行。
    """
    repo.create_run(conn, "r3", ["Notion"], ["pricing"])
    repo.update_run_status(conn, "r3", "done")

    graph = FakeGraph(chunks=[{"collect": {"evidence": []}}])
    async for _ in graph_event_stream(graph, {}, {}, "r3", conn=conn):
        pass

    # 验 cleaned up — 防 memory leak
    assert "r3" not in _ACTIVE_RUN_TASKS
