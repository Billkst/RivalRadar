/**
 * SelfAuditTrace — 审计轨迹(DESIGN.md §SelfAuditTrace / plan §4.5)。
 *
 * 从 /trace 取节点序列(采集 +N → 质检 verdict → 打回 → 再采集…),折叠成"查看工作"。
 * "shows its work" paradigm signal:每步技术轨迹诚实可查,默认折叠不抢决策流首屏。
 */
import { SectionTitle, PanelSkeleton, EmptyNote } from '@/components/cockpit/parts'
import type { LoadState } from '@/stores/cockpitStore'
import type { TraceEntry } from '@/types/api'

const NODE_LABEL: Record<string, string> = {
  collect: '采集',
  analyze: '分析',
  write: '撰写',
  qc: '质检',
  decide: '决策',
  finalize: '终结',
}

export function SelfAuditTrace({ trace, state }: { trace: TraceEntry[] | null; state: LoadState }) {
  if (state === 'loading' || state === 'idle') {
    return (
      <section className="space-y-2" aria-label="审计轨迹">
        <SectionTitle>查看工作(审计轨迹)</SectionTitle>
        <PanelSkeleton hint="正在记录分析步骤…" />
      </section>
    )
  }
  if (!trace || trace.length === 0) {
    return (
      <section className="space-y-2" aria-label="审计轨迹">
        <SectionTitle>查看工作(审计轨迹)</SectionTitle>
        <EmptyNote>{state === 'absent' ? '本轮无审计记录。' : '审计轨迹加载失败。'}</EmptyNote>
      </section>
    )
  }

  const retries = trace.filter((t) => t.node === 'collect').length - 1

  return (
    <section className="space-y-2" aria-label="审计轨迹">
      <SectionTitle>查看工作(审计轨迹)</SectionTitle>
      <details className="group rounded-lg border border-border bg-surface p-4">
        <summary className="cursor-pointer list-none text-[13px] text-text-primary">
          <span className="mr-1 inline-block transition-transform group-open:rotate-90">▸</span>
          {trace.length} 步 · {retries > 0 ? `自我纠错 ${retries} 次` : '一次通过'}(点击展开每步轨迹)
        </summary>
        <ol className="mt-3 space-y-1.5 border-l border-border pl-3">
          {trace.map((t) => (
            <li key={t.id} className="text-[12px]">
              <span className="font-mono text-text-muted">{t.ts.slice(11, 19)}</span>{' '}
              <span className="font-medium text-text-primary">{NODE_LABEL[t.node] ?? t.node}</span>{' '}
              <span className="text-text-muted">{t.output_summary}</span>
              {t.latency_ms > 0 ? (
                <span className="ml-1 font-mono text-[10px] text-text-muted">
                  {(t.latency_ms / 1000).toFixed(1)}s
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      </details>
    </section>
  )
}
