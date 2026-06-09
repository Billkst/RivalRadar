/**
 * RetryLoop — 重试环(2e §10,Plan C Task 17)。
 *
 * 青绿单回环(framer-motion 一次性 spin,无 repeat,符合 DESIGN.md「单次不无限抖动」)。
 * 「第 N 轮 · 证据 X→Y」来自 runStore.evidenceDeltas(round>0 的增量)。仅有 retry 时显。
 * prefers-reduced-motion 不转。selector 返 raw,空态用 module-level 稳定常量。
 */
import { useRunStore } from '@/stores/runStore'
import { motion } from 'framer-motion'
import type { SSEEvidenceDeltaData } from '@/types/api'

const EMPTY_D: SSEEvidenceDeltaData[] = []
const REDUCE =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export function RetryLoop() {
  const deltas = useRunStore((s) => s.evidenceDeltas)
  const list = deltas.length ? deltas : EMPTY_D
  const retryRounds = list.filter((d) => d.round > 0)
  if (!retryRounds.length) return null
  const last = retryRounds[retryRounds.length - 1]
  const before = last.total_count - last.added_count
  return (
    <div
      className="border rounded-lg px-[14px] py-3 mt-2.5 relative overflow-hidden"
      style={{ borderColor: 'var(--accent-line)', background: 'var(--accent-soft)' }}
    >
      <div className="flex items-center gap-2 text-[12px] font-semibold" style={{ color: 'var(--accent-deep)' }}>
        <motion.span
          className="flex-none w-4 h-4 text-accent"
          animate={REDUCE ? {} : { rotate: 360 }}
          transition={{ duration: 1, ease: 'easeOut' }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16">
            <path d="M3 8a5 5 0 1 1 1.6 3.7" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" />
            <path
              d="M3 4.5v3.5h3.5"
              stroke="currentColor"
              strokeWidth="1.6"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </motion.span>
        自我纠错回环 · 第 {last.round + 1} 轮补证
      </div>
      <div className="text-[11.5px] text-text-primary leading-[1.5] mt-[5px]">
        系统不接受弱结论:一条回环从<b>质检员</b>绕回<b>采集员</b>定向补证,补全后自动复检。
      </div>
      <div
        className="inline-flex items-center gap-1.5 mt-[9px] font-mono text-[11px] font-semibold text-white px-[11px] py-1 rounded-[13px] shadow-panel"
        style={{ background: 'var(--accent)' }}
      >
        <span>↻</span>
        <span>
          第 {last.round + 1} 轮 · 证据 {before}→{last.total_count}
        </span>
      </div>
    </div>
  )
}
