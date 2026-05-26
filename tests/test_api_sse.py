import asyncio
import json
import pytest

from rivalradar.api.sse import _summarize_delta, graph_event_stream, _replay_from_trace
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


def test_summarize_collect_returns_evidence_count():
    s = _summarize_delta("collect", {"evidence": [{"id": "e1"}, {"id": "e2"}]})
    assert s == {"node": "collect", "evidence_added": 2}


def test_summarize_analyze_returns_competitor_count():
    s = _summarize_delta("analyze",
                         {"analysis": {"competitors": [{"name": "A"}, {"name": "B"}],
                                       "comparison": [{"dimension": "pricing"}]}})
    assert s == {"node": "analyze", "competitors": 2, "comparison_rows": 1}


def test_summarize_write_returns_chars():
    s = _summarize_delta("write", {"report": "abcdef"})
    assert s == {"node": "write", "report_chars": 6}


def test_summarize_qc_returns_verdict_and_retry_with_issue_types():
    """35% money shot:issue_types 让前端 DAG 能区分『缺证据』vs『假说不支撑』。"""
    s = _summarize_delta("qc", {
        "qc_result": {"verdict": "retry_collect",
                      "issues": [
                          {"problem_type": "missing_evidence"},
                          {"problem_type": "missing_evidence"},
                          {"problem_type": "hallucination"},
                      ]},
        "retry_count": 1,
        "degraded": False,
    })
    assert s == {"node": "qc", "verdict": "retry_collect",
                 "issues": 3,
                 "issue_types": {"missing_evidence": 2, "hallucination": 1},
                 "retry_count": 1, "degraded": False}


def test_summarize_finalize_returns_status():
    s = _summarize_delta("finalize", {"status": "done",
                                       "qc_result": {"verdict": "pass"}})
    assert s == {"node": "finalize", "status": "done", "verdict": "pass"}


class _StubGraph:
    """模拟 LangGraph 的 astream 行为:逐步 yield {node_name: delta}。"""
    def astream(self, _input, *, config, stream_mode):
        assert stream_mode == "updates"
        async def gen():
            yield {"collect": {"evidence": [{"id": "e1"}, {"id": "e2"}]}}
            yield {"analyze": {"analysis": {"competitors": [{"name": "A"}],
                                            "comparison": []}}}
            yield {"write": {"report": "hi"}}
            yield {"qc": {"qc_result": {"verdict": "pass", "issues": []},
                          "retry_count": 0, "degraded": False}}
            yield {"finalize": {"status": "done",
                                "qc_result": {"verdict": "pass"}}}
        return gen()


async def _collect(gen):
    out = []
    async for ev in gen:
        out.append(ev)
    return out


def test_graph_event_stream_yields_start_node_done(tmp_path):
    c = connect(str(tmp_path / "sse.db"))
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r1", "done")  # 让 done event 能读到终态
    events = asyncio.run(_collect(graph_event_stream(
        _StubGraph(), initial={}, config={"configurable": {"thread_id": "r1"}},
        run_id="r1", conn=c)))
    # 期望:start + 5 node events + done = 7 条
    assert events[0]["event"] == "start"
    assert json.loads(events[0]["data"])["run_id"] == "r1"
    node_events = [e for e in events if e["event"] == "node"]
    assert [json.loads(e["data"])["node"] for e in node_events] == \
        ["collect", "analyze", "write", "qc", "finalize"]
    assert events[-1]["event"] == "done"


def test_graph_event_stream_emits_error_and_clean_exits(tmp_path):
    """graph 跑挂时:(1) 先 yield error 给客户端,然后 clean exit(不 re-raise);
    (2) 把 run.status 标 'failed' 防 zombie run 永久卡 'running'(关键 ship 修复)。"""
    class _BoomGraph:
        def astream(self, _input, *, config, stream_mode):
            async def gen():
                yield {"collect": {"evidence": []}}
                raise RuntimeError("upstream LLM down")
                yield  # unreachable
            return gen()

    c = connect(str(tmp_path / "boom.db"))
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    events = asyncio.run(_collect(graph_event_stream(
        _BoomGraph(), {}, {}, "r1", conn=c)))
    # clean exit:start + collect + error,**不应**有 done event
    assert events[0]["event"] == "start"
    # ship round-2 修复:error event 含 type(e).__name__ 但**不**含 raw str(e)
    # 防 OpenAI APIStatusError str() 泄露 Authorization Bearer key(Codex Critical #1)
    error_evt = next(e for e in events if e["event"] == "error")
    assert "RuntimeError" in error_evt["data"]
    assert "upstream LLM down" not in error_evt["data"], \
        "raw exception message leaked — re-introduces KEY leak risk"
    assert not any(e["event"] == "done" for e in events)
    # 关键 zombie-fix 断言:run 必须被标 failed,而非保留 'running'
    assert repo.get_run(c, "r1")["status"] == "failed"


