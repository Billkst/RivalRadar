from fastapi.testclient import TestClient

from rivalradar.api.app import create_app
from rivalradar.storage.db import connect, init_db
from rivalradar.storage.repository import (
    delete_agent_skill,
    list_agent_skills,
    upsert_agent_skill,
)


def _client(tmp_path):
    return TestClient(create_app(db_path=str(tmp_path / "api.db")))


def test_agent_skills_table_exists(tmp_path):
    db = tmp_path / "t.db"
    conn = connect(str(db))
    init_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(agent_skills)")}
    assert cols == {"agent_id", "skill_id", "version", "enabled", "installed_at"}


def test_upsert_list_delete(tmp_path):
    db = tmp_path / "t.db"
    conn = connect(str(db))
    init_db(conn)
    upsert_agent_skill(conn, "collector", "evidence-retrieving", "v1", True)
    upsert_agent_skill(conn, "collector", "evidence-retrieving", "v1", False)  # 幂等覆盖
    upsert_agent_skill(conn, "writer", "grounded-report-synthesis", "v1", True)
    rows = list_agent_skills(conn)
    assert len(rows) == 2
    coll = [r for r in rows if r["agent_id"] == "collector"][0]
    assert coll["enabled"] is False and coll["skill_id"] == "evidence-retrieving"
    delete_agent_skill(conn, "collector", "evidence-retrieving")
    rows2 = list_agent_skills(conn)
    assert len(rows2) == 1 and rows2[0]["agent_id"] == "writer"


def test_agent_skills_rest_roundtrip(tmp_path):
    c = _client(tmp_path)
    assert c.get("/agent-skills").json() == []  # 空表
    r = c.put("/agent-skills", json={
        "agent_id": "writer", "skill_id": "grounded-report-synthesis",
        "version": "v1", "enabled": True,
    })
    assert r.status_code == 200
    rows = c.get("/agent-skills").json()
    assert len(rows) == 1 and rows[0]["enabled"] is True
    c.put("/agent-skills", json={
        "agent_id": "writer", "skill_id": "grounded-report-synthesis",
        "version": "v1", "enabled": False,
    })
    assert c.get("/agent-skills").json()[0]["enabled"] is False  # upsert
    d = c.delete("/agent-skills/writer/grounded-report-synthesis")
    assert d.status_code == 200
    assert c.get("/agent-skills").json() == []


def test_agent_skills_put_validation(tmp_path):
    c = _client(tmp_path)
    r = c.put("/agent-skills", json={"agent_id": "writer"})  # 缺字段
    assert r.status_code == 422
