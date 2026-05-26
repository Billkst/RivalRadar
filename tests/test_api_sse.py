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


def test_graph_event_stream_yields_start_node_done():
    events = asyncio.run(_collect(graph_event_stream(
        _StubGraph(), initial={}, config={"configurable": {"thread_id": "r1"}},
        run_id="r1")))
    # 期望:start + 5 node events + done = 7 条
    assert events[0]["event"] == "start"
    assert json.loads(events[0]["data"])["run_id"] == "r1"
    node_events = [e for e in events if e["event"] == "node"]
    assert [json.loads(e["data"])["node"] for e in node_events] == \
        ["collect", "analyze", "write", "qc", "finalize"]
    assert events[-1]["event"] == "done"


def test_graph_event_stream_emits_error_and_clean_exits():
    """graph 跑挂时:先 yield error 给客户端,然后 clean exit(不 re-raise),
    让 sse-starlette task group 自然走优雅关停。"""
    class _BoomGraph:
        def astream(self, _input, *, config, stream_mode):
            async def gen():
                yield {"collect": {"evidence": []}}
                raise RuntimeError("upstream LLM down")
                yield  # unreachable
            return gen()

    events = asyncio.run(_collect(graph_event_stream(_BoomGraph(), {}, {}, "r1")))
    # clean exit:start + collect + error,**不应**有 done event
    assert events[0]["event"] == "start"
    assert any(e["event"] == "error" and "upstream LLM down" in e["data"]
               for e in events)
    assert not any(e["event"] == "done" for e in events)


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
