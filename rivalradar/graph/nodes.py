from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from rivalradar.agents.analyst import analyze, build_comparison
from rivalradar.agents.collector import collect_evidence
from rivalradar.agents.writer import (
    generate_decisions, generate_insight, render_body, stitch_report,
    write_report_with_insight,
)
from rivalradar.graph.router import extract_collect_targets
from rivalradar.agents import qc
from rivalradar.llm.runcontrol import wrap_client
from rivalradar.schema.models import (
    CONTROLLED_DIMENSIONS, CompetitorAnalysis, DecisionSet, Evidence, QCResult,
    ReportInsight,
)
from rivalradar.storage.repository import (
    append_trace, insert_evidence, insert_queries, mark_run_finalized, save_analysis,
    save_decisions, save_insight, save_qc_result, save_report, update_run_degraded,
)

logger = logging.getLogger(__name__)


# ── Epic 2.3-2.6:emit-driven progress events(plan v3.2 §5)─────────────────
# emit callback 由 sse.py 通过 config["configurable"]["emit"] 注入。Tests 不传
# emit,_get_emit 返 None,_emit_progress 是 no-op,backward compat。
def _get_emit(config: dict) -> Callable[[str, dict[str, Any]], None] | None:
    """从 langgraph config 取 emit callback;tests 不传 emit 时返 None。"""
    return config.get("configurable", {}).get("emit")


def _run_client(client, config: dict):
    """按 config 注入的 RunControl 包装 client(每次 LLM 调用前查取消/超时)。
    无 control(单测/CLI)→ 原样返回 → 行为不变,backward compat。"""
    return wrap_client(client, config.get("configurable", {}).get("run_control"))


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


def _make_ticker(
    emit: Callable[[str, dict[str, Any]], None] | None,
    agent_id: str, step: str, total: int,
) -> Callable[[str], None] | None:
    """线程安全增量进度回调:长节点(analyze ~174s / qc ~94s / collect)内并行 worker 各自
    完成一个工作单元时调 tick(detail),锁内自增计数 + emit progress(current/total)。锁
    **串行化并发 put_nowait**(emit 桥跨 worker 线程→事件循环边界,见 sse.py)——这是从 worker
    线程安全 emit 的关键。emit is None(单测/CLI)→ 返 None,调用方据此跳过(零开销、向后兼容)。
    total 低估时 max(total,n) 兜底,进度条永不显示 >100%。"""
    if emit is None:
        return None
    lock = threading.Lock()
    counter = {"n": 0}

    def tick(detail: str) -> None:
        with lock:
            counter["n"] += 1
            n = counter["n"]
            _emit_progress(emit, agent_id, step, detail,
                           metric={"current": min(n, total), "total": max(total, n)})

    return tick


def _collect_round(state: dict) -> int:
    """采集轮次(spec §5.1 codex [P1] 防造假):首轮 qc_result 为 None → 0;retry 轮由
    qc_result 存在性推导(第一次 retry 时 retry_count 仍为 0,qc 节点首轮不 +1),故
    round = retry_count + 1。不能直接用 retry_count(会把第一次 retry 误标 round 0)。"""
    if state.get("qc_result") is None:
        return 0
    return int(state.get("retry_count", 0)) + 1


