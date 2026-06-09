"""Supabase(Postgres)真打冒烟:验 db.py PG 路径 + repository 方言改造端到端正确。

跑法(不经聊天泄露连接串):
    DATABASE_URL=$(cat ~/.rr_supabase_url) .venv/bin/python spikes/spike_supabase_crud.py

前置:pip install 'psycopg[binary]'(本地默认 SQLite 不装;Render 靠 pyproject 装)。
DATABASE_URL 必须是 postgres:// / postgresql://(Supabase Session pooler 串,端口 5432)。

设计:用独立 run_id="rr_pg_smoke" + agent_id="rr_pg_smoke_agent",首尾各清一次,
绝不污染既有数据。每段打 [PASS];任一断言失败立刻抛 AssertionError 中止。
spike 不进 pytest(testpaths=["tests"]),真打外部服务专用。
"""
from __future__ import annotations

import os
import sys

# 守门:必须显式给 postgres:// 连接串,否则会误打本地 SQLite,这个 spike 就没意义了
_url = os.getenv("DATABASE_URL", "").strip()
if not (_url.startswith("postgres://") or _url.startswith("postgresql://")):
    sys.exit("ERROR: 需要 DATABASE_URL=postgres://...(Supabase 连接串)才能验 PG 路径")

from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db
from rivalradar.schema.models import (
    ComparisonCell, ComparisonRow, CompetitorAnalysis, Decision, DecisionSet,
    Evidence, QCResult, ReportInsight,
)

RUN = "rr_pg_smoke"
AGENT = "rr_pg_smoke_agent"


def _ev(eid: str, fetched_at: str) -> Evidence:
    return Evidence(
        id=eid, competitor="Notion", dimension="pricing",
        content="Free / Plus $10", source_url="https://notion.so/pricing",
        source_title="Pricing", language="en", fetched_at=fetched_at,
    )


