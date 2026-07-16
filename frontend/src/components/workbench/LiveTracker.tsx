/**
 * LiveTracker — 「此刻」实时追踪卡(钉在实时引擎顶部,原地刷新,不依赖滚动)。
 *
 * 用户反馈:执行时间轴垫在累积面板(检索台/来源卡)后、默认在最下方,初始视口看不到
 * 进度更新,没有「实时追踪」的感觉。改法:把「当前在干什么」钉在右栏顶部常驻 + 原地
 * 刷新,时间轴退化为下方历史脊梁。用户初始位置不拖动即可看到进度变化。
 *
 * 阶段(phase)判定:
 *   - agent:nodes 里 running/retrying 的角色节点(采集/分析/撰写/质检),显阶段细节
 *     (采集=最新检索词+已抓取来源数;分析=矩阵 N/total 维进度条;撰写=报告打字 tail;质检=narrative)。
 *   - decide:qc 通过后的「决策合成」LLM 节点(可数十秒)。它不在 4-node DAG 模型里、无 NodeState,
 *     但 progress 会填 perAgentNarrative['decide'] → 据此识别,避免成为新的「冻结长阶段」。
 *   - startup:run 已 running 但尚未启动任何节点(首个 progress 前)。
 *   - gap:节点间交接的短暂空窗。
 *   - terminal:idle / 终态。
 * 统一带「已用时 Ns」(agent + decide 阶段),客户端墙钟锚点(demo 用历史假 ts,不能用 nodeStartTs)。
 *
 * selector 全部返 raw;派生在 useMemo / render body。
 */
import * as React from 'react'
import { useRunStore } from '@/stores/runStore'
import { useTypingStore } from '@/stores/typingStore'
import { SourceCards } from '@/components/workbench/SourceCards'
import { roleOf, ROLE_ORDER } from '@/lib/agentRoles'
import { dimensionLabel } from '@/lib/dimensions'
import { useElapsed } from '@/hooks/useElapsed'
import type { AgentId } from '@/types/agents'
import { NODE_NAMES, type NodeName } from '@/stores/runStore'
import type { SSEQueryData, SSESourceData, SSECellRowData } from '@/types/api'

type VerdictSummary = { supported: number; partial: number; dropped: number } | null

const EMPTY_NARR: string[] = []

function truncate(s: string, n: number): string {
  if (!s) return '—'
  return s.length > n ? s.slice(0, n) + '…' : s
}

// 一条一条「播放」批量到达的项:shown 从 0 起每 ms 递增至 target。后端常把 source / cell_row
// 在节点末尾紧凑批量 emit(并行 worker 扎堆),前端据此错峰逐条揭示 → 「一条一条播放」体感,
// 不再「搜集完一次性蹦出来」。target 缩小(切 run/阶段,子组件重挂)→ 复位。
function useStaggered(target: number, ms = 320): number {
  const [shown, setShown] = React.useState(0)
  React.useEffect(() => {
    if (shown > target) {
      // target 缩小时立即裁回,避免短暂展示上一阶段的额外项目。
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShown(target)
      return
    }
    if (shown >= target) return
    const id = setTimeout(() => setShown((s) => Math.min(s + 1, target)), ms)
    return () => clearTimeout(id)
  }, [shown, target, ms])
  return Math.min(shown, target)
}

// 工作日志 feed:agent 工作期 ticker 逐单元 emit 的 narrative(检索/抽取/对比/逐格校验步骤)
// 实时累积 → 显最近 max 条历史(最新由卡片 headline 行显,这里显其之前的,最新在顶)。
// 这是各长阶段(尤其分析抽取段 / 质检)「全程在动」的可靠信号,治「卡住」。
function WorkLog({ entries, color, max = 5 }: { entries: string[]; color: string; max?: number }) {
  const hist = entries.slice(0, -1) // 最新一条由 headline 显,避免重复
  if (!hist.length) return null
  const recent = hist.slice(-max).reverse() // 最新历史在顶
  return (
    <div className="mt-2 space-y-0.5">
      {recent.map((e, i) => {
        const absIdx = hist.length - 1 - i
        return (
          <div key={absIdx} className="flex items-start gap-1.5 text-[11px] leading-[1.45] text-text-muted">
            <span className="flex-none" style={{ color }} aria-hidden>
              ·
            </span>
            <span className="min-w-0 flex-1">{e}</span>
          </div>
        )
      })}
    </div>
  )
}

