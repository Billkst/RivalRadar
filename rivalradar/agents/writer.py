from __future__ import annotations

from pydantic import BaseModel

from rivalradar.llm.structured import structured_call
from rivalradar.schema.feature_tree import assemble_tree
from rivalradar.schema.models import (
    CompetitorAnalysis, CompetitorProfile, ComparisonRow, DecisionSet,
    EvidenceRef, Evidence, FeatureItem,
)

# 套话黑名单(反"持续关注/深入研究"型空话)— writer v2 negative-example 纪律的
# 单一真源,generate_decisions prompt 约束 + Epic 2.5 platitude 机械门复用。
PLATITUDE_TERMS: tuple[str, ...] = (
    "持续关注", "深入研究", "保持观察", "密切关注", "进一步了解",
    "拭目以待", "静观其变", "有待观察", "值得关注",
)


def _fmt_refs(refs: list[EvidenceRef]) -> str:
    """把 evidence_refs 渲染成内联引用标记,如 ' [e1, e2]';无引用则空串。"""
    ids = [r.evidence_id for r in refs]
    return f" [{', '.join(ids)}]" if ids else ""


def _render_features(features: list[FeatureItem]) -> str:
    """按 assemble_tree 的层级缩进渲染功能项,每项挂内联引用。"""
    lines: list[str] = []

    def walk(nodes: list[dict], depth: int) -> None:
        for n in nodes:
            it = n["item"]
            indent = "  " * depth
            desc = f":{it.description}" if it.description else ""
            lines.append(f"{indent}- {it.name}{desc}{_fmt_refs(it.evidence_refs)}")
            walk(n["children"], depth + 1)

    walk(assemble_tree(features), 0)
    return "\n".join(lines)


def render_competitor(profile: CompetitorProfile) -> str:
    """确定性渲染单个竞品 Profile 为 Markdown,每条结论挂内联引用。"""
    parts = [f"## {profile.name}", "### 功能"]
    parts.append(_render_features(profile.features) if profile.features else "_(无)_")

    parts.append(f"### 定价({profile.pricing.model_type}){_fmt_refs(profile.pricing.evidence_refs)}")
    if profile.pricing.tiers:
        for t in profile.pricing.tiers:
            tail = f" — {t.limits}" if t.limits else ""
            parts.append(f"- {t.name}:{t.price} / {t.billing_cycle}{tail}")
    else:
        parts.append("_(无)_")

    parts.append("### 用户画像")
    if profile.personas:
        for p in profile.personas:
            needs = "、".join(p.needs) or "—"
            pains = "、".join(p.pain_points) or "—"
            praise = "、".join(p.praise) or "—"
            parts.append(f"- {p.segment}:需求 {needs};痛点 {pains};好评 {praise}{_fmt_refs(p.evidence_refs)}")
    else:
        parts.append("_(无)_")

    parts.append("### SWOT")
    quads = (("优势", profile.swot.strengths), ("劣势", profile.swot.weaknesses),
             ("机会", profile.swot.opportunities), ("威胁", profile.swot.threats))
    swot_lines = [f"- {label}:{pt.text}{_fmt_refs(pt.evidence_refs)}"
                  for label, points in quads for pt in points]
    parts.append("\n".join(swot_lines) if swot_lines else "_(无)_")

    return "\n".join(parts)


