# Lane F Frontend Plan v3 — 虚拟办公室 + 拟物动物 Multi-Agent Team

**版本**: v3.2(v3 + eng review 5 + Codex 4 + design review 3 = 12 修订)
**日期**: 2026-05-27
**触发**: Task 6.5 spike 真后端实测 user 反馈 4 个产品层根本盲点 → plan v2 的"DAG 节点变颜色"被证实是工程师视角,用户视角看到的是"4 个抽象圆圈,不知道 AI 在干啥"
**Branch**: feat/frontend (HEAD `84efa82`,Task 1-6 已 commit,部分将复用)
**Demo deadline**: **2026-06-02 周二**(剩余 6 天,D1=05-28 周四 至 D6=06-02 周二)

---

## v3.2 修订摘要(plan-eng-review + Codex + plan-design-review 共 12 处)

**eng-review 5 处(D7-D11)**:
1. **§3 typingStore throttle + window 50 + 16ms batch**(避免 chunk event 爆炸 → 内存/re-render 灾难)
2. **§5 sse.py try/finally + listener detect + drain on exit**(SSE queue race/leak 修)
3. **§9 Epic 7.5b core path 最小 unit test ~10 测**(backend SSE emit/cancel/agent 改造保 regression)
4. **§9 Epic 4.7 Lottie dynamic-import + bundle 验证**(避免 Day-6 bundle 超 250KB 紧急修)

**Codex outside voice 4 处(D13-D14)**:
5. **§4 + §6 删 backend AgentSpec.workspace_seat / GET /agents**:**reverse D9**,改 frontend Layout 直接 hardcode 4 agent constants(P0-2 单场景 demo 优先,extension 推到 demo 后,省 30-45 min)
6. **§10 日历重算**:D1=2026-05-28 周四 / D2=05-29 周五 / D3=05-30 周六 / D4=05-31 周日 / D5=06-01 周一 / **D6=06-02 周二 demo**(plan v3 原写 06-02 周三是错的)
7. **§9 Epic 3.0 fake SSE event player**(office UI 用 recorded stream 验证视觉,backend Epic 2 出问题不连带 office 崩)
8. **§7 SVG sprite + CSS state 优先,Lottie 只在 cohesive set 找到后才用**(P0-1 拟物动物质量风险 — Lottie 找不到 cohesive 4 动物时 fallback 不崩)
9. **§5 cancel asyncio.Task handle per run + task.cancel()**(原 sqlite flag 只在 step 间生效,停不掉 in-flight Doubao stream → demo 看起来 cancel 坏;Epic 0.4 cost 1h → 1.5h)

**plan-design-review 3 处(D16-D18)**:
10. **DESIGN.md 更新接纳 v3 paradigm**(D16):原 DESIGN.md "研报/intelligence desk 沉稳"vs plan v3"虚拟办公室+拟物动物"paradigm conflict。**保 user vision**,改 DESIGN.md 加"office paradigm + agent character"章节 + Decisions Log,保 90% 不冲突 tokens(IBM Plex 字体 / 24 CSS vars / Signature Patterns)— Epic 0.0 加,~30-45 min
11. **5 个 user-visible UI state 详细 spec**(D17):loading(创建 run 中)/ empty(第一次打开虚拟办公室)/ error(SSE 断/LLM 5xx)/ cancelled(stop 后)/ partial(部分 agent done)— Epic 0.0 加 + §3 加表,~45 min plan + 30 min 实装
12. **a11y keyboard nav + ARIA landmarks baseline**(D18):keyboard Tab/Enter/Escape 路径 + ARIA role/aria-label + contrast 4.5:1。Mobile 仅需 Layout fallback 不坍。~30 min plan + 30 min 实装

**净 cost 变化**:+30 min(Epic 3.0)+ 30 min(Epic 4.7)+ 2-3h(Epic 7.5b 测) + 30 min(Epic 0.4 cancel 重写) + 45 min(Epic 0.0a DESIGN.md update) + 75 min(Epic 0.0b 5 UI state spec + 实装) + 60 min(Epic 0.0c a11y baseline) = ~5.5-6h
**净 cost 抵消**:-45 min(D9 reverse 删 backend AgentSpec)= 实际净增 ~5h
**6 天 buffer 影响**:Epic 7 audit/lighthouse 必须压缩;Day-5 上午 check-in 关键;Epic 0 cost 从 4h → 6.5h(加 design 3 项),Day-1 上午 + 下午都被 Epic 0 + Epic 1 + DESIGN.md 占满

**Polish 决策 defer**(D19):动物种类 final / agent 名字 / typing 速度 / 移交动画样式 / ReportSheet 默认 / DAG tab vs modal 6 项 polish 决策 defer 到 Day-3 实装时 user 看 mockup 决(plan v3 §"P1 决策 TODO"原表保留)

---

## Vision Pivot 背景

### Spike 真正的 deliverable(2026-05-27 真打 LLM 实测)

plan v2 设计 35% money shot = "实时 DAG 4 节点 + retry 弧",代码层 Task 1-6 完工 (commit `84efa82`),mechanical checklist 8/11 pass。**但 user 真后端浏览器实测发现 4 个根本设计盲点**:

| # | user 反馈 | 根因 | plan v2 缺陷 |
|---|---|---|---|
| 1 | 看不到实时工作 + 时长 + 中间产物 + 操作过程 | backend SSE node event 只有 count,frontend DAG 只显示节点状态 + 颜色 | **35% money shot 设计错位** — 评委 5 秒看到"4 个抽象圆圈",看不出 AI 在干啥 |
| 2 | 维度 checkbox 英文 + EN 按钮无效 | 后端 `CONTROLLED_DIMENSIONS` 是英文 key,frontend 没 label 映射 | i18n 排到 Task 12 太晚 |
| 3 | running 中无法取消 | backend 无 cancel API,frontend Pause/Reset disabled | plan v2 完全没 cancel |
| 4 | 实时观感差 → 参考腾讯马维斯式角色化设计 | 整个 UI paradigm = 工程师视角的"流程图",非用户视角的"我请了员工" | **plan v2 paradigm 错** |

### Spike 学习(写入 memory)

- **"代码层通 ≠ 产品层对"** — DAG 4 节点状态切换 + 边变色 = 工程师视角端到端 ≠ 用户视角"看得见的 AI 工作"
- **"plan 当目标用不当圣经用"** 反面案例:plan v2 自评 35% money shot ✓,真实产品体验 5 分
- **outside voice 必跑** 二次验证:user 手测 5 min 抓的盲点 > 我跑 80% mechanical checklist 找到的(SVG warning + RunSummary stale)

### Design 调研综合(详 Phase 0 报告)

调研 6 产品(腾讯马维斯 / 阿里悟空 / AgentOffice / Stanford Smallville / Microsoft AutoGen Studio / 字节 Coze)提炼共识:

| Paradigm | 共识 | 适用 RivalRadar |
|---|---|---|
| **agent = 有 persona 的可爱角色**(马维斯小马驹 + 悟空龙虾)| 中国 AI 产品圈已是设计语言共识 | ✅ user 直接点名要 |
| **虚拟办公室 + 工位 + 多状态动画**(AgentOffice / 马维斯)| 像素艺术或 Lottie 卡通,游戏感 | ✅ 高 ROI 视觉差异化 |
| **中间产物 surface**(thought bubble + speech bubble + typing 效果)| AutoGen Studio "inner monologue" 工程师调试用 | ✅ 用户视角改写为"我在思考...我找到了...我正在写..." |
| **agent 抽象解耦**(name/role/avatar/persona/capabilities)| 国内外通用框架 (Coze/CrewAI/AutoGen) | ✅ user 提的"全能 team 扩展性" |

### RivalRadar 差异化定位

| 已有产品 | 定位 | RivalRadar 卡位 |
|---|---|---|
| 马维斯 | OS 级 AI 助手(野心大) | C 端 + **任务专用做透** |
| 悟空 | 企业级 + 钉钉绑定 | **独立 web app,不绑生态** |
| AgentOffice | 开源 demo(无真业务) | **真业务 + 角色化 UI** |
| AutoGen Studio | 工程师 debug 工具 | **用户视角"我请了一队员工"叙事** |

→ **RivalRadar v3 卡位** = "**任务专用 multi-agent 团队的角色化呈现**" — 单场景做透,可视化领先,架构预留扩展。

---

## User Vision 决策摘要(P0 锁定)

| # | 决策 | 选项 | 实施意义 |
|---|---|---|---|
| **P0-1** | **角色形象** | **拟物动物 + 真实可爱 + 展示效果非常重要** | Lottie character body + 自定义动物头像 overlay,2-3 天 polish。**4 种动物**(plan v3 §3 定) |
| **P0-2** | **场景边界** | **只竞品调研单场景** | scope 不分散,架构留扩展 hook 但 UI 只 1 场景 |
| **P0-3** | **DAG vs 办公室** | **方案 B:虚拟办公室主视图 + DAG 次切换** | 默认虚拟办公室,办公室界面右上角 DAG mini-preview + 点击切换 fullscreen DAG 详情 |
| **P0-4** | **中间产物 surface** | **方案 C:完整 streaming** | LLM 字符流 + 实时 typing 效果 + thought stream + evidence stream。混合 strategy:reasoning stream / 结构化 tools function-calling |

