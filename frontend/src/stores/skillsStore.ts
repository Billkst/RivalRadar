/**
 * 技能子系统 store(C-D4):后端 agent_skills 表权威 + 前端首次空表 seed。
 * catalog(DEFAULT_SKILLS/MARKET)是 UI 元数据;state(version/enabled)持久化在后端。
 * 行为接入下一期 —— 本期装/删/开关不改变 agent 运行时行为。
 */
import { create } from 'zustand'

import { deleteAgentSkill, fetchAgentSkills, putAgentSkill } from '../lib/api'
import { DEFAULT_SKILLS, MARKET, type SkillDef, type SkillState } from '../lib/skillCatalog'
import type { AgentId } from '../types/agents'

interface SkillsState {
  // 每 agent 当前已装技能列表(catalog 顺序 + 已装 market) + 每技能状态
  installed: Record<AgentId, SkillDef[]>
  state: Record<string, SkillState> // skill_id → {version,enabled}
  behaviorNote: string // 诚实标注「行为接入下一期」
  loaded: boolean
  load: () => Promise<void>
  toggle: (agentId: AgentId, skillId: string) => Promise<void>
  install: (agentId: AgentId, skillId: string) => Promise<void>
  remove: (agentId: AgentId, skillId: string) => Promise<void>
}

const seedFromDefaults = () => {
  const installed = {} as Record<AgentId, SkillDef[]>
  const state: Record<string, SkillState> = {}
  ;(Object.keys(DEFAULT_SKILLS) as AgentId[]).forEach((role) => {
    installed[role] = [...DEFAULT_SKILLS[role]]
    DEFAULT_SKILLS[role].forEach((s) => {
      state[s.id] = { version: 'v1', enabled: true }
    })
  })
  return { installed, state }
}

const catalogLookup = (skillId: string): SkillDef | null => {
  for (const role of Object.keys(DEFAULT_SKILLS) as AgentId[]) {
    const d =
      DEFAULT_SKILLS[role].find((s) => s.id === skillId) ||
      MARKET[role].find((s) => s.id === skillId)
    if (d) return d
  }
  return null
}

export const useSkillsStore = create<SkillsState>((set, get) => ({
  ...seedFromDefaults(),
  behaviorNote: '技能行为接入下一期 —— 本期装/删/开关不改变 agent 运行时行为',
  loaded: false,
  load: async () => {
    let rows
    try {
      rows = await fetchAgentSkills()
    } catch {
      set({ loaded: true })
      return
    } // 后端不可达 → 用默认(graceful)
    if (rows.length === 0) {
      // 空表:seed 默认到后端(one-time bulk PUT),用默认 state
      const { installed, state } = seedFromDefaults()
      await Promise.all(
        (Object.keys(DEFAULT_SKILLS) as AgentId[]).flatMap((role) =>
          DEFAULT_SKILLS[role].map((s) =>
            putAgentSkill({ agent_id: role, skill_id: s.id, version: 'v1', enabled: true }).catch(
              () => {},
            ),
          ),
        ),
      )
      set({ installed, state, loaded: true })
      return
    }
    // 非空:表权威。按 agent 分组,catalog 查元数据;catalog 没有的 skill_id 跳过(脏数据防御)
    const installed = {} as Record<AgentId, SkillDef[]>
    const state: Record<string, SkillState> = {}
    ;(Object.keys(DEFAULT_SKILLS) as AgentId[]).forEach((r) => {
      installed[r] = []
    })
    rows.forEach((row) => {
      const def = catalogLookup(row.skill_id)
      if (!def) return
      const role = row.agent_id as AgentId
      if (!installed[role]) installed[role] = []
      installed[role].push(def)
      state[row.skill_id] = { version: row.version, enabled: row.enabled }
    })
    set({ installed, state, loaded: true })
  },
  toggle: async (agentId, skillId) => {
    const cur = get().state[skillId]
    if (!cur) return
    const next = { ...cur, enabled: !cur.enabled }
    set((s) => ({ state: { ...s.state, [skillId]: next } })) // 乐观更新
    await putAgentSkill({
      agent_id: agentId,
      skill_id: skillId,
      version: next.version,
      enabled: next.enabled,
    }).catch(() => {})
  },
  install: async (agentId, skillId) => {
    const def = MARKET[agentId].find((s) => s.id === skillId)
    if (!def) return
    if (get().installed[agentId].some((s) => s.id === skillId)) return // 已装
    set((s) => ({
      installed: { ...s.installed, [agentId]: [...s.installed[agentId], def] },
      state: { ...s.state, [skillId]: { version: 'v1', enabled: true } },
    }))
    await putAgentSkill({ agent_id: agentId, skill_id: skillId, version: 'v1', enabled: true }).catch(
      () => {},
    )
  },
  remove: async (agentId, skillId) => {
    set((s) => {
      const rest = Object.fromEntries(Object.entries(s.state).filter(([id]) => id !== skillId))
      return {
        installed: { ...s.installed, [agentId]: s.installed[agentId].filter((x) => x.id !== skillId) },
        state: rest,
      }
    })
    await deleteAgentSkill(agentId, skillId).catch(() => {})
  },
}))
