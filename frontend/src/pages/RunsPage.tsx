import * as React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Play, Plus, Search } from 'lucide-react'
import { discoverCompetitors, fetchRuns } from '@/lib/api'
import { dimensionLabel } from '@/lib/dimensions'
import { DEMO_RUN_ID } from '@/lib/demoFixture'
import { useSSE } from '@/hooks/useSSE'
import { CONTROLLED_DIMENSIONS, type DiscoveredCompetitor, type RunSummary } from '@/types/api'
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

// 决策处境卡片(Epic 1.2/1.3 / D8):必选一张,决定下游决策面语气 + 行动建议。
// context 字面值进 RunRequest.decision_context;"通用浏览" → 决策面收敛语气。
const PERSONA_CARDS = [
  { key: '选型PM', label: '选型 PM', desc: '为团队评估 / 选型一款工具', context: '选型PM:为团队评估并选型合适的工具' },
  { key: '竞品PM', label: '竞品 PM', desc: '盯防竞品动向、定产品策略', context: '竞品PM:盯防竞品动向并制定产品策略' },
  { key: '分析师', label: '分析师', desc: '为决策层产出竞品分析', context: '分析师:为决策层产出结构化竞品分析' },
  { key: '自定义', label: '自定义', desc: '描述你的具体处境', context: '' },
  { key: '通用浏览', label: '通用浏览 · 先看看', desc: '没有具体决策,先了解市场', context: '通用浏览' },
] as const

/**
 * CreateRunForm — 引导式 setup(Epic 1.3 / D8):
 *   ① 种子产品 → POST /discover-competitors 建议竞品(用户勾选增删确认,也可手动加)
 *   ② 对比维度(checkbox)
 *   ③ 决策处境卡片(必选一张;"通用浏览"→ 决策面收敛语气;"自定义"→ free text)
 *   → POST /run({competitors, dimensions, decision_context})
 *
 * 诚实(T4):发现只建议,用户点 + 显式确认才进竞品。LLM 不通 → 提示手动添加,不阻塞。
 * 用 div 而非 form:多个 Enter 目标(seed→发现 / 手动框→添加),避免误触发表单提交。
 */