// agent_id → 节点名(两个 domain,不可假设同名;记忆 [[silent type-domain]])。
const NODE_OF_ROLE: Record<AgentId, NodeName> = {
  collector: 'collect',
  analyst: 'analyze',
  writer: 'write',
  qc: 'qc',
}

// 各角色「进行时」动词(放在 ● 角色名 之后)。
const PHASE_VERB: Record<AgentId, string> = {
  collector: '联网检索中',
  analyst: '对比分析中',
  writer: '撰写报告中',
  qc: '质检裁决中',
}

// 当前阶段描述符。
type Phase =
  | { kind: 'agent'; id: AgentId }
  | { kind: 'decide' }
  | { kind: 'startup' }
  | { kind: 'gap' }
  | { kind: 'terminal' }

// 镜像 StatusBar.fmtElapsed(格式一致;6 行 dup 可接受,避免为此动已验收的 StatusBar)。
function fmtElapsed(ms: number): string {
  const total = Math.floor(ms / 1000)
  if (total < 60) return `${total}s`
  const m = Math.floor(total / 60)
  if (m < 60) return `${m}m${(total % 60).toString().padStart(2, '0')}s`
  return `${Math.floor(m / 60)}h${(m % 60).toString().padStart(2, '0')}m`
}

function terminalLabel(status: string): string {
  switch (status) {
    case 'done':
      return '本轮调研已完成'
    case 'degraded':
      return '本轮调研完成 · 部分降级'
    case 'insufficient_evidence':
      return '证据不足 · 已如实标注'
    case 'cancelled':
      return '本轮调研已停止'
    case 'failed':
      return '本轮调研中断'
    default:
      return '待启动'
  }
}

