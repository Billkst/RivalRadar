/**
 * Demo fixture — D6 demo day bullet-proof 兜底(plan v3.2 §10 D5 Epic 7.1 +
 * §11 R3 Clash demo day 风险 mitigation)。
 *
 * 目标:demo 当天 LLM 不通(Clash 卡 / API rate limit / 网络故障)仍能完整跑
 * 一遍 25s office UI 演示。**纯前端 fixture,零依赖**:
 *   - 不打 backend(GET /run/:id 用 DEMO_RUN_DETAIL 替代)
 *   - 不打 SSE(用 fakeSSEPlayer 直接 replay SAMPLE_EVENTS)
 *   - 不需 LLM key,不需 backend 进程,只要 vite dev server / 静态 build
 *
 * 入口:
 *   - RunsPage 顶部 "🎬 Demo 模式" 卡片 → /run/run_demo01
 *   - RunPage 检测 isDemoRun() → bypass fetchRun + SSE,自动 playFakeSSE Real
 *
 * 与 fakeSSEPlayer 的关系:
 *   fakeSSEPlayer 是 dev 模式的"手动按按钮 spike",demo fixture 是"用户进入
 *   demo URL 自动播放" — 复用同一份 SAMPLE_EVENTS,只是触发路径不同。
 */
import type {
  CompetitorAnalysis,
  CompetitorProfile,
  DecisionSet,
  Evidence,
  ReportInsight,
  RunDetail,
  SanitizedQCResult,
  TraceEntry,
} from '@/types/api'

/** demo 专用 run_id,RunPage / RunsPage 用它判断走 demo 路径还是真打 backend。 */
export const DEMO_RUN_ID = 'run_demo01'

/** Mock RunSummary —— 数据与 SAMPLE_EVENTS 里的竞品 / 维度 1:1 对齐让 demo
 *  叙事一致。created_at 用 mount 时刻,这样卡片时间戳是"今天此刻"。 */
export const DEMO_RUN_DETAIL: RunDetail = {
  run_id: DEMO_RUN_ID,
  competitors: ['飞书', '钉钉', '企业微信'],
  dimensions: ['pricing', 'core_workflows', 'integrations', 'target_users'],
  status: 'done',
  degraded: false,
  decision_context: '选型PM:为团队评估协作办公平台选型', // full-C(Epic 2):cockpit 回访显示处境
  created_at: new Date().toISOString(),
}

/** RunPage / RunsPage 用这个判断当前 run 是否走 demo 路径。 */
export function isDemoRun(run_id: string | undefined | null): boolean {
  return run_id === DEMO_RUN_ID
}

// ─── cockpit 决策面 demo 数据(Epic 4/5)──────────────────────────────────────
// demo day backend down / Clash 卡时,左决策面(DecisionBoard / 对比矩阵 / 证据 /
// ContradictionPanel / SelfAuditTrace)仍能渲染真实形态。数据与 SAMPLE_EVENTS 叙事
// 1:1 对齐:飞书/钉钉/企业微信 × 定价/核心工作流/集成/目标用户,12→19 证据(重试轮),
// 3 条决策(三 stance 全覆盖 + watch),决策 evidence_refs 与对比矩阵单元格共享
// evidence_id → 因果桥("点决策高亮相关行列")可在 demo 演示。

/** 相对今天的 ISO 时间(fresh 用近期,stale 用 >90 天前演示过期角标)。 */
const daysAgo = (n: number): string => new Date(Date.now() - n * 86_400_000).toISOString()

