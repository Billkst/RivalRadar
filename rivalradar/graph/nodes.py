from __future__ import annotations

import logging
import time
from typing import Any, Callable

from rivalradar.agents.analyst import analyze
from rivalradar.agents.collector import collect_evidence
from rivalradar.agents.writer import generate_decisions, render_body, write_report_with_insight
from rivalradar.graph.router import extract_collect_targets
from rivalradar.agents import qc
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, DecisionSet, Evidence, QCResult,
)
from rivalradar.storage.repository import (
    append_trace, insert_evidence, mark_run_finalized, save_analysis,
    save_decisions, save_insight, save_qc_result, save_report, update_run_degraded,
)

logger = logging.getLogger(__name__)


# ── Epic 2.3-2.6:emit-driven progress events(plan v3.2 §5)─────────────────
# emit callback 由 sse.py 通过 config["configurable"]["emit"] 注入。Tests 不传
# emit,_get_emit 返 None,_emit_progress 是 no-op,backward compat。
def _get_emit(config: dict) -> Callable[[str, dict[str, Any]], None] | None:
    """从 langgraph config 取 emit callback;tests 不传 emit 时返 None。"""
    return config.get("configurable", {}).get("emit")


def _emit_progress(
    emit: Callable[[str, dict[str, Any]], None] | None,
    agent_id: str,
    step: str,
    summary: str,
    metric: dict[str, int] | None = None,
) -> None:
    """发 progress event(no-op if emit is None — tests / CLI 调用 path)。

    payload 跟 backend api/schemas.py SSEProgressData + frontend types/api.ts
    SSEProgressData 字段一致:agent_id / step / summary / metric / ts。ts 由
    sse.py emit() 自动注入。
    """
    if emit is None:
        return
    payload: dict[str, Any] = {
        "agent_id": agent_id,
        "step": step,
        "summary": summary,
    }
    if metric is not None:
        payload["metric"] = metric
    emit("progress", payload)


def make_collect_node(*, conn, provider, official_domains, max_results: int = 5):
    """采集节点:首遍全量采;retry 时按 qc issues 只补缺口 + broaden 广搜。
    只 insert 真新增(对 state 已有 id 去重),证据 dict 由 reducer 累加去重。"""
    def collect_node(state, config):
        run_id = config["configurable"]["thread_id"]
        emit = _get_emit(config)
        t0 = time.monotonic()
        existing = {e["id"] for e in state.get("evidence", [])}
        qc_result = state.get("qc_result")
        if qc_result is None:
            _emit_progress(
                emit, "collector", "search",
                f"开始搜索 {len(state['competitors'])} 个竞品 × {len(state['dimensions'])} 个维度",
            )
            evs = collect_evidence(state["competitors"], state["dimensions"],
                                   provider=provider, official_domains=official_domains,
                                   max_results=max_results)
            tgt_desc = "all"
        else:
            targets = extract_collect_targets(
                qc_result["issues"], state["competitors"],
                allowed_dimensions=tuple(state.get("dimensions") or CONTROLLED_DIMENSIONS))
            _emit_progress(
                emit, "collector", "broaden",
                f"按质检反馈广搜 {len(targets)} 个证据缺口",
                metric={"current": 0, "total": len(targets)},
            )
            evs = []
            for comp, dim in targets:
                evs += collect_evidence([comp], [dim], provider=provider,
                                        official_domains=official_domains,
                                        max_results=max_results, broaden=True)
            tgt_desc = f"{len(targets)} gaps"
        fresh = [e for e in evs if e.id not in existing]
        for e in fresh:
            insert_evidence(conn, run_id, e)
        _emit_progress(
            emit, "collector", "done",
            f"找到 {len(fresh)} 条新证据,累计 {len(existing) + len(fresh)} 条",
            metric={"current": len(fresh), "total": len(existing) + len(fresh)},
        )
        append_trace(conn, run_id, "collect",
                     input_summary=f"targets={tgt_desc}",
                     output_summary=f"+{len(fresh)} (total {len(existing) + len(fresh)})",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"evidence": [e.model_dump() for e in fresh]}
    return collect_node


