/**
 * cockpitStore — 左决策面的 REST 数据编排(Epic 5)。
 *
 * 设计要点:
 *   1. **渐进 fetch**(plan §5.1):analysis 在 analyze 节点完成即取;qc/insight/
 *      decisions/trace/evidence-list 在 run done 时取。每资源独立 LoadState,
 *      面板按状态渲染专属 skeleton(非通用 spinner)。
 *   2. **idempotent**:load() 只在 state==='idle' 时触发;sync 可被 effect 反复调
 *      (status / analyzeReady 变化)不会重复打 API。
 *   3. **404 = 'absent'**(老 run / 进行中 run 无表行)区别于 'error'(网络/5xx);
 *      面板空态 ≠ 错误态。
 *   4. **demo 路径**(isDemoRun):同一状态机,fetcher 换成 Promise.resolve(fixture),
 *      零网络依赖(demo day Clash 卡 / backend down 仍渲染决策面)。
 *   5. **evidence-list 一次性 seed evidenceStore**(plan §5.2)→ EvidencePill cache
 *      hit,消 per-pill N+1。
 *   6. **过期结果丢弃**:fetcher resolve 时若 runId 已切走,丢弃(防 race 把旧 run
 *      数据写进新 run)。
 *
 * Codex #8 已验证不成立:backend 各节点 save_*+commit() 在节点返回前完成,SSE
 * node/done event 在 astream yield 完成 chunk 后才发 → commit 严格先于事件;
 * 前端按 node/done 触发 fetch 读到的必是已提交数据(read-before-commit 不会发生)。
 */
import { create } from 'zustand'
import {
  ApiError,
  fetchAnalysis,
  fetchDecisions,
  fetchInsight,
  fetchQc,
  fetchRunEvidence,
  fetchTrace,
} from '@/lib/api'
import { useEvidenceStore } from '@/stores/evidenceStore'
import { getDemoCockpitData, isDemoRun } from '@/lib/demoFixture'
import type { RunStatus } from '@/stores/runStore'
import type {
  CompetitorAnalysis,
  DecisionSet,
  Evidence,
  ReportInsight,
  SanitizedQCResult,
  TraceEntry,
} from '@/types/api'

/** idle:未触发 · loading:在飞 · loaded:成功 · absent:404 空态 · error:网络/5xx。 */
export type LoadState = 'idle' | 'loading' | 'loaded' | 'absent' | 'error'

interface CockpitData {
  runId: string | null
  analysis: CompetitorAnalysis | null
  decisions: DecisionSet | null
  insight: ReportInsight | null
  qc: SanitizedQCResult | null
  evidenceList: Evidence[] | null
  trace: TraceEntry[] | null
  analysisState: LoadState
  decisionsState: LoadState
  insightState: LoadState
  qcState: LoadState
  evidenceState: LoadState
  traceState: LoadState
}

interface CockpitStore extends CockpitData {
  /** 由 DecisionSurface effect 调,依据 run 状态渐进取数(idempotent)。 */
  sync: (args: { runId: string; status: RunStatus; analyzeReady: boolean }) => void
  reset: () => void
}

const initial = (): CockpitData => ({
  runId: null,
  analysis: null,
  decisions: null,
  insight: null,
  qc: null,
  evidenceList: null,
  trace: null,
  analysisState: 'idle',
  decisionsState: 'idle',
  insightState: 'idle',
  qcState: 'idle',
  evidenceState: 'idle',
  traceState: 'idle',
})

export const useCockpitStore = create<CockpitStore>((set, get) => {
  /** 单资源加载:idle 守护 + loading/loaded/absent/error 状态机 + 过期丢弃。 */
  function load(opts: {
    runId: string
    stateField: keyof CockpitData
    dataField: keyof CockpitData
    fetcher: (runId: string) => Promise<unknown>
    onData?: (data: unknown) => void
  }): void {
    if (get()[opts.stateField] !== 'idle') return
    set({ [opts.stateField]: 'loading' } as Partial<CockpitStore>)
    opts
      .fetcher(opts.runId)
      .then((data) => {
        if (get().runId !== opts.runId) return // 切 run 了,丢弃过期结果
        set({ [opts.dataField]: data, [opts.stateField]: 'loaded' } as Partial<CockpitStore>)
        opts.onData?.(data)
      })
      .catch((err) => {
        if (get().runId !== opts.runId) return
        const absent = err instanceof ApiError && err.status === 404
        set({ [opts.stateField]: absent ? 'absent' : 'error' } as Partial<CockpitStore>)
      })
  }

  return {
    ...initial(),

    sync: ({ runId, status, analyzeReady }) => {
      if (get().runId !== runId) set({ ...initial(), runId })

      const demo = isDemoRun(runId) ? getDemoCockpitData() : null
      const done =
        status === 'done' || status === 'degraded' || status === 'insufficient_evidence'
      const interrupted = status === 'failed' || status === 'cancelled'
      // 中断 run 也取累积型产物(evidence / trace / analysis 在节点完成时已落库),
      // 诚实展示已得;qc/insight/decisions 依赖完整节点链,仅 done 取(中断时 404→absent)。
      const terminal = done || interrupted

      // analysis 渐进:analyze 节点完成即可(或 terminal 补偿 deep-link/replay/中断)。
      if (analyzeReady || terminal) {
        load({
          runId,
          stateField: 'analysisState',
          dataField: 'analysis',
          fetcher: demo ? () => Promise.resolve(demo.analysis) : fetchAnalysis,
        })
      }

      // 累积型产物:done 或中断都取(中断 run 诚实展示已采集证据 + 审计轨迹)。
      if (terminal) {
        load({
          runId, stateField: 'traceState', dataField: 'trace',
          fetcher: demo ? () => Promise.resolve(demo.trace) : fetchTrace,
        })
        load({
          runId, stateField: 'evidenceState', dataField: 'evidenceList',
          fetcher: demo ? () => Promise.resolve(demo.evidence) : fetchRunEvidence,
          onData: (data) => useEvidenceStore.getState().seed(data as Evidence[]),
        })
      }

      // 决策链产物:仅 done 取(中断 run 这些节点未跑完 → 不取,面板显中断态)。
      if (done) {
        load({
          runId, stateField: 'qcState', dataField: 'qc',
          fetcher: demo ? () => Promise.resolve(demo.qc) : fetchQc,
        })
        load({
          runId, stateField: 'insightState', dataField: 'insight',
          fetcher: demo ? () => Promise.resolve(demo.insight) : fetchInsight,
        })
        load({
          runId, stateField: 'decisionsState', dataField: 'decisions',
          fetcher: demo ? () => Promise.resolve(demo.decisions) : fetchDecisions,
        })
      }
    },

    reset: () => set(initial()),
  }
})
