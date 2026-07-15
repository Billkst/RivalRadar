from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from rivalradar.schema.models import (
    CompetitorAnalysis, DecisionSet, Evidence, QCResult, ReportInsight,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- runs ----
def create_run(conn: sqlite3.Connection, run_id: str,
               competitors: list[str], dimensions: list[str],
               *, decision_context: str = "") -> None:
    conn.execute(
        "INSERT INTO runs (run_id, competitors, dimensions, status, decision_context, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, json.dumps(competitors), json.dumps(dimensions), "running",
         decision_context, _now()),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "competitors": json.loads(row["competitors"]),
        "dimensions": json.loads(row["dimensions"]),
        "status": row["status"],
        "degraded": bool(row["degraded"]),
        "decision_context": row["decision_context"],
        "created_at": row["created_at"],
    }


def update_run_status(conn: sqlite3.Connection, run_id: str, status: str) -> None:
    conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
    conn.commit()


def mark_run_failed(conn: sqlite3.Connection, run_id: str) -> bool:
    """把 'running' 状态的 run 标 'failed'(CAS 防覆盖已 finalize 的状态)。

    场景:SSE graph 主流 except 分支调此函数标 failed,但若 finalize 节点已
    update_run_status(done) 成功后,后续步骤(update_run_degraded 等)又抛,
    sse.py except 不应该把 'done' 覆盖成 'failed' — 否则前端拒绝渲染已存好的报告。
    返回 True if 真的改了一行(原 status='running'),False 表示已是终态没动。

    Reviewer 揪到的 ship round-2 race(adversarial 9/10:fix made it worse)。
    """
    cursor = conn.execute(
        "UPDATE runs SET status='failed' WHERE run_id=? AND status='running'",
        (run_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def mark_run_cancelled(conn: sqlite3.Connection, run_id: str) -> bool:
    """把 'running' 状态的 run 标 'cancelled'(CAS 同 mark_run_failed,F4 修订)。

    场景:user POST /run/:id/cancel,backend task.cancel() 中断 in-flight LLM 同时
    此函数持久化 status='cancelled' — 后续 GET /run/:id / GET /stream/:id 返回
    cancelled 让前端切 cancelled UI(也供 partial 状态聚合用)。

    CAS 防覆盖:已 finalize 到 done / insufficient_evidence / failed 的 run 不被
    cancelled 覆盖(timing race:user 点 cancel 时 run 刚好 finalize 完;CAS 只
    在 status='running' 时更新)。
    """
    cursor = conn.execute(
        "UPDATE runs SET status='cancelled' WHERE run_id=? AND status='running'",
        (run_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def mark_run_finalized(conn: sqlite3.Connection, run_id: str, status: str) -> bool:
    """finalize_node 用 CAS 写终态(post-ship review:对称 mark_run_failed/cancelled
    的窄窗 race 保护)。

    场景:user 点 cancel 进入 mark_run_cancelled CAS 成功(status='cancelled'),
    但 task.cancel() 在 LangGraph 节点边界才能落地;若 cancel 恰好在 finalize 节点
    sync 执行的 ~50ms 内到达,CancelledError 不能 preempt sync code,finalize 跑完
    用非 CAS update_run_status('done') 把 'cancelled' 覆盖 → DB 状态损坏(user UI
    显示已停止,GET /run 看到 done)。

    用 CAS 守 expected='running' 阻止 finalize 覆盖任何已 finalize 状态。
    """
    cursor = conn.execute(
        "UPDATE runs SET status=? WHERE run_id=? AND status='running'",
        (status, run_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def update_run_degraded(conn: sqlite3.Connection, run_id: str, degraded: bool) -> None:
    """持久化「蕴含降级」标志(Lane D state["degraded"] → 落 SQLite,spec §11.5 横幅依赖)。"""
    conn.execute("UPDATE runs SET degraded=? WHERE run_id=?",
                 (1 if degraded else 0, run_id))
    conn.commit()


# 带 run_id 列的子表(供 delete_run 级联清理)。agent_skills 是 run 无关配置,故不在内。
# 显式常量取代旧 sqlite_master/PRAGMA 内省 —— Postgres 无这两个接口,显式列方言无关;
# schema 新增带 run_id 的表时,需同步加进本元组。
_RUN_SCOPED_TABLES = (
    "evidence", "analysis", "report", "decisions", "qc_result", "insight",
    "queries", "curation_drops", "trace", "annotations",
)


def delete_run(conn: sqlite3.Connection, run_id: str) -> bool:
    """整条删除一个 run 及其全部关联数据(_RUN_SCOPED_TABLES 各子表 + runs 本行)。

    返回 True if run 原本存在(删到了 runs 行),False 表示 run 不存在(供路由层返 404)。
    """
    if get_run(conn, run_id) is None:
        return False
    for t in _RUN_SCOPED_TABLES:
        conn.execute(f"DELETE FROM {t} WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
    conn.commit()
    return True


# ---- evidence ----
def insert_evidence(conn: sqlite3.Connection, run_id: str, ev: Evidence) -> None:
    # ON CONFLICT DO NOTHING:同 run 内重复 (run_id, id) 被 reducer 防过,这里是双保险
    # 防意外 IntegrityError 让 SSE 流崩(Codex 实测:重跑同 competitor+dim+url 会触发)。
    # 用标准 ON CONFLICT 而非 SQLite 私有 OR IGNORE,SQLite≥3.24 与 Postgres 一套 SQL 通吃。
    conn.execute(
        "INSERT INTO evidence (id, run_id, competitor, dimension, content, "
        "source_url, source_title, language, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (run_id, id) DO NOTHING",
        (ev.id, run_id, ev.competitor, ev.dimension, ev.content,
         ev.source_url, ev.source_title, ev.language, ev.fetched_at),
    )
    conn.commit()


def get_evidence(conn: sqlite3.Connection, evidence_id: str) -> Evidence | None:
    row = conn.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
    if row is None:
        return None
    return Evidence(
        id=row["id"], competitor=row["competitor"], dimension=row["dimension"],
        content=row["content"], source_url=row["source_url"],
        source_title=row["source_title"], language=row["language"],
        fetched_at=row["fetched_at"],
    )


def list_evidence(conn: sqlite3.Connection, run_id: str) -> list[Evidence]:
    # 插入顺序排序:SQLite 用隐式 rowid;Postgres 无 rowid,evidence 也无自增列,
    # 用 (fetched_at, id) 近似插入序(fetched_at 大致即采集序,id 派生 hash 作稳定 tiebreaker)。
    order = "fetched_at, id" if getattr(conn, "dialect", "") == "pg" else "rowid"
    rows = conn.execute(f"SELECT * FROM evidence WHERE run_id=? ORDER BY {order}", (run_id,))
    return [
        Evidence(
            id=r["id"], competitor=r["competitor"], dimension=r["dimension"],
            content=r["content"], source_url=r["source_url"],
            source_title=r["source_title"], language=r["language"],
            fetched_at=r["fetched_at"],
        )
        for r in rows
    ]


# ---- analysis ----
def save_analysis(conn: sqlite3.Connection, run_id: str,
                  analysis: CompetitorAnalysis) -> None:
    conn.execute(
        "INSERT INTO analysis (run_id, payload, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT (run_id) DO UPDATE SET payload=excluded.payload, created_at=excluded.created_at",
        (run_id, analysis.model_dump_json(), _now()),
    )
    conn.commit()


def get_analysis(conn: sqlite3.Connection, run_id: str) -> CompetitorAnalysis | None:
    row = conn.execute("SELECT payload FROM analysis WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return CompetitorAnalysis.model_validate_json(row["payload"])


# ---- report ----
def save_report(conn: sqlite3.Connection, run_id: str, markdown: str) -> None:
    conn.execute(
        "INSERT INTO report (run_id, markdown, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT (run_id) DO UPDATE SET markdown=excluded.markdown, created_at=excluded.created_at",
        (run_id, markdown, _now()),
    )
    conn.commit()


def get_report(conn: sqlite3.Connection, run_id: str) -> str | None:
    row = conn.execute("SELECT markdown FROM report WHERE run_id=?", (run_id,)).fetchone()
    return row["markdown"] if row else None


# ---- decisions(full-C / Epic 2.4)----
def save_decisions(conn: sqlite3.Connection, run_id: str,
                   decision_set: DecisionSet) -> None:
    conn.execute(
        "INSERT INTO decisions (run_id, payload, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT (run_id) DO UPDATE SET payload=excluded.payload, created_at=excluded.created_at",
        (run_id, decision_set.model_dump_json(), _now()),
    )
    conn.commit()


def get_decisions(conn: sqlite3.Connection, run_id: str) -> DecisionSet | None:
    row = conn.execute("SELECT payload FROM decisions WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return DecisionSet.model_validate_json(row["payload"])


# ---- qc_result(full-C / Epic 2.4)----
def save_qc_result(conn: sqlite3.Connection, run_id: str, result: QCResult) -> None:
    """持久化终态 QCResult(finalize 节点调用)。存全量(含 detail);/qc 端点 serve 时
    sanitize(qc.sanitize_qc_result),绝不把 detail 原文/模型文本暴露给公开端点。"""
    conn.execute(
        "INSERT INTO qc_result (run_id, payload, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT (run_id) DO UPDATE SET payload=excluded.payload, created_at=excluded.created_at",
        (run_id, result.model_dump_json(), _now()),
    )
    conn.commit()


def get_qc_result(conn: sqlite3.Connection, run_id: str) -> QCResult | None:
    row = conn.execute("SELECT payload FROM qc_result WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return QCResult.model_validate_json(row["payload"])


# ---- insight(full-C / Epic 2.4)----
def save_insight(conn: sqlite3.Connection, run_id: str, insight: ReportInsight) -> None:
    conn.execute(
        "INSERT INTO insight (run_id, payload, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT (run_id) DO UPDATE SET payload=excluded.payload, created_at=excluded.created_at",
        (run_id, insight.model_dump_json(), _now()),
    )
    conn.commit()


def get_insight(conn: sqlite3.Connection, run_id: str) -> ReportInsight | None:
    row = conn.execute("SELECT payload FROM insight WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return ReportInsight.model_validate_json(row["payload"])


# ---- trace ----
def append_trace(conn: sqlite3.Connection, run_id: str, node: str, *,
                 prompt: str = "", input_summary: str = "", output_summary: str = "",
                 tokens: int = 0, prompt_tokens: int = 0, completion_tokens: int = 0,
                 llm_calls: int = 0, latency_ms: int = 0) -> None:
    """一节点一行。token 四元组由 TokenMeter.trace_fields() 摊平传入;不调 LLM 的节点
    (collect 走 Tavily / finalize 纯本地)全 0 —— 那是真实的 0,不是缺数据。"""
    conn.execute(
        "INSERT INTO trace (run_id, node, prompt, input_summary, output_summary, "
        "tokens, prompt_tokens, completion_tokens, llm_calls, latency_ms, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, node, prompt, input_summary, output_summary, tokens, prompt_tokens,
         completion_tokens, llm_calls, latency_ms, _now()),
    )
    conn.commit()


def list_trace(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM trace WHERE run_id=? ORDER BY id", (run_id,))
    return [dict(r) for r in rows]


# ---- queries(Plan A:真实查询词检索台)----
def insert_queries(conn: sqlite3.Connection, run_id: str,
                   records: list[dict]) -> None:
    """批量插入真实查询词记录。records 每项:
    {competitor, dimension, language, query_text, round, hit_count}。
    在 collect_node 主线程一次性写(worker 线程只 emit + 收集,不并发写 sqlite)。"""
    if not records:
        return
    now = _now()
    conn.executemany(
        "INSERT INTO queries (run_id, competitor, dimension, language, "
        "query_text, round, hit_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(run_id, r["competitor"], r["dimension"], r["language"],
          r["query_text"], int(r.get("round", 0)), int(r.get("hit_count", 0)), now)
         for r in records],
    )
    conn.commit()


def list_queries(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT competitor, dimension, language, query_text, round, hit_count, created_at "
        "FROM queries WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]


# ---- curation_drops(Plan B:策展剔除清单,REPLACE per scope)----
def replace_curation_drops(conn: sqlite3.Connection, run_id: str, scope: str,
                           items: list[dict]) -> None:
    """替换某 run+scope 的策展剔除清单(codex #2:qc/decide 每轮调,先删后插,绝不 append →
    多轮重试后被补回的 cell/decision 不留幽灵)。items:cell → {"competitor","dimension"};
    decision → {"detail"}。空列表 = 清空该 scope。在 qc_node(cell)/decide_node(decision)主线程调。"""
    now = _now()
    conn.execute("DELETE FROM curation_drops WHERE run_id=? AND scope=?", (run_id, scope))
    if items:
        conn.executemany(
            "INSERT INTO curation_drops (run_id, scope, competitor, dimension, detail, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(run_id, scope, it.get("competitor", ""), it.get("dimension", ""),
              it.get("detail", ""), now) for it in items],
        )
    conn.commit()


def list_curation_drops(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT scope, competitor, dimension, detail, created_at FROM curation_drops "
        "WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]


# ---- agent_skills(Plan C:run 无关的 agent 技能配置,upsert per (agent_id, skill_id))----
def upsert_agent_skill(conn: sqlite3.Connection, agent_id: str, skill_id: str,
                       version: str, enabled: bool) -> None:
    conn.execute(
        "INSERT INTO agent_skills (agent_id, skill_id, version, enabled, installed_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(agent_id, skill_id) DO UPDATE SET "
        "version=excluded.version, enabled=excluded.enabled",
        (agent_id, skill_id, version, 1 if enabled else 0, _now()),
    )
    conn.commit()


def list_agent_skills(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT agent_id, skill_id, version, enabled, installed_at FROM agent_skills "
        "ORDER BY agent_id, installed_at").fetchall()
    return [
        {"agent_id": r["agent_id"], "skill_id": r["skill_id"], "version": r["version"],
         "enabled": bool(r["enabled"]), "installed_at": r["installed_at"]}
        for r in rows
    ]


def delete_agent_skill(conn: sqlite3.Connection, agent_id: str, skill_id: str) -> None:
    conn.execute("DELETE FROM agent_skills WHERE agent_id=? AND skill_id=?",
                 (agent_id, skill_id))
    conn.commit()


# ---- runs list ----
def list_runs(conn: sqlite3.Connection, *, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [
        {
            "run_id": r["run_id"],
            "competitors": json.loads(r["competitors"]),
            "dimensions": json.loads(r["dimensions"]),
            "status": r["status"],
            "degraded": bool(r["degraded"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---- annotations(spec §11.6 D10 桩,§17 人工质疑率)----
def insert_annotation(conn: sqlite3.Connection, *, run_id: str,
                      evidence_id: str | None, conclusion_path: str | None,
                      note: str) -> int:
    # 取新行主键:SQLite 用 cursor.lastrowid;Postgres 无 lastrowid,用 RETURNING id 取回。
    if getattr(conn, "dialect", "") == "pg":
        cur = conn.execute(
            "INSERT INTO annotations (run_id, evidence_id, conclusion_path, note, created_at) "
            "VALUES (?, ?, ?, ?, ?) RETURNING id",
            (run_id, evidence_id, conclusion_path, note, _now()),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return int(new_id)
    cur = conn.execute(
        "INSERT INTO annotations (run_id, evidence_id, conclusion_path, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, evidence_id, conclusion_path, note, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_annotations(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM annotations WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [
        {
            "id": r["id"],
            "run_id": r["run_id"],
            "evidence_id": r["evidence_id"],
            "conclusion_path": r["conclusion_path"],
            "note": r["note"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
