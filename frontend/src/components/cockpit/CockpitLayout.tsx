/**
 * CockpitLayout — 证据驾驶舱主壳(DESIGN.md §Layout / v5 融合主轴,Plan C Epic 4)。
 *
 * 顶 StatusBar(sticky)+ 融合主轴双栏:左决策面 / 右研究员工作台(ResearcherWorkbench)。
 * 2e 基线(spec §6.1):
 *   - running:`1fr 472px` —— 右栏满宽呈现实时调研引擎。
 *   - done(terminal):`1fr 280px` —— 右栏收窄成摘要,左决策面成焦点(DESIGN.md v5)。
 * 响应式:`<lg`(<1024)单栏纵堆,**决策面优先**(DOM 左先 → 单栏时在上)。
 * 左决策面经 children slot 注入 —— Epic 3 传骨架占位,Epic 4 传 DecisionBoard/对比矩阵/证据。
 */
import * as React from 'react'
import { StatusBar, type VerdictSummary } from '@/components/cockpit/StatusBar'
import { ResearcherWorkbench } from '@/components/workbench/ResearcherWorkbench'
import { useRunStore } from '@/stores/runStore'

interface CockpitLayoutProps {
  /** 左决策面内容(Epic 4: DecisionBoard 等;Epic 3: 骨架占位)。 */
  children: React.ReactNode
  /** StatusBar 决策派生指标(Epic 4/5 喂入;未就绪显 "—")。 */
  decisionCount?: number
  riskCount?: number
  verdictSummary?: VerdictSummary
}

export function CockpitLayout({
  children, decisionCount, riskCount, verdictSummary,
}: CockpitLayoutProps) {
  const status = useRunStore((s) => s.status)
  const terminal =
    status === 'done' ||
    status === 'degraded' ||
    status === 'insufficient_evidence' ||
    status === 'failed' ||
    status === 'cancelled'
  return (
    <div className="flex h-[100dvh] flex-col">
      <StatusBar
        decisionCount={decisionCount}
        riskCount={riskCount}
        verdictSummary={verdictSummary}
      />
      <div
        className={
          'grid min-h-0 flex-1 grid-cols-1 ' +
          (terminal ? 'lg:grid-cols-[1fr_280px]' : 'lg:grid-cols-[1fr_472px]')
        }
      >
        <main aria-label="决策与证据" className="min-w-0 overflow-y-auto bg-bg px-6 pb-14 pt-5">
          {children}
        </main>
        <aside className="relative flex min-w-0 flex-col overflow-hidden border-l border-border bg-surface-subtle">
          <ResearcherWorkbench collapsed={terminal} />
        </aside>
      </div>
    </div>
  )
}
