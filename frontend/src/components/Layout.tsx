import * as React from 'react'
import { Link, Outlet, useParams } from 'react-router-dom'
import { useThemeStore } from '@/stores/themeStore'
import { ThemeToggle } from './ThemeToggle'

/**
 * RivalRadar 应用外壳(v0.4 证据驾驶舱)。
 *   ┌ 顶栏: 项目名 / 副标 / run_id / ThemeToggle / "EN"(即将支持) ┐
 *   └ 所有页面:主区全宽(run 页 cockpit 自带分屏;列表/报告页自带布局) ┘
 *
 * v0.4:run 页退役 office AgentTeamRoster 左轨(卡通动物违背机构级 cockpit 美学)。
 * 列表页原有的「证据驾驶舱」空占位左轨(只有引导文案、无内容)已移除 —— RunsPage 全宽。
 *
 * themeStore.init() 在 mount 时挂载 matchMedia listener;cleanup 在 unmount/strict-mode
 * re-effect 时移除,防 listener leak (CQ4).
 */
export function Layout() {
  // A3: CredibilityBadge 条件式 — 仅在 /run/:run_id 等路由下渲染。Task 7 (lib/credibility) 完成后实装。
  const { run_id } = useParams<{ run_id?: string }>()
  const initTheme = useThemeStore((s) => s.init)

  React.useEffect(() => {
    return initTheme()
  }, [initTheme])

  return (
    <div className="flex h-full flex-col bg-bg text-text-primary">
      <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-4">
        <div className="flex items-center gap-3">
          <Link to="/runs" className="text-lg font-semibold text-text-primary hover:text-accent">
            RivalRadar
          </Link>
          <span className="text-xs text-text-muted">AI 多 Agent 竞品分析</span>
          {run_id && (
            <span className="font-mono text-xs text-text-muted">/ {run_id}</span>
            /* Task 7: <CredibilityBadge runId={run_id} size="sm" /> */
          )}
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            type="button"
            disabled
            className="cursor-not-allowed rounded-md border border-border px-2 py-1 text-xs text-text-muted opacity-50"
            title="中英文切换 · 即将支持(本轮暂未实装)"
            aria-label="中英文切换,即将支持"
          >
            EN
          </button>
        </div>
      </header>
      <div className="flex flex-1 overflow-hidden">
        {/* relative:成为绝对定位后代(如 VerdictDot 的 sr-only span)的包含块,
            否则它们绕过本容器的 overflow 裁剪、撑高 html → 凭空多一条整页滚动条(Q6 修复)。 */}
        <main className="relative flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
