/**
 * ViewSwitcher — office / DAG view 切换 tab(plan v3.2 §6 + P0-3 双视图叙事)。
 *
 * 设计要点(DESIGN.md §Layout):
 *   - 双 button + active state(无 router state,父组件持 view state)
 *   - active = bg-accent-soft + text-accent;inactive = text-muted + hover bg-subtle
 *   - 受控 component:value + onChange,跨 view 切换不丢 store state
 *   - a11y:role="tablist" / button role="tab" / aria-selected
 *   - Keyboard:Tab 顺序内 ← / → 切换(D18 a11y baseline,未实装,先 button 默认)
 */
export type OfficeView = 'office' | 'dag'

interface ViewSwitcherProps {
  value: OfficeView
  onChange: (v: OfficeView) => void
}

export function ViewSwitcher({ value, onChange }: ViewSwitcherProps) {
  return (
    <div
      role="tablist"
      aria-label="主视图切换"
      className="inline-flex items-center gap-1 rounded-md border border-border bg-surface p-0.5"
    >
      <TabButton
        active={value === 'office'}
        onClick={() => onChange('office')}
        label="🏢 实时画面"
        ariaLabel="实时画面 — 看 4 个 agent 正在做什么"
        title="看 4 个 agent 正在做什么"
      />
      <TabButton
        active={value === 'dag'}
        onClick={() => onChange('dag')}
        label="📊 流程详情"
        ariaLabel="流程详情 — agent 协作流程 + 节点输入输出 + 质检报告"
        title="查看 agent 协作流程 + 节点输入输出 + 质检详情"
      />
    </div>
  )
}

function TabButton({
  active,
  onClick,
  label,
  ariaLabel,
  title,
}: {
  active: boolean
  onClick: () => void
  label: string
  ariaLabel: string
  title?: string
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-label={ariaLabel}
      title={title}
      onClick={onClick}
      className={
        active
          ? 'rounded px-3 py-1 text-xs font-medium bg-accent-soft text-accent'
          : 'rounded px-3 py-1 text-xs text-text-muted hover:bg-surface-subtle'
      }
    >
      {label}
    </button>
  )
}
