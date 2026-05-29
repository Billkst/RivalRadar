/**
 * CockpitLayout — 证据驾驶舱主壳(DESIGN.md §Layout Manus 分屏,Epic 3.1)。
 *
 * 顶 StatusBar + 分屏:左决策面(~62%)/ 右实时分析流程(~38%)。
 * 响应式(§12.3 #11):
 *   - ≥1280(xl):双栏 1.63fr / 1fr ≈ 62% / 38%,执行流定高内滚。
 *   - <1280:单栏纵堆,**决策面优先**(执行流降到下方,自然高度)。
 * 左决策面经 children slot 注入 —— Epic 3 传骨架占位,Epic 4 传 DecisionBoard/对比矩阵/证据。
 */
import * as React from 'react'
import { StatusBar, type VerdictSummary } from '@/components/cockpit/StatusBar'
import { ExecutionStream } from '@/components/cockpit/ExecutionStream'

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
  return (
    <div className="flex flex-col gap-3">
      <StatusBar
        decisionCount={decisionCount}
        riskCount={riskCount}
        verdictSummary={verdictSummary}
      />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.63fr_1fr]">
        <section aria-label="决策与证据" className="min-w-0">
          {children}
        </section>
        <div className="min-w-0 xl:h-[640px]">
          <ExecutionStream />
        </div>
      </div>
    </div>
  )
}
