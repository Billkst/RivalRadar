/**
 * StatusBar — cockpit 顶栏(DESIGN.md §Signature #1 + §关键组件基调 StatusBar,Epic 3.1 / Plan C Task 24)。
 *
 * 两组信息:
 *   (1) 用户价值计数口径(§12.3 #6):结论 N 条 │ 关键风险 N 个 │ 已打回 N 次 │ 最新证据 日期
 *   (2) 全局 support_verdict 三色簇(DESIGN.md v5 §C-D5):**充分 X · 部分 Y · 已剔除 Z**
 *       —— cell 级真算(runStore.verdictSummary,verdict_recheck 实时)+ curation-drops 兜底剔除计数。
 *       红○「已剔除」可点 → 弹出剔除清单(策展剔除的 competitor · dimension)。
 *   ●状态 = 运行态指示点(idle/running/done/degraded…),muted 置右。
 *
 * codex P1#9:旧三色基于 ref 级 EvidenceRef.support_verdict(RunPage aggregateVerdicts,已删),
 * 现一律读 cell 级真算 —— running 用 runStore.verdictSummary,done 兜底 GET /curation-drops。
 */
import * as React from 'react'
import { useRunStore } from '@/stores/runStore'
import { useElapsed } from '@/hooks/useElapsed'
import { fetchCurationDrops } from '@/lib/api'
import { formatBeijingDate } from '@/lib/time'
import { VerdictDot } from '@/components/cockpit/VerdictDot'
import type { RunStatus } from '@/stores/runStore'
import type { CurationDrop } from '@/types/api'

interface StatusBarProps {
  /** 当前 run_id(done 后拉 curation-drops 兜底剔除计数 + 清单)。 */
  runId: string
  /** 结论(决策)条数 — Epic 4 经 /decisions 喂入。 */
  decisionCount?: number
  /** 关键风险数(需要警惕 + 不可逆决策)— Epic 4 derive。 */
  riskCount?: number
}

const STATUS_META: Record<RunStatus, { label: string; tone: string; pulse?: boolean }> = {
  idle: { label: '待开始', tone: 'text-text-muted' },
  running: { label: '运行中', tone: 'text-accent', pulse: true },
  done: { label: '已完成', tone: 'text-success' },
  insufficient_evidence: { label: '证据不足', tone: 'text-warning' },
  degraded: { label: '已降级', tone: 'text-warning' },
  failed: { label: '失败', tone: 'text-error' },
  cancelled: { label: '已停止', tone: 'text-text-muted' },
}

const TERMINAL: ReadonlySet<RunStatus> = new Set<RunStatus>([
  'done',
  'degraded',
  'insufficient_evidence',
  'failed',
  'cancelled',
])

const EMPTY_DROPS: CurationDrop[] = []

/** ms → 紧凑用时:"7s" / "1m20s" / "1h05m"。 */
function fmtElapsed(ms: number): string {
  const total = Math.floor(ms / 1000)
  if (total < 60) return `${total}s`
  const m = Math.floor(total / 60)
  if (m < 60) return `${m}m${(total % 60).toString().padStart(2, '0')}s`
  return `${Math.floor(m / 60)}h${(m % 60).toString().padStart(2, '0')}m`
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <span className="whitespace-nowrap">
      <span className="text-text-muted">{label} </span>
      <span className="font-medium tabular-nums text-text-primary">{value}</span>
    </span>
  )
}

const Sep = () => <span className="text-border">│</span>