def test_graph_event_stream_failed_status_does_not_overwrite_finalized(tmp_path):
    """/review fix(critical 9/10):adversarial 实测:finalize 节点 update_run_status(done)
    成功后,若 update_run_degraded 抛(DB locked / disk full),sse.py except 不能把
    'done' 覆盖成 'failed'(否则前端拒绝渲染已存好的报告)。
    `mark_run_failed` CAS 模式:WHERE status='running' 让终态不被覆盖。"""
    class _BoomAfterFinalize:
        def astream(self, _input, *, config, stream_mode):
            async def gen():
                yield {"collect": {"evidence": []}}
                # 模拟 finalize 成功后续步骤抛
                raise RuntimeError("post-finalize step crashed")
                yield  # unreachable
            return gen()

    c = connect(str(tmp_path / "finalized.db"))
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    # 关键:模拟 finalize 已经把 status 设成 done(典型 race 场景)
    repo.update_run_status(c, "r1", "done")
    asyncio.run(_collect(graph_event_stream(
        _BoomAfterFinalize(), {}, {}, "r1", conn=c)))
    # 期望:CAS 防覆盖,run 保持 'done',不被改成 'failed'
    assert repo.get_run(c, "r1")["status"] == "done", \
        "CAS BUG: 'done' 被覆盖成 'failed' → 前端拒绝渲染已存好的报告"


def test_graph_event_stream_done_event_carries_status(tmp_path):
    """ship 修复:live 流 done event 必须含 status 字段(与 replay 路径对称),
    前端可一处取终态,不再需 done 后再 GET /run/:id 拉详情。"""
    c = connect(str(tmp_path / "done_status.db"))
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r1", "insufficient_evidence")
    events = asyncio.run(_collect(graph_event_stream(
        _StubGraph(), initial={}, config={"configurable": {"thread_id": "r1"}},
        run_id="r1", conn=c)))
    done = next(e for e in events if e["event"] == "done")
    payload = json.loads(done["data"])
    assert payload["status"] == "insufficient_evidence"
    assert payload["run_id"] == "r1"


def test_replay_from_trace_yields_trace_events(tmp_path):
    c = connect(str(tmp_path / "replay.db"))
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r1", "done")
    repo.append_trace(c, "r1", "collect", input_summary="targets=all",
                      output_summary="+2", latency_ms=10)
    repo.append_trace(c, "r1", "qc", output_summary="verdict=pass", latency_ms=20)

    events = asyncio.run(_collect(_replay_from_trace(c, "r1", pacing=0.0)))
    assert events[0]["event"] == "start"
    trace_events = [e for e in events if e["event"] == "trace"]
    assert [json.loads(e["data"])["node"] for e in trace_events] == ["collect", "qc"]
    assert events[-1]["event"] == "done"
    assert json.loads(events[-1]["data"])["status"] == "done"


def test_summarize_delta_unknown_node_passthrough():
    """未识别节点名只透传 node 名,不崩、不 KeyError。"""
    s = _summarize_delta("new_node_future", {"foo": "bar"})
    assert s == {"node": "new_node_future"}


def test_replay_trace_event_uses_unified_summary_shape(tmp_path):
    """ship round-2 (api-contract specialist CRITICAL):replay 'trace' event 必须
    与 live 'node' event 同形状 `{node, summary:{...}, ts}`(context7 调研后决定:
    sse-starlette 无 application 级 opinion,统一形状让前端单解析路径处理 live + replay,
    Lane F DAG 动画消费便利度优先)。"""
    c = connect(str(tmp_path / "shape.db"))
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r1", "done")
    repo.append_trace(c, "r1", "collect", input_summary="targets=all",
                      output_summary="+3", latency_ms=42)

    events = asyncio.run(_collect(_replay_from_trace(c, "r1", pacing=0.0)))
    trace_evt = next(e for e in events if e["event"] == "trace")
    payload = json.loads(trace_evt["data"])
    # 关键:必须是 summary 嵌套形状(与 live 'node' event 对齐),不是 flat shape
    assert "summary" in payload, f"replay event missing summary nesting: {payload}"
    assert "input" in payload["summary"]
    assert "output" in payload["summary"]
    assert "latency_ms" in payload["summary"]
    # 旧 flat shape 不应再存在(老前端代码会取不到值)
    assert "input" not in payload, "flat shape leaked — frontend dual-parsing risk"


def test_replay_from_trace_no_trace_yields_only_start_done(tmp_path):
    """run 存在但 trace 表为空 → 只有 start + done 两条事件,无 trace 事件。"""
    c = connect(str(tmp_path / "empty_trace.db"))
    init_db(c)
    repo.create_run(c, "r2", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r2", "done")

    events = asyncio.run(_collect(_replay_from_trace(c, "r2", pacing=0.0)))
    assert events[0]["event"] == "start"
    assert json.loads(events[0]["data"])["replay"] is True
    trace_events = [e for e in events if e["event"] == "trace"]
    assert trace_events == []
    assert events[-1]["event"] == "done"