export const DEMO_EVIDENCE: Evidence[] = [
  { id: 'ev-fs-pricing-1', competitor: '飞书', dimension: 'pricing',
    content: '飞书标准版对小团队免费,企业版按人/月计费,审批、OKR、多维表格等高级能力随版本解锁。',
    source_url: 'https://www.feishu.cn/price', source_title: '飞书官网 · 价格', language: 'zh', fetched_at: daysAgo(6) },
  { id: 'ev-fs-workflow-1', competitor: '飞书', dimension: 'core_workflows',
    content: '飞书把文档、IM、会议、审批放在同一工作台,审批流可直接嵌入文档与群,跨场景一体化程度高。',
    source_url: 'https://www.feishu.cn/product', source_title: '飞书官网 · 产品能力', language: 'zh', fetched_at: daysAgo(5) },
  { id: 'ev-fs-integ-1', competitor: '飞书', dimension: 'integrations',
    content: '飞书开放平台提供完整 OpenAPI 与应用市场,支持企业自建应用与第三方 SaaS 接入。',
    source_url: 'https://open.feishu.cn', source_title: '飞书开放平台', language: 'zh', fetched_at: daysAgo(7) },
  { id: 'ev-fs-users-1', competitor: '飞书', dimension: 'target_users',
    content: '飞书在互联网与新经济中大型团队渗透较深,强调一体化协作与快速迭代场景。',
    source_url: 'https://www.feishu.cn/case', source_title: '飞书客户案例', language: 'zh', fetched_at: daysAgo(8) },
  { id: 'ev-dt-pricing-1', competitor: '钉钉', dimension: 'pricing',
    content: '钉钉基础办公功能免费,专业版/专属版按规模与增值能力阶梯收费,部分高级能力需单独采购。',
    source_url: 'https://www.dingtalk.com/price', source_title: '钉钉官网 · 商业化版本', language: 'zh', fetched_at: daysAgo(9) },
  { id: 'ev-dt-workflow-1', competitor: '钉钉', dimension: 'core_workflows',
    content: '钉钉以考勤、审批、汇报等行政办公流程见长,OA 场景成熟,模板与生态插件丰富。',
    source_url: 'https://www.dingtalk.com/product', source_title: '钉钉官网 · 功能', language: 'zh', fetched_at: daysAgo(10) },
  { id: 'ev-dt-integ-1', competitor: '钉钉', dimension: 'integrations',
    content: '钉钉宜搭低代码 + 开放平台支持业务系统对接,应用市场覆盖 ERP/CRM 等行业应用。',
    source_url: 'https://open.dingtalk.com', source_title: '钉钉开放平台', language: 'zh', fetched_at: daysAgo(11) },
  { id: 'ev-dt-users-1', competitor: '钉钉', dimension: 'target_users',
    content: '钉钉在传统行业、政企与连锁门店等规模化组织覆盖广,行政管理诉求强的团队偏好明显。',
    source_url: 'https://www.dingtalk.com/case', source_title: '钉钉客户案例', language: 'zh', fetched_at: daysAgo(12) },
  { id: 'ev-wx-pricing-1', competitor: '企业微信', dimension: 'pricing',
    content: '企业微信基础功能免费,主要增值来自与微信生态打通的客户联系/CRM 能力,部分接口有调用限制。',
    source_url: 'https://work.weixin.qq.com/price', source_title: '企业微信官网 · 价格', language: 'zh', fetched_at: daysAgo(7) },
  { id: 'ev-wx-workflow-1', competitor: '企业微信', dimension: 'core_workflows',
    content: '企业微信强项在外部客户触达与社群运营,内部协作(文档/项目)相对依赖第三方补齐。',
    source_url: 'https://work.weixin.qq.com/product', source_title: '企业微信官网 · 功能', language: 'zh', fetched_at: daysAgo(9) },
  { id: 'ev-wx-users-1', competitor: '企业微信', dimension: 'target_users',
    content: '企业微信在零售、教育、服务等需要连接 C 端客户的行业渗透高,与微信用户无缝触达是核心卖点。',
    source_url: 'https://work.weixin.qq.com/case', source_title: '企业微信客户案例', language: 'zh', fetched_at: daysAgo(8) },
  // 故意 >90 天:演示对比矩阵 / 原文卡 stale 灰角标 + 决策"佐证不足"。
  { id: 'ev-wx-integ-1', competitor: '企业微信', dimension: 'integrations',
    content: '企业微信开放接口集中在客户联系与消息能力,通用业务系统集成深度弱于飞书/钉钉(资料较旧)。',
    source_url: 'https://developer.work.weixin.qq.com', source_title: '企业微信开发者文档', language: 'zh', fetched_at: daysAgo(132) },
]

function demoProfile(name: string): CompetitorProfile {
  return {
    name,
    features: [],
    pricing: { model_type: 'freemium', tiers: [], evidence_refs: [] },
    personas: [],
    swot: { strengths: [], weaknesses: [], opportunities: [], threats: [] },
  }
}

