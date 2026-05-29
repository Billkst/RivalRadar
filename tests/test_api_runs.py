import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "runs.db")


@pytest.fixture()
def client(db_path):
    return TestClient(create_app(db_path=db_path))


def _seed_three_runs(db_path):
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r_done", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r_done", "done")
    repo.create_run(c, "r_insuf", ["Linear"], ["pricing"])
    repo.update_run_status(c, "r_insuf", "insufficient_evidence")
    repo.create_run(c, "r_degr", ["Asana"], ["pricing"])
    repo.update_run_status(c, "r_degr", "degraded")
    c.close()


def test_list_runs_returns_summary(db_path, client):
    _seed_three_runs(db_path)
    r = client.get("/runs")
    assert r.status_code == 200
    items = r.json()
    assert {x["run_id"] for x in items} == {"r_done", "r_insuf", "r_degr"}
    statuses = {x["status"] for x in items}
    assert statuses == {"done", "insufficient_evidence", "degraded"}


def test_get_run_done_state(db_path, client):
    _seed_three_runs(db_path)
    r = client.get("/run/r_done")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["degraded"] is False


def test_get_run_insufficient_state(db_path, client):
    _seed_three_runs(db_path)
    r = client.get("/run/r_insuf")
    assert r.status_code == 200
    assert r.json()["status"] == "insufficient_evidence"


def test_get_run_degraded_state_sets_degraded_flag(db_path, client):
    """status=degraded 时 degraded 标记必须 True,前端 §11.5 据此显示告警横幅。"""
    _seed_three_runs(db_path)
    r = client.get("/run/r_degr")
    body = r.json()
    assert body["status"] == "degraded"
    assert body["degraded"] is True


def test_get_run_404(client):
    r = client.get("/run/no_such")
    assert r.status_code == 404


import hashlib
import json

from rivalradar.agents import qc
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, CompetitorProfile, PricingModel,
    SWOT, ComparisonRow, ComparisonCell, Decision, DecisionSet, EvidenceRef, ReportInsight,
)
from rivalradar.search.base import SearchResult


class _OneShotProvider:
    """采集 1 条假证据立刻够本,无需 retry。"""
    name = "oneshot"
    def search(self, query, *, max_results=5):
        url = "https://fake.example/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        return [SearchResult(url=url, title="t", content="s",
                             raw_content="body for " + query)]


def _fake_analyze(evidence, competitors, *, dimensions=None, client, model):
    """覆盖已有维度的对比,引用真实 id;无 features/personas/swot。"""
    dims_present = {e.dimension for e in evidence}
    profiles = []
    for c in competitors:
        price_ev = next((e for e in evidence
                         if e.competitor == c and e.dimension == "pricing"), None)
        refs = [EvidenceRef(evidence_id=price_ev.id, quote="q")] if price_ev else []
        profiles.append(CompetitorProfile(
            name=c, pricing=PricingModel(model_type="freemium", evidence_refs=refs),
            swot=SWOT()))
    rows = []
    for dim in CONTROLLED_DIMENSIONS:
        if dim not in dims_present:
            continue
        cells = []
        for c in competitors:
            ev = next((e for e in evidence
                       if e.competitor == c and e.dimension == dim), None)
            if ev:
                cells.append(ComparisonCell(competitor=c, value_type="enum",
                                            value="x",
                                            evidence_refs=[EvidenceRef(evidence_id=ev.id, quote="q")]))
        rows.append(ComparisonRow(dimension=dim, cells=cells))
    return CompetitorAnalysis(competitors=profiles, comparison=rows)


@pytest.fixture()
def stubbed_client(db_path, monkeypatch):
    # 用与 test_graph_loop.py 同款 stub:跳过真实 LLM,但跑完整图
    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _fake_analyze)
    monkeypatch.setattr("rivalradar.graph.nodes.write_report_with_insight",
                        lambda *a, **k: ("# 竞品分析报告\n正文",
                                         ReportInsight(market_context="m",
                                                       differentiation_thesis="d",
                                                       actionable_takeaway="a")))
    monkeypatch.setattr(qc, "check_entailment", lambda *a, **k: [])
    # full-C decide 节点(Epic 2):stub 让它走"成功产出决策"路径(否则 client=str → 降级空决策),
    # 使完整图 E2E 覆盖 decide 接进图 + 三张新表持久化(adversarial M5)。
    monkeypatch.setattr(
        "rivalradar.graph.nodes.generate_decisions",
        lambda *a, **k: DecisionSet(decisions=[Decision(
            stance="建议采用", action="评估接入", horizon="短期", risk_reversibility="可逆",
            risk_cost="低", why="x", evidence_refs=[EvidenceRef(evidence_id="e1", quote="q")])]))
    monkeypatch.setattr(qc, "check_decision_traceability", lambda *a, **k: [])
    monkeypatch.setattr(qc, "check_decision_entailment", lambda *a, **k: [])
    app = create_app(db_path=db_path, doubao_client="stub-client",
                     provider=_OneShotProvider(), as_of="2026-05-26")
    return TestClient(app)


