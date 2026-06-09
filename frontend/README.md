# RivalRadar Frontend

RivalRadar 的前端:把后端「采集→分析→撰写→质检→决策」的全过程做成**实时可见的研究员工作台**,并把结果渲染成**决策座舱**(三色佐证 + 决策建议 + 报告)。

后端 SSE 流(`POST /run`)实时驱动界面;刷新 / 深链时走 `GET /stream/:id` 从持久化状态重建过程事件(replay)。无后端时用内置 `fakeSSEPlayer` 放完整过程演示。

## 技术栈

- **React 19** + **TypeScript 6** + **Vite 8**
- **Tailwind CSS 3** — 设计 token 见根目录 [`DESIGN.md`](../DESIGN.md)
- **Zustand 5** — 状态(`useSyncExternalStore`;selector 必须返 raw,派生放 render body,否则无限循环)
- **framer-motion** — 过程动画(全部带 `motion-reduce` 退化)
- **react-router-dom 6** — 路由
- **@microsoft/fetch-event-source** — SSE 客户端(module-level 单 run controller,跨路由不断流)
- **Radix UI**(dialog/slot)、**lucide-react**、**IBM Plex** 字体

## 开发

```bash
pnpm install
pnpm dev          # Vite dev(http://localhost:3000,/api/* 代理到后端 :8000)
pnpm build        # tsc -b && vite build(生产构建)
pnpm typecheck    # tsc -b --noEmit(只类型检查,不出包)
pnpm preview      # 预览生产构建
pnpm lint         # eslint
pnpm format       # prettier 写入
```

> WSL2:dev 从 Windows 浏览器访问用 WSL2 IP(`http://<wsl-ip>:3000`)。后端启停见根目录 `scripts/dev-*.sh`。

## 结构

```
src/
  pages/        # RunPage(座舱主页)· RunsPage · ReportView · SamplesPage(范文库)· CompetitorPage
  components/
    workbench/  # 实时引擎:LiveTracker(顶部「此刻」追踪卡)· ResearcherWorkbench
                #          · ExecutionTimeline(正序时间轴)· SourceCards · RetryLoop · AgentBadge/Roster
    cockpit/    # 决策座舱:DecisionBoard/DecisionSurface(决策三色)· StatusBar(三色簇 + 计时器)
                #          · EvidenceTimeline · SelfAuditTrace · VerdictDot
    report/     # Markdown(零依赖渲染器:表格 / 图片白名单 / [ev_] 可点溯源)
    drawer/     # navStack 抽屉:证据 / 步骤 / 技能目录
    ui/         # 基础组件
  stores/       # runStore(SSE 派生主状态)· cockpitStore · drawerStore · evidenceStore
                #          · skillsStore · typingStore · themeStore
  lib/          # api 客户端 · SSE 钩子 · 时间(北京时间)· 维度/角色映射 · freshness
  types/        # 与后端对齐的 SSE / API 类型
```

## 验证

```bash
pnpm typecheck && pnpm build   # 两个都要绿(改完前端先跑这个,别裸跑 pnpm build 看 cwd)
```

前端 E2E(Vitest / Playwright)尚未接入(见根目录 [`TODOS.md`](../TODOS.md));当前靠 `pnpm build` + gstack `/browse` 做视觉与流程 QA。