/** 剔除清单弹层(诚实文案:这些格因证据不足被策展剔除,矩阵显「—」)。ESC / 遮罩关。 */
function DropsPanel({ drops, onClose }: { drops: CurationDrop[]; onClose: () => void }) {
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center" role="dialog" aria-modal="true" aria-label="策展剔除清单">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden />
      <div className="relative mt-20 max-h-[70vh] w-[min(440px,92vw)] overflow-y-auto rounded-lg border border-border bg-surface p-4 shadow-panel">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-[15px] font-semibold text-text-primary">已剔除的格 · {drops.length}</div>
            <p className="mt-0.5 text-[12px] leading-relaxed text-text-muted">
              以下格因证据不足被质检策展剔除,矩阵显「—」。剔除不等于降级,是健康的策展(只留站得住的结论)。
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="关闭"
            className="flex h-8 w-8 flex-none items-center justify-center rounded-md border border-border text-text-muted hover:border-verdict-unsupported hover:text-verdict-unsupported"
          >
            ✕
          </button>
        </div>
        <ul className="mt-3 space-y-1.5">
          {drops.length ? (
            drops.map((d, i) => (
              <li key={`${d.competitor}-${d.dimension}-${i}`} className="flex items-baseline gap-2 text-[13px]">
                <span className="font-medium text-text-primary">{d.competitor}</span>
                <span className="text-text-muted">·</span>
                <span className="text-text-primary">{d.dimension}</span>
              </li>
            ))
          ) : (
            <li className="text-[13px] italic text-text-muted">本轮无被剔除的格。</li>
          )}
        </ul>
      </div>
    </div>
  )
}