export const DEMO_ANALYSIS: CompetitorAnalysis = {
  competitors: [demoProfile('飞书'), demoProfile('钉钉'), demoProfile('企业微信')],
  comparison: [
    {
      dimension: 'pricing',
      cells: [
        { competitor: '飞书', value_type: 'enum', value: '免费起 + 企业版按人/月',
          evidence_refs: [{ evidence_id: 'ev-fs-pricing-1', quote: '企业版按人/月计费,高级能力随版本解锁', support_verdict: 'supported' }] },
        { competitor: '钉钉', value_type: 'enum', value: '免费起 + 阶梯收费',
          evidence_refs: [{ evidence_id: 'ev-dt-pricing-1', quote: '专业版/专属版按规模阶梯收费,部分能力需单独采购', support_verdict: 'partial' }] },
        { competitor: '企业微信', value_type: 'enum', value: '免费 + 增值来自微信生态',
          evidence_refs: [{ evidence_id: 'ev-wx-pricing-1', quote: '增值来自与微信生态打通的客户联系能力', support_verdict: 'supported' }] },
      ],
    },
    {
      dimension: 'core_workflows',
      cells: [
        { competitor: '飞书', value_type: 'quote_text', value: '文档+IM+会议+审批一体化',
          evidence_refs: [{ evidence_id: 'ev-fs-workflow-1', quote: '审批流可直接嵌入文档与群,跨场景一体化程度高', support_verdict: 'supported' }] },
        { competitor: '钉钉', value_type: 'quote_text', value: '行政 OA 流程成熟',
          evidence_refs: [{ evidence_id: 'ev-dt-workflow-1', quote: '考勤、审批、汇报等行政办公流程见长,OA 场景成熟', support_verdict: 'supported' }] },
        { competitor: '企业微信', value_type: 'quote_text', value: '外部触达强,内部协作偏弱',
          evidence_refs: [{ evidence_id: 'ev-wx-workflow-1', quote: '内部协作相对依赖第三方补齐', support_verdict: 'partial' }] },
      ],
    },
    {
      dimension: 'integrations',
      cells: [
        { competitor: '飞书', value_type: 'quote_text', value: '开放平台 + 应用市场完整',
          evidence_refs: [{ evidence_id: 'ev-fs-integ-1', quote: '提供完整 OpenAPI 与应用市场', support_verdict: 'supported' }] },
        { competitor: '钉钉', value_type: 'quote_text', value: '宜搭低代码 + 行业应用',
          evidence_refs: [{ evidence_id: 'ev-dt-integ-1', quote: '宜搭低代码 + 开放平台支持业务系统对接', support_verdict: 'supported' }] },
        { competitor: '企业微信', value_type: 'quote_text', value: '集成集中在客户联系(资料较旧)',
          evidence_refs: [{ evidence_id: 'ev-wx-integ-1', quote: '通用业务系统集成深度弱于飞书/钉钉', support_verdict: 'unsupported' }] },
      ],
    },
    {
      dimension: 'target_users',
      cells: [
        { competitor: '飞书', value_type: 'quote_text', value: '互联网/新经济中大型团队',
          evidence_refs: [{ evidence_id: 'ev-fs-users-1', quote: '互联网与新经济中大型团队渗透较深', support_verdict: 'supported' }] },
        { competitor: '钉钉', value_type: 'quote_text', value: '传统行业/政企/连锁',
          evidence_refs: [{ evidence_id: 'ev-dt-users-1', quote: '传统行业、政企与连锁门店等规模化组织覆盖广', support_verdict: 'supported' }] },
        { competitor: '企业微信', value_type: 'quote_text', value: '需连接 C 端客户的行业',
          evidence_refs: [{ evidence_id: 'ev-wx-users-1', quote: '与微信用户无缝触达是核心卖点', support_verdict: 'supported' }] },
      ],
    },
  ],
}

export const DEMO_DECISIONS: DecisionSet = {
  decisions: [
    {
      stance: '建议采用',
      action: '本周启动飞书审批 + 文档一体化迁移试点(选 1-2 个高频协作团队)',
      horizon: '短期',
      risk_reversibility: '可逆',
      risk_cost: '中',
      why: '飞书把文档、IM、会议、审批收敛在同一工作台,跨场景一体化程度在三家中最高,最贴合"减少工具切换、提升协作效率"的选型目标;试点范围可控、可回退。',
      evidence_refs: [
        { evidence_id: 'ev-fs-workflow-1', quote: '审批流可直接嵌入文档与群,跨场景一体化程度高', support_verdict: 'supported' },
        { evidence_id: 'ev-fs-integ-1', quote: '提供完整 OpenAPI 与应用市场', support_verdict: 'supported' },
      ],
      watch: null,
    },
    {
      stance: '需要警惕',
      action: '与钉钉锁定书面报价与 SLA,明确高级能力是否需单独采购,再纳入预算',
      horizon: '中期',
      risk_reversibility: '不可逆',
      risk_cost: '高',
      why: '钉钉专业版/专属版按规模阶梯收费、部分高级能力需单独采购,长期 TCO 不透明;一旦全员迁入再涨价,切换成本极高,属不可逆高成本决策,需前置把价格条款谈死。',
      evidence_refs: [
        { evidence_id: 'ev-dt-pricing-1', quote: '专业版/专属版按规模阶梯收费,部分能力需单独采购', support_verdict: 'partial' },
      ],
      watch: null,
    },
    {
      stance: '持续观察',
      action: '暂不将企业微信纳入主选型,持续观察其通用业务系统集成能力的开放进度',
      horizon: '长期',
      risk_reversibility: '可逆',
      risk_cost: '低',
      why: '企业微信外部客户触达是独有强项,但通用业务系统集成深度证据偏旧且支撑不足,当前不足以支持"作为统一协作平台"的选型结论;待其开放能力补齐再评估。',
      evidence_refs: [
        { evidence_id: 'ev-wx-integ-1', quote: '通用业务系统集成深度弱于飞书/钉钉', support_verdict: 'unsupported' },
      ],
      watch: {
        metric: '企业微信通用业务系统开放 API 数量',
        threshold: '季度环比 +20%',
        trigger: '达到则纳入下一轮选型评估并补采集证据',
      },
    },
  ],
}

