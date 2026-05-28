/**
 * ObservabilityPanel — DAG tab 内 raw event timeline(plan v3.2 §6 Epic 5.3 +
 * Codex #15)。
 *
 * 展示 useRunStore.events 全量原始 SSE event,工程视角辅助 debug + 评委可看
 * "调研机器到底跑了什么"。chunk events 不存 events[](太频繁),所以本面板
 * 不显示 chunks —— typing 累积内容看 SpeechBubble / ReportSheet。
 *
 * 每行字段:
 *   - ts:event 时间戳 HH:MM:SS
 *   - type:start / progress / node / trace / error / done(color-coded)
 *   - target:agent_id(progress)/ node name(node/trace)/ run_id(start/done)
 *   - summary:event-specific 关键摘要
 *   - #retry:同 node 第几次出现(0=首次,1=首次 retry,通过 retryIndexOf 计算)
 *
 * 默认 collapsed(<details closed),click summary 展开看 timeline 表。
 */
import { useRunStore, retryIndexOf, NODE_NAMES, type NodeName } from '@/stores/runStore'
import type { SSEEvent } from '@/types/api'

const TYPE_COLOR: Record<string, string> = {
  start: 'text-info',
  progress: 'text-warning',
  node: 'text-accent',
  trace: 'text-accent',
  error: 'text-error',
  done: 'text-success',
}

function eventTarget(ev: SSEEvent): string {
  if (ev.type === 'progress' || ev.type === 'chunk') return ev.data.agent_id
  if (ev.type === 'node' || ev.type === 'trace') return ev.data.node
  if (ev.type === 'start' || ev.type === 'done') return ev.data.run_id
  return '-'
}

function eventSummary(ev: SSEEvent): string {
  if (ev.type === 'progress') return ev.data.summary
  if (ev.type === 'node') {
    // NodeSummary 是 strongly-typed interface,转 Record<string, unknown> 让本
    // 函数能 generic 处理各 node 的 polymorphic 字段(evidence_added / verdict
    // / report_chars 等)。TS 要求 unknown 中转(structural type 不重叠)。
    const s = ev.data.summary as unknown as Record<string, unknown>
    if (s.verdict) {
      const parts = [`verdict=${s.verdict}`]
      if (typeof s.issues === 'number') parts.push(`issues=${s.issues}`)
      if (typeof s.retry_count === 'number') parts.push(`retry=${s.retry_count}`)
      return parts.join(' ')
    }
    if (typeof s.evidence_added === 'number') return `+${s.evidence_added} 证据`
    if (typeof s.competitors === 'number')
      return `${s.competitors} 竞品 · ${s.comparison_rows ?? '?'} 行`
    if (typeof s.report_chars === 'number') return `${s.report_chars} 字`
    if (typeof s.status === 'string') return `status=${s.status}`
    return ''
  }
  if (ev.type === 'trace') {
    const s = ev.data.summary
    return s ? JSON.stringify(s).slice(0, 80) : ''
  }
  if (ev.type === 'error') return ev.data.error ?? 'error'
  if (ev.type === 'done') return `status=${ev.data.status}`
  return ''
}

export function ObservabilityPanel() {
  const events = useRunStore((s) => s.events)
  if (events.length === 0) return null

  return (
    <details className="rounded-md border border-border bg-surface">
      <summary className="cursor-pointer select-none p-2 text-xs font-semibold text-text-muted hover:bg-surface-subtle">
        🔬 Observability · 原始事件 timeline({events.length} events,不含 chunk)
      </summary>
      <div className="max-h-[320px] overflow-y-auto border-t border-border">
        <table className="w-full text-[10px]">
          <thead className="sticky top-0 border-b border-border bg-surface-subtle">
            <tr className="text-left text-text-muted">
              <th className="w-[80px] px-2 py-1 font-medium">ts</th>
              <th className="w-[64px] px-2 py-1 font-medium">type</th>
              <th className="w-[80px] px-2 py-1 font-medium">target</th>
              <th className="px-2 py-1 font-medium">summary</th>
              <th
                className="w-[40px] px-2 py-1 text-center font-medium"
                title="同 node 第几次出现(0=首次,1=首次 retry)"
              >
                #retry
              </th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {events.map((ev, idx) => {
              const isNodeOrTrace = ev.type === 'node' || ev.type === 'trace'
              const isKnown =
                isNodeOrTrace && (NODE_NAMES as readonly string[]).includes(ev.data.node)
              const retryIdx = isKnown
                ? retryIndexOf(events, ev.data.node as NodeName, idx)
                : null
              const summary = eventSummary(ev)
              return (
                <tr
                  key={`obs-${idx}`}
                  className="border-b border-border/30 hover:bg-surface-subtle"
                >
                  <td className="px-2 py-0.5 text-text-muted">
                    {ev.data.ts ? ev.data.ts.slice(11, 19) : '-'}
                  </td>
                  <td className={`px-2 py-0.5 ${TYPE_COLOR[ev.type] ?? ''}`}>{ev.type}</td>
                  <td className="px-2 py-0.5 text-text-primary">{eventTarget(ev)}</td>
                  <td
                    className="max-w-0 truncate px-2 py-0.5 text-text-primary"
                    title={summary}
                  >
                    {summary || '-'}
                  </td>
                  <td className="px-2 py-0.5 text-center text-text-muted">
                    {retryIdx ?? '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </details>
  )
}
