"""Eval 套件(Epic 2.5)—— 输出质量自动评测。

两层:
1. **机械门(本模块,跑进 pytest)**:确定性、零 LLM、毫秒级,守 CI:
   - decision_traceability_violations:每条决策必须挂非空 evidence_refs(+ id 存在)。
   - platitude_violations:套话黑名单(复用 writer.PLATITUDE_TERMS 单一真源)。
   - report_structural_violations:报告结构回归(rubric 24/30 的机械代理:3 段执行
     洞察 header + 来源段 + insight 段无套话)。committed run-002(24/30 baseline)
     报告必须通过本门 —— 结构退化是 rubric 退化的早期信号。

2. **LLM-judge(spikes/spike_evals_judge.py,真打,ship 前手动跑,不进 pytest)**:
   - (a) rubric 评分 vs references/ 4 baselines,gate ≥24/30。
   - (d) 决策质量 LLM-judge(action 是否 actionable / why 是否站得住 / 是否套话)。

机械门是 necessary but insufficient(Codex #10):它保"可溯源 + 无套话 + 结构完整",
但"决策是否真有洞察"只有 LLM-judge(真打)能评。
"""
from __future__ import annotations

from rivalradar.agents.writer import PLATITUDE_TERMS
from rivalradar.schema.models import DecisionSet, ReportInsight

_INSIGHT_HEADERS = (
    "## 执行洞察", "### 市场格局", "### 战略路径分歧", "### 给企业产品团队的 takeaway",
)


def decision_traceability_violations(
    decision_set: DecisionSet, *, valid_evidence_ids: set[str] | None = None
) -> list[str]:
    """决策可溯源机械门(Epic 2.5 b):每条决策 evidence_refs 非空;给 valid_evidence_ids
    时其 id 必须存在于证据集。返回违规描述列表(空 = 通过)。"""
    out: list[str] = []
    for i, d in enumerate(decision_set.decisions):
        if not d.evidence_refs:
            out.append(f"decision[{i}]「{d.action}」无 evidence_refs")
            continue
        if valid_evidence_ids is not None:
            for r in d.evidence_refs:
                if r.evidence_id not in valid_evidence_ids:
                    out.append(f"decision[{i}] 引用悬空 evidence_id={r.evidence_id}")
    return out


def platitude_violations(
    texts: list[str], *, terms: tuple[str, ...] = PLATITUDE_TERMS
) -> list[str]:
    """套话黑名单检测(Epic 2.5 c)。返回命中描述(空 = 通过)。"""
    out: list[str] = []
    for t in texts:
        for term in terms:
            if term in t:
                out.append(f"套话「{term}」出现于:{t[:50]}")
    return out


def decision_platitude_violations(decision_set: DecisionSet) -> list[str]:
    """扫描每条决策的 action + why 是否含套话。"""
    return platitude_violations([f"{d.action} {d.why}" for d in decision_set.decisions])


def insight_platitude_violations(insight: ReportInsight) -> list[str]:
    return platitude_violations(
        [insight.market_context, insight.differentiation_thesis, insight.actionable_takeaway]
    )


def _insight_section(report_md: str) -> str:
    """截出报告的「执行洞察」段(到下一个 level-2 header 前)。套话只在 LLM synthesis 段
    算违规;确定性正文里的引语原文可能含这些词,不该误伤。"""
    start = report_md.find("## 执行洞察")
    if start == -1:
        return ""
    rest = report_md[start + len("## 执行洞察"):]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]


def report_structural_violations(report_md: str) -> list[str]:
    """报告结构回归(Epic 2.5 a 的机械代理):3 段执行洞察 header + 来源段 + insight 段无套话。
    committed run-002(24/30)baseline 必须通过 —— 结构退化即 rubric 退化早期信号。"""
    out: list[str] = []
    for h in _INSIGHT_HEADERS:
        if h not in report_md:
            out.append(f"缺执行洞察 header:{h}")
    if "## 来源" not in report_md:
        out.append("缺来源段(引用完整性锚点)")
    out += platitude_violations([_insight_section(report_md)])
    return out
