/**
 * 技能 catalog(UI 元数据,留前端 — C-D4)。DEFAULT_SKILLS = 各 agent 默认装,
 * MARKET = 可加装。后端 agent_skills 表持有状态(version/enabled),catalog 提供文案。
 * 只保留 id/name/do/core(spec §6.3:不展示 why/boundary)。
 */
import type { AgentId } from '../types/agents'

export interface SkillDef { id: string; name: string; do: string; core?: boolean }
export interface SkillState { version: string; enabled: boolean }

export const DEFAULT_SKILLS: Record<AgentId, SkillDef[]> = {
  collector: [
    { id: 'evidence-retrieving', name: '证据检索', do: '按「竞品×6维×中英双语」模板生成查询,Tavily→Exa 顺序回退联网搜索,并行抓取后按 id 去重、过滤空内容,产出原始证据集。' },
    { id: 'evidence-grooming', name: '证据整备', do: '对原始证据做正文清洗(剥图床 / 链接壳、压空白)+ 按来源优先级排序(官方 > 已知评价平台 > 杂源)。' },
    { id: 'gap-refetching', name: '缺口补采', do: 'retry 时只针对 QC 标出的 missing_evidence / low_coverage 缺口,broaden 换词(评测 / 对比 / 替代方案)精准补采,不全量重跑。' },
  ],
  analyst: [
    { id: 'profile-extracting', name: '画像抽取', do: '从证据结构化抽取四类 profile(功能树 / 定价模型 / 用户画像 / SWOT),每条挂 evidence_refs。' },
    { id: 'comparison-matrixing', name: '对比矩阵构建', do: '只在请求维度上逐维横向对比(每维小调用),cell 带 value_type + value + evidence_refs,无证据维不产行(显「-」),绝不张冠李戴。' },
    { id: 'grounding-discipline', name: '溯源粒度纪律', do: '强制「只依据给定证据、每条挂 ref、id 只能取自给定证据、禁止过度拆解」的横切约束。' },
    { id: 'extraction-degrading', name: '抽取降级兜底', do: '单项抽取失败时返空占位 + 记 degraded_sink,其余照常,绝不杀整 run。' },
  ],
  writer: [
    { id: 'grounded-report-synthesis', name: '有据报告综合', core: true, do: '封装 RivalRadar 真打验证(18.5→24/30)整套撰写方法论:总-分-总骨架 + Hybrid 分工(事实/引用走确定性 Python 模板、判断/综合走 LLM 标「AI 综合」)+ 引用完整性即结构保证(0 broken refs)+ ReportInsight 三段 Schema 强制(市场锚定/战略推论/时间分层)+ 反套话黑名单。' },
    { id: 'body-rendering', name: '确定性正文渲染', do: '纯 Python 模板把分析结果机械渲染成 Markdown(逐竞品 Profile + 对比表 + 来源清单 evidence_id→[标题](URL)(as of date)),缺 cell 标「-」,不在证据集的 id 标 missing。' },
    { id: 'insight-synthesizing', name: '执行洞察生成', do: '基于正文调 LLM 产 ReportInsight 三段(market_context 禁编市场规模数字 / differentiation_thesis 因为 X 所以 Y + 母公司战略映射 / actionable_takeaway 短中长期命令式),严禁引入正文外数字/新事实/新竞品,禁套话。' },
  ],
  qc: [
    { id: 'mechanical-gating', name: '机械三闸', do: '免 LLM 始终跑的确定性硬闸(check_traceability 结论必挂存在的引用 + check_ontology 维度落 6 维本体 + check_coverage 每竞品每维应有 cell)。' },
    { id: 'entailment-judging', name: '蕴含判定', do: '逐结论一次 LLM 调用判「被引证据是否真支撑结论」,不支撑 = 幻觉;并发 ≤8,可 scope 到请求维度/只判矩阵 cell;决策级对称提供。' },
    { id: 'evidence-curating', name: '证据策展', do: '策展人模型(非法官):把站不住的 cell(机械悬空 + 蕴含不支撑)直接丢弃返回 (curated, dropped) 而非否决整 run;丢后空 row 消失→coverage 发现缺口→触发 broaden 补搜。' },
    { id: 'output-sanitizing', name: '输出脱敏', do: '把 QCResult 投影成可公开 serve 形状(detail 换罐装中文文案、越界 dimension 替占位),绝不外泄 LLM 文本/异常文本。' },
  ],
}

export const MARKET: Record<AgentId, SkillDef[]> = {
  collector: [
    { id: 'domain-allowlisting', name: '来源域名白名单', do: '按行业维护可信域名清单,检索时优先选取白名单内来源,杂源降权。' },
    { id: 'bilingual-templating', name: '中英查询模板扩展', do: '为指定维度补充英文检索模板词,提升海外来源召回。' },
  ],
  analyst: [
    { id: 'dimension-laddering', name: '维度粒度分层', do: '按战略/范围/结构对维度做显式分层,避免「功能多」与「定位准」混为一谈。' },
    { id: 'matrix-conflict-flagging', name: '矩阵口径冲突标注', do: '同一格多源口径不一致时标注分歧,留待蕴含判定裁决。' },
  ],
  writer: [
    { id: 'audience-toning', name: '受众语气适配', do: '按 PM/高管/采购切换洞察段落的详略与措辞。' },
    { id: 'takeaway-horizoning', name: '行动项时间分层', do: '把 actionable_takeaway 拆成短/中/长期命令式条目。' },
  ],
  qc: [
    { id: 'source-bias-tagging', name: '来源偏见标注', do: '标注厂商自述/软文等高偏见来源,提示结论强度折扣(基于来源类型,不做内容情感打分)。' },
    { id: 'staleness-flagging', name: '证据时效红线', do: '对超过红线天数的证据加「陈旧」标(基于 as_of 日期,确定性比较,非实时监控)。' },
  ],
}
