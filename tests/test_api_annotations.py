import pytest
from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "anno.db")


@pytest.fixture()
def client(db_path):
    return TestClient(create_app(db_path=db_path))


def _seed_run(db_path):
    c = connect(db_path)
    init_db(c)
    repo.create_run(c, "r1", ["Notion"], ["pricing"])
    # 同时 seed evidence "ev1" 用于 evidence_id 关联测试(annotations.py 现在校验
    # evidence_id 存在,reviewer adversarial 7/10 揪到的孤儿 evidence 链)
    from rivalradar.schema.models import Evidence
    repo.insert_evidence(c, "r1", Evidence(
        id="ev1", competitor="Notion", dimension="pricing", content="$10/mo",
        source_url="https://notion.so/pricing", source_title="Pricing",
        language="en", fetched_at="2026-05-25T00:00:00Z",
    ))
    c.close()


def test_post_annotation_creates_and_returns_id(db_path, client):
    _seed_run(db_path)
    r = client.post("/annotations", json={
        "run_id": "r1", "evidence_id": "ev1",
        "conclusion_path": "competitors[0].swot.strengths[0]",
        "note": "此处存疑,缺直接证据",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["id"] > 0
    assert body["note"] == "此处存疑,缺直接证据"
    assert body["evidence_id"] == "ev1"


def test_post_annotation_evidence_id_optional(db_path, client):
    _seed_run(db_path)
    r = client.post("/annotations", json={
        "run_id": "r1", "evidence_id": None,
        "conclusion_path": "competitors[0]", "note": "整体可疑",
    })
    assert r.status_code == 201
    assert r.json()["evidence_id"] is None


def test_post_annotation_rejects_empty_note(db_path, client):
    _seed_run(db_path)
    r = client.post("/annotations", json={
        "run_id": "r1", "evidence_id": None,
        "conclusion_path": None, "note": "",
    })
    assert r.status_code == 422


def test_post_annotation_404_when_evidence_does_not_exist(db_path, client):
    """/review fix(adversarial 7/10):evidence_id 给了但不存在 → 必须 404,
    防孤儿 annotation 指向不存在的 evidence 污染 §17 质疑率"""
    _seed_run(db_path)  # 只 seed run + ev1
    r = client.post("/annotations", json={
        "run_id": "r1", "evidence_id": "ev_ghost",  # 不存在
        "conclusion_path": None, "note": "悬空证据",
    })
    assert r.status_code == 404
    assert "evidence not found" in r.json()["detail"]


def test_post_annotation_404_when_run_does_not_exist(db_path, client):
    """ship 修复 — 防孤儿 annotation:对不存在的 run_id 必须 404,
    否则 §17 人工质疑率被未关联的 phantom 标注污染。"""
    # 不 seed run,直接 POST
    r = client.post("/annotations", json={
        "run_id": "ghost_run", "evidence_id": None,
        "conclusion_path": None, "note": "悬空标注",
    })
    assert r.status_code == 404
    assert "run not found" in r.json()["detail"]


def test_post_annotation_does_not_mutate_run_state(db_path, client):
    """§11.6 桩:只记日志、不写回 state、不重跑。"""
    _seed_run(db_path)
    client.post("/annotations", json={
        "run_id": "r1", "evidence_id": "ev1",
        "conclusion_path": "x", "note": "y"})
    c = connect(db_path)
    init_db(c)
    run = repo.get_run(c, "r1")
    assert run["status"] == "running"  # 未被任何方式改动
    c.close()
