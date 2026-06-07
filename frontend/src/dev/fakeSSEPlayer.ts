/**
 * fakeSSEPlayer — replay recorded SSE events into runStore for office UI dev(F2 修订)。
 *
 * 用途(plan v3.2 §9 Epic 3.0):office UI 实装时(Day-3 Epic 3.3-3.6 + 4.1-4.4)
 * 用 fake stream 验证视觉,不依赖 backend Epic 2 ready / Doubao network 真打。
 * Backend down / Clash fake-ip 卡时也能 demo office UI。
 *
 * Usage(dev mode only,production tree-shake 掉):
 *   import { playFakeSSE } from '@/dev/fakeSSEPlayer'
 *   await playFakeSSE()                            // 用内嵌 SAMPLE_EVENTS
 *   await playFakeSSE({ pacing: 50 })              // 加快 replay
 *   await playFakeSSE({ events: customEvents })    // 自定义 events array
 *
 * SAMPLE_EVENTS 模拟 4 agent 协作 cycle(collector 搜索 → analyst 分析 → writer 撰写
 * → qc 质检),包含 progress / chunk(typing 效果)/ node / done events,与 backend
 * Epic 2 实际 emit 行为一致。
 *
 * 维度集与 demoFixture 的 DEMO_RUN_DETAIL / DEMO_ANALYSIS 1:1 对齐(4 维:
 * pricing / core_workflows / integrations / target_users),且 cell 真值镜像
 * DEMO_ANALYSIS。integrations·企业微信 是唯一被策展剔除的格(证据 >90 天 stale +
 * 不支撑结论),qc 第 1 轮 retry_collect 因它低覆盖,第 2 轮补证后仍不足 → 剔除。
 */
import type { SSEEvent } from '@/types/api'
import { useRunStore } from '@/stores/runStore'