export function LiveTracker({ totalDimensions = 0 }: { totalDimensions?: number }) {
  const status = useRunStore((s) => s.status)
  const nodes = useRunStore((s) => s.nodes)
  const narrative = useRunStore((s) => s.perAgentNarrative)
  const queries = useRunStore((s) => s.queries)
  const sources = useRunStore((s) => s.sources)
  const cellRows = useRunStore((s) => s.cellRows)
  const verdictSummary = useRunStore((s) => s.verdictSummary)
  const writerTyping = useTypingStore((s) => s.byAgent['writer']) ?? ''

  // 当前阶段:角色节点 running 优先;否则 run 仍 running 时区分 decide / 启动 / 交接 gap。
  const phase: Phase = (() => {
    if (status !== 'running') return { kind: 'terminal' }
    for (const id of ROLE_ORDER) {
      const ns = nodes[NODE_OF_ROLE[id]]
      if (ns === 'running' || ns === 'retrying') return { kind: 'agent', id }
    }
    // 无角色在跑但 run 仍 running:
    if ((narrative['decide']?.length ?? 0) > 0) return { kind: 'decide' } // 决策合成(qc 后,可数十秒)
    if (NODE_NAMES.every((n) => nodes[n] === 'idle')) return { kind: 'startup' } // 尚未启动任何节点
    return { kind: 'gap' } // 节点间交接空窗
  })()

  // 客户端墙钟锚点:仅 agent / decide 这类「持续工作」阶段计时;阶段切换重置(每段独立计时)。
  const phaseKey = phase.kind === 'agent' ? `agent:${phase.id}` : phase.kind
  const [anchor, setAnchor] = React.useState<{ key: string; t: number } | null>(null)
  React.useEffect(() => {
    if (phase.kind !== 'agent' && phase.kind !== 'decide') {
      // 非持续工作阶段不显示上一阶段计时。
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAnchor(null)
      return
    }
    // 阶段切换时建立新的客户端墙钟锚点。
    setAnchor((prev) => (prev && prev.key === phaseKey ? prev : { key: phaseKey, t: Date.now() }))
  }, [phaseKey, phase.kind])
  const elapsed = useElapsed(anchor ? anchor.t : null)

  // 简单态(终态 / 启动 / 交接 gap):一行状态,不跳动。
  if (phase.kind === 'terminal' || phase.kind === 'startup' || phase.kind === 'gap') {
    const label =
      phase.kind === 'terminal'
        ? terminalLabel(status)
        : phase.kind === 'startup'
          ? '正在唤醒研究团队…'
          : '正在衔接下一步…'
    return (
      <div className="flex-none mx-[18px] mt-3 rounded-lg border border-border bg-surface px-3.5 py-3">
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">此刻</div>
        <div className="mt-1 text-[13px] font-semibold text-text-primary">{label}</div>
      </div>
    )
  }

  // decide:系统「决策合成」阶段(中性 accent 色,带计时 + narrative,治 decide 长阶段冻结)。
  if (phase.kind === 'decide') {
    const latest = narrative['decide']?.at(-1) ?? '正在基于证据生成决策建议'
    return (
      <div
        className="flex-none mx-[18px] mt-3 rounded-lg border bg-surface px-3.5 py-3"
        style={{ borderColor: 'var(--accent-line)' }}
      >
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">此刻</div>
        <div className="mt-1.5 flex items-center gap-2">
          <span
            className="h-[8px] w-[8px] flex-none rounded-full bg-accent animate-pulse motion-reduce:animate-none"
            aria-hidden
          />
          <span className="text-[13px] font-semibold text-text-primary">决策合成</span>
          <span className="text-[12px] text-text-muted">生成决策建议中</span>
          <span className="ml-auto flex-none font-mono text-[11px] tabular-nums text-text-muted">
            已用时 {fmtElapsed(elapsed)}
          </span>
        </div>
        <div className="mt-1.5 text-[12px] leading-[1.5] text-text-primary" aria-live="polite">
          {latest}
        </div>
      </div>
    )
  }

  // agent 角色阶段:身份色卡 + 阶段实时细节。
  const role = roleOf(phase.id)
  const latest = narrative[phase.id]?.at(-1) ?? null
  return (
    <div
      className="flex-none mx-[18px] mt-3 rounded-lg border bg-surface px-3.5 py-3"
      style={{ borderColor: role?.line ?? 'var(--border)' }}
    >
      <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">此刻</div>
      {/* 行1:● 角色 · 动词 · 已用时(右对齐计时,每 100ms 跳) */}
      <div className="mt-1.5 flex items-center gap-2">
        <span
          className="h-[8px] w-[8px] flex-none rounded-full animate-pulse motion-reduce:animate-none"
          style={{ background: role?.col ?? 'var(--accent)' }}
          aria-hidden
        />
        <span
          className="text-[13px] font-semibold"
          style={{ color: role?.col ?? 'var(--text-primary)' }}
        >
          {role?.name ?? '系统'}
        </span>
        <span className="text-[12px] text-text-muted">{PHASE_VERB[phase.id]}</span>
        <span className="ml-auto flex-none font-mono text-[11px] tabular-nums text-text-muted">
          已用时 {fmtElapsed(elapsed)}
        </span>
      </div>
      {/* 行2:最新进度 narrative(progress event 持续刷新 → 长阶段也在动) */}
      {latest && (
        <div className="mt-1.5 text-[12px] leading-[1.5] text-text-primary" aria-live="polite">
          {latest}
        </div>
      )}
      {/* 行3:阶段中间产物(动态流式 + 工作日志 feed) */}
      <PhaseDetail
        active={phase.id}
        queries={queries}
        sources={sources}
        cellRows={cellRows}
        verdictSummary={verdictSummary}
        totalDimensions={totalDimensions}
        writerTyping={writerTyping}
        narrative={narrative[phase.id] ?? EMPTY_NARR}
      />
    </div>
  )
}

