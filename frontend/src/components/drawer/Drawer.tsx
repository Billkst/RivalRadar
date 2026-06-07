/**
 * Drawer — 通用抽屉,由 drawerStore.navStack 栈顶驱动（Plan C Epic 6 Task 20）。
 *
 * 单逻辑栈 → 一个物理抽屉:按栈顶 view.type 渲染 AgentDrawer / EvidenceView / StepDrawer。
 * a11y(DESIGN.md):role="dialog" aria-modal + useFocusTrap(Esc 关 + Tab 循环) +
 * scrim 点击 fullClose + 焦点恢复(drawerStore.lastFocus,goBack/fullClose 承担)。
 * 在 CockpitLayout 最外层挂一次。
 */
import { useDrawerStore } from '@/stores/drawerStore'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { AgentDrawer } from '@/components/drawer/AgentDrawer'
import { StepDrawer } from '@/components/drawer/StepDrawer'

export function Drawer() {
  const stack = useDrawerStore((s) => s.stack)
  const goBack = useDrawerStore((s) => s.goBack)
  const fullClose = useDrawerStore((s) => s.fullClose)
  const open = stack.length > 0
  const top = open ? stack[stack.length - 1] : null
  const hasBack = stack.length > 1
  const trapRef = useFocusTrap(open, fullClose)

  return (
    <>
      <div
        onClick={fullClose}
        aria-hidden="true"
        className={`fixed inset-0 z-[60] bg-black/30 transition-opacity duration-200 ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      />
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-hidden={!open}
        className={`fixed right-0 top-0 z-[61] flex h-full w-[466px] max-w-[94vw] flex-col border-l border-border bg-surface shadow-panel transition-transform duration-300 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {top?.type === 'agent' && (
          <AgentDrawer role={top.role} hasBack={hasBack} onBack={goBack} onClose={fullClose} />
        )}
        {top?.type === 'evidence' && (
          // Task 22 替换为 <EvidenceView id={top.id} .../>(从 EvidenceSlideOver 导出)
          <div className="p-5 text-[13px] text-text-muted">证据视图(Task 22 填实)</div>
        )}
        {top?.type === 'step' && (
          <StepDrawer id={top.id} hasBack={hasBack} onBack={goBack} onClose={fullClose} />
        )}
      </div>
    </>
  )
}
