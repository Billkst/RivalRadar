/**
 * DecisionBoard — 左栏顶层「决策流」(DESIGN.md §决策流骨架 / plan §4.1 / D9)。
 *
 * 每条决策 = 三件套单元:
 *   - **做什么**(action,22px 首屏第一眼)+ 自解释 stance 标签 + horizon + risk(可逆/成本)。
 *   - **为什么**(why)+ 依据行常驻(最佳证据原句 + 来源/日期/support_verdict + 查看原文)+ [n] pills。
 *   - **哪里可能错**(<details> 折叠,对结论的攻击)。
 *   - 持续观察 → 必渲染 watch{metric/threshold/trigger}。
 *
 * ⚠️ schema 现实:Decision 无 counterargument 字段。"哪里可能错" **诚实派生**自
 *    最弱证据 verdict + 决策后果(可逆/成本),framing 为结构性警示,**不虚构后端字段**。
 *    (未来可在 Decision 加 LLM 生成的 counterargument;见交付说明。)
 *
 * 状态(§12.4):loading skeleton / 0 决策解释性空卡 / degraded 每条 caveat /
 *              通用浏览 收敛语气 banner。insufficient_evidence 处境卡在 DecisionSurface 处理。
 */
import { useEvidence } from '@/stores/evidenceStore'
import { ageDays, isStale } from '@/lib/freshness'
import { SectionTitle, PanelSkeleton, EmptyNote, ErrorNote } from '@/components/cockpit/parts'
import { VerdictDot } from '@/components/cockpit/VerdictDot'
import { EvidencePill } from '@/components/cockpit/EvidencePill'
import type { LoadState } from '@/stores/cockpitStore'
import type { Decision, EvidenceRef, Stance, SupportVerdict } from '@/types/api'

const STANCE_STYLE: Record<Stance, string> = {
  建议采用: 'bg-accent-soft text-accent',
  需要警惕: 'bg-warning/15 text-warning',
  持续观察: 'bg-surface-subtle text-text-muted',
}

const SEVERITY: Record<SupportVerdict, number> = { unsupported: 2, partial: 1, supported: 0 }

/** 依据行用的"最佳证据":优先佐证充分,否则取第一条。 */
function bestRef(refs: EvidenceRef[]): EvidenceRef | null {
  if (refs.length === 0) return null
  return refs.find((r) => r.support_verdict === 'supported') ?? refs[0]
}

/** 派生"哪里可能错":最弱证据 verdict + 决策后果 → 对结论的攻击 + 收敛建议。 */
function deriveCounterargument(d: Decision): string {
  let weakest: SupportVerdict = 'supported'
  for (const r of d.evidence_refs) {
    if (SEVERITY[r.support_verdict] > SEVERITY[weakest]) weakest = r.support_verdict
  }
  const head =
    weakest === 'unsupported'
      ? '这条建议的关键依据目前佐证不足'
      : weakest === 'partial'
        ? '这条建议有部分依据只拿到部分佐证'
        : '即使依据当前充分,市场与产品仍在变化'
  const risk =
    d.risk_reversibility === '不可逆'
      ? `,且这是不可逆、成本${d.risk_cost}的决策,一旦判断有误代价高`
      : ''
  const fallback = d.stance === '持续观察' ? '保持观察并补充证据' : '降级为持续观察、补足证据后再决定'
  return `这个建议可能错,因为${head}${risk}。若为真,应${fallback}。`
}

function EvidenceLine({ refItem }: { refItem: EvidenceRef }) {
  const ev = useEvidence(refItem.evidence_id)
  const stale = ev ? isStale(ev.fetched_at) : false
  return (
    <div className="rounded-md border-l-2 border-accent bg-accent-soft/40 px-3 py-2">
      <div className="flex items-start gap-2">
        <span className="mt-0.5">
          <VerdictDot verdict={refItem.support_verdict} />
        </span>
        <p className="text-[15px] leading-snug text-text-primary">“{refItem.quote}”</p>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2 pl-5 font-mono text-[11px] text-text-muted">
        <span className="truncate">{ev ? ev.source_title : '来源加载中…'}</span>
        {ev ? (
          <span>
            · {ev.fetched_at.slice(0, 10)}
            {stale ? (
              <span className="text-evidence-stale"> · {ageDays(ev.fetched_at)} 天前(可能过期)</span>
            ) : null}
          </span>
        ) : null}
      </div>
    </div>
  )
}

