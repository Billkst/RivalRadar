import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { ApiError, fetchRun } from '@/lib/api'
import { dimensionLabel } from '@/lib/dimensions'
import { DEMO_RUN_DETAIL, isDemoRun } from '@/lib/demoFixture'
import { useSSE } from '@/hooks/useSSE'
import { useRunStore } from '@/stores/runStore'
import { useCockpitStore } from '@/stores/cockpitStore'
import { aggregateVerdicts } from '@/lib/verdict'
import type { EvidenceRef, RunDetail } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CancelButton } from '@/components/office/CancelButton'
import { CockpitLayout } from '@/components/cockpit/CockpitLayout'
import { DecisionSurface } from '@/components/cockpit/DecisionSurface'

/**
 * /run/:run_id — 单 run 详情页(v0.4 证据驾驶舱,Epic 3)。
 *
 * 布局(DESIGN.md §Layout Manus 分屏):
 *   顶部:返回按钮 + CancelButton(只 running 时显示)
 *   RunSummary 卡(中文维度 + storeStatus 优先)
 *   CockpitLayout:顶 StatusBar + 左决策面(Epic 3 骨架,Epic 4 填)/ 右实时分析流程
 *   (DAG / 虚拟办公室双视图 v0.4 退役 —— ViewSwitcher / VirtualOfficeView / DagDetailView /
 *    LiveFeedPanel / ReportSheet 不再 import,作 dead code 留待清理,Vite tree-shake 出 bundle)
 *
 * SSE 接入策略(Task 5):
 *   - store 已 tracking 此 run_id 且非 idle → live 流在背后继续,不重启
 *   - 否则(deep-link / 刷新)→ 启动 replay (GET /stream/:id)
 */
export function RunPage() {
  const { run_id } = useParams<{ run_id: string }>()
  const sse = useSSE()
  const storeRunId = useRunStore((s) => s.runId)
  const storeStatus = useRunStore((s) => s.status)

  const [run, setRun] = React.useState<RunDetail | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  // StrictMode(dev)双调 effect + playFakeSSE 异步起播的竞态守卫:同步标记"已为此
  // run_id 起播",防双播(证据计数翻倍)。genuine 重挂载(导航离开再回)→ 新 ref → 重播。
  const demoFiredRef = React.useRef<string | null>(null)

  // Fetch RunSummary metadata (independent of SSE stream).
  // Demo path(Epic 7.1):isDemoRun 直接 set fixture,不打 backend。
  React.useEffect(() => {
    if (!run_id) return
    if (isDemoRun(run_id)) {
      setRun(DEMO_RUN_DETAIL)
      return
    }
    fetchRun(run_id)
      .then(setRun)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : String(err))
      })
  }, [run_id])

  // Reattach SSE: skip if live stream already feeding this run_id.
  // Demo path(Epic 7.1):isDemoRun 自动 playFakeSSE Real 节奏,不打 backend SSE。
  // 这样 demo day Clash 卡 LLM / backend down 也能完整跑 25s 演示。
  //
  // Codex review P1 fixes:
  //   - Demo path 传 runId 让 fakeSSEPlayer 把 store.runId 设成 run_id(不再
  //     是 SAMPLE_EVENTS 的 'run_fake01'),storeRunId === run_id guard 才能命中
  //   - liveAlreadyHere 改成 storeStatus !== 'idle'(原先只接受 running/done
  //     遗漏 failed/insufficient_evidence/degraded/cancelled,replay 终态时
  //     guard 失效 → 又 trigger sse.start → startRun 重置 store 'running' →
  //     循环 hammer /stream/:id)
  React.useEffect(() => {
    if (!run_id) return
    if (isDemoRun(run_id)) {
      if (storeRunId === run_id || demoFiredRef.current === run_id) return
      demoFiredRef.current = run_id // 同步标记,先于异步 import,挡 StrictMode 第二次进入
      void import('@/dev/fakeSSEPlayer').then((m) =>
        m.playFakeSSE({ speed: 1.0, runId: run_id }),
      )
      return
    }
    const liveAlreadyHere = storeRunId === run_id && storeStatus !== 'idle'
    if (liveAlreadyHere) return
    sse.start({ mode: 'replay', runId: run_id }).catch((err) => {
      // replay 不通(run 过期/event log 被裁剪/backend 重启/Clash)—— 非致命但**不静默吞**:
      // 左决策面已由 DecisionSurface 走 RunDetail.status 回退从 REST 取齐(Codex C-3),
      // 这里记录便于排查;右执行流无 live 数据时显"正在连接分析流…"。
      console.warn('SSE replay failed for', run_id, err)
    })
  }, [run_id, storeRunId, storeStatus, sse])

  // StatusBar 决策派生指标(Epic 5):从 cockpitStore 读,防串 run(runId 不匹配显 "—")。
  const cockpitRunId = useCockpitStore((s) => s.runId)
  const decisions = useCockpitStore((s) => s.decisions)
  const analysis = useCockpitStore((s) => s.analysis)
  const cockpitLive = !!run_id && cockpitRunId === run_id
  const decisionCount = cockpitLive && decisions ? decisions.decisions.length : undefined
  const riskCount =
    cockpitLive && decisions
      ? decisions.decisions.filter(
          (d) => d.stance === '需要警惕' || d.risk_reversibility === '不可逆',
        ).length
      : undefined
  const verdictSummary = React.useMemo(() => {
    if (!cockpitLive) return undefined
    const refs: EvidenceRef[] = []
    if (analysis) for (const row of analysis.comparison) for (const cell of row.cells) refs.push(...cell.evidence_refs)
    if (decisions) for (const d of decisions.decisions) refs.push(...d.evidence_refs)
    if (refs.length === 0) return undefined
    return aggregateVerdicts(refs)
  }, [cockpitLive, analysis, decisions])

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

      {import.meta.env.DEV && (
        <div className="flex items-center gap-2 text-[10px] text-text-muted">
          <span className="text-warning">🧪 fake SSE</span>
          {[
            { label: 'Fast', speed: 0.2, hint: '0.2x — 5s 全程,快速看动画' },
            { label: 'Real', speed: 1.0, hint: '1.0x — 25s 真 LLM 节奏' },
            { label: 'Slow', speed: 2.0, hint: '2.0x — 50s 慢动作' },
          ].map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => {
                void import('@/dev/fakeSSEPlayer').then((m) =>
                  m.playFakeSSE({ speed: preset.speed }),
                )
              }}
              className="rounded border border-dashed border-warning px-2 py-0.5 text-warning hover:bg-warning/10"
              title={preset.hint}
            >
              {preset.label}
            </button>
          ))}
        </div>
      )}

      {/* 证据驾驶舱:StatusBar + 左决策面(Epic 4 实装)/ 右实时分析流程(重试环) */}
      {run_id && (
        <CockpitLayout
          decisionCount={decisionCount}
          riskCount={riskCount}
          verdictSummary={verdictSummary}
        >
          <DecisionSurface
            runId={run_id}
            decisionContext={run?.decision_context}
            runStatus={run?.status}
            runDegraded={run?.degraded}
          />
        </CockpitLayout>
      )}
    </div>
  )
}
