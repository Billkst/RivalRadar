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

// agent 名字采用职责命名(评委 5 秒看到职责名即知在做什么)。
// Plan C(DESIGN.md v5):去除 v3 office emoji 动物 persona / sprite avatar /
// workspace_seat 工位语义(机构级工牌身份见 lib/agentRoles.ts ROLES)。
export const AGENTS: readonly AgentDescriptor[] = [
  {
    id: 'collector',
    name: '采集员',
    role: '采集员',
    capabilities: ['web_search'],
  },
  {
    id: 'analyst',
    name: '分析员',
    role: '分析员',
    capabilities: ['extract_features', 'extract_pricing', 'compare'],
  },
  {
    id: 'writer',
    name: '撰写员',
    role: '撰写员',
    capabilities: ['narrative_write'],
  },
  {
    id: 'qc',
    name: '质检员',
    role: '质检员',
    capabilities: ['entailment_check', 'controlled_check'],
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
