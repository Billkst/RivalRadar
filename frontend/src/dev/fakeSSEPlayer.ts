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

  // ── collector 收集员:search → done ──────────────────────────────────────
  { type: 'progress', data: { agent_id: 'collector', step: 'search',
      summary: '开始搜索 3 个竞品 × 4 个维度', ts: '2026-05-28T10:00:01Z' } },
  { type: 'progress', data: { agent_id: 'collector', step: 'done',
      summary: '找到 12 条新证据,累计 12 条',
      metric: { current: 12, total: 12 }, ts: '2026-05-28T10:00:08Z' } },
  { type: 'node', data: { node: 'collect',
      summary: { node: 'collect', evidence_added: 12 }, ts: '2026-05-28T10:00:08Z' } },

  // ── analyst 分析员:thinking + chunk(reasoning typing) ─────────────────
  { type: 'progress', data: { agent_id: 'analyst', step: 'thinking',
      summary: '正在分析 12 条证据,提取 3 个竞品的特征', ts: '2026-05-28T10:00:09Z' } },
  // 5 段 chunk 模拟 LLM typing(每段几字符,backend stream_chat 产出的 delta 形态)
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: '正在', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: '比较 ', ts: '2026-05-28T10:00:10Z' } },
  { type: 'chunk', data: { agent_id: 'analyst', step: 'reasoning', delta: 'Notion 和 Coda', ts: '2026-05-28T10:00:10Z' } },
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
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '\nNotion 在', ts: '2026-05-28T10:00:17Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '一体化协作', ts: '2026-05-28T10:00:18Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: '上占优', ts: '2026-05-28T10:00:18Z' } },
  { type: 'chunk', data: { agent_id: 'writer', step: 'drafting', delta: ' [1][2]', ts: '2026-05-28T10:00:18Z' } },
  { type: 'progress', data: { agent_id: 'writer', step: 'done',
      summary: '完成报告 1842 字',
      metric: { current: 1842, total: 1842 }, ts: '2026-05-28T10:00:22Z' } },
  { type: 'node', data: { node: 'write',
      summary: { node: 'write', report_chars: 1842 }, ts: '2026-05-28T10:00:22Z' } },

  // ── qc 质检员:validate + verdict ───────────────────────────────────────
  { type: 'progress', data: { agent_id: 'qc', step: 'validate',
      summary: '开始质检 3 个竞品 profile', ts: '2026-05-28T10:00:23Z' } },
  { type: 'progress', data: { agent_id: 'qc', step: 'done',
      summary: '裁决:通过(发现 0 项问题,第 1 轮)',
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
