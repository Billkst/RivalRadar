/**
 * CompetitorComparison — 对比矩阵(DESIGN.md §对比矩阵 / plan §4.2 / Plan C Task 23)。
 *
 * 行=维度(请求顺序)、列=竞品;header sticky-top + 首列 sticky-left;竞品 >3 矩阵内横滚。
 *
 * **逐维生长**(spec §5.3):running 时按维度从 `runStore.cellRows` 填(乱序安全,按 dimension
 * key 落位);done 后回落 `cockpitStore.analysis.comparison`。
 *
 * **单元格四态 + 剔除**:
 *   - 有据三色(cell 级 support_verdict)/ 查无此项(斜体灰"未找到公开数据")/
 *     采集失败("分析失败"/"—")/ stale(灰角标)。
 *   - **剔除格**(`runStore.droppedCells` 含 `${dim}|${comp}`)显「—」,qc 完成即生效(不必等 done)。
 *   - **三色一律读 cell 级**:`runStore.cellVerdicts['${dim}|${comp}']`(verdict_recheck 实时)
 *     → 回落 `analysisCell.support_verdict`(REST)。**绝不读 ref 级**(反幻觉核心)。
 *
 * **因果桥**(DESIGN §对比矩阵 #146):接受 `highlightedCells: ReadonlySet<string>`(`${dim}|${comp}`),
 * 由 DecisionBoard 选中决策(其 evidence_refs ∩ cell evidence ids 求交)驱动;命中格高亮,其余淡化。
 * 每 `<td>` 暴露 `data-ev-ids`(该 cell evidence_id 列表)供因果桥契约与调试。
 */
import { dimensionLabel } from '@/lib/dimensions'
import { useEvidence } from '@/stores/evidenceStore'
import { isStale } from '@/lib/freshness'
import { SectionTitle, PanelSkeleton, EmptyNote, ErrorNote } from '@/components/cockpit/parts'
import { VerdictDot } from '@/components/cockpit/VerdictDot'
import { useRunStore } from '@/stores/runStore'
import { useCockpitStore } from '@/stores/cockpitStore'
import type { LoadState } from '@/stores/cockpitStore'
import type { SupportVerdict } from '@/types/api'

/** 归一后的格子模型(同时承接 cell_row cell 与 analysis cell)。 */
interface MatrixCell {
  competitor: string
  value: string
  evidenceIds: string[]
}

function Cell({
  cell,
  verdict,
  dropped,
  matched,
  dimmed,
  cellKey,
}: {
  cell: MatrixCell | null
  verdict: SupportVerdict | null
  dropped: boolean
  matched: boolean
  dimmed: boolean
  cellKey: string
}) {
  const firstId = cell?.evidenceIds[0]
  const ev = useEvidence(firstId)
  const stale = ev ? isStale(ev.fetched_at) : false

  // 被策展剔除:矩阵显「—」(不再永久「待裁决」,codex P2#12)。
  if (dropped) {
    return (
      <td
        className="border border-border px-2 py-2 align-top text-[13px] text-text-muted"
        data-cell={cellKey}
        title="该格因证据不足被质检策展剔除"
      >
        —
      </td>
    )
  }

  // 查无此项:没有该竞品的格子。
  if (!cell) {
    return (
      <td
        className="border border-border px-2 py-2 align-top text-[12px] italic text-text-muted"
        data-cell={cellKey}
      >
        未找到公开数据
      </td>
    )
  }

  const empty = !cell.value || cell.value.trim() === '' || cell.value.trim() === '—'

  return (
    <td
      className={`border px-2 py-2 align-top transition-colors ${
        matched ? 'border-accent bg-accent-soft ring-2 ring-accent ring-inset' : 'border-border'
      } ${dimmed ? 'opacity-45' : ''}`}
      data-cell={cellKey}
      data-ev-ids={cell.evidenceIds.join(',')}
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
      {/* cell 级真三色:充分不挂点(全绿=噪音),只在「部分/不足」显标记;stale 单独标。 */}
      {verdict && verdict !== 'supported' ? (
        <div className="mt-1.5 flex items-center gap-1">
          <VerdictDot verdict={verdict} showLabel />
          {stale ? <span className="text-[10px] text-evidence-stale" title="证据可能过期">· 旧</span> : null}
        </div>
      ) : stale ? (
        <div className="mt-1.5 text-[10px] text-evidence-stale" title="证据可能过期">· 证据偏旧</div>
      ) : null}
    </td>
  )
}

