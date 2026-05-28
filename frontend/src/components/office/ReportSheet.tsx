/**
 * ReportSheet — 底部 drawer 报告显示(plan v3.2 §6 Epic 6.2 + DESIGN.md
 * §虚拟办公室 layout)。
 *
 * 默认 collapsed 80px(露标题 + 字数 / 状态);click expand 60vh 渲染报告全文。
 *
 * 数据源(本 commit MVP):
 *   - useRunStore.writerReport — writer agent chunks 持久累积(D5 加的新字段)
 *   - typingStore.clear (D19 #4) 不影响 writerReport —— ReportSheet 永远显示
 *     完整 writer 输出,不会被 progress 'done' 清空导致空白
 *   - production 真打 LLM:writer streaming output 实时累积
 *   - D6 polish:GET /run/:id/report API 替换 fake replay 模式
 *
 * markdown 渲染:本 commit MVP 用 <pre> + whitespace-pre-wrap 保 \n 和 ## 形态
 *   (react-markdown / unified 渲染真 markdown + 引用 chip 留 D19)。
 */
import * as React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useRunStore } from '@/stores/runStore'

export function ReportSheet() {
  const [expanded, setExpanded] = React.useState(false)
  const writerReport = useRunStore((s) => s.writerReport)
  const status = useRunStore((s) => s.status)

  const hasContent = writerReport.length > 0
  const isDone = status === 'done'

  return (
    <motion.section
      className="overflow-hidden rounded-lg border border-border bg-surface"
      animate={{ height: expanded ? '60vh' : 80 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      aria-label="竞品分析报告"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between p-3 text-left hover:bg-surface-subtle"
        aria-expanded={expanded}
      >
        <div className="min-w-0">
          <div className="text-sm font-semibold text-text-primary">竞品分析报告</div>
          <div className="text-xs text-text-muted">
            {hasContent
              ? `${writerReport.length} 字 · ${isDone ? '已完成' : '撰写中…'}`
              : '等待 writer agent 输出…'}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span>{expanded ? '收起' : '展开'}</span>
          <span
            className="inline-block"
            style={{
              transform: expanded ? 'rotate(180deg)' : 'none',
              transition: 'transform 200ms',
            }}
            aria-hidden
          >
            ▼
          </span>
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-y-auto border-t border-border p-4"
            style={{ height: 'calc(60vh - 56px)' }}
          >
            {hasContent ? (
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-text-primary">
                {writerReport}
              </pre>
            ) : (
              <div className="text-sm italic text-text-muted">
                Writer agent 还没开始撰写报告。点 dev "🧪 fake SSE → Real" 跑一遍演示,
                或等真打 LLM 走到 writer 阶段后这里会实时累积。
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  )
}
