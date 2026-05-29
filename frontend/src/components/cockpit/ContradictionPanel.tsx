/**
 * ContradictionPanel — 质检与自我纠错(DESIGN.md §ContradictionPanel / plan §4.4)。
 *
 * 复用 QCIssuePanel 思路,两个数据源:
 *   - runStore.events:逐轮 verdict + 问题类型 + 证据 delta。**live(node event)+ replay
 *     (trace event)双路径** —— replay 的 qc 轮没有 node event,从 trace.output_summary
 *     解析 verdict/issues(否则 deep-link 重放时本面板会误判"无质检记录")。
 *   - cockpitStore.qc:**sanitized** 终态 detail(罐装文案,严禁 raw exception/model text);
 *     events 为空(冷 deep-link / 重放失败)时回退用它渲染终态裁决。
 *
 * 终态通过且 0 问题时如实展示"经 N 轮质检最终通过";有未消解问题(降级 run)才列
 * sanitized detail。**不伪造未解决问题**。错误态(/qc 5xx/网络)给红色 ErrorNote,
 * **绝不**伪装成"无质检记录"空态。
 */
import * as React from 'react'
import { useRunStore } from '@/stores/runStore'
import { SectionTitle, PanelSkeleton, EmptyNote, ErrorNote } from '@/components/cockpit/parts'
import type { LoadState } from '@/stores/cockpitStore'
import type { SanitizedQCResult, SSEEvent } from '@/types/api'

const PROBLEM_TYPE_LABELS: Record<string, string> = {
  missing_evidence: '缺证据',
  schema_incomplete: '结构不完整',
  hallucination: '疑似臆测',
  low_coverage: '覆盖不足',
}

const VERDICT_LABELS: Record<string, { text: string; tone: string }> = {
  pass: { text: '通过', tone: 'text-verdict-supported' },
  retry_collect: { text: '打回采集', tone: 'text-verdict-partial' },
  retry_analyze: { text: '打回分析', tone: 'text-verdict-partial' },
  insufficient_evidence: { text: '证据不足(降级)', tone: 'text-verdict-unsupported' },
}

interface Round {
  round: number
  verdict: string
  issues: number
  types: Record<string, number>
}

function deriveRounds(events: SSEEvent[]): Round[] {
  const rounds: Round[] = []
  for (const e of events) {
    if (e.type === 'node' && e.data.node === 'qc') {
      // live 路径:node event 带结构化 summary。
      const s = e.data.summary
      rounds.push({
        round: rounds.length + 1,
        verdict: s.verdict ?? '',
        issues: s.issues ?? 0,
        types: s.issue_types ?? {},
      })
    } else if (e.type === 'trace' && e.data.node === 'qc') {
      // replay 路径:trace.output 是 "verdict=… issues=… degraded=… retry=…" 字符串。
      const out = e.data.summary?.output ?? ''
      const vm = out.match(/verdict=(\w+)/)
      const im = out.match(/issues=(\d+)/)
      rounds.push({
        round: rounds.length + 1,
        verdict: vm?.[1] ?? '',
        issues: im ? Number(im[1]) : 0,
        types: {},
      })
    }
  }
  return rounds
}

