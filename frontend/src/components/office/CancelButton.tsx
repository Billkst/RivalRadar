/**
 * CancelButton — F4 修订:真中断 + 立即 UI 反馈。
 *
 * 设计要点(plan v3.2 §6 office 组件 + D17 5 UI state cancelled + D18 a11y):
 *   1. **UI 立即 stop-receiving 不等 backend confirm**(F4 mitigation):click 后
 *      同步调 useSSE.stop() abort SSE,UI 文案立刻切 "停止中…",backend
 *      task.cancel() 异步完成(SDK 网络层 await 可能滞后 1-2s)。
 *   2. POST /run/:id/cancel 异步,backend task.cancel() 中断 in-flight LLM。
 *   3. Esc keyboard 快捷键(D18 a11y baseline):running 时按 Esc = 等效 click。
 *   4. **本地 state 机**:isRunning(store) → cancelling(本地)→ cancelled(本地)。
 *      不依赖 runStore.status 加 'cancelled' enum—— store 扩 Epic 1.5 改造范围,
 *      本组件 self-contained 保 0.5 scope 不越界。
 *   5. 三态可视:running(红 "停止")/ cancelling(灰 "停止中…")/ cancelled
 *      (灰 disabled "已停止")/ 其他(返 null 让 RunSummary 处理 error/done)。
 */
import * as React from 'react'
import { X } from 'lucide-react'
import { cancelRun } from '@/lib/api'
import { useSSE } from '@/hooks/useSSE'
import { useRunStore } from '@/stores/runStore'

interface CancelButtonProps {
  runId: string
}

export function CancelButton({ runId }: CancelButtonProps) {
  const status = useRunStore((s) => s.status)
  const cancelStoreRun = useRunStore((s) => s.cancelRun)
  const sse = useSSE()
  const [cancelling, setCancelling] = React.useState(false)
  const [cancelled, setCancelled] = React.useState(false)

  // store status 'running' AND 本地 state 未在 cancel 流程中
  const canCancel = status === 'running' && !cancelling && !cancelled

  const handleCancel = React.useCallback(() => {
    if (!canCancel) return
    setCancelling(true)
    // F4 mitigation:立刻 stop SSE,UI 同步切 "停止中…"。Backend task.cancel()
    // 异步进行,SDK 网络层 await 中断可能滞后 1-2s 但不影响 UI。
    sse.stop()
    cancelRun(runId)
      .catch(() => {
        // 即使 POST 失败 UI 已 stop-receiving,user 视角 cancel 成功。
        // backend log 会记录原因(SDK 提前 close / 网络抖动)。
      })
      .finally(() => {
        // Codex review P2 fix:同步切 runStore.status='cancelled' —— sse.stop()
        // 在 server 'cancelled' event 之前 abort,store 永远卡 'running',
        // RunSummary status line / animations / reattach 全 stale 直到刷新。
        cancelStoreRun()
        // 切到 "已停止" final 状态(无论 POST 成功失败)
        setCancelling(false)
        setCancelled(true)
      })
  }, [canCancel, sse, runId, cancelStoreRun])

  // D18 a11y baseline:running 中 Esc keyboard 触发 cancel。
  React.useEffect(() => {
    if (!canCancel) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        handleCancel()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [canCancel, handleCancel])

  if (cancelled) {
    return (
      <button
        type="button"
        disabled
        aria-label="已停止"
        className="inline-flex cursor-not-allowed items-center gap-1 rounded-md border border-border bg-surface-subtle px-3 py-1.5 text-xs font-medium text-text-muted"
      >
        <X className="h-3 w-3" />
        已停止
      </button>
    )
  }

  if (cancelling) {
    return (
      <button
        type="button"
        disabled
        aria-label="停止中"
        className="inline-flex cursor-not-allowed items-center gap-1 rounded-md bg-error/60 px-3 py-1.5 text-xs font-medium text-white"
      >
        <X className="h-3 w-3 animate-pulse" />
        停止中…
      </button>
    )
  }

  if (!canCancel) return null  // idle / loading / failed / done — 由 RunSummary 处理

  return (
    <button
      type="button"
      onClick={handleCancel}
      aria-label="停止当前调研"
      title="Esc 快捷键"
      className="inline-flex items-center gap-1 rounded-md bg-error px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all hover:bg-error/90 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-error"
    >
      <X className="h-3 w-3" />
      停止
    </button>
  )
}
