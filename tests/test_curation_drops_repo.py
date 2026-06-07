from rivalradar.storage.db import connect, init_db
from rivalradar.storage.repository import replace_curation_drops, list_curation_drops


def _conn():
    c = connect(":memory:"); init_db(c); return c


def test_curation_drops_structured_columns():
    conn = _conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(curation_drops)").fetchall()}
    assert {"run_id", "scope", "competitor", "dimension", "detail", "created_at"} <= cols
    replace_curation_drops(conn, "run1", "cell",
                           [{"competitor": "Notion", "dimension": "pricing"},
                            {"competitor": "Notion", "dimension": "deployment"}])
    replace_curation_drops(conn, "run1", "decision", [{"detail": "停止投入 X"}])
    rows = list_curation_drops(conn, "run1")
    assert len(rows) == 3
    cell = [r for r in rows if r["scope"] == "cell"]
    assert {(r["competitor"], r["dimension"]) for r in cell} == {("Notion", "pricing"), ("Notion", "deployment")}
    assert [r["detail"] for r in rows if r["scope"] == "decision"] == ["停止投入 X"]
    assert list_curation_drops(conn, "missing") == []


def test_curation_drops_replace_no_ghost_after_retry():
    """codex #2:多轮重试——后轮覆盖前轮(REPLACE per scope),deployment 证据补回后无幽灵剔除。"""
    conn = _conn()
    replace_curation_drops(conn, "run1", "cell",
                           [{"competitor": "Notion", "dimension": "pricing"},
                            {"competitor": "Notion", "dimension": "deployment"}])
    replace_curation_drops(conn, "run1", "decision", [{"detail": "停止投入 X"}])
    # 第二轮:deployment 补回,只剩 pricing 被剔
    replace_curation_drops(conn, "run1", "cell", [{"competitor": "Notion", "dimension": "pricing"}])
    rows = list_curation_drops(conn, "run1")
    cell = [r for r in rows if r["scope"] == "cell"]
    assert len(cell) == 1 and cell[0]["dimension"] == "pricing"   # deployment 幽灵已清
    assert any(r["scope"] == "decision" for r in rows)            # decision scope 不受 cell replace 影响
    # 空列表 = 清空该 scope
    replace_curation_drops(conn, "run1", "cell", [])
    assert [r for r in list_curation_drops(conn, "run1") if r["scope"] == "cell"] == []
