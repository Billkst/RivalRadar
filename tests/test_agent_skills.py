from rivalradar.storage.db import connect, init_db


def test_agent_skills_table_exists(tmp_path):
    db = tmp_path / "t.db"
    conn = connect(str(db))
    init_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(agent_skills)")}
    assert cols == {"agent_id", "skill_id", "version", "enabled", "installed_at"}
