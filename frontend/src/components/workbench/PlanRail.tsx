/**
 * PlanRail — 研究计划 rail(左决策面顶,Plan C Epic 7 Task 26 / C-D8 / DESIGN.md v5 §计划勾选)。
 *
 * step = 请求维度(每维一步)。状态由 SSE 派生(边做边勾):
 *   - todo:维度尚未到达任何数据(run idle / 未开始)。
 *   - doing:collect/analyze 节点在跑、该维 cell_row 还没到。
 *   - done:`runStore.cellRows[dim]` 已到达(逐维生长)。
 *   - reopen:round>0 的 evidence_delta 命中该维来源(补证 in flight),且补证的 delta ts
 *     晚于该维 cell_row ts —— 短暂 reopen,补证后新 cell_row 重到 → 回 done。
 *
 * 点 done/reopen 步 → `drawerStore.openStep(dimension)`(StepDrawer 显查询词 + 命中来源)。
 *
 * selector 纪律(记忆 confidence 10/10):selector 返 raw 引用;派生在 render body 用 module-level
 * 稳定常量 + useMemo,绝不在 selector 内 .filter()/.map()/new Set()。
 */
import { useMemo } from 'react'
import { useRunStore } from '@/stores/runStore'
import { useDrawerStore } from '@/stores/drawerStore'
import { dimensionLabel } from '@/lib/dimensions'
import type { SSESourceData, SSEEvidenceDeltaData, SSECellRowData } from '@/types/api'

type StepState = 'todo' | 'doing' | 'done' | 'reopen'

const EMPTY_SOURCES: SSESourceData[] = []
const EMPTY_DELTAS: SSEEvidenceDeltaData[] = []
const EMPTY_CELLROWS: Record<string, SSECellRowData> = {}

const PMark = ({ state }: { state: StepState }) => (
  <svg className="pmk h-3.5 w-3.5 flex-none" viewBox="0 0 14 14" aria-hidden>
    <circle
      cx="7"
      cy="7"
      r="5.6"
      fill="none"
      strokeWidth="1.5"
      className={
        state === 'done'
          ? 'stroke-v-sup'
          : state === 'doing'
            ? 'stroke-accent'
            : state === 'reopen'
              ? 'stroke-v-uns'
              : 'stroke-border-strong'
      }
    />
    {state === 'doing' ? <circle cx="7" cy="7" r="2.4" className="fill-accent" /> : null}
    {state === 'done' ? (
      <path
        d="M4 7.3l2.2 2.2 3.9-4.6"
        fill="none"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="stroke-v-sup [stroke-dasharray:14] [stroke-dashoffset:0] [transition:stroke-dashoffset_.4s_ease-out]"
      />
    ) : null}
  </svg>
)

export function PlanRail({ dimensions }: { dimensions: string[] }) {
  // raw selectors（稳定引用）→ 派生在 render body。
  const cellRowsRaw = useRunStore((s) => s.cellRows)
  const sourcesRaw = useRunStore((s) => s.sources)
  const deltasRaw = useRunStore((s) => s.evidenceDeltas)
  const status = useRunStore((s) => s.status)
  const collectState = useRunStore((s) => s.nodes.collect)
  const analyzeState = useRunStore((s) => s.nodes.analyze)
  const openStep = useDrawerStore((s) => s.openStep)

  const cellRows = Object.keys(cellRowsRaw).length ? cellRowsRaw : EMPTY_CELLROWS
  const sources = sourcesRaw.length ? sourcesRaw : EMPTY_SOURCES
  const deltas = deltasRaw.length ? deltasRaw : EMPTY_DELTAS

  // 补证(reopen)检测:evidence_id → dimension(来源映射)。
  const idToDim = useMemo(() => {
    const m: Record<string, string> = {}
    for (const src of sources) m[src.evidence_id] = src.dimension
    return m
  }, [sources])

  // 每维最近一次「round>0 补证 delta」的 ts(命中该维来源)。
  const reopenTsByDim = useMemo(() => {
    const m: Record<string, string> = {}
    for (const d of deltas) {
      if (d.round <= 0) continue
      for (const id of d.new_evidence_ids) {
        const dim = idToDim[id]
        if (!dim) continue
        if (!m[dim] || d.ts > m[dim]) m[dim] = d.ts
      }
    }
    return m
  }, [deltas, idToDim])

  const steps = useMemo(() => {
    const running =
      status === 'running' &&
      (collectState === 'running' || collectState === 'retrying' || analyzeState === 'running')
    return dimensions.map((dim) => {
      const cr = cellRows[dim]
      let state: StepState = 'todo'
      if (cr) {
        // 补证 in flight:补证 delta ts 晚于该维 cell_row ts → reopen,否则 done。
        const reopenTs = reopenTsByDim[dim]
        state = reopenTs && reopenTs > cr.ts ? 'reopen' : 'done'
      } else if (running) {
        state = 'doing'
      }
      return { dim, state }
    })
  }, [dimensions, cellRows, reopenTsByDim, status, collectState, analyzeState])

  if (dimensions.length === 0) return null

  const doneCount = steps.filter((s) => s.state === 'done').length

  return (
    <section aria-label="研究计划" className="space-y-1.5">
      <div className="flex items-center gap-2 text-[13px]">
        <span className="font-medium text-text-muted">研究计划</span>
        <span className="font-mono text-[11px] tabular-nums text-text-muted">
          {doneCount} / {dimensions.length}
        </span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {steps.map(({ dim, state }) => {
          const clickable = state === 'done' || state === 'reopen'
          const sub =
            state === 'done'
              ? '✓ 已完成'
              : state === 'reopen'
                ? '↺ 补证中'
                : state === 'doing'
                  ? '检索中'
                  : '待开始'
          return (
            <button
              key={dim}
              type="button"
              disabled={!clickable}
              onClick={clickable ? () => openStep(dim) : undefined}
              aria-label={`研究步骤 ${dimensionLabel(dim)}(${sub}）${clickable ? ',点击查看执行详情' : ''}`}
              className={`flex min-w-[148px] flex-none flex-col gap-1.5 rounded-md border px-3 py-2 text-left transition-colors ${
                state === 'doing'
                  ? 'border-accent bg-accent-soft'
                  : state === 'reopen'
                    ? 'border-v-uns bg-v-uns-soft'
                    : 'border-border bg-surface'
              } ${clickable ? 'cursor-pointer hover:border-accent-line' : 'cursor-default opacity-[.62]'}`}
            >
              <span className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                <PMark state={state} />
                <span
                  className={
                    state === 'doing'
                      ? 'text-accent-deep'
                      : state === 'reopen'
                        ? 'text-v-uns'
                        : 'text-text-primary'
                  }
                >
                  {dimensionLabel(dim)}
                </span>
              </span>
              <span
                className={`font-mono text-[10px] tracking-[.2px] ${
                  state === 'done'
                    ? 'text-v-sup'
                    : state === 'reopen'
                      ? 'text-v-uns'
                      : 'text-text-muted'
                }`}
              >
                {sub}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
