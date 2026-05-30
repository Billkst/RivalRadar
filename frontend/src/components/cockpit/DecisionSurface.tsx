/**
 * DecisionSurface — 左决策面合成 + 数据编排(Epic 4 合成 + Epic 5 编排)。
 *
 * 职责:
 *   - 触发 cockpitStore.sync(渐进 fetch:analyze-done 取 /analysis;done 取
 *     /qc /insight /decisions /trace /evidence-list 并 seed evidenceStore)。
 *   - 顶部 InsightHeadline(market_context / differentiation_thesis 一句话语境)。
 *   - 决策流(DecisionBoard)+ 对比矩阵 + 质检 + 审计轨迹 + 证据时间线。
 *   - **因果桥**:选中决策 → 其证据 id 集合传给对比矩阵高亮。
 *   - 运行级状态(§12.4):insufficient_evidence → 处境卡片;failed/cancelled →
 *     已填充面板保留、未解锁面板标"运行已中断未生成"。
 *   - 挂载 EvidenceSlideOver(全局单例,pill / 时间线点开)。
 *
 * 防串 run:cockpitStore.runId !== 本页 runId 时,数据视为未就绪(idle),避免
 * 切 run 首帧闪上一个 run 的内容。
 */
import * as React from 'react'
import { useRunStore } from '@/stores/runStore'
import { useCockpitStore } from '@/stores/cockpitStore'
import { isDemoRun } from '@/lib/demoFixture'
import { EmptyNote } from '@/components/cockpit/parts'
import { DecisionBoard } from '@/components/cockpit/DecisionBoard'
import { CompetitorComparison } from '@/components/cockpit/CompetitorComparison'
import { ContradictionPanel } from '@/components/cockpit/ContradictionPanel'
import { SelfAuditTrace } from '@/components/cockpit/SelfAuditTrace'
import { EvidenceTimeline } from '@/components/cockpit/EvidenceTimeline'
import { EvidenceSlideOver } from '@/components/cockpit/EvidenceSlideOver'
import type { LoadState } from '@/stores/cockpitStore'
import type { RunStatus } from '@/stores/runStore'

function SituationCard({ evidenceCount }: { evidenceCount: number }) {
  return (
    <div className="rounded-lg border border-dashed border-warning/50 bg-surface-subtle p-4">
      <div className="text-[15px] font-medium text-text-primary">本轮证据不足,暂不给出明确决策</div>
      <p className="mt-1 text-[13px] leading-relaxed text-text-muted">
        部分维度在有界广搜后仍未找到足够公开数据。为避免臆测,这里不编造结论 —— 已采集{' '}
        {evidenceCount} 条证据可在下方查看。
      </p>
      <p className="mt-2 text-[12px] italic text-text-muted">
        建议:放宽竞品范围 / 重新发现竞品 / 换更具体的维度后重跑。
      </p>
    </div>
  )
}

