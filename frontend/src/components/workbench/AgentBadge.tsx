/**
 * AgentBadge — 单 agent 工牌(2e §4,Plan C Task 13)。
 *
 * 头像(身份色描边)+ 职能名 + 工号 + 状态灯(待命灰 / 执行身份色 / 完成绿)+ 当前任务
 * + retry 角标。状态机映射 runStore.nodes[NODE_OF_ROLE[id]](NodeName,跨 domain 映射,
 * 记忆 [[silent type-domain]])。点击 → drawerStore.openAgent。
 */
import type { AgentId } from '@/types/agents'
import type { NodeName } from '@/stores/runStore'
import { ROLES } from '@/lib/agentRoles'
import { avatarSrc, onAvatarError } from '@/lib/avatar'
import { useRunStore } from '@/stores/runStore'
import { useDrawerStore } from '@/stores/drawerStore'

// codex P1#2:类型必须 NodeName(strict 索引),不是 string。AgentId(collector…)
// 与 nodes key(collect…)是两个 domain,不可假设同名。
const NODE_OF_ROLE: Record<AgentId, NodeName> = {
  collector: 'collect',
  analyst: 'analyze',
  writer: 'write',
  qc: 'qc',
}

export function AgentBadge({ id, currentTask }: { id: AgentId; currentTask?: string }) {
  const r = ROLES[id]
  const nodeState = useRunStore((s) => s.nodes[NODE_OF_ROLE[id]]) // idle|running|done|failed|retrying
  const retryCount = useRunStore((s) => s.retryCount)
  const status = useRunStore((s) => s.status)
  const openAgent = useDrawerStore((s) => s.openAgent)
  const active = nodeState === 'running' || nodeState === 'retrying'
  const done = nodeState === 'done'
  // cancelled 终态:已完成节点保留「已完成」,未跑(idle)节点灰显「已停止」(Task 27)。
  const stopped = status === 'cancelled' && nodeState === 'idle'
  const stateText = active
    ? '执行中'
    : done
      ? '已完成'
      : nodeState === 'failed'
        ? '失败'
        : stopped
          ? '已停止'
          : '待命'
  const lampColor = done ? 'var(--v-sup)' : active ? r.col : 'var(--text-faint)'
  return (
    <button
      onClick={() => openAgent(id)}
      className="text-left border rounded-lg bg-surface p-[10px_11px_11px] relative overflow-hidden flex flex-col gap-2 transition-colors"
      style={{ borderColor: active || done ? r.col : 'var(--border)', ['--idc' as string]: r.col }}
      aria-label={`${r.name} 工牌`}
    >
      {nodeState === 'retrying' && (
        <span
          className="absolute top-2 right-[9px] font-mono text-[8.5px] font-semibold leading-none text-white rounded-[7px] px-[5px] py-[2px]"
          style={{ background: 'var(--accent)' }}
        >
          第{retryCount + 1}轮
        </span>
      )}
      <div className="flex items-center gap-[9px]">
        <div
          className="relative w-10 h-10 rounded-[9px] overflow-hidden border-[1.5px]"
          style={{ borderColor: r.line, background: r.soft }}
        >
          <img
            src={avatarSrc(id)}
            alt={`${r.name}头像`}
            loading="lazy"
            onError={onAvatarError}
            className="w-full h-full object-cover"
          />
          <span
            className="absolute -right-[3px] -bottom-[3px] w-[13px] h-[13px] rounded-full border-2 border-surface"
            style={{ background: lampColor }}
          />
        </div>
        <div>
          <div className="text-[12.5px] font-semibold text-text-primary leading-tight">{r.name}</div>
          <div className="font-mono text-[9.5px] text-text-muted tracking-[.3px] mt-px">{r.no}</div>
        </div>
      </div>
      <div
        className="text-[10.5px] leading-[1.3] min-h-[14px] overflow-hidden text-ellipsis whitespace-nowrap"
        style={{ color: active ? r.col : 'var(--text-muted)' }}
      >
        {currentTask || r.fn}
      </div>
      <div
        className="font-mono text-[9px] tracking-[.3px]"
        style={{ color: done ? 'var(--v-sup)' : active ? r.col : 'var(--text-faint)' }}
      >
        {stateText}
      </div>
    </button>
  )
}