def make_collect_node(*, conn, provider, official_domains, max_results: int = 5):
    """采集节点:首遍全量采;retry 时按 qc issues 只补缺口 + broaden 广搜。
    只 insert 真新增(对 state 已有 id 去重),证据 dict 由 reducer 累加去重。"""
    def collect_node(state, config):
        run_id = config["configurable"]["thread_id"]
        emit = _get_emit(config)
        t0 = time.monotonic()
        existing = {e["id"] for e in state.get("evidence", [])}
        qc_result = state.get("qc_result")
        rnd = _collect_round(state)

        # 真实查询词检索台:每 query 完成发 query + query_hit 事件(worker 线程,emit 经
        # sse.py call_soon_threadsafe 线程安全),并收集 query 记录供主线程批量落库。
        q_records: list[dict] = []
        q_lock = threading.Lock()

        def on_query(q, evs):
            if emit is not None:
                emit("query", {"competitor": q.competitor, "dimension": q.dimension,
                               "query_text": q.query_text, "language": q.language, "round": rnd})
                emit("query_hit", {"query_text": q.query_text,
                                   "hit_count": len(evs), "round": rnd})
            with q_lock:
                q_records.append({"competitor": q.competitor, "dimension": q.dimension,
                                  "language": q.language, "query_text": q.query_text,
                                  "round": rnd, "hit_count": len(evs)})

        if qc_result is None:
            _emit_progress(
                emit, "collector", "search",
                f"开始搜索 {len(state['competitors'])} 个竞品 × {len(state['dimensions'])} 个维度",
            )
            # 增量进度:每 query 完成报一次(竞品×维度×2 语 = 总 query 数,采集段不再静默)。
            tick = _make_ticker(emit, "collector", "search",
                                len(state["competitors"]) * len(state["dimensions"]) * 2)
            evs = collect_evidence(state["competitors"], state["dimensions"],
                                   provider=provider, official_domains=official_domains,
                                   max_results=max_results, on_progress=tick, on_query=on_query)
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
            tick = _make_ticker(emit, "collector", "broaden", max(len(targets), 1) * 2)
            evs = []
            for comp, dim in targets:
                evs += collect_evidence([comp], [dim], provider=provider,
                                        official_domains=official_domains,
                                        max_results=max_results, broaden=True,
                                        on_progress=tick, on_query=on_query)
            tgt_desc = f"{len(targets)} gaps"

        fresh = [e for e in evs if e.id not in existing]
        for e in fresh:
            insert_evidence(conn, run_id, e)
            # 来源卡明细(spec §5.2):只发实际落库的新证据,不发 content 全文(点开走 REST)。
            if emit is not None:
                emit("source", {"evidence_id": e.id, "competitor": e.competitor,
                                "dimension": e.dimension, "source_title": e.source_title,
                                "source_url": e.source_url, "fetched_at": e.fetched_at,
                                "language": e.language, "round": rnd})
        # 真实查询词落库(主线程批量,worker 线程只收集,避免并发写 sqlite)。
        insert_queries(conn, run_id, q_records)
        # retry 增量(spec §5.4):本轮新增汇总,前端重试环显「第 N 轮 · 证据 X→Y」。
        total_after = len(existing) + len(fresh)
        if emit is not None:
            emit("evidence_delta", {"round": rnd, "added_count": len(fresh),
                                    "total_count": total_after,
                                    "new_evidence_ids": [e.id for e in fresh]})
        _emit_progress(
            emit, "collector", "done",
            f"找到 {len(fresh)} 条新证据,累计 {total_after} 条",
            metric={"current": len(fresh), "total": total_after},
        )
        append_trace(conn, run_id, "collect",
                     input_summary=f"targets={tgt_desc} round={rnd}",
                     output_summary=f"+{len(fresh)} (total {total_after})",
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
        dims = tuple(state.get("dimensions") or CONTROLLED_DIMENSIONS)

        def on_cell_row(dimension, row, status):
            if emit is None:
                return
            cells = [] if row is None else [
                {"competitor": c.competitor, "value_type": c.value_type, "value": c.value,
                 "evidence_refs": [{"evidence_id": r.evidence_id, "quote": r.quote}
                                   for r in c.evidence_refs]}
                for c in row.cells]
            emit("cell_row", {"dimension": dimension, "status": status, "cells": cells})
        # 收集本轮 profile 抽取降级(单项 LLM 截断/失败优雅降级,见 analyst._safe_extract)。
        # 非空 → 置 run 级 degraded,保证「降级必可见」(否则整竞品 profile 半瘫却 done)。
        degraded_sink: list[str] = []
        rc_client = _run_client(client, config)

        # post-real-run-7「坏维度精准重跑」:**仅 retry_analyze** 时复用上轮竞品画像,只重做对比矩阵。
        # 依据:qc 只对【对比矩阵 cell】做 entailment(comparison_only=True),retry_analyze 的
        # 触发因永远在对比层,且证据未变 → 竞品画像(features/pricing/personas/swot)无需重抽,
        # 省掉 N×4 次抽取调用(整轮重跑 → 只重对比,~省一半)。画像在 qc 策展中不被改(只丢对比 cell)。
        # **retry_collect 不走此路**:它补了新证据,画像必须用新证据重抽 → 仍走完整 analyze。
        prior = state.get("analysis")
        reuse_profiles = (prior is not None
                          and state.get("qc_result", {}).get("verdict") == "retry_analyze")
        profiles = None
        if reuse_profiles:
            # 兜底:上轮 analysis shape 异常(理论上不会——同进程 model_dump,无 checkpointer)→
            # 不崩,回退完整 analyze(与本节点「never crash the run」一致,见 _safe_extract)。
            try:
                profiles = CompetitorAnalysis(**prior).competitors
            except Exception:  # noqa: BLE001
                logger.warning("精准重跑:上轮 analysis 反序列化失败,回退完整 analyze")
                reuse_profiles = False
        if reuse_profiles:
            _emit_progress(emit, "analyst", "thinking",
                           f"重跑:复用 {len(profiles)} 个竞品画像,只重做对比矩阵(精准重跑)")
            tick = _make_ticker(emit, "analyst", "thinking", len(dims))  # 只剩对比阶段进度
            comparison = build_comparison(profiles, evidence, dimensions=dims,
                                          degraded_sink=degraded_sink, on_progress=tick,
                                          on_cell_row=on_cell_row, client=rc_client, model=model)
            analysis = CompetitorAnalysis(competitors=profiles, comparison=comparison)
        else:
            _emit_progress(
                emit, "analyst", "thinking",
                f"正在分析 {len(evidence)} 条证据,提取 {len(state['competitors'])} 个竞品的特征",
            )
            # 增量进度:每竞品 4 抽取 + 每维度 1 对比 = 总单元数,逐项 emit(最长静默段被打散成
            # 「竞品·抽取项」与「对比·维度」逐项亮起,post-real-run-7 把对比阶段从 1 格细分到 N 格)。
            tick = _make_ticker(emit, "analyst", "thinking", len(state["competitors"]) * 4 + len(dims))
            analysis = analyze(evidence, state["competitors"], dimensions=dims,
                               degraded_sink=degraded_sink, on_progress=tick,
                               on_cell_row=on_cell_row, client=rc_client, model=model)
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
            analysis, evidence, as_of=as_of, client=_run_client(client, config), model=model,
            emit=emit)
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
        # insight 经 state 传给 qc 节点:qc 策展后用 curated body 重拼报告时复用同一 insight
        # (不重生成,守 24/30 baseline)。见 make_qc_node 的反幻觉重渲染。
        return {"report": report, "insight": insight.model_dump()}
    return write_node