---

## 设计哲学 — RivalRadar v3 核心 paradigm

### 三层叙事(用户视角)

```
我请了一队员工(virtual office)
  ↓
他们正在我面前工作(typing/thinking/searching/writing/checking — 看得见)
  ↓
他们交付了完整的竞品报告(structured output — 用得上)
```

### 设计 principle

1. **角色优先**:每个 agent 是一只动物 + 有名字 + 有 persona + 有专长 — 不是抽象节点
2. **过程可见**:thinking / searching / writing / checking 都 stream 出来 — 不只 final output
3. **空间叙事**:虚拟办公室空间布局 + 工位 + agent 之间的物理移动 — 不是流程图
4. **工程兜底**:DAG 视图保留(切换可见)+ ObservabilityPanel — 评委需要看工程深度
5. **可扩展架构**:agent / team 抽象解耦 — 未来场景模板 plug-in 不动核心

### 4 个 agent 角色设定(plan v3 §3 详细 spec)

| Agent | 动物 | 名字 | persona | 工位 |
|---|---|---|---|---|
| 收集员 | 🦉 猫头鹰 | "夜枭" | 视野广 + 24h 不睡 + 全网搜索 | 左下,工位有显示器 + 文件堆 |
| 分析员 | 🦊 狐狸 | "灵犀" | 聪明 + 擅长抽取 + 看穿本质 | 左上,工位有放大镜 + 笔记本 |
| 撰稿员 | 🦝 浣熊 | "灵巧" | 灵巧 + 整理表达 + 文笔老练 | 右上,工位有打字机 + 纸笔 |
| 质检员 | 🐢 乌龟 | "镜湖" | 稳健 + 细致 + 慢工出细活 | 右下,工位有审查桌 + 印章 |

(注:动物 + 名字 + persona 是 P1 决策,plan v3 propose,user review 时定)

### 5 User-Visible UI State Spec(D17,Epic 0.0b)

5 状态覆盖 RunPage 全 lifecycle,UI 决不留空。

| State | Trigger | 4 Agent 状态 | 中央区域 | 主操作 | DESIGN.md 元素 |
|---|---|---|---|---|---|
| **loading** | POST /run 后等待 SSE start event | 4 agent 都 idle 坐工位 | 顶部 16px progress bar "正在创建调研..." | 灰 disabled CancelButton | `--accent` progress + IBM Plex Sans 13px |
| **empty** | 第一次打开 /run/:id 无 SSE / 直链 invalid id | 4 agent 都 idle 坐工位 | 中央占位 "等待你提交调研" + "回到调研列表" link | `→ /runs` button | `--text-muted` 15px + accent CTA |
| **error** | SSE error event(LLM 5xx / Tavily down / Doubao timeout) | 全 agent warning state(`--seat-N` opacity → `--warning`) | 红 banner "agent 网络异常 · [retry]" + 出错 agent SpeechBubble 显示具体错误 | "重试" button | `--error` banner + `--warning` agent overlay |
| **cancelled** | POST /run/:id/cancel + SSE 收到 cancelled event | 全 agent 立刻停动作(切 idle,无 typing) | 中央 "已停止 · 已收集 N 条证据" + 引导"新调研" / "查看部分结果" | 2 button | `--text-muted` 15px + accent CTA |
| **partial** | 部分 agent done 部分 running(正常进行中) | done agent 切 idle 但保留最后 SpeechBubble narrative;running agent 保 working 动画 | LiveFeedPanel 继续 scroll | running CancelButton + done agent 头像 ✓ chip | done overlay ✓ `--success` chip + running `--seat-N` highlight |

**实装范围(Epic 4.x)**:VirtualOfficeView + AgentTeamRoster 共用 `UIState` enum (`'loading' | 'empty' | 'error' | 'cancelled' | 'partial'`)+ runStore selector `deriveUIState(store)` + 每 state 一段 JSX branch。约 30 min 实装。

### Accessibility Baseline(D18,Epic 0.0c)

不做完整 mobile 支持(D18 决策 B),只保 keyboard + ARIA + 对比度 baseline。

| Domain | 要求 | 实施 | 验证 |
|---|---|---|---|
| **Tab 顺序** | CancelButton → AgentCharacter ×4(z-order 左下/左上/右上/右下)→ ReportSheet toggle → DAG tab → AgentTeamRoster ×4 → footer | `tabIndex={0}` 显式标 + `:focus-visible` accent ring 2px | 手测 Tab 顺序 + visual ring 清晰 |
| **Enter** | AgentCharacter Enter → 展开 SpeechBubble 完整 narrative drawer;ReportSheet Enter = 切 expand/collapse;CancelButton Enter = cancel API | `onKeyDown={(e) => e.key === 'Enter' && handler()}` 各 component | 键盘 Enter = 鼠标 click 等效 |
| **Escape** | running 中 Escape = CancelButton.click()(快捷停止);ReportSheet expanded 时 Escape = collapse | RunPage 顶层 useEffect `window.addEventListener('keydown', handleEsc)` | 键盘 Escape 行为符合用户心智 |
| **ARIA landmarks** | `<header>` / `<nav role="navigation">` AgentTeamRoster / `<main role="main">` Office / `<aside role="complementary">` LiveFeedPanel / `<footer>` | Layout.tsx 顶层 5 landmark + RunPage 子组件继承 | screen reader rotor 列出 5 个 landmark |
| **ARIA labels** | AgentCharacter `aria-label="${name} ${role} · ${state}"`;CancelButton `aria-label="停止当前调研"`;ReportSheet `aria-expanded={open}` | 各 component prop | screen reader 念出语义化标签 |
| **对比度** | text-primary on bg ≥ 7:1(AAA);text-muted on bg ≥ 4.5:1(AA);accent UI 元素 on surface ≥ 3:1(AA) | DESIGN.md 24 vars 已满足;office tokens(`--seat-N` on `--office-bg`)需重测 | Chrome DevTools 取色 + WCAG calculator |
| **Mobile fallback** | Layout.tsx ≤ 768px 不坍(三栏改单栏 stack,Office 居中 fit viewport,LiveFeed/AgentTeam collapsible)| Tailwind `md:grid-cols-3 grid-cols-1` + `md:flex flex-col` | DevTools 切 iPhone 14 viewport 不出现横滚 |

**实装范围**:Epic 1.x Layout.tsx ARIA 改造(15 min)+ Epic 3.x AgentCharacter / SpeechBubble / CancelButton 加 ARIA props(15 min)+ Day-5 上午 a11y manual smoke test(已计入 Day-5 check-in)。约 30 min 实装。

---

## Agent 抽象层 Design

### Backend: `AgentSpec`(新 schema)

```python
# rivalradar/agents/spec.py (新文件)
class AgentSpec(BaseModel):
    """Agent 抽象描述符 — 解耦节点 hardcode,支持未来场景模板。"""
    id: str                              # "collector" / "analyst" / "writer" / "qc"
    name: str                            # "夜枭" / "灵犀" / "灵巧" / "镜湖"
    role: str                            # "收集员" / "分析员" / "撰稿员" / "质检员"
    avatar: str                          # "/agents/owl.lottie" or "/agents/owl.png"
    persona: str                         # 一句话人设
    capabilities: list[str]              # ["web_search", "extract_evidence"]
    workspace_seat: tuple[int, int]      # (x, y) 在 office 中坐标
```

### Backend: `GET /agents`(新 endpoint)

返回当前场景的 agent 团队配置:

```python
@app.get("/agents")
def list_agents(scenario: str = "competitor_radar") -> list[AgentSpec]:
    """场景 → 团队配置 mapping,frontend 自适应渲染团队。"""
    return AGENT_TEAMS[scenario]
```

### Frontend: `AgentDescriptor` + `AgentTeam`

```typescript
// frontend/src/types/agents.ts(新文件)
export interface AgentDescriptor {
  id: string
  name: string
  role: string
  avatar: string
  persona: string
  capabilities: string[]
  workspace_seat: [number, number]
}

export interface AgentTeam {
  scenario: string
  agents: AgentDescriptor[]
}
```

### Frontend: `agentConstants.ts`(D13 reverse + F5 — hardcode 替代 store)

D13 reverse 后,前端不再 fetch /agents,而是直接 hardcode 4 agent 在常量文件:

