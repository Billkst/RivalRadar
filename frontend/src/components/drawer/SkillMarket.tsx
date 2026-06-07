/**
 * SkillMarket — 技能市场(可展开,Plan C Epic 6 Task 21)。
 *
 * 列该 agent 可安装的正交 skill(MARKET);已装显「已安装」灰,未装可点「安装」。
 * 只列真实/正交能力(spec §6.3,排除未实现的情感打分/趋势监控)。
 */
import { useState } from 'react'
import type { AgentId } from '@/types/agents'
import { MARKET } from '@/lib/skillCatalog'
import { useSkillsStore } from '@/stores/skillsStore'

export function SkillMarket({ role }: { role: AgentId }) {
  const [open, setOpen] = useState(false)
  const installed = useSkillsStore((s) => s.installed[role])
  const install = useSkillsStore((s) => s.install)
  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="min-h-[36px] rounded-md border border-accent-line bg-accent-soft px-[11px] py-1.5 font-mono text-[11px] text-accent"
      >
        + 安装技能
      </button>
      {open && (
        <div className="mt-2.5 rounded-lg border border-border bg-surface-subtle p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-semibold text-text-primary">技能市场 · 可安装</span>
            <button
              onClick={() => setOpen(false)}
              aria-label="收起市场"
              className="flex h-9 w-9 items-center justify-center text-text-muted"
            >
              ✕
            </button>
          </div>
          {MARKET[role].map((it) => {
            const has = installed.some((s) => s.id === it.id)
            return (
              <div
                key={it.id}
                className="flex items-start justify-between gap-2 border-t border-border py-2 first:border-t-0"
              >
                <div className="min-w-0">
                  <div className="text-[12.5px] font-semibold text-ink">
                    {it.name} <span className="font-mono text-[9.5px] text-text-faint">v1</span>
                  </div>
                  <div className="mt-0.5 text-[11.5px] leading-[1.5] text-text-muted">{it.do}</div>
                </div>
                <button
                  disabled={has}
                  onClick={() => install(role, it.id)}
                  className={`min-h-[36px] flex-none rounded-md border px-[9px] py-1 font-mono text-[10.5px] ${
                    has
                      ? 'border-border text-text-faint'
                      : 'border-accent-line text-accent hover:bg-accent-soft'
                  }`}
                >
                  {has ? '已安装' : '安装'}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