function PhaseDetail({
  active,
  queries,
  sources,
  cellRows,
  verdictSummary,
  totalDimensions,
  writerTyping,
  narrative,
}: {
  active: AgentId
  queries: SSEQueryData[]
  sources: SSESourceData[]
  cellRows: Record<string, SSECellRowData>
  verdictSummary: VerdictSummary
  totalDimensions: number
  writerTyping: string
  narrative: string[]
}) {
  // 各阶段拆成独立子组件 → 各自持有 useStaggered hook;切阶段时子组件重挂,错峰进度自动复位。
  if (active === 'collector') return <CollectDetail queries={queries} sources={sources} />
  if (active === 'analyst')
    return <AnalyzeDetail cellRows={cellRows} totalDimensions={totalDimensions} narrative={narrative} />
  if (active === 'writer') return <WriteDetail writerTyping={writerTyping} />
  return <QcDetail cellRows={cellRows} verdictSummary={verdictSummary} narrative={narrative} />
}

// 采集员:最新检索词 + 命中来源「一条一条播放」(错峰揭示,最新在顶,可点溯源)。
function CollectDetail({ queries, sources }: { queries: SSEQueryData[]; sources: SSESourceData[] }) {
  const shown = useStaggered(sources.length)
  const latestQuery = queries[0]?.query_text
  return (
    <div className="mt-2 space-y-1.5">
      {latestQuery && (
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-text-primary">
          <span className="flex-none text-accent">▸</span>
          <span className="min-w-0 flex-1 truncate">{latestQuery}</span>
        </div>
      )}
      <div className="font-mono text-[10.5px] text-text-muted">
        命中来源 · {shown}
        {shown < sources.length ? ` / ${sources.length}` : ''}
      </div>
      {sources.length > 0 ? (
        <div className="max-h-[200px] overflow-y-auto pr-0.5">
          <SourceCards embedded newestFirst limit={shown} />
        </div>
      ) : (
        <div className="text-[11px] italic text-text-muted">正在联网检索,等待首批来源…</div>
      )}
    </div>
  )
}

