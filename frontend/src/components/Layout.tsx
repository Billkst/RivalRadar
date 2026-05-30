import * as React from 'react'
import { Link, Outlet, useParams } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useThemeStore } from '@/stores/themeStore'
import { ThemeToggle } from './ThemeToggle'

/**
 * RivalRadar 应用外壳(v0.4 证据驾驶舱)。
 *   ┌ 顶栏: 项目名 / 副标 / run_id / ThemeToggle / disabled "EN" ┐
 *   └ run 页:cockpit 全宽(CockpitLayout 自带分屏);列表页:左 rail(208px)+ 主区 ┘
 *
 * v0.4:run 页退役 office AgentTeamRoster 左轨(卡通动物违背机构级 cockpit 美学),
 * cockpit(StatusBar + 决策面 + 实时分析流程)占满主区。列表页保留轻量 rail 占位。
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
          <span
            className="cursor-not-allowed rounded-md border border-border px-2 py-1 text-xs text-text-muted opacity-50"
            title="EN 切换 — Day-4 stretch"
          >
            EN
          </span>
        </div>
      </header>
      <div className="flex flex-1 overflow-hidden">
        {/* run 页:cockpit 全宽(无 office 左轨);列表/其它页:保留轻量 rail 占位 */}
        {!run_id && (
          <aside
            className={cn(
              'flex flex-shrink-0 flex-col border-r border-border bg-surface-subtle p-4',
              'w-rail',
            )}
          >
            <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              证据驾驶舱
            </div>
            <div className="mt-2 text-xs italic text-text-muted">
              选一个 run 看决策面板 + 实时分析流程
            </div>
          </aside>
        )}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
