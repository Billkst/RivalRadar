/**
 * ResearcherWorkbench — 研究员工作台右栏 shell(spec §6.1 2e,Epic 4 Task 12)。
 *
 * 2e §1 DOM:`.engine > .eng-hd(kicker + 状态) + .eng-body(roster + live-pane + timeline)`。
 * 本 shell 只搭区块插槽,各面板在 Epic 5 逐个填实(现为空壳返 null)。
 * collapsed(done 态)→ 收窄摘要条 WorkbenchSummary(Epic 8 Task 27 补全)。
 */
import { useState } from 'react'
import { AgentRoster } from '@/components/workbench/AgentRoster'
import { SearchStation } from '@/components/workbench/SearchStation'
import { SourceCards } from '@/components/workbench/SourceCards'
import { RetryLoop } from '@/components/workbench/RetryLoop'
import { ReportStation } from '@/components/workbench/ReportStation'
import { ExecutionTimeline } from '@/components/workbench/ExecutionTimeline'
import { useRunStore } from '@/stores/runStore'

export function ResearcherWorkbench({ collapsed }: { collapsed: boolean }) {
  const status = useRunStore((s) => s.status)
  // done 态局部展开:点「查看工作 ↗」临时切回 full workbench(不改 store / layout 宽度)。
  const [expanded, setExpanded] = useState(false)
  if (collapsed && !expanded) return <WorkbenchSummary onExpand={() => setExpanded(true)} />
  return (
    <>
      <div className="px-[18px] pt-[15px] pb-[13px] border-b border-border bg-surface">
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">研究团队 · 实时引擎</div>
        <div className="text-[13px] font-semibold text-text-primary mt-1">{statusLabel(status)}</div>
      </div>
      <div className="flex-1 overflow-y-auto px-[18px] pt-[14px] pb-7">
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mb-2">研究团队 · 持证员工</div>
        <AgentRoster />
        <SearchStation />
        <SourceCards />
        <RetryLoop />
        <ReportStation />
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mt-[18px] mb-2">执行时间轴 · 当日</div>
        <ExecutionTimeline />
      </div>
    </>
  )
}

function WorkbenchSummary({ onExpand }: { onExpand: () => void }) {
  // done 态收窄摘要条:N 步 · M 轮 · 自我纠错 K 次 + 「查看工作 ↗」(Epic 8 Task 27)。
  // selector 返 raw;计数在 render body 派生。
  const cellRows = useRunStore((s) => s.cellRows)
  const deltas = useRunStore((s) => s.evidenceDeltas)
  const retryCount = useRunStore((s) => s.retryCount)
  const steps = Object.keys(cellRows).length
  // 总轮次 = 自我纠错次数 + 1(首轮)。retryCount 是后端权威纠错计数。
  const rounds = retryCount + 1
  void deltas // 轮次以 retryCount 为权威(evidenceDeltas 仅承载补证增量,不一定逐轮齐全)
  return (
    <div className="flex h-full flex-col px-4 pt-[15px]">
      <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">研究团队 · 本轮回顾</div>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-text-primary">
        <span className="font-semibold tabular-nums">{steps} 步</span>
        <span className="text-text-faint">·</span>
        <span className="font-semibold tabular-nums">{rounds} 轮</span>
        <span className="text-text-faint">·</span>
        <span className="font-semibold tabular-nums">自我纠错 {retryCount} 次</span>
      </div>
      <button
        onClick={onExpand}
        className="mt-3 self-start font-mono text-[12px] font-semibold text-accent hover:opacity-80"
      >
        查看工作 ↗
      </button>
    </div>
  )
}

function statusLabel(s: string): string {
  return s === 'running'
    ? '调研进行中…'
    : s === 'idle'
      ? '待启动'
      : s === 'cancelled'
        ? '本轮调研已停止'
        : s === 'failed'
          ? '本轮调研中断'
          : '本轮调研完成'
}
