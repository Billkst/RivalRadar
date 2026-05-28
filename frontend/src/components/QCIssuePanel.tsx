import { useRunStore } from '@/stores/runStore'

/**
 * QCIssuePanel — Codex #5 关键面板:让"分歧→解决"看得见。
 *
 * 数据源:runStore 从 SSE qc event 拿到的 verdict + issue count + issue_types map +
 *         evidenceCountSnapshots(从 collect event 累计)+ retryCount。
 *
 * **已知限制**:后端 SSE qc event 只暴露 issue **count + types map**,不带 issue
 * detail text(如"缺定价证据")。这是后端 schema 限制 — Task 16 stretch 加 GET /qc/:run
 * 才能拿到详细。Task 6 阶段:显示 issue 类型分布 + evidence delta,**不虚构** issue text。
 *
 * 评委 5 秒看到:第 N 轮 verdict + 问题类型分布 + 采集证据 delta
 *  → 印证"4 agent 在争论决策",而非单向流水线。
 */
const PROBLEM_TYPE_LABELS: Record<string, string> = {
  missing_evidence: '缺证据',
  schema_incomplete: '架构不完整',
  hallucination: '幻觉',
  low_coverage: '覆盖不足',
}

const VERDICT_LABELS: Record<string, { text: string; tone: string }> = {
  pass: { text: '✓ 通过', tone: 'text-success' },
  retry_collect: { text: '⟲ 打回采集', tone: 'text-warning' },
  retry_analyze: { text: '⟲ 打回分析', tone: 'text-warning' },
  insufficient_evidence: { text: '⚠ 证据不足(降级)', tone: 'text-error' },
}

export function QCIssuePanel() {
  const qcVerdict = useRunStore((s) => s.qcVerdict)
  const qcIssueCount = useRunStore((s) => s.qcIssueCount)
  const qcIssueTypes = useRunStore((s) => s.qcIssueTypes)
  const retryCount = useRunStore((s) => s.retryCount)
  const snapshots = useRunStore((s) => s.evidenceCountSnapshots)

  if (!qcVerdict) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="text-xs uppercase tracking-wide text-text-muted">质检面板</div>
        <div className="mt-3 text-xs italic text-text-muted">等待质检...</div>
      </div>
    )
  }

  const verdict = VERDICT_LABELS[qcVerdict] ?? { text: qcVerdict, tone: 'text-text-muted' }
  const isHealthy = qcVerdict === 'pass' && retryCount === 0

  const firstSnap = snapshots[0]?.count ?? 0
  const lastSnap = snapshots.at(-1)?.count ?? 0
  const delta = lastSnap - firstSnap

  return (
    <div className="rounded-lg border border-border bg-surface p-4 text-xs">
      <div className="mb-3 text-xs uppercase tracking-wide text-text-muted">质检面板</div>

      {isHealthy ? (
        <div className="space-y-2">
          <div className={`text-sm font-medium ${verdict.tone}`}>{verdict.text}</div>
          <div className="text-text-muted">一次性通过 · 无 retry</div>
          {lastSnap > 0 && <div className="font-mono text-text-muted">采集证据 {lastSnap} 条</div>}
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <div className="mb-1 text-text-muted">第 {retryCount + 1} 轮质检</div>
            <div className={`text-sm font-medium ${verdict.tone}`}>{verdict.text}</div>
          </div>

          {qcIssueCount > 0 && (
            <div>
              <div className="mb-1 text-text-muted">问题类型({qcIssueCount} 项)</div>
              <ul className="space-y-1">
                {Object.entries(qcIssueTypes).map(([type, count]) => (
                  <li key={type} className="flex items-center justify-between">
                    <span>{PROBLEM_TYPE_LABELS[type] ?? type}</span>
                    <span className="font-mono text-text-muted">×{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {snapshots.length > 0 && (
            <div>
              <div className="mb-1 text-text-muted">采集证据 delta</div>
              <div className="font-mono">
                {firstSnap} → {lastSnap}
                {delta > 0 && <span className="ml-2 text-success">(+{delta})</span>}
              </div>
            </div>
          )}
        </div>
      )}

      {qcIssueCount > 0 && (
        <div className="mt-3 border-t border-border pt-2 text-text-muted italic">
          详细 issue 文本待 Task 16 后端补强(GET /qc/:run)
        </div>
      )}
    </div>
  )
}
