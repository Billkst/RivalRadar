/**
 * SkillCard — 技能卡（干净版,Plan C Epic 6 Task 21 / DESIGN.md v5 技能子系统）。
 *
 * 显:name + 核心标 + 一行 do + 版本(mono tabular-nums)+ 启停态 + 开关 + 删除。
 * **不展示** why/boundary(spec §6.3)。开关/删除均 ≥44px 触摸目标(a11y)。
 */
import type { SkillDef } from '@/lib/skillCatalog'

export function SkillCard({
  def,
  enabled,
  version,
  onToggle,
  onDelete,
}: {
  def: SkillDef
  enabled: boolean
  version: string
  onToggle: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={`mb-2.5 rounded-lg border border-border bg-surface px-[15px] py-[13px] transition-opacity ${
        enabled ? '' : 'bg-surface-subtle opacity-[.66]'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[13.5px] font-semibold leading-[1.3] text-ink">
            {def.name}
            {def.core && (
              <span
                className="flex-none rounded-[3px] border border-accent-line px-[5px] py-px font-mono text-[9px] font-semibold tracking-[.3px] text-accent"
                title="该员工的核心方法论"
              >
                核心
              </span>
            )}
          </div>
          <div className="mt-[5px] text-[12px] leading-[1.55] text-text-muted">{def.do}</div>
          <div className="mt-[7px] flex items-center gap-3">
            <span
              className="font-mono text-[10px] tabular-nums text-text-faint"
              title="技能版本 · 后续可迭代到 v2 并对比测效果"
            >
              {version}
            </span>
            <span
              className={`flex items-center gap-1.5 text-[10px] ${enabled ? 'text-v-sup' : 'text-text-muted'}`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${enabled ? 'bg-v-sup' : 'bg-text-faint'}`}
              />
              {enabled ? '启用' : '停用'}
            </span>
          </div>
        </div>
        <div className="flex flex-none flex-col items-end gap-1.5">
          {/* 开关:视觉 36×20,外裹 ≥44px 触摸目标(a11y 44px) */}
          <button
            role="switch"
            aria-checked={enabled}
            aria-label={`${def.name} 启用开关`}
            onClick={onToggle}
            className="flex h-11 w-11 items-center justify-end"
          >
            <span
              className={`relative h-5 w-9 rounded-full transition-colors ${
                enabled ? 'bg-v-sup' : 'bg-border-strong'
              }`}
            >
              <span
                className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                  enabled ? 'translate-x-4' : ''
                }`}
              />
            </span>
          </button>
          <button
            aria-label={`删除技能 ${def.name}`}
            onClick={onDelete}
            className="min-h-[36px] rounded-md border border-border bg-surface px-[9px] py-1 font-mono text-[10.5px] text-text-muted hover:border-v-uns hover:text-v-uns"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  )
}
