/**
 * SourceCards — 命中来源卡(2e §7,Plan C Task 15)。
 *
 * 数据 runStore.sources(到达序)。支撑度三色读 runStore.cellVerdicts
 * (`${dimension}|${competitor}`,qc 后才有);被策展剔除(droppedCells)标「已剔除」,
 * 其余未裁决标「待裁决」(C-D6)。stale 由 freshness.isStale 从 fetched_at 派生。
 * 点击 → drawerStore.openEvidence(REST 拉全文)。selector 返 raw。
 */
import { useRunStore } from '@/stores/runStore'
import { useDrawerStore } from '@/stores/drawerStore'
import { isStale } from '@/lib/freshness'
import { formatBeijingDate } from '@/lib/time'
import { VerdictDot } from '@/components/cockpit/VerdictDot'
import type { SSESourceData, SupportVerdict } from '@/types/api'

const EMPTY_S: SSESourceData[] = []

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url.slice(0, 40)
  }
}

export function SourceCards({
  round,
  embedded = false,
  newestFirst = false,
  limit,
}: {
  /** 只显该采集轮的来源(source.round);省略 = 全部。供执行时间轴折叠进采集行复用。 */
  round?: number
  /** embedded:去掉「命中来源 · N」标题与上间距,纯卡片列表(嵌进折叠条内 / LiveTracker 采集流)。 */
  embedded?: boolean
  /** newestFirst:最新到达的来源在前(LiveTracker 实时流:最新在顶,不滚也可见)。 */
  newestFirst?: boolean
  /** limit:最多显示前 N 条(配合 newestFirst = 最新 N 条);省略 = 全部。 */
  limit?: number
} = {}) {
  const sources = useRunStore((s) => s.sources)
  const verdicts = useRunStore((s) => s.cellVerdicts)
  const droppedKeys = useRunStore((s) => s.droppedCells)
  const openEvidence = useDrawerStore((s) => s.openEvidence)
  const all = sources.length ? sources : EMPTY_S
  const filtered = round === undefined ? all : all.filter((s) => s.round === round)
  // newestFirst / limit 在 render body 派生新数组(非 selector,无 zustand 新引用陷阱)。
  const ordered = newestFirst ? [...filtered].reverse() : filtered
  const list = limit !== undefined ? ordered.slice(0, limit) : ordered
  if (!list.length) return null
  return (
    <div className={`flex flex-col gap-[7px]${embedded ? '' : ' mt-[18px]'}`}>
      {!embedded && (
        <div className="mb-1 font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">
          命中来源 · {list.length}
        </div>
      )}
      {list.map((src) => {
        const key = `${src.dimension}|${src.competitor}`
        const v = verdicts[key] as SupportVerdict | undefined
        const dropped = droppedKeys.includes(key)
        const stale = isStale(src.fetched_at)
        return (
          <button
            key={src.evidence_id}
            onClick={() => openEvidence(src.evidence_id)}
            className="text-left bg-surface border border-border rounded-md px-[11px] py-[9px] hover:border-accent-line transition-colors"
          >
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-semibold text-ink leading-[1.3] truncate">
                  {src.source_title}
                </div>
                <div className="font-mono text-[10px] text-text-muted mt-px flex items-center gap-1.5 flex-wrap">
                  <span>{domainOf(src.source_url)}</span>
                  <span>·</span>
                  <span className={stale ? 'text-evidence-stale' : ''}>
                    {formatBeijingDate(src.fetched_at)}
                    {stale ? ' · 陈旧' : ''}
                  </span>
                </div>
              </div>
              <div className="flex-none flex items-center gap-[5px] font-mono text-[9.5px] text-text-muted whitespace-nowrap">
                {v ? (
                  <VerdictDot verdict={v} showLabel />
                ) : dropped ? (
                  <span className="text-v-uns">已剔除</span>
                ) : (
                  <span className="text-text-faint">待裁决</span>
                )}
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