function CreateRunForm() {
  const navigate = useNavigate()
  const sse = useSSE()
  const [seed, setSeed] = React.useState('')
  const [discovering, setDiscovering] = React.useState(false)
  const [discoverError, setDiscoverError] = React.useState<string | null>(null)
  const [suggestions, setSuggestions] = React.useState<DiscoveredCompetitor[]>([])
  const [competitors, setCompetitors] = React.useState<string[]>([])
  const [manualInput, setManualInput] = React.useState('')
  const [selectedDims, setSelectedDims] = React.useState<string[]>(['pricing', 'core_workflows'])
  const [personaKey, setPersonaKey] = React.useState<string | null>(null)
  const [customContext, setCustomContext] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const addCompetitor = (name: string) => {
    const n = name.trim()
    if (!n) return
    setCompetitors((prev) =>
      prev.length >= 5 || prev.some((c) => c.toLowerCase() === n.toLowerCase()) ? prev : [...prev, n],
    )
  }
  const removeCompetitor = (name: string) =>
    setCompetitors((prev) => prev.filter((c) => c !== name))

  const runDiscover = async () => {
    if (!seed.trim() || discovering) return
    setDiscovering(true)
    setDiscoverError(null)
    try {
      const res = await discoverCompetitors(seed.trim())
      setSuggestions(res.competitors)
      if (res.competitors.length === 0) setDiscoverError('未发现明确竞品,请在下方手动添加。')
    } catch (err) {
      // 后端 503 的 detail 已含"请手动输入竞品名",直接透传避免文案重复;网络错则给原因。
      setDiscoverError(`竞品发现失败:${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setDiscovering(false)
    }
  }

  const persona = PERSONA_CARDS.find((p) => p.key === personaKey) ?? null
  const decisionContext = persona
    ? persona.key === '自定义'
      ? customContext.trim()
      : persona.context
    : ''
  const personaOk = !!persona && (persona.key !== '自定义' || customContext.trim().length > 0)
  const canSubmit =
    !submitting &&
    competitors.length >= 1 &&
    competitors.length <= 5 &&
    selectedDims.length >= 1 &&
    personaOk

  const submit = async () => {
    if (!canSubmit) return
    setError(null)
    setSubmitting(true)
    try {
      const { runId } = await sse.start({
        mode: 'live',
        request: { competitors, dimensions: selectedDims, decision_context: decisionContext },
      })
      navigate(`/run/${runId}`)
      // NB: stream continues in module-level controller; RunPage reads runStore.
    } catch (err) {
      setError(`启动失败 — ${err instanceof Error ? err.message : String(err)}`)
      setSubmitting(false)
    }
  }

  const inputCls =
    'w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Plus className="h-4 w-4 text-accent" />
          新调研
        </CardTitle>
        <CardDescription>
          ① 发现 / 确认竞品 → ② 选对比维度 → ③ 选你的决策处境,启动完整调研(采集 → 分析 →
          撰写 → 质检 → 决策)。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-5">
          {/* ① 种子 + 自动发现 */}
          <div>
            <label htmlFor="seed" className="text-xs font-medium text-text-muted">
              ① 种子产品 → 自动发现竞品(可选;也可直接在下方手动添加)
            </label>
            <div className="mt-1 flex gap-2">
              <input
                id="seed"
                type="text"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void runDiscover()
                  }
                }}
                placeholder="例:飞书"
                className={inputCls}
                disabled={discovering}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => void runDiscover()}
                disabled={!seed.trim() || discovering}
                className="shrink-0 gap-1"
              >
                {discovering ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                发现竞品
              </Button>
            </div>
            {discoverError && <div className="mt-1 text-xs text-warning">{discoverError}</div>}
            {suggestions.length > 0 && (
              <div className="mt-2 space-y-1">
                <div className="text-xs text-text-muted">建议竞品(点 + 确认添加,可增删):</div>
                {suggestions.map((s) => {
                  const added = competitors.some((c) => c.toLowerCase() === s.name.toLowerCase())
                  return (
                    <div key={s.name} className="flex items-center gap-2 text-xs">
                      <button
                        type="button"
                        onClick={() => addCompetitor(s.name)}
                        disabled={added || competitors.length >= 5}
                        className={`shrink-0 rounded border px-1.5 py-0.5 ${
                          added
                            ? 'border-accent bg-accent-soft text-accent'
                            : 'border-border text-text-muted hover:border-accent hover:text-accent disabled:opacity-50'
                        }`}
                      >
                        {added ? '✓ 已加' : '+ 添加'}
                      </button>
                      <span className="font-medium text-text-primary">{s.name}</span>
                      <span className="truncate text-text-muted" title={s.rationale}>
                        — {s.rationale}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* 已选竞品 chips + 手动添加 */}
          <div>
            <span className="text-xs font-medium text-text-muted">已选竞品({competitors.length}/5)</span>
            <div className="mt-1 flex flex-wrap gap-2">
              {competitors.length === 0 ? (
                <span className="text-xs italic text-text-muted">
                  还没选竞品 —— 从上方建议添加,或手动输入。
                </span>
              ) : (
                competitors.map((c) => (
                  <span
                    key={c}
                    className="inline-flex items-center gap-1 rounded-md border border-accent bg-accent-soft px-2 py-1 text-xs text-accent"
                  >
                    {c}
                    <button
                      type="button"
                      onClick={() => removeCompetitor(c)}
                      aria-label={`移除 ${c}`}
                      className="text-accent hover:text-error"
                    >
                      ×
                    </button>
                  </span>
                ))
              )}
            </div>
            <div className="mt-2 flex gap-2">
              <input
                type="text"
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addCompetitor(manualInput)
                    setManualInput('')
                  }
                }}
                placeholder="手动添加竞品名"
                className={inputCls}
                disabled={competitors.length >= 5}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  addCompetitor(manualInput)
                  setManualInput('')
                }}
                disabled={!manualInput.trim() || competitors.length >= 5}
                className="shrink-0"
              >
                添加
              </Button>
            </div>
          </div>

          {/* ② 维度 */}
          <div>
            <span className="text-xs font-medium text-text-muted">② 对比维度(至少 1 个)</span>
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

          {/* ③ 决策处境(必选一张) */}
          <div>
            <span className="text-xs font-medium text-text-muted">
              ③ 你的决策处境(必选一张 —— 决定结论的语气与行动建议)
            </span>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {PERSONA_CARDS.map((p) => {
                const active = personaKey === p.key
                return (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => setPersonaKey(p.key)}
                    className={`rounded-md border p-2 text-left transition-colors ${
                      active
                        ? 'border-accent bg-accent-soft'
                        : 'border-border bg-surface hover:bg-surface-subtle'
                    }`}
                  >
                    <div
                      className={`text-xs font-medium ${active ? 'text-accent' : 'text-text-primary'}`}
                    >
                      {p.label}
                    </div>
                    <div className="mt-0.5 text-[11px] text-text-muted">{p.desc}</div>
                  </button>
                )
              })}
            </div>
            {personaKey === '自定义' && (
              <input
                type="text"
                value={customContext}
                onChange={(e) => setCustomContext(e.target.value)}
                placeholder="例:为 20 人研发团队选型协作平台,要能接审批"
                className={`${inputCls} mt-2`}
              />
            )}
            {personaKey === '通用浏览' && (
              <div className="mt-2 text-[11px] text-text-muted">
                已选「通用浏览」—— 决策面将收敛为"市场观察"语气,不给针对性行动指令。
              </div>
            )}
          </div>

          {error && (
            <div className="rounded-md border border-error bg-error/10 px-3 py-2 text-xs text-error">
              {error}
            </div>
          )}

          <div className="flex justify-end">
            <Button type="button" onClick={() => void submit()} disabled={!canSubmit} className="gap-2">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              启动调研
            </Button>
          </div>
        </div>
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
