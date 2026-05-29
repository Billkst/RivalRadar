/**
 * EvidenceTimeline — 证据时间线(DESIGN.md / plan §4.6,最低优先级)。
 *
 * 从 evidence-list 按 fetched_at 倒序;点条目 → 证据原文 slide-over。默认折叠不抢首屏。
 * stale(>90 天)灰角标。
 */
import { useEvidenceViewer } from '@/stores/evidenceViewerStore'
import { ageDays, isStale } from '@/lib/freshness'
import { SectionTitle, PanelSkeleton, EmptyNote } from '@/components/cockpit/parts'
import type { LoadState } from '@/stores/cockpitStore'
import type { Evidence } from '@/types/api'

export function EvidenceTimeline({ evidence, state }: { evidence: Evidence[] | null; state: LoadState }) {
  const open = useEvidenceViewer((s) => s.open)

  if (state === 'loading' || state === 'idle') {
    return (
      <section className="space-y-2" aria-label="证据时间线">
        <SectionTitle>证据来自哪里</SectionTitle>
        <PanelSkeleton hint="正在汇总证据来源…" />
      </section>
    )
  }
  if (!evidence || evidence.length === 0) {
    return (
      <section className="space-y-2" aria-label="证据时间线">
        <SectionTitle>证据来自哪里</SectionTitle>
        <EmptyNote>{state === 'absent' ? '本轮无证据记录。' : '证据列表加载失败。'}</EmptyNote>
      </section>
    )
  }

  const sorted = [...evidence].sort((a, b) => b.fetched_at.localeCompare(a.fetched_at))

  return (
    <section className="space-y-2" aria-label="证据时间线">
      <SectionTitle>证据来自哪里</SectionTitle>
      <details className="group rounded-lg border border-border bg-surface p-4">
        <summary className="cursor-pointer list-none text-[13px] text-text-primary">
          <span className="mr-1 inline-block transition-transform group-open:rotate-90">▸</span>
          共 {sorted.length} 条证据(按采集时间倒序,点击展开)
        </summary>
        <ul className="mt-3 space-y-1">
          {sorted.map((ev) => {
            const stale = isStale(ev.fetched_at)
            return (
              <li key={ev.id}>
                <button
                  type="button"
                  onClick={() => open(ev.id)}
                  className="flex w-full items-baseline gap-2 rounded px-1 py-1 text-left hover:bg-surface-subtle"
                >
                  <span className="font-mono text-[11px] text-text-muted">{ev.fetched_at.slice(0, 10)}</span>
                  <span className="rounded bg-surface-subtle px-1 text-[10px] text-text-muted">{ev.competitor}</span>
                  <span className="flex-1 truncate text-[12px] text-text-primary">{ev.source_title}</span>
                  {stale ? (
                    <span className="text-[10px] text-evidence-stale" title="证据可能过期">
                      {ageDays(ev.fetched_at)}天前
                    </span>
                  ) : null}
                </button>
              </li>
            )
          })}
        </ul>
      </details>
    </section>
  )
}
