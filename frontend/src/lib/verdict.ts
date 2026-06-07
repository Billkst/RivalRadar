/**
 * support_verdict 展示元数据(DESIGN.md §support_verdict tokens / §12.3 #10)。
 *
 * 唯一信任信号:三色 supported / partial / unsupported。**色盲双编码** ——
 * 颜色(token class)+ 形状(实心●/半填◐/空心○)+ title 文案。
 * 三处复用同一映射:对比矩阵单元格 / 决策依据行 / 证据原文卡。
 */
import type { SupportVerdict } from '@/types/api'

export interface VerdictMeta {
  label: string // 充分/部分/不足
  shape: string // 色盲双编码形状
  cls: string // text-verdict-* token class
}

export const VERDICT_META: Record<SupportVerdict, VerdictMeta> = {
  supported: { label: '佐证充分', shape: '●', cls: 'text-verdict-supported' },
  partial: { label: '部分佐证', shape: '◐', cls: 'text-verdict-partial' },
  unsupported: { label: '佐证不足', shape: '○', cls: 'text-verdict-unsupported' },
}
