/**
 * OfficeBackground — 虚拟办公室背景 SVG(plan v3.2 §8 + DESIGN.md §虚拟办公室 layout)。
 *
 * 2x2 工位 layout(每工位 ~280×180 + 中央会议区椭圆):
 *   ┌──────────┬──────────┐
 *   │ 灵犀工位 │ 灵巧工位 │   (analyst 0,0)  (writer 1,0)
 *   ├──────────┼──────────┤
 *   │     会议区(handoff) │
 *   ├──────────┼──────────┤
 *   │ 夜枭工位 │ 镜湖工位 │   (collector 0,1) (qc 1,1)
 *   └──────────┴──────────┘
 *
 * 坐标 viewBox 800×600,Day-3 VirtualOfficeView 把本组件作 background layer,
 * AgentCharacter 按 workspace_seat [col,row] 计算位置 mount 在 character 区。
 *
 * 配色继承 DESIGN.md:
 *   --office-bg / --surface / --surface-subtle / --border / --text-muted
 *   --seat-1 夜枭 / --seat-2 灵犀 / --seat-3 灵巧 / --seat-4 镜湖
 *   (CSS vars 通过 SVG presentation attribute fill="var(--xxx)" 在浏览器解析)
 *
 * 工位标识(简笔 SVG icon):
 *   收集员 夜枭 — 显示器 □□  ;分析员 灵犀 — 放大镜 ⊙─ ;
 *   撰稿员 灵巧 — 打字机 ▭▭ ;质检员 镜湖 — 印章 ⊟─ 。
 */
import * as React from 'react'

interface OfficeBackgroundProps {
  className?: string
}

interface SeatProps {
  x: number
  y: number
  seatColor: string      // CSS var name like '--seat-1'
  iconChildren: React.ReactNode  // 工位标识 icon(相对工位 x,y 偏移)
  charMountX?: number     // AgentCharacter mount 中心 x(相对 viewBox)
  charMountY?: number     // AgentCharacter mount 中心 y
  ariaLabel?: string
}

const SEAT_W = 280
const SEAT_H = 180

function Seat({ x, y, seatColor, iconChildren, charMountX, charMountY, ariaLabel }: SeatProps) {
  return (
    <g aria-label={ariaLabel}>
      {/* 工位主框 */}
      <rect x={x} y={y} width={SEAT_W} height={SEAT_H} rx={12}
            fill="var(--surface)" stroke="var(--border)" strokeWidth={1.5} />
      {/* 顶部 seat color band(身份标识) */}
      <rect x={x} y={y} width={SEAT_W} height={6} rx={3}
            fill={`var(${seatColor})`} />
      {/* 工位 desk(下方矩形,放工作物品) */}
      <rect x={x + 40} y={y + SEAT_H - 50} width={SEAT_W - 80} height={36} rx={4}
            fill="var(--surface-subtle)" stroke="var(--border)" strokeWidth={1} />
      {/* 工位标识 icon(顶部偏左) */}
      <g transform={`translate(${x + 56} ${y + 28})`}>{iconChildren}</g>
      {/* AgentCharacter mount 区(64×64 占位,Day-3 实装时 absolute-position 真 character) */}
      {charMountX !== undefined && charMountY !== undefined && (
        <rect x={charMountX - 32} y={charMountY - 32} width={64} height={64} rx={8}
              fill={`var(${seatColor})`} fillOpacity={0.12}
              stroke={`var(${seatColor})`} strokeWidth={1} strokeDasharray="3 3" />
      )}
    </g>
  )
}

/** 显示器 icon — 收集员 夜枭(plan §3) */
function MonitorIcon({ stroke }: { stroke: string }) {
  return (
    <g fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round">
      <rect x={0} y={0} width={44} height={28} rx={2} />
      <line x1={16} y1={32} x2={28} y2={32} />
      <line x1={10} y1={36} x2={34} y2={36} />
    </g>
  )
}

/** 放大镜 icon — 分析员 灵犀(plan §3) */
function MagnifierIcon({ stroke }: { stroke: string }) {
  return (
    <g fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round">
      <circle cx={14} cy={14} r={12} />
      <line x1={24} y1={24} x2={34} y2={34} />
    </g>
  )
}

/** 打字机 icon — 撰稿员 灵巧(plan §3) */
function TypewriterIcon({ stroke }: { stroke: string }) {
  return (
    <g fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round">
      <rect x={0} y={6} width={40} height={20} rx={3} />
      <rect x={6} y={0} width={28} height={8} rx={1} fill={stroke} fillOpacity={0.15} />
      <line x1={6} y1={20} x2={34} y2={20} />
    </g>
  )
}

/** 印章 icon — 质检员 镜湖(plan §3) */
function StampIcon({ stroke }: { stroke: string }) {
  return (
    <g fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round">
      <rect x={4} y={0} width={28} height={16} rx={2} />
      <line x1={12} y1={20} x2={24} y2={20} />
      <line x1={0} y1={28} x2={36} y2={28} strokeWidth={3} />
    </g>
  )
}

export function OfficeBackground({ className }: OfficeBackgroundProps) {
  return (
    <svg
      viewBox="0 0 800 600"
      className={className}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="虚拟办公室 · 4 agent 工位 + 中央会议区"
    >
      {/* 办公室背景 */}
      <rect width="100%" height="100%" fill="var(--office-bg)" />

      {/* 灵犀 分析员 工位 [0,0] 左上 — seat-2 琥珀(`--seat-2`) */}
      <Seat x={60} y={60} seatColor="--seat-2"
            iconChildren={<MagnifierIcon stroke="var(--seat-2)" />}
            charMountX={260} charMountY={130}
            ariaLabel="灵犀 分析员 工位" />

      {/* 灵巧 撰稿员 工位 [1,0] 右上 — seat-3 墨蓝 */}
      <Seat x={460} y={60} seatColor="--seat-3"
            iconChildren={<TypewriterIcon stroke="var(--seat-3)" />}
            charMountX={660} charMountY={130}
            ariaLabel="灵巧 撰稿员 工位" />

      {/* 夜枭 收集员 工位 [0,1] 左下 — seat-1 青绿 */}
      <Seat x={60} y={360} seatColor="--seat-1"
            iconChildren={<MonitorIcon stroke="var(--seat-1)" />}
            charMountX={260} charMountY={430}
            ariaLabel="夜枭 收集员 工位" />

      {/* 镜湖 质检员 工位 [1,1] 右下 — seat-4 松绿 */}
      <Seat x={460} y={360} seatColor="--seat-4"
            iconChildren={<StampIcon stroke="var(--seat-4)" />}
            charMountX={660} charMountY={430}
            ariaLabel="镜湖 质检员 工位" />

      {/* 中央会议区(handoff 动画落点)— 虚线椭圆 */}
      <g aria-label="会议区">
        <ellipse cx={400} cy={300} rx={90} ry={56}
                 fill="var(--surface-subtle)"
                 stroke="var(--border)" strokeWidth={1.5}
                 strokeDasharray="4 4" />
        <text x={400} y={305} textAnchor="middle"
              fontSize={12}
              fill="var(--text-muted)"
              fontFamily="IBM Plex Sans, system-ui, sans-serif"
              letterSpacing={2}>
          会议区
        </text>
      </g>
    </svg>
  )
}