```typescript
// frontend/src/lib/agentConstants.ts(新文件)
import type { AgentDescriptor } from '@/types/agents'

export const AGENTS: readonly AgentDescriptor[] = [
  { id: 'collector', name: '夜枭', role: '收集员', avatar: '/agents/owl', persona: '视野广 · 24h 不睡', capabilities: ['web_search'] },
  { id: 'analyst',   name: '灵犀', role: '分析员', avatar: '/agents/fox', persona: '聪明 · 看穿本质', capabilities: ['extract_features', 'extract_pricing'] },
  { id: 'writer',    name: '灵巧', role: '撰稿员', avatar: '/agents/raccoon', persona: '灵巧 · 文笔老练', capabilities: ['narrative_write'] },
  { id: 'qc',        name: '镜湖', role: '质检员', avatar: '/agents/turtle', persona: '稳健 · 慢工出细活', capabilities: ['entailment_check'] },
] as const

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a]))
```

### Store: `typingStore`(D7 修订:throttle + window buffer)

```typescript
// frontend/src/stores/typingStore.ts(新文件 + D7 修订)
// Per-agent typing buffer with throttle window 50 chunks + 16ms batch setState
// Avoids zustand store balloon + React re-render storm from LLM stream chunks.
interface TypingStore {
  byAgent: Record<string, string>  // agent_id → current typing string (last 50 chunks merged)
  appendChunk: (agent_id: string, delta: string) => void
  clear: (agent_id: string) => void
}

const WINDOW = 50           // 每 agent 最多保最近 50 chunks
const BATCH_MS = 16         // 16ms ~ 60fps batch setState

const pending: Record<string, string[]> = {}  // 批量累积区
let flushTimer: ReturnType<typeof setTimeout> | null = null

export const useTypingStore = create<TypingStore>((set, get) => ({
  byAgent: {},
  appendChunk: (agent_id, delta) => {
    // 1. 累积到 pending(同步,不触发 setState)
    if (!pending[agent_id]) pending[agent_id] = []
    pending[agent_id].push(delta)
    if (pending[agent_id].length > WINDOW) pending[agent_id].shift()  // 截 window
    // 2. 防抖 batch flush(每 16ms 最多 1 次 setState)
    if (flushTimer) return
    flushTimer = setTimeout(() => {
      const updates: Record<string, string> = {}
      for (const [aid, chunks] of Object.entries(pending)) {
        updates[aid] = (get().byAgent[aid] || '') + chunks.join('')
      }
      // window 截:仅保最后 N 字符防止单 agent 长 narrative balloon
      for (const aid in updates) updates[aid] = updates[aid].slice(-3000)
      set({ byAgent: { ...get().byAgent, ...updates } })
      for (const aid in pending) pending[aid] = []
      flushTimer = null
    }, BATCH_MS)
  },
  clear: (agent_id) => set({ byAgent: { ...get().byAgent, [agent_id]: '' } }),
}))
```

**内存上限**:4 agent × 3000 char string + 4 × 50 chunk pending ~ 12 KB。完全可控。
**re-render 速率**:最多 60fps,不会快闪。

---

## 后端改造 — SSE event v2 + 混合 LLM streaming

### SSE event 增量(plan v2 4 类 → v3 6 类)

| Event | plan v2 | plan v3 | 用途 |
|---|---|---|---|
| `start` | ✓ | ✓ | run 启动,带 run_id + agent team |
| `node` | ✓ | ✓(payload 富化) | 节点完成 + summary(`evidence_titles[]`/`preview`/`elapsed_ms`)|
| `error` | ✓ | ✓ | run 失败 |
| `done` | ✓ | ✓ | run 完成 + final verdict |
| **`progress`** | ❌ | ✅ 新增 | 节点内 step-level 进度("正在搜索 Notion pricing..."/"已抽取 3/7 feature") |
| **`chunk`** | ❌ | ✅ 新增 | LLM 字符 stream(reasoning step typing 效果) |

### `progress` event schema

```python
class SSEProgressData(BaseModel):
    agent_id: str           # "collector"
    step: str               # "search" / "extract" / "write" / "validate"
    summary: str            # "正在搜索 Notion pricing"(用户可见 narrative)
    metric: dict | None     # {"found": 5, "target": 10} optional progress
    ts: str
```

### `chunk` event schema

```python
class SSEChunkData(BaseModel):
    agent_id: str           # "analyst"
    step: str               # "thinking" / "drafting"
    delta: str              # LLM 增量 token(几个字符)
    ts: str
```

### 混合 LLM streaming 策略

| 调用类型 | 模式 | 用途 |
|---|---|---|
| **Reasoning / thinking step** | `stream=True` + chunk event forward | "正在思考 Notion 和 Coda 的核心差异..." typing 效果 |
| **结构化 extraction**(features / pricing / SWOT) | tools function-calling(non-stream)| 保证 schema 正确 |
| **Narrative writing**(撰稿员 final output) | `stream=True` + chunk event | 评委看到字逐个 typed 出来 |

### Backend agent 节点改造模板

```python
# rivalradar/agents/collector.py(改造后)
async def collect_node(state: GraphState, *, emit: EmitFn) -> dict:
    """Emit-driven SSE event forwarding (CQ-extend)."""
    await emit("progress", {
        "agent_id": "collector",
        "step": "search",
        "summary": f"夜枭正在搜索 {len(competitors)} 个竞品...",
    })

    for i, comp in enumerate(competitors):
        await emit("progress", {
            "agent_id": "collector",
            "step": "search",
            "summary": f"搜索 {comp}",
            "metric": {"current": i + 1, "total": len(competitors)},
        })
        evidence = await search_provider(comp)
        await emit("progress", {
            "agent_id": "collector",
            "step": "found",
            "summary": f"找到 {len(evidence)} 条证据",
        })

    # final yield (node done event)
    return {"evidence": all_evidence, "evidence_titles": [...]}
```

### `emit` callback 注入(LangGraph 集成)

```python
# rivalradar/graph/build.py(改造)
def build_graph(emit: EmitFn) -> StateGraph:
    """Build graph with emit callback bound to each node."""
    g = StateGraph(GraphState)
    g.add_node("collect", partial(collect_node, emit=emit))
    g.add_node("analyze", partial(analyze_node, emit=emit))
    g.add_node("write", partial(write_node, emit=emit))
    g.add_node("qc", partial(qc_node, emit=emit))
    # ...
```

### SSE generator 桥接

```python
# rivalradar/api/sse.py(改造)
async def graph_event_stream(...):
    queue = asyncio.Queue()
    emit = lambda ev_type, data: queue.put_nowait({"event": ev_type, "data": json.dumps(data)})

    graph = build_graph(emit=emit)

    # Run graph in background, drain queue to SSE
    task = asyncio.create_task(graph.ainvoke(initial))

    yield {"event": "start", "data": json.dumps({"run_id": run_id})}

    while not task.done() or not queue.empty():
        try:
            ev = await asyncio.wait_for(queue.get(), timeout=0.1)
            yield ev
        except asyncio.TimeoutError:
            continue

    yield {"event": "done", "data": json.dumps(await task)}
```

### Cancel API(P0-3 fix Problem 3 + F4 修订:asyncio.Task 真中断 in-flight)

**问题**:plan v3 原设计只在 step 间 check sqlite flag,**停不掉 in-flight Doubao stream / Tavily search** — demo 按 stop 后等当前 LLM call(20-60s)完才停 = 看起来 cancel 坏了。

**F4 修订设计**:

```python
# rivalradar/api/runs.py(新增 + F4 修订)
_RUN_TASKS: dict[str, asyncio.Task] = {}  # 全局 in-memory store

@router.post("/run/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict:
    """真中断:cancel asyncio.Task + close in-flight LLM/network streams."""
    task = _RUN_TASKS.get(run_id)
    if task and not task.done():
        task.cancel()  # 抛 CancelledError 到 graph 执行栈,中断 in-flight await
    return {"cancelled": True, "run_id": run_id}

# POST /run 时:
async def post_run(...):
    task = asyncio.create_task(graph.ainvoke(initial))
    _RUN_TASKS[run_id] = task
    try:
        async for chunk in stream:
            yield chunk
    except asyncio.CancelledError:
        # graph + LLM SDK 都会清理 in-flight streams
        yield {"event": "cancelled", "data": json.dumps({"run_id": run_id})}
    finally:
        _RUN_TASKS.pop(run_id, None)
```

**前端配合**:UI 立即标 "stop receiving" + 切到 cancelled state,不等 backend confirm(F4 mitigation)。

---

## 前端 Component 重构

### 顶层架构变化

```
plan v2:
  RunPage = RunSummary + DagCanvas + QCIssuePanel + Placeholders

plan v3:
  RunPage = RunHeader + VirtualOfficeView (主) | DagDetailView (次,切换)
           + AgentTeamRoster (左 rail 替换原 "竞品列表" placeholder)
           + ReportSheet (底部抽屉,structured output)
```

### 新 component map(详细 spec)

