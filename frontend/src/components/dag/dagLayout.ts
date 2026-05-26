/**
 * DAG layout — 4 节点固定坐标 + 5 边路径(3 主流 + 2 retry 弧)。
 * SVG viewBox 960×320,水平排列,DESIGN.md 节奏 700-1100ms。
 *
 * Spec §11.4: 严格 4 节点(collect/analyze/write/qc)— 不画 finalize 第 5 节点。
 * Codex #6: retry_collect + retry_analyze 双弧都画(plan v2 从 stretch 移到 core)。
 */
import type { NodeName } from '@/stores/runStore'

export interface NodeLayout {
  name: NodeName
  label: string
  x: number
  y: number
  r: number
}

export const NODE_LAYOUTS: NodeLayout[] = [
  { name: 'collect', label: '采集', x: 160, y: 200, r: 44 },
  { name: 'analyze', label: '分析', x: 400, y: 200, r: 44 },
  { name: 'write', label: '撰写', x: 640, y: 200, r: 44 },
  { name: 'qc', label: '质检', x: 880, y: 200, r: 44 },
]

// Main edge path endpoints account for node radius so the line doesn't enter the circle.
export const MAIN_EDGES = [
  { from: 'collect' as const, to: 'analyze' as const, d: 'M 204 200 L 356 200' },
  { from: 'analyze' as const, to: 'write' as const, d: 'M 444 200 L 596 200' },
  { from: 'write' as const, to: 'qc' as const, d: 'M 684 200 L 836 200' },
]

// Retry arcs: qc → collect (long arc up & over) / qc → analyze (shorter arc).
// Starts at qc's top (y = 200 - 44 = 156), curves up to y ≈ 60-90, lands on
// target's top. Bezier control points pull each end vertically for smooth arc.
export const RETRY_ARCS = [
  {
    name: 'retry_collect' as const,
    from: 'qc' as const,
    to: 'collect' as const,
    d: 'M 880 156 C 880 60, 160 60, 160 156',
    labelX: 520,
    labelY: 50,
  },
  {
    name: 'retry_analyze' as const,
    from: 'qc' as const,
    to: 'analyze' as const,
    d: 'M 880 156 C 880 90, 400 90, 400 156',
    labelX: 640,
    labelY: 80,
  },
]
