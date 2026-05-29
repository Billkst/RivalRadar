/**
 * CompetitorComparison — 对比矩阵(DESIGN.md §对比矩阵 / plan §4.2)。
 *
 * 行=维度、列=竞品;header sticky-top + 首列 sticky-left;竞品 >3 矩阵内横滚。
 * **单元格四态**:有据三色(support_verdict)/ 查无此项(斜体灰"未找到公开数据")/
 * 采集失败("—")/ stale(灰角标)。证据徽章固定挂格底。
 *
 * **因果桥**(DESIGN §对比矩阵 #110):选中决策 → 其 evidence_refs 的 id 集合传入,
 * 命中(cell.evidence_refs ∩ highlightIds 非空)的格子高亮,其余淡化。
 */
import { dimensionLabel } from '@/lib/dimensions'
import { useEvidence } from '@/stores/evidenceStore'
import { isStale } from '@/lib/freshness'
import { SectionTitle, PanelSkeleton, EmptyNote, ErrorNote } from '@/components/cockpit/parts'
import { VerdictDot } from '@/components/cockpit/VerdictDot'
import type { LoadState } from '@/stores/cockpitStore'
import type { CompetitorAnalysis, ComparisonCell, EvidenceRef, SupportVerdict } from '@/types/api'

const SEVERITY: Record<SupportVerdict, number> = { unsupported: 2, partial: 1, supported: 0 }

function worstVerdict(refs: EvidenceRef[]): SupportVerdict | null {
  if (refs.length === 0) return null
  let w: SupportVerdict = 'supported'
  for (const r of refs) if (SEVERITY[r.support_verdict] > SEVERITY[w]) w = r.support_verdict
  return w
}

/** 列顺序:优先 analysis.competitors,空则从 comparison cells 并集推导。 */
function competitorOrder(analysis: CompetitorAnalysis): string[] {
  if (analysis.competitors.length > 0) return analysis.competitors.map((c) => c.name)
  const seen: string[] = []
  for (const row of analysis.comparison) {
    for (const cell of row.cells) if (!seen.includes(cell.competitor)) seen.push(cell.competitor)
  }
  return seen
}

function Cell({ cell, matched, dimmed }: { cell: ComparisonCell | null; matched: boolean; dimmed: boolean }) {
  const firstRef = cell?.evidence_refs[0]
  const ev = useEvidence(firstRef?.evidence_id)
  const stale = ev ? isStale(ev.fetched_at) : false
  const verdict = cell ? worstVerdict(cell.evidence_refs) : null

  // 查无此项:没有该竞品的格子
  if (!cell) {
    return (
      <td className="border border-border px-2 py-2 align-top text-[12px] italic text-text-muted">
        未找到公开数据
      </td>
    )
  }
  // 采集失败:格子在但无值
  const empty = !cell.value || cell.value.trim() === '' || cell.value.trim() === '—'

  return (
    <td
      className={`border px-2 py-2 align-top transition-colors ${
        matched ? 'border-accent bg-accent-soft' : 'border-border'
      } ${dimmed ? 'opacity-45' : ''}`}
    >
      {empty ? (
        <span className="text-[13px] text-text-muted">—</span>
      ) : (
        <span
          className="block overflow-hidden text-[13px] leading-snug text-text-primary"
          style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}
          title={cell.value}
        >
          {cell.value}
        </span>
      )}
      {verdict ? (
        <div className="mt-1.5 flex items-center gap-1">
          <VerdictDot verdict={verdict} />
          {stale ? <span className="text-[10px] text-evidence-stale" title="证据可能过期">· 旧</span> : null}
        </div>
      ) : null}
    </td>
  )
}

export function CompetitorComparison({
  analysis,
  state,
  highlightIds,
  evidenceCount,
}: {
  analysis: CompetitorAnalysis | null
  state: LoadState
  highlightIds: Set<string>
  evidenceCount: number
}) {
  if (state === 'loading' || state === 'idle') {
    return (
      <section className="space-y-2" aria-label="对比矩阵">
        <SectionTitle>竞品怎么比</SectionTitle>
        <PanelSkeleton
          hint={
            evidenceCount > 0
              ? `分析员正在比较证据(已采集 ${evidenceCount} 条)…`
              : '分析员正在比较竞品…'
          }
        />
      </section>
    )
  }
  if (state === 'error') {
    return (
      <section className="space-y-2" aria-label="对比矩阵">
        <SectionTitle>竞品怎么比</SectionTitle>
        <ErrorNote>对比矩阵加载失败(网络或服务异常)。</ErrorNote>
      </section>
    )
  }
  if (!analysis || analysis.comparison.length === 0) {
    return (
      <section className="space-y-2" aria-label="对比矩阵">
        <SectionTitle>竞品怎么比</SectionTitle>
        <EmptyNote>本轮未产出可对比的维度数据。</EmptyNote>
      </section>
    )
  }

  const competitors = competitorOrder(analysis)
  const hlActive = highlightIds.size > 0

  return (
    <section className="space-y-2" aria-label="对比矩阵">
      <SectionTitle>竞品怎么比</SectionTitle>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-left tabular-nums">
          <thead>
            <tr>
              <th className="sticky left-0 top-0 z-20 border-b border-r border-border bg-surface-subtle px-2 py-2 text-[12px] font-medium text-text-muted">
                维度
              </th>
              {competitors.map((c) => (
                <th
                  key={c}
                  className="sticky top-0 z-10 min-w-[140px] border-b border-border bg-surface-subtle px-2 py-2 text-[13px] font-semibold text-text-primary"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {analysis.comparison.map((row) => {
              // 行命中:本行任一 cell 证据与高亮集合相交
              const rowMatched =
                hlActive &&
                row.cells.some((cell) => cell.evidence_refs.some((r) => highlightIds.has(r.evidence_id)))
              return (
                <tr key={row.dimension}>
                  <th
                    className={`sticky left-0 z-10 border-b border-r border-border bg-surface px-2 py-2 text-left text-[13px] font-medium ${
                      rowMatched ? 'text-accent' : 'text-text-primary'
                    } ${hlActive && !rowMatched ? 'opacity-45' : ''}`}
                  >
                    {dimensionLabel(row.dimension)}
                  </th>
                  {competitors.map((comp) => {
                    const cell = row.cells.find((c) => c.competitor === comp) ?? null
                    const matched =
                      hlActive && !!cell && cell.evidence_refs.some((r) => highlightIds.has(r.evidence_id))
                    return (
                      <Cell
                        key={comp}
                        cell={cell}
                        matched={matched}
                        dimmed={hlActive && !matched}
                      />
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {hlActive ? (
        <p className="text-[11px] text-accent">已高亮选中决策的依据所在行列(再点一次决策的高亮按钮取消)。</p>
      ) : null}
    </section>
  )
}
