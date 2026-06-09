/**
 * EvidenceView — 证据原文收据内容体(DESIGN.md §证据原文 slide-over / §状态覆盖 原文卡三态)。
 *
 * Plan C Epic 6 Task 22:收编为 navStack 抽屉的 evidence 渲染体(由 Drawer 提供定位/scrim/
 * 焦点 trap;本组件只渲内容 + 头部 back/close)。不再自带 Sheet 定位 wrapper、不再读
 * evidenceViewerStore —— 改由 drawerStore 栈顶 {type:'evidence', id} 驱动。
 *
 * 拉全文:优先读已 seed 的 evidenceStore cache;miss 时冷取兜底(evidenceStore.getEvidence)。
 * 失败必须显错误,**绝不**永久卡"证据加载中…"(silent-failure 修复)。
 *
 * 三态(§12.4):
 *   - content 缺失 → "原文已抓取但未提取到正文" + 仍给来源链接
 *   - source_url 不可达/为空 → 禁用"查看原文"标"来源链接不可用"(非死链)
 *   - stale(>90 天) → 灰角标"采集于 N 天前(可能过期)"
 */
import * as React from 'react'
import { ExternalLink } from 'lucide-react'
import { useEvidence, useEvidenceStore } from '@/stores/evidenceStore'
import { ageDays, isStale } from '@/lib/freshness'
import { formatBeijingDate } from '@/lib/time'
import type { Evidence } from '@/types/api'

export function EvidenceView({
  id,
  hasBack,
  onBack,
  onClose,
}: {
  id: string
  hasBack: boolean
  onBack: () => void
  onClose: () => void
}) {
  const cached = useEvidence(id)
  const [fetched, setFetched] = React.useState<Evidence | null>(null)
  const [failed, setFailed] = React.useState(false)

  // cache miss(理论上 seed 后不该发生,但 LRU 溢出 / seed race 可能)→ 冷取兜底。
  React.useEffect(() => {
    if (id && !cached) {
      let live = true
      setFailed(false)
      useEvidenceStore
        .getState()
        .getEvidence(id)
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
  }, [id, cached])

  const ev = cached ?? fetched
  const stale = ev ? isStale(ev.fetched_at) : false
  const hasSource = !!ev?.source_url

  return (
    <>
      <div className="flex items-start gap-[13px] border-b border-border px-5 pb-[15px] pt-[18px]">
        <div className="flex-1">
          <div className="text-[16px] font-bold text-ink" tabIndex={-1}>
            证据原文
          </div>
          {ev ? (
            <div className="mt-[5px] flex flex-wrap items-center gap-2 text-[12px] text-text-muted">
              <span className="rounded bg-surface-subtle px-1.5 py-0.5">{ev.competitor}</span>
              <span className="rounded bg-surface-subtle px-1.5 py-0.5">{ev.dimension}</span>
              <span className="font-mono">
                采集于 {formatBeijingDate(ev.fetched_at)}
                {stale ? (
                  <span className="ml-1 text-evidence-stale">
                    · {ageDays(ev.fetched_at)} 天前(可能过期)
                  </span>
                ) : null}
              </span>
            </div>
          ) : null}
        </div>
        <div className="ml-auto flex flex-none items-center gap-[7px]">
          {hasBack && (
            <button
              onClick={onBack}
              aria-label="返回上一层"
              className="h-11 rounded-md border border-border-strong bg-surface px-[11px] font-mono text-[12px] font-semibold text-text-primary hover:border-accent hover:text-accent"
            >
              返回
            </button>
          )}
          <button
            onClick={onClose}
            aria-label="关闭"
            className="flex h-11 w-11 items-center justify-center rounded-md border border-border-strong bg-surface text-text-muted hover:border-v-uns hover:text-v-uns"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-5 pb-7 pt-[18px]">
        {!ev ? (
          failed ? (
            <div className="text-[13px] text-error">
              证据原文加载失败,可能已被清理或服务暂时不可用。
            </div>
          ) : (
            <div className="text-[13px] italic text-text-muted">证据加载中…</div>
          )
        ) : (
          <>
            <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-border bg-surface-subtle p-3 text-[14px] leading-relaxed text-text-primary">
              {ev.content?.trim()
                ? ev.content
                : '原文已抓取但未提取到正文,请通过下方来源链接查看原始页面。'}
            </div>
            <div className="mt-auto pt-2">
              <div className="mb-1 truncate font-mono text-[12px] text-text-muted">
                {ev.source_title}
              </div>
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
      </div>
    </>
  )
}