| Component | 文件 | 职责 |
|---|---|---|
| `VirtualOfficeView` | `components/office/VirtualOfficeView.tsx` | 主视图 — 办公室 SVG/Canvas + 4 agent 工位 + 移交动画 |
| `AgentCharacter` | `components/office/AgentCharacter.tsx` | 单 agent — Lottie body + 动物头像 overlay + state-driven 动画 |
| `SpeechBubble` | `components/office/SpeechBubble.tsx` | agent 头顶 thought bubble — 实时 typing + auto-fade |
| `LiveFeedPanel` | `components/office/LiveFeedPanel.tsx` | 右侧 scroll feed — agent narrative log(全 progress events 累积) |
| `HandoffAnimation` | `components/office/HandoffAnimation.tsx` | agent 之间文档移交动画(framer-motion path + 文件 icon) |
| `DagDetailView` | `components/office/DagDetailView.tsx` | 切换视图 — 复用 Task 6 DagCanvas 80% + 加 ObservabilityPanel |
| `ViewSwitcher` | `components/office/ViewSwitcher.tsx` | 右上角 tab 切换 "办公室视图 / 流程图详情" |
| `ReportSheet` | `components/office/ReportSheet.tsx` | 底部抽屉 — final structured report(竞品报告 + 引用) |
| `AgentTeamRoster` | `components/office/AgentTeamRoster.tsx` | 左 rail — 4 agent 头像 + 名字 + 当前状态 chip + 点击 focus |
| `CancelButton` | `components/office/CancelButton.tsx` | 顶部 + 单 agent 卡片 — Pause/Resume/Stop 三按钮(P0 阻断项) |

### 旧 component 复用 vs 重写决策矩阵

| Task 6 文件 | plan v3 决策 | 说明 |
|---|---|---|
| `components/dag/DagCanvas.tsx` | 🔄 改造复用 | 移到 `DagDetailView` 内部,SVG layout 不变 |
| `components/dag/DagNode.tsx` | 🔄 改造复用 | 在 DagDetailView 用,虚拟办公室不用(被 AgentCharacter 取代) |
| `components/dag/DagEdge.tsx` | 🔄 改造复用 | 同上 |
| `components/dag/DagRetryArc.tsx` | 🔄 改造复用 | 同上 |
| `components/dag/DagDrawer.tsx` | 🔄 改造复用 | 改成"agent 详情抽屉",点 AgentCharacter 也弹同样 trace |
| `components/dag/dagLayout.ts` | 🔄 改造复用 | 同上 |
| `components/QCIssuePanel.tsx` | 🔄 改造复用 | 移到 DagDetailView,虚拟办公室换成镜湖(质检员)speech bubble |
| `components/placeholders.tsx` | 🗑 删除 | 替换为真实 components |
| `components/Layout.tsx` | ✅ 保留 | 顶部 header + 左 rail layout 仍用 |
| `components/ThemeToggle.tsx` | ✅ 保留 | dark mode 不变 |
| `components/BackendDownBanner.tsx` | ✅ 保留 | 不变 |
| `stores/runStore.ts` | 🔄 改造复用 60% | 加 progress/chunk event 处理 + agent typing buffer |
| `stores/evidenceStore.ts` | ✅ 保留 | LRU cache 不变 |
| `stores/themeStore.ts` | ✅ 保留 | 不变 |
| **新建** `stores/agentTeamStore.ts` | 🆕 新 | 从 backend 拉 agent 配置 |
| **新建** `stores/typingStore.ts` | 🆕 新 | per-agent typing buffer(chunk event 累积) |
| `hooks/useSSE.ts` | ✅ 保留 | module-level controller 不变 |
| `hooks/useHealthz.ts` | ✅ 保留 | 不变 |
| `lib/api.ts` | 🔄 改造复用 | 加 `fetchAgents` / `cancelRun` |
| `types/api.ts` | 🔄 改造复用 | 加 SSE progress/chunk event types + AgentSpec/AgentTeam |
| `pages/RunsPage.tsx` | 🔄 改造小 | dimension label 中文映射(P0 阻断项 P2)|
| `pages/RunPage.tsx` | 🔄 大改 | 集成 ViewSwitcher + VirtualOfficeView + AgentTeamRoster + CancelButton |
| `pages/CompetitorPage.tsx` | ✅ 保留 | 不变 |

**复用 vs 重写 比例:** ~55% 复用 / ~45% 新写。Task 1-5 基础设施(scaffolding/theme/router/stores/SSE driver)100% 复用,Task 6 DAG 改成"次要视图"完整保留。

---

## File Structure(新增 + 改造)

```
frontend/src/
├── types/
│   ├── api.ts                          # 🔄 改造:加 SSE progress/chunk + AgentSpec
│   └── agents.ts                       # 🆕 AgentDescriptor + AgentTeam
├── lib/
│   ├── api.ts                          # 🔄 加 fetchAgents / cancelRun
│   ├── dimensions.ts                   # 🆕 DIMENSION_LABELS 中文映射(P0 Problem 2)
│   └── officeLayout.ts                 # 🆕 4 agent 工位坐标 + 办公室区域 layout
├── stores/
│   ├── runStore.ts                     # 🔄 加 progress/chunk handler
│   ├── agentTeamStore.ts               # 🆕 backend agent 团队配置缓存
│   ├── typingStore.ts                  # 🆕 per-agent typing buffer
│   └── evidenceStore.ts                # ✅ 保留
├── hooks/
│   ├── useSSE.ts                       # ✅ 保留
│   └── useElapsed.ts                   # 🆕 100ms tick timer for "已工作 12s"
├── components/
│   ├── office/                         # 🆕 整目录
│   │   ├── VirtualOfficeView.tsx       # 🆕 主视图(SVG 办公室 + 工位 + agent)
│   │   ├── AgentCharacter.tsx          # 🆕 Lottie + 动物头像
│   │   ├── SpeechBubble.tsx            # 🆕 thought + typing
│   │   ├── LiveFeedPanel.tsx           # 🆕 narrative scroll log
│   │   ├── HandoffAnimation.tsx        # 🆕 文档移交动画
│   │   ├── AgentTeamRoster.tsx         # 🆕 左 rail 4 agent 卡
│   │   ├── ViewSwitcher.tsx            # 🆕 office / dag tab
│   │   ├── DagDetailView.tsx           # 🆕 包装现有 DagCanvas + ObservabilityPanel
│   │   ├── ReportSheet.tsx             # 🆕 底部 structured output sheet
│   │   └── CancelButton.tsx            # 🆕 Pause/Resume/Stop
│   ├── dag/                            # 🔄 整目录改成 DagDetailView 内部
│   ├── QCIssuePanel.tsx                # 🔄 移到 DagDetailView 内部
│   ├── Layout.tsx                      # ✅ 保留
│   ├── ThemeToggle.tsx                 # ✅ 保留
│   └── BackendDownBanner.tsx           # ✅ 保留
└── assets/
    └── agents/                         # 🆕 整目录
        ├── owl.json                    # Lottie body
        ├── owl-avatar.svg              # 动物头像 overlay
        ├── fox.json
        ├── fox-avatar.svg
        ├── raccoon.json
        ├── raccoon-avatar.svg
        ├── turtle.json
        ├── turtle-avatar.svg
        └── office-bg.svg               # 办公室背景(工位 + 装饰)
```

```
backend/rivalradar/
├── agents/
│   ├── collector.py                    # 🔄 加 emit callback,reasoning stream
│   ├── analyst.py                      # 🔄 加 emit callback,reasoning stream
│   ├── writer.py                       # 🔄 加 emit callback,narrative stream
│   ├── qc.py                           # 🔄 加 emit callback
│   └── spec.py                         # 🆕 AgentSpec + AGENT_TEAMS["competitor_radar"]
├── graph/
│   ├── build.py                        # 🔄 emit injection via partial
│   ├── nodes.py                        # 🔄 emit-aware node wrappers
│   ├── state.py                        # 🔄 加 cancelled flag
│   └── router.py                       # ✅ 保留
├── llm/
│   ├── structured.py                   # ✅ 保留(tools function-calling)
│   └── streaming.py                    # 🆕 stream=True wrapper,emit chunk events
├── api/
│   ├── sse.py                          # 🔄 大改:queue-driven event drain
│   ├── runs.py                         # 🔄 加 POST /run/:id/cancel + GET /agents
│   └── deps.py                         # ✅ 保留
└── db/
    └── repository.py                   # 🔄 加 set_run_cancelled / get_run_cancel_status
```

---

## Asset / Design 资源策略(F3 修订:SVG sprite 优先)

### **D2 上午资源决策**(plan v3 v3.1 — F3 修订)

按 P0-1 拟物动物 + 真实可爱 + 展示效果重要,**asset 风险被识别为产品风险而非简单采购**。**决策顺序:**

1. **优先 path:SVG sprite + CSS state class**(P0):
   - 从 Iconscout / Storyset / Manypixels 找一致风格 4 动物(同一 illustrator 系列)
   - 每动物 4 state SVG = 16 个 SVG 文件 + CSS class 切换
   - 优点:风格 cohesive 可控、bundle size 小(每 SVG ~5-15 KB)、无运行时 Lottie player 依赖
   - **D2 上午 1.5-2h 找完 + 试装,找不到 cohesive set → fallback Lottie**

