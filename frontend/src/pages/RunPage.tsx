import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { ApiError, fetchRun } from '@/lib/api'
import { useSSE } from '@/hooks/useSSE'
import { useRunStore } from '@/stores/runStore'
import type { RunDetail } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DagCanvas } from '@/components/dag/DagCanvas'
import { DagDrawer } from '@/components/dag/DagDrawer'
import { QCIssuePanel } from '@/components/QCIssuePanel'
import {
  ComparisonMatrixRowPlaceholder,
  CompetitorOverviewPlaceholder,
  EvidenceSheetPlaceholder,
} from '@/components/placeholders'

/**
 * /run/:run_id — 单 run 详情页(Task 6 vertical slice MVP)。
 *
 * 布局(spec §11.1 主画布):
 *   - 顶部:RunSummary (back / run_id / 竞品 / 维度 / 状态 / 创建)
 *   - DAG 区:DagCanvas (左 8 col) + QCIssuePanel (右 4 col)
 *   - 占位区:CompetitorOverview + ComparisonMatrix (2 col)
 *   - EvidenceSheet 占位(Task 9 引用 chip 实装)
 *   - DagDrawer Sheet:点 DAG 节点 → 拉 trace 详情(input/output/tokens/latency/retry index)
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
  const [drawerNode, setDrawerNode] = React.useState<string | null>(null)

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
      <Button variant="ghost" size="sm" asChild>
        <Link to="/runs" className="gap-1">
          <ArrowLeft className="h-3 w-3" />
          返回列表
        </Link>
      </Button>

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
                <span className="text-xs text-text-muted">维度:</span> {run.dimensions.join(' · ')}
              </div>
              <div>
                <span className="text-xs text-text-muted">状态:</span> {run.status}
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

      {/* DAG money shot + QC panel */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8">
          <DagCanvas onNodeClick={setDrawerNode} />
        </div>
        <div className="col-span-12 lg:col-span-4">
          <QCIssuePanel />
        </div>
      </div>

      {/* Vertical slice 占位 (Task 8/9/10 实装) */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <CompetitorOverviewPlaceholder />
        <ComparisonMatrixRowPlaceholder />
      </div>
      <EvidenceSheetPlaceholder />

      {/* Trace drawer (右侧 Sheet) */}
      <DagDrawer
        runId={run_id ?? null}
        nodeName={drawerNode}
        open={drawerNode !== null}
        onClose={() => setDrawerNode(null)}
      />
    </div>
  )
}