export function StatusBar({ runId, decisionCount, riskCount }: StatusBarProps) {
  const status = useRunStore((s) => s.status)
  const degraded = useRunStore((s) => s.degraded)
  const retryCount = useRunStore((s) => s.retryCount)
  const snapshots = useRunStore((s) => s.evidenceCountSnapshots)
  // 计时器(#1):running 实时走表;终态显总耗时;无 ts(冷 REST 载入)→ 不显,诚实不臆造。
  const runStartTs = useRunStore((s) => s.runStartTs)
  const runEndTs = useRunStore((s) => s.runEndTs)
  // live 走表用客户端墙钟锚点(本 run 首次进 running 的本地时刻),**不**直接用 server runStartTs:
  // demo 用历史假 ts(2026-05-28),Date.now()-假ts 会显示数百小时;真 live run 客户端锚点 ≈ 真起点。
  // 终态总耗时用 server ts 差值(demo 用一致的历史假 ts → 时长正确)。replay 的 start/done 都是
  // _now()(回放秒级,非真实时长)→ runStore 把 replay 的 runStartTs 置 null → 此处 totalMs=null 不显。
  const [liveStart, setLiveStart] = React.useState<number | null>(null)
  React.useEffect(() => {
    // 本地计时锚点只属于当前 run。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLiveStart(null)
  }, [runId])
  React.useEffect(() => {
    // 状态边界决定计时器开始/停止,不能沿用上一个 running 区间。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLiveStart((prev) => (status === 'running' ? prev ?? Date.now() : null))
  }, [status])
  const liveElapsed = useElapsed(status === 'running' ? liveStart : null)
  // cell 级真三色汇总(verdict_recheck 实时刷;running 期由 SSE 填,done 后保留最后一次)。
  const verdictSummary = useRunStore((s) => s.verdictSummary)
  // SSE 剔除格 keys(`${dimension}|${competitor}`)—— REST /curation-drops 不可达(demo 无后端)时清单回落它。
  const droppedCells = useRunStore((s) => s.droppedCells)

  // 剔除清单:done 后拉 curation-drops(scope=cell)兜底计数 + 点开清单。
  const [drops, setDrops] = React.useState<CurationDrop[]>(EMPTY_DROPS)
  const [showDrops, setShowDrops] = React.useState(false)
  const terminal = TERMINAL.has(status)
  React.useEffect(() => {
    // 剔除清单与弹层状态均为 run-scoped。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDrops(EMPTY_DROPS)
    setShowDrops(false)
  }, [runId])
  React.useEffect(() => {
    if (!terminal || !runId) return
    let alive = true
    fetchCurationDrops(runId)
      .then((rows) => {
        if (alive) setDrops(rows)
      })
      .catch(() => {
        /* 兜底失败不阻断:running 期 verdictSummary.dropped 已是真值 */
      })
    return () => {
      alive = false
    }
  }, [terminal, runId])

  const cellDrops = React.useMemo(() => drops.filter((d) => d.scope === 'cell'), [drops])
  // 剔除清单:REST(scope=cell)优先;为空(demo 无后端 / 未拉到)时回落 SSE droppedCells,
  // 让「已剔除计数」与「清单」一致(verdict_recheck.summary.dropped 与 droppedCells 同源)。
  const dropList = React.useMemo<CurationDrop[]>(() => {
    if (cellDrops.length) return cellDrops
    return droppedCells.map((k) => {
      const [dimension, competitor] = k.split('|')
      return { scope: 'cell', competitor, dimension, detail: '', created_at: '' }
    })
  }, [cellDrops, droppedCells])
  // 剔除计数:live verdictSummary.dropped 优先(running 实时),回落清单长度(done 兜底)。
  const droppedCount = verdictSummary?.dropped ?? (dropList.length || undefined)

  const latest = snapshots.at(-1)
  const latestDate = latest ? formatBeijingDate(latest.ts) : '—'
  const meta = STATUS_META[status] ?? STATUS_META.idle
  const dash = (n: number | undefined) => (typeof n === 'number' ? n : '—')

  // running → 实时走表;终态 → 总耗时;无 ts → 不显(冷 REST 载入,诚实不臆造)。
  const totalMs =
    runStartTs && runEndTs
      ? Math.max(0, new Date(runEndTs).getTime() - new Date(runStartTs).getTime())
      : null
  const timer =
    status === 'running'
      ? liveStart != null
        ? { label: '已用时', value: fmtElapsed(liveElapsed) }
        : null
      : totalMs != null && totalMs > 0
        ? { label: '总耗时', value: fmtElapsed(totalMs) }
        : null

  return (
    <header
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-surface px-4 py-2 font-mono text-[13px]"
      role="status"
      aria-label="运行状态汇总"
    >
      <Metric label="结论" value={`${dash(decisionCount)} 条`} />
      <Sep />
      <Metric label="关键风险" value={`${dash(riskCount)} 个`} />
      <Sep />
      <Metric label="已打回" value={`${retryCount} 次`} />
      <Sep />
      {timer ? (
        <>
          <Metric label={timer.label} value={timer.value} />
          <Sep />
        </>
      ) : null}
      <Metric label="最新证据" value={latest ? `${latestDate}（${latest.count} 条）` : '—'} />
      <Sep />
      {/* 证据支持度三色簇(cell 级真算,色盲双编码:颜色 + 形状 ●◐○) */}
      <span className="flex items-center gap-3 whitespace-nowrap">
        <span className="text-text-muted">证据支持度</span>
        <span className="flex items-center gap-1 tabular-nums" title="佐证充分(cell 级真算)">
          <VerdictDot verdict="supported" />充分 {dash(verdictSummary?.supported)}
        </span>
        <span className="flex items-center gap-1 tabular-nums" title="部分佐证(cell 级真算)">
          <VerdictDot verdict="partial" />部分 {dash(verdictSummary?.partial)}
        </span>
        <button
          type="button"
          onClick={() => setShowDrops((v) => !v)}
          aria-expanded={showDrops}
          className="flex items-center gap-1 tabular-nums hover:underline"
          title="点击查看/收起被策展剔除的格(矩阵显「—」)"
        >
          <VerdictDot verdict="unsupported" />已剔除 {dash(droppedCount)}
        </button>
      </span>

      {/* ●状态 — 运行态指示点,muted 置右 */}
      <span className={`ml-auto flex items-center gap-1.5 ${meta.tone}`} aria-live="polite">
        <span className={meta.pulse ? 'animate-pulse' : ''} aria-hidden>
          ●
        </span>
        {meta.label}
        {degraded && status === 'done' && (
          <span className="ml-1 text-warning" title="本轮存在未消解的质检/决策降级">
            · 降级
          </span>
        )}
      </span>

      {showDrops ? <DropsPanel drops={dropList} onClose={() => setShowDrops(false)} /> : null}
    </header>
  )
}
