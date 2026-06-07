/**
 * ExecutionTimeline — 执行时间轴(2e §9,Plan C Task 16)。
 *
 * 绝对 HH:MM + 角色 + 「→ 导致变化」(每节点必产可见变化,防 agent theater)。
 * 派生自 runStore.events(node/progress + replay trace 双路径),镜像 ExecutionStream
 * 的 deriveRows 拓扑(cumulative 证据 / retry 轮次)但渲染换 2e timeline 样式 + effect 行。
 *
 * selector 返 raw(events),派生在 useMemo。role 字段存 AgentId 供 roleOf() 解析。
 */
import { useMemo } from 'react'
import { useRunStore } from '@/stores/runStore'
import { roleOf } from '@/lib/agentRoles'
import { formatBeijingTime } from '@/lib/time'
import type { AgentId } from '@/types/agents'
import type { SSEEvent } from '@/types/api'

const NODE_TO_AGENT: Record<string, AgentId> = {
  collect: 'collector',
  analyze: 'analyst',
  write: 'writer',
  qc: 'qc',
}

const QC_VERDICT_ZH: Record<string, string> = {
  pass: '裁决通过',
  retry_collect: '证据不足 · 打回采集',
  retry_analyze: '分析有误 · 打回分析',
  insufficient_evidence: '证据耗尽 · 标降级',
}

type Cls = 'normal' | 'reject' | 'pass' | 'failed'
interface TimelineRow {
  time: string
  role: AgentId | null // null = 系统/决策步
  msg: string
  effect?: string
  cls: Cls
}

/** 把后端 error 串脱敏成可读原因(绝不外泄 raw exception / stack;DESIGN.md §状态覆盖)。
 *  仅按关键字归类成罐装中文文案,未命中走通用兜底。 */
function sanitizeError(raw: string): string {
  const s = (raw || '').toLowerCase()
  if (s.includes('timeout') || s.includes('timed out')) return '调研超时,已中断本轮运行'
  if (s.includes('network') || s.includes('connection') || s.includes('proxy'))
    return '网络连接异常,已中断本轮运行'
  if (s.includes('rate') || s.includes('quota') || s.includes('429'))
    return '上游服务限流,已中断本轮运行'
  return '运行遇到异常,已中断本轮运行'
}

/** 从有序 SSE event 派生时间轴行(完成节点 + replay trace;progress 不单独成行,
 *  避免刷屏 —— 节点 done 行已含该节点产出)。effect = 该步导致的左栏可见变化。 */