def _parse_sse(raw_bytes: bytes) -> list[dict]:
    """把原始 SSE 响应字节解析成 [{event, data}] 列表。"""
    events, current = [], {}
    for line in raw_bytes.decode("utf-8").splitlines():
        if line == "":
            if current:
                events.append(current)
                current = {}
        elif line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = line[6:]
    if current:
        events.append(current)
    return events


def test_post_run_streams_sse_with_start_nodes_done(stubbed_client):
    """POST /run 应当返 EventSourceResponse,先 start、过程节点事件、最后 done。"""
    r = stubbed_client.post("/run",
                            json={"competitors": ["Notion"],
                                  "dimensions": list(CONTROLLED_DIMENSIONS)})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.content)
    assert events[0]["event"] == "start"
    node_events = [e for e in events if e["event"] == "node"]
    nodes_hit = [json.loads(e["data"])["node"] for e in node_events]
    for n in ("collect", "analyze", "write", "qc", "decide", "finalize"):
        assert n in nodes_hit  # decide 已接进真实图(full-C / Epic 2)
    assert events[-1]["event"] == "done"
    done_data = json.loads(events[-1]["data"])
    assert done_data["run_id"].startswith("run_")


def test_post_run_persists_state_after_stream(stubbed_client, db_path):
    """SSE 流跑完后,数据库里应有 run/evidence/analysis/report。"""
    r = stubbed_client.post("/run",
                            json={"competitors": ["Notion"],
                                  "dimensions": list(CONTROLLED_DIMENSIONS)})
    assert r.status_code == 200
    events = _parse_sse(r.content)
    done = json.loads(events[-1]["data"])
    run_id = done["run_id"]

    c = connect(db_path)
    init_db(c)
    run = repo.get_run(c, run_id)
    assert run is not None
    assert run["status"] in ("done", "insufficient_evidence", "degraded")
    assert len(repo.list_evidence(c, run_id)) > 0
    assert repo.get_report(c, run_id) is not None
    # full-C 三张新表都经真实 graph.invoke 端到端落库(adversarial M5)
    assert repo.get_decisions(c, run_id) is not None
    assert repo.get_qc_result(c, run_id) is not None
    assert repo.get_insight(c, run_id) is not None
    c.close()


def test_get_run_exposes_decision_context(db_path, client):
    """full-C(Epic 2):GET /run/:id 经 RunDetail expose decision_context(cockpit 回访显示处境)。"""
    from rivalradar.storage.db import connect, init_db
    c = connect(db_path); init_db(c)
    repo.create_run(c, "r_ctx", ["飞书"], ["pricing"], decision_context="选型PM:评估飞书")
    repo.update_run_status(c, "r_ctx", "done")
    c.close()
    r = client.get("/run/r_ctx")
    assert r.status_code == 200
    assert r.json()["decision_context"] == "选型PM:评估飞书"


def test_post_run_rejects_empty_competitors(stubbed_client):
    r = stubbed_client.post("/run", json={"competitors": [], "dimensions": ["pricing"]})
    assert r.status_code == 422


def test_post_run_422_returns_error_out_string_shape(stubbed_client):
    """422 体形必须与 ErrorOut(detail: str)一致,Lane F 前端契约统一。"""
    r = stubbed_client.post("/run", json={"competitors": [], "dimensions": ["pricing"]})
    assert r.status_code == 422
    body = r.json()
    assert isinstance(body["detail"], str)
    assert "competitors" in body["detail"]


def test_post_run_emits_error_event_when_graph_crashes(stubbed_client, monkeypatch):
    """money shot 诚实失败:graph 跑崩时 SSE 必须发 error event 给客户端
    (而非连接突然断掉,前端能显示失败原因)。
    ship round-2:error 只暴露 type(e).__name__,**不**透传 raw str(e)
    (防 OpenAI APIStatusError str() 泄 Authorization Bearer key,Codex Critical #1)。"""
    def _boom(*a, **k):
        raise RuntimeError("boom in analyze")
    monkeypatch.setattr("rivalradar.graph.nodes.analyze", _boom)
    r = stubbed_client.post("/run",
                            json={"competitors": ["Notion"],
                                  "dimensions": ["pricing"]})
    # SSE 协议头还是 200(streaming 本身不算 HTTP error)
    assert r.status_code == 200
    events = _parse_sse(r.content)
    error_evt = next((e for e in events if e.get("event") == "error"), None)
    assert error_evt is not None, f"no error event in stream: {events}"
    assert "RuntimeError" in error_evt["data"]  # 含 type
    assert "boom in analyze" not in error_evt["data"], \
        "raw msg leaked — 重新引入 KEY 泄露面"