// 分析员:工作日志 feed(抽取/对比步骤全程流)+ 对比矩阵逐维「一条一条」填充(错峰)。
function AnalyzeDetail({
  cellRows,
  totalDimensions,
  narrative,
}: {
  cellRows: Record<string, SSECellRowData>
  totalDimensions: number
  narrative: string[]
}) {
  const dims = Object.keys(cellRows)
  const shownDims = useStaggered(dims.length, 500)
  const done = dims.length
  const total = totalDimensions || 0
  const capped = total > 0 ? Math.min(done, total) : done
  const pct = total > 0 ? Math.round((capped / total) * 100) : 0
  const visible = dims.slice(0, shownDims)
  return (
    <div className="mt-2">
      <div className="mb-1 flex items-center justify-between font-mono text-[10.5px] text-text-muted">
        <span>对比矩阵</span>
        <span className="tabular-nums">{total > 0 ? `${capped}/${total} 维` : `已成型 ${done} 维`}</span>
      </div>
      {total > 0 && (
        <div className="h-[5px] w-full overflow-hidden rounded-full bg-surface-subtle">
          <div
            className="h-full rounded-full transition-[width] duration-500"
            style={{ width: `${pct}%`, background: 'var(--id-analyst)' }}
          />
        </div>
      )}
      {/* 抽取/对比步骤实时流 —— 抽画像阶段(尚无 cell)也全程在动,治「卡住」。 */}
      <WorkLog entries={narrative} color="var(--id-analyst)" max={4} />
      {/* 矩阵逐维填充:错峰一条条出现(后端并行扎堆到达 → 前端逐维揭示)。 */}
      {visible.length > 0 && (
        <div className="mt-2 max-h-[170px] space-y-1.5 overflow-y-auto pr-0.5">
          {visible.map((dim) => {
            const row = cellRows[dim]
            return (
              <div key={dim} className="rounded border border-border bg-surface px-2 py-1.5 text-[11px] leading-[1.5]">
                <span className="font-semibold" style={{ color: 'var(--id-analyst)' }}>
                  {dimensionLabel(dim)}
                </span>
                {row.status === 'failed' ? (
                  <span className="text-text-faint"> · 分析失败</span>
                ) : row.status === 'empty' || row.cells.length === 0 ? (
                  <span className="text-text-faint"> · 未找到公开数据</span>
                ) : (
                  <div className="mt-0.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-text-muted">
                    {row.cells.map((c) => (
                      <span key={c.competitor}>
                        <span className="text-text-primary">{c.competitor}</span> {truncate(c.value, 10)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// 撰写员:报告草稿实时增长。CSS justify-end 裁顶 → 最新文字永在底部可见,无需自动滚。
// 首段未到(insight 流式有 ~40s TTFB,真 run 实测;body 是确定性生成不流前端)→ 显脉冲骨架,
// 诚实表达「报告正在成形」,不伪造内容(工作期确无可流的中间产物,见 writer.py)。
function WriteDetail({ writerTyping }: { writerTyping: string }) {
  if (!writerTyping) {
    return (
      <div className="mt-2 rounded-md bg-surface-subtle px-2.5 py-2">
        <div className="flex items-center gap-1.5 text-[11.5px] italic text-text-muted">
          <span
            className="h-[6px] w-[6px] flex-none rounded-full animate-pulse motion-reduce:animate-none"
            style={{ background: 'var(--id-writer)' }}
            aria-hidden
          />
          撰写员正在综合判断,起草首段(约 30–40 秒)…
        </div>
        <div className="mt-2 space-y-1.5" aria-hidden>
          {['90%', '78%', '85%', '70%'].map((w, i) => (
            <div
              key={i}
              className="h-[8px] rounded bg-border animate-pulse motion-reduce:animate-none"
              style={{ width: w }}
            />
          ))}
        </div>
      </div>
    )
  }
  return (
    <div className="mt-2 flex max-h-[200px] flex-col justify-end overflow-hidden rounded-md bg-surface-subtle px-2.5 py-2">
      <div className="whitespace-pre-wrap text-[11.5px] leading-[1.55] text-text-primary">
        {writerTyping}
        <span
          className="ml-px inline-block h-[13px] w-[2px] animate-pulse align-[-2px] motion-reduce:animate-none"
          style={{ background: 'var(--id-writer)' }}
        />
      </div>
    </div>
  )
}

// 质检员:逐格校验工作日志 feed(每格 emit「质检校验 竞品·维度」全程流)+ 汇总(到达即显)。
// verdict 三色在 qc 完成后才到(不在 qc 期流,不可造)→ qc 期显逐格校验流,汇总到了再显计数。
function QcDetail({
  cellRows,
  verdictSummary,
  narrative,
}: {
  cellRows: Record<string, SSECellRowData>
  verdictSummary: VerdictSummary
  narrative: string[]
}) {
  const dims = Object.keys(cellRows)
  const cellCount = dims.reduce((n, d) => n + cellRows[d].cells.length, 0)
  return (
    <div className="mt-2 space-y-1.5">
      <div className="font-mono text-[10.5px] text-text-muted">
        正在逐格校验佐证充分度{cellCount > 0 ? ` · 共 ${cellCount} 格` : ''}
      </div>
      {verdictSummary && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] tabular-nums">
          <span className="text-v-sup">充分 {verdictSummary.supported}</span>
          <span className="text-text-muted">部分 {verdictSummary.partial}</span>
          <span className="text-v-uns">剔除 {verdictSummary.dropped}</span>
        </div>
      )}
      <WorkLog entries={narrative} color="var(--id-qc)" max={6} />
    </div>
  )
}
