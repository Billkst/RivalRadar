import { Pause, Play, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { retryIndexOf, useRunStore, type NodeName } from '@/stores/runStore'
import { MAIN_EDGES, NODE_LAYOUTS, RETRY_ARCS } from './dagLayout'
import { DagEdge, type EdgeState } from './DagEdge'
import { DagNode } from './DagNode'
import { DagRetryArc } from './DagRetryArc'

interface DagCanvasProps {
  onNodeClick?: (name: string) => void
}

/**
 * 实时 DAG canvas — money shot 主体(spec §11.4 + DESIGN.md Motion)。
 *
 * 状态机:
 *   - main edge active = source node 已 done(画路径走过)
 *   - main edge retry-flowing = destination 处于 retrying
 *   - retry arc visible = qc verdict 是 retry_X 或对应 node state = retrying
 *
 * Play/Pause/Reset 按钮 Task 14 接入(目前 disabled — vertical slice 不阻断)。
 */
export function DagCanvas({ onNodeClick }: DagCanvasProps) {
  const nodes = useRunStore((s) => s.nodes)
  const events = useRunStore((s) => s.events)
  const qcVerdict = useRunStore((s) => s.qcVerdict)
  const retryCount = useRunStore((s) => s.retryCount)
  const status = useRunStore((s) => s.status)

  const isRunning = status === 'running'

  function edgeState(from: NodeName, to: NodeName): EdgeState {
    if (nodes[to] === 'retrying') return 'retry-flowing'
    if (nodes[from] !== 'idle') return 'active'
    return 'latent'
  }

  const showRetryCollect = qcVerdict === 'retry_collect' || nodes.collect === 'retrying'
  const showRetryAnalyze = qcVerdict === 'retry_analyze' || nodes.analyze === 'retrying'

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="text-xs uppercase tracking-wide text-text-muted">
          实时 DAG · 4 Agent 协作
        </div>
        <div className="flex items-center gap-2">
          {retryCount > 0 && (
            <span className="rounded bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
              retry × {retryCount}
            </span>
          )}
          <Button variant="ghost" size="sm" disabled title="Play/Pause (Task 14)">
            {isRunning ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
          </Button>
          <Button variant="ghost" size="sm" disabled title="Reset (Task 14)">
            <RefreshCw className="h-3 w-3" />
          </Button>
        </div>
      </div>
      <svg viewBox="0 0 960 320" className="h-auto w-full">
        <defs>
          <marker
            id="arrowhead"
            viewBox="0 -5 10 10"
            refX="8"
            refY="0"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M0,-5 L10,0 L0,5" fill="var(--accent)" />
          </marker>
          <marker
            id="arrowhead-muted"
            viewBox="0 -5 10 10"
            refX="8"
            refY="0"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M0,-5 L10,0 L0,5" fill="var(--border)" />
          </marker>
          <marker
            id="arrowhead-warning"
            viewBox="0 -5 10 10"
            refX="8"
            refY="0"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M0,-5 L10,0 L0,5" fill="var(--warning)" />
          </marker>
        </defs>

        {MAIN_EDGES.map((e) => (
          <DagEdge key={`${e.from}-${e.to}`} d={e.d} state={edgeState(e.from, e.to)} />
        ))}

        <DagRetryArc
          d={RETRY_ARCS[0].d}
          labelX={RETRY_ARCS[0].labelX}
          labelY={RETRY_ARCS[0].labelY}
          visible={showRetryCollect}
          label={
            showRetryCollect
              ? `retry_collect · #${retryIndexOf(events, 'collect', events.length)}`
              : undefined
          }
        />
        <DagRetryArc
          d={RETRY_ARCS[1].d}
          labelX={RETRY_ARCS[1].labelX}
          labelY={RETRY_ARCS[1].labelY}
          visible={showRetryAnalyze}
          label={
            showRetryAnalyze
              ? `retry_analyze · #${retryIndexOf(events, 'analyze', events.length)}`
              : undefined
          }
        />

        {/* Nodes drawn on top so they sit above edges + arcs */}
        {NODE_LAYOUTS.map((n) => (
          <DagNode key={n.name} {...n} state={nodes[n.name]} onOpen={() => onNodeClick?.(n.name)} />
        ))}
      </svg>
    </div>
  )
}
