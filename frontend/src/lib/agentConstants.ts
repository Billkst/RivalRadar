/**
 * 竞品调研场景 hardcode 4 agent(D13 reverse + Codex F5)。
 *
 * 为什么 frontend hardcode 而非 backend GET /agents:
 *   - P0-2 单场景 demo,不需要 runtime 配置驱动(plan §4)
 *   - 省 backend AgentSpec schema + GET /agents endpoint + frontend store fetch
 *     (Codex F5 = ~30-45 min 节省)
 *   - Backend SSE event 用 stable agent_id 串接,frontend 用 AGENT_BY_ID 查 metadata
 *
 * 工位 layout(plan §3 + DESIGN.md §虚拟办公室 layout 2x2):
 *   [0,0] 分析员 灵犀 🦊      [1,0] 撰稿员 灵巧 🦝
 *   [0,1] 收集员 夜枭 🦉      [1,1] 质检员 镜湖 🐢
 *
 * (注:动物 / 名字 / persona 是 P1 决策,Day-3 visual spike 时 user 可改;
 *  改动本表即可,无需动 backend。)
 */
import type { AgentDescriptor, AgentId } from '@/types/agents'

// D19 polish #1 spike 决:agent 名字采用职责命名(user 反馈 — 拟人名字过于抽象,
// 评委 5 秒看到"夜枭"不知道在做什么)。拟物动物 vision 通过 persona 字段 emoji 保留
// (P0-1 "拟物动物 + 真实可爱"不放弃,只是 name 字段 = 职责名,emoji 移 persona)。
export const AGENTS: readonly AgentDescriptor[] = [
  {
    id: 'collector',
    name: '收集员',
    role: '收集员',
    avatar: '/agents/owl',
    persona: '🦉 视野广 · 24h 不睡 · 全网搜证据',
    capabilities: ['web_search'],
    workspace_seat: [0, 1],
  },
  {
    id: 'analyst',
    name: '分析员',
    role: '分析员',
    avatar: '/agents/fox',
    persona: '🦊 聪明 · 看穿本质 · 提取关键',
    capabilities: ['extract_features', 'extract_pricing', 'compare'],
    workspace_seat: [0, 0],
  },
  {
    id: 'writer',
    name: '撰稿员',
    role: '撰稿员',
    avatar: '/agents/raccoon',
    persona: '🦝 灵巧 · 文笔老练 · 句句有据',
    capabilities: ['narrative_write'],
    workspace_seat: [1, 0],
  },
  {
    id: 'qc',
    name: '质检员',
    role: '质检员',
    avatar: '/agents/turtle',
    persona: '🐢 稳健 · 细致 · 慢工出细活',
    capabilities: ['entailment_check', 'controlled_check'],
    workspace_seat: [1, 1],
  },
] as const

export const AGENT_BY_ID: Readonly<Record<AgentId, AgentDescriptor>> = Object.fromEntries(
  AGENTS.map((a) => [a.id, a]),
) as Readonly<Record<AgentId, AgentDescriptor>>

export const TEAM_COMPETITOR_RESEARCH = {
  scenario: 'competitor_research',
  agents: AGENTS,
} as const

/** Resolve agent metadata by id; returns null for unknown ids (defensive). */
export function agentById(id: string): AgentDescriptor | null {
  return (AGENT_BY_ID as Record<string, AgentDescriptor>)[id] ?? null
}
