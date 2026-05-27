/**
 * Agent abstraction layer types(plan v3.2 §4)。
 *
 * AgentDescriptor 描述一个 agent 的身份 + 渲染元数据。D13 reverse 后 frontend
 * hardcode 4 agent(lib/agentConstants.ts),backend SSE event 只 emit 稳定的
 * agent_id。未来扩场景模板时,AgentTeam 按 scenario 组合不同 agents(plan §4
 * P0-2 单场景 demo 后)。
 */

export type AgentId = 'collector' | 'analyst' | 'writer' | 'qc'

export interface AgentDescriptor {
  id: AgentId
  name: string                       // 中文名:夜枭 / 灵犀 / 灵巧 / 镜湖
  role: string                       // 中文 role:收集员 / 分析员 / 撰稿员 / 质检员
  avatar: string                     // SVG sprite path / Lottie path(不带扩展,组件按 state 加 -idle.svg 等)
  persona: string                    // 一句话人设(speech bubble idle 时 hover / aria-label 显示)
  capabilities: readonly string[]    // 能力 tag(LiveFeedPanel 标签 / DAG 节点 label)
  workspace_seat: readonly [number, number]  // 2x2 office 工位坐标 (col, row),[0,0]=左上
}

export interface AgentTeam {
  scenario: string
  agents: readonly AgentDescriptor[]
}
