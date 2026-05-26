import { motion } from 'framer-motion'

export type EdgeState = 'latent' | 'active' | 'retry-flowing'

interface DagEdgeProps {
  d: string
  state: EdgeState
}

const EDGE_STROKE: Record<EdgeState, string> = {
  latent: 'var(--border)',
  active: 'var(--accent)',
  'retry-flowing': 'var(--warning)',
}

export function DagEdge({ d, state }: DagEdgeProps) {
  return (
    <motion.path
      d={d}
      fill="none"
      stroke={EDGE_STROKE[state]}
      strokeWidth={state === 'latent' ? 1.5 : 3}
      strokeLinecap="round"
      animate={{ stroke: EDGE_STROKE[state] }}
      transition={{ duration: 0.5 }}
      markerEnd={state === 'latent' ? 'url(#arrowhead-muted)' : 'url(#arrowhead)'}
    />
  )
}
