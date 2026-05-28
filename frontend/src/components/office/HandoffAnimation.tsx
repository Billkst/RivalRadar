/**
 * HandoffAnimation — 文档从 source agent 经会议区移到 target agent(plan v3.2 §6 +
 * DESIGN.md §Signature Patterns 招牌时刻 #3 "看得见的处理")。
 *
 * 设计要点(DESIGN.md HandoffAnimation 段):
 *   - 文档 icon 20×20 沿 quadratic curve 800ms 从 source → 会议区 → target
 *   - 落点 target 工位 highlight pulse 一次(--seat-N opacity 0.2 → 0.6 → 0)
 *   - easing 全程 ease-in-out(DESIGN.md Motion 段 move 系列)
 *   - pointer-events-none 不挡 character click
 *   - z-[5]:character(z-1)+ seat pulse(z-2)之上,SpeechBubble(z-10)之下
 *
 * 父组件契约:
 *   - 每次新 handoff 必须用 `key={handoff.id}` 强制重 mount —— framer-motion
 *     keyframe 动画半路被 props 替换会丢 onAnimationComplete,导致 runStore queue
 *     无法 dequeue 后续 handoff
 *   - onComplete 触发后 parent 应 dequeue,卸载本组件(unmount 后 motion.div 不再
 *     占位,target pulse 也随之消失)
 *   - 坐标系 = 百分比相对 parent container(VirtualOfficeView 的 aspectRatio 4/3
 *     容器),与 SpeechBubble / character 一致
 */
import { motion } from 'framer-motion'
import { FileText } from 'lucide-react'

export interface HandoffPosition {
  /** 0-100 — 相对父容器宽度百分比 */
  x: number
  /** 0-100 — 相对父容器高度百分比 */
  y: number
}

interface HandoffAnimationProps {
  /** 起点 — source agent 工位中心 */
  from: HandoffPosition
  /** 终点 — target agent 工位中心 */
  to: HandoffPosition
  /** 中转 — 会议区中心(quadratic curve 控制点) */
  meeting: HandoffPosition
  /** 1-4 — target 工位 seat color index,落点 pulse 用 */
  targetSeatNum: number
  /** 动画结束 callback,parent 用来 dequeue 下一个 handoff */
  onComplete: () => void
}

// 800ms — DESIGN.md Motion 段 HandoffAnimation spec
const DURATION_S = 0.8

export function HandoffAnimation({
  from,
  to,
  meeting,
  targetSeatNum,
  onComplete,
}: HandoffAnimationProps) {
  return (
    <>
      {/* 文档 icon — 沿 from → meeting → to 三 keyframe 移动 */}
      <motion.div
        className="pointer-events-none absolute z-[5] flex h-7 w-7 items-center justify-center rounded-md shadow"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          color: 'var(--accent)',
          transform: 'translate(-50%, -50%)',
        }}
        initial={{ left: `${from.x}%`, top: `${from.y}%`, opacity: 0, scale: 0.8 }}
        animate={{
          // 4 keyframe(配 times 4 元),最后一帧让文档在 target 处略 fade 收尾
          left: [`${from.x}%`, `${meeting.x}%`, `${to.x}%`, `${to.x}%`],
          top: [`${from.y}%`, `${meeting.y}%`, `${to.y}%`, `${to.y}%`],
          opacity: [0, 1, 1, 0.6],
          scale: [0.8, 1, 1.05, 0.9],
        }}
        transition={{
          duration: DURATION_S,
          ease: 'easeInOut',
          times: [0, 0.5, 0.9, 1],
        }}
        onAnimationComplete={onComplete}
        aria-hidden
      >
        <FileText className="h-4 w-4" />
      </motion.div>

      {/* Target seat pulse — 文档接近终点(t≈0.75)时启动,400ms 一次 */}
      <motion.div
        className="pointer-events-none absolute z-[2] h-16 w-16 rounded-full"
        style={{
          left: `${to.x}%`,
          top: `${to.y}%`,
          transform: 'translate(-50%, -50%)',
          background: `var(--seat-${targetSeatNum})`,
        }}
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: [0, 0.5, 0], scale: [0.6, 1.4, 1.7] }}
        transition={{ duration: 0.4, delay: 0.55, ease: 'easeOut' }}
        aria-hidden
      />
    </>
  )
}
