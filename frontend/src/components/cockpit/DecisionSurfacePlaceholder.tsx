/**
 * DecisionSurfacePlaceholder — Epic 3 左决策面骨架占位。
 *
 * Epic 4 用真组件替换本占位(DecisionBoard 决策流 / CompetitorComparison 对比矩阵 /
 * EvidencePill 证据)。Epic 3 只立壳:展示决策面三段结构 + 状态感知提示,不臆造内容
 * (DESIGN.md §状态覆盖:不留空、不臆测;真正的渐进解锁 ← SSE node-done 在 Epic 5 接)。
 */
import { useRunStore } from '@/stores/runStore'

const SECTIONS = [
  { title: '下一步怎么做', hint: '决策流(做什么 / 为什么 / 哪里可能错)' },
  { title: '竞品如何比', hint: '对比矩阵(维度 × 竞品 · 三色支持度)' },
  { title: '证据来自哪里', hint: '逐条结论的证据原句 + 查看原文' },
]

function SkeletonBlock({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-[13px] font-medium text-text-muted">{title}</div>
      <div className="mt-1 text-[11px] text-text-muted">{hint}</div>
      <div className="mt-3 space-y-2" aria-hidden>
        <div className="h-3 w-3/4 rounded bg-surface-subtle" />
        <div className="h-3 w-1/2 rounded bg-surface-subtle" />
      </div>
    </div>
  )
}

export function DecisionSurfacePlaceholder() {
  const status = useRunStore((s) => s.status)
  const running = status === 'running' || status === 'idle'

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-dashed border-border bg-surface-subtle px-4 py-3 text-[13px] text-text-muted">
        {running
          ? '分析进行中 —— 决策、对比矩阵与证据将在分析完成后在此呈现。'
          : '决策面板将在此呈现（决策流 / 对比矩阵 / 证据,Epic 4 实装）。'}
      </div>
      {SECTIONS.map((s) => (
        <SkeletonBlock key={s.title} title={s.title} hint={s.hint} />
      ))}
    </div>
  )
}
