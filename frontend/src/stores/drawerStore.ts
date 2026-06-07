/**
 * drawerStore — 抽屉导航栈(navStack)。2e §2 语义移植到 Zustand(Plan C C-D3)。
 *
 * view = agent / evidence / step 三型。语义:
 *   - openX 从顶层进(栈空)= reset 栈到一层 + 记 lastFocus(用于关闭恢复焦点)
 *   - openX 栈已开 = push 一层(研究计划→步骤→命中来源 这类深入)
 *   - goBack = pop 一层;栈底则恢复焦点 + 全关
 *   - fullClose = 清栈 + 恢复焦点
 *
 * selector 纪律(记忆):组件读 `useDrawerStore((s) => s.stack)`(raw 引用);
 * top()/hasBack() 是函数,在组件里调一次或 `s.stack.at(-1)` 取 raw view。
 */
import { create } from 'zustand'
import type { AgentId } from '@/types/agents'

export type DrawerView =
  | { type: 'agent'; role: AgentId }
  | { type: 'evidence'; id: string }
  | { type: 'step'; id: string }

interface DrawerState {
  stack: DrawerView[]
  lastFocus: HTMLElement | null
  top: () => DrawerView | null
  hasBack: () => boolean
  openAgent: (role: AgentId) => void
  openEvidence: (id: string) => void
  openStep: (id: string) => void
  goBack: () => void
  fullClose: () => void
}

function rememberFocus(): HTMLElement | null {
  return typeof document !== 'undefined' ? (document.activeElement as HTMLElement) : null
}

export const useDrawerStore = create<DrawerState>((set, get) => ({
  stack: [],
  lastFocus: null,
  top: () => {
    const s = get().stack
    return s.length ? s[s.length - 1] : null
  },
  hasBack: () => get().stack.length > 1,
  openAgent: (role) =>
    set((s) =>
      s.stack.length
        ? { stack: [...s.stack, { type: 'agent', role }] }
        : { stack: [{ type: 'agent', role }], lastFocus: rememberFocus() },
    ),
  openEvidence: (id) =>
    set((s) =>
      s.stack.length
        ? { stack: [...s.stack, { type: 'evidence', id }] }
        : { stack: [{ type: 'evidence', id }], lastFocus: rememberFocus() },
    ),
  openStep: (id) =>
    set((s) =>
      s.stack.length
        ? { stack: [...s.stack, { type: 'step', id }] }
        : { stack: [{ type: 'step', id }], lastFocus: rememberFocus() },
    ),
  goBack: () =>
    set((s) => {
      if (s.stack.length > 1) return { stack: s.stack.slice(0, -1) }
      if (s.lastFocus?.focus) s.lastFocus.focus()
      return { stack: [], lastFocus: null }
    }),
  fullClose: () =>
    set((s) => {
      if (s.lastFocus?.focus) s.lastFocus.focus()
      return { stack: [], lastFocus: null }
    }),
}))
