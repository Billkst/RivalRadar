/**
 * support_verdict 展示元数据(DESIGN.md §support_verdict tokens / §12.3 #10)。
 *
 * 唯一信任信号:三色 supported / partial / unsupported。**色盲双编码** ——
 * 颜色(token class)+ 形状(实心●/半填◐/空心○)+ title 文案。
 * 三处复用同一映射:对比矩阵单元格 / 决策依据行 / 证据原文卡。
 */
import type { EvidenceRef, SupportVerdict } from '@/types/api'

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

export interface VerdictSummary {
  supported: number
  partial: number
  unsupported: number
}

const EMPTY_SUMMARY: VerdictSummary = { supported: 0, partial: 0, unsupported: 0 }
// "最差优先" 去重:同一 evidence_id 在多处被引用且 verdict 不一致时,取最保守的
// (不足 > 部分 > 充分),全局汇总诚实偏悲观,不掩盖弱支撑。
const SEVERITY: Record<SupportVerdict, number> = { unsupported: 2, partial: 1, supported: 0 }

/** 把一组 EvidenceRef 按 evidence_id 去重(最差 verdict 胜)后汇总三色计数。 */
export function aggregateVerdicts(refs: EvidenceRef[]): VerdictSummary {
  if (refs.length === 0) return EMPTY_SUMMARY
  const worst = new Map<string, SupportVerdict>()
  for (const r of refs) {
    const prev = worst.get(r.evidence_id)
    if (prev === undefined || SEVERITY[r.support_verdict] > SEVERITY[prev]) {
      worst.set(r.evidence_id, r.support_verdict)
    }
  }
  const summary: VerdictSummary = { supported: 0, partial: 0, unsupported: 0 }
  for (const v of worst.values()) summary[v] += 1
  return summary
}