def test_get_stream_replays_finished_run(stubbed_client, db_path):
    """先 POST /run 让 trace 落库,再 GET /stream/:run 从 trace 表回放。"""
    r = stubbed_client.post("/run",
                            json={"competitors": ["Notion"],
                                  "dimensions": list(CONTROLLED_DIMENSIONS)})
    events = _parse_sse(r.content)
    run_id = json.loads(events[-1]["data"])["run_id"]

    r2 = stubbed_client.get(f"/stream/{run_id}")
    assert r2.status_code == 200
    replay = _parse_sse(r2.content)
    assert replay[0]["event"] == "start"
    assert json.loads(replay[0]["data"])["replay"] is True
    trace_events = [e for e in replay if e["event"] == "trace"]
    assert len(trace_events) > 0
    nodes = [json.loads(e["data"])["node"] for e in trace_events]
    for n in ("collect", "analyze", "write", "qc", "finalize"):
        assert n in nodes, f"node {n} missing in replay; got {nodes}"
    assert replay[-1]["event"] == "done"


def test_get_stream_404_for_unknown_run(client):
    """没种 run + 没 POST 过,纯空 db,GET 不存在的 run_id 必须 404。"""
    r = client.get("/stream/no_such_run")
    assert r.status_code == 404


def test_post_run_422_empty_dimensions(stubbed_client):
    """POST /run 空 dimensions 也应 422 — RunRequest 双字段都有 min_length=1。"""
    r = stubbed_client.post("/run", json={"competitors": ["Notion"], "dimensions": []})
    assert r.status_code == 422
    body = r.json()
    assert isinstance(body["detail"], str)
    assert "dimensions" in body["detail"]


def test_get_run_returns_degraded_true_when_persisted(db_path, client):
    """蕴含降级路径(verdict=pass + state.degraded=True)持久化后,API 必须暴露
    degraded=True 给前端做 §11.5 警示横幅 —— 这是 Lane D 遗留(state.degraded
    在 pass 路径不暴露)被 Lane E 正面收口的关键测试。"""
    c = connect(db_path); init_db(c)
    repo.create_run(c, "r_done_degr", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r_done_degr", "done")
    repo.update_run_degraded(c, "r_done_degr", True)
    c.close()

    r = client.get("/run/r_done_degr")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["degraded"] is True  # 前端据此显示警示横幅(蕴含降级但 verdict=pass)


def test_post_run_rejects_too_many_competitors(stubbed_client):
    """ship 修复 — RunRequest.competitors 上限 5(spec §3 "1-5 个竞品"),
    防恶意/误用 POST 100 个竞品打爆 LLM + 搜索 API 配额(KEY 纪律间接面)。"""
    r = stubbed_client.post("/run",
                            json={"competitors": ["a"] * 10,  # 超 max_length=5
                                  "dimensions": ["pricing"]})
    assert r.status_code == 422
    assert "competitors" in r.json()["detail"]


def test_post_run_competitor_string_boundary_200_201(stubbed_client):
    """/review fix(testing specialist 7/10):锁住临界值 — 防止 max_length 被
    悄悄收紧(如改成 50)而无人察觉。200 char 应过,201 char 应 422。"""
    # 200 char 边界 — 应该被接受(进入业务流,SSE 流开始即可,不必跑完图)
    r_ok = stubbed_client.post("/run",
                               json={"competitors": ["X" * 200],
                                     "dimensions": ["pricing"]})
    assert r_ok.status_code == 200  # SSE 协议头不算 4xx
    # 201 char — 必须 422
    r_bad = stubbed_client.post("/run",
                                json={"competitors": ["X" * 201],
                                      "dimensions": ["pricing"]})
    assert r_bad.status_code == 422
    assert "competitors" in r_bad.json()["detail"]


def test_post_run_rejects_oversized_competitor_string(stubbed_client):
    """ship round-2 (Codex High #3):per-item max_length=200 必须实际生效
    (而非只在 docstring 写) — 200KB 的"竞品名"通过 list max_length=5 但仍能打爆 prompt。"""
    huge = "X" * 1000  # 超 200 字符上限
    r = stubbed_client.post("/run",
                            json={"competitors": [huge],
                                  "dimensions": ["pricing"]})
    assert r.status_code == 422
    assert "competitors" in r.json()["detail"]


def test_list_runs_summary_includes_degraded_field(db_path, client):
    """ship 修复 — RunSummary 含 degraded 字段(原 Lane E 盲点:只加到 RunDetail)。
    /runs 列表的降级横幅 §11.5 依赖此字段,缺失会被 FastAPI response_model 静默剥除。"""
    c = connect(db_path); init_db(c)
    repo.create_run(c, "r_normal", ["Notion"], ["pricing"])
    repo.update_run_status(c, "r_normal", "done")
    repo.create_run(c, "r_degraded", ["Linear"], ["pricing"])
    repo.update_run_status(c, "r_degraded", "done")
    repo.update_run_degraded(c, "r_degraded", True)
    c.close()

    r = client.get("/runs")
    assert r.status_code == 200
    items = {x["run_id"]: x for x in r.json()}
    # 关键:degraded 字段必须在 list 项里出现(否则 Pydantic response_model 剥掉)
    assert items["r_normal"]["degraded"] is False
    assert items["r_degraded"]["degraded"] is True
