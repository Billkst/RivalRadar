import * as React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Play, Plus } from 'lucide-react'
import { fetchRuns } from '@/lib/api'
import { dimensionLabel } from '@/lib/dimensions'
import { DEMO_RUN_ID } from '@/lib/demoFixture'
import { useSSE } from '@/hooks/useSSE'
import { CONTROLLED_DIMENSIONS, type RunSummary } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * /runs — 历史 run 列表 + Create Form (Codex #3 live run 入口)。
 *
 * Create Form 流程(Task 5: useSSE 接管 SSE 连接,跨路由不断流):
 *   1. 用户填竞品 (1-5,逗号分隔) + 维度 (1-6,checkbox)
 *   2. useSSE.start({mode:'live', request}) → 流写 runStore + 第一个 start event 返回 run_id
 *   3. navigate(/run/${run_id}) — RunPage 复用 runStore(live 流仍在 module-level 跑)
 */
export function RunsPage() {
  return (
    <div className="space-y-6">
      <DemoEntry />
      <CreateRunForm />
      <RunsList />
    </div>
  )
}

/**
 * DemoEntry — D6 demo day bullet-proof 入口(plan v3.2 §10 Epic 7.1)。
 *
 * 评委 / 自己 demo 时一键进入完整 25s office UI 演示,**不依赖 backend / LLM**。
 * RunPage 检测 isDemoRun(run_id) → 跳过 fetchRun + 跳过 SSE,直接 playFakeSSE。
 *
 * Clash 卡 / API 没钱 / backend down 都不影响 — 只要 vite dev server 在。
 */
function DemoEntry() {
  return (
    <Link
      to={`/run/${DEMO_RUN_ID}`}
      className="block rounded-lg border-2 border-accent bg-accent-soft p-4 transition-shadow hover:shadow-panel"
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl" aria-hidden>
          🎬
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-accent">Demo 模式 · 一键看 25s office UI 演示</div>
          <div className="mt-0.5 text-xs text-text-muted">
            预录 fixture 走完整 4 agent 协作 cycle:🦉 收集员 → 🦊 分析员 → 🦝 撰稿员 → 🐢 质检员。
            零依赖,不打 backend / LLM,适合 demo 兜底。
          </div>
        </div>
        <Play className="h-4 w-4 flex-shrink-0 text-accent" aria-hidden />
      </div>
    </Link>
  )
}

function CreateRunForm() {
  const navigate = useNavigate()
  const sse = useSSE()
  const [competitorsRaw, setCompetitorsRaw] = React.useState('')
  const [selectedDims, setSelectedDims] = React.useState<string[]>(['pricing', 'core_workflows'])
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const competitors = competitorsRaw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

  const canSubmit =
    !submitting && competitors.length >= 1 && competitors.length <= 5 && selectedDims.length >= 1

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Plus className="h-4 w-4 text-accent" />
          新调研
        </CardTitle>
        <CardDescription>
          填写 1-5 个竞品名 + 选择对比维度,启动一次完整调研(采集 → 分析 → 撰写 → 质检)。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={async (e) => {
            e.preventDefault()
            if (!canSubmit) return
            setError(null)
            setSubmitting(true)
            try {
              const { runId } = await sse.start({
                mode: 'live',
                request: { competitors, dimensions: selectedDims },
              })
              navigate(`/run/${runId}`)
              // NB: stream continues in module-level controller; RunPage reads runStore.
            } catch (err) {
              setError(`启动失败 — ${err instanceof Error ? err.message : String(err)}`)
              setSubmitting(false)
            }
          }}
          className="space-y-4"
        >
          <div>
            <label htmlFor="competitors" className="text-xs font-medium text-text-muted">
              竞品名(逗号分隔,1-5 个)
            </label>
            <input
              id="competitors"
              type="text"
              value={competitorsRaw}
              onChange={(e) => setCompetitorsRaw(e.target.value)}
              placeholder="例:Notion, Coda, ClickUp"
              className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent"
              disabled={submitting}
            />
            <div className="mt-1 text-xs text-text-muted">
              {competitors.length === 0
                ? '至少 1 个'
                : competitors.length > 5
                  ? `超出上限 (${competitors.length}/5)`
                  : `${competitors.length}/5`}
            </div>
          </div>

          <div>
            <span className="text-xs font-medium text-text-muted">对比维度(至少 1 个)</span>
            <div className="mt-2 flex flex-wrap gap-2">
              {CONTROLLED_DIMENSIONS.map((dim) => {
                const checked = selectedDims.includes(dim)
                return (
                  <label
                    key={dim}
                    className={`cursor-pointer rounded-md border px-3 py-1.5 text-xs transition-colors ${
                      checked
                        ? 'border-accent bg-accent-soft text-accent'
                        : 'border-border bg-surface text-text-muted hover:bg-surface-subtle'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) =>
                        setSelectedDims((prev) =>
                          e.target.checked ? [...prev, dim] : prev.filter((d) => d !== dim),
                        )
                      }
                      className="sr-only"
                      disabled={submitting}
                    />
                    {dimensionLabel(dim)}
                  </label>
                )
              })}
            </div>
          </div>

          {error && (
            <div className="rounded-md border border-error bg-error/10 px-3 py-2 text-xs text-error">
              {error}
            </div>
          )}

          <div className="flex justify-end">
            <Button type="submit" disabled={!canSubmit} className="gap-2">
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              启动调研
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function RunsList() {
  const [runs, setRuns] = React.useState<RunSummary[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    fetchRuns()
      .then(setRuns)
      .catch((err) => setError(String(err)))
  }, [])

  if (error) {
    return (
      <Card>
        <CardContent className="pt-4 text-xs text-text-muted">列表加载失败:{error}</CardContent>
      </Card>
    )
  }

  if (runs === null) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 pt-4 text-xs text-text-muted">
          <Loader2 className="h-3 w-3 animate-spin" />
          加载中…
        </CardContent>
      </Card>
    )
  }

  if (runs.length === 0) {
    return (
      <Card>
        <CardContent className="pt-4 text-xs italic text-text-muted">
          暂无历史 run。上方提交一次新调研即可。
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>历史调研</CardTitle>
        <CardDescription>{runs.length} 条 · 点击进入详情</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border">
          {runs.map((r) => (
            <li key={r.run_id} className="py-2">
              <Link
                to={`/run/${r.run_id}`}
                className="flex items-center justify-between gap-4 rounded-md px-2 py-1 text-sm hover:bg-surface-subtle"
              >
                <div className="flex flex-col">
                  <span className="font-mono text-xs text-text-muted">{r.run_id}</span>
                  <span className="text-text-primary">{r.competitors.join(' · ')}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <StatusBadge status={r.status} degraded={r.degraded} />
                  <time className="font-mono text-text-muted">{r.created_at.slice(0, 16)}</time>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

// 中文 status label —— 与 office UI 元素全中文风格 一致(post-ship review fix:
// 之前漏 'cancelled' 直接渲染英文 raw,跟旁边中文 "降级" 视觉断层)。
const STATUS_LABEL: Record<string, string> = {
  done: '完成',
  running: '进行中',
  failed: '失败',
  cancelled: '已停止',
  insufficient_evidence: '证据不足',
  degraded: '降级',
}

function StatusBadge({ status, degraded }: { status: string; degraded: boolean }) {
  const tone =
    status === 'done'
      ? 'bg-success/15 text-success'
      : status === 'running'
        ? 'bg-info/15 text-info'
        : status === 'failed'
          ? 'bg-error/15 text-error'
          : status === 'cancelled'
            ? 'bg-surface-subtle text-text-muted'
            : status === 'insufficient_evidence' || degraded
              ? 'bg-warning/15 text-warning'
              : 'bg-surface-subtle text-text-muted'
  return (
    <span className={`rounded px-2 py-0.5 ${tone}`}>
      {STATUS_LABEL[status] ?? status}
      {degraded && status !== 'degraded' ? ' · 降级' : ''}
    </span>
  )
}
