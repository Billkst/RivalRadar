/**
 * AgentTeamRoster — 左 rail 4 agent 卡片(plan v3.2 §6 Epic 6.1 + DESIGN.md
 * §虚拟办公室 layout)。
 *
 * 每个 agent 卡显示:
 *   - 40×40 emoji 头像 + seat color 边框(persona 段含 🦉🦊🦝🐢)
 *   - 中文 role 名(收集员/分析员/撰稿员/质检员)
 *   - 1 行 persona 描述 truncate(hover 看 full title)
 *   - 状态 chip(待机/工作中/已完成/失败/重试中)— --seat-N 色背景
 *
 * 数据源:useRunStore.nodes 实时反映 4 agent 状态。idle 时整卡 opacity 0.7
 * 显得安静;running/retrying 时 border 用 seat 色突出 active。
 *
 * 未来扩展(D19 / D6):
 *   - click → office camera pan focus 对应工位(plan §6 Epic 6.1 后半)
 *   - elapsed badge "已工作 N 秒"(useElapsed 同 office character)
 */
import { useRunStore, type NodeName, type NodeState } from '@/stores/runStore'
import { AGENTS } from '@/lib/agentConstants'

const AGENT_TO_NODE: Record<string, NodeName> = {
  collector: 'collect',
  analyst: 'analyze',
  writer: 'write',
  qc: 'qc',
}

const SEAT_NUM: Record<string, number> = {
  collector: 1,
  analyst: 2,
  writer: 3,
  qc: 4,
}

const EMOJI: Record<string, string> = {
  collector: '🦉',
  analyst: '🦊',
  writer: '🦝',
  qc: '🐢',
}

const STATE_LABEL: Record<NodeState, string> = {
  idle: '待机',
  running: '工作中',
  done: '已完成',
  failed: '失败',
  retrying: '重试中',
}

export function AgentTeamRoster() {
  const nodes = useRunStore((s) => s.nodes)
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        Agent 团队
      </div>
      <ol className="space-y-2">
        {AGENTS.map((agent) => {
          const nodeName = AGENT_TO_NODE[agent.id]
          const state: NodeState = (nodes[nodeName] ?? 'idle') as NodeState
          const seatNum = SEAT_NUM[agent.id] ?? 1
          const emoji = EMOJI[agent.id] ?? '🤖'
          const isActive = state === 'running' || state === 'retrying'
          const isIdle = state === 'idle'
          return (
            <li
              key={agent.id}
              className="flex items-start gap-2 rounded-md border bg-surface p-2"
              style={{
                borderColor: isActive ? `var(--seat-${seatNum})` : 'var(--border)',
                opacity: isIdle ? 0.7 : 1,
                transition: 'opacity 200ms ease-out, border-color 200ms',
              }}
            >
              <div
                className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full text-[20px]"
                style={{
                  background: 'var(--surface-subtle)',
                  border: `1.5px solid var(--seat-${seatNum})`,
                }}
                aria-hidden
              >
                {emoji}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-semibold text-text-primary">
                  {agent.role}
                </div>
                <div
                  className="truncate text-[10px] text-text-muted"
                  title={agent.persona}
                >
                  {agent.persona}
                </div>
                <span
                  className="mt-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium"
                  style={{
                    background: isIdle
                      ? 'var(--surface-subtle)'
                      : `var(--seat-${seatNum})`,
                    color: isIdle ? 'var(--text-muted)' : 'white',
                  }}
                >
                  {STATE_LABEL[state]}
                </span>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
