import { motion, AnimatePresence } from 'framer-motion'

interface DagRetryArcProps {
  d: string
  visible: boolean
  label?: string
  labelX?: number
  labelY?: number
}

/**
 * DESIGN.md 招牌时刻 ——「打回 = 反向扫掠 + 上游节点重亮」。
 * 弧从 qc 上方画起,贝塞尔上扬过顶,落在目标节点顶部。
 * 出现:opacity 0→1 + pathLength 0→1(1.2s 慢扫确保投影看得清)。
 */
export function DagRetryArc({ d, visible, label, labelX = 480, labelY = 60 }: DagRetryArcProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.g
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
        >
          <motion.path
            d={d}
            fill="none"
            stroke="var(--warning)"
            strokeWidth={2.5}
            strokeDasharray="6 4"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.2, ease: 'easeInOut' }}
            markerEnd="url(#arrowhead-warning)"
          />
          {label && (
            <text
              x={labelX}
              y={labelY}
              textAnchor="middle"
              fontSize={12}
              fontWeight={600}
              fill="var(--warning)"
              fontFamily="ui-monospace, monospace"
              pointerEvents="none"
            >
              {label}
            </text>
          )}
        </motion.g>
      )}
    </AnimatePresence>
  )
}
