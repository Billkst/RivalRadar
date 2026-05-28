import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { ApiError, fetchRun } from '@/lib/api'
import { dimensionLabel } from '@/lib/dimensions'
import { useSSE } from '@/hooks/useSSE'
import { useRunStore } from '@/stores/runStore'
import type { RunDetail } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CancelButton } from '@/components/office/CancelButton'
import { ViewSwitcher, type OfficeView } from '@/components/office/ViewSwitcher'
import { VirtualOfficeView } from '@/components/office/VirtualOfficeView'
import { DagDetailView } from '@/components/office/DagDetailView'
import { LiveFeedPanel } from '@/components/office/LiveFeedPanel'
import {
  ComparisonMatrixRowPlaceholder,
  CompetitorOverviewPlaceholder,
  EvidenceSheetPlaceholder,
} from '@/components/placeholders'

/**
 * /run/:run_id — 单 run 详情页(plan v3.2 P0-3 双视图叙事 + Epic 5 集成)。
 *
 * 布局(DESIGN.md §虚拟办公室 layout):
 *   顶部:返回按钮 + CancelButton(只 running 时显示)
 *   RunSummary 卡(中文维度 + storeStatus 优先)
 *   ViewSwitcher + 主画布(office 默认 / DAG 切换)+ 右侧 LiveFeedPanel
 *   Placeholders(Day-3+ Epic 6 实装 TeamRoster + ReportSheet)
 *
 * SSE 接入策略(Task 5):
 *   - store 已 tracking 此 run_id 且 running/done → live 流在背后继续,不重启
 *   - 否则(deep-link / 刷新)→ 启动 replay (GET /stream/:id)
 */
export function RunPage() {
  const { run_id } = useParams<{ run_id: string }>()
  const sse = useSSE()
  const storeRunId = useRunStore((s) => s.runId)
  const storeStatus = useRunStore((s) => s.status)

  const [run, setRun] = React.useState<RunDetail | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [view, setView] = React.useState<OfficeView>('office')

  // Fetch RunSummary metadata (independent of SSE stream).
  React.useEffect(() => {
    if (!run_id) return
    fetchRun(run_id)
      .then(setRun)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : String(err))
      })
  }, [run_id])

  // Reattach SSE: skip if live stream already feeding this run_id.
  React.useEffect(() => {
    if (!run_id) return
    const liveAlreadyHere =
      storeRunId === run_id && (storeStatus === 'running' || storeStatus === 'done')
    if (liveAlreadyHere) return
    sse.start({ mode: 'replay', runId: run_id }).catch(() => {
      // Swallow — replay failure is non-fatal; user still sees RunSummary above.
    })
  }, [run_id, storeRunId, storeStatus, sse])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/runs" className="gap-1">
            <ArrowLeft className="h-3 w-3" />
            返回列表
          </Link>
        </Button>
        {run_id && <CancelButton runId={run_id} />}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-mono text-base">{run_id}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {error && <div className="text-xs text-error">加载失败:{error}</div>}
          {!error && !run && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <Loader2 className="h-3 w-3 animate-spin" />
              加载中…
            </div>
          )}
          {run && (
            <>
              <div>
                <span className="text-xs text-text-muted">竞品:</span>{' '}
                {run.competitors.map((c, idx) => (
                  <Link
                    key={c}
                    to={`/run/${run_id}/competitor/${idx}`}
                    className="mr-2 underline-offset-2 hover:underline"
                  >
                    {c}
                  </Link>
                ))}
              </div>
              <div>
                <span className="text-xs text-text-muted">维度:</span>{' '}
                {run.dimensions.map(dimensionLabel).join(' · ')}
              </div>
              <div>
                <span className="text-xs text-text-muted">状态:</span>{' '}
                {storeRunId === run_id && storeStatus !== 'idle' ? storeStatus : run.status}
                {run.degraded && <span className="ml-2 text-warning">· 降级</span>}
              </div>
              <div>
                <span className="text-xs text-text-muted">创建:</span>{' '}
                <time className="font-mono">{run.created_at}</time>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <ViewSwitcher value={view} onChange={setView} />
        <div className="flex items-center gap-3 text-[10px] text-text-muted">
          {import.meta.env.DEV && (
            <>
              <span className="text-[10px] text-warning">🧪 fake SSE</span>
              {[
                { label: 'Fast', speed: 0.2, hint: '0.2x — 5s 全程,快速看动画' },
                { label: 'Real', speed: 1.0, hint: '1.0x — 25s 真 LLM 节奏(与时间戳同步)' },
                { label: 'Slow', speed: 2.0, hint: '2.0x — 50s 慢动作 spike 节奏' },
              ].map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    void import('@/dev/fakeSSEPlayer').then((m) =>
                      m.playFakeSSE({ speed: preset.speed }),
                    )
                  }}
                  className="rounded border border-dashed border-warning px-2 py-0.5 text-[10px] text-warning hover:bg-warning/10"
                  title={preset.hint}
                >
                  {preset.label}
                </button>
              ))}
            </>
          )}
          <span>
            {view === 'office'
              ? '看 4 个 agent 在你面前实时工作'
              : 'agent 协作流程 + 节点详情 + 质检报告'}
          </span>
        </div>
      </div>

      {/* 主画布 8 col + LiveFeedPanel 4 col */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8">
          {view === 'office' ? (
            <VirtualOfficeView />
          ) : (
            <DagDetailView runId={run_id ?? null} />
          )}
        </div>
        <div className="col-span-12 lg:col-span-4">
          <div className="h-[480px] lg:h-[540px]">
            <LiveFeedPanel />
          </div>
        </div>
      </div>

      {/* Vertical slice 占位(Day-3+ Epic 6 实装 TeamRoster + ReportSheet) */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <CompetitorOverviewPlaceholder />
        <ComparisonMatrixRowPlaceholder />
      </div>
      <EvidenceSheetPlaceholder />
    </div>
  )
}
