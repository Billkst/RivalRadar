/**
 * VirtualOfficeView — 虚拟办公室主视图(plan v3.2 §6 + DESIGN.md §虚拟办公室 layout)。
 *
 * 组合层级(z 顺序):
 *   1. OfficeBackground SVG 背景层(absolute inset-0)— 2x2 工位 + 中央会议区
 *   2. AgentCharacter overlay × 4(Day-3 spike 后实装,本 commit 仅占位 div)
 *   3. SpeechBubble overlay × 4 — pointer-events-none,定位在 character 上方
 *
 * 工位坐标(跟 OfficeBackground.tsx Seat charMountX/Y 一致):
 *   分析员 灵犀 [0,0] mount=(260,130) → percent (32.5%, 21.7%)
 *   撰稿员 灵巧 [1,0] mount=(660,130) → percent (82.5%, 21.7%)
 *   收集员 夜枭 [0,1] mount=(260,430) → percent (32.5%, 71.7%)
 *   质检员 镜湖 [1,1] mount=(660,430) → percent (82.5%, 71.7%)
 *
 * SpeechBubble yPercent = mount.y - 12(放 character 上方 12% viewport)。
 *
 * Visibility:agent nodes[NodeName] !== 'idle' 时 SpeechBubble 才 visible
 * (idle 不显示 narrative;loading/empty 状态由 RunPage 顶层处理 plan §3 5 UI state)。
 */
import { useRunStore, type NodeName } from '@/stores/runStore'
import { OfficeBackground } from './OfficeBackground'
import { SpeechBubble } from './SpeechBubble'
import { HandoffAnimation } from './HandoffAnimation'
import { AGENTS } from '@/lib/agentConstants'

// 工位 mount 坐标(viewBox 800x600 → percent)
const SEAT_MOUNT_PERCENT: Record<string, { x: number; y: number }> = {
  analyst: { x: (260 / 800) * 100, y: (130 / 600) * 100 },
  writer: { x: (660 / 800) * 100, y: (130 / 600) * 100 },
  collector: { x: (260 / 800) * 100, y: (430 / 600) * 100 },
  qc: { x: (660 / 800) * 100, y: (430 / 600) * 100 },
}

// agent_id → NodeName 映射(1:1,跟 LiveFeedPanel NODE_TO_AGENT 反向)
const AGENT_TO_NODE: Record<string, NodeName> = {
  collector: 'collect',
  analyst: 'analyze',
  writer: 'write',
  qc: 'qc',
}

// 会议区中心(OfficeBackground 中央椭圆 cx=400 cy=300,viewBox 800×600)
// HandoffAnimation quadratic curve 的控制点。
const MEETING_PERCENT = { x: (400 / 800) * 100, y: (300 / 600) * 100 }

// agent_id → seat color index(1:1,跟 globals.css --seat-N 同步)
const SEAT_NUM_BY_AGENT_ID: Record<string, number> = {
  collector: 1,
  analyst: 2,
  writer: 3,
  qc: 4,
}

export function VirtualOfficeView() {
  const nodes = useRunStore((s) => s.nodes)
  // 选 queue head 而非整 array — head 引用稳定时不触发 re-render。
  // 空 queue → undefined,不渲染 HandoffAnimation。
  const handoffHead = useRunStore((s) => s.handoffQueue[0])
  const dequeueHandoff = useRunStore((s) => s.dequeueHandoff)

  return (
    <div
      className="relative w-full overflow-hidden rounded-lg border border-border"
      style={{ aspectRatio: '4 / 3' }}
      role="region"
      aria-label="虚拟办公室 · 4 agent 实时协作"
    >
      {/* Background SVG 全填充 */}
      <OfficeBackground className="absolute inset-0 h-full w-full" />

      {/* AgentCharacter 占位(Day-3 spike 后 mount 真 SVG sprite / Lottie)
          现暂用一个 16x16 小圆 + agent 名,标 mount 位置 */}
      {AGENTS.map((agent) => {
        const coord = SEAT_MOUNT_PERCENT[agent.id]
        if (!coord) return null
        const nodeName = AGENT_TO_NODE[agent.id]
        const state = nodes[nodeName] ?? 'idle'
        const seatNum = { collector: 1, analyst: 2, writer: 3, qc: 4 }[agent.id] ?? 1
        return (
          <div
            key={`char-${agent.id}`}
            className="pointer-events-none absolute z-[1] flex h-12 w-12 items-center justify-center rounded-full border-2 text-[11px] font-medium"
            style={{
              left: `${coord.x}%`,
              top: `${coord.y}%`,
              transform: 'translate(-50%, -50%)',
              background: `var(--surface)`,
              borderColor: `var(--seat-${seatNum})`,
              color: `var(--seat-${seatNum})`,
              opacity: state === 'idle' ? 0.5 : 1,
              transition: 'opacity 200ms ease-out',
            }}
            aria-label={`${agent.name} ${agent.role} · ${state}`}
          >
            {agent.name}
          </div>
        )
      })}

      {/* SpeechBubble overlay × 4 — 显示在 character 上方,只 non-idle 显示 */}
      {AGENTS.map((agent) => {
        const coord = SEAT_MOUNT_PERCENT[agent.id]
        if (!coord) return null
        const nodeName = AGENT_TO_NODE[agent.id]
        const state = nodes[nodeName] ?? 'idle'
        return (
          <SpeechBubble
            key={`bubble-${agent.id}`}
            agentId={agent.id}
            xPercent={coord.x}
            yPercent={coord.y - 8}  // character 上方 8% viewport
            visible={state !== 'idle'}
          />
        )
      })}

      {/* HandoffAnimation — 招牌时刻 #3。key={head.id} 强制新 handoff 重 mount,
          避免 keyframe 动画半路被 props 替换丢 onAnimationComplete。 */}
      {handoffHead && (
        <HandoffAnimation
          key={handoffHead.id}
          from={SEAT_MOUNT_PERCENT[handoffHead.from]}
          to={SEAT_MOUNT_PERCENT[handoffHead.to]}
          meeting={MEETING_PERCENT}
          targetSeatNum={SEAT_NUM_BY_AGENT_ID[handoffHead.to] ?? 1}
          onComplete={dequeueHandoff}
        />
      )}
    </div>
  )
}
