/**
 * LiveFeedPanel — 实时 agent narrative scroll feed(plan v3.2 §6 + DESIGN.md office 段)。
 *
 * 数据源:runStore.events filter + map → LiveFeedItem 列表
 *   - progress event → 一行(agent 名 + 中文 narrative + ts)
 *   - node event → 一行 ✓ 完成标识(节点 done 后 anchor 视觉)
 *   - chunk event 不显示(太频繁,SpeechBubble 已展示)
 *
 * 设计要点(DESIGN.md):
 *   - agent role 4 色 chip(`--seat-N`)
 *   - 13px mono timestamp + 15px body
 *   - auto-scroll bottom + 鼠标 hover 暂停 + 按钮手动切跟随 / 暂停
 *   - 空态 "等待 agent 工作..."(plan §3 5 UI state empty 范围)
 *   - 失败态 "agent 网络异常"(plan §3 5 UI state error,留 future error event handler)
 */
import * as React from 'react'
import { useRunStore } from '@/stores/runStore'
import { AGENT_BY_ID } from '@/lib/agentConstants'
import type { AgentId } from '@/types/agents'
import type { SSEEvent } from '@/types/api'

interface LiveFeedItem {
  ts: string
  agent_id: string
  summary: string
  done?: boolean   // 是否是 node done event(✓ marker)
}

// node name 1:1 映射到 agent_id(plan §4 + agentConstants)
const NODE_TO_AGENT: Record<string, AgentId> = {
  collect: 'collector',
  analyze: 'analyst',
  write: 'writer',
  qc: 'qc',
}

function eventToFeedItem(ev: SSEEvent): LiveFeedItem | null {
  if (ev.type === 'progress') {
    return { ts: ev.data.ts, agent_id: ev.data.agent_id, summary: ev.data.summary }
  }
  if (ev.type === 'node') {
    const agentId = NODE_TO_AGENT[ev.data.node]
    if (!agentId) return null
    const agent = AGENT_BY_ID[agentId]
    return {
      ts: ev.data.ts,
      agent_id: agentId,
      summary: `${agent?.name ?? agentId} 完成 ${agent?.role ?? ''}`,
      done: true,
    }
  }
  return null
}

const SEAT_NUM: Record<string, number> = {
  collector: 1,
  analyst: 2,
  writer: 3,
  qc: 4,
}

export function LiveFeedPanel() {
  const events = useRunStore((s) => s.events)
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = React.useState(true)

  const items: LiveFeedItem[] = React.useMemo(
    () => events.map(eventToFeedItem).filter((i): i is LiveFeedItem => i !== null),
    [events],
  )

  // Auto-scroll bottom on new item if autoScroll on
  React.useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [items.length, autoScroll])

  return (
    <aside
      className="flex h-full flex-col rounded-lg border border-border bg-surface"
      role="complementary"
      aria-label="实时 agent narrative log"
    >
      <header className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-xs font-medium text-text-muted">实时反馈</span>
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
        {items.length === 0 ? (
          <div className="p-4 text-xs italic text-text-muted">等待 agent 工作...</div>
        ) : (
          <ol className="divide-y divide-border">
            {items.map((item, i) => {
              const agent = AGENT_BY_ID[item.agent_id as AgentId]
              const seatN = SEAT_NUM[item.agent_id] ?? 1
              return (
                <li key={`${item.ts}-${i}`} className="px-3 py-2">
                  <div className="flex items-baseline gap-2">
                    <span
                      className="rounded px-1.5 py-0.5 text-[10px] font-medium text-white"
                      style={{ background: `var(--seat-${seatN})` }}
                    >
                      {agent?.name ?? item.agent_id}
                    </span>
                    <time className="font-mono text-[10px] text-text-muted">
                      {item.ts.slice(11, 19)}
                    </time>
                    {item.done && (
                      <span className="text-[10px] text-success" aria-label="完成">
                        ✓
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-[13px] leading-snug text-text-primary">
                    {item.summary}
                  </p>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </aside>
  )
}
