"""Lane D 整图真打:FakeProvider 喂源 + 真实 Doubao 驱动 analyze/write/qc。需 ARK_API_KEY。

验证整图在真模型上端到端跑通:采集(累加)→分析→撰写→质检→路由→终态,
并落 evidence/analysis/report/trace。真实 LLM 不确定 → 断言放宽到「跑通 + 合法 verdict」。
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.graph.build import run_research
from rivalradar.schema.models import CONTROLLED_DIMENSIONS
from rivalradar.search.base import SearchResult
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db


class _SeededProvider:
    """对每个查询返回一条带正文的源(url 随查询变),让真实 analyze 有据可依。"""
    name = "seeded"

    def search(self, query, *, max_results=5):
        url = "https://example.com/" + hashlib.sha1(query.encode()).hexdigest()[:10]
        body = (f"This is reference content addressing: {query}. "
                "It describes pricing tiers, core features, integrations and user feedback.")
        return [SearchResult(url=url, title="ref", content=body[:120], raw_content=body)]


def main() -> None:
    client = config.get_doubao_client()
    model = config.doubao_model()
    conn = connect(":memory:")
    init_db(conn)

    run_id, final = run_research(
        ["Notion"], list(CONTROLLED_DIMENSIONS),
        conn=conn, client=client, model=model, provider=_SeededProvider(),
        as_of="2026-05-26", max_retries=2)

    report = final.get("report", "")
    verdict = final["qc_result"]["verdict"]
    n_ev = len(repo.list_evidence(conn, run_id))
    trace = repo.list_trace(conn, run_id)
    nodes_hit = [t["node"] for t in trace]

    print("=== REPORT (head) ===")
    print(report[:400])
    print(f"=== run_id={run_id} verdict={verdict} evidence={n_ev} status={final.get('status')} ===")
    print(f"=== trace nodes: {nodes_hit} ===")

    assert report.startswith("# 竞品分析报告") or report.lstrip().startswith(">")
    assert verdict in {"pass", "insufficient_evidence", "retry_collect", "retry_analyze"}
    assert n_ev > 0
    assert "collect" in nodes_hit and "analyze" in nodes_hit and "qc" in nodes_hit
    print("SPIKE F OK: real Doubao drove the full graph end-to-end")


if __name__ == "__main__":
    main()
