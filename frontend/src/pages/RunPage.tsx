import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, FileText, Loader2 } from 'lucide-react'
import { ApiError, fetchRun } from '@/lib/api'
import { dimensionLabel } from '@/lib/dimensions'
import { formatBeijing } from '@/lib/time'
import { DEMO_RUN_DETAIL, isDemoRun } from '@/lib/demoFixture'
import { useSSE } from '@/hooks/useSSE'
import { useRunStore } from '@/stores/runStore'
import { useCockpitStore } from '@/stores/cockpitStore'
import type { RunDetail } from '@/types/api'
import { Button } from '@/components/ui/button'
import { CancelButton } from '@/components/office/CancelButton'
import { CockpitLayout } from '@/components/cockpit/CockpitLayout'
import { DecisionSurface } from '@/components/cockpit/DecisionSurface'
import { AgentRoster } from '@/components/workbench/AgentRoster'

// run 状态 → 头卡状态药丸(● 字符复用已知 tone text-class,不依赖 bg-* token;中文标签不漏英文 enum)。
const STATUS_PILL: Record<string, { label: string; tone: string }> = {
  idle: { label: '待开始', tone: 'text-text-muted' },
  running: { label: '运行中', tone: 'text-accent' },
  done: { label: '已完成', tone: 'text-success' },
  insufficient_evidence: { label: '证据不足', tone: 'text-warning' },
  degraded: { label: '已降级', tone: 'text-warning' },
  failed: { label: '失败', tone: 'text-error' },
  cancelled: { label: '已停止', tone: 'text-text-muted' },
}

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

  // StatusBar 用户价值计数(Epic 5):从 cockpitStore 读,防串 run(runId 不匹配显 "—")。
  // 三色汇总已不在此聚合 —— 旧 aggregateVerdicts 基于 ref 级 support_verdict(LLM 自报、
  // 不可信,codex P1#9)已删除;StatusBar 直接读 runStore.verdictSummary(cell 级真算,
  // verdict_recheck 实时)+ curation-drops 兜底。
  const cockpitRunId = useCockpitStore((s) => s.runId)
  const decisions = useCockpitStore((s) => s.decisions)
  const cockpitLive = !!run_id && cockpitRunId === run_id
  const decisionCount = cockpitLive && decisions ? decisions.decisions.length : undefined
  const riskCount =
    cockpitLive && decisions
      ? decisions.decisions.filter(
          (d) => d.stance === '需要警惕' || d.risk_reversibility === '不可逆',
        ).length
      : undefined

  return (
    // 整页满高 flex 列:返回行 + 概要卡 flex-none,cockpit 占剩余空间(flex-1)。原先 space-y-4
    // 自然高 + cockpit h-[100dvh] → 文档超一屏滚出白区(#6)。现在卡片 + cockpit 正好一屏。
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex flex-none items-center justify-between gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/runs" className="gap-1">
            <ArrowLeft className="h-3 w-3" />
            返回列表
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          {run_id && (
            <Button variant="outline" size="sm" asChild>
              <Link to={`/run/${run_id}/report`} className="gap-1">
                <FileText className="h-3 w-3" />
                查看完整报告
              </Link>
            </Button>
          )}
          {run_id && <CancelButton runId={run_id} />}
        </div>
      </div>

      {/* 紧凑 run 头卡:左 run 元信息,右研究团队工牌(填满原本空白的右半边)。 */}
      <div className="flex-none rounded-lg border border-border bg-surface p-4">
        {error && <div className="text-xs text-error">加载失败:{error}</div>}
        {!error && !run && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Loader2 className="h-3 w-3 animate-spin" />
            加载中…
          </div>
        )}
        {run &&
          (() => {
            const ds =
              storeRunId === run_id && storeStatus !== 'idle' ? storeStatus : run.status
            const pill = STATUS_PILL[ds] ?? STATUS_PILL.idle
            return (
              <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                {/* 左:调研任务身份 —— kicker(对称右侧)+ run_id 标题 + 状态药丸 + 结构化元信息 */}
                <div className="min-w-0 lg:flex-1">
                  <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">
                    调研任务
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                    <h1 className="font-mono text-[18px] font-semibold leading-tight text-text-primary">
                      {run_id}
                    </h1>
                    <span className={`inline-flex items-center gap-1 text-[12px] ${pill.tone}`}>
                      <span aria-hidden>●</span>
                      {pill.label}
                    </span>
                    {run.degraded && (
                      <span className="rounded bg-warning/15 px-1.5 py-0.5 text-[11px] font-medium text-warning">
                        降级
                      </span>
                    )}
                  </div>
                  {/* 结构化标签栅格(8px 节奏,标签 mono muted 对齐,值有呼吸) */}
                  <dl className="mt-3.5 space-y-2">
                    <div className="flex gap-3">
                      <dt className="w-9 flex-none pt-0.5 font-mono text-[10px] uppercase tracking-[.4px] text-text-muted">
                        竞品
                      </dt>
                      <dd className="flex flex-wrap gap-1.5">
                        {run.competitors.map((c, idx) => (
                          <Link
                            key={c}
                            to={`/run/${run_id}/competitor/${idx}`}
                            className="rounded bg-surface-subtle px-2 py-0.5 text-[12px] text-text-primary underline-offset-2 hover:text-accent"
                          >
                            {c}
                          </Link>
                        ))}
                      </dd>
                    </div>
                    <div className="flex gap-3">
                      <dt className="w-9 flex-none pt-0.5 font-mono text-[10px] uppercase tracking-[.4px] text-text-muted">
                        维度
                      </dt>
                      <dd className="text-[12px] leading-relaxed text-text-muted">
                        {run.dimensions.map(dimensionLabel).join(' · ')}
                      </dd>
                    </div>
                    <div className="flex gap-3">
                      <dt className="w-9 flex-none pt-0.5 font-mono text-[10px] uppercase tracking-[.4px] text-text-muted">
                        创建
                      </dt>
                      <dd className="font-mono text-[12px] text-text-muted">
                        <time title={run.created_at}>{formatBeijing(run.created_at)}</time> 北京时间
                      </dd>
                    </div>
                  </dl>
                </div>
                {/* 右:研究团队四个 agent 工牌 */}
                <div className="min-w-0 lg:flex-1">
                  <div className="mb-2 font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">
                    研究团队 · 持证员工
                  </div>
                  <AgentRoster />
                </div>
              </div>
            )
          })()}
      </div>

      {/* 证据驾驶舱:StatusBar + 左决策面 / 右实时分析流程。flex-1 min-h-0 吃掉剩余高度,
          内部各列自滚,页面不再溢出白区(#6)。 */}
      <div className="min-h-0 flex-1">
        {run_id && (
          <CockpitLayout
            runId={run_id}
            decisionCount={decisionCount}
            riskCount={riskCount}
            totalDimensions={run?.dimensions?.length}
          >
            <DecisionSurface
              runId={run_id}
              decisionContext={run?.decision_context}
              runStatus={run?.status}
              runDegraded={run?.degraded}
              dimensions={run?.dimensions ?? []}
              competitors={run?.competitors ?? []}
            />
          </CockpitLayout>
        )}
      </div>
    </div>
  )
}
