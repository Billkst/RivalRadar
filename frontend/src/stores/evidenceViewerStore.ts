/**
 * evidenceViewerStore — 当前打开的证据原文 slide-over(DESIGN.md §证据原文 slide-over)。
 *
 * "同时仅一条":全局单一 openId。EvidencePill / 依据行 "查看原文" 调 open(id);
 * EvidenceSlideOver 订阅 openId 渲染。模块级 zustand 让任意层级组件无需 prop 透传。
 */
import { create } from 'zustand'

interface EvidenceViewerStore {
  openId: string | null
  open: (id: string) => void
  close: () => void
}

export const useEvidenceViewer = create<EvidenceViewerStore>((set) => ({
  openId: null,
  open: (id) => set({ openId: id }),
  close: () => set({ openId: null }),
}))
