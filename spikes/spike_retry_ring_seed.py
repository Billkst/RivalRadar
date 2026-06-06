"""retry-ring 备用种子:真 Tavily + 真 Doubao,确定性触发一次 broaden 自纠环 → 收敛 done。

为什么需要 gate(受控触发):重试空转修复后,飞书/钉钉/企业微信 × 常见维度首轮即收敛
(无环)。要演示招牌时刻「质检发现某维度欠采 → 打回采集 → broaden 补到 → 收敛」,需要一个
**首轮真·零证据**的维度。本 spike 用一层薄 gate 把 deployment 维度的真证据**延后到 broaden
轮**释放:
  - 首轮 deployment narrow query(无 CRAG 后缀)→ 返 [](真·零证据,模拟稀疏维度);
  - broaden 轮 deployment query(带 CRAG 后缀 review comparison alternative / 评测 对比 替代
    方案)→ 放行到真 Tavily → 补到证据。
证据全真(Tavily)、推理全真(Doubao)、graph 机制全真(原样跑),只是确定性地制造那个缺口。
其余 3 维(pricing/core_workflows/integrations)与现有 done 种子完全一致,首轮即干净 pass。

写进 RIVALRADAR_DB(默认 rivalradar.db)供 cockpit replay 兜底。幂等:重跑先清旧种子。
运行(必先 unset 代理 + NO_PROXY,见 CLAUDE.md WSL2 Clash 注记):
  .venv/bin/python spikes/spike_retry_ring_seed.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.graph.build import run_research
from rivalradar.search.fallback import FallbackSearch
from rivalradar.search.tavily_provider import TavilyProvider
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db

# 首轮 deployment 模板的判别标记(queries.py _TEMPLATES["deployment"] 的稳定子串)。
_DEPLOY_NARROW = ("deployment self-hosted SSO enterprise", "部署 私有化 企业版 SSO")
# broaden 轮 CRAG 后缀(queries.py _BROADEN_SUFFIX);带它 = 第二轮补搜,放行。
_BROADEN = ("review comparison alternative", "评测 对比 替代方案")

RUN_ID = "run_selfheal01"
COMPETITORS = ["飞书", "钉钉", "企业微信"]
DIMENSIONS = ["pricing", "core_workflows", "integrations", "deployment"]
DECISION_CONTEXT = (
    "我们是一家约 500 人的企业,正在为公司选型协同办公平台,"
    "重点关注私有化部署能力、集成生态与综合成本。"
)
AS_OF = "2026-05-31"


class _RoundOneGatedProvider:
    """把 deployment 维度首轮(narrow)query 的真证据延后到 broaden 轮释放。

    判别无状态、纯文本匹配(provider.search 只见查询串,看不到 (竞品,维度) 结构),
    故线程并发与跨轮调用都安全:narrow 标记在场 且 broaden 后缀不在场 = 首轮 deployment
    查询 → 扣下(返 []);broaden 轮 query 含后缀 → 放行真 Tavily。其余维度全程透传。
    """
    name = "gated-tavily"

    def __init__(self, inner: FallbackSearch):
        self._inner = inner
        self.withheld = 0
        self.passed = 0

    def search(self, query: str, *, max_results: int = 5):
        narrow = any(m in query for m in _DEPLOY_NARROW)
        broadened = any(m in query for m in _BROADEN)
        if narrow and not broadened:
            self.withheld += 1
            return []  # 首轮 deployment 真·零证据(模拟稀疏维度,确定性触发自纠环)
        self.passed += 1
        return self._inner.search(query, max_results=max_results)


def _purge(conn, run_id: str) -> None:
    """幂等:删掉所有带 run_id 列的表里该 run 的旧行(支持重跑)。"""
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t})")]
        if "run_id" in cols:
            conn.execute(f"DELETE FROM {t} WHERE run_id=?", (run_id,))
    conn.commit()


def main() -> None:
    db = config.db_path()
    conn = connect(db)
    init_db(conn)
    _purge(conn, RUN_ID)

    inner = FallbackSearch([TavilyProvider(api_key=config.tavily_api_key())])
    provider = _RoundOneGatedProvider(inner)

    print(f"[seed] db={db} run_id={RUN_ID} comps={COMPETITORS} dims={DIMENSIONS}")
    run_id, final = run_research(
        COMPETITORS, DIMENSIONS,
        conn=conn, client=config.get_doubao_client(), model=config.doubao_model(),
        provider=provider, as_of=AS_OF, max_retries=2,
        run_id=RUN_ID, decision_context=DECISION_CONTEXT,
    )

    status = final.get("status")
    verdict = final["qc_result"]["verdict"]
    trace = repo.list_trace(conn, run_id)
    n_ev = len(repo.list_evidence(conn, run_id))

    print(f"\n=== gate: withheld={provider.withheld} passed={provider.passed} ===")
    print("=== TRACE ===")
    rings = 0
    for t in trace:
        out = t["output_summary"] or ""
        print(f"  {t['node']:9} | {out}")
        if t["node"] == "qc" and ("retry_collect" in out or "retry_analyze" in out):
            rings += 1
    print(f"\n=== run_id={run_id} status={status} verdict={verdict} evidence={n_ev} rings={rings} ===")

    # 验收:status=done + 至少一次 retry 环。单环最干净(只 deployment 一个缺口),
    # 但即便偶发第二环,_has_substantive_output 保证仍收敛 done(矩阵非空)。
    assert status == "done", f"期望 done,实际 {status}(种子不可用作干净 money-shot)"
    assert rings >= 1, "没有重试环 — gate 未触发 retry_collect(deployment 未零证据?)"
    if rings == 1:
        print("SEED OK: 干净单环自纠 → done(招牌 money-shot)")
    else:
        print(f"SEED OK(带 {rings} 环): 仍收敛 done,但非最干净单环;如需单环可微调维度集")


if __name__ == "__main__":
    main()
