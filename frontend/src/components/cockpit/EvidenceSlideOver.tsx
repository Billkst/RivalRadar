/**
 * EvidenceSlideOver — 证据原文收据(DESIGN.md §证据原文 slide-over / §状态覆盖 原文卡三态)。
 *
 * 全局单例(evidenceViewerStore.openId 驱动),420–520px 右滑(sheet.tsx side=right
 * sm:max-w-md ≈ 448px)。"同时仅一条"。优先读已 seed 的 cache;miss 时冷取兜底。
 *
 * 三态(§12.4):
 *   - content 缺失 → "原文已抓取但未提取到正文" + 仍给来源链接
 *   - source_url 不可达/为空 → 禁用"查看原文"标"来源链接不可用"(非死链)
 *   - stale(>90 天) → 灰角标"采集于 N 天前(可能过期)"
 */
import * as React from 'react'
import { ExternalLink } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { useEvidenceViewer } from '@/stores/evidenceViewerStore'
import { useEvidence, useEvidenceStore } from '@/stores/evidenceStore'
import { ageDays, isStale } from '@/lib/freshness'
import type { Evidence } from '@/types/api'

export function EvidenceSlideOver() {
  const openId = useEvidenceViewer((s) => s.openId)
  const close = useEvidenceViewer((s) => s.close)
  const cached = useEvidence(openId)
  const [fetched, setFetched] = React.useState<Evidence | null>(null)
  const [failed, setFailed] = React.useState(false)

  // cache miss(理论上 seed 后不该发生,但 LRU 溢出 / seed race 可能)→ 冷取兜底。
  // 失败必须显错误,**绝不**永久卡"证据加载中…"(silent-failure 修复)。
  React.useEffect(() => {
    if (openId && !cached) {
      let live = true
      setFailed(false)
      useEvidenceStore
        .getState()
        .getEvidence(openId)
        .then((e) => {
          if (live) {
            setFetched(e)
            setFailed(false)
          }
        })
        .catch(() => {
          if (live) {
            setFetched(null)
            setFailed(true)
          }
        })
      return () => {
        live = false
      }
    }
    setFetched(null)
    setFailed(false)
    return undefined
  }, [openId, cached])

  const ev = cached ?? fetched
  const stale = ev ? isStale(ev.fetched_at) : false
  const hasSource = !!ev?.source_url

  return (
    <Sheet
      open={!!openId}
      onOpenChange={(o) => {
        if (!o) close()
      }}
    >
      <SheetContent side="right" className="flex flex-col gap-3 overflow-y-auto">
        <SheetHeader>
          <SheetTitle>证据原文</SheetTitle>
          {ev ? (
            <div className="flex flex-wrap items-center gap-2 text-[12px] text-text-muted">
              <span className="rounded bg-surface-subtle px-1.5 py-0.5">{ev.competitor}</span>
              <span className="rounded bg-surface-subtle px-1.5 py-0.5">{ev.dimension}</span>
              <span className="font-mono">
                采集于 {ev.fetched_at.slice(0, 10)}
                {stale ? (
                  <span className="ml-1 text-evidence-stale">· {ageDays(ev.fetched_at)} 天前(可能过期)</span>
                ) : null}
              </span>
            </div>
          ) : null}
        </SheetHeader>

        {!ev ? (
          failed ? (
            <div className="text-[13px] text-error">证据原文加载失败,可能已被清理或服务暂时不可用。</div>
          ) : (
            <div className="text-[13px] italic text-text-muted">证据加载中…</div>
          )
        ) : (
          <>
            <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-border bg-surface-subtle p-3 text-[14px] leading-relaxed text-text-primary">
              {ev.content?.trim() ? ev.content : '原文已抓取但未提取到正文,请通过下方来源链接查看原始页面。'}
            </div>
            <div className="mt-auto pt-2">
              <div className="mb-1 truncate font-mono text-[12px] text-text-muted">{ev.source_title}</div>
              {hasSource ? (
                <a
                  href={ev.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex items-center gap-1 text-[13px] text-accent underline underline-offset-2 hover:opacity-80"
                >
                  查看原文 <ExternalLink className="h-3 w-3" />
                </a>
              ) : (
                <span className="text-[13px] italic text-text-muted">来源链接不可用</span>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
