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
import type { AgentId } from '@/types/agents'
import type { QCVerdict, SSEEvent } from '@/types/api'

export type NodeState = 'idle' | 'running' | 'done' | 'failed' | 'retrying'
export type NodeName = 'collect' | 'analyze' | 'write' | 'qc'

export const NODE_NAMES: readonly NodeName[] = ['collect', 'analyze', 'write', 'qc'] as const

/** 文档移交事件(招牌时刻 #3)。queue 形式让 back-to-back node events 排队播放,
 *  HandoffAnimation 处理 head,onComplete 触发 dequeue。 */
export interface HandoffEvent {
  /** React mount key — `${from}-${to}-${ts}`,确保新 handoff 强制重 mount */
  id: string
  from: AgentId
  to: AgentId
  ts: string
}

/** 节点链:collect → analyze → write → qc。qc 是终点不再 forward handoff。
 *  retry_collect / retry_analyze 走反向(qc→collector / qc→analyst),目前由 DAG
 *  tab 的招牌 #2 反向箭头承担,office 主视图只显示正向。 */
const HANDOFF_NEXT_AGENT: Record<NodeName, AgentId | null> = {
  collect: 'analyst',
  analyze: 'writer',
  write: 'qc',
  qc: null,
}

/** NodeName 1:1 AgentId 反向映射(VirtualOfficeView 用同样的 mapping)。 */
const NODE_TO_AGENT_ID: Record<NodeName, AgentId> = {
  collect: 'collector',
  analyze: 'analyst',
  write: 'writer',
  qc: 'qc',
}

/** AgentId → NodeName 正向映射(progress event 用 agent_id,nodes / nodeStartTs
 *  用 NodeName key,需要这层翻译)。和 NODE_TO_AGENT_ID 互为反向。
 *  Record<string, NodeName | undefined> 让未知 agent_id(future scenario)安全 fallback。 */
const AGENT_TO_NODE_INTERNAL: Record<string, NodeName | undefined> = {
  collector: 'collect',
  analyst: 'analyze',
  writer: 'write',
  qc: 'qc',
}

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

  // v3 招牌时刻 #3(Epic 4.5):forward handoff queue。
  // node done 时入队 → VirtualOfficeView 渲染队头 → onComplete 调 dequeueHandoff。
  handoffQueue: readonly HandoffEvent[]

  // v3 Epic 6.2:writer agent chunks 持久累积(供 ReportSheet 展示)。
  // 不被 typingStore.clear(progress event 触发)影响 —— ReportSheet 永远
  // 显示完整 writer 输出,不会因为 progress 'done' 而失去内容。
  writerReport: string

  startRun: (runId: string) => void
  handleEvent: (ev: SSEEvent) => void
  dequeueHandoff: () => void
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
  handoffQueue: [],
  writerReport: '',

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
      handoffQueue: [],
      writerReport: '',
    }),

  handleEvent: (ev) => {
    const state = get()

    // ── chunk event(v2 新增 + Epic 6.2 writer report 累积)───────────────
    // chunk 频率 ~30-50/s,存 events[] 会爆 array → forward typingStore 即可,
    // typingStore 内部 throttle window 50 + 16ms batch setState 防 re-render storm。
    // Writer chunks 额外持久化累积到 writerReport(Epic 6.2 新字段)供 ReportSheet
    // 显示。不走 typingStore 是因为 typingStore 在 progress event 时被 clear
    // (D19 #4 fix 让 done summary 能显示),而 ReportSheet 需要完整 writer 输出
    // 不被任何 progress event 清。
    if (ev.type === 'chunk') {
      useTypingStore.getState().appendChunk(ev.data.agent_id, ev.data.delta)
      if (ev.data.agent_id === 'writer') {
        set((s) => ({ writerReport: s.writerReport + ev.data.delta }))
      }
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
        // Epic 4.5 漏了 handoffQueue reset(start event handler 与 startRun
        // 是两套 reset 路径,startRun 在 SSE 连前调,start event 在第一个 SSE
        // 包到达时调 — 都该清 queue 防 stale state)。同时加 writerReport reset。
        handoffQueue: [],
        writerReport: '',
      })
      return
    }

    // ── progress event(v2 新增 + D19 #3 state-machine fix)──────────────
    // 节点内 step-level 进度("正在搜索 Notion pricing")。3 件事:
    //   1. push perAgentNarrative 给 LiveFeedPanel / SpeechBubble
    //   2. 第一次到达 → 记 nodeStartTs(用于 useElapsed "已工作 N 秒")
    //   3. **触发 'running' state transition** —— D19 #3 fix:之前 nodes 只在
    //      idle/done 两态切换跳过 'running' 中间态,导致 SpeechBubble visible
    //      条件 `state !== 'idle'` 在 progress 时不触发,user 看到的是 "突然
    //      冒完成总结" 而非 "开始 → 进展 → 完成"。retry_collect 把 collect
    //      切 'retrying' 后,新 collect progress 来时同样切回 'running'。
    //   修订:用 AGENT_TO_NODE_INTERNAL 翻译 agent_id → NodeName,nodeStartTs
    //   也用 NodeName 做 key(之前 isKnownNode('collector')=false silent bug
    //   让 nodeStartTs 从来没赋值过 → useElapsed 形同虚设)。
    if (ev.type === 'progress') {
      const agentId = ev.data.agent_id
      const perAgentNarrative = {
        ...state.perAgentNarrative,
        [agentId]: [...(state.perAgentNarrative[agentId] || []), ev.data.summary],
      }
      const nodeName = AGENT_TO_NODE_INTERNAL[agentId]
      const nodeStartTs = { ...state.nodeStartTs }
      const nodes = { ...state.nodes }
      if (nodeName) {
        if (nodeStartTs[nodeName] === undefined) {
          nodeStartTs[nodeName] = ev.data.ts
        }
        if (nodes[nodeName] === 'idle' || nodes[nodeName] === 'retrying') {
          nodes[nodeName] = 'running'
        }
      }
      // D19 spike fix:清空 typing buffer 让 progress summary 显示。
      // SpeechBubble `text = typingText || lastNarrative` typing 优先,
      // 不清的话 chunks 累积后会永久覆盖后续 progress (特别是 done summary)。
      // 清空策略:每个 progress event(thinking/search/drafting/validate/done)
      // 都重置 typing,让 chunks 成为 "两个 progress event 之间的临时显示",
      // progress summary 是 "持久 anchor"。
      useTypingStore.getState().clear(agentId)
      set({ events, perAgentNarrative, nodeStartTs, nodes })
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

    // v3 招牌时刻 #3(Epic 4.5)— node 完成 → 推 handoff 给下一个 agent。retry 完成
    // 也再次入队(qc→collect 再到 collect→analyst 是真业务流,handoff 应该重播)。
    let handoffQueue = state.handoffQueue
    const nextAgentId = HANDOFF_NEXT_AGENT[nodeName]
    if (nextAgentId) {
      const sourceAgentId = NODE_TO_AGENT_ID[nodeName]
      handoffQueue = [
        ...state.handoffQueue,
        {
          id: `${sourceAgentId}-${nextAgentId}-${ev.data.ts}`,
          from: sourceAgentId,
          to: nextAgentId,
          ts: ev.data.ts,
        },
      ]
    }

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
      handoffQueue,
    })
  },

  dequeueHandoff: () =>
    set((state) => ({ handoffQueue: state.handoffQueue.slice(1) })),

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
      handoffQueue: [],
      writerReport: '',
    }),
}))
