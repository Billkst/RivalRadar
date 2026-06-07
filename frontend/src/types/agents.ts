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
  name: string                       // 中文 role 名:采集员 / 分析员 / 撰写员 / 质检员
  role: string                       // 中文 role:采集员 / 分析员 / 撰写员 / 质检员
  capabilities: readonly string[]    // 能力 tag(LiveFeedPanel 标签 / DAG 节点 label)
}

export interface AgentTeam {
  scenario: string
  agents: readonly AgentDescriptor[]
}