2. **fallback path:Lottie character + 自定义动物头像 overlay**(F3 mitigation):
   - generic Lottie character body(LottieFiles 免费)+ 自定义 SVG 动物头像叠加
   - 牺牲一致性,保 4 agent 体感差异
   - Lottie 文件 dynamic-import(Epic 4.7),首页不 load

3. **最差 path:emoji + 简笔 SVG**(应急):
   - 🦉🦊🦝🐢 大 emoji + CSS hover 动画 + speech bubble
   - 不符合 P0-1 "真实可爱 + 展示效果"
   - **仅在 D2 上午 path 1 + 2 都失败才用,需 user 即时决策**

| Agent | 优先 SVG 关键词 | Lottie fallback 关键词 |
|---|---|---|
| 收集员(🦉 夜枭) | "owl illustration set" / "wise bird character pack" | "owl character lottie" |
| 分析员(🦊 灵犀) | "fox illustration set" / "smart fox character pack" | "fox character lottie" |
| 撰稿员(🦝 灵巧) | "raccoon illustration set" / "writer animal pack" | "raccoon character lottie" |
| 质检员(🐢 镜湖) | "turtle illustration set" / "wise turtle pack" | "turtle character lottie" |

### 办公室背景 SVG(自绘 + 免费 illustration)

- 4 个工位区域(LayoutGrid 2x2 或 1x4 水平排列)
- 每个工位有 desk + chair + 标识物品(显示器/放大镜/打字机/印章)
- 中央有"会议区"用于移交动画
- 风格:flat illustration + 莫兰迪青绿配色(继承 DESIGN.md)
- 来源:Storyset (free) / Manypixels / 自绘 figma export

### DESIGN.md 更新(plan v3 实装时同步)

新增 design tokens:
- `--office-bg`(办公室背景色,比 surface-subtle 稍暗)
- `--seat-1/2/3/4`(4 个工位 highlight 色 — 跟 agent role 关联)
- `--speech-bg`(thought bubble 背景,白色 + 阴影)
- `--typing-cursor`(typing 光标闪烁色)

---

## Phase 4 Task 拆解(Epic 1-7)

时间预算 6 天到 demo (06-02/03),每 Epic 分配如下:

### Epic 0: P0 bug fix + design alignment + 基础设施(Day-1 全天,~6.5h)

> 这些是 spike 找到的 P0 bug + design review 找到的 design alignment + plan v3 实装的前置 — 必须先清

- [ ] **0.0a DESIGN.md 更新接纳 v3 paradigm(D16 修订)**:保留 90% 不冲突 tokens(IBM Plex / 24 CSS vars / Spacing / Signature Patterns),加 "office paradigm + agent character + 双视图叙事" 章节 + Decisions Log 记录 paradigm pivot — **45 min**
- [ ] **0.0b 5 user-visible UI state 详细 spec(D17 修订)**:plan v3 §3 加表 + Epic 4.x 实装时跟进:
  - loading(创建 run 中):虚拟办公室出现,4 agent 都坐工位 idle + 顶部 "正在创建调研..." progress bar
  - empty(第一次打开虚拟办公室,无 SSE):4 agent 都 idle 状态 + 中央"等待你提交调研"占位 + 引导回 /runs
  - error(SSE 断/LLM 5xx):红色 banner "agent 网络异常 · [retry button]" + 4 agent 都标橙色 warning + speech bubble 显示具体 agent 错误
  - cancelled(stop 后):4 agent 立刻停动作 + 中央 "已停止 · 已收集 N 条证据" + 引导"新调研"或"查看部分结果"
  - partial(只部分 agent done):还在跑的 agent 保 working 动画,done 的 agent 切 idle 但保留 speech bubble 最后一条 narrative
  — plan v3 §3 加表 ~45 min + Epic 4.x 实装 ~30 min(各 state UI)
- [ ] **0.0c a11y keyboard nav + ARIA landmarks baseline(D18 修订)**:keyboard Tab/Enter/Escape 路径 spec(Tab 顺序:CancelButton→AgentCharacter×4→ReportSheet→DAG tab)+ ARIA `role="main"/"complementary"/"navigation"` + 关键按钮 `aria-label` + contrast 4.5:1 验证 + Layout.tsx Tailwind mobile fallback 不坍(无完整 mobile 支持)— ~30 min plan + 30 min 实装
- [ ] 0.1 dimension label 中文映射(`lib/dimensions.ts` + RunsPage map)— 15 min
- [ ] 0.2 DagNode SVG r=undefined 已 fix(working tree)— commit 即可 — 5 min
- [ ] 0.3 RunSummary 优先 runStore.status fallback `fetchRun.status`(避免 stale) — 15 min
- [ ] **0.4 backend cancel API + asyncio.Task handle per run(F4 修订)**:`POST /run/:id/cancel` + 全局 `dict[run_id → asyncio.Task]` + `task.cancel()` 中断 in-flight LLM/network + SSE generator catch CancelledError emit `cancelled` event — **1.5h**(从 1h 增)
- [ ] 0.5 frontend CancelButton 组件(顶部 Stop)+ 接入 useSSE.stop() + UI 立即 "stop receiving" 标 cancelled,即使 backend 上游 cleanup 滞后 — 30 min
- [ ] ~~0.6 backend `GET /agents` API + `AgentSpec` schema~~ — **删除(D13 reverse)**:frontend Layout.tsx 直接 hardcode 4 agent constants(name/role/avatar/persona),backend 只 emit event payload 带 stable `agent_id` 字段
- [ ] 0.7 backend SSE event v2:`SSEProgressData` + `SSEChunkData` + sse-starlette payload mapping — 45 min

**Epic 0 完成 = 4 P0 problem 全清 + plan v3 基础设施落地**(净 cost: 4h → 3.5h,因删 0.6 + 加 0.4 cost)

### Epic 1: agent constants + frontend store(Day-1 下午,~3.5h)

- [ ] 1.1 `frontend/src/types/agents.ts`:AgentDescriptor (id/name/role/avatar/persona/capabilities) — 15 min
- [ ] 1.2 `frontend/src/lib/api.ts`:cancelRun typed wrapper(D13 reverse 后无 fetchAgents)— 15 min
- [ ] **1.3 `frontend/src/lib/agentConstants.ts` hardcode 4 agent(D13 reverse)**:`AGENTS = [{id:'collector',name:'夜枭',role:'收集员',...}, ...]` 直接 export,Layout.tsx 引用 — 30 min(从 0.5h)
- [ ] **1.4 `frontend/src/stores/typingStore.ts`:per-agent typing buffer + throttle window 50 chunks + 16ms batch setState(D7 fix)** — 1h(从 45 min)
- [ ] 1.5 `frontend/src/stores/runStore.ts` 改造:progress + chunk event handler + 节点开始/结束时间记录(为 useElapsed)— 1h
- [ ] 1.6 `frontend/src/hooks/useElapsed.ts`:per-agent elapsed timer hook(100ms tick)— 30 min
- [ ] 1.7 types/api.ts 加 SSEProgressData + SSEChunkData mirror — 20 min

**Epic 1 完成 = frontend agent 常量 + state 完整**(净 cost 4h → 3.5h)

### Epic 2: backend agent 节点 emit-driven 改造(Day-2 上午,~4.5h)

> 这是 P0-4 完整 streaming 的 backend 核心改造,关键路径

- [ ] 2.1 `rivalradar/graph/build.py`:emit callback injection via partial — 30 min
- [ ] **2.2 `rivalradar/api/sse.py` 大改:queue-driven event drain + try/finally + listener detect + drain on exit(D8 fix)**:client disconnect 时 cleanup queue,graph exception emit error 后 exit,cancel 在 wait_for 时被接住 — 2h(从 1.5h,加 safety net +30 min)
- [ ] 2.3 `rivalradar/agents/collector.py` 加 emit:search step / found step — 30 min
- [ ] 2.4 `rivalradar/agents/analyst.py` 加 emit:thinking stream / extract step — 1h
- [ ] 2.5 `rivalradar/agents/writer.py` 加 emit:writing stream(narrative typing) — 1h
- [ ] 2.6 `rivalradar/agents/qc.py` 加 emit:validate step / verdict — 30 min
- [ ] 2.7 `rivalradar/llm/streaming.py`:stream=True wrapper + chunk forward helper — 45 min

**Epic 2 完成 = backend 真正 stream 出来,SSE 6 类 event 全产 + queue race/leak 修**(净 cost 4h → 4.5h)

### Epic 3: 虚拟办公室 layout + AgentCharacter(Day-2 下午 + Day-3 上午,~7h)

