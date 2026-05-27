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
        label="🏢 办公室"
        ariaLabel="虚拟办公室视图"
      />
      <TabButton
        active={value === 'dag'}
        onClick={() => onChange('dag')}
        label="🔗 流程图"
        ariaLabel="DAG 流程图详情视图"
      />
    </div>
  )
}

function TabButton({
  active,
  onClick,
  label,
  ariaLabel,
}: {
  active: boolean
  onClick: () => void
  label: string
  ariaLabel: string
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-label={ariaLabel}
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