def make_qc_node(*, conn, client, model, as_of):
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
        # 增量进度:每个对比 cell 蕴含判完报一次(~94s 静默段 → 逐格亮起)。
        tick = _make_ticker(emit, "qc", "validate",
                            sum(len(r.cells) for r in analysis.comparison
                                if r.dimension in requested_dims))
        # 策展(信任模型「否决闸」→「策展人」):站不住的对比 cell(机械悬空 + LLM 蕴含
        # 不支撑)被丢弃,而非把整个 run 打回 retry_analyze → 耗尽 degraded。人类分析师不
        # 因某格证据薄就给整份报告盖降级章,而是只展示站得住的。LLM 蕴含失败(网络/限流)→
        # 降级 + 机械门 fallback(只丢悬空,免 LLM)。
        local_degraded = False
        try:
            curated, dropped = qc.curate_analysis(
                analysis, evidence, dimensions=requested_dims, on_progress=tick,
                client=_run_client(client, config), model=model)
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

        # 反幻觉收口(TODOS P2 + ship-time 对抗验证 MAJOR):report markdown 与 cockpit
        # 顶部 insight headline 都在 write 节点用**未策展** analysis 生成,被策展丢的 cell
        # 可能残留其中(check_traceability comparison_only 只校验对比矩阵 cell,管不到 report
        # markdown,也**从不校验 insight 自由文本**)。
        #   ① 用 curated analysis 重渲染 body(render_body 确定性,免 LLM)→ report 对比表 +
        #      来源清单与 /analysis 一致。
        #   ② **仅当策展真丢了 cell(dropped 非空)时**,用 curated body 重生成 insight + 覆盖
        #      落库 → 顶部 headline 不再引用被丢的结论。happy path(dropped 空 = 现有所有种子
        #      curated=0)零触发 → 不动 24/30 baseline、不多花一次 LLM。重生成本身不改
        #      generate_insight 逻辑,只是按需重调用(计划「不碰 generate_insight」不破)。
        #   重生成失败(网络/限流)→ 保留原 insight(pre-curation 但自洽)+ degraded(降级
        #   必可见),绝不崩图。insight 缺失(老 checkpoint / 直接单测 qc_node)时整段跳过,
        #   回退原 report(向后兼容)。重试轮里每轮 write→qc 都重做一次;收敛轮的产物流向 finalize。
        curated_report = None
        insight_dict = state.get("insight")
        if insight_dict is not None:
            insight_obj = ReportInsight(**insight_dict)
            curated_body = render_body(curated, evidence, as_of=as_of)
            if dropped:  # 策展真丢了 cell → headline 须用 curated body 重生成(否则引用已丢结论)
                try:
                    insight_obj = generate_insight(curated_body, client=_run_client(client, config), model=model)
                    save_insight(conn, run_id, insight_obj)
                except Exception as e:  # noqa: BLE001 — 重生成尽力而为,失败保原 insight + 降级,绝不崩图
                    logger.exception("qc insight regenerate failed for run %s", run_id)
                    append_trace(conn, run_id, "qc",
                                 output_summary=f"insight regen degraded: {type(e).__name__}")
                    local_degraded = True
            curated_report = stitch_report(insight_obj, curated_body)
            save_report(conn, run_id, curated_report)

        # 确定性门跑在**策展后**的分析上:traceability(comparison_only,策展后应已干净)+
        # ontology + coverage(只查请求维度,且传 evidence 区分两类缺口)。**零证据**维度 →
        # low_coverage → retry_collect → broaden 补搜环(诚实自纠 money-shot,broaden 能补且会
        # 收敛);**采到了证据但 cell 被策展丢掉**的维度显「—」不重采(broaden 补不了"证据撑不住
        # 结论",非确定策展反复重开缺口=不收敛的重试空转,真 run 暴露)。收敛成 pass 或诚实
        # insufficient,绝不再因 hallucination 盖 degraded 章。
        issues = qc.check_traceability(curated, evidence, comparison_only=True)
        issues += qc.check_ontology(curated, evidence)
        issues += qc.check_coverage(curated, required=requested_dims, evidence=evidence)
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
        out = {"analysis": curated.model_dump(), "qc_result": result.model_dump(),
               "retry_count": new_rc, "degraded": degraded}
        if curated_report is not None:
            out["report"] = curated_report  # finalize 拿到策展后的报告(与 /analysis 一致)
        return out
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
        dropped: list[str] = []  # 被策展掉的 ungrounded 决策 action(可见性,非降级)
        try:
            decision_set = generate_decisions(body, decision_context,
                                              client=_run_client(client, config), model=model)
        except Exception as e:  # noqa: BLE001 — 生成失败降级,绝不崩图
            logger.exception("decide generate failed for run %s", run_id)
            append_trace(conn, run_id, "decide",
                         output_summary=f"generate degraded: {type(e).__name__}")
            decision_set = DecisionSet(decisions=[])
            decision_degraded = True
        else:
            # 策展:丢弃 ungrounded 决策(机械悬空免 LLM + 蕴含不支撑),只留站得住的。
            try:
                kept, dropped = qc.curate_decisions(
                    decision_set.decisions, evidence, client=_run_client(client, config), model=model)
                decision_set = DecisionSet(decisions=kept)
            except Exception as e:  # noqa: BLE001 — 蕴含失败:机械门 fallback(只丢悬空)+ 降级,绝不崩图
                logger.exception("decide curate failed for run %s", run_id)
                append_trace(conn, run_id, "decide",
                             output_summary=f"entailment degraded: {type(e).__name__}")
                valid = {ev.id for ev in evidence}
                kept = [d for d in decision_set.decisions
                        if d.evidence_refs and all(r.evidence_id in valid for r in d.evidence_refs)]
                dropped = [d.action for d in decision_set.decisions if d not in kept]
                decision_set = DecisionSet(decisions=kept)
                decision_degraded = True

        save_decisions(conn, run_id, decision_set)
        # 策展丢弃 ungrounded 决策是**健康的策展路径,不是降级**(丢≠degrade,与 qc_node 同模型),
        # 但仍须**可见**(ship outside-voice C1:_dropped 静默吞掉违反「降级必可见」精神)——
        # 故把丢弃数记入 trace + emit,但**不**置 decision_degraded(那会回退到一票否决的病)。
        _emit_progress(
            emit, "decide", "done",
            f"生成 {len(decision_set.decisions)} 条决策建议"
            + (f"(策展剔除 {len(dropped)} 条无据)" if dropped else "")
            + ("(蕴含降级,机械门兜底)" if decision_degraded else ""),
            metric={"current": len(decision_set.decisions),
                    "total": len(decision_set.decisions)},
        )
        append_trace(conn, run_id, "decide",
                     input_summary=f"context={'set' if decision_context else 'generic'}",
                     output_summary=f"decisions={len(decision_set.decisions)} "
                                    f"dropped={len(dropped)} degraded={decision_degraded}",
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
        if verdict == "pass" and substantive:
            status = "done"
        elif verdict == "pass":
            # ship-time 双模型评审 MAJOR(Claude+Codex 共识):verdict=pass 但策展后空手
            # (每个请求维度都有证据 → coverage 无缺口 → pass,但所有 cell 被蕴含判不支撑
            # 全丢 + 无决策)→ 绝不出"看似通过实则空白"的 done。这是 _has_substantive_output
            # 要防的病的镜像反面(89% 满盖数据不足 ↔ 0% 满盖 done),必须诚实 insufficient。
            result["verdict"] = "insufficient_evidence"
            report = _BANNER_INSUFFICIENT + report
            status = "insufficient_evidence"
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
