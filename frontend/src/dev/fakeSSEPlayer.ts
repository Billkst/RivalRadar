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
 */
import type { SSEEvent } from '@/types/api'
import { useRunStore } from '@/stores/runStore'

export const SAMPLE_EVENTS: SSEEvent[] = [
  { type: 'start', data: { run_id: 'run_fake01', ts: '2026-05-28T10:00:00Z' } },

  // ── collector 夜枭:search → done ────────────────────────────────────────
  { type: 'progress', data: { agent_id: 'collector', step: 'search',
      summary: '夜枭开始搜索 3 个竞品 × 4 个维度', ts: '2026-05-28T10:00:01Z' } },
  { type: 'progress', data: { agent_id: 'collector', step: 'done',
      summary: '夜枭找到 12 条新证据,累计 12 条',
      metric: { current: 12, total: 12 }, ts: '2026-05-28T10:00:08Z' } },
  { type: 'node', data: { node: 'collect',
      summary: { node: 'collect', evidence_added: 12 }, ts: '2026-05-28T10:00:08Z' } },

  // ── analyst 灵犀:thinking + chunk(reasoning typing) ────────────────────
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '灵犀正在分析 12 条证据,提取 3 个竞品的特征', ts: '2026-05-28T10:00:09Z' } },
  // 5 段 chunk 模拟 LLM typing(每段几字符,backend stream_chat 产出的 delta 形态)
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: '正在', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: '比较 ', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: 'Notion 和 Coda', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: ' 的定价模型', ts: '2026-05-28T10:00:11Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta:'差异...', ts: '2026-05-28T10:00:11Z' } },
  { type: 'progress', data: { agent_id: 'analyst', step: 'done',
      summary: '灵犀完成分析:3 个竞品 profile + 4 维对比',
      metric: { current: 3, total: 3 }, ts: '2026-05-28T10:00:15Z' } },
  { type: 'node', data: { node: 'analyze',
      summary: { node: 'analyze', competitors: 3, comparison_rows: 4 }, ts: '2026-05-28T10:00:15Z' } },

  // ── writer 灵巧:drafting + chunk(narrative typing) ────────────────────
  { type: 'progress', data: { agent_id: 'writer', step: 'drafting',
      summary: '灵巧正在撰写 3 个竞品的对比报告', ts: '2026-05-28T10:00:16Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '## 综述', ts: '2026-05-28T10:00:17Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '\nNotion 在', ts: '2026-05-28T10:00:17Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '一体化协作', ts: '2026-05-28T10:00:18Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '上占优', ts: '2026-05-28T10:00:18Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: ' [1][2]', ts: '2026-05-28T10:00:18Z' } },
  { type: 'progress', data: { agent_id: 'writer', step: 'done',
      summary: '灵巧完成报告 1842 字',
      metric: { current: 1842, total: 1842 }, ts: '2026-05-28T10:00:22Z' } },
  { type: 'node', data: { node: 'write',
      summary: { node: 'write', report_chars: 1842 }, ts: '2026-05-28T10:00:22Z' } },

  // ── qc 镜湖:validate + verdict ─────────────────────────────────────────
  { type: 'progress', data: { agent_id: 'qc', step: 'validate',
      summary: '镜湖开始质检 3 个竞品 profile', ts: '2026-05-28T10:00:23Z' } },
  { type: 'progress', data: { agent_id: 'qc', step: 'done',
      summary: '镜湖裁决:通过(发现 0 项问题,第 1 轮)',
      metric: { current: 0, total: 0 }, ts: '2026-05-28T10:00:26Z' } },
  { type: 'node', data: { node: 'qc',
      summary: { node: 'qc', verdict: 'pass', issues: 0, issue_types: {},
                 retry_count: 0, degraded: false }, ts: '2026-05-28T10:00:26Z' } },

  // ── finalize + done ────────────────────────────────────────────────────
  { type: 'node', data: { node: 'finalize',
      summary: { node: 'finalize', status: 'done', verdict: 'pass' }, ts: '2026-05-28T10:00:27Z' } },
  { type: 'done', data: { run_id: 'run_fake01', status: 'done', ts: '2026-05-28T10:00:27Z' } },
]

export interface PlayFakeSSEOptions {
  /** ms between events;default 100ms 显感 cycle ~3s。 */
  pacing?: number
  /** 自定义 events override SAMPLE_EVENTS。 */
  events?: SSEEvent[]
}

/**
 * Replay events into runStore.handleEvent with timing pacing(F2 mitigation)。
 *
 * 流程:reset → 每 event handleEvent + sleep(pacing)→ 返回 done。
 * 调用方应该已经 mount RunPage 看 office UI 跟 SSE state 协同。
 */
export async function playFakeSSE(opts: PlayFakeSSEOptions = {}): Promise<void> {
  const events = opts.events ?? SAMPLE_EVENTS
  const pacing = opts.pacing ?? 100
  const store = useRunStore.getState()
  store.reset()
  store.startRun(events[0]?.type === 'start' ? events[0].data.run_id : 'run_fake')
  for (const ev of events) {
    store.handleEvent(ev)
    if (pacing > 0) {
      await new Promise((r) => setTimeout(r, pacing))
    }
  }
}
