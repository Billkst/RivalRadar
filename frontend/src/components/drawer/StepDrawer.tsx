/**
 * StepDrawer — 计划步骤执行详情(Plan C Epic 6 Task 22)。
 *
 * id = dimension key(PlanRail 用 dimension 作 step id)。显该维:查询词
 * (runStore.queries 按 dimension 过滤)+ 命中来源(runStore.sources 按 dimension 过滤),
 * 点来源 → openEvidence → push 第 3 层(navStack)。
 *
 * selector 纪律(codex P1#3,记忆 confidence 10/10):selector 返 **raw**
 * (`useRunStore((s) => s.queries)`),**绝不**在 selector 内 .filter()(每次返新数组 →
 * Zustand v5 reference equality 失效 → Maximum update depth 死循环)。过滤在 render
 * body 用 useMemo。
 */
import { useMemo } from 'react'
import { useRunStore } from '@/stores/runStore'
import { useDrawerStore } from '@/stores/drawerStore'
import { dimensionLabel } from '@/lib/dimensions'

export function StepDrawer({
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
  // raw select(稳定引用)→ useMemo 过滤(codex P1#3:严禁 selector 内 .filter())
  const allQueries = useRunStore((s) => s.queries)
  const allSources = useRunStore((s) => s.sources)
  const queries = useMemo(() => allQueries.filter((q) => q.dimension === id), [allQueries, id])
  const sources = useMemo(() => allSources.filter((x) => x.dimension === id), [allSources, id])
  const openEvidence = useDrawerStore((s) => s.openEvidence)

  return (
    <>
      <div className="flex items-start gap-[13px] border-b border-border px-5 pb-[15px] pt-[18px]">
        <div className="flex-1">
          <div className="font-mono text-[10px] uppercase tracking-[.4px] text-text-muted">
            计划步骤 · 执行详情
          </div>
          <div className="mt-0.5 text-[16px] font-bold text-ink" tabIndex={-1}>
            {dimensionLabel(id)}
          </div>
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

      <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-[18px]">
        <div>
          <div className="mb-1.5 font-mono text-[11px] text-text-muted">查询词 · {queries.length} 条</div>
          {queries.length ? (
            queries.map((q, i) => (
              <div key={`${q.round}-${i}`} className="py-0.5 font-mono text-[11px] text-text-primary">
                ▸ {q.query_text}
              </div>
            ))
          ) : (
            <div className="text-[11px] italic text-text-muted">本步暂无查询记录。</div>
          )}
        </div>
        <div>
          <div className="mb-1.5 font-mono text-[11px] text-text-muted">命中来源 · {sources.length} 条</div>
          {sources.length ? (
            sources.map((s) => (
              <div key={s.evidence_id} className="flex items-baseline gap-2 py-1 text-[12px]">
                <span className="flex-1 truncate text-text-primary">{s.source_title}</span>
                <button
                  onClick={() => openEvidence(s.evidence_id)}
                  aria-label={`查看来源 ${s.source_title} 原文`}
                  className="flex-none text-[11px] text-accent underline hover:opacity-80"
                >
                  查看
                </button>
              </div>
            ))
          ) : (
            <div className="text-[11px] italic text-text-muted">本步暂无命中来源。</div>
          )}
        </div>
      </div>
    </>
  )
}
