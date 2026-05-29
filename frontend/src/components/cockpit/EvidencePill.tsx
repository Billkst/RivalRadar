/**
 * EvidencePill — claim 级行内引用 `[n]`(DESIGN.md §EvidencePill)。
 *
 * mono 小号 + 青绿描边;hover/focus popover → quote / source_title / fetched_at /
 * support_verdict 圆点;点击 → 证据原文 slide-over。**无 provider / confidence**。
 * 来源/日期从已 seed 的 evidenceStore cache 读(useEvidence,无 N+1 冷取)。
 */
import { useEvidenceViewer } from '@/stores/evidenceViewerStore'
import { useEvidence } from '@/stores/evidenceStore'
import { ageDays, isStale } from '@/lib/freshness'
import { VerdictDot } from '@/components/cockpit/VerdictDot'
import type { EvidenceRef } from '@/types/api'

export function EvidencePill({ refItem, index }: { refItem: EvidenceRef; index: number }) {
  const open = useEvidenceViewer((s) => s.open)
  const ev = useEvidence(refItem.evidence_id)
  const stale = ev ? isStale(ev.fetched_at) : false

  return (
    <span className="group relative inline-block align-baseline">
      <button
        type="button"
        onClick={() => open(refItem.evidence_id)}
        className="rounded border border-accent/50 px-1 font-mono text-[10px] leading-tight text-accent hover:bg-accent-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        aria-label={`查看证据 ${index} 原文`}
      >
        [{index}]
      </button>
      {/* hover/focus popover — 只读提要,点击 pill 才进 slide-over 看全文 */}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-30 mt-1 hidden w-64 rounded-lg border border-border bg-surface p-3 text-left shadow-panel group-hover:block group-focus-within:block"
      >
        <span className="block text-[12px] leading-snug text-text-primary">
          “{refItem.quote}”
        </span>
        <span className="mt-2 flex items-center gap-2 text-[11px] text-text-muted">
          <VerdictDot verdict={refItem.support_verdict} showLabel />
        </span>
        <span className="mt-1 block truncate font-mono text-[11px] text-text-muted">
          {ev ? ev.source_title : '来源加载中…'}
        </span>
        {ev ? (
          <span className="mt-0.5 block font-mono text-[10px] text-text-muted">
            采集于 {ev.fetched_at.slice(0, 10)}
            {stale ? ` · ${ageDays(ev.fetched_at)} 天前(可能过期)` : ''}
          </span>
        ) : null}
      </span>
    </span>
  )
}