function DecisionCard({
  decision,
  index,
  degraded,
  selected,
  onToggle,
}: {
  decision: Decision
  index: number
  degraded: boolean
  selected: boolean
  onToggle: () => void
}) {
  const best = bestRef(decision.evidence_refs)
  return (
    <article
      className={`rounded-lg border bg-surface p-4 ${
        selected ? 'border-accent ring-1 ring-accent' : 'border-border'
      } ${degraded ? 'opacity-90' : ''}`}
    >
      {/* 做什么 */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-[22px] font-semibold leading-tight text-text-primary">
          {index}. {decision.action}
        </h3>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px]">
        <span className={`rounded px-2 py-0.5 font-medium ${STANCE_STYLE[decision.stance]}`}>
          {decision.stance}
        </span>
        <span className="rounded bg-surface-subtle px-2 py-0.5 font-mono text-text-muted">
          {decision.horizon}
        </span>
        <span className="rounded bg-surface-subtle px-2 py-0.5 font-mono text-text-muted">
          {decision.risk_reversibility} · 成本{decision.risk_cost}
        </span>
      </div>

      {degraded ? (
        <p className="mt-2 text-[12px] text-warning">⚠ 本轮证据未完全达标,此建议置信度下降,请谨慎参考。</p>
      ) : null}

      {/* 为什么 */}
      <div className="mt-3">
        <SectionTitle>为什么这么判断</SectionTitle>
        <p className="mt-1 text-[15px] leading-relaxed text-text-primary">{decision.why}</p>
        {best ? (
          <div className="mt-2">
            <EvidenceLine refItem={best} />
          </div>
        ) : (
          <p className="mt-2 text-[12px] italic text-text-muted">本条暂无可展示的证据原句。</p>
        )}
        {decision.evidence_refs.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-1">
            <span className="text-[11px] text-text-muted">证据:</span>
            {decision.evidence_refs.map((r, i) => (
              <EvidencePill key={`${r.evidence_id}-${i}`} refItem={r} index={i + 1} />
            ))}
            <button
              type="button"
              onClick={onToggle}
              className={`ml-1 rounded border px-1.5 py-0.5 text-[11px] ${
                selected
                  ? 'border-accent bg-accent-soft text-accent'
                  : 'border-border text-text-muted hover:border-accent hover:text-accent'
              }`}
              aria-pressed={selected}
            >
              {selected ? '已在矩阵高亮 ✓' : '在矩阵高亮依据 ⤵'}
            </button>
          </div>
        ) : null}
      </div>

      {/* 持续观察 → watch */}
      {decision.watch ? (
        <div className="mt-3 rounded-md border border-border bg-surface-subtle p-3 text-[13px]">
          <div className="text-[12px] font-medium text-text-muted">何时回看(监控触发器)</div>
          <ul className="mt-1 space-y-0.5 text-text-primary">
            <li>
              <span className="text-text-muted">盯指标:</span> {decision.watch.metric}
            </li>
            <li>
              <span className="text-text-muted">阈值:</span> {decision.watch.threshold}
            </li>
            <li>
              <span className="text-text-muted">越线则:</span> {decision.watch.trigger}
            </li>
          </ul>
        </div>
      ) : null}

      {/* 哪里可能错(派生) */}
      <details className="mt-3 group">
        <summary className="cursor-pointer list-none text-[13px] font-medium text-text-muted hover:text-text-primary">
          <span className="mr-1 inline-block transition-transform group-open:rotate-90">▸</span>
          哪里可能错
        </summary>
        <p className="mt-1 pl-4 text-[15px] leading-relaxed text-text-primary">
          {deriveCounterargument(decision)}
        </p>
      </details>
    </article>
  )
}

export function DecisionBoard({
  decisions,
  state,
  degraded,
  genericContext,
  evidenceCount,
  selectedIdx,
  onSelect,
}: {
  decisions: Decision[]
  state: LoadState
  degraded: boolean
  genericContext: boolean
  evidenceCount: number
  selectedIdx: number | null
  onSelect: (idx: number | null) => void
}) {
  return (
    <section className="space-y-3" aria-label="决策流">
      <SectionTitle>下一步怎么做</SectionTitle>

      {state === 'loading' || state === 'idle' ? (
        <PanelSkeleton
          hint={
            evidenceCount > 0
              ? `分析与质检进行中(已采集 ${evidenceCount} 条证据)—— 决策建议将在分析完成后生成。`
              : '分析进行中 —— 决策建议将在分析完成后生成。'
          }
        />
      ) : state === 'error' ? (
        <ErrorNote>决策加载失败(网络或服务异常),可刷新重试;其余面板不受影响。</ErrorNote>
      ) : decisions.length === 0 ? (
        <EmptyNote>
          本轮未形成可建议的行动。可能是证据不足以支撑明确决策 —— 可查看下方对比矩阵与证据,或放宽竞品范围重跑。
        </EmptyNote>
      ) : (
        <>
          {genericContext ? (
            <div className="rounded-md border border-border bg-surface-subtle px-3 py-2 text-[12px] text-text-muted">
              你未设定具体决策处境,以下为通用市场观察判断(语气已收敛,非针对性行动建议)。
            </div>
          ) : null}
          {decisions.map((d, idx) => (
            <DecisionCard
              key={idx}
              decision={d}
              index={idx + 1}
              degraded={degraded}
              selected={selectedIdx === idx}
              onToggle={() => onSelect(selectedIdx === idx ? null : idx)}
            />
          ))}
        </>
      )}
    </section>
  )
}
