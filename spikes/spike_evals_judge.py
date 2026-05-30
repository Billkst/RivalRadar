"""Spike:Eval LLM-judge(Epic 2.5 a + d)—— ship 前手动跑,真打 Doubao,不进 pytest。

两部分:
- (a) rubric 评分:LLM-judge 给 committed run-002(人工评 24/30)报告打 10 条 ×0-3 分,
      断言 total ≥ 24。这是 ship gate —— 模型自评应与人工 baseline 一致(回归 + 校准)。
- (d) 决策质量:把该报告当 body 跑真 generate_decisions,先过机械门(可溯源 + 无套话),
      再 LLM-judge 每条决策(action 是否真 actionable / why 是否站得住 / 是否套话)。

跑法:`python spikes/spike_evals_judge.py`(需 .env 含 ARK_API_KEY + DOUBAO_MODEL;
unset 代理 + NO_PROXY 防 Clash 卡)。失败/低分会打印明细 + 非零退出,供 ship 前 gate。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field

from rivalradar import config
from rivalradar.agents.writer import generate_decisions
from rivalradar.evals import decision_platitude_violations, decision_traceability_violations
from rivalradar.llm.structured import structured_call

_RUBRIC = """RivalRadar rubric v1(10 条 × 0-3 = 30 满,见 references/README.md):
A 结构与覆盖:#1 市场锚定 #2 对比矩阵 #3 维度粒度 #4 信息溯源完整 #5 定价模型
B 质量与洞察:#6 数据密度 #7 战略推论 #8 Schema 深度 #9 时间分层 #10 反幻觉信号
每条 0=缺失 1=薄弱 2=合格 3=优秀。"""

_BASELINE = (pathlib.Path(__file__).resolve().parent.parent
             / "references/rivalradar-output/run-002-writer-v2/report.md")
_GATE = 24  # ship 阈值(人工 baseline = 24/30)


class RubricScore(BaseModel):
    market_anchor: int = Field(ge=0, le=3)
    comparison_matrix: int = Field(ge=0, le=3)
    dimension_granularity: int = Field(ge=0, le=3)
    source_traceability: int = Field(ge=0, le=3)
    pricing_model: int = Field(ge=0, le=3)
    data_density: int = Field(ge=0, le=3)
    strategic_inference: int = Field(ge=0, le=3)
    schema_depth: int = Field(ge=0, le=3)
    time_layering: int = Field(ge=0, le=3)
    anti_hallucination: int = Field(ge=0, le=3)
    rationale: str = ""

    def total(self) -> int:
        return sum(getattr(self, f) for f in self.model_fields if f != "rationale")


class DecisionJudgment(BaseModel):
    actionable: bool        # action 是否真可执行(非"评估/考虑"类 hedge)
    why_holds: bool         # why 是否站得住(基于正文,非空泛)
    is_platitude: bool      # 是否套话
    note: str = ""


class DecisionPanelJudgment(BaseModel):
    judgments: list[DecisionJudgment] = Field(default_factory=list)


def judge_rubric(report_md: str, *, client, model) -> RubricScore:
    msgs = [{"role": "user", "content":
             f"{_RUBRIC}\n\n请对下面这份竞品分析报告按 10 条逐条打分,通过 emit_result 返回。\n\n"
             f"报告:\n{report_md}"}]
    return structured_call(RubricScore, msgs, client=client, model=model)


def judge_decisions(report_md: str, decisions, *, client, model) -> DecisionPanelJudgment:
    listing = "\n".join(f"{i}. [{d.stance}] {d.action} —— 理由:{d.why}"
                        for i, d in enumerate(decisions))
    msgs = [{"role": "user", "content":
             "逐条评判下列决策建议(基于其后报告正文),通过 emit_result 返回 judgments 数组,"
             "顺序与决策一致。actionable=action 是否真可执行;why_holds=理由是否基于正文站得住;"
             "is_platitude=是否空话套话。\n\n"
             f"决策:\n{listing}\n\n报告正文:\n{report_md[:6000]}"}]
    return structured_call(DecisionPanelJudgment, msgs, client=client, model=model)


def main() -> int:
    client = config.get_doubao_client()
    model = config.doubao_model()
    report = _BASELINE.read_text(encoding="utf-8")

    print("=== (a) rubric LLM-judge vs 24/30 baseline ===")
    score = judge_rubric(report, client=client, model=model)
    total = score.total()
    print(f"total = {total}/30 (gate ≥{_GATE})  rationale: {score.rationale[:160]}")
    rubric_ok = total >= _GATE

    print("\n=== (d) 决策质量(真 generate_decisions + 机械门 + LLM-judge)===")
    ds = generate_decisions(report, "选型PM:是否采购飞书作为团队协作平台",
                            client=client, model=model)
    trace_v = decision_traceability_violations(ds)
    plat_v = decision_platitude_violations(ds)
    print(f"生成 {len(ds.decisions)} 条决策;可溯源违规 {len(trace_v)};套话违规 {len(plat_v)}")
    for v in trace_v + plat_v:
        print("  ✗", v)
    panel = judge_decisions(report, ds.decisions, client=client, model=model)
    bad = [j for j in panel.judgments if not j.actionable or not j.why_holds or j.is_platitude]
    for d, j in zip(ds.decisions, panel.judgments):
        flag = "✓" if (j.actionable and j.why_holds and not j.is_platitude) else "✗"
        print(f"  {flag} [{d.stance}] {d.action} | {j.note[:80]}")

    decisions_ok = not trace_v and not plat_v and not bad
    print(f"\nGATE: rubric {'PASS' if rubric_ok else 'FAIL'} / "
          f"decisions {'PASS' if decisions_ok else 'FAIL'}")
    return 0 if (rubric_ok and decisions_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
