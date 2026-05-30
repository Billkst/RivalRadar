/**
 * 决策面共享小件(Epic 4)。utility 标题 + 三种状态占位(loading/empty/error),
 * 每面板传各自文案(DESIGN.md §状态覆盖:loading 文案 ≠ empty 文案,不留空不臆测)。
 */
import * as React from 'react'

/** utility 标题(下一步怎么做 / 为什么这么判断 / 哪里可能错 / 证据来自哪里)。 */
export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[13px] font-medium uppercase tracking-wide text-text-muted">{children}</div>
  )
}

/** 渐进 skeleton + 进度提示(非通用 spinner;hint 随 evidenceCountSnapshots 跳数由调用方传)。 */
export function PanelSkeleton({ hint }: { hint: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-[12px] text-text-muted">{hint}</div>
      <div className="mt-3 space-y-2" aria-hidden>
        <div className="h-3 w-3/4 animate-pulse rounded bg-surface-subtle" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-surface-subtle" />
      </div>
    </div>
  )
}

/** 空态 / 中断未生成:灰条 + 虚线边 + 斜体,不臆测。 */
export function EmptyNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface-subtle px-4 py-3 text-[12px] italic text-text-muted">
      {children}
    </div>
  )
}

/** 错误态(网络/5xx):区别于空态,给可读原因 + 不阻塞其它面板。 */
export function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-error/40 bg-surface px-4 py-3 text-[12px] text-error">
      {children}
    </div>
  )
}
