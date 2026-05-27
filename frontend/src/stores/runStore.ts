/**
 * runStore — 单 run 实时状态(SSE event reducer)。
 *
 * 设计要点:
 *   1. events 保留所有原始 SSE event(供 ObservabilityPanel 原始 timeline + retry index 推导)
 *      **chunk event 不存 events[]**(plan v3.2 §6:chunk 100/s,会爆 array,forward typingStore)
 *   2. NodeState = idle/running/done/failed/retrying (spec §11.4 5 状态)
 *   3. 语义:**node event 到达 = 该节点 done**(后端节点完成时 yield);
 *      "running" 中间态由 Task 6 DAG canvas 用过渡视觉呈现,store 不存
 *   4. CQ1 trace normalize:trace event 转 node event 形式后走同 reducer
 *   5. retry_index 不存字段,从 events.filter 推导(Codex #2)
 *   6. qcIssueCount/qcIssueTypes — 后端 SSE 只暴露 count + types map,不带 detail;
 *      issue text 详情等 Task 16 后端 schema 补强(plan v2 Day-4 S9)
 *
 * v2 修订(plan v3.2 §6 + Epic 1.5):
 *   7. **chunk event**:forward 给 typingStore.appendChunk(throttle 50 + 16ms batch);
 *      不存 events[](太频繁)。
 *   8. **progress event**:存 events[] + push perAgentNarrative + 第一次到达记
 *      nodeStartTs(用于 useElapsed "已工作 12s")。
 *   9. **node event**:nodes[node]='done' 时同时记 nodeEndTs(LiveFeedPanel 显示
 *      "完成于 14:32")。retry 时覆盖(只保留最后一次 done ts)。
 */
import { create } from 'zustand'
import { useTypingStore } from '@/stores/typingStore'
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

  // v2 新增(Epic 1.5):
  perAgentNarrative: Record<string, string[]>      // agent_id → progress summaries
  nodeStartTs: Partial<Record<NodeName, string>>   // node → 第一次 progress event ts
  nodeEndTs: Partial<Record<NodeName, string>>     // node → 最后一次 node event ts

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

const initialPerAgentNarrative = (): Record<string, string[]> => ({})
const initialNodeTs = (): Partial<Record<NodeName, string>> => ({})

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
  perAgentNarrative: initialPerAgentNarrative(),
  nodeStartTs: initialNodeTs(),
  nodeEndTs: initialNodeTs(),

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
      perAgentNarrative: initialPerAgentNarrative(),
      nodeStartTs: initialNodeTs(),
      nodeEndTs: initialNodeTs(),
    }),

  handleEvent: (ev) => {
    const state = get()

    // ── chunk event(v2 新增)─────────────────────────────────────────────
    // chunk 频率 ~30-50/s,存 events[] 会爆 array → forward typingStore 即可,
    // typingStore 内部 throttle window 50 + 16ms batch setState 防 re-render storm。
    if (ev.type === 'chunk') {
      useTypingStore.getState().appendChunk(ev.data.agent_id, ev.data.delta)
      return
    }

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
        perAgentNarrative: initialPerAgentNarrative(),
        nodeStartTs: initialNodeTs(),
        nodeEndTs: initialNodeTs(),
      })
      return
    }

    // ── progress event(v2 新增)──────────────────────────────────────────
    // 节点内 step-level 进度("正在搜索 Notion pricing")。累积到 events[] 给
    // ObservabilityPanel,push perAgentNarrative 给 LiveFeedPanel,第一次到达
    // 记 nodeStartTs(agent_id 1:1 NodeName,用于 useElapsed 算"已工作 N 秒")。
    if (ev.type === 'progress') {
      const agentId = ev.data.agent_id
      const perAgentNarrative = {
        ...state.perAgentNarrative,
        [agentId]: [...(state.perAgentNarrative[agentId] || []), ev.data.summary],
      }
      const nodeStartTs = { ...state.nodeStartTs }
      if (isKnownNode(agentId) && nodeStartTs[agentId] === undefined) {
        nodeStartTs[agentId] = ev.data.ts
      }
      set({ events, perAgentNarrative, nodeStartTs })
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

    // v2 新增:记 nodeEndTs(retry 时覆盖,只保最后一次 done ts —— LiveFeedPanel
    // 显示 "完成于 14:32" / DagDetailView 算节点耗时 = endTs - startTs)。
    const nodeEndTs = { ...state.nodeEndTs, [nodeName]: ev.data.ts }

    set({
      events,
      nodes,
      retryCount,
      qcVerdict,
      qcIssueCount,
      qcIssueTypes,
      evidenceCountSnapshots,
      degraded,
      nodeEndTs,
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
      perAgentNarrative: initialPerAgentNarrative(),
      nodeStartTs: initialNodeTs(),
      nodeEndTs: initialNodeTs(),
    }),
}))