export function ContradictionPanel({
  qc,
  qcState,
  interrupted = false,
}: {
  qc: SanitizedQCResult | null
  qcState: LoadState
  interrupted?: boolean
}) {
  const events = useRunStore((s) => s.events)
  const rounds = React.useMemo(() => deriveRounds(events), [events])

  const Title = () => <SectionTitle>哪里可能错(质检)</SectionTitle>

  // 既无逐轮记录、也无终态 qc → 区分中断 / 错误 / 加载中 / 真空态(诚实,不臆测)。
  if (rounds.length === 0 && !qc) {
    if (interrupted) {
      return (
        <section className="space-y-2" aria-label="质检与自我纠错">
          <Title />
          <EmptyNote>运行已中断,未完成质检。</EmptyNote>
        </section>
      )
    }
    if (qcState === 'error') {
      return (
        <section className="space-y-2" aria-label="质检与自我纠错">
          <Title />
          <ErrorNote>质检结论加载失败(网络或服务异常),可刷新重试;其余面板不受影响。</ErrorNote>
        </section>
      )
    }
    if (qcState === 'loading' || qcState === 'idle') {
      return (
        <section className="space-y-2" aria-label="质检与自我纠错">
          <Title />
          <PanelSkeleton hint="质检员尚未给出裁决…" />
        </section>
      )
    }
    return (
      <section className="space-y-2" aria-label="质检与自我纠错">
        <Title />
        <EmptyNote>本轮无质检记录。</EmptyNote>
      </section>
    )
  }

  // 终态裁决:优先 sanitized /qc,回退到最后一轮(events 路径)。
  const finalVerdict = qc?.verdict ?? rounds[rounds.length - 1]?.verdict ?? ''
  const fv = VERDICT_LABELS[finalVerdict] ?? { text: finalVerdict, tone: 'text-text-muted' }
  const retries = Math.max(0, rounds.length - 1)
  const sanitizedIssues = qc?.issues ?? []
  const roundsLabel =
    rounds.length > 0
      ? `${rounds.length} 轮质检${retries > 0 ? ` · 自我纠错 ${retries} 次` : ' · 一次通过'}`
      : '已完成质检'

  return (
    <section className="space-y-2" aria-label="质检与自我纠错">
      <Title />
      <div className="rounded-lg border border-border bg-surface p-4 text-[13px]">
        <div className="flex items-baseline gap-2">
          <span className="text-text-muted">最终裁决</span>
          <span className={`text-[15px] font-medium ${fv.tone}`}>{fv.text}</span>
          <span className="text-text-muted">· {roundsLabel}</span>
        </div>

        {/* 逐轮"分歧→解决"(events 路径才有;冷 deep-link 仅终态时省略) */}
        {rounds.length > 0 ? (
          <ol className="mt-3 space-y-1.5">
            {rounds.map((r) => {
              const v = VERDICT_LABELS[r.verdict] ?? { text: r.verdict, tone: 'text-text-muted' }
              const typeStr = Object.entries(r.types)
                .map(([t, n]) => `${PROBLEM_TYPE_LABELS[t] ?? t}×${n}`)
                .join(' · ')
              return (
                <li key={r.round} className="flex items-baseline gap-2">
                  <span className="font-mono text-[11px] text-text-muted">第{r.round}轮</span>
                  <span className={`font-medium ${v.tone}`}>{v.text}</span>
                  {r.issues > 0 ? (
                    <span className="text-[12px] text-text-muted">
                      {r.issues} 项{typeStr ? `(${typeStr})` : ''}
                    </span>
                  ) : (
                    <span className="text-[12px] text-text-muted">无问题</span>
                  )}
                </li>
              )
            })}
          </ol>
        ) : null}

        {/* 终态明细加载失败(有逐轮但 /qc 取失败)→ 诚实告知未消解明细不可用 */}
        {qcState === 'error' && rounds.length > 0 ? (
          <p className="mt-3 border-t border-border pt-2 text-[12px] text-error">
            终态质检明细加载失败,以上为逐轮记录,可能不含未消解问题。
          </p>
        ) : sanitizedIssues.length > 0 ? (
          <div className="mt-3 border-t border-border pt-2">
            <div className="mb-1 text-[12px] text-text-muted">未消解的问题({sanitizedIssues.length} 项)</div>
            <ul className="space-y-1">
              {sanitizedIssues.map((it, i) => (
                <li key={i} className="text-[12px] text-text-primary">
                  <span className="font-mono text-text-muted">
                    [{it.competitor} · {it.dimension}]
                  </span>{' '}
                  {it.detail}
                </li>
              ))}
            </ul>
          </div>
        ) : retries > 0 ? (
          <p className="mt-3 border-t border-border pt-2 text-[12px] text-text-muted">
            首轮发现的问题已通过补采证据消解,最终结论建立在更充分的证据之上。
          </p>
        ) : null}
      </div>
    </section>
  )
}
