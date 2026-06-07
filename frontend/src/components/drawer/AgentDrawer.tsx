/**
 * AgentDrawer — agent 详情 + 技能管理（Plan C Epic 6 Task 21 / DESIGN.md v5 agent 人格层）。
 *
 * 大头像(身份色描边)+ 角色名 + 工号/职能 + 当前/最近任务 + 技能管理(卡片 toggle/delete
 * + 市场 install)。诚实标注「行为接入下一期」(spec §6.3,不假装已生效)。
 * 头部 back/close 均 ≥44px 触摸目标(a11y)。
 */
import type { CSSProperties } from 'react'
import type { AgentId } from '@/types/agents'
import { ROLES } from '@/lib/agentRoles'
import { avatarSrc, onAvatarError } from '@/lib/avatar'
import { useSkillsStore } from '@/stores/skillsStore'
import { SkillCard } from '@/components/drawer/SkillCard'
import { SkillMarket } from '@/components/drawer/SkillMarket'

export function AgentDrawer({
  role,
  hasBack,
  onBack,
  onClose,
}: {
  role: AgentId
  hasBack: boolean
  onBack: () => void
  onClose: () => void
}) {
  const r = ROLES[role]
  const installed = useSkillsStore((s) => s.installed[role])
  const state = useSkillsStore((s) => s.state)
  const toggle = useSkillsStore((s) => s.toggle)
  const remove = useSkillsStore((s) => s.remove)
  const note = useSkillsStore((s) => s.behaviorNote)
  const onCount = installed.filter((s) => state[s.id]?.enabled).length

  return (
    <>
      <div
        className="flex items-start gap-[13px] border-b border-border px-5 pb-[15px] pt-[18px]"
        style={
          {
            '--agc': r.col,
            '--agc-line': r.line,
            '--agc-soft': r.soft,
          } as CSSProperties
        }
      >
        <div
          className="h-[52px] w-[52px] flex-none overflow-hidden rounded-[11px] border-[1.5px]"
          style={{ borderColor: r.line, background: r.soft }}
        >
          <img
            src={avatarSrc(role)}
            alt=""
            onError={onAvatarError}
            className="h-full w-full object-cover"
          />
        </div>
        <div className="flex-1">
          <div className="text-[18px] font-bold text-ink" tabIndex={-1}>
            {r.name}
          </div>
          <div className="mt-[3px] flex items-center gap-[7px] font-mono text-[11px] text-text-muted">
            <span>{r.no}</span>
            <span>·</span>
            <span className="font-semibold" style={{ color: r.col }}>
              {r.fn}
            </span>
          </div>
        </div>
        <div className="ml-auto flex flex-none items-center gap-[7px]">
          {hasBack && (
            <button
              onClick={onBack}
              aria-label="返回上一层"
              className="h-11 rounded-md border border-border-strong bg-surface px-[11px] font-mono text-[12px] font-semibold text-text-primary hover:border-accent hover:text-accent"
            >
              返回
            </button>
          )}
          <button
            onClick={onClose}
            aria-label="关闭"
            className="flex h-11 w-11 items-center justify-center rounded-md border border-border-strong bg-surface text-text-muted hover:border-v-uns hover:text-v-uns"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 pb-7 pt-[18px]">
        <div className="rounded-lg border border-border bg-surface-subtle px-[13px] py-[10px]">
          <div className="font-mono text-[10px] uppercase tracking-[.4px] text-text-muted">
            当前 / 最近任务
          </div>
          <div className="mt-1 text-[13px] text-text-primary">{r.fn}</div>
        </div>

        <div className="mb-2 mt-4 flex items-center gap-2">
          <span className="text-[13px] font-semibold text-text-primary">技能管理</span>
          <span className="font-mono text-[10px] text-text-muted">
            {onCount} 启用 / {installed.length} 已装
          </span>
        </div>
        <div className="mb-3 rounded-md border border-dashed border-border px-2.5 py-1.5 text-[11px] italic text-text-muted">
          {note}
        </div>

        <SkillMarket role={role} />

        <div className="mt-3">
          {installed.map((def) => (
            <SkillCard
              key={def.id}
              def={def}
              enabled={state[def.id]?.enabled ?? true}
              version={state[def.id]?.version ?? 'v1'}
              onToggle={() => toggle(role, def.id)}
              onDelete={() => remove(role, def.id)}
            />
          ))}
        </div>
      </div>
    </>
  )
}
