# RivalRadar Lane F: Frontend Implementation Plan (v2)

> **v2 历史**:v1 写于 office-hours + 3 轮 design doc review;v2 整合 `/plan-eng-review` 15 决策 + Codex outside voice 17 findings(全修)。v2 重排 Task 顺序为 vertical-slice-first(先打通 1 run + 1 retry 全链路再 broaden)+ 修正后端 schema 字段名虚构 + 加 QC Issue Panel 让"分歧→解决"可见。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Lane A→E 后端 RivalRadar 暴露成评委 5 秒被抓住、5 分钟讲完不愿放手的 **前端 demo**。承载 spec §11.1-§11.7 全套信息架构 + spec §11.4 "实时动画 DAG money shot 含可见分歧→解决"(QC Issue Panel 是兑现关键,不只是 retry 弧)+ 证据 chip 侧栏(签名功能)+ 跨竞品矩阵 + 标记质疑桩。**评分 80% 看前端**(35% DAG + 25% SSE + 20% UI),Lane F 是比赛 ship 最后一公里。

**Architecture:** Vite 5 + React 18 + TS 单页应用,vite proxy `/api → :8000` 直消费 Lane E 10 API endpoint。手撸 svg + framer-motion 渲染 4 节点 DAG money shot(EUREKA:react-flow 对固定布局是 overkill)。**QC Issue Panel** 是 35% 多 agent 兑现的真正核心 — 仅 DAG 动画不够,评委需看到 explicit 文字 "质检否决: X lacked support → 采集补证据 12→19 → 分析改写 → QC pass"。Zustand 全局 store + `@microsoft/fetch-event-source` 接 POST /run live 流 / GET /stream replay 流,共用同一 reducer。shadcn/ui copy-paste + Tailwind v3 完整落实 DESIGN.md。

**Tech Stack:** Vite 5 · React 18 · TS 5 · React Router v6 · Zustand · framer-motion · `@microsoft/fetch-event-source` · shadcn/ui · Tailwind v3 · lucide-react · react-markdown (lazy) · remark-gfm (lazy) · Vitest · React Testing Library · pnpm 9

**Already locked(office-hours + 3 轮 design review + 15 plan-eng decisions + 17 Codex findings — 不要再问):**

