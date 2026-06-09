# Plan C — 调研进行时过程可视化 · 前端研究员工作台 + 三色真消费 + 技能子系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把后端(Plan A+B)已 emit 的真实活儿事件 + 真算 support_verdict 在前端落成「融合主轴 + 研究员工作台 + 三色真消费 + agent 工牌 + 技能子系统 + 抽屉导航栈」,实现 spec §6 全部前端改造与 §6.3/§7.3 的 `agent_skills` 后端持久化。

**Architecture:** 承 v4 证据驾驶舱 + 2e 认可原型。后端不变(Plan A+B 已 SHIP_READY,全部新事件 + cell/decision 级 support_verdict 已就绪);Plan C 在前端消费它们 —— 扩 `types/api.ts` 镜像新事件、扩 `useSSE.parseSSE` + `runStore.handleEvent`、把右栏从 `ExecutionStream` 升级为「研究员工作台」(roster 工牌 / 检索台 / 来源卡 / 执行时间轴 / 重试环 / 报告台)、矩阵改读 cell 级真三色 + `verdict_recheck` 刷新、StatusBar 三色重定义为「充分/部分/已剔除 Z(剔除计数,点开看清单)」、新增 navStack 抽屉(agent / 证据 / 步骤)+ 技能卡 UI(框架真·行为接入二期)。唯一后端增量 = `agent_skills` 表持久化技能状态(垂直切片)。

**Tech Stack:** 前端 React 19 + TypeScript + Tailwind 3 + Vite 8 + Zustand 5 + framer-motion + @microsoft/fetch-event-source。后端 FastAPI + SQLite(WAL)。前端验证 = `cd frontend && pnpm build`(`tsc -b && vite build`,记忆 [[verify-with-real-project-script]],**不是** `tsc --noEmit`)+ `/browse`(gstack,强制;**禁止** `mcp__claude-in-chrome__*`)。后端验证 = `.venv/bin/python -m pytest`。

---

## 0. 上下文:已完成 vs 本计划范围

**已 SHIP_READY(Plan A + Plan B,后端全量真实化,勿重做)**:
- SSE 新事件已 emit:`query` / `query_hit` / `source`(含 `fetched_at`)/ `evidence_delta` / `cell_row`(status ok|empty|failed)/ `verdict_recheck`(cell_verdicts/dropped/downgraded/summary)/ `chunk`(insight 两步 step1 流式草稿,step="drafting")。
- 数据模型:`ComparisonCell.support_verdict` + `Decision.support_verdict` 已是后端字段(真算三级回写)。
- 持久化 + REST:`GET /runs/{id}/queries`、`GET /runs/{id}/curation-drops`(scope=cell/decision,结构化 competitor/dimension/detail)、`GET /analysis/{id}`(cell 带真 support_verdict)、`GET /decisions/{id}`(decision 带真 support_verdict)。
- 反幻觉不变量:三级判定绝不进 `qc_result.issues`、partial 绝不触发 retry_analyze(策展人模型 [[qc-curator-not-judge]])。

**本计划范围(spec §6 前端 + §6.3/§7.3 技能后端持久化)**:Epic 1–9(见下)。

**不在本计划(Plan D)**:`fakeSSEPlayer`/replay-trace 全量平价(把新事件并入 replay)、demo URL 端到端 25s 无 dead-loop spike、真 run support_verdict 三级门槛最终校准、DESIGN.md v5 已写校验。Plan C 仅做**最小** `fakeSSEPlayer` 样本扩充(够 /browse 验证各新面板),Plan D 升级为 demo 级。

---

## 1. 范围决策(写死,实现据此,勿临场二选一)

| # | 决策点 | 锁定选择 | 理由 |
|---|--------|---------|------|
| C-D1 | 头像来源 | **vendor 4 张 lorelei SVG 到 `frontend/public/agents/{collector,analyst,writer,qc}.svg`**,组件引本地路径;`<img onerror>` 回落到身份色底纹 | spec §3.2「lorelei 占位」+ demo bullet-proof 必须离线(记忆 confidence 10/10);DiceBear 远程 URL 投影现场网络可能挂。抓取走海外代理(`ALL_PROXY=http://172.30.64.1:7897`,同 codex)。 |
| C-D2 | SSE 派生状态归属 | **扩 `runStore`(单一 SSE reducer),不新建 store** | 架构原则:SSE 单一真相源,所有事件经 `handleEvent`(架构报告确认无 selector 死循环)。 |
| C-D3 | 抽屉导航栈 | **新建 `drawerStore`(navStack)+ 通用 `Drawer` 组件**;`EvidenceSlideOver` 收编为 evidence 视图的渲染体 | 2e navStack 已验证(研究计划→步骤→命中来源,返回退一层、✕全关);现有 `EvidenceSlideOver` 单层不够。 |
| C-D4 | 技能状态持久化 | **后端 `agent_skills` 表权威 + 前端首次空表 seed**;catalog(DEFAULT_SKILLS/MARKET)留前端(UI 元数据);toggle/install=PUT upsert、delete=真 DELETE;reload 读表为准,按 skill_id 合并 catalog 元数据 | spec §7.3「本期后端持久化」;catalog 是 UI 文案不入后端(DRY);删默认技能靠「表权威」生效(seed 后表是真相,缺行=未装)。全表删空→下次 GET 空→重新 seed(回默认,可接受 UX)。 |
| C-D5 | StatusBar 三色语义 | **充分 X(绿●=supported cell 数)· 部分 Y(琥珀◐=partial cell 数)· 已剔除 Z(红○=`GET /curation-drops` scope=cell 计数,点开看清单)** | spec §5.5;红○ 不再是矩阵格假数据,是策展剔除计数(DESIGN.md v5)。 |
| C-D6 | `verdict_recheck` 无 `decision_verdicts` | 矩阵 cell 三色由 `verdict_recheck.cell_verdicts` 实时刷 + `GET /analysis` 兜底;**决策三色读 `decision.support_verdict`(`GET /decisions`)**,不依赖事件 | 实测后端 `SSEVerdictRecheckData` 只含 cell_verdicts/dropped/downgraded/summary(spec §7.1 写了 decision_verdicts 但实现未发);照实现接。 |
| C-D7 | 报告台 typing | 复用现有 `chunk → typingStore + writerReport`(`runStore` 已接);新增 `ReportStation` 组件渲染 `typingStore.byAgent['writer']`,首块前 **~38s** 显「起草中…」占位(后端 write_node 先发 `progress step="drafting"`,Spike H TTFB 38s) | spec §5.6 + Spike H;typing best-effort,结构化产物有契约保证(回落一次性数据仍真)。 |
| C-D8 | 研究计划 rail 位置 | **左决策面顶部**(2e DOM 基线:`.decision > 研究计划 + 对比矩阵 + 决策建议 + 哪里可能错`),由 SSE 事件驱动 doing→done/reopen,点 done/reopen 步骤开 step 抽屉 | 2e 用户认可基线;spec §6.4 的「计划勾选」指其由工作台事件驱动,位置仍在左栏(spec §3.1 左决策面含「研究计划 rail」)。 |
| C-D9 | 旧组件处置 | `ExecutionStream` 被 `ResearcherWorkbench` 取代(右栏改挂工作台);office/ 死代码不删(CLAUDE.md §3 不删既有死代码,只在本计划新建/改必要项);`dag/` 不动 | surgical(CLAUDE.md §3);office/dag 已 unmounted,tree-shake 自然剔除。 |

---

## 2. 文件结构(决策锁定处)

### 新建(前端)
- `frontend/src/lib/agentRoles.ts` — ROLE registry:`id → {mono,name,no,fn,seed,col,line,soft,avbg}`,4 身份色。
- `frontend/src/lib/skillCatalog.ts` — `DEFAULT_SKILLS` + `MARKET` + `SkillDef`/`SkillState` 类型(UI 元数据)。
- `frontend/src/lib/avatar.ts` — 头像本地路径 helper + onError 回落。
- `frontend/src/stores/skillsStore.ts` — `skillState` + load/toggle/install/remove + REST 同步。
- `frontend/src/stores/drawerStore.ts` — navStack + `openAgent/openEvidence/openStep/pushView/goBack/fullClose`。
- `frontend/src/hooks/useFocusTrap.ts` — 抽屉焦点 trap + Esc + 恢复触发焦点。
- `frontend/src/components/workbench/ResearcherWorkbench.tsx` — 右栏 shell(eng-hd + roster + live-pane + timeline)。
- `frontend/src/components/workbench/AgentRoster.tsx` + `AgentBadge.tsx` — 2×2 工牌。
- `frontend/src/components/workbench/SearchStation.tsx` — 检索台(query 行 + 打字 + 命中)。
- `frontend/src/components/workbench/SourceCards.tsx` — 来源卡列表。
- `frontend/src/components/workbench/ExecutionTimeline.tsx` — 执行时间轴(绝对 HH:MM + 角色 + → 导致变化)。
- `frontend/src/components/workbench/RetryLoop.tsx` — 重试环(青绿单回环一次性)。
- `frontend/src/components/workbench/ReportStation.tsx` — 报告台 typing。
- `frontend/src/components/workbench/PlanRail.tsx` — 研究计划 rail(左栏顶)。
- `frontend/src/components/drawer/Drawer.tsx` — 通用抽屉(back/close/scrim/a11y)。
- `frontend/src/components/drawer/AgentDrawer.tsx` — agent 详情 + 技能管理。
- `frontend/src/components/drawer/SkillCard.tsx` — 技能卡。
- `frontend/src/components/drawer/SkillMarket.tsx` — 技能市场。
- `frontend/src/components/drawer/StepDrawer.tsx` — 计划步骤详情。

### 新建(后端)
- `rivalradar/api/agent_skills.py` — `GET/PUT/DELETE /agent-skills` 路由。
- `tests/test_agent_skills.py` — 表 CRUD + REST 成功/失败两路。

### 新建(资产)
- `frontend/public/agents/collector.svg` / `analyst.svg` / `writer.svg` / `qc.svg`(vendored lorelei)。

### 修改(前端)
- `frontend/src/types/api.ts` — 新 SSE payload 类型 + `SSEEvent` 联合扩 + `ComparisonCell.support_verdict` + `Decision.support_verdict` + `QueryRecord`/`CurationDrop`/`AgentSkillRow` 类型。
- `frontend/src/hooks/useSSE.ts` — `parseSSE` 认新事件串。
- `frontend/src/stores/runStore.ts` — 新 slices + `handleEvent` 新分支(枚举防御 [[enum guard]])。
- `frontend/src/lib/api.ts` — `fetchQueries` / `fetchCurationDrops` / `fetchAgentSkills` / `putAgentSkill` / `deleteAgentSkill`。
- `frontend/src/lib/agentConstants.ts` + `frontend/src/types/agents.ts` — 去 emoji 动物 persona,改指 `agentRoles`(或保留 id 列表,persona 字段删)。
- `frontend/src/components/cockpit/CockpitLayout.tsx` — 1fr/472px + done 收窄 + 挂 `ResearcherWorkbench`。
- `frontend/src/components/cockpit/StatusBar.tsx` — 三色重定义(充分/部分/已剔除 Z)+ 点已剔除开 drops。
- `frontend/src/components/cockpit/CompetitorComparison.tsx` — 读 cell 级 verdict + 逐维 `cell_row` 填 + `verdict_recheck` 刷 + 失败维态 + 因果桥。
- `frontend/src/components/cockpit/DecisionBoard.tsx` — 读 `decision.support_verdict` + 因果桥。
- `frontend/src/components/cockpit/VerdictDot.tsx` — 形状对齐 2e `.shp`(●◐○)。
- `frontend/src/components/cockpit/DecisionSurface.tsx` — 顶部挂 `PlanRail`;接 drawer 化的证据视图。
- `frontend/src/components/cockpit/EvidenceSlideOver.tsx` — 收编为 `Drawer` 的 evidence 渲染体(或保留并由 drawerStore 驱动)。
- `frontend/src/styles/globals.css` + `frontend/tailwind.config.ts` — 新 token(`--id-*` + `line/soft` + `--surface-sink/--border-strong/--ink/--text-faint/--accent-deep/--accent-line/--v-*-soft/--r-pill`)。
- `frontend/src/dev/fakeSSEPlayer.ts` — **最小**扩充 `SAMPLE_EVENTS`(新事件,够 /browse;Plan D 升级 demo 级)。

### 修改(后端)
- `rivalradar/storage/db.py` — `agent_skills` 表。
- `rivalradar/storage/repository.py` — `list_agent_skills` / `upsert_agent_skill` / `delete_agent_skill`。
- `rivalradar/api/app.py` — 注册 `agent_skills` 路由。

---

## Epic 1 — 基础:类型 + SSE 解析 + store 接线(无 UI,先把数据接进来)

> 本 Epic 完成后 build 绿但界面无变化(数据进了 store,UI 还没消费)。这是有意的增量基座。验证 = `cd frontend && pnpm build` 绿 + 浏览器 console 打印新 store 切片有值(/browse 看不出 UI 变化属正常)。

### Task 1: 扩 `types/api.ts` —— 新事件类型 + cell/decision 三色字段 + REST 类型

**Files:**
- Modify: `frontend/src/types/api.ts`

**背景**:后端实测契约(均来自 `rivalradar/api/schemas.py`,Plan A+B 已 ship):
- `query`:`{competitor,dimension,query_text,language,round,ts}`
- `query_hit`:`{query_text,hit_count,round,ts}`
- `source`:`{evidence_id,competitor,dimension,source_title,source_url,fetched_at,language,round,ts}`
- `evidence_delta`:`{round,added_count,total_count,new_evidence_ids,ts}`
- `cell_row`:`{dimension,status:"ok"|"empty"|"failed",cells:[{competitor,value_type,value,evidence_refs:[{evidence_id,quote}]}],ts}`
- `verdict_recheck`:`{cell_verdicts:[{dimension,competitor,support_verdict}],dropped:dict[],downgraded:dict[],summary:{supported,partial,dropped},ts}`(**无 decision_verdicts**,C-D6)
- `chunk`:`{agent_id,step,delta,ts}`(已存在于现有 union)

- [ ] **Step 1: 加 SSE payload 类型 + 扩 union**

在 `frontend/src/types/api.ts` 现有 SSE 区(`SSEStartData` 等附近)追加:

```typescript
// --- Plan A/B 新事件(后端已 emit;此处镜像)---
export interface SSEQueryData { competitor: string; dimension: string; query_text: string; language: string; round: number; ts: string }
export interface SSEQueryHitData { query_text: string; hit_count: number; round: number; ts: string }
export interface SSESourceData {
  evidence_id: string; competitor: string; dimension: string;
  source_title: string; source_url: string; fetched_at: string;
  language: string; round: number; ts: string;
}
export interface SSEEvidenceDeltaData {
  round: number; added_count: number; total_count: number;
  new_evidence_ids: string[]; ts: string;
}
export interface SSECellRowRef { evidence_id: string; quote: string }
export interface SSECellRowCell { competitor: string; value_type: ValueType; value: string; evidence_refs: SSECellRowRef[] }
export type CellRowStatus = 'ok' | 'empty' | 'failed';
export interface SSECellRowData { dimension: string; status: CellRowStatus; cells: SSECellRowCell[]; ts: string }
export interface SSEVerdictRecheckCell { dimension: string; competitor: string; support_verdict: SupportVerdict }
export interface SSEVerdictRecheckData {
  cell_verdicts: SSEVerdictRecheckCell[];
  dropped: Array<Record<string, string>>;
  downgraded: Array<Record<string, string>>;
  summary: { supported?: number; partial?: number; dropped?: number };
  ts: string;
}
```

- [ ] **Step 2: 扩 `SSEEvent` 判别联合**

把现有 `SSEEvent` 联合(`{type:'start'...} | ... | {type:'chunk'...} | ...`)追加 6 个成员:

```typescript
export type SSEEvent =
  | { type: 'start'; data: SSEStartData }
  | { type: 'node'; data: SSENodeData }
  | { type: 'trace'; data: SSETraceData }
  | { type: 'progress'; data: SSEProgressData }
  | { type: 'chunk'; data: SSEChunkData }
  | { type: 'error'; data: SSEErrorData }
  | { type: 'done'; data: SSEDoneData }
  | { type: 'query'; data: SSEQueryData }
  | { type: 'query_hit'; data: SSEQueryHitData }
  | { type: 'source'; data: SSESourceData }
  | { type: 'evidence_delta'; data: SSEEvidenceDeltaData }
  | { type: 'cell_row'; data: SSECellRowData }
  | { type: 'verdict_recheck'; data: SSEVerdictRecheckData };
```

- [ ] **Step 3: 给 `ComparisonCell` / `Decision` 加 cell/decision 级 `support_verdict`**

`SupportVerdict` 已定义(`'supported'|'partial'|'unsupported'`)。改两处实体(后端 `models.py` 已有此字段,默认 `"supported"`):

```typescript
export interface ComparisonCell {
  competitor: string;
  value_type: ValueType;
  value: string;
  evidence_refs: EvidenceRef[];
  support_verdict: SupportVerdict;   // ← 新增(cell 级真三色;信任信号读此,不读 ref 级)
}
```
```typescript
export interface Decision {
  stance: Stance;
  action: string;
  horizon: Horizon;
  risk_reversibility: Reversibility;
  risk_cost: RiskCost;
  why: string;
  evidence_refs: EvidenceRef[];
  support_verdict: SupportVerdict;   // ← 新增(decision 级真三色;读此,C-D6)
  watch?: Watch | null;
}
```

