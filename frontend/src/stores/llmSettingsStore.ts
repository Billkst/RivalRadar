/**
 * llmSettingsStore — 只管「模型设置」抽屉开合 + 配置变更通知。
 *
 * config 本体(含 API Key)走 lib/llmConfig(localStorage 是唯一事实源),
 * 刻意不进 zustand 状态树 —— 防 key 被 devtools / 序列化观测(KEY 纪律)。
 * 保存/清除后 bumpVersion(),订阅 configVersion 的组件重读 loadLLMConfig()。
 *
 * 已知坑:selector 里绝不返回新引用(不写 || [] / .filter),只取原始字段。
 */
import { create } from 'zustand'

interface LLMSettingsStore {
  isOpen: boolean
  configVersion: number
  open: () => void
  close: () => void
  bumpVersion: () => void
}

export const useLLMSettingsStore = create<LLMSettingsStore>((set) => ({
  isOpen: false,
  configVersion: 0,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  bumpVersion: () => set((s) => ({ configVersion: s.configVersion + 1 })),
}))