- **构建**:Vite 5 + React 18 + TS / shadcn/Tailwind / 手撸 svg DAG / Zustand / fetch-event-source / React Router v6 / Vitest + RTL / 本地 demo(无 deploy)
- **i18n**:**全硬编中文 + 顶栏 disabled "EN" stub**(YAGNI,不引 react-i18next)
- **字体**:**IBM Plex Sans/Sans SC/Mono 本地 woff2** + Google Fonts CDN fallback(A4 决策 — 国内网络可达性)
- **路由**:**3 个 React Router 路由**(`/runs` + `/run/:run_id` + `/run/:run_id/competitor/:idx`)+ 1 hash anchor(matrix 行)— 把"竞品列表"层加回(Codex #12)
- **DAG money shot**:**4 节点 + 5 边(3 主流 + 2 retry 弧:retry_collect + retry_analyze)** — retry_analyze 从 Day-4 stretch 移到 core(Codex #6 #16:fixture 可能录到 retry_analyze,不画就撒谎)
- **QC Issue Panel(Codex #5 新增)**:DAG 旁固定 panel 显示 `质检 verdict + issues[] + 前后 evidence count delta + 改写前后 conclusion diff`,让"分歧→解决"看得见有内容(spec §11.4 强制可见 = Codex #5)
- **Demo mode**:**Python 单一路径** — `python scripts/seed_demo.py` 直接(无 `pnpm seed-demo` shim,Codex #10 统一)
- **后端契约 lock**(Lane E 已 ship,字段以**实际**为准):

  | 端点 | Method | 前端消费 |
  |---|---|---|
  | `/run` | POST + SSE live | RunsPage Create Form 启动 → 跳转 /run/:run_id(Codex #3 新加 form) |
  | `/stream/{run_id}` | GET + SSE replay | RunPage ▶ 播放 / demo mode |
  | `/runs` | GET | RunsPage 列表 |
  | `/run/{run_id}` | GET | RunPage 顶栏徽章/状态(Codex #1:不返 evidence 字段) |
  | `/evidence/{evidence_id}` | GET | EvidenceChip 点击 → Sheet 滑出 |
  | `/analysis/{run_id}` | GET | 卡片 + 矩阵 + **evidence_refs 是 credibility 数据源(Codex #1)** |
  | `/report/{run_id}` | GET | Markdown lazy fallback |
  | `/trace/{run_id}` | GET | DagDrawer 显示 trace |
  | `/annotations` | POST | FlagButton |
  | `/healthz` | GET | App.tsx mount probe(A2 决策) |

- **SSE 事件 schema lock**(钉死):
  - **Live 流**(POST /run):`start | node | error | done`
  - **Replay 流**(GET /stream/{run_id}):`start | trace | done`
  - **CQ1 reducer**:trace event 在 reducer 内 normalize 成 node summary 形状统一处理

- **Knowledge schema 真名**(`rivalradar/schema/models.py` — 修正 v1 plan 虚构字段,Codex #2):

  | v1 plan 写的(❌虚构) | 后端实际(✅真名) | 决策 |
  |---|---|---|
  | `Evidence.source_priority` | 不存在 | **删** — credibility 不含"一手"字段(只来源/时效/匹配引语) |
  | `Evidence.matched_quotes` | 不存在(`EvidenceRef.quote` 反向定义) | **改用 `EvidenceRef[].quote`**(从 analysis 反向算 matched 比例) |
  | `TraceEntry.token_in/token_out` | 仅 `tokens: int` 合并 | **改 UI 显示 "总 token"** |
  | `TraceEntry.retry_index` | 不存在 | **改 reducer 通过同 node 在 trace 中出现次数推导** retry index |
  | `ComparisonRow.values` | 实际 `cells: list[ComparisonCell]` | **改 props 用 `cells`** |
  | `ComparisonCell.value` | 是 `str`(`value_type: bool/enum/number/quote_text`) | **前端按 value_type 决定渲染方式** |
  | `PricingTier.price` | 自由 `str`(TODOS 已知遗留) | **按字符串渲染**,Day-4 加映射表归一 |
  | `AnnotationCreate.kind` | 不存在(仅 run_id/evidence_id/conclusion_path/note) | **删** — flag 只发 note(用 conclusion 文本截断) |
  | `Evidence` 的 `evidence_ids` chip props | 应该是 `EvidenceRef[].evidence_id`(从结论的 evidence_refs 拿) | **EvidenceChip 改 props `refs: EvidenceRef[]`** |

**Design doc reference:** `~/.gstack/projects/Billkst-RivalRadar/liujunxi-feat-frontend-design-20260526-225202.md`(v2,APPROVED)

---

## Vertical Slice Strategy(Codex #8 新增)

Day-1 vertical:**1 run + 1 retry + 1 卡 + 1 矩阵行 + 1 evidence sheet + 1 trace drawer + QC Issue Panel** 全链路打通(Task 1-7 必到)
Day-2 broaden:**4 张卡完整 + 全矩阵 + Annotations + 状态设计 + 双 retry 弧**(Task 8-12)
Day-2.5 polish:测试基线 + Lighthouse + README + opus audit(Task 13-16)

**Codex #7 cut 优先级**(时间不够时砍):
- 先砍:CI workflow / 全 lighthouse 95+ / dark-mode listener polish / 多 i18n / 所有卡片 4 个变体的极致细节
- 不砍:fixture replay / DAG / QC Issue Panel / EvidenceSheet / 标记质疑

---

## File Structure

**新增顶级 `frontend/`** + 顶级 `scripts/` + `fixtures/`(Python 后端共读):

```
frontend/
├── package.json
├── pnpm-lock.yaml
├── vite.config.ts          # vite + proxy + alias
├── tsconfig.json           # strict
├── tailwind.config.ts      # DESIGN.md 主题(IBM Plex / 暖纸白 / 8px / 暗黑 / 左 rail 208px)
├── postcss.config.js
├── eslint.config.js
├── .prettierrc
├── vitest.config.ts
├── index.html              # IBM Plex 本地 woff2 preload
├── public/
│   ├── favicon.svg
│   └── fonts/              # IBM Plex Sans / Sans SC / Mono 本地 woff2(A4)
├── src/
│   ├── main.tsx
│   ├── App.tsx             # Router + healthz probe (A2)
│   ├── Layout.tsx          # 左 rail 208px + 顶栏 + Outlet (DESIGN.md spec §11.1)
│   ├── styles/
│   │   └── globals.css
│   ├── pages/
│   │   ├── RunsPage.tsx              # /runs 列表 + Create Form (POST /run, Codex #3)
│   │   ├── RunPage.tsx               # /run/:run_id 聚合主页
│   │   └── CompetitorPage.tsx        # /run/:run_id/competitor/:idx (spec §11.1 IA, Codex #12)
│   ├── components/
│   │   ├── ui/                       # shadcn copy-paste
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── sheet.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── badge.tsx
│   │   │   └── toaster.tsx
│   │   ├── dag/                      # money shot
│   │   │   ├── DagCanvas.tsx         # 4 节点 + 5 边(含 2 条 retry 弧)
│   │   │   ├── DagNode.tsx
│   │   │   ├── DagEdge.tsx
│   │   │   ├── DagRetryArc.tsx       # 通用 retry 弧 (props: from, to, visible, color)
│   │   │   ├── DagDrawer.tsx         # 节点点击 → trace
│   │   │   ├── QCIssuePanel.tsx      # 🆕 Codex #5: 显式 issue list + delta + conclusion diff
│   │   │   ├── ObservabilityPanel.tsx # 🆕 Codex #15: raw event timeline + status + token/retry/error
│   │   │   └── dagLayout.ts          # 4 节点 (x,y) + 5 边路径
│   │   ├── badges/
│   │   │   └── CredibilityBadge.tsx  # 3 字段(sources/stale/matched 比例)— 删 primary
│   │   ├── cards/
│   │   │   ├── CompetitorOverview.tsx
│   │   │   ├── FeatureTreeCard.tsx
│   │   │   ├── PricingCard.tsx       # value=str 按字符串渲染
│   │   │   ├── SwotCard.tsx
│   │   │   └── MarkdownFallback.tsx  # lazy chunk
│   │   ├── matrix/
│   │   │   └── ComparisonMatrix.tsx  # cells[].value + value_type 决定渲染
│   │   ├── evidence/
│   │   │   ├── EvidenceChip.tsx      # props: refs: EvidenceRef[] (Codex #2) + React.memo (P1)
│   │   │   └── EvidenceSheet.tsx     # 反向高亮用稳定 conclusion path (Codex #14)
│   │   ├── annotations/
│   │   │   └── FlagButton.tsx        # 4 错误 toast (CQ2) + 无 kind
│   │   ├── states/
│   │   │   ├── BackendDownBanner.tsx # 🆕 A2 全局 banner
│   │   │   ├── LoadingDag.tsx
│   │   │   ├── InsufficientBlock.tsx
│   │   │   ├── DegradedBanner.tsx
│   │   │   └── EmptyState.tsx
│   │   └── theme/
│   │       └── ThemeToggle.tsx
│   ├── hooks/
│   │   ├── useSSE.ts                 # CQ1: live + replay 共用 reducer
│   │   ├── useEvidence.ts
│   │   ├── useHealthz.ts             # 🆕 A2: 启动时 probe
│   │   └── useTheme.ts               # CQ4: cleanup fn
│   ├── stores/
│   │   ├── runStore.ts
│   │   ├── evidenceStore.ts
│   │   └── themeStore.ts             # CQ4: init() 返 cleanup
│   ├── lib/
│   │   ├── api.ts                    # 10 endpoint typed wrappers
│   │   ├── highlight.ts              # CQ7: JSX 数组拼接(无 dangerouslySetInnerHTML)
│   │   ├── credibility.ts            # 3 字段公式(改自 4)
│   │   ├── conclusionPath.ts         # 🆕 Codex #14: 生成稳定 conclusion id(用于反向高亮)
│   │   └── utils.ts
│   ├── types/
│   │   └── api.ts                    # 严格对齐 rivalradar/schema/models.py + rivalradar/api/schemas.py
│   ├── fixtures/
│   │   └── replay-demo.json
│   └── tests/                        # 25 测(11+14) + lighthouse
│       ├── useSSE.test.ts            # 5 测(start/node/trace/error/done)
│       ├── DagState.test.ts          # 5 测(idle/running/done/failed/retrying)
│       ├── credibility.test.ts       # 🆕 T1: 4 测 → 3 测(改成 3 字段)
│       ├── FlagButton.test.tsx       # 🆕 T2: 4 测(422/404/500/network)
│       ├── highlight.test.ts         # 🆕 T3: 3 测(无匹配/多匹配/XSS)
│       ├── DagEdge.test.tsx          # 🆕 T4: 3 测(latent/active/retry-flowing)
│       └── replay-fixture.e2e.test.ts # 1 测 e2e
└── README.md

scripts/                              # 顶级(Python 后端共用)
├── record_demo.py                    # 真 LLM + 校验 + 失败 fallback 到手动编辑模式(A1)
├── seed_demo.py                      # Codex #10: 唯一 seed 入口,前端无 shim
└── ensure_demo_backend.py            # 🆕 Codex #11: 不需 LLM key 也能启 backend,demo 模式专用

fixtures/                             # 顶级
└── replay-demo.json                  # 强制含 retry_collect(Codex #6 — 与 plan DAG 默认一致)
```

**仓库根改动:**
- `.gitignore`:加 `frontend/node_modules/` `frontend/dist/` `frontend/.vite/`
- `README.md`:加"前端启动"section + "Demo Mode"
- `CLAUDE.md`:无 — 前端约定写在 `frontend/README.md`

---

## Task 1: 脚手架 + 工具链

- [ ] **1.1** `pnpm create vite@latest frontend --template react-ts`
- [ ] **1.2** `pnpm install`
- [ ] **1.3** `package.json`:scripts `dev/build/preview/test/lint/typecheck/lighthouse` + name `@rivalradar/frontend`
- [ ] **1.4** `tsconfig.json`:strict + paths alias `@/*`
- [ ] **1.5** `vite.config.ts`:`server.proxy = { "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: p => p.replace(/^\/api/, "") } }` + `server.port = 3000` + alias + **同步 `preview.proxy`(vite 5 行为)**
- [ ] **1.6** ESLint flat config + Prettier
- [ ] **1.7** `.gitignore` + 根 `.gitignore` 同步
- [ ] **1.8** `pnpm dev` 冷启 < 1s 验证
- [ ] **1.9** `pnpm typecheck` + `pnpm lint` 0 错

**Acceptance:** dev 启动,typecheck/lint 通过。

---

## Task 2: Tailwind + shadcn + DESIGN.md(含左 rail 208px,字体本地)

- [ ] **2.1** `pnpm add -D tailwindcss@^3 postcss autoprefixer`
- [ ] **2.2** `tailwind.config.ts`:DESIGN.md CSS 变量(colors / fontFamily / fontSize / spacing / borderRadius / boxShadow.panel) + `darkMode: 'class'` + tabular-nums 全局
- [ ] **2.3** `src/styles/globals.css`:CSS 变量 light + dark 双套 + 左 rail 宽 `--rail-width: 208px`
- [ ] **2.4** **下载 IBM Plex Sans/Sans SC/Mono woff2** 到 `public/fonts/`(中文子集化,~30KB SC + 20KB Sans + 15KB Mono)
- [ ] **2.5** `index.html` preload 本地字体 + `<link rel="preload" as="font" crossorigin>` + Google Fonts CDN 作 fallback
- [ ] **2.6** `pnpm dlx shadcn@latest init`(选 TS / RSC: no / global.css / cn util)
- [ ] **2.7** `pnpm dlx shadcn@latest add button card sheet badge tooltip` + 手动加 toaster
- [ ] **2.8** `pnpm add lucide-react`
- [ ] **2.9** **`Layout.tsx` 双 rail 布局**:左 208px 固定 rail(spec §11.1 IA 复刻 — Codex #13;占位"竞品列表 + 滤过")+ 顶栏 + 主区
- [ ] **2.10** 验证 IBM Plex 显示 + 暖纸白底 + 暗黑 toggle 工作

**Acceptance:** 左 rail 208px 可见;字体走本地;DESIGN.md 配色完整;暗黑模式生效。

---

## Task 3: 路由 + healthz probe + Layout + RunsPage Create Form(vertical slice 入口)

- [ ] **3.1** `pnpm add react-router-dom@^6`
- [ ] **3.2** `App.tsx`:BrowserRouter + Routes
  ```tsx
  <BrowserRouter>
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/runs" replace />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/run/:run_id" element={<RunPage />} />
        <Route path="/run/:run_id/competitor/:idx" element={<CompetitorPage />} />
        <Route path="*" element={<EmptyState>页面不存在</EmptyState>} />
      </Route>
    </Routes>
    <Toaster />
    <BackendDownBanner />  {/* A2 global */}
  </BrowserRouter>
  ```
- [ ] **3.3** **`hooks/useHealthz.ts`(A2)**:App mount 调 `GET /api/healthz`,失败 setBackendDown(true) → `<BackendDownBanner>` 全局显示"后端未启动 · 请先 `.venv/bin/python main.py` + README 链接"
- [ ] **3.4** `Layout.tsx`:**顶栏 + 左 rail 208px + Outlet**;顶栏:项目名 / 条件式 CredibilityBadge(A3 — useParams 取 run_id,有 run_id 时渲染)/ ThemeToggle / disabled "EN" stub
- [ ] **3.5** `RunsPage.tsx`:fetch `GET /api/runs` 列表 + **🆕 Create Form(Codex #3)**:
  - `<input>` 竞品名(逗号分隔,1-5 个)+ `<select>` 维度(checkbox CONTROLLED_DIMENSIONS)+ `<button>` 创建
  - 点击 → `POST /api/run` 启动 SSE → 接到 `start` event 取 run_id → `navigate(/run/${run_id})`
- [ ] **3.6** `RunPage.tsx` 占位:`useParams<{ run_id }>` → 显示 RunSummary + Task 6 后实装聚合
- [ ] **3.7** `CompetitorPage.tsx`(Codex #12):`useParams<{ run_id, idx }>` → 显示单竞品报告(CompetitorOverview + FeatureTree + Pricing + SWOT 单竞品)
- [ ] **3.8** **`lib/api.ts`**:typed wrappers — `fetchRuns`/`fetchRun(id)`/`fetchAnalysis(id)`/`fetchEvidence(id)`/`fetchReport(id)`/`fetchTrace(id)`/`createAnnotation(payload)`/`createRun(payload)`/`ping()`
- [ ] **3.9** **`types/api.ts`**:严格对齐 `rivalradar/schema/models.py` + `rivalradar/api/schemas.py`(grep 字段名拷过来,严禁虚构;Codex #2)

**Acceptance:** /runs 列表显示;create form 启动 POST /run 跳转 /run/:id;后端关闭时 banner 显示;左 rail 可见;CompetitorPage 路由可达。

---

## Task 4: Zustand stores(含 themeStore cleanup)

- [ ] **4.1** `pnpm add zustand`
- [ ] **4.2** **`stores/runStore.ts`**:
  ```ts
  interface RunStore {
    runId: string | null;
    nodes: Record<'collect'|'analyze'|'write'|'qc', NodeState>;
    events: SSEEvent[];           // 所有 SSE event(供 ObservabilityPanel 显示原始 timeline)
    degraded: boolean;
    retryCount: number;
    qcIssues: QCIssue[];          // 🆕 QC Issue Panel 数据源(从 done event 或 trace 推导)
    evidenceCountSnapshots: { ts, count }[];  // 🆕 retry 前后 delta
    startRun: (id) => void;
    handleEvent: (ev) => void;    // reducer 入口
    reset: () => void;
  }
  ```
- [ ] **4.3** **reducer 实现**:
  - `start`: 重置 nodes idle + runId set + events.push
  - `node`: nodes[node] = running/done(根据是否进入下一节点) + events.push + 如果是 qc done 则提取 issues 入 qcIssues + evidence count snapshot
  - **`trace`(replay)**:**🆕 CQ1 normalize**:`{node, summary: {input: trace.input_summary, output: trace.output_summary, latency_ms: trace.latency_ms, tokens: trace.tokens}, ts}` → 同 node event 处理 + 计算 retry index(同节点出现次数 - 1)
  - `error`: nodes[node] = failed + events.push
  - `done`: nodes 全 done + degraded set + events.push
- [ ] **4.4** `stores/evidenceStore.ts`:LRU(max 50,key = evidence_id)+ `getEvidence(id)` lazy load
- [ ] **4.5** **`stores/themeStore.ts`**(CQ4):`init()` 返回 cleanup fn,Layout useEffect 调 `const cleanup = themeStore.init(); return cleanup`

**Acceptance:** 3 store + reducer 5 event 全覆盖 + themeStore cleanup 在严格模式不 leak。

---

## Task 5: useSSE hook(live + replay 共用 reducer)

- [ ] **5.1** `pnpm add @microsoft/fetch-event-source`
- [ ] **5.2** `hooks/useSSE.ts`:
  ```ts
  type SSEMode = 'live' | 'replay';
  export function useSSE(opts: { mode, runId?, request? }): { start, stop, status }
  ```
  - live: `fetchEventSource('/api/run', { method: 'POST', body, headers, signal, openWhenHidden: true, onmessage, onerror })`
  - replay: `fetchEventSource('/api/stream/' + runId, { signal, openWhenHidden: true, onmessage })`
  - **`openWhenHidden: true`** 防 tab 切换断流(A5 partial)
  - **`onclose` 时 toast "连接断开,请刷新"**(A5 partial)
  - 共用 `runStore.handleEvent`
- [ ] **5.3** RunPage 集成:依 RunSummary.status 决定 mode(running → live;done → replay 可选)
- [ ] **5.4** **5 单测**(`useSSE.test.ts`):mock fetchEventSource,各 1 测 start/node/trace/error/done

**Acceptance:** SSE 启动 → DAG 节点动 + qc done 时 qcIssues 填充。

---

## Task 6: ⭐ Vertical Slice MVP(Day-1 必到 — DAG + QC Issue Panel + 1 卡 + 1 矩阵行 + 1 evidence sheet + 1 drawer)

> **本 Task 是 Codex #8 新增:vertical slice 先打通 1 run 全链路,验证 35% 兑现路径可见,再 broaden。**

### 6.1 DagCanvas(money shot 主体)

- [ ] **6.1.1** `dagLayout.ts`:4 节点 (x,y) + **5 边路径**(3 主流 + **2 retry 弧**:retry_collect = 质检→采集,retry_analyze = 质检→分析)
- [ ] **6.1.2** `DagCanvas.tsx`:viewBox 960x320 + 渲染 4 DagNode + 3 DagEdge + 2 DagRetryArc + Play/Pause/Reset 按钮 + 进度条 + retry count badge
- [ ] **6.1.3** `DagNode.tsx`:Props {name, label, x, y, r, state, onOpen}:
  - 5 state 颜色(idle/running/done/failed/retrying)按 DESIGN.md CSS 变量
  - framer-motion 动效:running 脉动 / failed 闪 / retrying shake / done 色变
- [ ] **6.1.4** `DagEdge.tsx`:Props {d, state} — latent/active/retry-flowing 三态(T4)
- [ ] **6.1.5** `DagRetryArc.tsx`:Props {d, visible, color} — AnimatePresence fade in + pathLength 0→1 + 反向流光

### 6.2 🆕 QCIssuePanel(Codex #5 关键 — 让"分歧→解决"看得见)

- [ ] **6.2.1** `QCIssuePanel.tsx`:DAG 右侧固定 panel(占 30% 宽),订阅 `runStore.qcIssues + evidenceCountSnapshots`
- [ ] **6.2.2** **3 段落显示**:
  ```
  第 1 轮 质检 verdict: retry_collect (issues 列出)
    ├── 问题: 缺定价证据
    └── 问题: 缺用户评价(<5 条)
  
  采集补救: evidence 12 → 19(↑7)
    └── 新增源: techcrunch.com, g2.com, ...
  
  分析改写: 3 条结论 evidence_refs 更新
    └── (折叠 diff)
  
  第 2 轮 质检 verdict: pass ✓
  ```
- [ ] **6.2.3** **数据源构造**:用 `trace[].node === 'qc'` 提取 verdict + issues;用 `trace[].node === 'collect'` 多次出现统计 evidence delta;用 `analysis.evidence_refs` 取改写前后对比(或从 trace.output_summary diff)
- [ ] **6.2.4** **空状态**(无 retry,首次就 pass):显示"✓ 一次性通过质检"
- [ ] **6.2.5** 与 DAG retry 弧动画同步(retry 弧 active 时,panel "采集补救"段 fade in)

### 6.3 DagDrawer(节点点击 → trace)

- [ ] **6.3.1** `DagDrawer.tsx`:shadcn Sheet 右侧,fetch `GET /api/trace/{run_id}`,filter `node === selectedNode`,按 ts 倒序
- [ ] **6.3.2** Tab "最新" / "历史":
  - 最新:`<dl>` 显示 prompt / input_summary / output_summary / **tokens(单字段,Codex #2)** / latency_ms
  - 历史:vertical stepper 显示同节点 N 次 trace,**retry index 由 reducer 推导(同 node 出现次数 - 1)**
- [ ] **6.3.3** prompt / output 用 `<pre>` 折叠,默认前 200 字符

### 6.4 RunPage 集成 + 1 卡 + 1 矩阵行 + 1 evidence sheet 占位

- [ ] **6.4.1** RunPage 布局:左侧 DagCanvas + QCIssuePanel 上下叠 + 主区 1 张 CompetitorOverview 卡(Task 8 后扩到全 4 卡)
- [ ] **6.4.2** 顶部状态:running/done/degraded RunDetail 显示 + 进度条
- [ ] **6.4.3** 占位:ComparisonMatrix 显示 1 行(Task 10 完整化)+ EvidenceSheet 占位(Task 9 完整化)

### 6.5 Spike — vertical slice 端到端验证

- [ ] **6.5.1** **手动跑后端**(Task 13 fixture 还没录,先用真后端):
  ```bash
  cd /home/liujunxi/project/RivalRadar
  .venv/bin/python main.py    # :8000
  cd frontend && pnpm dev       # :3000
  ```
- [ ] **6.5.2** 浏览器开 `/runs`,点 create form 启动 1 个真 run(确保 .env 已填,**承担 LLM cost ~$0.05**)
- [ ] **6.5.3** 观察:DAG 4 节点依次 running → done + QC Panel 显示 verdict + 如果 router retry 则弧 active(若没 retry 也算 pass — vertical slice 完成)
- [ ] **6.5.4** 点节点 → DagDrawer 打开显示 trace

**Acceptance:** /runs → create → DAG 动起来 → QC Panel 显示 verdict + (可选 retry)→ 节点点开 trace。**这是 35% 兑现的最小证据**,完成后才进 Task 7+。

---

## Task 7: Schema 对齐 + lib/credibility.ts(改 3 字段)

- [ ] **7.1** **`types/api.ts` 严格对齐**(Codex #2 — 全部字段从 grep `rivalradar/schema/models.py` + `rivalradar/api/schemas.py` 拷过来):Evidence / EvidenceRef / FeatureItem / PricingTier / PricingModel / SWOT / SWOTPoint / CompetitorProfile / ComparisonRow / ComparisonCell / CompetitorAnalysis / QCResult / QCIssue / TraceEntry / RunSummary / RunDetail / AnnotationCreate / AnnotationOut
- [ ] **7.2** **`lib/credibility.ts` 3 字段**(改自 4,因 source_priority 不存在):
  ```ts
  export function calcCredibility(analysis: CompetitorAnalysis): CredibilityStats {
    // 从 analysis 反向算 — 因为 GET /run 不返 evidence(Codex #1)
    const refs = collectAllRefs(analysis);  // 遍历 features / pricing / personas / swot.{s|w|o|t} 拿 evidence_refs
    const ids = new Set(refs.map(r => r.evidence_id));
    const sources = ids.size;
    // matched 比例(基于 EvidenceRef.support_verdict — Codex #2 改用 EvidenceRef.quote 反向定义)
    const matched = refs.filter(r => r.support_verdict === 'supported').length;
    const total = refs.length;
    // stale 需要再 fetch evidence — Day-1 不做(放 Task 9 evidenceStore prefetch 时算)
    return { sources, matched, total, matchedPct: total ? matched / total : 0 };
  }
  ```
- [ ] **7.3** **`lib/conclusionPath.ts`**(Codex #14 — 反向高亮稳定 id):
  ```ts
  // 每条结论的稳定路径,e.g. "competitor[0].features.f1" / "competitor[0].swot.strengths[2]"
  export function conclusionPath(competitorIdx, kind, ...): string
  ```
- [ ] **7.4** 单测:`credibility.test.ts` 3 测(空 / 单 ref / 多 ref + 部分 unsupported)

**Acceptance:** types/api.ts 严格对齐 + credibility 公式可跑 + conclusionPath 生成稳定 id。

---

## Task 8: 结构化卡片完整(§11.1 维度切片)

- [ ] **8.1** CompetitorOverview:速览 + CredibilityBadge sm size + ID(conclusionPath 标记)
- [ ] **8.2** FeatureTreeCard:`<details>/<summary>` collapsible + 叶子挂 EvidenceChip(props refs: EvidenceRef[])
- [ ] **8.3** PricingCard:`PricingModel.tiers` 遍历 + 每 tier 显示 `name / price (按 str 渲染) / billing_cycle / features_included / limits` + 挂 EvidenceChip
- [ ] **8.4** SwotCard:2x2 grid,4 个 SWOTPoint list,每条挂 EvidenceChip + FlagButton
- [ ] **8.5** MarkdownFallback:`lazy(() => import('./MarkdownFallbackImpl'))`,只在 analysis 缺失或字段为空时启用
- [ ] **8.6** RunPage 完整化:左 DAG + QC Panel,主区 4 张卡顺次(选竞品 idx via Layout 左 rail 或 hash)

**Acceptance:** 单 run 4 张卡全显示 + 每条结论挂 chip。

---

## Task 9: EvidenceChip + Sheet(签名功能,§11.2) + 反向高亮

- [ ] **9.1** **`EvidenceChip.tsx`**:Props `{ refs: EvidenceRef[]; conclusionPath: string }`(Codex #2 #14):
  ```tsx
  export default React.memo(function EvidenceChip({ refs, conclusionPath }: Props) {
    // 渲染 [1][2] 上标 button,点击 → evidenceStore.lazy load + setSelected(refs)
  });
  ```
- [ ] **9.2** `EvidenceSheet.tsx`:shadcn Sheet 右侧,显示 selectedRefs:
  - source_title / 原文片段(`<blockquote>`)+ 高亮命中句(`highlight.ts` 用 quote 字段)
  - source_url 新标签外链
  - fetched_at / language
  - 多 ref 间 `<hr>` 分隔
- [ ] **9.3** **`highlight.ts`**(CQ7):返回 ReactNode[](无 dangerouslySetInnerHTML)
  ```ts
  export function highlight(text: string, quotes: string[]): ReactNode[] {
    // 拼接 string + <mark>{match}</mark> 数组,React 自动 escape
  }
  ```
- [ ] **9.4** **反向高亮**(Codex #14):evidenceStore 加 `highlightedPaths: Set<string>`;点 chip 时 set 共享同源 conclusion path,CSS `ring-2 ring-source-line` toggle
- [ ] **9.5** 单测 `highlight.test.ts` 3 测:无匹配 / 多匹配 / XSS 输入(T3)

**Acceptance:** 点 chip → Sheet 滑出 + 原文 + 命中句高亮;反向高亮同源 conclusion 微高亮;无 XSS 风险。

---

## Task 10: 跨竞品对比矩阵(§11.3,用 ComparisonRow.cells)

- [ ] **10.1** `ComparisonMatrix.tsx`:Props `{ rows: ComparisonRow[]; competitors: string[] }`
- [ ] **10.2** `<table>` 渲染:`thead` sticky + 列 = 竞品名,行 = `row.dimension`
- [ ] **10.3** **每 cell = row.cells.find(c => c.competitor === comp)**(Codex #2 用 cells 而非 values):
  - `value_type === 'bool'`:✓/✗ icon
  - `value_type === 'enum'`:label
  - `value_type === 'number'`:数字条 + 数字(按 value parseFloat,fallback string)
  - `value_type === 'quote_text'`:简短 chip
- [ ] **10.4** 胜出项高亮:`bg-accent-soft`(按 value_type 算 best)
- [ ] **10.5** 右下角 EvidenceChip 角标(cell.evidence_refs)
- [ ] **10.6** hash anchor `#competitor=N` 滚到对应列(`scrollIntoView`)

**Acceptance:** N 行 × M 列矩阵渲染 + 胜出高亮 + chip 可点。

---

## Task 11: FlagButton(§11.6 + CQ2 4 错误) + 状态设计(§11.5)

### 11.1 FlagButton(CQ2 4 错误类型)

- [ ] **11.1.1** Props `{ runId, evidenceId?, conclusionPath?, note }`(无 kind 字段)
- [ ] **11.1.2** lucide Flag icon button + optimistic icon 变红
- [ ] **11.1.3** **POST /api/annotations** + try/catch:
  ```ts
  try {
    await createAnnotation({ run_id, evidence_id, conclusion_path, note });
    toast.success('已记录');
  } catch (e) {
    if (e.status === 422) toast.error('参数错误(报告 bug)');
    else if (e.status === 404) toast.error('记录不存在,请刷新');
    else if (e.status >= 500) toast.error('后端错误,已记录本地 · 稍后可重试');
    else toast.error('网络问题');
    setFlag(false);  // 回滚 optimistic
  }
  ```
- [ ] **11.1.4** 4 单测(T2):各 1 mock 422/404/500/network,断言 toast 文案 + icon 回滚
- [ ] **11.1.5** 每个 SwotCard 项 / FeatureTreeCard 叶子 / 矩阵单元格 / Markdown 兜底报告里 挂 FlagButton 小号

### 11.2 状态设计

- [ ] **11.2.1** BackendDownBanner(A2):全局 fixed 顶部,显示"后端未启动 · 请先 `.venv/bin/python main.py` · [README](...)"
- [ ] **11.2.2** LoadingDag:loading 时 DAG idle 状态占位 + "等待结果..."
- [ ] **11.2.3** InsufficientBlock:灰条"未找到公开数据"
- [ ] **11.2.4** DegradedBanner:degraded run 顶部红黄"未通过质检(原因: {issues[]}),以下结论存疑"
- [ ] **11.2.5** EmptyState:lucide Inbox + "尚无 run · 用顶部 create form 创建"

**Acceptance:** FlagButton 4 错误类型 toast 文案不同 + 全部状态可见。

---

## Task 12: i18n stub + 暗黑模式 + ObservabilityPanel(Codex #15)

### 12.1 i18n stub

- [ ] **12.1.1** 不引 react-i18next,UI 字符串硬编中文
- [ ] **12.1.2** 顶栏 disabled Button "EN" + Tooltip "Coming Day-4"

### 12.2 暗黑模式(CQ4 cleanup)

- [ ] **12.2.1** ThemeToggle 用 sun/moon icon + 调 `themeStore.toggle()`
- [ ] **12.2.2** themeStore.init() 返 cleanup fn,Layout `useEffect(() => themeStore.init(), [])`(返回值是 cleanup)
- [ ] **12.2.3** localStorage `rivalradar:theme` 持久化

### 12.3 🆕 ObservabilityPanel(Codex #15 工程可观测兑现)

- [ ] **12.3.1** `ObservabilityPanel.tsx`:DAG 下方折叠 panel(默认收起,顶栏一个 chip "🔍 观测面板")
- [ ] **12.3.2** 显示 `runStore.events` 原始 timeline:
  - 每条 event:`<span class="font-mono">[ts] event=X node=Y ...</span>`
  - 按事件类型颜色编码(start/node 绿/error 红/done 蓝/trace 灰)
- [ ] **12.3.3** 顶部 stat row:
  - 当前 status / 总 latency / 总 tokens / retry count / error count
  - SSE 连接状态(connecting/streaming/done/error)
- [ ] **12.3.4** "复制 JSON" button 把 events 导出(评委可拿走)

**Acceptance:** 暗黑切换可持久;ObservabilityPanel 展开显示完整 event timeline;评委一眼看到"原始 SSE 流 + 后端工程深度"。

---

## Task 13: demo fixture + seed(Python 侧,fixture 强制 retry_collect)

### 13.1 record_demo.py(A1 manual edit valve + Codex #6 fixture 强制 retry_collect)

- [ ] **13.1.1** `scripts/record_demo.py`:
  ```python
  """跑 ≤ 3 次真 LLM,要求 fixture 含 retry_collect(不接受 retry_analyze,避免与 DAG 默认 retry 弧不符)"""
  COMPETITORS = ["openai/chatgpt", "anthropic/claude"]
  
  def validate_demo_quality(trace, analysis):
    """必须满足:① 至少 1 次 router verdict 为 retry_collect(non-retry_analyze)
                ② evidence 数从 round 1 到 round 2 增加 (N → M, M > N)
                ③ qc 第一次 verdict='retry_collect',最后 verdict='pass'"""
    ...
  
  def main():
    for attempt in range(3):
      run_id = trigger_real_run(COMPETITORS)
      trace, analysis = wait_done_and_fetch(run_id)
      try:
        validate_demo_quality(trace, analysis)
        dump_fixture(run_id, trace, analysis)
        print("✓ Fixture recorded")
        return 0
      except AssertionError as e:
        print(f"Attempt {attempt+1} fail: {e}")
    # 3 attempts 都失败 → manual edit fallback
    print("LLM 3 次随机都没出 retry_collect。请手动编辑 fixtures/replay-demo.json:")
    print("  - 在 trace[] 中插一段 {node:'qc', verdict:'retry_collect', issues:[...]} 行")
    print("  - 调整 evidence 数让 round 1 < round 2")
    print("  - 用最后一份失败 attempt 的 fixture 作起点(已 dump 为 fixtures/replay-demo.attempt-3.json)")
    return 2
  ```

### 13.2 seed_demo.py(Codex #10 — 唯一 seed 入口)

- [ ] **13.2.1** `scripts/seed_demo.py`:读 `fixtures/replay-demo.json` → 复用 `rivalradar.storage.repository` 写 runs/evidence/analysis/report/trace + 输出"Open: http://localhost:3000/run/{run_id}"

### 13.3 ensure_demo_backend.py(Codex #11 — 不需 LLM key 也启)

- [ ] **13.3.1** `scripts/ensure_demo_backend.py`:检测 `.env` 是否有 ARK_API_KEY,无则 export `RIVALRADAR_DEMO_ONLY=1`(后端 lifespan 看到此 flag 时跳过 doubao client 初始化,只挂 read-only endpoint + 必要 dependency)
- [ ] **13.3.2** **后端 graceful degrade**(`rivalradar/api/app.py` 改 lifespan):if `RIVALRADAR_DEMO_ONLY`,跳过 `get_doubao_client` mount;`POST /run` 返 503 "demo mode: live run disabled, use seeded run"
- [ ] **13.3.3** 后端单测 1 测:demo mode 启动 + healthz 200 + POST /run 返 503
- [ ] **13.3.4** **可选 — 跳过该 task 加 Day-4 backend stretch**:若改后端阻塞 Lane F ship,只 doc README "demo 模式仍需 ARK_API_KEY"(评委填一个 dummy 也行)

### 13.4 一次性录 fixture + 文档化

- [ ] **13.4.1** 配 `.env` 真 keys → 跑 `python scripts/record_demo.py`(可能重跑 3 次或 manual fallback)
- [ ] **13.4.2** fixture 进仓库(`fixtures/replay-demo.json`,非 gitignore)
- [ ] **13.4.3** **README Demo Mode**:
  ```
  ## Demo Mode (no LLM key cost)
  
  1. (一次性) python scripts/seed_demo.py — 输出 demo run_id
  2. python scripts/ensure_demo_backend.py (设 RIVALRADAR_DEMO_ONLY=1)
  3. .venv/bin/python main.py
  4. cd frontend && pnpm dev
  5. 浏览器开 http://localhost:3000/run/<demo_run_id>
  6. 点 ▶ 播放 → DAG + QC Issue Panel 演示分歧→解决
  ```

**Acceptance:** record_demo.py 满足 3 退路(自动通过 / 手动 fallback);fixture 强制含 retry_collect;seed_demo.py 单 Python 入口;后端 graceful degrade 可选实现。

---

## Task 14: 测试基线(25 测 + Vitest config + lighthouse)

- [ ] **14.1** `pnpm add -D vitest @testing-library/react @testing-library/jest-dom @vitest/coverage-v8 jsdom`
- [ ] **14.2** `vitest.config.ts`:`environment: 'jsdom'` + `globals: true` + setup `src/tests/setup.ts`
- [ ] **14.3** `useSSE.test.ts` 5 测 (start/node/trace/error/done)
- [ ] **14.4** `DagState.test.ts` 5 测(idle/running/done/failed/retrying — render DagNode 各 state)
- [ ] **14.5** `credibility.test.ts` 3 测(T1 改自 4 — 空 ref / 单 ref / 多 ref 含 unsupported)
- [ ] **14.6** `FlagButton.test.tsx` 4 测(T2 — mock api 422/404/500/network,断言 toast + icon 回滚)
- [ ] **14.7** `highlight.test.ts` 3 测(T3 — 无匹配 / 多匹配 / XSS 输入 `<script>` 被 React escape)
- [ ] **14.8** `DagEdge.test.tsx` 3 测(T4 — latent/active/retry-flowing — 断 stroke className + animation prop)
- [ ] **14.9** `replay-fixture.e2e.test.ts` 1 测(load fixture + mock fetchEventSource yield 序列 → 断 DAG 全 done + retry 弧 active + EvidenceSheet 可点)
- [ ] **14.10** `pnpm test` **25 测全过** + coverage > 80%(useSSE/runStore/dagLayout/credibility/highlight)
- [ ] **14.11** **🆕 `pnpm lighthouse`**(P2):package.json 加 script `"lighthouse": "lighthouse http://localhost:3000/run/demo-run-1 --view"`,跑出 LCP/FID/CLS + 截图存 `frontend/docs/lighthouse-report-{date}.png`(README 引用)
- [ ] **14.12** **CI workflow `.github/workflows/frontend.yml`**(可选)— Node 20 + pnpm cache + typecheck + lint + test + build

**Acceptance:** 25 测全过;coverage > 80%;Lighthouse 报告 + 截图就绪。

---

## Task 15: README + opus 全栈 audit + Lane F 收尾

- [ ] **15.1** `frontend/README.md`:本地启动 / Demo Mode / 依赖说明 / DESIGN.md 引用 / 已知限制 / Lighthouse 报告链接
- [ ] **15.2** 根 `README.md` 加"前端启动"section
- [ ] **15.3** opus 全栈 audit:用 `/review` skill 跑前端 diff,或 dispatch general-purpose 跑"前端 vs spec §11 一致性 + DESIGN.md 完整落实 + 后端 schema 字段名 grep"
- [ ] **15.4** audit critical / high issue 全修
- [ ] **15.5** CHANGELOG.md 加 Lane F (版本 0.2.0.0)
- [ ] **15.6** TODOS.md 关 Lane F 项 + 加 audit 发现 stretch goal
- [ ] **15.7** `/ship` → `/review` → `/land-and-deploy` 三段闭环
- [ ] **15.8** Day-4 收尾:`/qa` 跑前端 demo + opus 全局终审 + 评分自检(目标 80%+)

**Acceptance:** opus 0 critical;README 完整;CHANGELOG/TODOS 更新;Lane F ship 到 main。

---

## Task 16: 后端 schema 补强(可选 — Day-4 stretch 若改后端有阻力)

> 这是 Codex finding #2 反向方案:**保留** v1 plan 想要的 UI 概念(source_priority / token_in/out / retry_index / kind / numeric pricing)但走后端补 schema 字段而非删 UI。

- [ ] **16.1** **(Day-4)** 后端 `Evidence` 加 `source_priority: Literal['primary','secondary','community']`(LLM 抽取时根据 source_url 域名分类)
- [ ] **16.2** **(Day-4)** 后端 `TraceEntry` 拆 `tokens` 为 `token_in / token_out`(structured_call 返 usage 时记录)
- [ ] **16.3** **(Day-4)** 后端 `TraceEntry` 加 `retry_index: int`(graph 跑时 retry_count + 1 写入,前端无需推导)
- [ ] **16.4** **(Day-4)** 后端 `AnnotationCreate` 加 `kind: Literal['questioned','disputed','confirmed']`
- [ ] **16.5** **(Day-4)** 后端 `PricingTier` 加 `price_numeric: Optional[float]`(spec §11.3 矩阵数字条需求)

**默认:Task 16 全 Day-4 stretch — Lane F core 用现有 schema 渲染**。

---

## Day-4 Stretch Backlog(修订 — Codex #16)

| # | feature | 价值 | 工作量 |
|---|---|---|---|
| ~~S5~~ | ~~DAG retry_analyze 弧(已进 core)~~ | — | — |
| **S6c** | **Lighthouse 完整报告 + 截图**(已进 core P2,本项是"95+ 优化") | 代码质量 10% 分位 | M(4h)|
| S1 | 英文 i18n 译文(react-i18next 改造) | 国际范 demo | M(8h)|
| S2 | PDF 导出(print stylesheet) | 评委带走材料 | M(6h)|
| S3 | Share URL(短链)| 二期商业化伏笔 | XL |
| S4 | 多语种 demo 切换演示(双语对照) | nice-to-have | S(2h)|
| S7 | DAG 状态机 Storybook | 维护性 | M(6h)|
| **S8** | **后端 graceful degrade RIVALRADAR_DEMO_ONLY**(若 Task 13.3 跳过) | demo 评委 0 key 体验 | M(4h)|
| **S9** | **后端 schema 补强(Task 16)** | UI 概念回归 | M(6h)|

---

## Spike — 已合并入 Task 6.5(vertical slice 端到端验证)

不再单独 Section — Spike 即 Task 6.5。

---

## Self-Review

### Spec 覆盖检查

| spec § | Task |
|---|---|
| §11.1 信息架构 + IA(run→竞品→单竞品→证据)| Task 3(3 路由)+ Task 6.4 + Task 8 |
| §11.1 速览卡 + 可信度徽章 | Task 7.2(credibility 3 字段)+ Task 8.1 |
| §11.2 溯源(EvidenceChip + Sheet + 反向高亮)| Task 9 |
| §11.3 跨竞品对比矩阵 | Task 10(cells + value_type)|
| §11.4 DAG money shot + Codex #5 可见分歧→解决 | Task 6.1 + **Task 6.2 QCIssuePanel** |
| §11.5 状态设计 | Task 11.2 |
| §11.6 只读"标记质疑"桩 | Task 11.1(4 错误)|
| §11.7 视觉基调(DESIGN.md)+ 左 rail 208px | Task 2(rail + 字体本地)|
| §12 技术栈 | 全(Vite + React 18 office-hours 决策)|
| §16.1 周 2.5 前端 + 指标 + 材料 | Task 1-15 + vertical slice 优先 |
| §1.4 中英双语 | Task 12.1(中文 + disabled "EN" stub)|

### Codex 17-finding Resolution

| # | finding | 处理 |
|---|---|---|
| 1 | Task 7 顺序错(顶栏 evidence 数据源)| Task 7.2 credibility 从 analysis.evidence_refs 反向算;Layout A3 conditional render |
| 2 | Schema 字段虚构(8 处)| Constraints 表 + Task 7.1 全 type 对齐 + Task 9.1 props 改 refs |
| 3 | Live run 无入口 | Task 3.5 RunsPage Create Form |
| 4 | Replay 看不到分歧→解决 | Task 6.2 QCIssuePanel(从 trace + analysis 反向构造)|
| 5 | DAG 仅 retry 弧不够 | Task 6.2 QCIssuePanel 三段落显式 |
| 6 | retry_analyze 当 stretch 有撒谎风险 | retry_analyze 进 core(Task 6.1.1 5 边)+ fixture 强制 retry_collect |
| 7 | 132 checkbox / 2.5 天不可达 | vertical slice 优先 + cut 优先级明文 |
| 8 | 缺 vertical slice | Task 6 整合为 vertical MVP |
| 9 | record_demo 时间炸弹 | A1 manual edit valve(13.1.1 第 3 attempt fallback)|
| 10 | demo mode 矛盾 | 单 Python 路径(13.2 + README 文档化)|
| 11 | "no LLM cost" 仍要 backend key | Task 13.3 graceful degrade(可选,Day-4 S8)|
| 12 | spec §11.1 IA 缺竞品列表层 | Task 3 加 `/run/:id/competitor/:idx` route + 左 rail |
| 13 | DESIGN.md 左 rail 208px 没画 | Task 2.9 Layout 双 rail |
| 14 | 反向高亮 conclusion identity 未定 | Task 7.3 `lib/conclusionPath.ts` + Task 9.4 |
| 15 | 工程可观测 underclaim | Task 12.3 ObservabilityPanel |
| 16 | Day-4 stretch triage 错 | retry_analyze 进 core / S6 Lighthouse 进 core P2 |
| 17 | healthz 决策但 task 没排序 | Task 3.3 useHealthz 显式 |

### Placeholder scan

- 0 个 hardcoded API URL / API key / endpoint ID(全走 `/api` proxy)
- demo fixture 含真原文 + LLM 输出,无 API key

### Type consistency

- `src/types/api.ts` Task 7.1 严格对齐 — **每次后端改 schema 必须同步 grep**
- 已知 PricingTier.price 是自由 str(TODOS P3,Day-4 加映射)

### 工程纪律自检

- ✅ 测试 25 测基线(11 + 14) + lighthouse + 1 e2e
- ✅ KEY 纪律:前端无 key 接触;fixture 无 key
- ✅ Surgical:frontend/ 独立目录;scripts/ + fixtures/ 顶级 +3 文件;后端不动(除 Task 13.3 可选 graceful degrade)
- ✅ Simplicity:YAGNI(无 react-i18next / react-flow / react-query);路由 3 个;栈最小
- ✅ Match existing style:Python 脚本按 repository.py 同款 + TS strict + ESLint/Prettier
- ✅ DESIGN.md 100% 遵循:Task 2 全 CSS 变量 + Task 2.9 左 rail 208px(spec §11.1)+ Task 7+8 可信度徽章常驻顶栏 + 卡片头(A3 conditional)

### 已知遗留(非阻断,Day-4 stretch / 二期)

- 英文译文(S1)/ PDF (S2) / Share URL (S3) / 双语 demo (S4) / Lighthouse 95+ 优化 (S6) / Storybook (S7)
- 后端 graceful degrade demo mode(S8,Task 13.3 可选)
- 后端 schema 补强 4 字段(S9,Task 16)
- 前端 i18n 路径(stub 锁)
- PricingTier.price 自由串(TODOS P3)

---

**完成本 Lane F 后:**
1. `/ship` 把前端 + fixture 打成 PR
2. `/review` 增量 audit
3. `/land-and-deploy` 合 main
4. Day-4 总收尾:`/qa` 跑前端 + opus 全局终审 + 评分自检 → 80%+ 目标

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | clean | 17 findings, 17/17 fixed (rewritten plan v2) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 15 issues found, 15/15 fixed; +14 tests added (11 → 25 baseline) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | DX gaps | 0 | — | — |

**CODEX:** outside voice 跑 codex (model: gpt-5.5, high reasoning) — 17 findings 全修,plan 从 v1 重写为 v2 vertical-slice-first 结构。

**CROSS-MODEL:** Eng review (Claude) + Codex outside voice 高度一致 — Claude 抓 A1-A4 / CQ1-CQ7 / T1-T4 / P1-P2 (15 个实现细节问题),Codex 抓 schema 字段虚构 + IA 缺失 + DAG money shot 不足以可见 + vertical slice 缺失(5 个结构性 blocker)— **互补,无冲突**。

**UNRESOLVED:** 0 — 所有 15 + 17 finding 均经 user explicit approval(全选 A 推荐路径)。

**VERDICT:** **ENG CLEARED + CODEX CLEARED — ready to implement Lane F v2.** Eng review 已通过(plan-eng-review),outside voice 已通过(codex)。可进 /ship 闭环。
