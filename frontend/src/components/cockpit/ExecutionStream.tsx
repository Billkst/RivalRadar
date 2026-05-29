/**
 * ExecutionStream — cockpit 右栏「实时分析流程」(DESIGN.md §实时分析流程 + §Motion,Epic 3.2)。
 *
 * Manus 风纵向时间线,消费 runStore.events(re-skin 自 office LiveFeedPanel):
 *   - 四个直白命名角色:采集员 / 分析员 / 撰写员 / 质检员(严禁花哨代号)+ decide 决策步
 *   - 每节点产出可见变化(防 agent theater):采集 +N 证据 / 分析 N 竞品 / 质检裁决 / N 条决策
 *   - **重试环拓扑(招牌时刻)**:质检打回 → 实线青绿单回环(非平铺列表),标
 *     「↺ 第N轮 · 证据 X→Y」,沿用 DAG 招牌动效时长 900ms ease-in-out 单次不循环
 *
 * 双路径:live(node/progress event,structured summary)+ replay(trace event,output 串)。
 */
import * as React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { useRunStore } from '@/stores/runStore'
import { AGENT_BY_ID } from '@/lib/agentConstants'
import type { AgentId } from '@/types/agents'
import type { SSEEvent } from '@/types/api'

const NODE_TO_AGENT: Record<string, AgentId> = {
  collect: 'collector',
  analyze: 'analyst',
  write: 'writer',
  qc: 'qc',
}
const SEAT_NUM: Record<AgentId, number> = { collector: 1, analyst: 2, writer: 3, qc: 4 }

const QC_VERDICT_ZH: Record<string, string> = {
  pass: '通过',
  retry_collect: '证据不足,打回采集',
  retry_analyze: '分析有误,打回分析',
  insufficient_evidence: '证据耗尽,标降级',
}

type Row =
  | { kind: 'step'; key: string; ts: string; agentId: AgentId; summary: string; done: boolean }
  | { kind: 'decide'; key: string; ts: string; summary: string; degraded: boolean }
  | { kind: 'retry'; key: string; ts: string; round: number; evFrom: number; evTo: number | null }

/** 把有序 SSE event 派生成时间线行 + 重试环标记(live node/progress + replay trace 双路径)。 */
function deriveRows(events: SSEEvent[]): Row[] {
  const rows: Row[] = []
  let cumulative = 0
  let round = 1
  let pendingRetry: Extract<Row, { kind: 'retry' }> | null = null

  const pushRetry = (ts: string) => {
    round += 1
    const retry: Extract<Row, { kind: 'retry' }> = {
      kind: 'retry', key: `retry-${ts}-${round}`, ts, round, evFrom: cumulative, evTo: null,
    }
    rows.push(retry)
    pendingRetry = retry
  }

  events.forEach((ev, i) => {
    if (ev.type === 'progress') {
      const aid = ev.data.agent_id
      // decide 节点 progress(backend _emit_progress(emit,"decide",…))的 agent_id 不是
      // 4 角色之一 → 路由到 decide 行样式,避免 RoleChip 拿不到 seat 色渲染崩。
      if (aid === 'decide') {
        rows.push({ kind: 'decide', key: `p${i}`, ts: ev.data.ts, summary: ev.data.summary, degraded: false })
      } else {
        rows.push({ kind: 'step', key: `p${i}`, ts: ev.data.ts, agentId: aid as AgentId,
          summary: ev.data.summary, done: false })
      }
      return
    }
    if (ev.type === 'node') {
      const node = ev.data.node
      const s = ev.data.summary
      if (node === 'collect') {
        const added = s.evidence_added ?? 0
        cumulative += added
        if (pendingRetry && pendingRetry.evTo === null) pendingRetry.evTo = cumulative
        rows.push({ kind: 'step', key: `n${i}`, ts: ev.data.ts, agentId: 'collector',
          summary: `新增 ${added} 条证据,累计 ${cumulative} 条`, done: true })
      } else if (node === 'analyze') {
        rows.push({ kind: 'step', key: `n${i}`, ts: ev.data.ts, agentId: 'analyst',
          summary: `比较 ${s.competitors ?? 0} 个竞品 · ${s.comparison_rows ?? 0} 维对比`, done: true })
      } else if (node === 'write') {
        rows.push({ kind: 'step', key: `n${i}`, ts: ev.data.ts, agentId: 'writer',
          summary: `生成报告 ${s.report_chars ?? 0} 字`, done: true })
      } else if (node === 'qc') {
        const verdict = s.verdict ?? ''
        rows.push({ kind: 'step', key: `n${i}`, ts: ev.data.ts, agentId: 'qc',
          summary: `裁决:${QC_VERDICT_ZH[verdict] ?? verdict}(${s.issues ?? 0} 项问题)`, done: true })
        if (verdict === 'retry_collect' || verdict === 'retry_analyze') pushRetry(ev.data.ts)
      } else if (node === 'decide') {
        const n = s.decisions ?? 0
        rows.push({ kind: 'decide', key: `n${i}`, ts: ev.data.ts,
          summary: `生成 ${n} 条决策建议`, degraded: s.decision_degraded === true })
      }
      return
    }
    if (ev.type === 'trace') {
      // replay 路径:trace.summary.output 是字符串,角色 = node;不解析数字,直接展示
      const node = ev.data.node
      const agentId = NODE_TO_AGENT[node]
      const out = ev.data.summary?.output ?? ''
      if (node === 'decide') {
        rows.push({ kind: 'decide', key: `t${i}`, ts: ev.data.ts, summary: out || '生成决策建议',
          degraded: out.includes('degraded=True') })
      } else if (agentId) {
        rows.push({ kind: 'step', key: `t${i}`, ts: ev.data.ts, agentId, summary: out, done: true })
        if (node === 'qc' && (out.includes('retry_collect') || out.includes('retry_analyze'))) {
          pushRetry(ev.data.ts)
        }
      }
    }
  })
  return rows
}