export function DecisionSurface({
  runId,
  decisionContext,
  runStatus,
  runDegraded,
}: {
  runId: string
  decisionContext?: string
  /** RunDetail.status(REST 权威)。SSE replay 失败/未连时用它驱动取数,防全面板永久 skeleton。 */
  runStatus?: string
  /** RunDetail.degraded(REST 权威)。deep-link 无 live 流时仍能显降级 caveat。 */
  runDegraded?: boolean
}) {
  const storeRunId = useRunStore((s) => s.runId)
  const storeStatus = useRunStore((s) => s.status)
  const storeDegraded = useRunStore((s) => s.degraded)
  const analyzeDone = useRunStore((s) => s.nodes.analyze === 'done')
  const snapshots = useRunStore((s) => s.evidenceCountSnapshots)
  const evidenceCount = snapshots.at(-1)?.count ?? 0

  // 有效状态:本页 live SSE 流在跑(storeRunId 命中且非 idle)→ 用 store 状态(渐进揭示);
  // 否则(deep-link / 刷新 / replay 失败)→ 回退 RunDetail.status(REST 权威),
  // 确保 done run 即使 SSE 不通也能从 REST 取齐左决策面(Codex C-3 修复)。
  // demo 例外:playFakeSSE 必定提供 live 流,不走 REST 回退,保渐进揭示的招牌演示节奏。
  const storeLive = storeRunId === runId && storeStatus !== 'idle'
  const status: RunStatus = storeLive
    ? storeStatus
    : isDemoRun(runId)
      ? 'idle'
      : ((runStatus as RunStatus) || 'idle')

  const sync = useCockpitStore((s) => s.sync)
  const cockpitRunId = useCockpitStore((s) => s.runId)
  const analysis = useCockpitStore((s) => s.analysis)
  const decisions = useCockpitStore((s) => s.decisions)
  const insight = useCockpitStore((s) => s.insight)
  const qc = useCockpitStore((s) => s.qc)
  const evidenceList = useCockpitStore((s) => s.evidenceList)
  const trace = useCockpitStore((s) => s.trace)
  const analysisState = useCockpitStore((s) => s.analysisState)
  const decisionsState = useCockpitStore((s) => s.decisionsState)
  const insightState = useCockpitStore((s) => s.insightState)
  const qcState = useCockpitStore((s) => s.qcState)
  const evidenceState = useCockpitStore((s) => s.evidenceState)
  const traceState = useCockpitStore((s) => s.traceState)

  React.useEffect(() => {
    if (!runId) return
    sync({ runId, status, analyzeReady: analyzeDone })
  }, [runId, status, analyzeDone, sync])

  // 因果桥:选中决策 idx → 其 evidence id 集合。切 run 清选择。
  const [selectedIdx, setSelectedIdx] = React.useState<number | null>(null)
  React.useEffect(() => setSelectedIdx(null), [runId])

  // 防串 run:cockpit 数据属于本页 runId 才采信。
  const live = cockpitRunId === runId
  const s = (st: LoadState): LoadState => (live ? st : 'idle')
  const decisionList = live && decisions ? decisions.decisions : []

  const highlightIds = React.useMemo(() => {
    const set = new Set<string>()
    if (selectedIdx !== null && live && decisions) {
      const d = decisions.decisions[selectedIdx]
      d?.evidence_refs.forEach((r) => set.add(r.evidence_id))
    }
    return set
  }, [selectedIdx, decisions, live])

  const genericContext =
    !decisionContext || !decisionContext.trim() || decisionContext.trim().startsWith('通用浏览')
  // 降级信号:live SSE bool 或 RunDetail.degraded(REST 权威,deep-link 必需)。
  const degraded = storeDegraded || !!runDegraded
  const interrupted = status === 'failed' || status === 'cancelled'
  const insufficient = status === 'insufficient_evidence'

  return (
    <div className="space-y-4">
      {/* 运行中断横幅(failed/cancelled):诚实展示已得中间结果 */}
      {interrupted ? (
        <div className="rounded-lg border border-warning/50 bg-warning/10 px-4 py-2 text-[13px] text-warning">
          ⚠ 运行{status === 'cancelled' ? '已停止' : '失败'},以下为已获得的中间结果(决策与质检未生成)。
        </div>
      ) : null}

      {/* 顶部一句话语境 */}
      {live && insightState === 'loaded' && insight ? (
        <div className="rounded-lg border border-border bg-surface px-4 py-3">
          <p className="text-[15px] leading-relaxed text-text-primary">{insight.market_context}</p>
          <p className="mt-1 text-[13px] leading-relaxed text-text-muted">
            {insight.differentiation_thesis}
          </p>
          <p className="mt-1.5 text-[10px] uppercase tracking-wide text-text-muted">
            AI 基于证据综合判断
          </p>
        </div>
      ) : null}

      {/* 决策流(首屏)。insufficient + 有决策:不藏(StatusBar 计数一致),改置信度横幅 +
          每条强制 caveat;insufficient + 0 决策:处境卡片(真没结论)。 */}
      {interrupted && s(decisionsState) !== 'loaded' ? (
        <EmptyNote>运行已中断,未生成决策建议(下方为已得到的中间结果)。</EmptyNote>
      ) : insufficient && decisionList.length === 0 ? (
        <SituationCard evidenceCount={evidenceCount} />
      ) : (
        <>
          {insufficient ? (
            <div className="rounded-lg border border-warning/50 bg-warning/10 px-4 py-2 text-[13px] text-warning">
              ⚠ 本轮证据未达质检标准,以下建议置信度低,请谨慎参考(详见下方质检面板)。
            </div>
          ) : null}
          <DecisionBoard
            decisions={decisionList}
            state={s(decisionsState)}
            degraded={degraded || insufficient}
            genericContext={genericContext}
            evidenceCount={evidenceCount}
            selectedIdx={selectedIdx}
            onSelect={setSelectedIdx}
          />
        </>
      )}

      {/* 对比矩阵(analysis 在 done/中断都取 → 正常渲染,各态自处理) */}
      <CompetitorComparison
        analysis={live ? analysis : null}
        state={s(analysisState)}
        highlightIds={highlightIds}
        evidenceCount={evidenceCount}
      />

      {/* 质检与自我纠错 */}
      <ContradictionPanel qc={live ? qc : null} qcState={s(qcState)} interrupted={interrupted} />

      {/* 审计轨迹(次要,折叠;trace 在 done/中断都取) */}
      <SelfAuditTrace trace={live ? trace : null} state={s(traceState)} />

      {/* 证据时间线(最低优先,折叠;evidence 在 done/中断都取) */}
      <EvidenceTimeline evidence={live ? evidenceList : null} state={s(evidenceState)} />

      {/* 证据原文 slide-over(全局单例) */}
      <EvidenceSlideOver />
    </div>
  )
}