export const SAMPLE_EVENTS: SSEEvent[] = [
  { type: 'start', data: { run_id: 'run_fake01', ts: '2026-05-28T10:00:00Z' } },

  // ── collector 收集员:search → done ──────────────────────────────────────
  { type: 'progress', data: { agent_id: 'collector', step: 'search',
      summary: '开始搜索 3 个竞品 × 4 个维度', ts: '2026-05-28T10:00:01Z' } },
  // Plan C 检索台:逐条查询词 + 命中数(query / query_hit);来源卡:source(round 0)。
  { type: 'query', data: { competitor: '飞书', dimension: 'pricing',
      query_text: '飞书 定价 套餐 价格', language: 'zh', round: 0, ts: '2026-05-28T10:00:02Z' } },
  { type: 'query_hit', data: { query_text: '飞书 定价 套餐 价格', hit_count: 4, round: 0, ts: '2026-05-28T10:00:03Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_fs_pricing', competitor: '飞书', dimension: 'pricing',
      source_title: '飞书官网 · 价格', source_url: 'https://www.feishu.cn/price',
      fetched_at: '2026-05-28T10:00:03Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:03Z' } },
  { type: 'query', data: { competitor: '钉钉', dimension: 'pricing',
      query_text: '钉钉 专业版 价格 对比', language: 'zh', round: 0, ts: '2026-05-28T10:00:04Z' } },
  { type: 'query_hit', data: { query_text: '钉钉 专业版 价格 对比', hit_count: 3, round: 0, ts: '2026-05-28T10:00:05Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_dt_pricing', competitor: '钉钉', dimension: 'pricing',
      source_title: '钉钉官网 · 商业化版本', source_url: 'https://www.dingtalk.com/price',
      fetched_at: '2026-05-28T10:00:05Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:05Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_wx_pricing', competitor: '企业微信', dimension: 'pricing',
      source_title: '企业微信官网 · 价格', source_url: 'https://work.weixin.qq.com/price',
      fetched_at: '2026-05-28T10:00:05Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:05Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_fs_flow', competitor: '飞书', dimension: 'core_workflows',
      source_title: '飞书官网 · 产品能力', source_url: 'https://www.feishu.cn/product',
      fetched_at: '2026-05-28T10:00:05Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:05Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_dt_flow', competitor: '钉钉', dimension: 'core_workflows',
      source_title: '钉钉官网 · 功能', source_url: 'https://www.dingtalk.com/product',
      fetched_at: '2026-05-28T10:00:06Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:06Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_wx_flow', competitor: '企业微信', dimension: 'core_workflows',
      source_title: '企业微信官网 · 功能', source_url: 'https://work.weixin.qq.com/product',
      fetched_at: '2026-05-28T10:00:06Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:06Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_fs_integ', competitor: '飞书', dimension: 'integrations',
      source_title: '飞书开放平台', source_url: 'https://open.feishu.cn',
      fetched_at: '2026-05-28T10:00:06Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:06Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_dt_integ', competitor: '钉钉', dimension: 'integrations',
      source_title: '钉钉开放平台', source_url: 'https://open.dingtalk.com',
      fetched_at: '2026-05-28T10:00:06Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:06Z' } },
  // integrations·企业微信:英文检索 0 命中(覆盖不足),qc 第 1 轮 retry_collect 的原因。
  { type: 'query', data: { competitor: '企业微信', dimension: 'integrations',
      query_text: 'WeCom open API third-party integration', language: 'en', round: 0, ts: '2026-05-28T10:00:06Z' } },
  { type: 'query_hit', data: { query_text: 'WeCom open API third-party integration', hit_count: 0, round: 0, ts: '2026-05-28T10:00:07Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_fs_users', competitor: '飞书', dimension: 'target_users',
      source_title: '飞书客户案例', source_url: 'https://www.feishu.cn/case',
      fetched_at: '2026-05-28T10:00:07Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:07Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_dt_users', competitor: '钉钉', dimension: 'target_users',
      source_title: '钉钉客户案例', source_url: 'https://www.dingtalk.com/case',
      fetched_at: '2026-05-28T10:00:07Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:07Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_wx_users', competitor: '企业微信', dimension: 'target_users',
      source_title: '企业微信客户案例', source_url: 'https://work.weixin.qq.com/case',
      fetched_at: '2026-05-28T10:00:07Z', language: 'zh', round: 0, ts: '2026-05-28T10:00:07Z' } },
  { type: 'progress', data: { agent_id: 'collector', step: 'done',
      summary: '找到 12 条新证据,累计 12 条',
      metric: { current: 12, total: 12 }, ts: '2026-05-28T10:00:08Z' } },
  { type: 'node', data: { node: 'collect',
      summary: { node: 'collect', evidence_added: 12 }, ts: '2026-05-28T10:00:08Z' } },

  // ── analyst 分析员:thinking + chunk(reasoning typing) ─────────────────
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '正在分析 12 条证据,提取 3 个竞品的特征',
      metric: { current: 0, total: 13 }, ts: '2026-05-28T10:00:09Z' } },
  // 逐竞品·逐抽取增量进度(真 backend analyze 内 _make_ticker emit;在 cockpit 折成一条
  // 会动的进度条「分析 X·Y (n/13)」,而非每事件一行 —— 真跑 ~174s 长节点等待不静默)。
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '分析 飞书·定价', metric: { current: 2, total: 13 }, ts: '2026-05-28T10:00:10Z' } },
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '分析 钉钉·核心工作流', metric: { current: 5, total: 13 }, ts: '2026-05-28T10:00:12Z' } },
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '分析 企业微信·目标用户', metric: { current: 9, total: 13 }, ts: '2026-05-28T10:00:13Z' } },
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '生成跨竞品对比矩阵', metric: { current: 13, total: 13 }, ts: '2026-05-28T10:00:14Z' } },
  // Plan C 逐维 cell_row(乱序安全,按 dimension 落位 → 矩阵逐维生长 + 计划 rail 勾选)。
  // 值镜像 demoFixture.DEMO_ANALYSIS;cell_row 本身不带 support_verdict(只在
  // verdict_recheck cell_verdicts 里给三色)。
  { type: 'cell_row', data: { dimension: 'pricing', status: 'ok', ts: '2026-05-28T10:00:14Z',
      cells: [
        { competitor: '飞书', value_type: 'enum', value: '免费起 + 企业版按人/月',
          evidence_refs: [{ evidence_id: 'ev_fake_fs_pricing', quote: '企业版按人/月计费' }] },
        { competitor: '钉钉', value_type: 'enum', value: '免费起 + 阶梯收费',
          evidence_refs: [{ evidence_id: 'ev_fake_dt_pricing', quote: '按规模阶梯收费,部分能力需单独采购' }] },
        { competitor: '企业微信', value_type: 'enum', value: '免费 + 增值来自微信生态',
          evidence_refs: [{ evidence_id: 'ev_fake_wx_pricing', quote: '增值来自与微信生态打通的客户联系能力' }] },
      ] } },
  { type: 'cell_row', data: { dimension: 'core_workflows', status: 'ok', ts: '2026-05-28T10:00:14Z',
      cells: [
        { competitor: '飞书', value_type: 'quote_text', value: '文档+IM+会议+审批一体化',
          evidence_refs: [{ evidence_id: 'ev_fake_fs_flow', quote: '审批流可直接嵌入文档与群' }] },
        { competitor: '钉钉', value_type: 'quote_text', value: '行政 OA 流程成熟',
          evidence_refs: [{ evidence_id: 'ev_fake_dt_flow', quote: '考勤、审批、汇报等行政办公流程见长' }] },
        { competitor: '企业微信', value_type: 'quote_text', value: '外部触达强,内部协作偏弱',
          evidence_refs: [{ evidence_id: 'ev_fake_wx_flow', quote: '内部协作相对依赖第三方补齐' }] },
      ] } },
  { type: 'cell_row', data: { dimension: 'target_users', status: 'ok', ts: '2026-05-28T10:00:14Z',
      cells: [
        { competitor: '飞书', value_type: 'quote_text', value: '互联网/新经济中大型团队',
          evidence_refs: [{ evidence_id: 'ev_fake_fs_users', quote: '互联网与新经济中大型团队渗透较深' }] },
        { competitor: '钉钉', value_type: 'quote_text', value: '传统行业/政企/连锁',
          evidence_refs: [{ evidence_id: 'ev_fake_dt_users', quote: '传统行业、政企与连锁门店覆盖广' }] },
        { competitor: '企业微信', value_type: 'quote_text', value: '需连接 C 端客户的行业',
          evidence_refs: [{ evidence_id: 'ev_fake_wx_users', quote: '与微信用户无缝触达是核心卖点' }] },
      ] } },
  // integrations:round 0 只含 飞书 + 钉钉 两格(企业微信集成证据不足,本轮不出格)。
  { type: 'cell_row', data: { dimension: 'integrations', status: 'ok', ts: '2026-05-28T10:00:14Z',
      cells: [
        { competitor: '飞书', value_type: 'quote_text', value: '开放平台 + 应用市场完整',
          evidence_refs: [{ evidence_id: 'ev_fake_fs_integ', quote: '提供完整 OpenAPI 与应用市场' }] },
        { competitor: '钉钉', value_type: 'quote_text', value: '宜搭低代码 + 行业应用',
          evidence_refs: [{ evidence_id: 'ev_fake_dt_integ', quote: '宜搭低代码 + 开放平台支持业务系统对接' }] },
      ] } },
  // 5 段 chunk 模拟 LLM typing(每段几字符,backend stream_chat 产出的 delta 形态)
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: '正在', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: '比较 ', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: '飞书 和 钉钉', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: ' 的定价模型', ts: '2026-05-28T10:00:11Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta:'差异...', ts: '2026-05-28T10:00:11Z' } },
  { type: 'progress', data: { agent_id: 'analyst', step: 'done',
      summary: '完成分析:3 个竞品 profile + 4 维对比',
      metric: { current: 3, total: 3 }, ts: '2026-05-28T10:00:15Z' } },
  { type: 'node', data: { node: 'analyze',
      summary: { node: 'analyze', competitors: 3, comparison_rows: 4 }, ts: '2026-05-28T10:00:15Z' } },

  // ── writer 撰稿员:drafting + chunk(narrative typing) ──────────────────
  { type: 'progress', data: { agent_id: 'writer', step: 'drafting',
      summary: '正在撰写 3 个竞品的对比报告', ts: '2026-05-28T10:00:16Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '## 综述', ts: '2026-05-28T10:00:17Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '\n飞书 在', ts: '2026-05-28T10:00:17Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '一体化协作', ts: '2026-05-28T10:00:18Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '上占优', ts: '2026-05-28T10:00:18Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: ' [1][2]', ts: '2026-05-28T10:00:18Z' } },
  { type: 'progress', data: { agent_id: 'writer', step: 'done',
      summary: '完成报告 1842 字',
      metric: { current: 1842, total: 1842 }, ts: '2026-05-28T10:00:22Z' } },
  { type: 'node', data: { node: 'write',
      summary: { node: 'write', report_chars: 1842 }, ts: '2026-05-28T10:00:22Z' } },

  // ── qc 质检员(第 1 轮):证据不足,打回采集(招牌时刻 #2 — 重试环触发) ──────
  // 低覆盖问题对准 integrations·企业微信(本轮 0 命中 → 该格缺位)。
  { type: 'progress', data: { agent_id: 'qc', step: 'validate',
      summary: '开始质检 3 个竞品 profile', ts: '2026-05-28T10:00:23Z' } },
  { type: 'progress', data: { agent_id: 'qc', step: 'done',
      summary: '裁决:证据不足,打回采集(2 项问题,第 1 轮)', ts: '2026-05-28T10:00:26Z' } },
  { type: 'node', data: { node: 'qc',
      summary: { node: 'qc', verdict: 'retry_collect', issues: 2,
                 issue_types: { low_coverage: 2 }, retry_count: 0, degraded: false },
      ts: '2026-05-28T10:00:26Z' } },

  // ── 第 2 轮:采集员按反馈广搜补缺口 → 重试环显示「证据 12→19」 ─────────────────
  // 补 integrations·企业微信(资料偏旧),即便补了也仍不足以支撑 → 终态被策展剔除。
  { type: 'progress', data: { agent_id: 'collector', step: 'broaden',
      summary: '按质检反馈广搜 2 个证据缺口', ts: '2026-05-28T10:00:27Z' } },
  // Plan C retry 轮:补 source(round 1)+ evidence_delta(round 1)驱动重试环 + 计划 rail reopen。
  { type: 'query', data: { competitor: '企业微信', dimension: 'integrations',
      query_text: '企业微信 开放接口 业务系统 集成', language: 'zh', round: 1, ts: '2026-05-28T10:00:28Z' } },
  { type: 'query_hit', data: { query_text: '企业微信 开放接口 业务系统 集成', hit_count: 2, round: 1, ts: '2026-05-28T10:00:29Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_wx_integ', competitor: '企业微信', dimension: 'integrations',
      source_title: '企业微信开发者文档', source_url: 'https://developer.work.weixin.qq.com',
      fetched_at: '2026-05-28T10:00:30Z', language: 'zh', round: 1, ts: '2026-05-28T10:00:30Z' } },
  { type: 'source', data: { evidence_id: 'ev_fake_wx_integ2', competitor: '企业微信', dimension: 'integrations',
      source_title: '企业微信集成实践 - 知乎专栏', source_url: 'https://zhuanlan.zhihu.com/wecom-integ',
      fetched_at: '2026-05-28T10:00:31Z', language: 'zh', round: 1, ts: '2026-05-28T10:00:31Z' } },
  { type: 'evidence_delta', data: { round: 1, added_count: 7, total_count: 19,
      new_evidence_ids: ['ev_fake_wx_integ', 'ev_fake_wx_integ2'], ts: '2026-05-28T10:00:31Z' } },
  { type: 'node', data: { node: 'collect',
      summary: { node: 'collect', evidence_added: 7 }, ts: '2026-05-28T10:00:32Z' } },
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '重新分析 19 条证据,复核 integrations 缺口', ts: '2026-05-28T10:00:33Z' } },
  // 补证后 integrations 复核完成 → 重发该维 cell_row(ts 晚于 round-1 reopen),计划 rail 该维
  // 从「补证中」回落 done(招牌:reopen→done 闭环)。企业微信集成证据补了仍不足 → 终态被策展
  // 剔除(见下 verdict_recheck.dropped),故该维仍只 飞书+钉钉 两格,不回填企业微信。
  { type: 'cell_row', data: { dimension: 'integrations', status: 'ok', ts: '2026-05-28T10:00:37Z',
      cells: [
        { competitor: '飞书', value_type: 'quote_text', value: '开放平台 + 应用市场完整',
          evidence_refs: [{ evidence_id: 'ev_fake_fs_integ', quote: '提供完整 OpenAPI 与应用市场' }] },
        { competitor: '钉钉', value_type: 'quote_text', value: '宜搭低代码 + 行业应用',
          evidence_refs: [{ evidence_id: 'ev_fake_dt_integ', quote: '宜搭低代码 + 开放平台支持业务系统对接' }] },
      ] } },
  { type: 'node', data: { node: 'analyze',
      summary: { node: 'analyze', competitors: 3, comparison_rows: 4 }, ts: '2026-05-28T10:00:38Z' } },
  { type: 'progress', data: { agent_id: 'writer', step: 'drafting',
      summary: '更新对比报告', ts: '2026-05-28T10:00:39Z' } },
  { type: 'node', data: { node: 'write',
      summary: { node: 'write', report_chars: 2156 }, ts: '2026-05-28T10:00:43Z' } },
  { type: 'progress', data: { agent_id: 'qc', step: 'done',
      summary: '裁决:通过(0 项问题,第 2 轮)', ts: '2026-05-28T10:00:46Z' } },
  { type: 'node', data: { node: 'qc',
      summary: { node: 'qc', verdict: 'pass', issues: 0, issue_types: {},
                 retry_count: 1, degraded: false }, ts: '2026-05-28T10:00:46Z' } },
  // Plan C verdict_recheck:cell 级真三色刷新(supported/partial)+ dropped 剔除一格。
  // 体现 SourceCards/矩阵三色 + 「—」 + StatusBar「已剔除 Z」(droppedCells 另存,
  // cell_verdicts 只含保留格;codex P2#12)。值镜像 demoFixture.DEMO_ANALYSIS:
  // 11 保留格逐格三色 + integrations·企业微信 唯一被剔除。
  { type: 'verdict_recheck', data: {
      ts: '2026-05-28T10:00:46Z',
      cell_verdicts: [
        { dimension: 'pricing', competitor: '飞书', support_verdict: 'supported' },
        { dimension: 'pricing', competitor: '钉钉', support_verdict: 'partial' },
        { dimension: 'pricing', competitor: '企业微信', support_verdict: 'supported' },
        { dimension: 'core_workflows', competitor: '飞书', support_verdict: 'supported' },
        { dimension: 'core_workflows', competitor: '钉钉', support_verdict: 'supported' },
        { dimension: 'core_workflows', competitor: '企业微信', support_verdict: 'partial' },
        { dimension: 'integrations', competitor: '飞书', support_verdict: 'supported' },
        { dimension: 'integrations', competitor: '钉钉', support_verdict: 'supported' },
        { dimension: 'target_users', competitor: '飞书', support_verdict: 'supported' },
        { dimension: 'target_users', competitor: '钉钉', support_verdict: 'supported' },
        { dimension: 'target_users', competitor: '企业微信', support_verdict: 'supported' },
      ],
      dropped: [{ dimension: 'integrations', competitor: '企业微信',
        detail: '集成生态证据 >90 天且不支撑结论,策展剔除' }],
      downgraded: [
        { dimension: 'pricing', competitor: '钉钉' },
        { dimension: 'core_workflows', competitor: '企业微信' },
      ],
      summary: { supported: 9, partial: 2, dropped: 1 },
    } },

  // ── decide 决策(full-C / Epic 2)─────────────────────────────────────────
  { type: 'progress', data: { agent_id: 'decide', step: 'deciding',
      summary: '基于证据生成决策建议', ts: '2026-05-28T10:00:47Z' } },
  { type: 'node', data: { node: 'decide',
      summary: { node: 'decide', decisions: 3, decision_degraded: false }, ts: '2026-05-28T10:00:50Z' } },

  // ── finalize + done ────────────────────────────────────────────────────
  { type: 'node', data: { node: 'finalize',
      summary: { node: 'finalize', status: 'done', verdict: 'pass' }, ts: '2026-05-28T10:00:51Z' } },
  { type: 'done', data: { run_id: 'run_fake01', status: 'done', ts: '2026-05-28T10:00:51Z' } },
]

