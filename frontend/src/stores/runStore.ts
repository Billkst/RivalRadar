/**
 * runStore — 单 run 实时状态(SSE event reducer)。
 *
 * 设计要点:
 *   1. events 保留所有原始 SSE event(供 ObservabilityPanel 原始 timeline + retry index 推导)
 *   2. NodeState = idle/running/done/failed/retrying (spec §11.4 5 状态)
 *   3. 语义:**node event 到达 = 该节点 done**(后端节点完成时 yield);
 *      "running" 中间态由 Task 6 DAG canvas 用过渡视觉呈现,store 不存
 *   4. CQ1 trace normalize:trace event 转 node event 形式后走同 reducer
 *   5. retry_index 不存字段,从 events.filter 推导(Codex #2)
 *   6. qcIssueCount/qcIssueTypes — 后端 SSE 只暴露 count + types map,不带 detail;
 *      issue text 详情等 Task 16 后端 schema 补强(plan v2 Day-4 S9)
 */
import { create } from 'zustand'
import type { QCVerdict, SSEEvent } from '@/types/api'

export type NodeState = 'idle' | 'running' | 'done' | 'failed' | 'retrying'
export type NodeName = 'collect' | 'analyze' | 'write' | 'qc'

export const NODE_NAMES: readonly NodeName[] = ['collect', 'analyze', 'write', 'qc'] as const

export type RunStatus =
  | 'idle'
  | 'running'
  | 'done'
  | 'failed'
  | 'insufficient_evidence'
  | 'degraded'

export interface EvidenceCountSnapshot {
  ts: string
  count: number
}

interface RunStore {
  runId: string | null
  status: RunStatus
  nodes: Record<NodeName, NodeState>
  events: SSEEvent[]
  degraded: boolean
  retryCount: number
  qcVerdict: QCVerdict | null
  qcIssueCount: number
  qcIssueTypes: Record<string, number>
  evidenceCountSnapshots: EvidenceCountSnapshot[]

  startRun: (runId: string) => void
  handleEvent: (ev: SSEEvent) => void
  reset: () => void
}

const initialNodes = (): Record<NodeName, NodeState> => ({
  collect: 'idle',
  analyze: 'idle',
  write: 'idle',
  qc: 'idle',
})

const isKnownNode = (name: string): name is NodeName =>
  (NODE_NAMES as readonly string[]).includes(name)

/** Derive retry index for a given node by counting prior occurrences in event log. */
export function retryIndexOf(events: SSEEvent[], node: NodeName, beforeIdx: number): number {
  let count = 0
  for (let i = 0; i < beforeIdx; i++) {
    const e = events[i]
    if ((e.type === 'node' || e.type === 'trace') && e.data.node === node) count++
  }
  return count
}

export const useRunStore = create<RunStore>((set, get) => ({
  runId: null,
  status: 'idle',
  nodes: initialNodes(),
  events: [],
  degraded: false,
  retryCount: 0,
  qcVerdict: null,
  qcIssueCount: 0,
  qcIssueTypes: {},
  evidenceCountSnapshots: [],

  startRun: (runId) =>
    set({
      runId,
      status: 'running',
      nodes: initialNodes(),
      events: [],
      degraded: false,
      retryCount: 0,
      qcVerdict: null,
      qcIssueCount: 0,
      qcIssueTypes: {},
      evidenceCountSnapshots: [],
    }),

  handleEvent: (ev) => {
    const state = get()
    const events = [...state.events, ev]

    // ── start event ──────────────────────────────────────────────────────
    if (ev.type === 'start') {
      set({
        runId: ev.data.run_id,
        status: 'running',
        nodes: initialNodes(),
        events,
        degraded: false,
        retryCount: 0,
        qcVerdict: null,
        qcIssueCount: 0,
        qcIssueTypes: {},
        evidenceCountSnapshots: [],
      })
      return
    }

    // ── error event ──────────────────────────────────────────────────────
    if (ev.type === 'error') {
      const nodes = { ...state.nodes }
      // Mark whichever node was last 'running' or last touched as failed.
      const lastTouched = [...NODE_NAMES].reverse().find((n) => nodes[n] !== 'idle')
      if (lastTouched) nodes[lastTouched] = 'failed'
      set({ nodes, events, status: 'failed' })
      return
    }

    // ── done event ──────────────────────────────────────────────────────
    if (ev.type === 'done') {
      const finalStatus = (ev.data.status as RunStatus) || 'done'
      set({
        events,
        status: finalStatus,
        degraded: state.degraded || finalStatus === 'degraded',
      })
      return
    }

    // ── node + trace events (live or replay) ─────────────────────────────
    // CQ1: normalize trace event into node event shape so both walk the same
    // reducer path; reducer only cares about (node, evidence delta, qc fields).
    const nodeName = ev.data.node
    const summary = ev.type === 'node' ? ev.data.summary : null

    // finalize is a backend-internal node — surface its status, don't paint
    // a 5th DAG node (spec §11.4: 严格 4 节点).
    if (nodeName === 'finalize') {
      if (summary?.status) {
        const finalStatus = summary.status as RunStatus
        set({
          events,
          status: finalStatus,
          qcVerdict: (summary.verdict as QCVerdict) ?? state.qcVerdict,
          degraded: state.degraded || finalStatus === 'degraded',
        })
      } else {
        set({ events })
      }
      return
    }

    if (!isKnownNode(nodeName)) {
      // Unknown future node — preserve event for ObservabilityPanel, no node update.
      set({ events })
      return
    }

    const nodes = { ...state.nodes }
    let { retryCount, qcVerdict, qcIssueCount, qcIssueTypes, evidenceCountSnapshots, degraded } =
      state

    // ── per-node side effects (only for live `node` event; trace lacks them) ──
    if (summary) {
      if (nodeName === 'collect' && typeof summary.evidence_added === 'number') {
        const lastCount = evidenceCountSnapshots.at(-1)?.count ?? 0
        evidenceCountSnapshots = [
          ...evidenceCountSnapshots,
          { ts: ev.data.ts, count: lastCount + summary.evidence_added },
        ]
      }
      if (nodeName === 'qc') {
        if (summary.verdict) qcVerdict = summary.verdict
        if (typeof summary.issues === 'number') qcIssueCount = summary.issues
        if (summary.issue_types) qcIssueTypes = summary.issue_types
        if (typeof summary.retry_count === 'number') retryCount = summary.retry_count
        if (summary.degraded === true) degraded = true

        // Verdict-driven node painting: retry_collect → mark collect retrying;
        // retry_analyze → mark analyze retrying. The next collect/analyze event
        // will flip it back to 'done'.
        if (summary.verdict === 'retry_collect') nodes.collect = 'retrying'
        if (summary.verdict === 'retry_analyze') nodes.analyze = 'retrying'
        if (summary.verdict === 'insufficient_evidence') degraded = true
      }
    }

    // Node arrival ⇒ node is done. (Running animation is a UI concern
    // handled by Task 6 DAG canvas based on event ordering.)
    nodes[nodeName] = 'done'

    set({
      events,
      nodes,
      retryCount,
      qcVerdict,
      qcIssueCount,
      qcIssueTypes,
      evidenceCountSnapshots,
      degraded,
    })
  },

  reset: () =>
    set({
      runId: null,
      status: 'idle',
      nodes: initialNodes(),
      events: [],
      degraded: false,
      retryCount: 0,
      qcVerdict: null,
      qcIssueCount: 0,
      qcIssueTypes: {},
      evidenceCountSnapshots: [],
    }),
}))
