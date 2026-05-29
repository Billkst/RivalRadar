from __future__ import annotations

import uuid

from langgraph.graph import END, START, StateGraph

from rivalradar.graph.nodes import (
    make_analyze_node, make_collect_node, make_decide_node, make_finalize_node,
    make_qc_node, make_write_node,
)
from rivalradar.graph.router import decide_route
from rivalradar.graph.state import ResearchState
from rivalradar.storage.repository import create_run


def build_research_graph(*, conn, client, model, provider, as_of,
                         official_domains=None, max_retries: int = 2, checkpointer=None):
    """组装 RivalRadar 状态图(spec §4)。节点依赖经闭包注入;run_id 取自 config thread_id。

    拓扑:START→collect→analyze→write→qc→[decide_route]。qc 的条件边:
    collect(retry_collect)/analyze(retry_analyze)/decide(pass 或超限)→finalize→END。
    decide 是 full-C 决策节点(Epic 2),夹在终态路由与 finalize 之间:每次进入终态
    (pass 或重试耗尽)先经 decide 生成 + QC 决策一次,retry 路径(collect/analyze)绕过它。
    decide_route 返回的 "finalize" 分支映射到 decide 节点(纯逻辑路由不变,router 测试不破)。
    """
    g = StateGraph(ResearchState)
    g.add_node("collect", make_collect_node(
        conn=conn, provider=provider, official_domains=official_domains or {}))
    g.add_node("analyze", make_analyze_node(conn=conn, client=client, model=model))
    g.add_node("write", make_write_node(conn=conn, client=client, model=model, as_of=as_of))
    g.add_node("qc", make_qc_node(conn=conn, client=client, model=model))
    g.add_node("decide", make_decide_node(conn=conn, client=client, model=model, as_of=as_of))
    g.add_node("finalize", make_finalize_node(conn=conn, max_retries=max_retries))

    g.add_edge(START, "collect")
    g.add_edge("collect", "analyze")
    g.add_edge("analyze", "write")
    g.add_edge("write", "qc")
    g.add_conditional_edges(
        "qc",
        lambda s: decide_route(s["qc_result"]["verdict"], s["retry_count"], max_retries),
        {"collect": "collect", "analyze": "analyze", "finalize": "decide"},
    )
    g.add_edge("decide", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


def run_research(competitors, dimensions, *, conn, client, model, provider, as_of,
                 official_domains=None, max_retries: int = 2,
                 checkpointer=None, run_id=None, decision_context: str = ""):
    """一次完整调研:建 run → 编译图 → invoke。返回 (run_id, 终态 state dict)。
    decision_context 持久化到 runs + 注入初始 state,decide 节点据此 grounding(Epic 2)。"""
    run_id = run_id or "run_" + uuid.uuid4().hex[:12]
    create_run(conn, run_id, competitors, dimensions, decision_context=decision_context)
    graph = build_research_graph(
        conn=conn, client=client, model=model, provider=provider, as_of=as_of,
        official_domains=official_domains, max_retries=max_retries, checkpointer=checkpointer)
    final = graph.invoke(
        {"competitors": competitors, "dimensions": dimensions, "evidence": [],
         "retry_count": 0, "decision_context": decision_context},
        config={"configurable": {"thread_id": run_id}},
    )
    return run_id, final