def render_comparison(rows: list[ComparisonRow], competitors: list[str]) -> str:
    """跨竞品对比表:行=维度,列=竞品,cell 标 value + 内联引用;缺 cell 标 '—'。"""
    if not rows:
        return "## 跨竞品对比\n\n_(无对比数据)_"
    header = "| 维度 | " + " | ".join(competitors) + " |"
    sep = "|" + "---|" * (len(competitors) + 1)
    lines = ["## 跨竞品对比", "", header, sep]
    for row in rows:
        by_comp = {c.competitor: c for c in row.cells}
        cells = []
        for name in competitors:
            cell = by_comp.get(name)
            cells.append(f"{cell.value}{_fmt_refs(cell.evidence_refs)}" if cell else "—")
        lines.append(f"| {row.dimension} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _cited_ids(analysis: CompetitorAnalysis) -> list[str]:
    """按出现顺序收集 analysis 中所有被引的 evidence_id(去重)。"""
    ids: list[str] = []
    seen: set[str] = set()

    def add(refs: list[EvidenceRef]) -> None:
        for r in refs:
            if r.evidence_id not in seen:
                seen.add(r.evidence_id)
                ids.append(r.evidence_id)

    for prof in analysis.competitors:
        for f in prof.features:
            add(f.evidence_refs)
        add(prof.pricing.evidence_refs)
        for p in prof.personas:
            add(p.evidence_refs)
        for points in (prof.swot.strengths, prof.swot.weaknesses,
                       prof.swot.opportunities, prof.swot.threats):
            for pt in points:
                add(pt.evidence_refs)
    for row in analysis.comparison:
        for cell in row.cells:
            add(cell.evidence_refs)
    return ids


def render_sources(analysis: CompetitorAnalysis, evidence: list[Evidence]) -> str:
    """被引证据清单:evidence_id → [标题](URL)(as of fetched_at);不在证据集的标 missing。"""
    idx = {e.id: e for e in evidence}
    cited = _cited_ids(analysis)
    lines = ["## 来源"]
    if not cited:
        lines.append("_(无引用)_")
        return "\n".join(lines)
    for eid in cited:
        e = idx.get(eid)
        if e is None:
            lines.append(f"- [{eid}] (missing:该 evidence_id 不在证据集)")
        else:
            lines.append(f"- [{eid}] [{e.source_title}]({e.source_url})(as of {e.fetched_at})")
    return "\n".join(lines)


def render_body(analysis: CompetitorAnalysis, evidence: list[Evidence], *, as_of: str) -> str:
    """确定性正文:as-of 时效 + 逐竞品 Profile + 对比表 + 来源清单。"""
    parts = [f"> 数据时效:as of {as_of}"]
    parts += [render_competitor(p) for p in analysis.competitors]
    parts.append(render_comparison(analysis.comparison, [p.name for p in analysis.competitors]))
    parts.append(render_sources(analysis, evidence))
    return "\n\n".join(parts)


class ReportInsight(BaseModel):
    """3 段执行洞察(rubric v1 #1/#7/#9 补强 — 市场锚定 + 战略推论 + 时间分层 actionable)。

    body 仍 deterministic + 引用完整,insight 是 LLM 综合 strategic synthesis
    显式标"AI 基于正文综合",评委可清楚分辨"哪些是 fact extract 哪些是判断"。
    """
    market_context: str        # 1-2 句赛道格局 + 玩家定位(rubric #1 市场锚定)
    differentiation_thesis: str  # 2-3 句战略路径分歧 reasoning chain(rubric #7 战略推论)
    actionable_takeaway: str    # 3 句 短/中/长期 PT actionable(rubric #9 时间分层)


def generate_insight(body: str, *, client, model) -> ReportInsight:
    """LLM 综合 3 段执行洞察(替代旧 generate_summary 单段事实概括)。

    Why:rubric v1 评 18.5/30,#1 市场锚定 0/3 + #7 战略推论 1.5/3 + #9 时间分层
    0/3 共失 7.5 分,全集中在"summary 太事实化,缺战略综合"。本函数把单段事实摘要
    改成 3 段 structured insight,显式 prompt-encode "基于正文事实做综合推论"。

    安全约束:
    - 严禁引入正文没有的数字 / 新事实 / 新竞品(防幻觉,rubric #10 不退)
    - 所有推论必须可以从正文 SWOT + 对比表 + 用户画像 综合而来
    - 短/中/长期必须 actionable,不允许"持续关注" / "深入研究"类套话
    """
    prompt = f"""你是企业产品分析师,为中国企业产品团队决策提供深度竞品分析。下方是一份已经
deterministically 渲染好的竞品分析正文(含数据 + 引用 + SWOT + 跨竞品对比)。

请基于正文事实生成 3 段执行洞察,通过 emit_result 工具返回。**严禁引入正文没有的
数字、新事实、新竞品**。所有推论必须可以从正文 SWOT + 对比表 + 用户画像 综合而来。

字段说明:
1. market_context (1-2 句):赛道格局 + 玩家定位
   - 不要凭空编市场规模数字;若正文 / 用户画像里出现了「千万家企业」「500 强」等
     量级线索,可以引用作锚点
   - 要点出「这是什么赛道 + 主要玩家在格局中如何定位」

2. differentiation_thesis (2-3 句):基于 SWOT + 对比表,推论竞品战略路径分歧
   - 必须用「因为 X,所以 Y」形式的推论链
   - 例(此示例不在正文内,仅作格式参考):「飞书走互联网先进团队协作路径,钉钉
     走中小企业规模 + 母公司阿里 AI to B 入口路径」
   - 不要只罗列功能差异,要点出 strategic positioning 背后的母公司战略映射

3. actionable_takeaway (3 句,每段独立短句):面向中国企业 PT 读者
   - 短期(< 3 月):产品该做什么(具体动作,不是「评估」)
   - 中期(3-12 月):该关注什么 trend(具体信号,不是「持续关注」)
   - 长期(> 12 月):格局会怎么演变(预测,基于正文 trend)
   - 每句必须 actionable,**严禁「持续关注」/「深入研究」/「保持观察」类套话**

正文:
{body}"""
    msgs = [{"role": "user", "content": prompt}]
    return structured_call(ReportInsight, msgs, client=client, model=model)


def generate_decisions(
    body: str, decision_context: str | None, *, client, model
) -> DecisionSet:
    """LLM 基于正文 + 用户决策处境产出结构化决策建议(full-C / Epic 2.2)。

    设计不变量:
    - **不碰 generate_insight**(24/30 baseline 守护)。决策是 additive 结构化输出,
      与 3 段执行洞察各走各的 LLM 调用。
    - 每条决策必须挂 evidence_refs,evidence_id 取自正文「来源」清单(QC 校验溯源)。
    - 反套话:action / why 严禁 PLATITUDE_TERMS 型空话(命令式动作 > hedge 语言)。
    - **通用浏览 / 无处境(D8):** 收敛为中性「市场观察」语气 —— action 写成观察性
      判断而非命令式动作,并在 why 里点明"这是未设处境的通用判断"。
    - `持续观察` 必须带完整 watch{metric,threshold,trigger}(schema 强制,缺则
      structured_call 校验失败重试)。
    """
    ctx = (decision_context or "").strip()
    if ctx:
        situation = (
            f"用户的决策处境:{ctx}\n"
            "请针对该处境给出**命令式、可执行**的行动建议(action 是具体动作,"
            "不是「评估」「考虑」类 hedge)。"
        )
    else:
        situation = (
            "用户未设定具体决策处境(通用浏览)。请把全部建议收敛为中性的"
            "「市场观察」语气:stance 多用 持续观察 / 需要警惕;action 写成观察性"
            "判断而非命令式动作;每条 why 里点明「你未设定处境,以下为通用判断」。"
        )
    banned = "、".join(PLATITUDE_TERMS)
    prompt = f"""你是企业产品决策顾问。下方是一份已 deterministically 渲染好的竞品分析正文
(含逐竞品 Profile + 跨竞品对比 + SWOT + 「来源」清单,每条事实挂 [evidence_id] 引用)。

{situation}

请基于正文事实,通过 emit_result 工具产出 3-5 条决策建议(DecisionSet)。每条决策:
- stance:建议采用 / 需要警惕 / 持续观察(自解释立场)。
- action:一句话动作。命令式处境下是具体动作;通用浏览下是观察性判断。
- horizon:短期 / 中期 / 长期。
- risk_reversibility(可逆 / 不可逆)+ risk_cost(低 / 中 / 高):决策**后果**,
  与证据支持度无关。
- why:为什么这么判断(基于正文 SWOT + 对比 + 画像综合推论,严禁引入正文没有的事实)。
- evidence_refs:**每条决策至少挂 1 条**,evidence_id **必须取自正文「来源」清单里
  出现过的 id**;quote 摘自该证据。
- watch:**仅当 stance=持续观察 时必填**,给出 metric(盯什么指标)+ threshold(阈值)
  + trigger(越线做什么);其余 stance 留空。

硬约束:**严禁出现「{banned}」这类空话**;每条 action 必须 actionable 或 observable。

正文:
{body}"""
    msgs = [{"role": "user", "content": prompt}]
    return structured_call(DecisionSet, msgs, client=client, model=model)


def write_report(analysis: CompetitorAnalysis, evidence: list[Evidence], *,
                 as_of: str, client, model) -> str:
    """撰写 Agent 入口(混合):LLM 3 段执行洞察 + 确定性正文(所有引用在正文)。

    报告结构(post-rubric-v1 重构):
      # 竞品分析报告
      ## 执行洞察(AI 基于下方正文综合)     ← NEW:3 段战略综合
        ### 市场格局
        ### 战略路径分歧
        ### 给企业产品团队的 takeaway(短/中/长期)
      ## 飞书 / 钉钉 / ... (deterministic body)  ← 完整引用挂段内
      ## 跨竞品对比 (deterministic table)
      ## 来源 (61+ URLs with as_of)
    """
    body = render_body(analysis, evidence, as_of=as_of)
    insight = generate_insight(body, client=client, model=model)
    return (
        "# 竞品分析报告\n\n"
        "## 执行洞察(AI 基于下方正文综合)\n\n"
        "### 市场格局\n\n"
        f"{insight.market_context}\n\n"
        "### 战略路径分歧\n\n"
        f"{insight.differentiation_thesis}\n\n"
        "### 给企业产品团队的 takeaway(短期 / 中期 / 长期)\n\n"
        f"{insight.actionable_takeaway}\n\n"
        f"{body}"
    )
