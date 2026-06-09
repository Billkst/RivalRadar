/**
 * ResearcherWorkbench — 研究员工作台右栏 shell(spec §6.1 2e,Epic 4 Task 12)。
 *
 * 布局(用户反馈重构):顶部 kicker + **LiveTracker「此刻」追踪卡(常驻,不滚动)** +
 * 下方滚动区(自我纠错环 + 正序执行时间轴,作历史脊梁)。把「当前在干什么」钉在顶部
 * 原地刷新 → 用户初始位置不拖动即可看到进度变化;时间轴退化为历史(来源卡折进采集行)。
 * collapsed(done 收窄态)→ 摘要条 WorkbenchSummary。
 */
import { RetryLoop } from '@/components/workbench/RetryLoop'
import { ExecutionTimeline } from '@/components/workbench/ExecutionTimeline'
import { LiveTracker } from '@/components/workbench/LiveTracker'
import { useRunStore } from '@/stores/runStore'

export function ResearcherWorkbench({
  collapsed,
  onExpand,
  totalDimensions,
}: {
  collapsed: boolean
  /** 收窄摘要态点「查看工作 ↗」→ 由 CockpitLayout 展开(同时把右列加宽)。 */
  onExpand: () => void
  /** 分析阶段「矩阵 N/total 维」进度条的分母(run.dimensions.length)。 */
  totalDimensions?: number
}) {
  if (collapsed) return <WorkbenchSummary onExpand={onExpand} />
  return (
    <>
      <div className="flex-none border-b border-border bg-surface px-[18px] pb-[10px] pt-[15px]">
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">实时引擎 · 调研过程</div>
      </div>
      {/* 「此刻」追踪卡:钉在顶部常驻,原地刷新,不随下方时间轴滚动。 */}
      <LiveTracker totalDimensions={totalDimensions} />
      {/* 历史脊梁:自我纠错环 + 正序执行时间轴。独立滚动区(内容短,通常不溢出;真正的
          「当前进度」由上方常驻 LiveTracker 承担,故此处不再需要贴底自动跟随)。 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-[18px] pb-7 pt-3">
        <RetryLoop />
        <div className="mb-1 mt-[14px] font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">执行时间轴</div>
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
