/**
 * evidenceStore — LRU cache for Evidence detail fetched via GET /evidence/:id.
 *
 * Design:
 *   - max 50 entries (DESIGN.md: hover/click 引用 chip → 滑出证据面板, 50 上限对
 *     单 run 4 卡 + 矩阵 + drawer 同屏使用足够,避免内存累)
 *   - access-order eviction:Map insertion order maintained, on hit re-insert
 *     to move-to-end
 *   - in-flight Promise dedup:并发请求同 id 不打两次 fetch
 *   - Zustand store 暴露 getEvidence(id) — 调用方 await + 自动 cache
 */
import { create } from 'zustand'
import { fetchEvidence } from '@/lib/api'
import type { Evidence } from '@/types/api'

const MAX_ENTRIES = 50

interface EvidenceStore {
  cache: Map<string, Evidence>
  inflight: Map<string, Promise<Evidence>>
  getEvidence: (id: string) => Promise<Evidence>
  clear: () => void
}

function evict(cache: Map<string, Evidence>): Map<string, Evidence> {
  if (cache.size <= MAX_ENTRIES) return cache
  const next = new Map(cache)
  // Drop oldest entries until at capacity. Map iteration is insertion-order.
  while (next.size > MAX_ENTRIES) {
    const oldestKey = next.keys().next().value
    if (oldestKey === undefined) break
    next.delete(oldestKey)
  }
  return next
}

export const useEvidenceStore = create<EvidenceStore>((set, get) => ({
  cache: new Map(),
  inflight: new Map(),

  getEvidence: async (id) => {
    const state = get()

    // Cache hit — re-insert to move-to-end (LRU access tracking).
    const hit = state.cache.get(id)
    if (hit !== undefined) {
      const next = new Map(state.cache)
      next.delete(id)
      next.set(id, hit)
      set({ cache: next })
      return hit
    }

    // Already fetching — dedupe.
    const pending = state.inflight.get(id)
    if (pending) return pending

    // Cold fetch.
    const promise = fetchEvidence(id)
      .then((ev) => {
        const after = get()
        let cache = new Map(after.cache)
        cache.set(id, ev)
        cache = evict(cache)
        const inflight = new Map(after.inflight)
        inflight.delete(id)
        set({ cache, inflight })
        return ev
      })
      .catch((err) => {
        // Clear in-flight on failure so caller can retry.
        const after = get()
        const inflight = new Map(after.inflight)
        inflight.delete(id)
        set({ inflight })
        throw err
      })

    const inflight = new Map(state.inflight)
    inflight.set(id, promise)
    set({ inflight })

    return promise
  },

  clear: () => set({ cache: new Map(), inflight: new Map() }),
}))
