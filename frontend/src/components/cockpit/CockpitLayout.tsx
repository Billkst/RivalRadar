/**
 * CockpitLayout — 证据驾驶舱主壳(DESIGN.md §Layout / v5 融合主轴,Plan C Epic 4)。
 *
 * 顶 StatusBar(sticky)+ 融合主轴双栏:左决策面 / 右研究员工作台(ResearcherWorkbench)。
 * 2e 基线(spec §6.1):
 *   - running:`1fr 472px` —— 右栏满宽呈现实时调研引擎。
 *   - done(terminal):`1fr 280px` —— 右栏收窄成摘要,左决策面成焦点(DESIGN.md v5)。
 * 响应式:`<lg`(<1024)单栏纵堆,**决策面优先**(DOM 左先 → 单栏时在上)。
 * 左决策面经 children slot 注入 —— Epic 3 传骨架占位,Epic 4 传 DecisionBoard/对比矩阵/证据。
 */
import * as React from 'react'
import { StatusBar } from '@/components/cockpit/StatusBar'
import { ResearcherWorkbench } from '@/components/workbench/ResearcherWorkbench'
import { Drawer } from '@/components/drawer/Drawer'
import { useRunStore } from '@/stores/runStore'
import { useSkillsStore } from '@/stores/skillsStore'

interface CockpitLayoutProps {
  /** 左决策面内容(Epic 4: DecisionBoard 等;Epic 3: 骨架占位)。 */
  children: React.ReactNode
  /** 当前 run_id(StatusBar done 后拉 curation-drops 兜底剔除计数)。 */
  runId: string
  /** StatusBar 决策派生指标(Epic 4/5 喂入;未就绪显 "—")。 */
  decisionCount?: number
  riskCount?: number
  /** 实时引擎分析阶段「矩阵 N/total 维」进度条分母(run.dimensions.length)。 */
  totalDimensions?: number
}

export function CockpitLayout({
  children, runId, decisionCount, riskCount, totalDimensions,
}: CockpitLayoutProps) {
  const status = useRunStore((s) => s.status)
  // 收窄摘要态的「查看工作 ↗」展开:在此持有,展开时右列同步加宽(原先 expanded 在
  // ResearcherWorkbench 内,grid 宽度看不到它 → 终态展开时实时内容被挤进 280px,看不清)。
  const [expanded, setExpanded] = React.useState(false)
  React.useEffect(() => {
    // 切 run 必须收起上一 run 的本地展开态。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setExpanded(false)
  }, [runId])

  // 技能子系统:首次挂载加载一次(GET /agent-skills,空表 seed);loaded 守卫防重复。
  React.useEffect(() => {
    if (!useSkillsStore.getState().loaded) {
      void useSkillsStore.getState().load()
    }
  }, [])

  // 有决策产出的终态(done/degraded/insufficient)默认收窄成摘要,聚焦决策面;running 与
  // 中断态(failed/cancelled,无决策、实时内容才是主角)保持完整实时内容。展开则一律加宽。
  const collapsibleTerminal =
    status === 'done' || status === 'degraded' || status === 'insufficient_evidence'
  const showFull = !collapsibleTerminal || expanded
  return (
    // h-full + min-h-0:填满父级(RunPage flex-1 槽)而非强占整视口高度。原 h-[100dvh] 嵌在
    // 「返回行 + RunSummary 卡」下方的可滚动 main 里 → 文档高 = 卡片 + 100dvh > 一屏 → 页面滚出
    // 一大片空 cockpit 列背景(#6 白区)。改填满父级后,卡片 + cockpit 正好一屏,列内部各自滚。
    <div className="flex h-full min-h-0 flex-col">
      <StatusBar
        runId={runId}
        decisionCount={decisionCount}
        riskCount={riskCount}
      />
      <div
        className={
          'grid min-h-0 flex-1 grid-cols-1 ' +
          (showFull ? 'lg:grid-cols-[1fr_600px]' : 'lg:grid-cols-[1fr_280px]')
        }
      >
        {/* relative:成为决策面内绝对定位后代(VerdictDot sr-only span / pill popover 等)的
            包含块,使其被本列 overflow-y-auto 裁剪,而非逃逸到 Layout 外层 main 把其 scrollHeight
            撑高 → 外层凭空多一条可滚白区(#6 根因,/browse 实测 3088→844)。 */}
        <main aria-label="决策与证据" className="relative min-w-0 overflow-y-auto bg-bg px-6 pb-14 pt-5">
          {children}
        </main>
        <aside className="relative flex min-w-0 flex-col overflow-hidden border-l border-border bg-surface-subtle">
          <ResearcherWorkbench
            collapsed={!showFull}
            onExpand={() => setExpanded(true)}
            totalDimensions={totalDimensions}
          />
        </aside>
      </div>
      {/* 抽屉导航栈(agent / 证据 / 步骤)— 全局挂一次,由 drawerStore 驱动 */}
      <Drawer />
    </div>
  )
}
