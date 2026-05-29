/**
 * 证据新鲜度(DESIGN.md §support_verdict / §状态覆盖 原文卡 stale 态)。
 *
 * stale 阈值默认 >90 天(可调)。逻辑独立成文件:对比矩阵单元格、证据原文卡、
 * EvidenceTimeline 三处复用同一判定,避免阈值漂移。
 */
const STALE_DAYS = 90
const DAY_MS = 86_400_000

/** fetched_at 距今天数(向下取整,非法日期返 0,未来时间 clamp 0)。 */
export function ageDays(fetchedAt: string, nowMs: number = Date.now()): number {
  const t = new Date(fetchedAt).getTime()
  if (Number.isNaN(t)) return 0
  return Math.max(0, Math.floor((nowMs - t) / DAY_MS))
}

/** 证据是否过期(>90 天)。stale ≠ 报警,仅灰角标提示"采集于 N 天前"。 */
export function isStale(fetchedAt: string, nowMs: number = Date.now()): boolean {
  return ageDays(fetchedAt, nowMs) > STALE_DAYS
}