function deriveTimeline(events: SSEEvent[]): TimelineRow[] {
  const rows: TimelineRow[] = []
  let cumulative = 0
  let round = 1

  for (const ev of events) {
    if (ev.type === 'error') {
      rows.push({
        time: formatBeijingTime(ev.data.ts),
        role: null,
        msg: sanitizeError(ev.data.error),
        effect: '运行中断',
        cls: 'failed',
      })
      continue
    }
    if (ev.type === 'node') {
      const node = ev.data.node
      const s = ev.data.summary
      const time = formatBeijingTime(ev.data.ts)
      if (node === 'collect') {
        const added = s.evidence_added ?? 0
        cumulative += added
        rows.push({
          time,
          role: 'collector',
          msg: `联网检索完成,新增 ${added} 条证据`,
          effect: `证据库 +${added} · 累计 ${cumulative}`,
          cls: 'normal',
        })
      } else if (node === 'analyze') {
        rows.push({
          time,
          role: 'analyst',
          msg: `对比 ${s.competitors ?? 0} 个竞品`,
          effect: `矩阵 +${s.comparison_rows ?? 0} 维`,
          cls: 'normal',
        })
      } else if (node === 'write') {
        rows.push({
          time,
          role: 'writer',
          msg: `综合生成报告 ${s.report_chars ?? 0} 字`,
          effect: '报告成型',
          cls: 'normal',
        })
      } else if (node === 'qc') {
        const verdict = s.verdict ?? ''
        const reject = verdict === 'retry_collect' || verdict === 'retry_analyze'
        if (reject) round += 1
        rows.push({
          time,
          role: 'qc',
          msg: QC_VERDICT_ZH[verdict] ?? `裁决:${verdict}`,
          effect: reject ? `自我纠错 · 第${round}轮` : verdict === 'pass' ? '证据闭环' : undefined,
          cls: reject ? 'reject' : verdict === 'pass' ? 'pass' : 'normal',
        })
      } else if (node === 'decide') {
        rows.push({
          time,
          role: null,
          msg: `生成 ${s.decisions ?? 0} 条决策建议`,
          effect: '决策面更新',
          cls: 'normal',
        })
      }
      continue
    }
    if (ev.type === 'trace') {
      // replay 路径:trace.output 是串,角色 = node;collect 解析 total 喂 cumulative。
      const node = ev.data.node
      const out = ev.data.summary?.output ?? ''
      const time = formatBeijingTime(ev.data.ts)
      if (node === 'collect') {
        const m = out.match(/total\s+(\d+)/)
        if (m) cumulative = Number(m[1])
        rows.push({
          time,
          role: 'collector',
          msg: out || '联网检索',
          effect: `累计 ${cumulative} 条证据`,
          cls: 'normal',
        })
      } else if (node === 'qc') {
        const reject = out.includes('retry_collect') || out.includes('retry_analyze')
        if (reject) round += 1
        rows.push({
          time,
          role: 'qc',
          msg: out || '质检裁决',
          effect: reject ? `自我纠错 · 第${round}轮` : undefined,
          cls: reject ? 'reject' : out.includes('pass') ? 'pass' : 'normal',
        })
      } else if (node === 'decide') {
        rows.push({ time, role: null, msg: out || '生成决策建议', effect: '决策面更新', cls: 'normal' })
      } else {
        const role = NODE_TO_AGENT[node] ?? null
        rows.push({ time, role, msg: out || '执行', cls: 'normal' })
      }
    }
  }
  return rows
}

function dotColor(cls: Cls, role: AgentId | null): string {
  if (cls === 'reject' || cls === 'failed') return 'var(--v-uns)'
  if (cls === 'pass') return 'var(--v-sup)'
  return (role && roleOf(role)?.col) || 'var(--accent)'
}

export function ExecutionTimeline() {
  const events = useRunStore((s) => s.events)
  const rows = useMemo(() => deriveTimeline(events), [events])
  if (!rows.length) return null
  return (
    <div className="flex flex-col mt-1.5">
      {rows.map((r, i) => (
        <div key={i} className="flex gap-[10px] py-[7px]">
          <div className="flex-none w-[14px] flex flex-col items-center">
            <span
              className="w-[9px] h-[9px] rounded-full mt-[3px] flex-none z-[1]"
              style={{ background: dotColor(r.cls, r.role) }}
            />
            {i < rows.length - 1 && <span className="flex-1 w-[1.5px] bg-border mt-0.5" />}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-muted">{r.time}</span>
              <span
                className="text-[11px] font-semibold"
                style={{
                  color:
                    r.cls === 'reject' || r.cls === 'failed'
                      ? 'var(--v-uns)'
                      : r.cls === 'pass'
                        ? 'var(--v-sup)'
                        : (r.role && roleOf(r.role)?.col) || 'var(--text-primary)',
                }}
              >
                {(r.role && roleOf(r.role)?.name) ?? '系统'}
              </span>
            </div>
            <div className="text-[11.5px] text-text-primary leading-[1.45] mt-0.5">{r.msg}</div>
            {r.effect && (
              <div
                className="text-[10.5px] font-mono mt-0.5 flex items-center gap-[5px]"
                style={{ color: r.cls === 'reject' || r.cls === 'failed' ? 'var(--v-uns)' : 'var(--accent)' }}
              >
                <span>→</span>
                {r.effect}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