- [ ] **3.0 fake SSE event player(F2 修订)**:`scripts/fake_sse_player.ts`(frontend dev-only)+ recorded `fixtures/sample-run.jsonl` SSE 流 + dev mode toggle "fake stream",让 office UI 用 recorded events 验证视觉(不依赖 backend Epic 2 ready)— **30 min**
- [ ] **3.1 找 4 个 cohesive 动物角色资源(F3 修订)**:**优先 SVG sprite set + CSS state class**(Iconscout/Storyset/Manypixels 找一致风格 4 动物 × 4 state = 16 SVG)。Lottie 仅在 cohesive set 找到才用 fallback — 1.5-2h
- [ ] 3.2 自绘 / 改造 office background SVG(2x2 工位 + 中央区) — 1.5h
- [ ] 3.3 `components/office/AgentCharacter.tsx`:SVG sprite + CSS state class 切换(idle/working/thinking/handoff)— 1.5h
- [ ] 3.4 `components/office/VirtualOfficeView.tsx`:SVG layout + 4 工位 + 加载 4 AgentCharacter — 2h
- [ ] 3.5 `lib/officeLayout.ts`:工位坐标 + 移交路径(因 D13 reverse 改 frontend hardcode,坐标也在此 file)— 30 min
- [ ] 3.6 DESIGN.md 增 office tokens + 同步 tailwind.config.ts — 30 min

**Epic 3 完成 = 虚拟办公室静态版可看(4 动物坐工位,SSE 数据驱动 state + 可用 fake player 离线验证)**

### Epic 4: SpeechBubble + LiveFeedPanel + Handoff + dynamic-import(Day-3 下午 + Day-4 上午,~6.5h)

- [ ] 4.1 `components/office/SpeechBubble.tsx`:framer-motion AnimatePresence + typing 增量 render — 1.5h
- [ ] 4.2 typing buffer ↔ SpeechBubble 接线(typingStore subscribe,window 50 chunks 显示)— 30 min
- [ ] 4.3 `components/office/LiveFeedPanel.tsx`:scroll feed + agent role 颜色标 + auto-scroll bottom — 1.5h
- [ ] 4.4 `components/office/HandoffAnimation.tsx`:framer-motion path + 文档 icon + ease — 1h
- [ ] 4.5 office → handoff 触发逻辑(node 切换时检测 from→to,emit handoff event 给 frontend) — 1h
- [ ] 4.6 集成 + 真后端 spike 调试 — 30 min
- [ ] **4.7 Lottie/sprite dynamic-import + Suspense fallback + bundle size 验证(D11 修订)**:`React.lazy(() => import('./AgentCharacter'))` + Suspense + run `pnpm build` + 验证 gzip < 250 KB — 30 min

**Epic 4 完成 = 实时 typing + speech bubble + 移交动画全部跑通 + bundle size 验证 ≤ budget,35% money shot 真兑现**(净 cost 6h → 6.5h)

### Epic 5: DAG tab + DagDetailView 集成(Day-4 下午,~3h)