def main() -> None:
    conn = connect("unused-when-pg")  # PG 模式忽略 path 参数
    assert getattr(conn, "dialect", "") == "pg", "未走 PG 分支(dialect 应为 pg)"
    init_db(conn)
    print(f"[PASS] connect + init_db(PG):dialect={conn.dialect}")

    # 幂等前置清理(上次跑残留)
    repo.delete_run(conn, RUN)
    repo.delete_agent_skill(conn, AGENT, "deep-research")

    # ── runs 生命周期 ──────────────────────────────────────────────
    repo.create_run(conn, RUN, ["Notion", "Coda"], ["pricing"],
                    decision_context="选型给中小团队")
    got = repo.get_run(conn, RUN)
    assert got is not None and got["competitors"] == ["Notion", "Coda"]
    assert got["decision_context"] == "选型给中小团队"
    assert got["degraded"] is False and got["status"] == "running"
    repo.update_run_status(conn, RUN, "running")  # 保持 running 给下面 CAS 用
    repo.update_run_degraded(conn, RUN, True)
    assert repo.get_run(conn, RUN)["degraded"] is True
    assert RUN in {r["run_id"] for r in repo.list_runs(conn)}
    print("[PASS] runs CRUD + degraded 标志(INTEGER 0/1 ↔ bool)")

    # ── evidence:ON CONFLICT DO NOTHING 去重 + PG 排序分支 ─────────
    repo.insert_evidence(conn, RUN, _ev("ev1", "2026-06-09T10:00:00Z"))
    repo.insert_evidence(conn, RUN, _ev("ev1", "2026-06-09T10:00:00Z"))  # 重复 → 应被吞
    repo.insert_evidence(conn, RUN, _ev("ev2", "2026-06-09T10:05:00Z"))
    evs = repo.list_evidence(conn, RUN)
    assert len(evs) == 2, f"ON CONFLICT DO NOTHING 去重失败:期望 2 条,实得 {len(evs)}"
    assert [e.id for e in evs] == ["ev1", "ev2"], f"fetched_at 排序失败:{[e.id for e in evs]}"
    assert repo.get_evidence(conn, "ev1") is not None
    print("[PASS] evidence ON CONFLICT DO NOTHING 去重 + list_evidence(fetched_at,id)排序")

    # ── 5 个 save_*:ON CONFLICT DO UPDATE 覆盖语义(写两遍验更新)─
    a1 = CompetitorAnalysis(comparison=[ComparisonRow(
        dimension="pricing",
        cells=[ComparisonCell(competitor="Notion", value_type="quote_text", value="v1")])])
    a2 = CompetitorAnalysis(comparison=[ComparisonRow(
        dimension="pricing",
        cells=[ComparisonCell(competitor="Notion", value_type="quote_text", value="v2")])])
    repo.save_analysis(conn, RUN, a1)
    repo.save_analysis(conn, RUN, a2)  # 应覆盖,不报 PK 冲突
    got_a = repo.get_analysis(conn, RUN)
    assert got_a is not None and got_a.comparison[0].cells[0].value == "v2", "analysis upsert 未覆盖"

    repo.save_report(conn, RUN, "# R1")
    repo.save_report(conn, RUN, "# R2")
    assert repo.get_report(conn, RUN) == "# R2", "report upsert 未覆盖"

    ds = DecisionSet(decisions=[Decision(
        stance="建议采用", action="上线 Plus 档对标", horizon="短期",
        risk_reversibility="可逆", risk_cost="低", why="证据充分")])
    repo.save_decisions(conn, RUN, ds)
    repo.save_decisions(conn, RUN, ds)
    assert len(repo.get_decisions(conn, RUN).decisions) == 1, "decisions upsert 未覆盖"

    repo.save_qc_result(conn, RUN, QCResult(verdict="pass"))
    repo.save_qc_result(conn, RUN, QCResult(verdict="pass"))
    assert repo.get_qc_result(conn, RUN).verdict == "pass", "qc_result upsert 未覆盖"

    ins = ReportInsight(market_context="赛道格局", differentiation_thesis="路径分歧",
                        actionable_takeaway="短中长期")
    repo.save_insight(conn, RUN, ins)
    repo.save_insight(conn, RUN, ins)
    assert repo.get_insight(conn, RUN).market_context == "赛道格局", "insight upsert 未覆盖"
    print("[PASS] 5×save_* ON CONFLICT DO UPDATE 覆盖语义(写两遍不冲突、取回最新)")

    # ── trace / queries / curation_drops(BIGSERIAL 自增 + executemany)─
    repo.append_trace(conn, RUN, "collect", tokens=10, latency_ms=20)
    repo.append_trace(conn, RUN, "analyze", tokens=30, latency_ms=40)
    tr = repo.list_trace(conn, RUN)
    assert len(tr) == 2 and tr[0]["node"] == "collect", "trace 自增/排序异常"

    repo.insert_queries(conn, RUN, [
        {"competitor": "Notion", "dimension": "pricing", "language": "en",
         "query_text": "Notion pricing 2026", "round": 0, "hit_count": 3}])
    assert len(repo.list_queries(conn, RUN)) == 1, "queries 写入异常"

    repo.replace_curation_drops(conn, RUN, "cell", [
        {"competitor": "Coda", "dimension": "pricing"}])
    repo.replace_curation_drops(conn, RUN, "cell", [])  # 清空该 scope(先删后插语义)
    assert len(repo.list_curation_drops(conn, RUN)) == 0, "curation_drops replace 清空失败"
    print("[PASS] trace/queries/curation_drops(BIGSERIAL + executemany + replace)")

    # ── agent_skills:upsert(已有 ON CONFLICT)+ dict_row 列名访问 ──
    repo.upsert_agent_skill(conn, AGENT, "deep-research", "v1", True)
    repo.upsert_agent_skill(conn, AGENT, "deep-research", "v2", False)  # 覆盖
    skills = [s for s in repo.list_agent_skills(conn) if s["agent_id"] == AGENT]
    assert len(skills) == 1 and skills[0]["version"] == "v2", "agent_skills upsert 异常"
    assert skills[0]["enabled"] is False, "enabled INTEGER→bool 转换异常"
    print("[PASS] agent_skills upsert + list_agent_skills 列名访问(dict_row 不支持位置)")

    # ── annotations:INSERT ... RETURNING id 分支 ───────────────────
    aid = repo.insert_annotation(conn, run_id=RUN, evidence_id="ev1",
                                 conclusion_path=None, note="可疑定价")
    assert isinstance(aid, int) and aid > 0, f"RETURNING id 未取回有效主键:{aid!r}"
    anns = repo.list_annotations(conn, RUN)
    assert len(anns) == 1 and anns[0]["note"] == "可疑定价"
    print(f"[PASS] annotations INSERT...RETURNING id(取回 id={aid})")

    # ── delete_run:_RUN_SCOPED_TABLES 级联清理 ─────────────────────
    assert repo.delete_run(conn, RUN) is True, "delete_run 应返 True(run 存在)"
    assert repo.get_run(conn, RUN) is None, "runs 行未删"
    assert repo.list_evidence(conn, RUN) == [], "evidence 级联未删"
    assert repo.get_analysis(conn, RUN) is None, "analysis 级联未删"
    assert repo.list_trace(conn, RUN) == [], "trace 级联未删"
    assert repo.list_annotations(conn, RUN) == [], "annotations 级联未删"
    assert repo.delete_run(conn, RUN) is False, "二次 delete 应返 False(run 不存在)"
    print("[PASS] delete_run 级联清理 _RUN_SCOPED_TABLES + 404 语义")

    # ── 事务污染恢复(/review HIGH#1 fix:_PgConnection 失败即 rollback)──────
    # 故意制造一条写失败(重复主键 run_id),验连接没被 abort 污染:之后正常写仍成功。
    # 这是 happy-path 冒烟测不到、却让 run 卡死 running 的真实场景(Claude+Codex 跨模型一致 block)。
    repo.create_run(conn, RUN, ["X"], ["pricing"])  # 上面已 delete,这里重建(status=running)
    poisoned_raise = False
    try:
        repo.create_run(conn, RUN, ["X"], ["pricing"])  # 同 run_id 重复 → UniqueViolation,abort 事务
    except Exception:
        poisoned_raise = True
    assert poisoned_raise, "重复 create_run 应抛错(用于触发事务 abort)"
    # 关键断言:若连接被污染,下面这条会报 InFailedSqlTransaction;rollback 修复后应正常落库
    repo.update_run_status(conn, RUN, "done")
    assert repo.get_run(conn, RUN)["status"] == "done", \
        "写失败后连接被污染 → 后续写无声失败(HIGH#1 未修)"
    repo.delete_run(conn, RUN)
    print("[PASS] 事务污染恢复:写失败→rollback→连接未污染→后续写正常(HIGH#1 fix)")

    # 收尾:清掉 run 无关的 agent_skill,Supabase 回到干净态
    repo.delete_agent_skill(conn, AGENT, "deep-research")
    conn.close()
    print("\n✅ ALL PG SMOKE CHECKS PASSED — Supabase 迁移 PG 路径端到端验证通过")


if __name__ == "__main__":
    main()
