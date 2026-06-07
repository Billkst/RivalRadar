/**
 * AgentRoster — 2×2 工牌网格(2e §4,Plan C Task 13)。
 *
 * 每工牌当前任务取 perAgentNarrative[agent_id] 最后一条 progress 摘要。
 * selector 返 raw(perAgentNarrative),窄化在 render body。
 */
import { ROLE_ORDER } from '@/lib/agentRoles'
import { AgentBadge } from '@/components/workbench/AgentBadge'
import { useRunStore } from '@/stores/runStore'

export function AgentRoster() {
  const narrative = useRunStore((s) => s.perAgentNarrative) // agent_id → 进度摘要[]
  return (
    <div className="grid grid-cols-2 gap-[9px] mb-1.5">
      {ROLE_ORDER.map((id) => {
        const lines = narrative[id]
        const task = lines && lines.length ? lines[lines.length - 1] : undefined
        return <AgentBadge key={id} id={id} currentTask={task} />
      })}
    </div>
  )
}