- [ ] **Step 4: 加 REST 响应类型**

```typescript
export interface QueryRecord {
  competitor: string; dimension: string; language: string;
  query_text: string; round: number; hit_count: number; created_at: string;
}
export type CurationScope = 'cell' | 'decision';
export interface CurationDrop {
  scope: CurationScope; competitor: string; dimension: string; detail: string; created_at: string;
}
export interface AgentSkillRow {
  agent_id: string; skill_id: string; version: string; enabled: boolean; installed_at: string;
}
```

- [ ] **Step 5: 验证 build 绿**

Run: `cd frontend && pnpm build`
Expected: PASS(`tsc -b && vite build` 无类型错;注意 Step 3 给 `ComparisonCell`/`Decision` 加了必填字段 → demoFixture/samples 里手写的 cell/decision 若缺字段会报错,在 Task 后续修;若此步报 demoFixture 缺字段,先给那些手写对象补 `support_verdict: 'supported'`,记为 Step 5b)。

- [ ] **Step 5b(若 Step 5 因 demoFixture 报错)**:在 `frontend/src/lib/demoFixture.ts` 与 `frontend/src/lib/samples.ts`(及任何手写 `ComparisonCell`/`Decision` 的 fixture)给每个 cell/decision 补 `support_verdict`(demo 数据按叙事给 `'supported'|'partial'`,保持 demo 真实感)。再跑 `pnpm build` 绿。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/lib/demoFixture.ts frontend/src/lib/samples.ts
git commit -m "feat(planC): mirror Plan A/B SSE events + cell/decision support_verdict in TS types"
```

### Task 2: 扩 `useSSE.parseSSE` 认新事件串

**Files:**
- Modify: `frontend/src/hooks/useSSE.ts`

**背景**:`parseSSE`(架构报告:`useSSE.ts:39-64`)把 `event:` 串映射到判别联合。现仅认 start/node/trace/progress/chunk/error/done。`sse.py` 无白名单,任何 ev_type 透传,前端必须显式认才能 dispatch。

- [ ] **Step 1: 在 `parseSSE` 加 6 个 case**

定位 `parseSSE`(switch on event name)。在 `chunk` 分支后追加(`data` 已是 `JSON.parse` 后对象):

```typescript
case 'query':          return { type: 'query',          data: data as SSEQueryData };
case 'query_hit':      return { type: 'query_hit',      data: data as SSEQueryHitData };
case 'source':         return { type: 'source',         data: data as SSESourceData };
case 'evidence_delta': return { type: 'evidence_delta', data: data as SSEEvidenceDeltaData };
case 'cell_row':       return { type: 'cell_row',       data: data as SSECellRowData };
case 'verdict_recheck':return { type: 'verdict_recheck',data: data as SSEVerdictRecheckData };
```

确保从 `types/api.ts` import 了这些类型(顶部 import 块补齐)。**枚举防御**(记忆 [[enum guard]]):`parseSSE` 的 `default` 分支必须**保留**未知事件而非丢弃(返回一个 `{type:'unknown', raw}` 或直接 `return null` 并由调用点跳过)—— 查现有 default 行为,若现在是 `throw`/丢弃,改为安全跳过(`return null`),防后端将来加事件时前端炸。

- [ ] **Step 2: 验证 build 绿**

Run: `cd frontend && pnpm build`
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useSSE.ts
git commit -m "feat(planC): parseSSE recognizes query/source/cell_row/evidence_delta/verdict_recheck"
```

### Task 3: 扩 `runStore` —— 新切片 + `handleEvent` 新分支

**Files:**
- Modify: `frontend/src/stores/runStore.ts`

**背景**:`runStore.handleEvent` 是单一 SSE reducer(C-D2)。现处理 start/progress/chunk/node/trace/error/done(架构报告)。新增切片承载「真实活儿」。**乱序契约**(spec §5.3):`cell_row` 按完成顺序到达,前端按 `dimension` key 落位,不假设顺序。**round 不造假**:直接用事件携带的 `round` 字段(后端已正确推导,spec §5.1)。

- [ ] **Step 1: 加状态切片到 store 类型 + 初值**

在 `RunState`(或等价 state 接口)加:

```typescript
// Plan C 工作台切片(SSE 派生)
queries: SSEQueryData[];                       // 检索台:逐条查询词(prepend 最新在前)
queryHits: Record<string, number>;             // query_text → hit_count
sources: SSESourceData[];                       // 来源卡(到达序)
cellRows: Record<string, SSECellRowData>;       // dimension → 该维 cell_row(逐维填,乱序安全)
evidenceDeltas: SSEEvidenceDeltaData[];         // retry 增量(重试环)
cellVerdicts: Record<string, SupportVerdict>;   // `${dimension}|${competitor}` → 真三色(verdict_recheck 刷)
droppedCells: string[];                          // codex P2#12:被策展剔除的格 `${dimension}|${competitor}`(cell_verdicts 只含**保留**格,dropped 另存)
verdictSummary: { supported: number; partial: number; dropped: number } | null;
```

初值(在 reset()/初始 state 里):`queries: [], queryHits: {}, sources: [], cellRows: {}, evidenceDeltas: [], cellVerdicts: {}, droppedCells: [], verdictSummary: null`。**reset() 必须清这些**(每次 SSE.start 前 reset,防跨 run 污染)。

> 注意 selector 死循环(记忆 confidence 10/10):组件读这些切片时 selector 返 **raw** 引用,不在 selector 内 `|| []` / `.filter()` / `.map()`(会返新引用触发 infinite loop)。窄化在 render body 用 module-level 稳定常量(`const EMPTY_QUERIES: SSEQueryData[] = []`)。本 Task 只建 store;消费在 Epic 5。

