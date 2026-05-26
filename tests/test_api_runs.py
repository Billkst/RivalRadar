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