function RoleChip({ agentId }: { agentId: AgentId }) {
  const name = AGENT_BY_ID[agentId]?.name ?? agentId
  const seat = SEAT_NUM[agentId] ?? 1 // 未知 agent_id 安全兜底(防 var(--seat-undefined))
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[10px] font-medium text-white"
      style={{ background: `var(--seat-${seat})` }}
    >
      {name}
    </span>
  )
}

/** 重试环:实线青绿单回环 SVG 弧(向上回折,寓意"绕回采集"),pathLength 900ms 单次。 */
function RetryLoop({ round, evFrom, evTo }: { round: number; evFrom: number; evTo: number | null }) {
  const reduce = useReducedMotion()
  const ev = evTo !== null ? `证据 ${evFrom}→${evTo}` : `证据 ${evFrom}→…`
  return (
    <li className="relative py-2 pl-3">
      <div className="flex items-center gap-2">
        <svg width="28" height="40" viewBox="0 0 28 40" fill="none" aria-hidden className="shrink-0">
          {/* 从底部(质检)向上回折到顶部(采集)的单回环 */}
          <motion.path
            d="M14 38 C 2 30, 2 10, 14 4"
            stroke="var(--accent)"
            strokeWidth={2}
            strokeLinecap="round"
            fill="none"
            markerEnd="url(#es-retry-arrow)"
            initial={reduce ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.9, ease: 'easeInOut' }}
          />
          <defs>
            <marker id="es-retry-arrow" markerWidth="6" markerHeight="6" refX="3" refY="3"
                    orient="auto" markerUnits="strokeWidth">
              <path d="M0 0 L6 3 L0 6 Z" fill="var(--accent)" />
            </marker>
          </defs>
        </svg>
        <span className="rounded-md bg-accent-soft px-2 py-1 text-[11px] font-medium text-accent">
          ↺ 第{round}轮 · {ev}
        </span>
      </div>
    </li>
  )
}

export function ExecutionStream() {
  const events = useRunStore((s) => s.events)
  const status = useRunStore((s) => s.status)
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = React.useState(true)

  const rows = React.useMemo(() => deriveRows(events), [events])

  React.useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [rows.length, autoScroll])

  return (
    <aside
      className="flex h-full flex-col rounded-lg border border-border bg-surface"
      role="complementary"
      aria-label="实时分析流程"
    >
      <header className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-xs font-medium text-text-muted">实时分析流程</span>
        <button
          type="button"
          onClick={() => setAutoScroll((v) => !v)}
          className={`text-xs ${autoScroll ? 'text-accent' : 'text-text-muted'}`}
          aria-pressed={autoScroll}
        >
          {autoScroll ? '↓ 跟随' : '↑ 暂停'}
        </button>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        onMouseEnter={() => setAutoScroll(false)}
        onMouseLeave={() => setAutoScroll(true)}
      >
        {rows.length === 0 ? (
          <div className="p-4 text-xs italic text-text-muted">
            {status === 'idle' ? '等待分析开始…' : '正在连接分析流…'}
          </div>
        ) : (
          <ol className="divide-y divide-border">
            {rows.map((row) => {
              if (row.kind === 'retry') {
                return <RetryLoop key={row.key} round={row.round} evFrom={row.evFrom} evTo={row.evTo} />
              }
              if (row.kind === 'decide') {
                return (
                  <li key={row.key} className="px-3 py-2">
                    <div className="flex items-baseline gap-2">
                      <span className="rounded bg-accent px-1.5 py-0.5 text-[10px] font-medium text-white">
                        决策
                      </span>
                      <time className="font-mono text-[10px] text-text-muted">{row.ts.slice(11, 19)}</time>
                      <span className="text-[10px] text-success" aria-label="完成">✓</span>
                      {row.degraded && <span className="text-[10px] text-warning">· 降级</span>}
                    </div>
                    <p className="mt-1 text-[13px] leading-snug text-text-primary">{row.summary}</p>
                  </li>
                )
              }
              return (
                <li key={row.key} className="px-3 py-2">
                  <div className="flex items-baseline gap-2">
                    <RoleChip agentId={row.agentId} />
                    <time className="font-mono text-[10px] text-text-muted">{row.ts.slice(11, 19)}</time>
                    {row.done && <span className="text-[10px] text-success" aria-label="完成">✓</span>}
                  </div>
                  <p className="mt-1 text-[13px] leading-snug text-text-primary">{row.summary}</p>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </aside>
  )
}