- [ ] **Step 2: 在 `handleEvent` 加分支(if-chain,**非 switch** —— codex P1#1)**

> **codex 核验(P1#1)**:`runStore.handleEvent` 是 **if-chain 不是 switch**(`runStore.ts:180-198`);未识别事件会落到读 `ev.data.node` 的分支(`runStore.ts:286-290`),而新事件**没有** `node` 字段 → 会出错。**新事件分支必须放在 handleEvent 顶部、命中即早 return**,在任何读 `ev.data.node`/旧 node-fallthrough 之前拦截。先读 `runStore.ts:180-290` 确认 if-chain 形状再插入。

在 `handleEvent(ev: SSEEvent)` 开头(`chunk` 处理之后、node/trace 派生与 `ev.data.node` fall-through 之前)插入早 return 分支(`set((s)=>({...}))` immutable 更新):

```typescript
if (ev.type === 'query') {
  const q = ev.data;
  set((s) => ({ queries: [q, ...s.queries].slice(0, 200) }));   // 上限 200 防爆
  return;
}
if (ev.type === 'query_hit') {
  const { query_text, hit_count } = ev.data;
  set((s) => ({ queryHits: { ...s.queryHits, [query_text]: hit_count } }));
  return;
}
if (ev.type === 'source') {
  set((s) => ({ sources: [...s.sources, ev.data] }));
  // source 不含 content;来源卡点击走 openEvidence → REST 拉全文(此处不 seed)
  return;
}
if (ev.type === 'evidence_delta') {
  set((s) => ({ evidenceDeltas: [...s.evidenceDeltas, ev.data] }));
  return;
}
if (ev.type === 'cell_row') {
  const cr = ev.data;
  set((s) => ({ cellRows: { ...s.cellRows, [cr.dimension]: cr } }));   // 按 dimension 落位(乱序安全)
  return;
}
if (ev.type === 'verdict_recheck') {
  const vr = ev.data;
  const map: Record<string, SupportVerdict> = {};
  for (const cv of vr.cell_verdicts) map[`${cv.dimension}|${cv.competitor}`] = cv.support_verdict;
  const dropKeys = vr.dropped.map((d) => `${d.dimension}|${d.competitor}`);   // codex P2#12:dropped 另存
  set((s) => ({
    cellVerdicts: { ...s.cellVerdicts, ...map },
    droppedCells: [...new Set([...s.droppedCells, ...dropKeys])],
    verdictSummary: {
      supported: vr.summary.supported ?? 0,
      partial: vr.summary.partial ?? 0,
      dropped: vr.summary.dropped ?? 0,
    },
  }));
  return;
}
```

**枚举防御**(记忆 [[enum guard]]):上述早 return 已确保 6 个新事件不落到 `ev.data.node` fall-through(codex P1#1 根治);保持现有 if-chain 对未知事件的安全处理(不读不存在字段)。

- [ ] **Step 3: 验证 build 绿 + 手测切片有值**

Run: `cd frontend && pnpm build`
Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/runStore.ts
git commit -m "feat(planC): runStore consumes query/source/cell_row/evidence_delta/verdict_recheck"
```

### Task 4: REST client —— queries / curation-drops

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 加两个 fetch 函数**

仿现有 `jsonFetch<T>` 模式(架构报告:`lib/api.ts`):

```typescript
// codex P1#4:jsonFetch 已自动前缀 /api(api.ts:22-25)→ 路径**不要**再写 /api,否则 /api/api/...
export const fetchQueries = (runId: string) =>
  jsonFetch<QueryRecord[]>(`/runs/${runId}/queries`);

export const fetchCurationDrops = (runId: string) =>
  jsonFetch<CurationDrop[]>(`/runs/${runId}/curation-drops`);
```

import `QueryRecord` / `CurationDrop`(Task 1)。

- [ ] **Step 2: 验证 build 绿**

Run: `cd frontend && pnpm build`
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(planC): REST client fetchQueries + fetchCurationDrops"
```

---

## Epic 2 — `agent_skills` 后端持久化(垂直切片,唯一后端增量)

> spec §6.3/§7.3「技能子系统本期后端持久化」。run 无关的 agent 配置。后端走 TDD(成功+失败两路,CLAUDE.md 测试纪律)。验证 = `.venv/bin/python -m pytest`。**WSL2 Clash**:跑 pytest 是本地 SQLite 不联网,无需代理处理;若同 shell 后续要真打 LLM 才 unset 代理。

### Task 5: `agent_skills` 表

**Files:**
- Modify: `rivalradar/storage/db.py`
- Test: `tests/test_agent_skills.py`(新建)

**背景**:仿现有 `queries` / `curation_drops` 建表(Plan A/B 模式,`db.py:57-79`)。PK `(agent_id, skill_id)`。

- [ ] **Step 1: 写失败测试(表存在 + 列)**

`tests/test_agent_skills.py`:

```python
import sqlite3
from rivalradar.storage.db import connect, init_db

def test_agent_skills_table_exists(tmp_path):
    db = tmp_path / "t.db"
    conn = connect(str(db)); init_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(agent_skills)")}
    assert cols == {"agent_id", "skill_id", "version", "enabled", "installed_at"}
```

(若 `connect`/`init_db` 名称不同,按 `db.py` 实际导出名调整 —— 先 grep `def ` in db.py 对齐。)

- [ ] **Step 2: 跑测试看它失败**

Run: `.venv/bin/python -m pytest tests/test_agent_skills.py -v`
Expected: FAIL(no such table: agent_skills)。

- [ ] **Step 3: 建表**

在 `db.py` 的 schema 初始化处(`queries`/`curation_drops` CREATE 附近)加:

```python
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS agent_skills (
        agent_id    TEXT NOT NULL,
        skill_id    TEXT NOT NULL,
        version     TEXT NOT NULL DEFAULT 'v1',
        enabled     INTEGER NOT NULL DEFAULT 1,
        installed_at TEXT NOT NULL,
        PRIMARY KEY (agent_id, skill_id)
    )
    """
)
```

- [ ] **Step 4: 跑测试看它通过**

Run: `.venv/bin/python -m pytest tests/test_agent_skills.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/storage/db.py tests/test_agent_skills.py
git commit -m "feat(planC): agent_skills table"
```

### Task 6: repository CRUD

**Files:**
- Modify: `rivalradar/storage/repository.py`
- Test: `tests/test_agent_skills.py`

- [ ] **Step 1: 写失败测试(upsert / list / delete)**

追加到 `tests/test_agent_skills.py`:

```python
from rivalradar.storage.repository import (
    list_agent_skills, upsert_agent_skill, delete_agent_skill,
)

def test_upsert_list_delete(tmp_path):
    db = tmp_path / "t.db"
    conn = connect(str(db)); init_db(conn)
    upsert_agent_skill(conn, "collector", "evidence-retrieving", "v1", True)
    upsert_agent_skill(conn, "collector", "evidence-retrieving", "v1", False)  # 幂等覆盖
    upsert_agent_skill(conn, "writer", "grounded-report-synthesis", "v1", True)
    rows = list_agent_skills(conn)
    assert len(rows) == 2
    coll = [r for r in rows if r["agent_id"] == "collector"][0]
    assert coll["enabled"] is False and coll["skill_id"] == "evidence-retrieving"
    delete_agent_skill(conn, "collector", "evidence-retrieving")
    rows2 = list_agent_skills(conn)
    assert len(rows2) == 1 and rows2[0]["agent_id"] == "writer"
```

- [ ] **Step 2: 跑测试看它失败**

Run: `.venv/bin/python -m pytest tests/test_agent_skills.py::test_upsert_list_delete -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 repository 函数**

在 `repository.py`(仿 `replace_curation_drops`/`list_curation_drops` 风格,`repository.py:297-319`):

```python
def upsert_agent_skill(conn, agent_id: str, skill_id: str, version: str, enabled: bool) -> None:
    conn.execute(
        """
        INSERT INTO agent_skills (agent_id, skill_id, version, enabled, installed_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(agent_id, skill_id) DO UPDATE SET version=excluded.version, enabled=excluded.enabled
        """,
        (agent_id, skill_id, version, 1 if enabled else 0, _now()),
    )
    conn.commit()


def list_agent_skills(conn) -> list[dict]:
    cur = conn.execute(
        "SELECT agent_id, skill_id, version, enabled, installed_at FROM agent_skills ORDER BY agent_id, installed_at"
    )
    return [
        {"agent_id": r[0], "skill_id": r[1], "version": r[2], "enabled": bool(r[3]), "installed_at": r[4]}
        for r in cur.fetchall()
    ]


def delete_agent_skill(conn, agent_id: str, skill_id: str) -> None:
    conn.execute("DELETE FROM agent_skills WHERE agent_id=? AND skill_id=?", (agent_id, skill_id))
    conn.commit()
```

`_now()`:**codex P1#5 核验** —— repository 现有时间 helper 是 `_now()`(`repository.py:12-13`),直接用;**勿写 `_now_iso()`(不存在,会运行时崩)**。

- [ ] **Step 4: 跑测试看它通过**

Run: `.venv/bin/python -m pytest tests/test_agent_skills.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add rivalradar/storage/repository.py tests/test_agent_skills.py
git commit -m "feat(planC): agent_skills repository CRUD"
```

### Task 7: REST `GET/PUT/DELETE /agent-skills`

**Files:**
- Create: `rivalradar/api/agent_skills.py`
- Modify: `rivalradar/api/app.py`
- Test: `tests/test_agent_skills.py`

**背景**:仿现有 reads/runs 路由风格(`api/reads.py:19-21`)。**codex P1#6 核验**:db 依赖是 `get_db_conn`(来自 `rivalradar/api/deps.py:16-23`),**不是** `get_conn`;路由**无 `/api` 前缀**(前端 vite proxy 加,`app.py:78-84`)。请求体校验用 Pydantic(仿 `schemas.py`)。

- [ ] **Step 1: 写失败测试(REST 成功 + 失败两路)**

追加(用 `TestClient`,仿 `tests/test_api_reads.py`):

```python
from fastapi.testclient import TestClient
from rivalradar.api.app import create_app

def _client(tmp_path):
    return TestClient(create_app(db_path=str(tmp_path / "api.db")))

def test_agent_skills_rest_roundtrip(tmp_path):
    c = _client(tmp_path)
    assert c.get("/agent-skills").json() == []                       # 空表
    r = c.put("/agent-skills", json={"agent_id": "writer", "skill_id": "grounded-report-synthesis", "version": "v1", "enabled": True})
    assert r.status_code == 200
    rows = c.get("/agent-skills").json()
    assert len(rows) == 1 and rows[0]["enabled"] is True
    c.put("/agent-skills", json={"agent_id": "writer", "skill_id": "grounded-report-synthesis", "version": "v1", "enabled": False})
    assert c.get("/agent-skills").json()[0]["enabled"] is False      # upsert
    d = c.delete("/agent-skills/writer/grounded-report-synthesis")
    assert d.status_code == 200
    assert c.get("/agent-skills").json() == []

def test_agent_skills_put_validation(tmp_path):
    c = _client(tmp_path)
    r = c.put("/agent-skills", json={"agent_id": "writer"})          # 缺字段
    assert r.status_code == 422
```

- [ ] **Step 2: 跑测试看它失败**

Run: `.venv/bin/python -m pytest tests/test_agent_skills.py -k rest -v`
Expected: FAIL(404,路由不存在)。

- [ ] **Step 3: 实现路由**

`rivalradar/api/agent_skills.py`(codex P1#6:用真实依赖 `get_db_conn` from `rivalradar.api.deps`,路由无 `/api` 前缀):

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from rivalradar.storage import repository as repo
from rivalradar.api.deps import get_db_conn

router = APIRouter()

class AgentSkillIn(BaseModel):
    agent_id: str
    skill_id: str
    version: str = "v1"
    enabled: bool = True

@router.get("/agent-skills")
def get_agent_skills(conn=Depends(get_db_conn)):
    return repo.list_agent_skills(conn)

@router.put("/agent-skills")
def put_agent_skill(body: AgentSkillIn, conn=Depends(get_db_conn)):
    repo.upsert_agent_skill(conn, body.agent_id, body.skill_id, body.version, body.enabled)
    return {"ok": True}

@router.delete("/agent-skills/{agent_id}/{skill_id}")
def delete_agent_skill_route(agent_id: str, skill_id: str, conn=Depends(get_db_conn)):
    repo.delete_agent_skill(conn, agent_id, skill_id)
    return {"ok": True}
```

在 `app.py` 注册:`app.include_router(agent_skills.router)`(对齐现有 include_router 写法 + prefix;若其它路由无 `/api` prefix 而是前端 vite proxy 加,则保持一致,**勿擅自加 prefix**)。

- [ ] **Step 4: 跑测试看它通过**

Run: `.venv/bin/python -m pytest tests/test_agent_skills.py -v`
Expected: PASS(全 4 测试)。

- [ ] **Step 5: 全量回归**

Run: `.venv/bin/python -m pytest`
Expected: 现有 383 + 新增全绿。

- [ ] **Step 6: Commit**

```bash
git add rivalradar/api/agent_skills.py rivalradar/api/app.py tests/test_agent_skills.py
git commit -m "feat(planC): REST GET/PUT/DELETE /agent-skills + tests"
```

### Task 8: 前端技能 catalog + store + REST client

**Files:**
- Create: `frontend/src/lib/skillCatalog.ts`
- Create: `frontend/src/stores/skillsStore.ts`
- Modify: `frontend/src/lib/api.ts`

**背景**:catalog(DEFAULT_SKILLS + MARKET)是 UI 元数据,留前端(C-D4)。`skillState` 形状 = `{<skill_id>:{version,enabled}}`。merge 规则:mount 时 GET /agent-skills;空表→从 DEFAULT_SKILLS seed(bulk PUT)并用默认 state;非空→表为准,按 skill_id 合并 catalog 元数据(MARKET 已装项也能渲染)。

- [ ] **Step 1: port `skillCatalog.ts`(DEFAULT_SKILLS + MARKET verbatim)**

把 2e 的 `DEFAULT_SKILLS`(collector 3 / analyst 5 / writer 3 含 `grounded-report-synthesis` core / qc 4)与 `MARKET`(每 agent 2 项)逐字搬入(2e 提取 §3,内容已 verbatim;**只保留 `id/name/do/core`,删 `why`/`boundary`** —— spec §6.3「不展示 why/boundary」,数据也不必带进前端 catalog):

```typescript
import type { AgentId } from '../types/agents';
export interface SkillDef { id: string; name: string; do: string; core?: boolean }
export interface SkillState { version: string; enabled: boolean }

export const DEFAULT_SKILLS: Record<AgentId, SkillDef[]> = {
  collector: [
    { id: 'evidence-retrieving', name: '证据检索', do: '按「竞品×6维×中英双语」模板生成查询,Tavily→Exa 顺序回退联网搜索,并行抓取后按 id 去重、过滤空内容,产出原始证据集。' },
    { id: 'evidence-grooming',   name: '证据整备', do: '对原始证据做正文清洗(剥图床 / 链接壳、压空白)+ 按来源优先级排序(官方 > 已知评价平台 > 杂源)。' },
    { id: 'gap-refetching',      name: '缺口补采', do: 'retry 时只针对 QC 标出的 missing_evidence / low_coverage 缺口,broaden 换词(评测 / 对比 / 替代方案)精准补采,不全量重跑。' },
  ],
  analyst: [
    { id: 'profile-extracting',   name: '画像抽取',     do: '从证据结构化抽取四类 profile(功能树 / 定价模型 / 用户画像 / SWOT),每条挂 evidence_refs。' },
    { id: 'comparison-matrixing', name: '对比矩阵构建', do: '只在请求维度上逐维横向对比(每维小调用),cell 带 value_type + value + evidence_refs,无证据维不产行(显「-」),绝不张冠李戴。' },
    { id: 'grounding-discipline', name: '溯源粒度纪律', do: '强制「只依据给定证据、每条挂 ref、id 只能取自给定证据、禁止过度拆解」的横切约束。' },
    { id: 'extraction-degrading', name: '抽取降级兜底', do: '单项抽取失败时返空占位 + 记 degraded_sink,其余照常,绝不杀整 run。' },
  ],
  writer: [
    { id: 'grounded-report-synthesis', name: '有据报告综合', core: true, do: '封装 RivalRadar 真打验证(18.5→24/30)整套撰写方法论:总-分-总骨架 + Hybrid 分工(事实/引用走确定性 Python 模板、判断/综合走 LLM 标「AI 综合」)+ 引用完整性即结构保证(0 broken refs)+ ReportInsight 三段 Schema 强制(市场锚定/战略推论/时间分层)+ 反套话黑名单。' },
    { id: 'body-rendering',      name: '确定性正文渲染', do: '纯 Python 模板把分析结果机械渲染成 Markdown(逐竞品 Profile + 对比表 + 来源清单 evidence_id→[标题](URL)(as of date)),缺 cell 标「-」,不在证据集的 id 标 missing。' },
    { id: 'insight-synthesizing', name: '执行洞察生成',  do: '基于正文调 LLM 产 ReportInsight 三段(market_context 禁编市场规模数字 / differentiation_thesis 因为 X 所以 Y + 母公司战略映射 / actionable_takeaway 短中长期命令式),严禁引入正文外数字/新事实/新竞品,禁套话。' },
  ],
  qc: [
    { id: 'mechanical-gating',  name: '机械三闸', do: '免 LLM 始终跑的确定性硬闸(check_traceability 结论必挂存在的引用 + check_ontology 维度落 6 维本体 + check_coverage 每竞品每维应有 cell)。' },
    { id: 'entailment-judging', name: '蕴含判定', do: '逐结论一次 LLM 调用判「被引证据是否真支撑结论」,不支撑 = 幻觉;并发 ≤8,可 scope 到请求维度/只判矩阵 cell;决策级对称提供。' },
    { id: 'evidence-curating',  name: '证据策展', do: '策展人模型(非法官):把站不住的 cell(机械悬空 + 蕴含不支撑)直接丢弃返回 (curated, dropped) 而非否决整 run;丢后空 row 消失→coverage 发现缺口→触发 broaden 补搜。' },
    { id: 'output-sanitizing',  name: '输出脱敏', do: '把 QCResult 投影成可公开 serve 形状(detail 换罐装中文文案、越界 dimension 替占位),绝不外泄 LLM 文本/异常文本。' },
  ],
};

export const MARKET: Record<AgentId, SkillDef[]> = {
  collector: [
    { id: 'domain-allowlisting', name: '来源域名白名单',   do: '按行业维护可信域名清单,检索时优先选取白名单内来源,杂源降权。' },
    { id: 'bilingual-templating', name: '中英查询模板扩展', do: '为指定维度补充英文检索模板词,提升海外来源召回。' },
  ],
  analyst: [
    { id: 'dimension-laddering',      name: '维度粒度分层',   do: '按战略/范围/结构对维度做显式分层,避免「功能多」与「定位准」混为一谈。' },
    { id: 'matrix-conflict-flagging', name: '矩阵口径冲突标注', do: '同一格多源口径不一致时标注分歧,留待蕴含判定裁决。' },
  ],
  writer: [
    { id: 'audience-toning',     name: '受众语气适配',   do: '按 PM/高管/采购切换洞察段落的详略与措辞。' },
    { id: 'takeaway-horizoning', name: '行动项时间分层', do: '把 actionable_takeaway 拆成短/中/长期命令式条目。' },
  ],
  qc: [
    { id: 'source-bias-tagging', name: '来源偏见标注',   do: '标注厂商自述/软文等高偏见来源,提示结论强度折扣(基于来源类型,不做内容情感打分)。' },
    { id: 'staleness-flagging',  name: '证据时效红线', do: '对超过红线天数的证据加「陈旧」标(基于 as_of 日期,确定性比较,非实时监控)。' },
  ],
};
```

- [ ] **Step 2: REST client(`lib/api.ts`)**

```typescript
// codex P1#4:jsonFetch 已前缀 /api → 勿写 /api
export const fetchAgentSkills = () => jsonFetch<AgentSkillRow[]>(`/agent-skills`);
export const putAgentSkill = (body: { agent_id: string; skill_id: string; version: string; enabled: boolean }) =>
  jsonFetch<{ ok: boolean }>(`/agent-skills`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
export const deleteAgentSkill = (agentId: string, skillId: string) =>
  jsonFetch<{ ok: boolean }>(`/agent-skills/${agentId}/${skillId}`, { method: 'DELETE' });
```

- [ ] **Step 3: `skillsStore.ts`**

```typescript
import { create } from 'zustand';
import type { AgentId } from '../types/agents';
import { DEFAULT_SKILLS, MARKET, type SkillDef, type SkillState } from '../lib/skillCatalog';
import { fetchAgentSkills, putAgentSkill, deleteAgentSkill } from '../lib/api';

interface SkillsState {
  // 每 agent 当前已装技能列表(catalog 顺序 + 已装 market) + 每技能状态
  installed: Record<AgentId, SkillDef[]>;
  state: Record<string, SkillState>;   // skill_id → {version,enabled}
  behaviorNote: string;                 // 诚实标注「行为接入下一期」
  loaded: boolean;
  load: () => Promise<void>;
  toggle: (agentId: AgentId, skillId: string) => Promise<void>;
  install: (agentId: AgentId, skillId: string) => Promise<void>;
  remove: (agentId: AgentId, skillId: string) => Promise<void>;
}

const seedFromDefaults = () => {
  const installed = {} as Record<AgentId, SkillDef[]>;
  const state: Record<string, SkillState> = {};
  (Object.keys(DEFAULT_SKILLS) as AgentId[]).forEach((role) => {
    installed[role] = [...DEFAULT_SKILLS[role]];
    DEFAULT_SKILLS[role].forEach((s) => { state[s.id] = { version: 'v1', enabled: true }; });
  });
  return { installed, state };
};

const catalogLookup = (skillId: string): SkillDef | null => {
  for (const role of Object.keys(DEFAULT_SKILLS) as AgentId[]) {
    const d = DEFAULT_SKILLS[role].find((s) => s.id === skillId) || MARKET[role].find((s) => s.id === skillId);
    if (d) return d;
  }
  return null;
};

export const useSkillsStore = create<SkillsState>((set, get) => ({
  ...seedFromDefaults(),
  behaviorNote: '技能行为接入下一期 —— 本期装/删/开关不改变 agent 运行时行为',
  loaded: false,
  load: async () => {
    let rows;
    try { rows = await fetchAgentSkills(); } catch { set({ loaded: true }); return; } // 后端不可达 → 用默认(graceful)
    if (rows.length === 0) {
      // 空表:seed 默认到后端(one-time bulk PUT),用默认 state
      const { installed, state } = seedFromDefaults();
      await Promise.all(
        (Object.keys(DEFAULT_SKILLS) as AgentId[]).flatMap((role) =>
          DEFAULT_SKILLS[role].map((s) => putAgentSkill({ agent_id: role, skill_id: s.id, version: 'v1', enabled: true }).catch(() => {})),
        ),
      );
      set({ installed, state, loaded: true });
      return;
    }
    // 非空:表权威。按 agent 分组,catalog 查元数据;catalog 没有的 skill_id 跳过(脏数据防御)
    const installed = {} as Record<AgentId, SkillDef[]>;
    const state: Record<string, SkillState> = {};
    (Object.keys(DEFAULT_SKILLS) as AgentId[]).forEach((r) => { installed[r] = []; });
    rows.forEach((row) => {
      const def = catalogLookup(row.skill_id);
      if (!def) return;
      const role = row.agent_id as AgentId;
      if (!installed[role]) installed[role] = [];
      installed[role].push(def);
      state[row.skill_id] = { version: row.version, enabled: row.enabled };
    });
    set({ installed, state, loaded: true });
  },
  toggle: async (agentId, skillId) => {
    const cur = get().state[skillId]; if (!cur) return;
    const next = { ...cur, enabled: !cur.enabled };
    set((s) => ({ state: { ...s.state, [skillId]: next } }));   // 乐观更新
    await putAgentSkill({ agent_id: agentId, skill_id: skillId, version: next.version, enabled: next.enabled }).catch(() => {});
  },
  install: async (agentId, skillId) => {
    const def = MARKET[agentId].find((s) => s.id === skillId); if (!def) return;
    if (get().installed[agentId].some((s) => s.id === skillId)) return;  // 已装
    set((s) => ({
      installed: { ...s.installed, [agentId]: [...s.installed[agentId], def] },
      state: { ...s.state, [skillId]: { version: 'v1', enabled: true } },
    }));
    await putAgentSkill({ agent_id: agentId, skill_id: skillId, version: 'v1', enabled: true }).catch(() => {});
  },
  remove: async (agentId, skillId) => {
    set((s) => {
      const { [skillId]: _, ...rest } = s.state;
      return { installed: { ...s.installed, [agentId]: s.installed[agentId].filter((x) => x.id !== skillId) }, state: rest };
    });
    await deleteAgentSkill(agentId, skillId).catch(() => {});
  },
}));
```

> graceful 兜底(记忆:外部调用 graceful skip 是 production 必须):后端不可达时用默认 catalog,UI 仍可用(只是不持久化)。

- [ ] **Step 4: 验证 build 绿**

Run: `cd frontend && pnpm build`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/skillCatalog.ts frontend/src/stores/skillsStore.ts frontend/src/lib/api.ts
git commit -m "feat(planC): skill catalog + skillsStore + REST client (framework real, behavior phase-2)"
```

---

## Epic 3 — 设计 token + ROLE 注册表 + 头像 vendoring

> 视觉前置:把 2e 的新 token 与身份色落进设计系统(承 DESIGN.md v5)。**改 token 前重读 DESIGN.md「v5 设计系统增量」节**(CLAUDE.md:视觉决策前先读 DESIGN.md)。验证 = `pnpm build` 绿(token 加入不破现有)。

### Task 9: 新增 CSS token(身份色 + 2e 缺口 token)

**Files:**
- Modify: `frontend/src/styles/globals.css`
- Modify: `frontend/tailwind.config.ts`

**背景**:2e 提取 §14 列出现有 React token 已覆盖大部分(bg/surface/border/accent/verdict-* 精确匹配)。**必须新增**(无现有等价):4 身份色 `--id-*` + 每角色 `line/soft/avbg` 三档、`--surface-sink #ECEAE3`、`--border-strong #C4C0B5`、`--ink #141817`、`--text-faint #9AA29C`、`--accent-deep #0B574D`、`--accent-line #BCD9D2`、`--v-sup-soft #E2EFE7`/`--v-par-soft #F6EEDB`/`--v-uns-soft #F4E1E0`、`--r-pill 5px`。**身份色 ≠ 现有 `--seat-*`**(C-D9 提及;`--seat-*` 复用 accent/warning 等,身份色是独立低饱和值,勿混)。

- [ ] **Step 1: globals.css `:root`(Light)加 token**

在 `:root`(light)块加(承 DESIGN.md v5 §agent 人格层身份色):

```css
/* Plan C: agent 身份色(低饱和,DESIGN.md v5) */
--id-collector:#2C6E63; --id-collector-line:#A9CCC5; --id-collector-soft:#E5EFEC;
--id-analyst:#9A6312;   --id-analyst-line:#DCC79A;   --id-analyst-soft:#F4EBD7;
--id-writer:#3A6489;    --id-writer-line:#A9C0D6;    --id-writer-soft:#E5EDF4;
--id-qc:#7A5C8A;        --id-qc-line:#C5B2D0;        --id-qc-soft:#EEE7F2;
/* Plan C: 2e 缺口 token */
--surface-sink:#ECEAE3; --border-strong:#C4C0B5; --ink:#141817; --text-faint:#9AA29C;
--accent-deep:#0B574D; --accent-line:#BCD9D2;
--v-sup-soft:#E2EFE7; --v-par-soft:#F6EEDB; --v-uns-soft:#F4E1E0;
```

- [ ] **Step 2: `.dark` 块加深色对应值**

深色身份色调亮(承 DESIGN.md dark 色板自动跟随逻辑)。在 `.dark` 块加:

```css
.dark {
  --id-collector:#4FB0A0; --id-collector-line:#2E5B53; --id-collector-soft:#16322D;
  --id-analyst:#D7A33D;   --id-analyst-line:#5A4B22;   --id-analyst-soft:#352B14;
  --id-writer:#78AEDA;    --id-writer-line:#2C4660;    --id-writer-soft:#16263A;
  --id-qc:#B79BD0;        --id-qc-line:#4A3C57;        --id-qc-soft:#2A2233;
  --surface-sink:#1A201D; --border-strong:#48524D; --ink:#ECEBE4; --text-faint:#7B847F;
  --accent-deep:#7FD4C5; --accent-line:#2A574E;
  --v-sup-soft:#173B2A; --v-par-soft:#3A2E12; --v-uns-soft:#3A1E1D;
}
```

(深色值取近似,与现有 dark 色板风格一致;/browse 深色检查时若对比度不足在 Epic 8 微调。)

- [ ] **Step 3: tailwind.config.ts 暴露新 color token**

在 `theme.extend.colors` 加(仿现有 `accent: 'var(--accent)'` 写法):

```typescript
'id-collector': 'var(--id-collector)', 'id-collector-line': 'var(--id-collector-line)', 'id-collector-soft': 'var(--id-collector-soft)',
'id-analyst': 'var(--id-analyst)', 'id-analyst-line': 'var(--id-analyst-line)', 'id-analyst-soft': 'var(--id-analyst-soft)',
'id-writer': 'var(--id-writer)', 'id-writer-line': 'var(--id-writer-line)', 'id-writer-soft': 'var(--id-writer-soft)',
'id-qc': 'var(--id-qc)', 'id-qc-line': 'var(--id-qc-line)', 'id-qc-soft': 'var(--id-qc-soft)',
'surface-sink': 'var(--surface-sink)', 'border-strong': 'var(--border-strong)', ink: 'var(--ink)', 'text-faint': 'var(--text-faint)',
'accent-deep': 'var(--accent-deep)', 'accent-line': 'var(--accent-line)',
'v-sup-soft': 'var(--v-sup-soft)', 'v-par-soft': 'var(--v-par-soft)', 'v-uns-soft': 'var(--v-uns-soft)',
```

> 注:身份色多为运行时按 agent 动态切换 → 实际组件常用内联 `style={{'--idc': roleColor}}` + `text-[color:var(--idc)]`,Tailwind token 主要给静态用法。两种都保留。`--r-pill 5px` 用任意值类 `rounded-[5px]` 即可,不必入 config。

- [ ] **Step 4: 验证 build 绿**

Run: `cd frontend && pnpm build`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/globals.css frontend/tailwind.config.ts
git commit -m "feat(planC): add agent identity-color tokens + 2e gap tokens (DESIGN.md v5)"
```

### Task 10: ROLE 注册表 + vendored 头像 + 去 emoji persona

**Files:**
- Create: `frontend/src/lib/agentRoles.ts`
- Create: `frontend/src/lib/avatar.ts`
- Create: `frontend/public/agents/{collector,analyst,writer,qc}.svg`
- Modify: `frontend/src/lib/agentConstants.ts`, `frontend/src/types/agents.ts`

**背景**:DESIGN.md v5「立场(写死,防回退 v3 office)」—— 工牌=机构级持证专家身份,**严禁** 卡通动物/速记代号。现 `agentConstants.ts` 的 owl/fox/raccoon/turtle 🦉🦊🦝🐢 persona 必须去除(也指向不存在的 `/agents/owl` 资产)。

- [ ] **Step 1: vendor 4 张 lorelei 头像(海外代理)**

DiceBear 是海外服务 → **保留代理**(同 codex,`ALL_PROXY=http://172.30.64.1:7897`;**勿 unset**)。seeds 取自 2e ROLE:

```bash
cd /home/liujunxi/project/RivalRadar/frontend/public && mkdir -p agents
ALL_PROXY=http://172.30.64.1:7897 https_proxy=http://172.30.64.1:7897 \
  curl -fsSL "https://api.dicebear.com/9.x/lorelei/svg?seed=rivalradar-collector-c01&backgroundColor=e5efec&radius=10" -o agents/collector.svg
ALL_PROXY=http://172.30.64.1:7897 https_proxy=http://172.30.64.1:7897 \
  curl -fsSL "https://api.dicebear.com/9.x/lorelei/svg?seed=rivalradar-analyst-a01&backgroundColor=f4ebd7&radius=10" -o agents/analyst.svg
ALL_PROXY=http://172.30.64.1:7897 https_proxy=http://172.30.64.1:7897 \
  curl -fsSL "https://api.dicebear.com/9.x/lorelei/svg?seed=rivalradar-writer-w01&backgroundColor=e5edf4&radius=10" -o agents/writer.svg
ALL_PROXY=http://172.30.64.1:7897 https_proxy=http://172.30.64.1:7897 \
  curl -fsSL "https://api.dicebear.com/9.x/lorelei/svg?seed=rivalradar-qc-q01&backgroundColor=eee7f2&radius=10" -o agents/qc.svg
ls -la agents/   # 4 个 .svg,每个应 >1KB
```

若代理拿不到(网络),降级:写 4 个极简占位 SVG(身份色填充圆 + 职能首字「采/析/撰/质」),保证离线可用。占位 SVG 模板(以 collector 为例):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#E5EFEC"/><circle cx="32" cy="26" r="13" fill="#2C6E63"/><text x="32" y="54" font-size="14" text-anchor="middle" fill="#2C6E63" font-family="sans-serif">采</text></svg>
```

- [ ] **Step 2: `agentRoles.ts`(ROLE 注册表,verbatim from 2e §4)**

```typescript
import type { AgentId } from '../types/agents';
export interface AgentRole {
  id: AgentId; mono: string; name: string; no: string; fn: string;
  col: string; line: string; soft: string;   // 身份色三档(指向 CSS var)
  avatar: string;                              // 本地头像路径
}
export const ROLES: Record<AgentId, AgentRole> = {
  collector: { id: 'collector', mono: '采', name: '采集员', no: 'RR-C01', fn: '证据采集', col: 'var(--id-collector)', line: 'var(--id-collector-line)', soft: 'var(--id-collector-soft)', avatar: '/agents/collector.svg' },
  analyst:   { id: 'analyst',   mono: '析', name: '分析员', no: 'RR-A01', fn: '对比分析', col: 'var(--id-analyst)',   line: 'var(--id-analyst-line)',   soft: 'var(--id-analyst-soft)',   avatar: '/agents/analyst.svg' },
  writer:    { id: 'writer',    mono: '撰', name: '撰写员', no: 'RR-W01', fn: '报告撰写', col: 'var(--id-writer)',    line: 'var(--id-writer-line)',    soft: 'var(--id-writer-soft)',    avatar: '/agents/writer.svg' },
  qc:        { id: 'qc',        mono: '质', name: '质检员', no: 'RR-Q01', fn: '质量校验', col: 'var(--id-qc)',        line: 'var(--id-qc-line)',        soft: 'var(--id-qc-soft)',        avatar: '/agents/qc.svg' },
};
export const ROLE_ORDER: AgentId[] = ['collector', 'analyst', 'writer', 'qc'];
export const roleOf = (id: string): AgentRole | null => (ROLES as Record<string, AgentRole>)[id] ?? null;
```

- [ ] **Step 3: `avatar.ts`(onError 回落身份底纹)**

```typescript
import type { AgentId } from '../types/agents';
import { ROLES } from './agentRoles';
export const avatarSrc = (id: AgentId): string => ROLES[id].avatar;
// img onError handler:隐藏 broken img,露父级身份色底纹(父 div 已设 background:var(--idc-soft))
export const onAvatarError = (e: React.SyntheticEvent<HTMLImageElement>) => { e.currentTarget.style.display = 'none'; };
```

- [ ] **Step 4: 去 `agentConstants.ts` / `types/agents.ts` 的 emoji 动物 persona**

`types/agents.ts`:保留 `AgentId = 'collector'|'analyst'|'writer'|'qc'`;**删** `AgentDescriptor.persona`(emoji)、`avatar`(sprite)、`workspace_seat`(office 座位语义,DESIGN.md v5 禁 office)字段。若 `AgentTeam`/`TEAM_COMPETITOR_RESEARCH` 仅被 office 死代码用,标注但不删(C-D9);若被活代码引用,改为引 `ROLES`。

`agentConstants.ts`:`AGENTS` 数组的 `persona`/`avatar: '/agents/owl'`/`workspace_seat` 删除;若有活 caller 读 `name`,改为从 `ROLES[id].name` 取。**grep 两侧 caller**(记忆 [[silent CSS / type-domain 混淆]]:跨 domain identifier 必须 grep 两侧):`grep -rn "persona\|workspace_seat\|agentById\|AGENTS\b" frontend/src` → 改活引用,office 死代码保留。

- [ ] **Step 5: 验证 build 绿**

Run: `cd frontend && pnpm build`
Expected: PASS(若 office 死代码引用被删字段报错 → 该文件是 unmounted 死代码,可在其顶部用 `// @ts-nocheck` 或局部修引用;**优先**改为不依赖被删字段,避免 ts-nocheck 扩大;若纯死代码且 tsc 仍编译它,最小修复使其编译通过,不扩重构)。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/agentRoles.ts frontend/src/lib/avatar.ts frontend/public/agents/ frontend/src/lib/agentConstants.ts frontend/src/types/agents.ts
git commit -m "feat(planC): ROLE registry + vendored lorelei avatars; drop v3 office emoji persona"
```

---

## Epic 4 — 融合主轴布局 + 研究员工作台 shell

> spec §6.1。2e 基线:StatusBar 54px sticky + grid `1fr 472px` + done 收窄。验证 = `pnpm build` 绿 + `/browse` 看双栏布局(右栏现为空 shell,数据消费在 Epic 5)。

### Task 11: CockpitLayout → 2e 融合主轴 + done 收窄

**Files:**
- Modify: `frontend/src/components/cockpit/CockpitLayout.tsx`

**背景**:现 CockpitLayout(架构报告:StatusBar + 2 列 grid `lg:1.63fr/1fr`,右挂 `ExecutionStream`)。改为 2e 基线 `1fr 472px`,右挂新 `ResearcherWorkbench`(Task 12),done 态右栏收窄。

- [ ] **Step 1: 改 grid + 挂 workbench + done 收窄**

把 grid 列改为 2e 基线;running 时右 472px,done(terminal)收窄为摘要条。读 `runStore` 的 `status` 判 terminal:

```tsx
import { ResearcherWorkbench } from '../workbench/ResearcherWorkbench';
import { useRunStore } from '../../stores/runStore';
// ...
const status = useRunStore((s) => s.status);
const terminal = status === 'done' || status === 'degraded' || status === 'insufficient_evidence' || status === 'failed' || status === 'cancelled';
// grid:running → 1fr 472px;done → 1fr 280px(收窄,左栏成焦点;DESIGN.md v5 done 态)
return (
  <div className="flex flex-col h-[100dvh]">
    <StatusBar />
    <div
      className="grid flex-1 min-h-0"
      style={{ gridTemplateColumns: terminal ? '1fr 280px' : '1fr 472px' }}
    >
      <main className="overflow-y-auto bg-bg px-6 pb-14 pt-5">{children}</main>
      <aside className="border-l border-border bg-surface-subtle overflow-hidden flex flex-col relative">
        <ResearcherWorkbench collapsed={terminal} />
      </aside>
    </div>
  </div>
);
```

(精确 className 对齐现有 CockpitLayout 既有 wrapper;保留现有 StatusBar 挂载。响应式:`max-lg:grid-cols-1` 单栏 —— 用 `lg:` 前缀控制,<1024 右栏降折叠/顶条,见 Epic 8 状态覆盖。)

- [ ] **Step 2: 响应式断点(承 2e + DESIGN.md)**

`<1024` 单栏纵堆决策面优先:grid 用 `style` 时配 `class="max-lg:!grid-cols-1"`(或用 Tailwind 响应式 grid 类替代 inline style 的列定义,inline 仅给 ≥lg 宽度差异)。具体:用 Tailwind `grid-cols-1 lg:grid-cols-[1fr_472px]`(running)与 `lg:grid-cols-[1fr_280px]`(done)动态切;<lg 右栏移到下方(DOM 顺序左先 → 单栏时决策面在上)。`prefers-reduced-motion` 禁动画(globals 已有或 Epic 8 补)。

- [ ] **Step 3: 验证 build + browse**

Run: `cd frontend && pnpm build` → PASS。
`/browse`(gstack)开一个 run 页(demo 或 fixture),看:≥1280 双栏左宽右 472;done 后右收窄;<1024 单栏。**禁用 `mcp__claude-in-chrome__*`**。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cockpit/CockpitLayout.tsx
git commit -m "feat(planC): fusion-axis layout (1fr/472px) + done-state narrowing"
```

### Task 12: `ResearcherWorkbench` shell

**Files:**
- Create: `frontend/src/components/workbench/ResearcherWorkbench.tsx`

**背景**:2e §1 DOM:`.engine > .eng-hd(kicker + now + prog bar) + .eng-body(roster + live-pane + timeline)`。本 Task 只搭 shell + 区块占位,各面板在 Epic 5 填。

- [ ] **Step 1: shell + 区块插槽**

```tsx
import { AgentRoster } from './AgentRoster';
import { SearchStation } from './SearchStation';
import { SourceCards } from './SourceCards';
import { RetryLoop } from './RetryLoop';
import { ReportStation } from './ReportStation';
import { ExecutionTimeline } from './ExecutionTimeline';
import { useRunStore } from '../../stores/runStore';

export function ResearcherWorkbench({ collapsed }: { collapsed: boolean }) {
  const status = useRunStore((s) => s.status);
  if (collapsed) return <WorkbenchSummary />;   // done 态摘要条(Epic 8 实现;占位先渲简版)
  return (
    <>
      <div className="px-[18px] pt-[15px] pb-[13px] border-b border-border bg-surface">
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted">研究团队 · 实时引擎</div>
        <div className="text-[13px] font-semibold text-text-primary mt-1">{statusLabel(status)}</div>
      </div>
      <div className="flex-1 overflow-y-auto px-[18px] pt-[14px] pb-7">
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mb-2">研究团队 · 持证员工</div>
        <AgentRoster />
        <SearchStation />
        <SourceCards />
        <RetryLoop />
        <ReportStation />
        <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mt-[18px] mb-2">执行时间轴 · 当日</div>
        <ExecutionTimeline />
      </div>
    </>
  );
}
function WorkbenchSummary() {
  // done 态收窄摘要条:N 步 · M 轮 · 自我纠错 K 次(详见 Epic 8 Task 27)
  return <div className="p-4 text-[12px] text-text-muted">查看工作 ↗</div>;
}
function statusLabel(s: string): string {
  return s === 'running' ? '调研进行中…' : s === 'idle' ? '待启动' : '本轮调研完成';
}
```

> 各子组件本 Task 先建空壳(`export function X(){ return null }`)让 build 过,Epic 5 逐个实现。或本 Task 只建 ResearcherWorkbench + WorkbenchSummary,子组件在各自 Task 建文件(则本 Task import 会缺文件 → build 失败)。**选后者更干净**:本 Task 不 import 未建组件,改为内联 TODO 注释占位,Epic 5 各 Task 建组件文件后回填 import。**写死:本 Task 只渲 eng-hd + roster 区(AgentRoster 在 Task 13 紧接建),其余面板 import 在对应 Task 加。** 为避免 build 失败,Task 12 先只 import 已存在的,或把 Epic 5 全部组件文件作为「空壳先建」放在 Task 12 Step 0。采用:**Task 12 Step 0 先 `touch` 建 6 个空壳组件**(每个 `export function X(){return null}`),Task 12 import 全部,后续 Task 逐个填实。

- [ ] **Step 0: 建 6 个空壳组件文件**

`AgentRoster.tsx` / `SearchStation.tsx` / `SourceCards.tsx` / `RetryLoop.tsx` / `ReportStation.tsx` / `ExecutionTimeline.tsx`,每个:

```tsx
export function AgentRoster() { return null; }   // 各文件改对应名
```

- [ ] **Step 1: 写 ResearcherWorkbench(如上)**
- [ ] **Step 2: 验证 build + browse**

Run: `cd frontend && pnpm build` → PASS。`/browse` 看右栏出现 eng-hd 标题 + 空 body(各面板待填)。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/
git commit -m "feat(planC): ResearcherWorkbench shell + empty panel stubs"
```

---

## Epic 5 — 研究员工作台各面板(消费 SSE 真实活儿)

> spec §6.4 目标①②④落地。各面板读 `runStore` Epic 1 切片。**selector 纪律**(记忆 confidence 10/10):selector 返 raw,render body 用 module-level 稳定常量窄化。验证每 Task = `pnpm build` + `/browse`(用 Epic 9 最小 fakeSSEPlayer 驱动数据,或真 run)。

### Task 13: AgentRoster 工牌(2×2)

**Files:**
- Modify: `frontend/src/components/workbench/AgentRoster.tsx`
- Create: `frontend/src/components/workbench/AgentBadge.tsx`

**背景**:2e §4 工牌:头像(身份色描边)+ 职能名 + 工号 + 状态灯(待命灰/执行身份色/完成绿)+ 当前任务 + retry 角标。状态机映射 `runStore.nodes[role]`(`idle|running|done|failed|retrying`)。**id 映射**:`runStore.nodes` key 是 `'collect'|'analyze'|'write'|'qc'`(NodeName),`AgentId` 是 `'collector'|'analyst'|'writer'|'qc'` —— 需 NodeName↔AgentId 映射(记忆 [[silent type-domain]]:跨 domain identifier 别假设同名)。建映射常量:

```typescript
const NODE_OF_ROLE: Record<AgentId, NodeName> = { collector: 'collect', analyst: 'analyze', writer: 'write', qc: 'qc' };  // codex P1#2:类型必须 NodeName(strict 索引);import type { NodeName } from '../../stores/runStore'(若未 export 则在 runStore 补 export)
```

- [ ] **Step 1: `AgentBadge.tsx`(单工牌,port 2e §4 markup)**

```tsx
import type { AgentId } from '../../types/agents';
import { ROLES } from '../../lib/agentRoles';
import { avatarSrc, onAvatarError } from '../../lib/avatar';
import { useRunStore } from '../../stores/runStore';
import { useDrawerStore } from '../../stores/drawerStore';   // Epic 6;若未建先留 onClick 占位

const NODE_OF_ROLE: Record<AgentId, NodeName> = { collector: 'collect', analyst: 'analyze', writer: 'write', qc: 'qc' };  // codex P1#2:类型必须 NodeName(strict 索引);import type { NodeName } from '../../stores/runStore'(若未 export 则在 runStore 补 export)

export function AgentBadge({ id, currentTask }: { id: AgentId; currentTask?: string }) {
  const r = ROLES[id];
  const nodeState = useRunStore((s) => s.nodes[NODE_OF_ROLE[id]]);   // 'idle'|'running'|'done'|'failed'|'retrying'
  const openAgent = useDrawerStore((s) => s.openAgent);
  const active = nodeState === 'running' || nodeState === 'retrying';
  const done = nodeState === 'done';
  const stateText = active ? '执行中' : done ? '已完成' : nodeState === 'failed' ? '失败' : '待命';
  const lampColor = done ? 'var(--v-sup)' : active ? r.col : 'var(--text-faint)';
  return (
    <button
      onClick={() => openAgent(id)}
      className="text-left border rounded-lg bg-surface p-[10px_11px_11px] relative overflow-hidden flex flex-col gap-2 transition-colors"
      style={{ borderColor: active || done ? r.col : 'var(--border)', ['--idc' as string]: r.col }}
      aria-label={`${r.name} 工牌`}
    >
      {nodeState === 'retrying' && (
        <span className="absolute top-2 right-[9px] font-mono text-[8.5px] font-semibold leading-none text-white rounded-[7px] px-[5px] py-[2px]" style={{ background: 'var(--accent)' }}>第2轮</span>
      )}
      <div className="flex items-center gap-[9px]">
        <div className="relative w-10 h-10 rounded-[9px] overflow-hidden border-[1.5px]" style={{ borderColor: r.line, background: r.soft }}>
          <img src={avatarSrc(id)} alt={`${r.name}头像`} loading="lazy" onError={onAvatarError} className="w-full h-full object-cover" />
          <span className="absolute -right-[3px] -bottom-[3px] w-[13px] h-[13px] rounded-full border-2 border-surface" style={{ background: lampColor }} />
        </div>
        <div>
          <div className="text-[12.5px] font-semibold text-text-primary leading-tight">{r.name}</div>
          <div className="font-mono text-[9.5px] text-text-muted tracking-[.3px] mt-px">{r.no}</div>
        </div>
      </div>
      <div className="text-[10.5px] leading-[1.3] min-h-[14px] overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: active ? r.col : 'var(--text-muted)' }}>{currentTask || r.fn}</div>
      <div className="font-mono text-[9px] tracking-[.3px]" style={{ color: done ? 'var(--v-sup)' : active ? r.col : 'var(--text-faint)' }}>{stateText}</div>
    </button>
  );
}
```

- [ ] **Step 2: `AgentRoster.tsx`(2×2 grid)**

```tsx
import { ROLE_ORDER } from '../../lib/agentRoles';
import { AgentBadge } from './AgentBadge';
import { useRunStore } from '../../stores/runStore';

export function AgentRoster() {
  const narrative = useRunStore((s) => s.perAgentNarrative);   // agent_id → 进度摘要[];取最后一条作当前任务
  return (
    <div className="grid grid-cols-2 gap-[9px] mb-1.5">
      {ROLE_ORDER.map((id) => {
        const lines = narrative[id];
        const task = lines && lines.length ? lines[lines.length - 1] : undefined;
        return <AgentBadge key={id} id={id} currentTask={task} />;
      })}
    </div>
  );
}
```

(`perAgentNarrative` key 是 agent_id `'collector'` 等 — 架构报告确认 progress 事件 agent_id 是这些。selector 返 raw。)

- [ ] **Step 3: build + browse**

Run: `cd frontend && pnpm build` → PASS。`/browse` 看 2×2 工牌、头像、工号、状态灯随 run 变色。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/AgentRoster.tsx frontend/src/components/workbench/AgentBadge.tsx
git commit -m "feat(planC): agent roster 工牌 (avatar/工号/状态灯/retry badge)"
```

### Task 14: SearchStation 检索台(查询词逐字 + 命中)

**Files:**
- Modify: `frontend/src/components/workbench/SearchStation.tsx`

**背景**:2e §6 检索台:query 行,字符级打字(14ms/char),`+N 源`/`无新增`。React 不照搬命令式 DOM 打字;用「按到达逐行渲染 + CSS 过渡 + 可选 typewriter hook」。数据来自 `runStore.queries`(prepend,最新在前)+ `queryHits`(query_text→hit_count)。`prefers-reduced-motion` 跳过打字。

- [ ] **Step 1: typewriter(轻量,可选)**

逐字效果用一个小 hook(对最新一条 query 生效即可,旧的直接全显):

```tsx
import { useEffect, useState } from 'react';
function useTypewriter(text: string, on: boolean, ms = 14): string {
  const [n, setN] = useState(on ? 0 : text.length);
  useEffect(() => {
    if (!on) { setN(text.length); return; }
    setN(0); let i = 0;
    const t = setInterval(() => { i++; setN(i); if (i >= text.length) clearInterval(t); }, ms);
    return () => clearInterval(t);
  }, [text, on, ms]);
  return text.slice(0, n);
}
```

- [ ] **Step 2: SearchStation 渲染**

```tsx
import { useRunStore } from '../../stores/runStore';
import type { SSEQueryData } from '../../types/api';
const EMPTY_Q: SSEQueryData[] = [];
const REDUCE = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export function SearchStation() {
  const queries = useRunStore((s) => s.queries);
  const hits = useRunStore((s) => s.queryHits);
  const list = queries.length ? queries : EMPTY_Q;
  if (!list.length) return null;   // 无查询不渲(空态在父级或 idle 时不显)
  return (
    <div className="mt-[18px]">
      <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mb-2 flex items-center gap-[7px] before:content-[''] before:w-[14px] before:h-px before:bg-accent">检索台</div>
      <div className="flex flex-col gap-1.5">
        {list.map((q, i) => <QueryLine key={`${q.round}-${q.query_text}-${i}`} q={q} hit={hits[q.query_text]} latest={i === 0} />)}
      </div>
    </div>
  );
}
function QueryLine({ q, hit, latest }: { q: SSEQueryData; hit: number | undefined; latest: boolean }) {
  const shown = useTypewriter(q.query_text, latest && !REDUCE);
  const hasHit = hit !== undefined;
  return (
    <div className="flex items-center gap-2 font-mono text-[11px] bg-surface border border-border rounded-md px-[9px] py-[6px] text-text-primary">
      <span className="text-accent flex-none">▸</span>
      <span className="flex-1 overflow-hidden whitespace-nowrap min-w-0">{shown}</span>
      {hasHit && <span className={`flex-none text-[9.5px] whitespace-nowrap ${hit! > 0 ? 'text-v-sup' : 'text-text-faint'}`}>{hit! > 0 ? `+${hit} 源` : '无新增'}</span>}
    </div>
  );
}
```

(checkmark SVG 可省;命中文案足够。失败维/无结果:`hit===0` → 「无新增」,非 raw exception,符合 spec §6.6。)

- [ ] **Step 3: build + browse** → 检索台显真实中英查询词逐字 + 命中。
- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/SearchStation.tsx
git commit -m "feat(planC): SearchStation 检索台 (typed real queries + hit counts)"
```

### Task 15: SourceCards 来源卡

**Files:**
- Modify: `frontend/src/components/workbench/SourceCards.tsx`

**背景**:2e §7 来源卡:标题/域名/类型/日期 + 三色 dot + 可点开原文。数据 `runStore.sources`(`SSESourceData`:source_title/source_url/fetched_at/competitor/dimension)。**source 事件不带可信 support_verdict**(C-D6;真三色在 qc 后)→ 来源卡的「支撑度」用 `runStore.cellVerdicts` 按 `${dimension}|${competitor}` 查(qc 后才有,前期显「待裁决」)。stale 由 `freshness.ts` 从 `fetched_at` 派生(>90 天)。域名从 `source_url` 提取。点击 → `openEvidence(evidence_id)`(Epic 6 抽屉;拉全文走 REST)。

- [ ] **Step 1: 域名提取 helper(就地)**

```tsx
function domainOf(url: string): string { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url.slice(0, 40); } }
```

- [ ] **Step 2: SourceCards 渲染**

```tsx
import { useRunStore } from '../../stores/runStore';
import { useDrawerStore } from '../../stores/drawerStore';
import { isStale } from '../../lib/freshness';
import { formatBeijingDate } from '../../lib/time';
import { VerdictDot } from '../cockpit/VerdictDot';
import type { SSESourceData, SupportVerdict } from '../../types/api';
const EMPTY_S: SSESourceData[] = [];

export function SourceCards() {
  const sources = useRunStore((s) => s.sources);
  const verdicts = useRunStore((s) => s.cellVerdicts);
  const droppedKeys = useRunStore((s) => s.droppedCells);   // codex P2#12
  const openEvidence = useDrawerStore((s) => s.openEvidence);
  const list = sources.length ? sources : EMPTY_S;
  if (!list.length) return null;
  return (
    <div className="mt-[18px] flex flex-col gap-[7px]">
      <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mb-1">命中来源 · {list.length}</div>
      {list.map((src) => {
        const key = `${src.dimension}|${src.competitor}`;
        const v = verdicts[key] as SupportVerdict | undefined;
        const dropped = droppedKeys.includes(key);   // codex P2#12:被剔除格的来源标「已剔除」而非永久「待裁决」
        const stale = isStale(src.fetched_at);
        return (
          <button key={src.evidence_id} onClick={() => openEvidence(src.evidence_id)}
            className="text-left bg-surface border border-border rounded-md px-[11px] py-[9px] hover:border-accent-line transition-colors">
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-semibold text-ink leading-[1.3] truncate">{src.source_title}</div>
                <div className="font-mono text-[10px] text-text-muted mt-px flex items-center gap-1.5 flex-wrap">
                  <span>{domainOf(src.source_url)}</span><span>·</span>
                  <span className={stale ? 'text-evidence-stale' : ''}>{formatBeijingDate(src.fetched_at)}{stale ? ' · 陈旧' : ''}</span>
                </div>
              </div>
              <div className="flex-none flex items-center gap-[5px] font-mono text-[9.5px] text-text-muted whitespace-nowrap">
                {v ? <VerdictDot verdict={v} showLabel /> : dropped ? <span className="text-v-uns">已剔除</span> : <span className="text-text-faint">待裁决</span>}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
```

(**codex P1#7 核验**:`VerdictDot` 现 prop 是 `showLabel` 不是 `withLabel`(`VerdictDot.tsx:10-16`),用 `showLabel`。dropped 处理见上 `dropped` 分支。)

- [ ] **Step 3: build + browse** → 来源卡真实标题/域名/日期 + stale 灰角标;qc 后出三色。
- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/SourceCards.tsx
git commit -m "feat(planC): SourceCards 来源卡 (real title/domain/date + stale + verdict)"
```

### Task 16: ExecutionTimeline 执行时间轴

**Files:**
- Modify: `frontend/src/components/workbench/ExecutionTimeline.tsx`

**背景**:2e §9:绝对 HH:MM + 角色 + 「→ 导致变化」。DESIGN.md:每节点必产左侧可见变化(防 agent theater)。数据从 `runStore.events`(node/progress)派生 —— 现有 `ExecutionStream` 已做类似派生(架构报告:deriveRows from events,retry arc)。本 Task 重写为「时间轴 + → 导致变化」形态,绝对时间用事件 `ts`(`formatBeijingTime`)。**复用现有 ExecutionStream 的 deriveRows 逻辑**(若可),只换渲染为 2e §9 timeline 样式 + 加 effect 行。

- [ ] **Step 1: 派生时间轴行**

从 `runStore.events`(过滤 node/progress)+ `nodeStartTs`/`nodeEndTs` 生成行:`{time, role, msg, effect, cls}`。effect(导致变化)从 node summary 推:collect → `+N 证据`、analyze → `矩阵 +M 维`、qc reject → `打回 · 第N轮`、qc pass → `裁决通过`。role 用 NodeName→ROLE 映射(同 Task 13 `NODE_OF_ROLE` 反查)。

```tsx
import { useRunStore } from '../../stores/runStore';
import { roleOf } from '../../lib/agentRoles';
import { formatBeijingTime } from '../../lib/time';
// 复用/参考现有 ExecutionStream 的派生;此处给最小派生骨架
```

(实现:把现有 `ExecutionStream.tsx` 的派生函数抽出复用,渲染层换 2e timeline 样式。若 ExecutionStream 派生耦合渲染难抽，直接在此重写派生 —— 数据源都是 `runStore.events`。)

- [ ] **Step 2: 渲染 2e §9 timeline 样式**

```tsx
export function ExecutionTimeline() {
  const rows = useTimelineRows();   // 上step 派生 hook
  if (!rows.length) return null;
  return (
    <div className="flex flex-col mt-1.5">
      {rows.map((r, i) => (
        <div key={i} className="flex gap-[10px] py-[7px]">
          <div className="flex-none w-[14px] flex flex-col items-center">
            <span className="w-[9px] h-[9px] rounded-full mt-[3px] flex-none z-[1]" style={{ background: r.cls === 'reject' ? 'var(--v-uns)' : r.cls === 'pass' ? 'var(--v-sup)' : (roleOf(r.role)?.col ?? 'var(--accent)') }} />
            {i < rows.length - 1 && <span className="flex-1 w-[1.5px] bg-border mt-0.5" />}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-muted">{r.time}</span>
              <span className="text-[11px] font-semibold" style={{ color: r.cls === 'reject' ? 'var(--v-uns)' : r.cls === 'pass' ? 'var(--v-sup)' : (roleOf(r.role)?.col ?? 'var(--text-primary)') }}>{roleOf(r.role)?.name ?? '系统'}</span>
            </div>
            <div className="text-[11.5px] text-text-primary leading-[1.45] mt-0.5">{r.msg}</div>
            {r.effect && <div className="text-[10.5px] font-mono mt-0.5 flex items-center gap-[5px]" style={{ color: r.cls === 'reject' ? 'var(--v-uns)' : 'var(--accent)' }}><span>→</span>{r.effect}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: build + browse** → 时间轴绝对时间 + 角色色 + → 导致变化;打回行红、通过行绿。
- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/ExecutionTimeline.tsx
git commit -m "feat(planC): ExecutionTimeline (absolute HH:MM + role + → effect)"
```

### Task 17: RetryLoop 重试环

**Files:**
- Modify: `frontend/src/components/workbench/RetryLoop.tsx`

**背景**:2e §10:青绿单回环(一次性 `loopspin` 1s,**非无限**),「第 N 轮 · 证据 X→Y」。数据 `runStore.evidenceDeltas`(round>0 的增量)+ `retryCount`。仅在有 retry 时显。`prefers-reduced-motion` 不转。

- [ ] **Step 1: 渲染(port 2e §10)**

```tsx
import { useRunStore } from '../../stores/runStore';
import { motion } from 'framer-motion';
import type { SSEEvidenceDeltaData } from '../../types/api';
const EMPTY_D: SSEEvidenceDeltaData[] = [];
const REDUCE = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export function RetryLoop() {
  const deltas = useRunStore((s) => s.evidenceDeltas);
  const list = deltas.length ? deltas : EMPTY_D;
  const retryRounds = list.filter((d) => d.round > 0);
  if (!retryRounds.length) return null;
  const last = retryRounds[retryRounds.length - 1];
  const before = last.total_count - last.added_count;
  return (
    <div className="border rounded-lg px-[14px] py-3 mt-2.5 relative overflow-hidden" style={{ borderColor: 'var(--accent-line)', background: 'var(--accent-soft)' }}>
      <div className="flex items-center gap-2 text-[12px] font-semibold" style={{ color: 'var(--accent-deep)' }}>
        <motion.span className="flex-none w-4 h-4 text-accent" animate={REDUCE ? {} : { rotate: 360 }} transition={{ duration: 1, ease: 'easeOut' }}>
          <svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 8a5 5 0 1 1 1.6 3.7" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round"/><path d="M3 4.5v3.5h3.5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </motion.span>
        自我纠错回环 · 第 {last.round + 1} 轮补证
      </div>
      <div className="text-[11.5px] text-text-primary leading-[1.5] mt-[5px]">系统不接受弱结论:一条回环从<b>质检员</b>绕回<b>采集员</b>定向补证,补全后自动复检。</div>
      <div className="inline-flex items-center gap-1.5 mt-[9px] font-mono text-[11px] font-semibold text-white px-[11px] py-1 rounded-[13px] shadow-panel" style={{ background: 'var(--accent)' }}>
        <span>↻</span><span>第 {last.round + 1} 轮 · 证据 {before}→{last.total_count}</span>
      </div>
    </div>
  );
}
```

> 动画一次性:framer-motion `animate={{rotate:360}}` + `transition duration:1` 默认不循环(无 `repeat`),符合 DESIGN.md「单次不无限抖动」。

- [ ] **Step 2: build + browse**(需 retry 数据;Epic 9 fakeSSEPlayer 含第2轮)→ 重试环单次转 + 真实 X→Y。
- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/RetryLoop.tsx
git commit -m "feat(planC): RetryLoop 重试环 (one-shot spin, real 证据 X→Y)"
```

### Task 18: ReportStation 报告台 typing

**Files:**
- Modify: `frontend/src/components/workbench/ReportStation.tsx`

**背景**:C-D7。`chunk` 已接 `typingStore.byAgent['writer']` + `runStore.writerReport`(架构报告)。报告台读 `typingStore.byAgent['writer']` 实时显;首块前 ~38s(后端 write_node 先发 `progress step="drafting"`)显「起草中…」占位(Spike H TTFB)。判定:writer node 正在 running 且 step==='drafting' 且 typing 文本为空 → 占位;有 typing → 显文本(+ 光标)。

- [ ] **Step 1: 渲染**

```tsx
import { useTypingStore } from '../../stores/typingStore';
import { useRunStore } from '../../stores/runStore';

export function ReportStation() {
  const text = useTypingStore((s) => s.byAgent['writer']) ?? '';
  const writerState = useRunStore((s) => s.nodes['write']);   // NodeName 'write'
  const drafting = writerState === 'running' || writerState === 'retrying';
  if (!drafting && !text) return null;
  return (
    <div className="mt-[18px]">
      <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mb-2 flex items-center gap-[7px] before:content-[''] before:w-[14px] before:h-px" style={{ ['--tw' as string]: 'var(--id-writer)' }}>报告台 · 撰写员起草</div>
      <div className="bg-surface border border-border rounded-md px-[11px] py-[9px] text-[12px] leading-[1.6] text-text-primary whitespace-pre-wrap min-h-[40px]">
        {text ? (
          <>{text}<span className="inline-block w-[2px] h-[14px] align-[-2px] ml-px animate-pulse" style={{ background: 'var(--id-writer)' }} /></>
        ) : (
          <span className="text-text-muted italic">起草中…(撰写员正在综合判断,约 30–40 秒首段成型)</span>
        )}
      </div>
    </div>
  );
}
```

> 占位文案诚实:typing 是 best-effort,首块前后端在思考(Spike H TTFB 38s),不假装卡死。回落一次性时(stream 失败)无 chunk → 文本空 + 完成后 writerState 转 done → 组件 `!drafting && !text` 隐藏(数据仍由左栏报告/insight 真展示)。

- [ ] **Step 2: build + browse** → writer 阶段显「起草中…」→ 逐字长出。
- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/ReportStation.tsx
git commit -m "feat(planC): ReportStation typing (chunk revival + 38s drafting placeholder)"
```

---

## Epic 6 — 抽屉导航栈 + agent 抽屉 + 技能 UI + 证据/步骤抽屉

> spec §6.2/§6.3/§6.x。2e navStack(研究计划→步骤→命中来源,返回退一层、✕全关)。a11y:`role="dialog" aria-modal` + 焦点 trap + Esc + 恢复触发焦点(DESIGN.md a11y)。验证 = `pnpm build` + `/browse` 抽屉开关/返回/全关 + 焦点。

### Task 19: `drawerStore`(navStack)+ `useFocusTrap`

**Files:**
- Create: `frontend/src/stores/drawerStore.ts`
- Create: `frontend/src/hooks/useFocusTrap.ts`

**背景**:port 2e §2 navStack 语义到 Zustand。view = `{type:'agent', role}` | `{type:'evidence', id}` | `{type:'step', id}`。`openX` 从顶层进=reset 栈到一层;栈已开时=push 一层。`goBack`=pop 一层,栈底则 fullClose。`fullClose`=清栈 + 恢复焦点。

- [ ] **Step 1: `drawerStore.ts`**

```typescript
import { create } from 'zustand';
import type { AgentId } from '../types/agents';

export type DrawerView =
  | { type: 'agent'; role: AgentId }
  | { type: 'evidence'; id: string }
  | { type: 'step'; id: string };

interface DrawerState {
  stack: DrawerView[];
  lastFocus: HTMLElement | null;
  top: () => DrawerView | null;
  hasBack: () => boolean;
  openAgent: (role: AgentId) => void;
  openEvidence: (id: string) => void;
  openStep: (id: string) => void;
  goBack: () => void;
  fullClose: () => void;
}

function rememberFocus(): HTMLElement | null {
  return (typeof document !== 'undefined' ? (document.activeElement as HTMLElement) : null);
}

export const useDrawerStore = create<DrawerState>((set, get) => ({
  stack: [],
  lastFocus: null,
  top: () => { const s = get().stack; return s.length ? s[s.length - 1] : null; },
  hasBack: () => get().stack.length > 1,
  openAgent: (role) => set((s) => (s.stack.length ? { stack: [...s.stack, { type: 'agent', role }] } : { stack: [{ type: 'agent', role }], lastFocus: rememberFocus() })),
  openEvidence: (id) => set((s) => (s.stack.length ? { stack: [...s.stack, { type: 'evidence', id }] } : { stack: [{ type: 'evidence', id }], lastFocus: rememberFocus() })),
  openStep: (id) => set((s) => (s.stack.length ? { stack: [...s.stack, { type: 'step', id }] } : { stack: [{ type: 'step', id }], lastFocus: rememberFocus() })),
  goBack: () => set((s) => {
    if (s.stack.length > 1) return { stack: s.stack.slice(0, -1) };
    if (s.lastFocus?.focus) s.lastFocus.focus();
    return { stack: [], lastFocus: null };
  }),
  fullClose: () => set((s) => { if (s.lastFocus?.focus) s.lastFocus.focus(); return { stack: [], lastFocus: null }; }),
}));
```

> 注意 selector 纪律:组件读 `useDrawerStore((s)=>s.stack)`(raw);`top()`/`hasBack()` 是函数,在组件里调一次(`const top = useDrawerStore((s)=>s.stack.at(-1) ?? null)` 也可,返回 raw view 引用稳定)。

- [ ] **Step 2: `useFocusTrap.ts`**

```typescript
import { useEffect, useRef } from 'react';
export function useFocusTrap(active: boolean, onEscape: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!active) return;
    const el = ref.current; if (!el) return;
    const focusables = () => Array.from(el.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])')).filter((n) => n.offsetParent !== null);
    const first = focusables()[0]; first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onEscape(); return; }
      if (e.key !== 'Tab') return;
      const f = focusables(); if (!f.length) return;
      const a = f[0], z = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [active, onEscape]);
  return ref;
}
```

- [ ] **Step 3: build** → PASS。
- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/drawerStore.ts frontend/src/hooks/useFocusTrap.ts
git commit -m "feat(planC): drawerStore navStack + useFocusTrap (a11y)"
```

### Task 20: 通用 `Drawer` 组件 + scrim + 路由顶层 view

**Files:**
- Create: `frontend/src/components/drawer/Drawer.tsx`
- Modify: `frontend/src/components/cockpit/CockpitLayout.tsx`(挂 `<Drawer/>` + scrim 一次)

**背景**:2e 双物理抽屉(agent / evidence-step)由单逻辑栈驱动。React 用**一个** `Drawer` 组件按栈顶 type 渲染内容(agent→AgentDrawer,evidence→EvidenceView,step→StepDrawer)。scrim 点击 = fullClose。

- [ ] **Step 1: `Drawer.tsx`**

```tsx
import { useDrawerStore } from '../../stores/drawerStore';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { AgentDrawer } from './AgentDrawer';
import { StepDrawer } from './StepDrawer';
import { EvidenceView } from '../cockpit/EvidenceSlideOver';   // Task 22 导出 EvidenceView

export function Drawer() {
  const stack = useDrawerStore((s) => s.stack);
  const goBack = useDrawerStore((s) => s.goBack);
  const fullClose = useDrawerStore((s) => s.fullClose);
  const open = stack.length > 0;
  const top = open ? stack[stack.length - 1] : null;
  const hasBack = stack.length > 1;
  const trapRef = useFocusTrap(open, fullClose);
  return (
    <>
      <div onClick={fullClose} aria-hidden="true"
        className={`fixed inset-0 z-[60] bg-black/30 transition-opacity ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`} />
      <div ref={trapRef} role="dialog" aria-modal="true" aria-hidden={!open}
        className={`fixed top-0 right-0 h-full w-[466px] max-w-[94vw] bg-surface border-l border-border shadow-panel z-[61] flex flex-col transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'}`}>
        {top?.type === 'agent' && <AgentDrawer role={top.role} hasBack={hasBack} onBack={goBack} onClose={fullClose} />}
        {top?.type === 'evidence' && <EvidenceView id={top.id} hasBack={hasBack} onBack={goBack} onClose={fullClose} />}
        {top?.type === 'step' && <StepDrawer id={top.id} hasBack={hasBack} onBack={goBack} onClose={fullClose} />}
      </div>
    </>
  );
}
```

- [ ] **Step 2: CockpitLayout 挂一次 `<Drawer/>`**(最外层 wrapper 末尾,StatusBar+grid 之后)。**codex P1#8**:旧 `EvidenceSlideOver` 单例挂在 **`DecisionSurface`**(`DecisionSurface.tsx:27,187`)**不是** CockpitLayout —— 从 DecisionSurface 移除其挂载,改由本统一 `<Drawer/>` 驱动。

- [ ] **Step 3: build**(AgentDrawer/StepDrawer/EvidenceView 未建会失败 → 本 Task 先建 AgentDrawer/StepDrawer 空壳,EvidenceView 在 Task 22 从 EvidenceSlideOver 导出;为 build 过,先在 Drawer.tsx 用内联占位三元,Task 21/22 回填)。**写死**:Task 20 建 `AgentDrawer`/`StepDrawer` 空壳(`export function AgentDrawer(_:any){return null}`),`EvidenceView` 先内联 `<div/>` 占位,Task 22 替换。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/drawer/Drawer.tsx frontend/src/components/cockpit/CockpitLayout.tsx
git commit -m "feat(planC): generic Drawer driven by navStack + scrim + focus trap"
```

### Task 21: `AgentDrawer` + 技能卡 + 技能市场

**Files:**
- Modify: `frontend/src/components/drawer/AgentDrawer.tsx`
- Create: `frontend/src/components/drawer/SkillCard.tsx`
- Create: `frontend/src/components/drawer/SkillMarket.tsx`

**背景**:2e §5 agent 抽屉:大头像 + 角色名 + 工号/职能 + 当前任务 + 技能管理(技能卡 toggle/delete + 市场 install)。技能卡只显 name + 核心标 + 一行 do + 版本 + 启停开关 + 删除(**无 why/boundary**,spec §6.3)。诚实标注「行为接入下一期」。

- [ ] **Step 1: `SkillCard.tsx`(port 2e §5)**

```tsx
import type { SkillDef } from '../../lib/skillCatalog';
export function SkillCard({ def, enabled, version, onToggle, onDelete }: {
  def: SkillDef; enabled: boolean; version: string; onToggle: () => void; onDelete: () => void;
}) {
  return (
    <div className={`border border-border rounded-lg bg-surface px-[15px] py-[13px] mb-2.5 transition-opacity ${enabled ? '' : 'opacity-[.66] bg-surface-subtle'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[13.5px] font-semibold text-ink flex items-center gap-2 leading-[1.3]">
            {def.name}
            {def.core && <span className="font-mono text-[9px] font-semibold tracking-[.3px] text-accent border border-accent-line rounded-[3px] px-[5px] py-px flex-none" title="该员工的核心方法论">核心</span>}
          </div>
          <div className="text-[12px] text-text-muted leading-[1.55] mt-[5px]">{def.do}</div>
          <div className="flex items-center gap-3 mt-[7px]">
            <span className="font-mono tabular-nums text-[10px] text-text-faint" title="技能版本 · 后续可迭代到 v2 并对比测效果">{version}</span>
            <span className={`flex items-center gap-1.5 text-[10px] ${enabled ? 'text-v-sup' : 'text-text-muted'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${enabled ? 'bg-v-sup' : 'bg-text-faint'}`} />{enabled ? '启用' : '停用'}
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2 flex-none">
          <button role="switch" aria-checked={enabled} aria-label={`${def.name} 启用开关`} onClick={onToggle}
            className={`relative w-9 h-5 rounded-full transition-colors ${enabled ? 'bg-v-sup' : 'bg-border-strong'}`}>
            <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? 'translate-x-4' : ''}`} />
          </button>
          <button aria-label={`删除技能 ${def.name}`} onClick={onDelete}
            className="font-mono text-[10.5px] text-text-muted border border-border rounded-md bg-surface px-[9px] py-1 hover:border-v-uns hover:text-v-uns">删除</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `SkillMarket.tsx`(可展开,port 2e §5)**

```tsx
import { useState } from 'react';
import type { AgentId } from '../../types/agents';
import { MARKET } from '../../lib/skillCatalog';
import { useSkillsStore } from '../../stores/skillsStore';
export function SkillMarket({ role }: { role: AgentId }) {
  const [open, setOpen] = useState(false);
  const installed = useSkillsStore((s) => s.installed[role]);
  const install = useSkillsStore((s) => s.install);
  return (
    <div className="mt-3">
      <button onClick={() => setOpen((v) => !v)} className="font-mono text-[11px] text-accent border border-accent-line rounded-md bg-accent-soft px-[11px] py-1.5">+ 安装技能</button>
      {open && (
        <div className="mt-2.5 border border-border rounded-lg bg-surface-subtle p-3">
          <div className="flex items-center justify-between mb-2"><span className="text-[11px] font-semibold text-text-primary">技能市场 · 可安装</span><button onClick={() => setOpen(false)} aria-label="收起市场" className="text-text-muted">✕</button></div>
          {MARKET[role].map((it) => {
            const has = installed.some((s) => s.id === it.id);
            return (
              <div key={it.id} className="flex items-start justify-between gap-2 py-2 border-t border-border first:border-t-0">
                <div className="min-w-0"><div className="text-[12.5px] font-semibold text-ink">{it.name} <span className="font-mono text-[9.5px] text-text-faint">v1</span></div><div className="text-[11.5px] text-text-muted leading-[1.5] mt-0.5">{it.do}</div></div>
                <button disabled={has} onClick={() => install(role, it.id)}
                  className={`flex-none font-mono text-[10.5px] rounded-md px-[9px] py-1 border ${has ? 'text-text-faint border-border' : 'text-accent border-accent-line hover:bg-accent-soft'}`}>{has ? '已安装' : '安装'}</button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: `AgentDrawer.tsx`(组装 + dr-hd back/close + 诚实标注)**

```tsx
import type { AgentId } from '../../types/agents';
import { ROLES } from '../../lib/agentRoles';
import { avatarSrc, onAvatarError } from '../../lib/avatar';
import { useSkillsStore } from '../../stores/skillsStore';
import { SkillCard } from './SkillCard';
import { SkillMarket } from './SkillMarket';

export function AgentDrawer({ role, hasBack, onBack, onClose }: { role: AgentId; hasBack: boolean; onBack: () => void; onClose: () => void }) {
  const r = ROLES[role];
  const installed = useSkillsStore((s) => s.installed[role]);
  const state = useSkillsStore((s) => s.state);
  const toggle = useSkillsStore((s) => s.toggle);
  const remove = useSkillsStore((s) => s.remove);
  const note = useSkillsStore((s) => s.behaviorNote);
  const onCount = installed.filter((s) => state[s.id]?.enabled).length;
  return (
    <>
      <div className="flex items-start gap-[13px] px-5 pt-[18px] pb-[15px] border-b border-border" style={{ ['--agc' as string]: r.col, ['--agc-line' as string]: r.line, ['--agc-soft' as string]: r.soft }}>
        <div className="w-[52px] h-[52px] rounded-[11px] overflow-hidden flex-none border-[1.5px]" style={{ borderColor: r.line, background: r.soft }}>
          <img src={avatarSrc(role)} alt="" onError={onAvatarError} className="w-full h-full object-cover" />
        </div>
        <div className="flex-1">
          <div className="text-[18px] font-bold text-ink" tabIndex={-1}>{r.name}</div>
          <div className="font-mono text-[11px] text-text-muted mt-[3px] flex gap-[7px] items-center"><span>{r.no}</span><span>·</span><span className="font-semibold" style={{ color: r.col }}>{r.fn}</span></div>
        </div>
        <div className="ml-auto flex-none flex items-center gap-[7px]">
          {hasBack && <button onClick={onBack} aria-label="返回上一层" className="h-8 rounded-md border border-border-strong bg-surface px-[11px] text-[12px] font-semibold font-mono text-text-primary hover:border-accent hover:text-accent">返回</button>}
          <button onClick={onClose} aria-label="关闭" className="w-8 h-8 rounded-md border border-border-strong bg-surface text-text-muted hover:border-v-uns hover:text-v-uns">✕</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-5 pt-[18px] pb-7">
        <div className="bg-surface-subtle border border-border rounded-lg px-[13px] py-[10px]">
          <div className="font-mono text-[10px] text-text-muted uppercase tracking-[.4px]">当前 / 最近任务</div>
          <div className="text-[13px] text-text-primary mt-1">{r.fn}</div>
        </div>
        <div className="flex items-center gap-2 mt-4 mb-2">
          <span className="text-[13px] font-semibold text-text-primary">技能管理</span>
          <span className="font-mono text-[10px] text-text-muted">{onCount} 启用 / {installed.length} 已装</span>
        </div>
        <div className="text-[11px] text-text-muted italic mb-3 border border-dashed border-border rounded-md px-2.5 py-1.5">{note}</div>
        <SkillMarket role={role} />
        <div className="mt-3">
          {installed.map((def) => (
            <SkillCard key={def.id} def={def} enabled={state[def.id]?.enabled ?? true} version={state[def.id]?.version ?? 'v1'}
              onToggle={() => toggle(role, def.id)} onDelete={() => remove(role, def.id)} />
          ))}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: 在 RunPage / App 挂载处确保 `skillsStore.load()` 被调一次**(mount effect)。最稳:在 `CockpitLayout` 或 `RunPage` 的 mount effect 调 `useSkillsStore.getState().load()`(只一次,`loaded` 守卫)。

- [ ] **Step 5: build + browse** → 点工牌开 agent 抽屉,技能卡 toggle/delete 生效且刷新后持久化(REST),市场可装,「行为接入下一期」标注可见。
- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/drawer/AgentDrawer.tsx frontend/src/components/drawer/SkillCard.tsx frontend/src/components/drawer/SkillMarket.tsx frontend/src/components/cockpit/CockpitLayout.tsx
git commit -m "feat(planC): AgentDrawer + skill cards + skill market (honest behavior-phase-2 note)"
```

### Task 22: 证据视图(收编 EvidenceSlideOver)+ `StepDrawer`

**Files:**
- Modify: `frontend/src/components/cockpit/EvidenceSlideOver.tsx`(导出 `EvidenceView`)
- Modify: `frontend/src/components/drawer/StepDrawer.tsx`
- Modify: `frontend/src/components/cockpit/EvidencePill.tsx`(caller → `drawerStore.openEvidence`)
- Modify: `frontend/src/components/cockpit/EvidenceTimeline.tsx`(**codex P1#8**:也调 `evidenceViewerStore`,`EvidenceTimeline.tsx:7,15,51`,必须迁移)
- Modify: `frontend/src/components/cockpit/DecisionSurface.tsx`(**codex P1#8**:单例挂载 + 调用 `DecisionSurface.tsx:27,187`,移除挂载 + 迁移调用)

**背景**:现 `EvidenceSlideOver` 由 `evidenceViewerStore.openId` 驱动单层。改为导出纯内容组件 `EvidenceView({id, hasBack, onBack, onClose})`(无自身定位,由 `Drawer` 包壳),拉全文走 `evidenceStore.getEvidence(id)`(REST 懒拉)。原文卡三态(quote 缺/source 不可达/stale)保留(spec §6.6)。`StepDrawer` 显计划步骤详情(查询词 + 命中来源,点来源 `openEvidence` → push 第3层)。

- [ ] **Step 1: `EvidenceView`(从 EvidenceSlideOver 抽内容)**

把现有 slide-over 的「内容渲染」抽成 `export function EvidenceView({id, hasBack, onBack, onClose})`,复用现有原文卡三态逻辑 + `evidenceStore`。dr-hd 用 back/close(同 AgentDrawer 头部模式)。旧 `EvidenceSlideOver` 的定位 wrapper 删(改由 `Drawer` 提供)。**codex P1#8 —— `evidenceViewerStore` 调用点全迁移到 `drawerStore.openEvidence`,grep `evidenceViewerStore` 两侧 caller**:确认共 3 处:`EvidencePill`(点击)、`EvidenceTimeline.tsx:7,15,51`、`DecisionSurface.tsx:27,187`(挂载也在此,移除)。漏迁 EvidenceTimeline/DecisionSurface = 旧单例与新 Drawer 双开冲突。

- [ ] **Step 2: `StepDrawer`(计划步骤详情,port 2e §2 renderStep)**

数据:plan step 由 `runStore` 派生(Task 26 PlanRail 定义 step 模型)。step 详情 = 该步查询词(从 `runStore.queries` 按 dimension 过滤)+ 命中来源(`runStore.sources` 按 dimension 过滤)+ 填了哪些格/裁决。

```tsx
import { useMemo } from 'react';
import { useRunStore } from '../../stores/runStore';
import { useDrawerStore } from '../../stores/drawerStore';
import { dimensionLabel } from '../../lib/dimensions';
export function StepDrawer({ id, hasBack, onBack, onClose }: { id: string; hasBack: boolean; onBack: () => void; onClose: () => void }) {
  // id = dimension key(PlanRail 用 dimension 作 step id)
  // codex P1#3:selector 内 .filter() 每次返**新数组**→ Zustand v5 死循环。必须 selector 返 raw,filter 在 render 用 useMemo。
  const allQueries = useRunStore((s) => s.queries);
  const allSources = useRunStore((s) => s.sources);
  const queries = useMemo(() => allQueries.filter((q) => q.dimension === id), [allQueries, id]);
  const sources = useMemo(() => allSources.filter((x) => x.dimension === id), [allSources, id]);
  const openEvidence = useDrawerStore((s) => s.openEvidence);
  return (
    <>
      <div className="flex items-start gap-[13px] px-5 pt-[18px] pb-[15px] border-b border-border">
        <div className="flex-1"><div className="font-mono text-[10px] text-text-muted uppercase">计划步骤 · 执行详情</div><div className="text-[16px] font-bold text-ink mt-0.5" tabIndex={-1}>{dimensionLabel(id)}</div></div>
        <div className="ml-auto flex items-center gap-[7px]">
          {hasBack && <button onClick={onBack} className="h-8 rounded-md border border-border-strong px-[11px] text-[12px] font-mono font-semibold">返回</button>}
          <button onClick={onClose} aria-label="关闭" className="w-8 h-8 rounded-md border border-border-strong text-text-muted">✕</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-[18px] flex flex-col gap-3">
        <div><div className="font-mono text-[11px] text-text-muted mb-1.5">查询词 · {queries.length} 条</div>{queries.map((q, i) => <div key={i} className="font-mono text-[11px] text-text-primary py-0.5">▸ {q.query_text}</div>)}</div>
        <div><div className="font-mono text-[11px] text-text-muted mb-1.5">命中来源 · {sources.length} 条</div>{sources.map((s) => (
          <div key={s.evidence_id} className="text-[12px] py-1">{s.source_title} <button onClick={() => openEvidence(s.evidence_id)} className="text-accent underline text-[11px]" role="button">查看</button></div>
        ))}</div>
      </div>
    </>
  );
}
```

- [ ] **Step 3: 在 `Drawer.tsx` 把 `EvidenceView` 真 import 替换占位**;build。
- [ ] **Step 4: build + browse** → 证据抽屉拉全文 + 三态;step 抽屉显查询/来源;点来源 push 到证据(第3层),返回退回步骤,✕ 全关。焦点 trap + Esc 有效。
- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/cockpit/EvidenceSlideOver.tsx frontend/src/components/drawer/StepDrawer.tsx frontend/src/components/drawer/Drawer.tsx frontend/src/components/cockpit/EvidencePill.tsx
git commit -m "feat(planC): EvidenceView (navStack) + StepDrawer (queries+sources, push to evidence)"
```

---

## Epic 7 — 矩阵真三色 + StatusBar 重定义 + 决策三色 + 计划 rail + 因果桥

> spec §5.5 消费 + §6.4。左决策面接真三色与逐维填。验证 = `pnpm build` + `/browse`。

### Task 23: CompetitorComparison —— cell 级真三色 + 逐维 cell_row 填 + verdict_recheck 刷 + 失败维

**Files:**
- Modify: `frontend/src/components/cockpit/CompetitorComparison.tsx`
- Modify: `frontend/src/components/cockpit/VerdictDot.tsx`(形状对齐 2e `.shp` ●◐○,沿用现有 `showLabel` prop —— codex P1#7)

**背景**:现 CompetitorComparison 读 `cockpitStore.analysis`(done 后 REST)。要让矩阵**逐维生长**:running 时读 `runStore.cellRows`(逐维 cell_row),done 时 `cockpitStore.analysis` 兜底。真三色:cell 级 `support_verdict`(REST analysis)+ `runStore.cellVerdicts`(verdict_recheck 实时刷,key `${dim}|${comp}`)。失败维(`cell_row.status==='failed'`)显「分析失败」。乱序安全(按 dimension 落位)。

- [ ] **Step 1: VerdictDot 统一(●◐○ + `showLabel`)**

确保 `VerdictDot({verdict, showLabel?})`(**codex P1#7**:现 prop 名是 `showLabel`,核验 `VerdictDot.tsx:10-16`)渲染:supported `●`(实心 v-sup)/ partial `◐`(半填 v-par)/ unsupported `○`(空心环 v-uns),色盲双编码(色+形状 + `aria-label`/`title`)。port 2e §7 `.shp` 形状。

- [ ] **Step 2: 矩阵数据源合并(running 逐维 / done REST)**

```tsx
import { useRunStore } from '../../stores/runStore';
import { useCockpitStore } from '../../stores/cockpitStore';
// 维度行 = 请求维度顺序(从 run detail dimensions);每维数据优先 runStore.cellRows[dim](逐维到达),done 后用 analysis.comparison
const cellRows = useRunStore((s) => s.cellRows);
const cellVerdicts = useRunStore((s) => s.cellVerdicts);
const analysis = useCockpitStore((s) => s.analysis);
// 每 cell 三色:优先 cellVerdicts[`${dim}|${comp}`](实时),回落 analysisCell.support_verdict
```

渲染:行=维度(请求顺序),列=竞品。每维:`cellRows[dim]` 有 → 用其 cells(逐维生长,`status==='failed'` 整行显「分析失败」灰、`status==='empty'` 显「未找到公开数据」斜体灰);否则 analysis 兜底;都无 → skeleton(running)/「—」(done 被策展剔除)。胜出格加粗(承 v4 win 逻辑保留)。**codex P2#12**:被剔除格(`runStore.droppedCells` 含 `${dim}|${comp}`)显「—」,qc 完成即生效(不必等 done);三色一律读 cell 级(`cellVerdicts[key]` 实时 → 回落 `analysisCell.support_verdict`),**不读 ref 级**。

- [ ] **Step 3: 因果桥 cross-highlight 数据契约**

DESIGN.md:点决策 → 决策 `evidence_refs` ∩ 单元格 evidence ids 求交 → 高亮行列。cell 的 evidence ids 来自 `cell.evidence_refs[].evidence_id`(REST analysis cell 或 cell_row cell)。本 Task 给每 `<td>` 标 `data-ev-ids`(该 cell 的 evidence_id 列表);高亮态 className `ring-2 ring-accent bg-accent-soft`,由 DecisionBoard 选中决策驱动(Task 25 触发,选中决策 id 存 `cockpitStore` 或本地 context)。本 Task 只暴露 cell 的 evidence ids + 接受一个 `highlightedCells: Set<string>`(`${dim}|${comp}`)prop/store 读。

- [ ] **Step 4: build + browse** → 矩阵逐维填(running);qc 后三色刷新(supported●/partial◐);失败维「分析失败」;剔除维「—」。
- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/cockpit/CompetitorComparison.tsx frontend/src/components/cockpit/VerdictDot.tsx
git commit -m "feat(planC): matrix incremental cell_row fill + real cell-level 3-color + verdict_recheck refresh + failed-dim"
```

### Task 24: StatusBar 三色重定义(充分/部分/已剔除 Z + 点开清单)

**Files:**
- Modify: `frontend/src/components/cockpit/StatusBar.tsx`
- Modify: `frontend/src/pages/RunPage.tsx`(**codex P1#9**:现三色聚合在 `RunPage.tsx:103-109` 用 `aggregateVerdicts` 算 **`EvidenceRef.support_verdict`**(ref 级、LLM 自报、不可信),非 cell 级真三色。必须改为读 cell 级真算来源,否则光改 StatusBar 仍显假聚合。)

**背景**:C-D5。三色改为 cell 级真算:充分 X(`runStore.verdictSummary.supported`,verdict_recheck 实时)· 部分 Y(partial)· **已剔除 Z**(`verdictSummary.dropped` / `GET /runs/:id/curation-drops` scope=cell 计数,红○)。**codex P1#9**:删除/旁路 `RunPage.tsx:103-109` 基于 `EvidenceRef.support_verdict` 的旧聚合(`aggregateVerdicts`),StatusBar 三色一律读 `verdictSummary`(running 实时)+ curation-drops(done 兜底)。点已剔除 → 显剔除清单(抽屉或弹层)。

- [ ] **Step 1: 拉 curation-drops + 渲三色簇**

```tsx
import { useEffect, useState } from 'react';
import { fetchCurationDrops } from '../../lib/api';
import { useRunStore } from '../../stores/runStore';
import type { CurationDrop } from '../../types/api';
// done 后拉 drops;runId + terminal 触发
const [drops, setDrops] = useState<CurationDrop[]>([]);
const summary = useRunStore((s) => s.verdictSummary);
const cellDrops = drops.filter((d) => d.scope === 'cell');
const droppedCount = summary?.dropped ?? cellDrops.length;
```

三色簇 markup(承 2e StatusBar verdict 簇,**去 proto-tag**,Task 29):

```tsx
<div className="flex items-center gap-3 font-mono text-[11px]">
  <span className="flex items-center gap-1"><VerdictDot verdict="supported" />充分 {summary?.supported ?? 0}</span>
  <span className="flex items-center gap-1"><VerdictDot verdict="partial" />部分 {summary?.partial ?? 0}</span>
  <button onClick={() => setShowDrops(true)} className="flex items-center gap-1 hover:underline" title="点击查看被策展剔除的格">
    <VerdictDot verdict="unsupported" />已剔除 {droppedCount}
  </button>
</div>
```

- [ ] **Step 2: 剔除清单弹层/抽屉**

点「已剔除」→ 小面板列 `cellDrops`(competitor · dimension)。可用现有 `ui/sheet` 或简单弹层(ESC 关、scrim)。文案诚实:「以下格因证据不足被策展剔除(矩阵显「—」)」。

- [ ] **Step 3: 用户价值计数口径保留**(结论 N 条 │ 关键风险 N 个 │ 已打回 N 次 │ 最新证据 日期)—— 现 StatusBar 已有(架构报告),不动那部分,只改 verdict 簇语义。

- [ ] **Step 4: build + browse** → 三色簇为真;点已剔除看清单;无 proto-tag。
- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/cockpit/StatusBar.tsx
git commit -m "feat(planC): StatusBar 三色 redefine (充分/部分/已剔除 Z from curation-drops) + drops list"
```

### Task 25: DecisionBoard —— 决策三色 + 因果桥触发

**Files:**
- Modify: `frontend/src/components/cockpit/DecisionBoard.tsx`

**背景**:现 DecisionBoard 从最弱证据 verdict 派生「哪里可能错」(架构报告)。现后端有真 `decision.support_verdict`(C-D6)→ 决策卡读它显三色。因果桥:点决策卡 → 算该决策 `evidence_refs[].evidence_id` ∩ 各 cell evidence ids → 高亮矩阵行列(Task 23 接 `highlightedCells`)。选中态存 `cockpitStore`(或新 `selectionStore`)让矩阵读。

- [ ] **Step 1: 决策卡读 `decision.support_verdict`** 显三色 dot(承依据行 verdict 视觉)。
- [ ] **Step 2: 因果桥**:点决策 → 收集其 evidence ids → 对 `analysis.comparison` 各 cell 求交 → 得高亮 cell set(`${dim}|${comp}`)→ 存共享 store(`cockpitStore.setHighlightedCells` 或本地 lifted state)→ 矩阵(Task 23)读并加 `xhi` 高亮 + scrollIntoView 第一个。再点同决策取消。
- [ ] **Step 3: build + browse** → 决策三色;点决策矩阵交叉高亮 + 滚动到位;再点取消。
- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cockpit/DecisionBoard.tsx frontend/src/stores/cockpitStore.ts
git commit -m "feat(planC): decision-level 3-color + 因果桥 cross-highlight (decision refs ∩ cell evidence ids)"
```

### Task 26: PlanRail 研究计划(左栏顶,SSE 驱动 doing→done/reopen)

**Files:**
- Create: `frontend/src/components/workbench/PlanRail.tsx`
- Modify: `frontend/src/components/cockpit/DecisionSurface.tsx`(顶部挂 PlanRail)

**背景**:C-D8。step = 请求维度(每维一步)+ collect/分析整体步。状态由 SSE 派生:某维 `cell_row` 到达 → 该维 done;`evidence_delta` round>0 触发某维 reopen→再 done(补证)。点 done/reopen 步 → `openStep(dimension)`(Task 22 StepDrawer)。

- [ ] **Step 1: 派生 plan steps**

step 模型:`{id: dimension, name: dimensionLabel(dim), state: 'todo'|'doing'|'done'|'reopen'}`。派生:
- 初始所有请求维度 = todo;collect 开始 → 相关 doing。
- `runStore.cellRows[dim]` 存在 → 该维 done。
- `runStore.evidenceDeltas` 有 round>0 命中该维(按本轮 new source 的 dimension)→ 该维短暂 reopen → 补证后 cell_row 重到 → done。

```tsx
import { useRunStore } from '../../stores/runStore';
import { dimensionLabel } from '../../lib/dimensions';
import { useDrawerStore } from '../../stores/drawerStore';
// dimensions 来自 run detail(请求维度);state 派生如上
```

- [ ] **Step 2: 渲染(port 2e §11 .plan rail,横向 scroller + ✓ 动画)**

doing=accent 边框/底;done=psub 绿 + 可点;reopen=红边/底。✓ 用 stroke-dashoffset 动画。点 done/reopen → openStep(dim)。

- [ ] **Step 3: 挂 DecisionSurface 顶部**(在对比矩阵之上,2e DOM 顺序)。
- [ ] **Step 4: build + browse** → 计划随 run doing→done;补证维 reopen→done;点步开 step 抽屉。
- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/PlanRail.tsx frontend/src/components/cockpit/DecisionSurface.tsx
git commit -m "feat(planC): PlanRail (SSE-driven doing→done/reopen, click → StepDrawer)"
```

---

## Epic 8 — 状态覆盖 + a11y + 反幻觉收口

> spec §6.6/§6.7 + DESIGN.md 状态覆盖矩阵。验证 = `pnpm build` + `/browse`(浅/深 + 各终态)。

### Task 27: 新组件状态覆盖(loading/empty/error/failed/cancelled/degraded/insufficient)

**Files:**
- Modify: 各 workbench 组件 + `ResearcherWorkbench`(WorkbenchSummary 实现)

**背景**:现有面板已全覆盖(spec §2.4),新组件(检索台/来源卡/逐格/技能卡/工牌/时间轴)需补齐(DESIGN.md 状态覆盖)。

- [ ] **Step 1: 各面板 idle/loading/empty**:idle 不渲(已 return null);running 无数据显进度提示(非通用 spinner,随计数跳)。
- [ ] **Step 2: failed/cancelled**:失败节点工牌状态灯红 + stateText「失败」(已 Task 13);检索台失败维「无新增」(已 Task 14);ExecutionTimeline 失败节点红 + 可读原因(非 raw exception,用 sanitized);cancelled 保留已完成、未跑工牌灰「已停止」+ 顶「已停止·N 秒前」。
- [ ] **Step 3: WorkbenchSummary(done 收窄摘要条)**:`N 步 · M 轮 · 自我纠错 K 次` + 「查看工作 ↗」展开回 full workbench(点展开切 collapsed=false 局部 override)。数据从 `runStore`(retryCount / cellRows 数 / evidenceDeltas)。
- [ ] **Step 4: build + browse**(切各终态:demo done / 真 run failed / cancel)→ 无空白、无 raw exception、文案诚实。
- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/
git commit -m "feat(planC): workbench state coverage (loading/failed/cancelled/done-summary)"
```

### Task 28: a11y 收口

**Files:**
- Modify: 抽屉 / 工牌 / 矩阵 / VerdictDot 等

**背景**:DESIGN.md a11y。焦点 trap 已 Task 19/20;补其余。

- [ ] **Step 1: 键盘焦点序**:证据 popover → 原文卡 → 矩阵 → 决策卡;抽屉 `role=dialog aria-modal` + Esc + 恢复触发焦点(已 Task 19/20,核验)。
- [ ] **Step 2: 色盲双编码**:VerdictDot 色+形状 ●◐○ + aria-label(已 Task 23,核验所有 verdict 用处)。
- [ ] **Step 3: 对比度 ≥4.5:1**(浅黄高亮上字、灰字)+ 触摸目标 44px(工牌/技能开关/按钮)+ ARIA landmarks(`<main>`/`<aside>` 已有,补 `<nav>` 给 PlanRail?用 `aria-label`)。
- [ ] **Step 4: `prefers-reduced-motion`**:打字/重试环/抽屉过渡在 reduce 时禁(检索台 REDUCE 已处理;RetryLoop REDUCE 已处理;全局 globals.css 加 reduce 规则兜底)。
- [ ] **Step 5: build + browse**(键盘 Tab 走查 + 深色对比)→ 焦点不逃逸抽屉、Esc 关、对比度达标。
- [ ] **Step 6: Commit**

```bash
git add frontend/src/ frontend/src/styles/globals.css
git commit -m "feat(planC): a11y pass (focus order, color-blind coding, contrast, 44px, reduced-motion)"
```

### Task 29: 反幻觉收口 —— 删 proto-tag,affordance 做真或撤

**Files:**
- Modify: StatusBar(已 Task 24 不含 proto-tag)+ 任何残留 proto 文案处

**背景**:spec §6.7。2e 有 4 处 proto-tag(2e §13);React 端**本就没搬** proto-tag(三色已真,Task 23/24)。本 Task 核验:全前端无「原型态 / 待后端实现」文案;任何仍未真的展示项必须显式标注或不展示。

- [ ] **Step 1: grep 残留**:`grep -rn "原型态\|待后端实现\|proto-tag" frontend/src` → 应为空(若有则删/改真)。
- [ ] **Step 2: 核验「展示后端没有的能力」**:确认无 provider/confidence/sentiment/趋势 任何展示(spec §1.5 永不做);技能子系统有「行为接入下一期」诚实标注(已 Task 21)。
- [ ] **Step 3: 「打开原始来源」做真**:EvidenceView 的「打开原始来源」按钮 → `window.open(source_url, '_blank')`(真开新标签),source 不可达时禁用标「来源链接不可用」(spec §6.6),不留 proto 文案。
- [ ] **Step 4: build + browse** → 无 proto-tag;打开来源真跳。
- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(planC): anti-hallucination cleanup — no proto-tags, source link is real"
```

---

## Epic 9 — 验证(最小 demo 驱动 + 全量 build + /browse + 后端回归)

> Plan C 仅做**最小** fakeSSEPlayer 扩充(够 /browse 各面板);Plan D 升级 demo 级 + replay 平价。

### Task 30: 最小 fakeSSEPlayer 新事件 + 全量验证

**Files:**
- Modify: `frontend/src/dev/fakeSSEPlayer.ts`

**背景**:现 `SAMPLE_EVENTS`(架构报告:25s collector→analyst→writer→qc→retry)只发旧事件。补发新事件(query/source/cell_row/evidence_delta/verdict_recheck)够驱动新面板。**Plan D 做完整平价 + demo URL 端到端 spike**(记忆 [[demo bullet-proof]]);本 Task 只求 /browse 能看到各新面板有数据。

- [ ] **Step 1: 在 SAMPLE_EVENTS 插新事件**(对齐叙事时序):collector 阶段插若干 `query`/`query_hit`/`source`;analyst 阶段插逐维 `cell_row`;retry 轮插 `evidence_delta`(round>0)+ 补 `source`;qc 后插 `verdict_recheck`(含 partial 一格、dropped 一格,体现真三色)。每事件形状严格对齐 Task 1 类型。
- [ ] **Step 2: build** → PASS。
- [ ] **Step 3: /browse 端到端走查**(demo 路径):工牌 2×2 状态机、检索台逐字、来源卡三色、矩阵逐维填 + verdict_recheck 刷三色、重试环单转、报告台 typing、计划 rail doing→done/reopen、agent 抽屉技能 toggle/装/删持久化、navStack 返回/全关、StatusBar 三色 + 已剔除清单、因果桥高亮。浅色 + 深色各一遍。**禁 `mcp__claude-in-chrome__*`,用 gstack `/browse`。**
- [ ] **Step 4: 后端全量回归**

Run: `.venv/bin/python -m pytest`
Expected: 383 + agent_skills 新增全绿。

- [ ] **Step 5: 前端全量 build**

Run: `cd frontend && pnpm build`
Expected: PASS(`tsc -b && vite build`)。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/dev/fakeSSEPlayer.ts
git commit -m "feat(planC): minimal fakeSSEPlayer new events for /browse verification (Plan D = full parity)"
```

---

## 自检(writing-plans Self-Review)

**1. Spec 覆盖(§6 全部 + §6.3/§7.3)**:
- §6.1 融合主轴 = Epic 4(Task 11/12)。§6.2 工牌/头像/抽屉 = Task 10/13 + Epic 6。§6.3 技能子系统 = Epic 2(后端)+ Task 8/21。§6.4 研究员工作台 6 面板 = Epic 5(Task 13–18)+ PlanRail Task 26。§6.5 store/SSE 接线 = Epic 1(Task 1–4)。§6.6 状态覆盖+a11y = Epic 8(Task 27/28)。§6.7 反幻觉收口 = Task 29。§6.x navStack = Task 19/20/22。§7.1 新事件镜像 = Task 1/2/3。§7.2 cell/decision support_verdict 前端字段 = Task 1。§7.3 agent_skills 持久化 = Epic 2。§5.5 三色消费 = Task 23/24/25。chunk 报告台 = Task 18。
- **gap 检查**:spec §6.4「逐格依据:点决策→矩阵交叉高亮」= 因果桥 Task 23/25 ✓。spec §6.4「执行时间轴 → 导致变化」= Task 16 ✓。**无未覆盖 spec 前端要求。**(§5 后端 / §8 DESIGN.md v5 已在 Plan A/B + DESIGN.md 完成;§9 demo 平价归 Plan D,本计划只最小驱动。)

**2. Placeholder 扫描**:各 Task 给了真实 code/markup(port 自 2e verbatim + 真实后端字段);无「TBD/handle edge cases/类似 Task N」。空壳组件(Task 12 Step 0 / Task 20 Step 3)是**有意的增量基座**(明确标注后续 Task 回填),非 placeholder 失败。

**3. 类型一致性**:
- `support_verdict` 字段名贯穿 cell/decision(Task 1)+ 读处(Task 15/23/25)一致。
- `cellVerdicts` key 统一 `${dimension}|${competitor}`(Task 3 写 / Task 15/23 读)。
- NodeName↔AgentId 映射 `NODE_OF_ROLE`(Task 13)+ ReportStation 用 `'write'`(Task 18)一致(NodeName 'write' 非 'writer')。
- `SkillDef`/`SkillState`/`skillState` 名贯穿 catalog(Task 8)+ store + 卡片(Task 21)。
- drawerStore `openAgent/openEvidence/openStep/goBack/fullClose` 名贯穿(Task 19 定义 / Task 13/15/20/22 调用)。
- `verdict_recheck` **无 decision_verdicts**(C-D6),决策三色读 REST `decision.support_verdict`(Task 25),不读事件 —— 一致,无悬空字段。

**codex 已裁决(见下「## Codex 裁决」节)**:11 条 findings(8 P1 全采纳 + 3 P2:2 采纳 1 确认)。剩余实现期 watch-items(非 bug,执行时留意):① 矩阵「running 逐维(cellRows)/ done(analysis REST)」双源切换时机。② skillsStore 空表 seed 的并发 PUT 与「全删→重 seed」边界。③ CockpitLayout done 收窄 280px 与 <1024 单栏的响应式交互。④ `perAgentNarrative`(agent_id)vs `nodes`(NodeName)两套 key —— 工牌当前任务用 agent_id、状态灯用 NodeName(`NODE_OF_ROLE` 映射,已 codex 核验语义正确)。

---

## Codex 裁决(2026-06-07,plan-phase outside-voice,逐条裁决)

> 跨模型 grep 核验(`codex consult --high`,真读前后端 30+ 文件)。净结论 codex **FAIL not implementation-ready** —— 8 P1 全是真错(代码 file:line 佐证),已全修;3 P2 中 2 采纳 1 确认本计划正确。记忆 [[outside-voice-adjudicate-not-wholesale]] 逐条裁决,记忆「plan 阶段必跑 outside voice」再次兑现(零代码时抓 8 个会真炸的 bug)。

| # | 级别 | finding(codex 佐证) | 裁决 | 落点(已修) |
|---|------|---------------------|------|------------|
| 1 | P1 | `runStore.handleEvent` 是 **if-chain 不是 switch**(`runStore.ts:180-198`);未识别事件落到读 `ev.data.node`(`:286-290`),新事件无 node → 出错 | 采纳(实质错误) | Task 3 Step 2:改 if-chain 早 return,放 handleEvent 顶部 |
| 2 | P1 | `NODE_OF_ROLE: Record<AgentId, string>` 使 `s.nodes[NODE_OF_ROLE[id]]` strict 索引报错(`runStore.ts:25-33,85-89`) | 采纳 | Task 13:类型改 `Record<AgentId, NodeName>` + import NodeName |
| 3 | P1 | `StepDrawer` selector 内 `.filter()` 每渲返新数组 → Zustand v5 死循环(违反自定纪律) | 采纳 | Task 22:selector 返 raw + useMemo filter |
| 4 | P1 | REST 路径双前缀:`jsonFetch` 已加 `/api`(`api.ts:22-25`)→ `/api/agent-skills` 变 `/api/api/...` | 采纳(全 404) | Task 4/8:路径去 `/api` |
| 5 | P1 | repository 调虚构 `_now_iso()`;真 helper 是 `_now()`(`repository.py:12-13`) | 采纳 | Task 6:改 `_now()` |
| 6 | P1 | route 用虚构 `get_conn`;真依赖 `get_db_conn`(`deps.py:16-23`,`reads.py:19-21`) | 采纳 | Task 7:import + `Depends(get_db_conn)` |
| 7 | P1 | `VerdictDot` prop 是 `showLabel` 不是 `withLabel`(`VerdictDot.tsx:10-16`) | 采纳 | Task 15/23:改 `showLabel` |
| 8 | P1 | 证据抽屉迁移不全:单例挂在 `DecisionSurface`(非 CockpitLayout),`EvidenceTimeline` 也调 `evidenceViewerStore`(`:7,15,51`) | 采纳 | Task 20/22:文件清单 + caller 补 EvidenceTimeline/DecisionSurface |
| 9 | P1 | StatusBar 真 cell 级聚合需改 `RunPage` —— 现聚合在 `RunPage.tsx:103-109` 基于 `EvidenceRef.support_verdict`(ref 级不可信) | 采纳 | Task 24:加 RunPage,删旧 `aggregateVerdicts`,读 `verdictSummary` |
| 10 | P2 | SSE TS 接口是**收窄镜像**非「exact」(后端 `str`/`list[dict]`/`dict[str,int]` → 前端 literal union/Record/可选键) | 采纳(措辞) | Task 1:收窄是有意安全;不称「逐字 exact」,称「镜像/收窄」 |
| 11 | P2 | `verdict_recheck` 确无 `decision_verdicts`(`schemas.py:213-221`/`nodes.py:354-361`)—— 本计划写法正确 | 确认(C-D6 对) | 无需改;决策三色读 `decision.support_verdict`(REST) |
| 12 | P2 | SourceCards 只用 `cellVerdicts` 无法标剔除格 —— `cell_verdicts` 只含**保留**格,dropped 另发(`nodes.py:345-360`),被剔格永久「待裁决」 | 采纳 | Task 3:加 `droppedCells` slice;Task 15/23:被剔格标「已剔除」/「—」 |

**另**:codex 确认后端路由**无 `/api` 前缀**(`app.py:78-84`,vite proxy 加)—— 印证 #4 修法方向。

---

## 执行须知
- **执行 sub-skill**:superpowers:subagent-driven-development(逐 Task 新 subagent + 两阶段审查;crux Task = 23/24/25 矩阵三色 + 21 技能 + 19/20 navStack 用独立 reviewer)。
- **环境**:WSL2 Clash —— 跑 pytest/前端 build 本地不需代理;**vendor 头像(Task 10)走海外代理保留**(DiceBear);真 run /browse 若打后端 LLM 需 unset 代理 + NO_PROXY。
- **前端验证**:`cd frontend && pnpm build`(`tsc -b && vite build`,记忆 [[verify-with-real-project-script]]),**不是** `tsc --noEmit`。`/browse` 用 gstack,**禁 `mcp__claude-in-chrome__*`**。
- **ship 前**:全量 pytest + 前端 build + /browse 浅深双色 + codex ship-time outside-voice。
- **反幻觉永不做**(spec §1.5):provider/confidence 复活、sentiment、多源交叉验证、监控趋势。技能装删本期不改 agent 行为(诚实标注)。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Codex Review | `/codex consult` | 独立跨模型 plan 核验 | 1 | issues_found → all fixed | 11 findings(8 P1 + 3 P2);8 P1 全采纳已修,2 P2 采纳已修,1 P2 确认 |

- **CODEX:** plan-phase outside-voice 真 grep 30+ 前后端文件,初判 FAIL(not implementation-ready)→ 逐条裁决全修(handleEvent if-chain / NODE_OF_ROLE 类型 / StepDrawer selector loop / `/api` 双前缀 / `_now()` / `get_db_conn` / `showLabel` / 证据抽屉迁移面 / RunPage 旧聚合 / droppedCells)。详见「## Codex 裁决」节。
- **UNRESOLVED:** 0(8 P1 全修;3 watch-items 是实现期留意项非 bug,见自检节)。
- **VERDICT:** Codex CLEARED(修后)—— 计划 implementation-ready,可交 subagent-driven-development 执行。
