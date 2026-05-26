import { motion } from 'framer-motion'
import type { NodeState } from '@/stores/runStore'

interface DagNodeProps {
  name: string
  label: string
  x: number
  y: number
  r: number
  state: NodeState
  onOpen?: () => void
}

// DESIGN.md tokens (CSS var names — fill resolves at runtime via tailwind config).
const STATE_FILL: Record<NodeState, string> = {
  idle: 'var(--surface-subtle)',
  running: 'var(--info)',
  done: 'var(--accent)',
  failed: 'var(--error)',
  retrying: 'var(--warning)',
}

const STATE_STROKE: Record<NodeState, string> = {
  idle: 'var(--border)',
  running: 'var(--info)',
  done: 'var(--accent)',
  failed: 'var(--error)',
  retrying: 'var(--warning)',
}

export function DagNode({ name, label, x, y, r, state, onOpen }: DagNodeProps) {
  const isActive = state === 'running' || state === 'retrying'
  const isShaking = state === 'retrying'

  return (
    <motion.g
      onClick={onOpen}
      style={{ cursor: onOpen ? 'pointer' : 'default' }}
      animate={isShaking ? { x: [0, -3, 3, -2, 2, 0] } : { x: 0 }}
      transition={
        isShaking ? { duration: 0.4, repeat: Infinity, repeatDelay: 0.5 } : { duration: 0.3 }
      }
    >
      <motion.circle
        cx={x}
        cy={y}
        animate={{
          r: isActive ? [r, r + 4, r] : r,
        }}
        transition={{
          duration: 1,
          repeat: isActive ? Infinity : 0,
          ease: 'easeInOut',
        }}
        fill={STATE_FILL[state]}
        fillOpacity={state === 'idle' ? 0.6 : 0.22}
        stroke={STATE_STROKE[state]}
        strokeWidth={state === 'idle' ? 1.5 : 2.5}
      />
      <text
        x={x}
        y={y - 4}
        textAnchor="middle"
        fontSize={18}
        fontWeight={600}
        fill="var(--text-primary)"
        pointerEvents="none"
      >
        {label}
      </text>
      <text
        x={x}
        y={y + 14}
        textAnchor="middle"
        fontSize={11}
        fill="var(--text-muted)"
        fontFamily="ui-monospace, monospace"
        pointerEvents="none"
      >
        {name}
      </text>
    </motion.g>
  )
}
