/**
 * VerdictDot — support_verdict 圆点(DESIGN.md §support_verdict tokens / §12.3 #10)。
 *
 * **色盲双编码**:颜色(token class)+ 形状(●充分 / ◐部分 / ○不足)+ title/sr-only 文案。
 * 三处复用同一组件:对比矩阵单元格、决策依据行、证据原文卡。
 */
import { VERDICT_META } from '@/lib/verdict'
import type { SupportVerdict } from '@/types/api'

export function VerdictDot({
  verdict,
  showLabel = false,
}: {
  verdict: SupportVerdict
  showLabel?: boolean
}) {
  const m = VERDICT_META[verdict]
  return (
    <span className={`inline-flex items-center gap-1 ${m.cls}`} title={m.label}>
      <span aria-hidden className="text-[10px] leading-none">
        {m.shape}
      </span>
      {showLabel ? <span className="text-[11px] leading-none">{m.label}</span> : null}
      <span className="sr-only">{m.label}</span>
    </span>
  )
}
