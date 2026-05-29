/**
 * StatusBar — cockpit 顶栏(DESIGN.md §Signature #1 + §关键组件基调 StatusBar,Epic 3.1)。
 *
 * 两组信息:
 *   (1) 用户价值计数口径(§12.3 #6):结论 N 条 │ 关键风险 N 个 │ 已打回 N 次 │ 最新证据 日期
 *   (2) 全局 support_verdict 三色汇总(§12.3 #5 第二层):充分 X · 部分 Y · 不足 Z
 *   ●状态 = 运行态指示点(idle/running/done/degraded…),muted 置右。
 *
 * 数据源:已打回 / 最新证据 / 状态 从 runStore live derive;结论数 / 关键风险 / 三色汇总
 * 来自决策 + 证据(Epic 4/5 经 props 喂入),未就绪时显 "—"(不留空、不臆造)。
 */
import { useRunStore } from '@/stores/runStore'
import type { RunStatus } from '@/stores/runStore'

export interface VerdictSummary {
  supported: number
  partial: number
  unsupported: number
}

interface StatusBarProps {
  /** 结论(决策)条数 — Epic 4 经 /decisions 喂入。 */
  decisionCount?: number
  /** 关键风险数(需要警惕 + 不可逆决策)— Epic 4 derive。 */
  riskCount?: number
  /** 全局证据支持度三色汇总 — Epic 5 从 evidence-list derive。 */
  verdictSummary?: VerdictSummary
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

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <span className="whitespace-nowrap">
      <span className="text-text-muted">{label} </span>
      <span className="font-medium tabular-nums text-text-primary">{value}</span>
    </span>
  )
}

const Sep = () => <span className="text-border">│</span>

export function StatusBar({ decisionCount, riskCount, verdictSummary }: StatusBarProps) {
  const status = useRunStore((s) => s.status)
  const degraded = useRunStore((s) => s.degraded)
  const retryCount = useRunStore((s) => s.retryCount)
  const snapshots = useRunStore((s) => s.evidenceCountSnapshots)

  const latest = snapshots.at(-1)
  const latestDate = latest ? latest.ts.slice(0, 10) : '—'
  const meta = STATUS_META[status] ?? STATUS_META.idle
  const dash = (n: number | undefined) => (typeof n === 'number' ? n : '—')

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
      <Metric label="最新证据" value={latest ? `${latestDate}（${latest.count} 条）` : '—'} />
      <Sep />
      {/* 证据支持度三色汇总(色盲双编码:颜色 + 形状 ●◐○) */}
      <span className="flex items-center gap-2 whitespace-nowrap">
        <span className="text-text-muted">证据支持度</span>
        <span className="tabular-nums text-verdict-supported" title="佐证充分">
          ● {dash(verdictSummary?.supported)}
        </span>
        <span className="tabular-nums text-verdict-partial" title="部分佐证">
          ◐ {dash(verdictSummary?.partial)}
        </span>
        <span className="tabular-nums text-verdict-unsupported" title="佐证不足">
          ○ {dash(verdictSummary?.unsupported)}
        </span>
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
    </header>
  )
}
