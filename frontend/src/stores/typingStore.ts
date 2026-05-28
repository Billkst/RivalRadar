/**
 * typingStore — per-agent LLM chunk typing buffer with throttle(D7 修订)。
 *
 * 设计要点(plan v3.2 §4):
 *   1. **WINDOW = 50** chunks per agent —— pending 滚动 buffer,>50 时 shift 旧的
 *      防 backend backpressure 失控时单 agent 占太多内存。
 *   2. **BATCH_MS = 16ms** setState —— ~60fps 上限,把多个 chunk 合并成 1 次
 *      React re-render,防 chunk event 100/s 引发 re-render storm。
 *   3. **MAX_CHARS = 3000** 单 agent string 上限 —— 长 narrative 滚动 buffer,
 *      slice(-3000) 截尾。SpeechBubble 显示最后 N 字符,LiveFeedPanel 全文。
 *
 * 内存上限:4 agent × 3000 char + 4 × 50 chunks pending ≈ 12 KB。完全可控。
 * Re-render 速率:最多 60fps,流畅不卡。
 *
 * 输入:SSE chunk event 通过 runStore.handleEvent 调 appendChunk(agent_id, delta)。
 *      runStore 不存 chunk 到 events[](太频繁会爆 array),只 forward 给本 store。
 * 输出:SpeechBubble + LiveFeedPanel 通过 useTypingStore((s) => s.byAgent[id])
 *      subscribe per-agent string,React 自动 re-render。
 */
import { create } from 'zustand'

interface TypingStore {
  byAgent: Record<string, string>
  appendChunk: (agent_id: string, delta: string) => void
  clear: (agent_id: string) => void
  resetAll: () => void
}

const WINDOW = 50
const BATCH_MS = 16
const MAX_CHARS = 3000

// Module-level pending buffer + flush timer。不放 store state 因为这些是
// 节流实现细节(同步累积,不触发 re-render),只在 batch flush 时进 store。
const pending: Record<string, string[]> = {}
let flushTimer: ReturnType<typeof setTimeout> | null = null

export const useTypingStore = create<TypingStore>((set, get) => ({
  byAgent: {},

  appendChunk: (agent_id, delta) => {
    // 1. 同步累积到 pending(无 setState,不触发 React re-render)
    if (!pending[agent_id]) pending[agent_id] = []
    pending[agent_id].push(delta)
    if (pending[agent_id].length > WINDOW) pending[agent_id].shift()

    // 2. 防抖 batch flush —— 已有 timer 则等它执行,无 timer 则起新的
    if (flushTimer) return
    flushTimer = setTimeout(() => {
      const current = get().byAgent
      const updates: Record<string, string> = { ...current }
      for (const [aid, chunks] of Object.entries(pending)) {
        if (chunks.length === 0) continue
        const merged = (updates[aid] || '') + chunks.join('')
        updates[aid] = merged.length > MAX_CHARS ? merged.slice(-MAX_CHARS) : merged
        pending[aid] = []
      }
      set({ byAgent: updates })
      flushTimer = null
    }, BATCH_MS)
  },

  clear: (agent_id) => {
    // 同时清 pending buffer —— 否则下次 16ms batch flush 把 pending chunks
    // 加回 byAgent,clear 失效(race condition)。
    pending[agent_id] = []
    set((s) => ({ byAgent: { ...s.byAgent, [agent_id]: '' } }))
  },

  resetAll: () => {
    for (const aid in pending) pending[aid] = []
    if (flushTimer) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
    set({ byAgent: {} })
  },
}))
