/**
 * SpeechBubble — agent 头顶 thought bubble + typing 光标(plan v3.2 §6 office 组件)。
 *
 * 设计要点(DESIGN.md §关键组件 office 段):
 *   1. 圆角 12px + `var(--speech-bg)` 底 + 8px shadow
 *   2. 13px IBM Plex Sans + `var(--text-primary)` 字色
 *   3. typing 光标 `var(--typing-cursor)` 闪烁 1Hz(完成后变实色不再闪)
 *   4. max-width 240px,line-clamp 3 行 + LiveFeedPanel 看全文
 *   5. framer-motion 200ms enter(opacity + scale 0.95→1),exit 同(被替换或 idle 时)
 *
 * 数据源混合显示策略:
 *   - typingText 非空(chunk events 累积)→ 显示 typing text + cursor
 *   - typingText 空但 perAgentNarrative 有(progress events 累积)→ 显示最后一条 summary
 *   - 两者都空 → 不渲染(返 null)
 *
 * Position:absolute 定位,父容器 relative;`xPercent`/`yPercent` 是百分比
 * (相对 parent),transform translate(-50%, -100%) 让 bubble 底边中点对齐
 * (xPercent%, yPercent%) — 适合放 character mount 正上方。
 */
import { motion, AnimatePresence } from 'framer-motion'
import { useTypingStore } from '@/stores/typingStore'
import { useRunStore } from '@/stores/runStore'

interface SpeechBubbleProps {
  agentId: string
  /** 0-100 — 相对 parent container 宽度的百分比 */
  xPercent: number
  /** 0-100 — 相对 parent container 高度的百分比 */
  yPercent: number
  /** 强制隐藏(如 agent idle 时);默认 true 跟随数据展示 */
  visible?: boolean
}

export function SpeechBubble({ agentId, xPercent, yPercent, visible = true }: SpeechBubbleProps) {
  const typingText = useTypingStore((s) => s.byAgent[agentId] || '')
  const narratives = useRunStore((s) => s.perAgentNarrative[agentId] || [])

  const lastNarrative = narratives.length > 0 ? narratives[narratives.length - 1] : ''
  const text = typingText || lastNarrative
  const isTyping = !!typingText

  return (
    <AnimatePresence mode="wait">
      {visible && text && (
        <motion.div
          key={agentId}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          className="pointer-events-none absolute z-10 max-w-[240px] rounded-xl border border-border px-3 py-2 text-[13px] leading-snug shadow-md"
          style={{
            left: `${xPercent}%`,
            top: `${yPercent}%`,
            transform: 'translate(-50%, -100%)',
            background: 'var(--speech-bg)',
            color: 'var(--text-primary)',
            fontFamily: 'IBM Plex Sans, IBM Plex Sans SC, system-ui, sans-serif',
          }}
          role="status"
          aria-live="polite"
          aria-label={`${agentId} agent narrative`}
        >
          <span className="line-clamp-3">{text}</span>
          {isTyping && <TypingCursor />}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function TypingCursor() {
  return (
    <motion.span
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      className="ml-0.5 inline-block h-[14px] w-[2px] translate-y-0.5 align-middle"
      style={{ background: 'var(--typing-cursor)' }}
      aria-hidden
    />
  )
}