- [ ] 5.1 `components/office/ViewSwitcher.tsx`:右上 tab 切换 — 30 min
- [ ] 5.2 `components/office/DagDetailView.tsx`:包装现有 DagCanvas + QCIssuePanel — 1h
- [ ] 5.3 DagDetailView 加 ObservabilityPanel(Codex #15,从 plan v2 Task 12 提前) — 1h
- [ ] 5.4 双视图 state 同步(切换不丢 store state)— 30 min

**Epic 5 完成 = DAG 详情视图保留,评委可看工程深度**

### Epic 6: AgentTeamRoster + ReportSheet + EvidenceChip 简化版(Day-5 上午,~4h)

- [ ] 6.1 `components/office/AgentTeamRoster.tsx`:左 rail 4 agent 卡 + 状态 chip + click focus office — 1.5h
- [ ] 6.2 `components/office/ReportSheet.tsx`:底部抽屉 + structured report(报告 markdown 渲染 + EvidenceChip)— 2h
- [ ] 6.3 EvidenceChip 简化版(hover 显示 source URL + title,plan v2 Task 9 减重)— 30 min

**Epic 6 完成 = 报告交付端完整,evidence 可追溯**

### Epic 7: polish + demo fixture + audit + ship(Day-5 下午 + Day-6,~8.5h)

- [ ] 7.1 demo fixture(plan v2 Task 13 简化):录一次完整 SSE 流 → seed sqlite + JSONL,**不需要 LLM key 也能 demo**;**复用 Epic 3.0 fake SSE player 录制能力** — 1.5h
- [ ] 7.2 视觉 polish:动物 character 微调 / 工位摆放 / speech bubble 字号 / 移交流畅度 — 2h
- [ ] 7.3 demo screenshot 系列 + demo 视频脚本 — 1h
- [ ] 7.4 lighthouse 跑(已 Epic 4.7 done 一轮,这里二次验证)+ bundle 已分某 — 30 min(从 1h,因 Epic 4.7 提前做了)
- [ ] 7.5 typecheck + lint + format:check 全 PASS — 30 min
- [ ] **7.5b core path 最小 unit test ~10 测(D10 修订)**:backend cancel API + emit queue drain + agent abstract + chunk progress event + dimension label,LLM 调用全 mock — 2-3h
- [ ] 7.6 `/codex` outside voice 跑 frontend code review(指定重点 file:office/* + sse.py + cancel API,不全扫)— 45 min(从 1h,scope 缩)
- [ ] 7.7 `/ship` workflow:commit + PR + land-and-deploy — 1h

**Epic 7 完成 = demo ready + ship + audit pass + 测试基线**(净 cost 6-8h → 8.5h,主要是 +2-3h core path test)

---

## 时间预算 + 里程碑(D1-D6 真实日期)

| Day | 真实日期 | Epic | 里程碑 | Spike point |
|---|---|---|---|---|
| **D1** | **2026-05-28 周四** | Epic 0 + 1 | bug 全清 + frontend agent 抽象层(hardcode 4 agent) + cancel asyncio.Task | 单元跑新 store + cancel API 单测 pass |
| **D2** | **2026-05-29 周五** | Epic 2 + 3.0-3.2 | backend SSE 6 类 event 全产 + **fake SSE event player(F2)** + Lottie/sprite 资源决策(F3) + office bg 静态版 | curl POST /run 看 progress/chunk event 真流 + office-only 用 fake player demo |
| **D3** | **2026-05-30 周六** | Epic 3.3-3.6 + 4.1-4.3 | AgentCharacter + SpeechBubble + LiveFeed + typing throttle | 真后端 spike:4 动物坐工位 + speech bubble typing |
| **D4** | **2026-05-31 周日** | Epic 4.4-4.7 + 5 | 移交动画 + **Lottie/sprite dynamic-import(F1)** + DAG tab + DagDetailView | 完整 vertical slice spike:打开浏览器→submit→看完整虚拟办公室动画 |
| **D5** | **2026-06-01 周一** | Epic 6 + 7.1-7.3 + 7.5b | TeamRoster + ReportSheet + demo fixture + 视觉 polish + **core path test ~10 测** | **🚨 关键 check-in 上午**:全 vertical slice 真后端可看,bug 剩余 buffer 决策 |
| **D6** | **2026-06-02 周二 demo** | Epic 7.4-7.7 | lighthouse + audit + ship + land-and-deploy | 比赛 demo,PR landed |

**Demo deadline**: 2026-06-02 周二(D6 当天 demo)

**🚨 Day-5 关键 check-in**:D5 上午跑完整端到端 spike,如发现 P1 bug 未修需立刻决策:① 砍 Epic 6.3/7.4/7.6 P1 加分项保 ship;② 推迟 demo 1 天到 06-03(取决于比赛是否允许)

### 关键里程碑

- **D2 晚**:backend SSE event v2 端到端打通(curl 验证)— 风险最高的 Epic 2 完成 ✓
- **D3 晚**:虚拟办公室真后端可看(动物 + typing)— 35% money shot 真实可见
- **D4 晚**:完整 vertical slice spike — 跟 user 一起 demo 试跑
- **D5 晚**:demo fixture + 视觉 polish 完成 — 不需要 LLM key 也能 demo
- **D6 晚**:ship + audit + 全部完成

---

## 风险 + Mitigation

| # | 风险 | 概率 | 影响 | Mitigation |
|---|---|---|---|---|
| **R1** | Doubao stream chunk forward 协议不兼容(虽然 SDK 兼容但 ARK 服务实测可能不一样) | M | H | D2 上午先跑 spike(直接 curl ARK stream),提前 verify;不通则降级 "fake stream"(node done 后切字回放) |
| **R2** | Lottie 动物 character 找不到合适资源 | M | M | fallback:用 generic Lottie character + SVG 动物头像 overlay(免费 emoji 动物 icon);最差 case:Storyset / unDraw 插画截取 |
| **R3** | WSL2 + Clash fake-ip 卡 Doubao(spike 已确认)| H | H | demo fixture(Epic 7.1)是 mitigation — 录一次真打 LLM 然后 seed,demo 时不依赖实时 Doubao;或 user 关 Clash 跑 |
| **R4** | LangGraph emit callback inject 跟 stream_mode="updates" 冲突 | L | H | 备选:不用 emit callback,改用 LangGraph custom event(`graph.astream_events()`)— 但要换 v2/v3 stream API,改 sse.py 风险 |
| **R5** | 虚拟办公室 SVG 性能 / framer-motion 卡顿 | L | M | Lottie + framer-motion 都是 GPU accelerated,4 个角色 + 1-2 个移交动画在 60fps 范围;实测不行就降到 30fps |
| **R6** | Bundle size 超 250 KB(Lottie 文件 + framer-motion + 字体)| M | M | dynamic-import Lottie + Lottie 文件 lazy load(用到才请求);Lottie 选 compact 版本(< 30 KB each) |
| **R7** | 时间预算 overrun(6 天打满,任何 Epic 延 0.5 天都伤)| H | H | Epic 6.3 EvidenceChip / Epic 7.4 lighthouse / Epic 7.6 codex audit 是 P1 减重项,实在不行 cut;Epic 0/1/2/3/4 是 P0 不可减 |
| **R8** | Cancel API + frontend 协调(stop 后 backend 是否优雅清理) | M | M | LangGraph state cancelled flag check at each step + asyncio.CancelledError catch + SSE generator emit 'cancelled' event;前端 useSSE.stop() 已实现 |
| **R9** | 4 个动物 persona 跟"严肃竞品调研"业务气质冲突(评委觉得太幼稚)| L | M | persona 设计偏向"专业 + 一点拟人趣味"(夜枭/灵犀/灵巧/镜湖名字偏中性优雅),不卡通儿童;Day-3 spike 时 user review 决定 |

---

## P1 决策 TODO(plan v3 写完后 review 时定)

`<DECISION>` 标记的是 plan v3 没决定、需要 user 评审时决:

1. `<DECISION>` 动物种类 final 选择(plan v3 propose:🦉 猫头鹰/🦊 狐狸/🦝 浣熊/🐢 乌龟,user 可改)
2. `<DECISION>` agent 名字 final(plan v3 propose:夜枭/灵犀/灵巧/镜湖,中性优雅,user 可改成更口语)
3. `<DECISION>` 办公室 layout:2x2 vs 1x4 水平 vs 自由摆放
4. `<DECISION>` Lottie character 风格:写实卡通 vs 扁平插画 vs 像素艺术
5. `<DECISION>` speech bubble 语言风格:专业严谨("正在搜索 Notion 定价...")vs 拟人化("我去找 Notion 的定价信息啦~")
6. `<DECISION>` typing 速度:25 char/s(自然)vs 50 char/s(快)vs 跟 LLM 实际速度 1:1
7. `<DECISION>` 移交动画:文档图标飞过 vs 角色物理移动 vs Karen-Toa "传递" 动作
8. `<DECISION>` ReportSheet 默认 collapsed 还是 expanded(底部抽屉)
9. `<DECISION>` DAG tab 切换是 tab 还是 modal fullscreen
10. `<DECISION>` 一次 cancel 是 stop 整个 run 还是允许 stop 单 agent(P0 阻断项的简化 vs 完整)

---

## Phase 3 评审准备(Phase 2 完成后立刻进)

### 评审 1:`/plan-eng-review` — 架构与执行

**重点 review 区:**
- Epic 2 backend emit-driven 改造(LangGraph callback inject + queue-drain SSE generator)— 是否有 race condition / 内存泄漏 / cancel 协议清晰
- Epic 3 虚拟办公室 SVG / Lottie 性能(60fps 是否能保住,bundle size 影响)
- 复用 vs 重写决策矩阵(是否漏掉了应该保留的代码)
- Task 1-5 stores 改造范围(runStore 加 progress/chunk handler 是否破坏现有 invariant)
- 时间预算可执行性(6 天紧)

### 评审 2:`/plan-design-review` — 视觉与体验

**重点 review 区:**
- 拟物动物 + 4 个角色 persona 是否跟"严肃竞品调研"业务气质 align
- 双视图(办公室 + DAG)切换是否破坏 user 心智模型
- 中间产物 surface 节奏(thought / progress / typing)三层叠加是否信息过载
- DESIGN.md 莫兰迪青绿配色 + 动物角色风格是否协调
- 评委 5 秒第一眼看到什么 + 30 秒后印象

### 评审 3:`/codex` outside voice — 结构性盲点

**重点提问:**
- "plan v3 是否解决了 user 反馈的 4 个问题?有没有遗漏?"
- "agent 抽象层 design 是否真的支持未来场景扩展,还是 lockin 在竞品调研?"
- "Epic 2 emit-driven 改造的 callback inject 在 LangGraph 1.x 是不是 idiomatic?有没有更好的 stream_events v2 路径?"
- "Lottie + framer-motion + SVG 三技术叠加是否过重?"
- "时间预算 6 天 plan v3 全实装 + ship 是否现实?"

### 评审顺序 + 通过标准

```
1. /plan-eng-review  → 通过 = 架构无重大缺陷,Epic 拆解可执行
2. /plan-design-review → 通过 = 视觉方向 + 角色设定 user 接受
3. /codex consult/challenge → 通过 = 结构性盲点 < 3 个,无 critical
```

3 评审全过 = plan v3 锁定,进 Phase 4 实装。任何评审 fail → 改 plan v3 后重审。

---

## Success Criteria(plan v3 验收标准)

### plan v3 写作完成标准(Phase 2 出口)

- [ ] User vision(P0-1/2/3/4)100% 体现
- [ ] 4 个 spike 问题全有 fix path(在 Epic 0 或 Epic 2/3/4 里)
- [ ] Task 1-6 复用 vs 重写决策矩阵明确(到文件级)
- [ ] Phase 4 Epic 1-7 时间预算合计 ≤ 6 天
- [ ] 风险 + mitigation 至少 8 条
- [ ] P1 决策 TODO 明确(plan v3 review 时定)

### Phase 4 实装完成标准(plan v3 真正落地)

- [ ] 真后端 spike:4 动物坐办公室 + speech bubble typing + 移交动画全部跑通
- [ ] DAG tab 切换可见,ObservabilityPanel 工程深度兑现
- [ ] Cancel 按钮可用(stop 整个 run 优雅清理)
- [ ] dimension label 中文化
- [ ] 完整 streaming(reasoning chunk + 撰稿 narrative typing)
- [ ] demo fixture 录好,不需要 LLM key 也能放
- [ ] typecheck + lint + format:check + build 全 PASS
- [ ] Lighthouse > 80(理想 95+)
- [ ] Bundle size < 300 KB gzip(Lottie 加进来后预算可上调)
- [ ] /codex outside voice frontend review 无 critical
- [ ] /ship 完成 + PR landed(或本地 demo ready)

---

## 与 plan v2 的关键差异(便于 review)

| 维度 | plan v2 | plan v3 |
|---|---|---|
| **35% money shot 设计** | 实时 DAG + retry 弧 | 虚拟办公室 + 拟物动物 + 实时 typing + speech bubble |
| **paradigm 视角** | 工程师视角(流程图) | 用户视角(我请了一队员工) |
| **agent 抽象层** | hardcode 4 节点 enum | 解耦 AgentSpec/AgentTeam,GET /agents 配置驱动 |
| **SSE event 类型** | 4 类(start/node/error/done) | 6 类(+ progress + chunk) |
| **LLM 调用模式** | tools function-calling only | 混合(reasoning stream + 结构化 tools) |
| **Cancel 功能** | 完全没有 | Cancel API + frontend Stop button |
| **i18n / 中文化** | Task 12 才做 | Epic 0 立即做 dimension label,完整 i18n 仍 Day-4 |
| **Task 7-15 (plan v2)** | 9 个 broaden task | 重组为 Epic 0-7,大部分复用 + 拟物办公室换芯 |
| **demo fixture** | Task 13 | Epic 7.1 提前到 demo polish 阶段 |
| **总 task 数** | 16 task / 131 checkboxes | 8 Epic / 49 checkboxes(更聚焦) |
| **plan 行数** | 741 行 | ~600 行(目标) |

---

## Outside Voice 反馈待评审(Phase 3 输入)

plan v3 写完后立刻进 Phase 3 三角评审:

1. **plan-eng-review**:架构 + emit-driven + 复用决策 + 时间预算
2. **plan-design-review**:角色形象 + 视觉方向 + paradigm 切换风险
3. **codex consult**:结构性盲点 + 时间可执行性 + LangGraph 1.x 兼容

**预期通过率**:plan-eng 90% / plan-design 70% (角色 fine-tune)/ codex 80% (可能挑 emit-driven 实施细节)

---

## Memory + Learning 写入(plan v3 完成时)

- `vision-pivot-spike-driven`:spike 真打 LLM + 用户手测 = 比所有 mechanical checklist 更有价值
- `paradigm-engineer-vs-user-view`:DAG 流程图是工程师视角,虚拟办公室是用户视角 — 35% money shot 必须用用户视角
- `lottie-character-fallback-pattern`:找不到完美 character → generic body + 自定义头像 overlay
- `wsl-clash-fake-ip-llm-block`:Doubao 调用被 Clash fake-ip 路由海外 → demo fixture 是必须的 mitigation

---

## 文档版本历史

- **v3.1**(2026-05-27 此版本):v3 + plan-eng-review 5 处 + Codex outside voice 4 处 = 9 修订(详顶部 v3.1 修订摘要)
- **v3**(2026-05-27 初稿):虚拟办公室 + 拟物动物 + 完整 streaming(替换 v2 的 DAG paradigm)
- **v2**(2026-05-26):DAG vertical slice + retry 弧 + QC Issue Panel + 16 task 131 checkboxes
- **v1**(2026-05-26 早些):骨架版,被 outside voice review 打回(Codex 抓 7-8 处 schema 字段虚构)

---

**plan v3.1 三角评审完成,锁定**。

下一步:进 Phase 3 剩余评审(plan-design-review)→ Codex/eng tension 已 closed → Phase 4 实装(D1=05-28 周四起)。

---

## Implementation Tasks(eng review 综合)

| # | P | Component | Title | Source | Effort (human/CC) | Verify |
|---|---|---|---|---|---|---|
| T1 | P1 | frontend/stores/typingStore.ts | 实现 throttle window 50 + 16ms batch setState | D7 / Epic 1.4 | ~15min / ~10min | unit test:1000 chunk 输入 → store 内存 < 1KB |
| T2 | P1 | backend/rivalradar/api/sse.py | 加 try/finally + listener detect + drain on exit | D8 / Epic 2.2 | ~30min / ~20min | manual test:客户端关页 → backend log 无 emit 错误 |
| T3 | P1 | frontend/src/lib/agentConstants.ts | hardcode 4 agent + 删 agentTeamStore + GET /agents | D13 / Epic 1.3 | ~15min / ~10min | typecheck pass + Layout 渲染 4 agent |
| T4 | P1 | backend/api/runs.py + frontend | cancel asyncio.Task handle + UI stop-receiving | F4 / Epic 0.4 | ~1.5h / ~45min | spike:跑 run 10s 后 cancel,backend log 无 in-flight LLM 继续 |
| T5 | P1 | frontend dev scripts | fake SSE event player + recorded jsonl fixture | F2 / Epic 3.0 | ~30min / ~20min | office UI 用 fake player demo,无 backend 依赖 |
| T6 | P1 | frontend office/AgentCharacter | SVG sprite + CSS state class(Lottie fallback)| F3 / Epic 3.1+3.3 | ~2h / ~1h | 4 动物 × 4 state = 16 SVG cohesive 风格 |
| T7 | P1 | frontend bundle | Lottie/sprite dynamic-import + Suspense | D11 / Epic 4.7 | ~30min / ~20min | `pnpm build` 后 gzip < 250KB |
| T8 | P1 | backend tests | core path unit test ~10 测(cancel/emit/chunk)| D10 / Epic 7.5b | ~2-3h / ~1.5h | `pytest` 全 PASS,LLM 调用全 mock |
| T9 | P2 | plan v3 doc | 日历表 D1-D6 真实日期 + verdict 标 06-02 周二 | F1 / 顶部+§10 | 0 / 5min | 已完成(此 commit) |

**JSONL artifact**: 写入 `~/.gstack/projects/Billkst-RivalRadar/tasks-eng-review-{timestamp}.jsonl`(下一步 bash)

---

## NOT in scope(明确 defer)

- Lane F Task 14 完整 25 测基线 + Vitest 全装 → Day-4 stretch / demo 后(D10 选 A 只加 core path ~10 测)
- backend agent extensibility / scenario template / GET /agents endpoint → demo 后(D13 reverse)
- backend SqliteSaver checkpointer + retry 换 provider CRAG → 已在 TODOS.md
- 真 i18n 完整 zh-CN + en-US 双语切换(只 P0 dimension label 中文化)→ Lane F Day-4 stretch
- IBM Plex SC woff2 子集化 → Day-4 stretch
- PDF / Share URL / Storybook → Day-4 stretch
- 后端 SSE rate limit / SSRF / SDK timeout → 已在 TODOS.md(投产前必加)

## What already exists(Task 1-6 复用 + plan v3 不动)

- frontend Vite + React 19 + TS 6 脚手架 ✅ 100% 复用
- DESIGN.md 24 CSS vars + Tailwind ✅ 100% 复用,新增 office tokens
- Layout.tsx 双 rail 208px + ThemeToggle + BackendDownBanner ✅ 100% 复用
- useHealthz + useSSE module-level controller ✅ 100% 复用
- types/api.ts 16 entities mirror + 4 SSE event types ✅ 复用,加 2 类 event(progress/chunk)
- lib/api.ts 8 typed wrappers ✅ 复用,加 cancelRun
- runStore reducer 5 SSE events 全覆盖 ✅ 复用,加 progress/chunk handler
- evidenceStore LRU 50 + dedup ✅ 100% 复用
- themeStore init/cleanup ✅ 100% 复用
- DAG 4 节点 + retry 弧 + QCIssuePanel ✅ 复用,移到 DagDetailView(次要视图)
- ~55% Task 1-6 代码 复用,~45% 新写(office/* 10 components + agentConstants + typingStore)

## Failure modes(Day-5 上午 check-in 验证)

| 模式 | 是否有测 | 是否有 error handling | 用户看到 |
|---|---|---|---|
| backend SSE queue race(客户端关页时 leak)| ✓ T2 + T8 | ✓ try/finally + drain | 无显示(backend cleanup)|
| Doubao stream API timeout / 5xx | ❌ 待加 | ✓ SDK retry + emit error | "采集 Agent 暂时无法工作,正在重试" |
| Clash fake-ip 路由海外 vpn 卡 LLM | ❌ 不可测 | ✓ demo fixture fallback(Epic 7.1)| "切到离线 demo 模式"(user 看到) |
| cancel 时 in-flight Doubao stream 未关 | ✓ T4 + T8 | ✓ task.cancel() | UI 立即 "已停止",backend cleanup 2s 内 |
| Lottie animal 找不到 cohesive set | N/A | ✓ SVG sprite fallback(F3) | 用 SVG sprite,视觉差异变小但仍可看 |
| Bundle size > 250 KB | ✓ T7 | ✓ dynamic-import | lighthouse 评分降但 demo 不卡 |

**关键 gap**:Doubao 5xx 暂无测(需 mock httpx 重)— Day-4 stretch 补。

## Worktree parallelization(可选 Phase 4 加速)

| Lane | Epic | 触及 module | 依赖 |
|---|---|---|---|
| **Lane A** | Epic 0 + 1(frontend P0 fix + agent abstract)| frontend/src/* | — |
| **Lane B** | Epic 2(backend SSE emit-driven 改造)| backend/rivalradar/* | — |
| **Lane C** | Epic 3.0 + 3.1(fake SSE player + asset 资源决策)| frontend/scripts/* + assets/* | — |

**执行**:Lane A + B + C 并行 D1 起。D2 晚汇合 → Epic 3-4 主体 sequential(Lane B 必 ready 后才能跑 Lane A 真 SSE)。**保守 1 lane sequential 也可,parallelization 是加速 option**。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | 未跑(user 自己锁 vision D3-D5 4 个 P0 决策) |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | **CLEAR** | 5 findings 全 actionable(F1-F5),F1-F4 accepted(D14),F5 cross-model tension resolved(D13 reverse D9)|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | **CLEAR** | 5 P1 findings (D7-D11) 全 accept,arch 3 + test 1 + perf 1,scope challenge user accepted no-buffer |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | **CLEAR** | score: 5/10 → 7.5/10,4 decisions made(D16 paradigm align / D17 5 UI state / D18 a11y baseline / D19 6 polish defer)|
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | N/A(RivalRadar 是终端用户产品,无 dev-facing surface) |

**CODEX:** 5 findings 拓深盲点(日历错 / streaming 依赖风险 / asset 风险 / cancel 实施缺口 / over-engineering 单场景),与 Claude eng review 互补,无 Claude review 重叠。
**CROSS-MODEL:** 1 tension (Finding 5 backend AgentSpec) — user 选 Codex side reverse D9,P0-2 单场景 demo 优先。
**UNRESOLVED:** 0(D6/D7/D8/D9→D13/D10/D11/D12/D13/D14/D15/D16/D17/D18/D19 全锁,6 项 polish 决策 defer Day-3 visual 决)
**VERDICT:** **ENG + CODEX + DESIGN CLEARED — plan v3.2 ready to implement(D1=2026-05-28 周四起 Epic 0,~6.5h workload)**