export const DEMO_INSIGHT: ReportInsight = {
  market_context:
    '国内协作办公平台已形成飞书、钉钉、企业微信三强格局,分别锚定一体化协作、行政 OA、外部客户触达三种心智。',
  differentiation_thesis:
    '三家的分野不在功能多寡,而在"主场景":飞书赌一体化协作效率,钉钉赌组织管理与 OA,企业微信赌与 C 端客户的连接;选型的本质是先判断团队的核心场景属于哪一类。',
  actionable_takeaway:
    '短期:对一体化协作诉求强的团队跑飞书试点;中期:把钉钉的阶梯报价与 SLA 谈定再决策;长期:观察企业微信通用集成能力是否补齐。',
}

// 终态 QC = 通过(第 2 轮 0 问题)。"分歧→解决"叙事由 ContradictionPanel 从 runStore
// events 派生(第 1 轮 retry_collect 2 项低覆盖 → 补 7 条 → 第 2 轮通过);sanitized
// detail 仅在真实降级 run 有未消解 issue 时呈现(此处诚实为空,不伪造未解决问题)。
export const DEMO_QC: SanitizedQCResult = { verdict: 'pass', issues: [] }

const traceTs = (offsetSec: number): string =>
  new Date(Date.now() - (60 - offsetSec) * 1000).toISOString()

export const DEMO_TRACE: TraceEntry[] = [
  { id: 1, run_id: DEMO_RUN_ID, node: 'collect', prompt: '', input_summary: 'targets=all',
    output_summary: '+12 (total 12)', tokens: 0, latency_ms: 8000, ts: traceTs(8) },
  { id: 2, run_id: DEMO_RUN_ID, node: 'analyze', prompt: '', input_summary: '12 evidence',
    output_summary: '3 profiles, 4 rows', tokens: 1820, latency_ms: 6000, ts: traceTs(15) },
  { id: 3, run_id: DEMO_RUN_ID, node: 'write', prompt: '', input_summary: 'analysis of 3 competitors',
    output_summary: 'report 1842 chars', tokens: 2100, latency_ms: 6000, ts: traceTs(22) },
  { id: 4, run_id: DEMO_RUN_ID, node: 'qc', prompt: '', input_summary: '12 evidence',
    output_summary: 'verdict=retry_collect issues=2 degraded=False retry=0', tokens: 640, latency_ms: 3000, ts: traceTs(26) },
  { id: 5, run_id: DEMO_RUN_ID, node: 'collect', prompt: '', input_summary: 'targets=2 gaps',
    output_summary: '+7 (total 19)', tokens: 0, latency_ms: 5000, ts: traceTs(32) },
  { id: 6, run_id: DEMO_RUN_ID, node: 'analyze', prompt: '', input_summary: '19 evidence',
    output_summary: '3 profiles, 6 rows', tokens: 1960, latency_ms: 5000, ts: traceTs(38) },
  { id: 7, run_id: DEMO_RUN_ID, node: 'write', prompt: '', input_summary: 'analysis of 3 competitors',
    output_summary: 'report 2156 chars', tokens: 2240, latency_ms: 4000, ts: traceTs(43) },
  { id: 8, run_id: DEMO_RUN_ID, node: 'qc', prompt: '', input_summary: '19 evidence',
    output_summary: 'verdict=pass issues=0 degraded=False retry=1', tokens: 700, latency_ms: 3000, ts: traceTs(46) },
  { id: 9, run_id: DEMO_RUN_ID, node: 'decide', prompt: '', input_summary: 'context=set',
    output_summary: 'decisions=3 degraded=False', tokens: 1480, latency_ms: 4000, ts: traceTs(50) },
  { id: 10, run_id: DEMO_RUN_ID, node: 'finalize', prompt: '', input_summary: '',
    output_summary: 'status=done verdict=pass', tokens: 0, latency_ms: 20, ts: traceTs(51) },
]

export interface DemoCockpitData {
  analysis: CompetitorAnalysis
  decisions: DecisionSet
  insight: ReportInsight
  qc: SanitizedQCResult
  evidence: Evidence[]
  trace: TraceEntry[]
}

/** cockpitStore demo 路径一次性取数(零网络)。 */
export function getDemoCockpitData(): DemoCockpitData {
  return {
    analysis: DEMO_ANALYSIS,
    decisions: DEMO_DECISIONS,
    insight: DEMO_INSIGHT,
    qc: DEMO_QC,
    evidence: DEMO_EVIDENCE,
    trace: DEMO_TRACE,
  }
}
