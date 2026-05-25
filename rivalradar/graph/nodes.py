from __future__ import annotations

import time

from rivalradar.agents.analyst import analyze
from rivalradar.agents.collector import collect_evidence
from rivalradar.agents.writer import write_report
from rivalradar.graph.router import extract_collect_targets
from rivalradar.agents import qc
from rivalradar.schema.models import CompetitorAnalysis, Evidence, QCResult
from rivalradar.storage.repository import (
    append_trace, insert_evidence, save_analysis, save_report,
)


def make_collect_node(*, conn, provider, official_domains, max_results: int = 5):
    """采集节点:首遍全量采;retry 时按 qc issues 只补缺口 + broaden 广搜。
    只 insert 真新增(对 state 已有 id 去重),证据 dict 由 reducer 累加去重。"""
    def collect_node(state, config):
        run_id = config["configurable"]["thread_id"]
        t0 = time.monotonic()
        existing = {e["id"] for e in state.get("evidence", [])}
        qc_result = state.get("qc_result")
        if qc_result is None:
            evs = collect_evidence(state["competitors"], state["dimensions"],
                                   provider=provider, official_domains=official_domains,
                                   max_results=max_results)
            tgt_desc = "all"
        else:
            targets = extract_collect_targets(qc_result["issues"], state["competitors"])
            evs = []
            for comp, dim in targets:
                evs += collect_evidence([comp], [dim], provider=provider,
                                        official_domains=official_domains,
                                        max_results=max_results, broaden=True)
            tgt_desc = f"{len(targets)} gaps"
        fresh = [e for e in evs if e.id not in existing]
        for e in fresh:
            insert_evidence(conn, run_id, e)
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
        t0 = time.monotonic()
        evidence = [Evidence(**d) for d in state["evidence"]]
        analysis = analyze(evidence, state["competitors"], client=client, model=model)
        save_analysis(conn, run_id, analysis)
        append_trace(conn, run_id, "analyze",
                     input_summary=f"{len(evidence)} evidence",
                     output_summary=f"{len(analysis.competitors)} profiles, "
                                    f"{len(analysis.comparison)} rows",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"analysis": analysis.model_dump()}
    return analyze_node


def make_write_node(*, conn, client, model, as_of):
    """撰写节点:CompetitorAnalysis + 证据 → 混合报告 → 落库。"""
    def write_node(state, config):
        run_id = config["configurable"]["thread_id"]
        t0 = time.monotonic()
        analysis = CompetitorAnalysis(**state["analysis"])
        evidence = [Evidence(**d) for d in state["evidence"]]
        report = write_report(analysis, evidence, as_of=as_of, client=client, model=model)
        save_report(conn, run_id, report)
        append_trace(conn, run_id, "write",
                     input_summary=f"analysis of {len(state['analysis'].get('competitors', []))} competitors",
                     output_summary=f"report {len(report)} chars",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"report": report}
    return write_node


def make_qc_node(*, conn, client, model):
    """质检节点:确定性三闸(始终跑)+ LLM 蕴含(失败则降级,必办项①)。

    不调 qc.check(它会上抛),而是在本层组合子函数:traceability/ontology/coverage
    决定 verdict 主体;check_entailment 包在 try/except StructuredCallError,失败则
    degraded=True、记 trace,verdict 仅由确定性闸决定。
    retry_count 仅在「带着上一轮 qc_result 进来」时 +1(每轮唯一计数点,避免双重计数)。
    """
    def qc_node(state, config):
        run_id = config["configurable"]["thread_id"]
        t0 = time.monotonic()
        analysis = CompetitorAnalysis(**state["analysis"])
        evidence = [Evidence(**d) for d in state["evidence"]]
        issues = qc.check_traceability(analysis, evidence)
        issues += qc.check_ontology(analysis, evidence)
        issues += qc.check_coverage(analysis)
        degraded = False
        try:
            issues += qc.check_entailment(analysis, evidence, client=client, model=model)
        except Exception as e:  # noqa: BLE001 — 蕴含是尽力而为辅助闸,任何失败(解析/网络/限流)都降级,绝不崩整图(必办项①/spec §5)
            degraded = True
            append_trace(conn, run_id, "qc",
                         output_summary=f"entailment degraded: {e}")
        verdict = qc.decide_verdict(issues)
        result = QCResult(verdict=verdict, issues=issues)
        prior = state.get("qc_result")
        new_rc = state["retry_count"] + (1 if prior is not None else 0)
        append_trace(conn, run_id, "qc",
                     input_summary=f"{len(evidence)} evidence",
                     output_summary=f"verdict={verdict} issues={len(issues)} "
                                    f"degraded={degraded} retry={new_rc}",
                     latency_ms=int((time.monotonic() - t0) * 1000))
        return {"qc_result": result.model_dump(), "retry_count": new_rc, "degraded": degraded}
    return qc_node