export interface PlayFakeSSEOptions {
  /** 速度倍数 — 1.0 = 跟 SAMPLE_EVENTS ts 字段(模拟真 LLM ~25s)同步;
   *  0.2 = 5x faster(~5s);2.0 = 2x slower(~50s,慢动作 spike)。
   *  default 1.0 真节奏让 LiveFeedPanel timestamp 和 office UI 动作肉眼对得上,
   *  handoff 800ms 与节点间隔 1-7s 不会被覆盖。 */
  speed?: number
  /** 自定义 events override SAMPLE_EVENTS。 */
  events?: SSEEvent[]
  /** Codex review P1 fix:override run_id 给 store.startRun + rebased start event。
   *  根因:RunPage 用 isDemoRun(run_id) bypass 后调 playFakeSSE,但 fakeSSEPlayer
   *  默认从 SAMPLE_EVENTS[0].data.run_id 取 'run_fake01',store.runId 永远 !==
   *  'run_demo01' → RunPage liveAlreadyHere guard 失效 → 每次 store update
   *  re-trigger 新 playFakeSSE,demo bullet-proof dead loop。Demo 路径传
   *  { runId: DEMO_RUN_ID } 强制对齐。 */
  runId?: string
}

const MIN_DELAY_MS = 50 // 防 speed=0 死循环;两个事件间至少 50ms