def make_analyze_node(*, conn, client, model):
    """分析节点:state 证据 dict → Evidence → analyze() → CompetitorAnalysis → 落库。"""
    def analyze_node(state, config):
        run_id = config["configurable"]["thread_id"]
        emit = _get_emit(config)
        t0 = time.monotonic()
        evidence = [Evidence(**d) for d in state["evidence"]]
        _emit_progress(
            emit, "analyst", "thinking",
            f"正在分析 {len(evidence)} 条证据,提取 {len(state['competitors'])} 个竞品的特征",
        )
        # 收集本轮 profile 抽取降级(单项 LLM 截断/失败优雅降级,见 analyst._safe_extract)。
        # 非空 → 置 run 级 degraded,保证「降级必可见」(否则整竞品 profile 半瘫却 done)。
        degraded_sink: list[str] = []
        analysis = analyze(evidence, state["competitors"],
                           dimensions=tuple(state.get("dimensions") or CONTROLLED_DIMENSIONS),
                           degraded_sink=degraded_sink, client=client, model=model)
        save_analysis(conn, run_id, analysis)
        _emit_progress(
            emit, "analyst", "done",
            f"完成分析:{len(analysis.competitors)} 个竞品 profile + {len(analysis.comparison)} 维对比",
            metric={"current": len(analysis.competitors), "total": len(state["competitors"])},
        )
        # 降级 marker 折进现有 trace 行(一节点一 trace 行,reviewer ISSUE A),不另起一行。
        degraded_note = f" (降级: {', '.join(degraded_sink)})" if degraded_sink else ""
        append_trace(conn, run_id, "analyze",
                     input_summary=f"{len(evidence)} evidence",
                     output_summary=f"{len(analysis.competitors)} profiles, "
                                    f"{len(analysis.comparison)} rows{degraded_note}",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        out: dict = {"analysis": analysis.model_dump()}
        if degraded_sink:
            out["degraded"] = True  # qc_node read-then-OR 保 sticky 到 finalize
        return out
    return analyze_node


def make_write_node(*, conn, client, model, as_of):
    """撰写节点:CompetitorAnalysis + 证据 → 混合报告 → 落库。"""
    def write_node(state, config):
        run_id = config["configurable"]["thread_id"]
        emit = _get_emit(config)
        t0 = time.monotonic()
        analysis = CompetitorAnalysis(**state["analysis"])
        evidence = [Evidence(**d) for d in state["evidence"]]
        _emit_progress(
            emit, "writer", "drafting",
            f"正在撰写 {len(analysis.competitors)} 个竞品的对比报告",
        )
        report, insight = write_report_with_insight(
            analysis, evidence, as_of=as_of, client=client, model=model)
        save_report(conn, run_id, report)
        save_insight(conn, run_id, insight)  # Epic 2.4:结构化洞察持久化(/insight 端点)
        _emit_progress(
            emit, "writer", "done",
            f"完成报告 {len(report)} 字",
            metric={"current": len(report), "total": len(report)},
        )
        append_trace(conn, run_id, "write",
                     input_summary=f"analysis of {len(state['analysis'].get('competitors', []))} competitors",
                     output_summary=f"report {len(report)} chars",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"report": report}
    return write_node


def make_qc_node(*, conn, client, model):
    """质检节点(策展人模型):curate_analysis 丢弃站不住的对比 cell(机械悬空 + LLM 蕴含
    不支撑),持久化策展后的分析;再跑确定性门(traceability comparison_only + ontology +
    coverage 请求维度)定 verdict。策展丢空维度 → low_coverage → retry_collect 补搜环。
    curate 的 LLM 蕴含失败 → degraded + 机械门 fallback(必办项①),绝不崩整图。
    retry_count 仅在「带着上一轮 qc_result 进来」时 +1(每轮唯一计数点,避免双重计数)。
    """
    def qc_node(state, config):
        run_id = config["configurable"]["thread_id"]
        emit = _get_emit(config)
        t0 = time.monotonic()
        analysis = CompetitorAnalysis(**state["analysis"])
        evidence = [Evidence(**d) for d in state["evidence"]]
        _emit_progress(
            emit, "qc", "validate",
            f"开始质检 {len(analysis.competitors)} 个竞品 profile",
        )
        requested_dims = tuple(state.get("dimensions") or CONTROLLED_DIMENSIONS)
        # 策展(信任模型「否决闸」→「策展人」):站不住的对比 cell(机械悬空 + LLM 蕴含
        # 不支撑)被丢弃,而非把整个 run 打回 retry_analyze → 耗尽 degraded。人类分析师不
        # 因某格证据薄就给整份报告盖降级章,而是只展示站得住的。LLM 蕴含失败(网络/限流)→
        # 降级 + 机械门 fallback(只丢悬空,免 LLM)。
        local_degraded = False
        try:
            curated, dropped = qc.curate_analysis(
                analysis, evidence, dimensions=requested_dims, client=client, model=model)
        except Exception as e:  # noqa: BLE001 — 蕴含是尽力而为辅助闸,任何失败都降级,绝不崩整图(必办项①/spec §5)
            local_degraded = True
            # 只记 type(e).__name__,**绝不**写 str(e) 入 trace(GET /trace/:run 公开暴露,
            # Codex Critical #1:OpenAI APIStatusError str() 可能含 Authorization → 泄 KEY)
            logger.exception("qc curate failed for run %s", run_id)
            append_trace(conn, run_id, "qc",
                         output_summary=f"curate degraded: {type(e).__name__}")
            curated, dropped = qc._curate_mechanical(analysis, evidence, requested_dims)
        # 持久化策展后的分析(showcase 只显示活下来的 cell),并经 state 传给 decide 节点
        # (decide 用 curated body 生成决策,不会基于已丢弃的 cell)。
        save_analysis(conn, run_id, curated)

        # 确定性门跑在**策展后**的分析上:traceability(comparison_only,策展后应已干净)+
        # ontology + coverage(只查请求维度)。策展丢空某维度 → low_coverage → retry_collect →
        # broaden 补搜环(诚实自纠 money-shot);broaden 补到有据证据后重分析再策展,收敛成
        # pass 或诚实 insufficient,绝不再因 hallucination 盖 degraded 章。
        issues = qc.check_traceability(curated, evidence, comparison_only=True)
        issues += qc.check_ontology(curated, evidence)
        issues += qc.check_coverage(curated, required=requested_dims)
        # degraded sticky OR 累积:一旦任何一轮发生蕴含降级,持续标记到 finalize(而非每轮
        # 覆盖)— 防 round 1 降级 / round 2 成功 → 终态 degraded=False 隐瞒"曾降级"。
        degraded = bool(state.get("degraded", False)) or local_degraded
        verdict = qc.decide_verdict(issues)
        result = QCResult(verdict=verdict, issues=issues)
        prior = state.get("qc_result")
        new_rc = state["retry_count"] + (1 if prior is not None else 0)
        # 中文 verdict 映射(plan v3.2 §3 5 UI state cancelled 风格):告诉用户镜湖的裁决。
        verdict_zh = {
            "pass": "通过",
            "retry_collect": "证据不足,打回收集",
            "retry_analyze": "分析有误,打回分析",
            "insufficient_evidence": "证据耗尽,标降级",
        }.get(verdict, verdict)
        _emit_progress(
            emit, "qc", "done",
            f"裁决:{verdict_zh}(策展 {len(dropped)} 项 / 发现 {len(issues)} 项问题,第 {new_rc + 1} 轮)",
            metric={"current": len(issues), "total": len(issues)},
        )
        append_trace(conn, run_id, "qc",
                     input_summary=f"{len(evidence)} evidence",
                     output_summary=f"verdict={verdict} curated={len(dropped)} issues={len(issues)} "
                                    f"degraded={degraded} retry={new_rc}",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"analysis": curated.model_dump(), "qc_result": result.model_dump(),
                "retry_count": new_rc, "degraded": degraded}
    return qc_node


def make_decide_node(*, conn, client, model, as_of):
    """决策节点(full-C / Epic 2.2-2.3,策展人模型):分析正文(已被 qc 策展)+ 用户处境 →
    结构化决策建议,curate_decisions 丢弃 ungrounded 决策(机械悬空 + LLM 蕴含不支撑),
    只留站得住的。ungrounded 决策被丢弃而非标 decision_degraded —— 与 qc_node 策展对称。

    错误契约(对齐 qc 节点必办项①):generate 失败 → 空决策 + degraded;curate 蕴含失败 →
    机械门 fallback(只丢悬空)+ degraded。绝不崩整图。decision_degraded 只为真·LLM 失败保留。
    """
    def decide_node(state, config):
        run_id = config["configurable"]["thread_id"]
        emit = _get_emit(config)
        t0 = time.monotonic()
        analysis = CompetitorAnalysis(**state["analysis"])  # 已被 qc_node 策展
        evidence = [Evidence(**d) for d in state["evidence"]]
        decision_context = state.get("decision_context") or ""
        body = render_body(analysis, evidence, as_of=as_of)  # 确定性,无 LLM
        _emit_progress(emit, "decide", "deciding", "正在基于证据生成决策建议")

        decision_degraded = False
        try:
            decision_set = generate_decisions(body, decision_context, client=client, model=model)
        except Exception as e:  # noqa: BLE001 — 生成失败降级,绝不崩图
            logger.exception("decide generate failed for run %s", run_id)
            append_trace(conn, run_id, "decide",
                         output_summary=f"generate degraded: {type(e).__name__}")
            decision_set = DecisionSet(decisions=[])
            decision_degraded = True
        else:
            # 策展:丢弃 ungrounded 决策(机械悬空免 LLM + 蕴含不支撑),只留站得住的。
            try:
                kept, _dropped = qc.curate_decisions(
                    decision_set.decisions, evidence, client=client, model=model)
                decision_set = DecisionSet(decisions=kept)
            except Exception as e:  # noqa: BLE001 — 蕴含失败:机械门 fallback(只丢悬空)+ 降级,绝不崩图
                logger.exception("decide curate failed for run %s", run_id)
                append_trace(conn, run_id, "decide",
                             output_summary=f"entailment degraded: {type(e).__name__}")
                valid = {ev.id for ev in evidence}
                kept = [d for d in decision_set.decisions
                        if d.evidence_refs and all(r.evidence_id in valid for r in d.evidence_refs)]
                decision_set = DecisionSet(decisions=kept)
                decision_degraded = True

        save_decisions(conn, run_id, decision_set)
        _emit_progress(
            emit, "decide", "done",
            f"生成 {len(decision_set.decisions)} 条决策建议"
            + ("(蕴含降级,机械门兜底)" if decision_degraded else ""),
            metric={"current": len(decision_set.decisions),
                    "total": len(decision_set.decisions)},
        )
        append_trace(conn, run_id, "decide",
                     input_summary=f"context={'set' if decision_context else 'generic'}",
                     output_summary=f"decisions={len(decision_set.decisions)} "
                                    f"degraded={decision_degraded}",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"decisions": decision_set.model_dump(), "decision_degraded": decision_degraded}
    return decide_node


_BANNER_INSUFFICIENT = (
    "> ⚠️ **数据不足**:部分维度在有界广搜后仍未找到公开数据。"
    "以下为现有证据下的结论(诚实标注优于编造)。\n\n"
)
_BANNER_DEGRADED = (
    "> ⚠️ **未达质检标准**:存在未消解的质检问题,以下结论请谨慎参考。\n\n"
)
_BANNER_PARTIAL = (
    "> ℹ️ **覆盖说明**:个别维度公开资料有限,已在对比矩阵中以「—」如实标注。"
    "下列对比与决策建议**均有据可溯**(策展时已剔除证据撑不住的结论)。\n\n"
)


def _has_substantive_output(state: dict) -> bool:
    """重试耗尽时判「是否有可交付的有据产出」:策展后矩阵 cell + 决策。
    真 run 暴露——89% 满的矩阵 + 5 条决策被旧逻辑盖「数据不足」章是错的:覆盖度闸
    本是策展人不是法官,有可展示的有据内容就该 done(缺格显「—」),只有几乎空手才
    insufficient/degraded。决策直接挂证据(不依赖矩阵完整),故任一非空即算有产出。"""
    analysis = state.get("analysis") or {}
    matrix_cells = sum(len(r.get("cells", [])) for r in analysis.get("comparison", []))
    decisions = (state.get("decisions") or {}).get("decisions", [])
    return matrix_cells > 0 or len(decisions) > 0


def make_finalize_node(*, conn, max_retries):
    """终态节点(策展人模型):pass → done;重试耗尽时按**策展后实际产出**决定终态——
    有可交付的有据内容(矩阵 cell + 决策)→ done(缺维度矩阵显「—」+ 轻量覆盖说明),
    真·几乎空手才 insufficient(retry_collect 耗尽)/ degraded(retry_analyze 耗尽)。

    route 保证只有 pass 或耗尽才进来(spec §4/§8 + 必办项③)。覆盖度从"全有或全无的
    法官"改"策展人"(真 run 暴露:89% 满却盖数据不足章是同一病的新症状)。
    """
    def finalize_node(state, config):
        run_id = config["configurable"]["thread_id"]
        result = dict(state["qc_result"])
        verdict = result["verdict"]
        report = state["report"]
        substantive = _has_substantive_output(state)
        if verdict == "pass":
            status = "done"
        elif substantive:
            # 重试耗尽但有可交付产出 → done。verdict 记 pass(可交付),issues 保留
            # 缺口记录(/qc 诚实显示"通过,有这些维度缺口");缺格矩阵显「—」+ 轻量说明。
            result["verdict"] = "pass"
            report = _BANNER_PARTIAL + report
            status = "done"
        elif verdict == "retry_collect":
            result["verdict"] = "insufficient_evidence"
            report = _BANNER_INSUFFICIENT + report
            status = "insufficient_evidence"
        else:  # retry_analyze 或其他耗尽,且几乎空手
            report = _BANNER_DEGRADED + report
            status = "degraded"
        save_report(conn, run_id, report)
        # Epic 2.4:持久化终态 QCResult(/qc 端点 sanitized serve)。result 已含本轮
        # 终态 verdict(可能被上面改写成 insufficient_evidence)。
        save_qc_result(conn, run_id, QCResult.model_validate(result))
        # post-ship review fix:mark_run_finalized CAS 守 expected='running',
        # 防 cancel race(cancel CAS 把 status 设 'cancelled' 后,finalize 内
        # 50ms sync 代码 跑完用非 CAS update_run_status 覆盖)。对称 mark_run_failed
        # /mark_run_cancelled CAS pattern。
        mark_run_finalized(conn, run_id, status)
        # 持久化降级标志(Lane D 遗留收口,spec §11.5 前端横幅依赖)。Epic 2.3:决策
        # 降级(decision_degraded)并入同一 degraded 信号 —— 用户看到的"以下结论请谨慎"
        # 横幅同样覆盖"决策未达溯源标准"(reuse degraded-on-failure pattern)。
        update_run_degraded(
            conn, run_id,
            bool(state.get("degraded", False)) or bool(state.get("decision_degraded", False)))
        append_trace(conn, run_id, "finalize",
                     output_summary=f"status={status} verdict={result['verdict']}")
        return {"report": report, "qc_result": result, "status": status}
    return finalize_node