export function CompetitorComparison({
  state,
  dimensions,
  competitors,
  evidenceCount,
}: {
  /** analysis 资源 LoadState(skeleton / error / empty 控制)。 */
  state: LoadState
  /** 请求维度(行顺序,来自 run detail)。 */
  dimensions: string[]
  /** 请求竞品(列顺序,来自 run detail)。 */
  competitors: string[]
  /** running 进度文案的已采集证据数。 */
  evidenceCount: number
}) {
  // 逐维生长源(running 实时)+ 真三色 + 剔除集合(cell 级,绝不读 ref 级)。
  const cellRows = useRunStore((s) => s.cellRows)
  const cellVerdicts = useRunStore((s) => s.cellVerdicts)
  const droppedCells = useRunStore((s) => s.droppedCells)
  // done 兜底:REST analysis(渐进 fetch)。
  const analysis = useCockpitStore((s) => s.analysis)
  // 因果桥:共享高亮格集合(cockpitStore,稳定引用 — selector 返 raw 不 new Set)。
  const highlightedCells = useCockpitStore((s) => s.highlightedCells)

  const hlActive = highlightedCells.size > 0
  const droppedSet = new Set(droppedCells)

  // 行 = 请求维度(请求顺序,非到达序)。每维数据优先 cellRows[dim],回落 analysis.comparison。
  const hasAnyCellRow = Object.keys(cellRows).length > 0
  const hasAnalysis = !!analysis && analysis.comparison.length > 0

  // loading / idle:既无逐维 cell_row、也无 analysis → skeleton(running 进度提示)。
  if (!hasAnyCellRow && !hasAnalysis) {
    if (state === 'error') {
      return (
        <section className="space-y-2" aria-label="对比矩阵">
          <SectionTitle>竞品怎么比</SectionTitle>
          <ErrorNote>对比矩阵加载失败(网络或服务异常)。</ErrorNote>
        </section>
      )
    }
    if (state === 'loaded' || state === 'absent') {
      return (
        <section className="space-y-2" aria-label="对比矩阵">
          <SectionTitle>竞品怎么比</SectionTitle>
          <EmptyNote>本轮未产出可对比的维度数据。</EmptyNote>
        </section>
      )
    }
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

  // analysis 列回落:run detail 未给竞品时,从 analysis cells 并集推导。
  const analysisCompetitors =
    competitors.length > 0
      ? competitors
      : (() => {
          const seen: string[] = []
          if (analysis) {
            for (const row of analysis.comparison) {
              for (const c of row.cells) if (!seen.includes(c.competitor)) seen.push(c.competitor)
            }
          }
          return seen
        })()

  // 行维度回落:run detail 未给维度时,用 cellRows + analysis 并集(到达 / REST 顺序)。
  const rowDims =
    dimensions.length > 0
      ? dimensions
      : (() => {
          const seen: string[] = []
          for (const d of Object.keys(cellRows)) if (!seen.includes(d)) seen.push(d)
          if (analysis) for (const r of analysis.comparison) if (!seen.includes(r.dimension)) seen.push(r.dimension)
          return seen
        })()

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
              {analysisCompetitors.map((c) => (
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
            {rowDims.map((dim) => {
              const cr = cellRows[dim]
              const analysisRow = analysis?.comparison.find((r) => r.dimension === dim)

              // 该维整行失败:cell_row.status === 'failed'。
              if (cr && cr.status === 'failed') {
                return (
                  <tr key={dim}>
                    <th className="sticky left-0 z-10 border-b border-r border-border bg-surface px-2 py-2 text-left text-[13px] font-medium text-text-primary">
                      {dimensionLabel(dim)}
                    </th>
                    <td
                      className="border border-border px-2 py-2 text-[12px] italic text-text-muted"
                      colSpan={Math.max(1, analysisCompetitors.length)}
                    >
                      分析失败(本维度采集 / 抽取异常,未产出可对比数据)
                    </td>
                  </tr>
                )
              }
              // 该维整行查无:cell_row.status === 'empty'。
              if (cr && cr.status === 'empty') {
                return (
                  <tr key={dim}>
                    <th className="sticky left-0 z-10 border-b border-r border-border bg-surface px-2 py-2 text-left text-[13px] font-medium text-text-primary">
                      {dimensionLabel(dim)}
                    </th>
                    <td
                      className="border border-border px-2 py-2 text-[12px] italic text-text-muted"
                      colSpan={Math.max(1, analysisCompetitors.length)}
                    >
                      未找到公开数据
                    </td>
                  </tr>
                )
              }

              // 该维任一格命中高亮 → 行头高亮。
              const rowMatched =
                hlActive && analysisCompetitors.some((comp) => highlightedCells.has(`${dim}|${comp}`))

              return (
                <tr key={dim}>
                  <th
                    className={`sticky left-0 z-10 border-b border-r border-border bg-surface px-2 py-2 text-left text-[13px] font-medium ${
                      rowMatched ? 'text-accent' : 'text-text-primary'
                    } ${hlActive && !rowMatched ? 'opacity-45' : ''}`}
                  >
                    {dimensionLabel(dim)}
                  </th>
                  {analysisCompetitors.map((comp) => {
                    const cellKey = `${dim}|${comp}`
                    const dropped = droppedSet.has(cellKey)
                    // 归一格子:优先 cell_row(逐维生长),回落 analysis cell(REST)。
                    let cell: MatrixCell | null = null
                    if (cr) {
                      const c = cr.cells.find((x) => x.competitor === comp)
                      if (c) {
                        cell = {
                          competitor: comp,
                          value: c.value,
                          evidenceIds: c.evidence_refs.map((r) => r.evidence_id),
                        }
                      }
                    } else if (analysisRow) {
                      const c = analysisRow.cells.find((x) => x.competitor === comp)
                      if (c) {
                        cell = {
                          competitor: comp,
                          value: c.value,
                          evidenceIds: c.evidence_refs.map((r) => r.evidence_id),
                        }
                      }
                    }
                    // 三色:cell 级真算优先 cellVerdicts(实时),回落 analysisCell.support_verdict;绝不读 ref 级。
                    const verdict: SupportVerdict | null =
                      cellVerdicts[cellKey] ??
                      analysisRow?.cells.find((x) => x.competitor === comp)?.support_verdict ??
                      null
                    const matched = hlActive && highlightedCells.has(cellKey)
                    return (
                      <Cell
                        key={comp}
                        cell={cell}
                        verdict={verdict}
                        dropped={dropped}
                        matched={matched}
                        dimmed={hlActive && !matched}
                        cellKey={cellKey}
                      />
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-text-muted">
        佐证不足的结论已被质检剔除(显「—」),矩阵仅列站得住的格子;◐/○ 标记表示该格证据偏弱,需谨慎。
      </p>
      {hlActive ? (
        <p className="text-[11px] text-accent">已高亮选中决策的依据所在格(再点一次该决策的高亮按钮取消)。</p>
      ) : null}
    </section>
  )
}