/**
 * Replay events into runStore.handleEvent 按 SAMPLE_EVENTS ts 字段的相对间隔
 * (F2 mitigation)。
 *
 * 节奏来源:每个 event 的 data.ts 字段(SAMPLE_EVENTS 模拟真 LLM 时间线 ~25s)。
 * 相邻 event ts 差就是真实间隔,乘 speed multiplier 得到实际 sleep。
 *
 * 这样 default speed=1.0 时,user 看到的 "office UI 节奏" 跟 "LiveFeedPanel
 * 时间戳跨度" 完全一致 —— 25s 戏本就跑 25s,不会出现 "3s 跑完 25s" 的脱节感。
 *
 * 调用方应该已经 mount RunPage 看 office UI 跟 SSE state 协同。
 */
export async function playFakeSSE(opts: PlayFakeSSEOptions = {}): Promise<void> {
  const events = opts.events ?? SAMPLE_EVENTS
  const speed = opts.speed ?? 1.0
  const store = useRunStore.getState()
  // opts.runId override 优先(demo path 传 DEMO_RUN_ID 让 RunPage guard 对齐),
  // fallback events[0].run_id 或 'run_fake'(老调用方 / 自定义 events 路径)
  const effectiveRunId =
    opts.runId ?? (events[0]?.type === 'start' ? events[0].data.run_id : 'run_fake')
  store.reset()
  store.startRun(effectiveRunId)

  // D19 spike fix:rebase event ts 到 user 本地 wall clock 起点。
  // 根因:SAMPLE_EVENTS ts 写死为 '2026-05-28T10:00:01Z' 等历史时刻,直接 emit
  // 给 store 会导致 useElapsed 算 Date.now() - 历史 ts:
  //   wall clock < 历史 ts → diff 为负 → Math.max(0,negative) clamp 0 →
  //   character 下方 "已工作 N 秒" 永远显示 "0s"。
  // 修法:把第一个 event ts 当 baseline,replay 时所有 event ts 改成
  // Date.now() + (eventTs - baselineTs) * speed。useElapsed 用 Date.now() 算
  // 自然就对了。production 真打 LLM ts 本来就是 emit 时刻,不需要 rebase。
  // 顺便 LiveFeedPanel 显示的时间戳也变 user 本地实时(更真实)。
  const baselineTsMs = events[0]?.data.ts ? new Date(events[0].data.ts).getTime() : null
  const wallClockStartMs = Date.now()

  let prevTsMs: number | null = null
  for (const ev of events) {
    const curTsMs = ev.data.ts ? new Date(ev.data.ts).getTime() : null
    if (prevTsMs !== null && curTsMs !== null && curTsMs > prevTsMs) {
      const realIntervalMs = (curTsMs - prevTsMs) * speed
      const delay = Math.max(MIN_DELAY_MS, realIntervalMs)
      await new Promise((r) => setTimeout(r, delay))
    }
    prevTsMs = curTsMs

    // 改写 ts 到 wall clock + 改写 start event run_id 到 effectiveRunId,
    // emit rebased event 给 store(start event 的 run_id 也要 override 让 runStore
    // 后续 events 用同样 id,否则 SSE 'start' handler 会把 store.runId 改回
    // SAMPLE_EVENTS 的 run_fake01,demo guard 又失效)
    let evToEmit: SSEEvent = ev
    if (baselineTsMs !== null && curTsMs !== null) {
      const newTs = new Date(
        wallClockStartMs + (curTsMs - baselineTsMs) * speed,
      ).toISOString()
      evToEmit = { ...ev, data: { ...ev.data, ts: newTs } } as SSEEvent
    }
    if (evToEmit.type === 'start' && opts.runId) {
      evToEmit = {
        ...evToEmit,
        data: { ...evToEmit.data, run_id: opts.runId },
      } as SSEEvent
    }
    store.handleEvent(evToEmit)
  }
}
