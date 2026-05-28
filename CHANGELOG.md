# Changelog

All notable changes to RivalRadar are documented here per [Keep a Changelog](https://keepachangelog.com/) conventions.

Versioning follows 4-digit semver `MAJOR.MINOR.PATCH.MICRO`(< 1.0 表 API 未稳定,迭代期允许 breaking changes)。

## [0.2.0.0] - 2026-05-28

**Lane F 前端完整交付**:虚拟办公室 paradigm 实装(35% 评分命门)。用户进 `/run/:id` 看到 4 个 agent character(收集员 🦉 / 分析员 🦊 / 撰稿员 🦝 / 质检员 🐢)在 2x2 工位实时工作,带 ripple ring(工作中)/ ✓ checkmark(完成)/ "已工作 N 秒" elapsed badge。Agent 间任务交接走中央会议区动画(招牌时刻 #3),writer chunks 实时累积到底部 ReportSheet drawer。Office 视图旁可一键切 DAG 工程视图(架构图 + ObservabilityPanel 原始 event timeline),保留工程深度展示。Demo 模式 fixture(`run_demo01`)走纯前端 replay,demo day 即使 backend / Clash / Doubao 全挂也能完整跑 25s。

### Added

- **frontend stack**:Vite 8 + React 19.2 + TS 6 + Tailwind 3 + Zustand 5 + framer-motion 12 + @microsoft/fetch-event-source + Radix UI。bundle 148 KB gzip(<<250 KB target,59% 余量)。lighthouse 100/100 realistic mode(FCP 0.5s / LCP 0.5s / TBT 0ms / CLS 0.056)。
- **office UI components**(Epic 0-6 plan v3.2)— `VirtualOfficeView`(2x2 工位 + AgentCharacter + ring/checkmark/elapsed badge)+ `SpeechBubble`(framer-motion typing)+ `LiveFeedPanel`(scroll feed + role color)+ `HandoffAnimation`(800ms keyframe from→meeting→to)+ `AgentTeamRoster`(左 rail 4 agent 卡)+ `ReportSheet`(底 drawer markdown)+ `ObservabilityPanel`(DAG tab raw timeline)+ `CancelButton`(Esc + 3 态:running/cancelling/cancelled)+ `OfficeBackground`(SVG 自绘)+ `ViewSwitcher`(office vs DAG)。
- **state machine**:`runStore`(progress / chunk / node / done / handoff 5 类 SSE event handlers · perAgentNarrative · nodeStartTs/EndTs · writerReport 持久累积 · handoffQueue 单槽 FIFO · cancelRun action · 'cancelled' enum)+ `typingStore`(throttle WINDOW 50 + 16ms batch + pending buffer race fix)+ `useElapsed` hook(100ms tick wall clock)。
- **dev / demo 兜底**:`fakeSSEPlayer`(SAMPLE_EVENTS replay · ts rebase 到 wall clock · runId override · 3 速度 preset Fast/Real/Slow)+ `demoFixture`(DEMO_RUN_ID `run_demo01` + DEMO_RUN_DETAIL + isDemoRun bypass)+ RunsPage 顶部 "🎬 Demo 模式" 大卡片。
- **i18n + a11y baseline**:6 个 controlled dimension 中文映射(`定价/部署方式/集成生态/目标用户/核心工作流/用户口碑`)+ status badge 中文 label(`完成/进行中/失败/已停止/证据不足/降级`)+ Esc 快捷键 cancel + 全 office 组件 ARIA(`role="region"` / `role="tablist"` / `aria-label` / `aria-expanded`)。
- **backend SSE v2 queue-driven**:`sse.py` async main task + `asyncio.Queue` drain + sync `emit` 回调通过 `config["configurable"]["emit"]` 注入(backward compat:tests 不传 emit → None → no-op)+ `_ACTIVE_RUN_TASKS` dict 记录 task 句柄供 cancel + `try/finally` 清理。新增 SSE event 类型:`progress`(agent_id / step / summary / metric)+ `chunk`(agent_id / delta / step)+ `cancelled`。`llm/streaming.py` `stream_chat` 包装器(累 + skip empty + emit 回调每 chunk)。
- **cancel API + DB CAS**:`POST /run/:id/cancel` → `task.cancel()` + `mark_run_cancelled` CAS(仅 status='running' 时切 cancelled,防覆盖已 finalize 的 done)。
- **demo fixture path bullet-proof**:RunPage `isDemoRun` bypass 自动 `playFakeSSE Real`,不打 backend / SSE。Demo URL 直接进 office UI 演示。
- **backend test 增量**:198 → 215(+17 新)。新增 `test_api_cancel.py`(5 tests:idempotent + CAS + finalize race guard)+ `test_streaming.py`(3 tests)+ `test_sse_emit.py`(3 tests)+ `test_config.py` 新增 DOUBAO_MODEL strict-raise + `test_api_sse.py` 新增 SSE error sanitize 用例。213 → 214 测试全过 7.97s。

### Changed

- **DESIGN.md 更新接纳 v3 paradigm**(143 lines)— office tokens(`--office-bg` · `--speech-bg` · `--typing-cursor` · `--seat-1..4`)+ 5 office 组件 spec + Decisions Log paradigm pivot 记录(从 engineer-view DAG 切到 user-view 办公室)+ 工位坐标 + AgentCharacter SVG state class。globals.css :root + .dark 各 7 office tokens 落地(修一个 D4 silent CSS fallback bug:之前 `--seat-N` 全是浏览器 fallback default 色)。
- **frontend types/api.ts**:SSE 事件 schema mirror backend Pydantic models(`SSEProgressData` / `SSEChunkData` / `SSECancelledData`),`RunStatus` 增加 `'cancelled'` enum(同步 backend DB 已有的状态字符串)。
- **plan v3.2 doc 锁定**(970 lines)— 三角评审 12 修订(eng + design + Codex outside)+ Task 6.5 spike DagNode `r=undefined` fix + Epic 0-7 完整 Day-1 到 D6 拆解 + §11 R1-R12 风险登记。

### Fixed

ship 前 codex review(Epic 7.6)+ ship 中 pre-landing/adversarial review 抓出 + 修的 8 个 finding:

- **P1 demo run_id mismatch**(codex Epic 7.6):RunPage `isDemoRun` bypass 调 `playFakeSSE` 不传 runId,fakeSSEPlayer 默认从 SAMPLE_EVENTS 取 `run_fake01`,store.runId 永远 ≠ `run_demo01` → guard 失效 → 每次 store update 再 trigger 新 player → demo bullet-proof dead loop。修法:`PlayFakeSSEOptions` 加 `runId` override + `startRun(effectiveRunId)` + start event run_id 改写。
- **P1 replay infinite loop**(codex Epic 7.6):`liveAlreadyHere` 只接受 `running`/`done`,replay 终态 `failed`/`insufficient_evidence`/`degraded`/`cancelled` 都不算 attached → 又 trigger `sse.start` → 循环 hammer `/stream/:id`。修法:`storeStatus !== 'idle'` 取代 enum 列举(枚举防御 "exclude bad" 不是 "include good")。
- **P1 ReportSheet 数据源**(codex Epic 7.6):writer node finalize 时 emit progress/node summaries 但不 emit chunks(real LLM 走 `structured_call` 非 `stream_chat`),trace replay 同样无 chunks → ReportSheet `writerReport` 永远空 → 显示 "等待 writer agent 输出…"。修法:`fetchReport` 用 `jsonFetch` 解 JSON(原 `r.text()` silent bug)+ ReportSheet `useEffect` fallback fetch `/report/:id` 取持久 markdown。
- **P2 CancelButton state stale**(codex Epic 7.6):`sse.stop()` 在 server `cancelled` event 之前 abort,store status 永远卡 `running`,RunSummary / 动画 / reattach 全 stale 直到刷新。修法:`runStore.cancelRun` action + CancelButton `finally` 调 `cancelStoreRun()` 同步切 `status='cancelled'`。
- **post-ship review:cancel-finalize race**(critical 9/10):`finalize_node` 用非 CAS `update_run_status` 覆盖 `mark_run_cancelled` CAS 已写的 `cancelled` 状态(narrow 50ms window:cancel 恰好在 finalize sync 执行内到达,task.cancel 不能 preempt sync code)。镜像 `mark_run_failed` round-2 CAS pattern,新增 `mark_run_finalized(conn, run_id, status)` CAS 守 `expected='running'`。新增 `test_mark_run_finalized_CAS_guards_cancel_race` 测试。
- **post-ship review:demo fixture `ai_features` 维度不在 backend 词汇表**:5 秒评委可见 — 3 中文维度 + 1 英文 raw `ai_features`(因 `DIMENSION_LABELS` 没条目降级显示 key)。修法:swap → `target_users`(在 `CONTROLLED_DIMENSIONS` 内)。
- **post-ship review:DagDrawer 404 on demo run**:`fetchTrace('run_demo01')` backend 无此 run → 红字 "加载失败"。修法:加 `isDemoRun` bypass 早返空 trace 显示 "该节点暂无 trace 数据"。
- **post-ship review:StatusBadge 'cancelled' raw 英文**:跟旁边中文 "降级" 视觉断层。修法:`STATUS_LABEL` map 加 6 个中文 label + tone class 'cancelled' 分支。
- **post-ship review:CancelButton demo path 多余 backend POST**:demo fixture 是纯前端 replay,backend 不知道这个 run_id。`isDemoRun` 早返 `cancelStoreRun()` 跳过 POST + sse.stop。
- **D19 spike 7 个 fix**(全 user spike-driven product feedback,~16 min CC total):agent `'running'` state 缺失 + nodeStartTs key silent bug(用 agent_id 不是 NodeName)/ progress event 清空 typing buffer 防 chunks 覆盖 done summary / character 圆 56px 防中文 3 字 "收集员" 等被裁切 / 已工作/用时 elapsed badge(running tick / done 静态)/ fakeSSEPlayer 真节奏(SAMPLE_EVENTS ts 相对间隔)+ 3 速度 preset / fakeSSEPlayer rebase event ts 到 wall clock(防 useElapsed 算 Date.now() - 历史 ts 永远 0s)。
- **silent CSS fallback**:globals.css :root + .dark 漏 office tokens 导致 `var(--seat-N)` 全浏览器 fallback default 色(D4 round-1 修)。
- **typingStore.clear race**:`pending[agent_id] = []` 同步清 pending buffer(防 progress event clear 后 throttle 又 flush 旧 pending 内容)。
- **SpeechBubble selector infinite loop**:zustand selector 内 `|| []` fallback 返新引用绕 reference equality → React useSyncExternalStore 死循环。修法:selector 返 raw + render body narrow with module-level 稳定常量。

### Engineering

- 35 backend test files / 214 tests / 8.0s / 0 regression。
- frontend tsc silent / bundle 148 KB gzip / lighthouse 100/100 realistic。
- 11 commits 本次 ship round + 2 post-review commits + 1 VERSION/CHANGELOG commit。

## [0.1.0.0] - 2026-05-26

首次完整发布:RivalRadar AI 多 Agent 竞品分析系统(4 个 Agent:采集 / 分析 / 撰写 / 质检),FastAPI + SSE 后端 + LangGraph 真闭环图编排。

### Added

- **Lane A 地基**:`pyproject.toml` + 配置层 + Pydantic 知识 Schema(`Evidence`、`CompetitorAnalysis`、`QCResult`)+ Doubao schema `$ref` 内联(`to_doubao_schema`)+ `structured_call` 包装器(validate-retry + 显式 error,Spike A 后切 function-calling/tools 路径,目标 EP `${DOUBAO_MODEL}` 不支持 `response_format`)。
- **Lane B 存储**:SQLite 5 表 schema(`runs / evidence / analysis / report / trace`)+ `annotations` 表(§11.6 标记质疑桩)+ `repository` CRUD + LangGraph `SqliteSaver` checkpointer 工厂。
- **Lane C-1 搜索 + 采集基础**:`SearchProvider` 协议 + `TavilyProvider` + `ExaProvider` + `FallbackSearch`(主→兜底失效切换)+ 源策略(`RED_DENYLIST` + `robots.txt` 诚实 UA)+ `safe_fetch` + 按域名速率限制 + 维度 × 语言查询模板 + 稳定 evidence id + 并行 `collect()` 管线 + `DATA_SOURCES.md` 合规声明。
- **Lane C-2a 采集 + 分析 Agent**:`clean_text` + 来源优先级排序 + 按维度结构化抽取(`features / pricing / personas / swot`)+ 类型化对比矩阵 + `analyze()` 入口。
- **Lane C-2b 撰写 + 质检 Agent**:确定性 Markdown 渲染(refs / competitor / comparison / sources / body)+ LLM 导语生成(grounded)+ QC 确定性闸(`check_traceability / check_ontology / check_coverage`)+ LLM 蕴含检查(`check_entailment`)+ verdict 决策。
- **Lane D 多 Agent 编排(35% 评分命门)**:LangGraph `StateGraph`(`collect / analyze / write / qc / finalize` 节点)+ 5 分支路由(`decide_route`)+ `extract_collect_targets` 含 `*` 全竞品 fan-out + ★★★ 真闭环回归测试(improve→pass + exhaust→insufficient)+ Spike F 真打 Doubao 端到端跑通。
- **Lane E 后端 API + SSE(25% 工程可观测)**:FastAPI + sse-starlette 9 端点(`POST /run` · `GET /runs` · `/run/:id` · `/stream/:run` · `/evidence/:id` · `/analysis/:run` · `/report/:run` · `/trace/:run` · `POST /annotations`)+ 同步流式 `POST /run` 用 `EventSourceResponse` + `ping=15` 保活 + 5 类 SSE event(`start / node / error / done / trace`)+ live + replay 两路同 `summary` 嵌套形状(Lane F 单解析路径)+ WAL 模式 + 每请求一条 DB conn(写写并发测试通过)+ Spike G 真打 Doubao + Tavily 端到端 SSE 跑通。
- **`state.degraded` 持久化**:`runs.degraded` 列 + 老 db 自适应 `ALTER` 迁移 + `finalize` 节点持久化 + `GET /run/:id` + `GET /runs` 同时暴露(前端 §11.5 警示横幅依赖)。
- **首版 ship audit 测试增量**:174 → 198 个测试(+24)。覆盖率 94%(58/62 路径)。

### Fixed

ship 前 review army(6 specialist subagent + Claude adversarial opus + Codex)发现并修复的 critical/security:

- **SSE error event sanitize**(KEY 纪律 hard rule):`error` event 只暴露 `type(e).__name__`,绝不透传 `str(e)` 给客户端 — OpenAI / Tavily SDK 的 `APIStatusError` 的 `str()` 可能含 `Authorization: Bearer <key>` header(Codex 实测 + FastAPI 官方 `handling-errors` 明确建议)。同样修复 `qc` trace、`FallbackSearch` 异常列表。server log 用 `logger.exception` 留完整 traceback 给运维。
- **graph crash zombie run 修复**:`SSE` 主流的 `except Exception` 分支现在调 `repo.update_run_status(run_id, "failed")`,防 Tavily 429 / Doubao 限流让 run 永久卡在 `running` 状态。SSE `done` event 也补 `status` 字段(与 replay 路径对称,前端 onDone 一次取终态)。
- **`degraded` 跨轮 sticky OR 累积**:`qc` 节点 round 1 蕴含降级 + round 2 成功 → 终态 `degraded=True`(而非被 round 2 覆盖为 False)。否则前端 §11.5 警示横幅消失、对用户隐瞒"曾发生过降级"的事实。
- **`evidence` PRIMARY KEY collision 修复**(Codex 实测复现):`evidence.id` 由 `competitor|dim|url` 派生,旧 schema 单列 PK 让重跑同 URL 触 `IntegrityError` 崩 SSE 流。新 schema 复合 PK `(run_id, id)` 让不同 run 各持一份证据副本;`INSERT OR IGNORE` 双保险防同 run 重插。
- **`RunSummary` 缺 `degraded` 字段修复**:Lane E 收口时只把 `degraded` 加到 `RunDetail`,FastAPI `response_model=list[RunSummary]` 把字段静默剥除 — `GET /runs` 列表降级横幅完全失效。现在 `RunSummary` 直接持有,`RunDetail` 继承。
- **`RunRequest` 上限保护**:`competitors` ≤ 5 + `dimensions` ≤ 6 + 每项字符串 1-200 字符(`Annotated[str, StringConstraints]`)。防恶意/误用打爆 LLM + 搜索 API 配额(KEY 纪律间接面)。
- **`main.py` 默认绑 `127.0.0.1`**:从 `0.0.0.0` 改默认 localhost,opt-in 跨主机访问设 `RIVALRADAR_HOST=0.0.0.0`。防同 LAN 用户烧 API key budget。
- **`POST /annotations` 加 `run_id` 存在校验**:不存在的 `run_id` 返 404,防孤儿 annotation 污染 §17 人工质疑率统计。
- **`qc` 节点蕴含异常消息截断**:`type(e).__name__` 入 trace,避免 4KB+ Doubao error body 污染 `GET /trace/:run` 响应。

### Notes

- 17 个 Lane D + Lane E commits + 7 个 ship audit commits(2 commit `.gitignore` + coverage tests / round-1 fix / round-2 fix / VERSION+CHANGELOG)= 项目主体首次完整 PR。
- 评分轴:35% 多 Agent 可信(Lane D ★★★ + Spike F 真打)+ 25% 工程可观测(Lane E + Spike G 真打)双双兑现。
- 仍有非阻断遗留入 `TODOS.md`(主要是 Day-4 部署 / 投产硬化 / 维护性 polish),详见该文件。

[0.1.0.0]: https://github.com/Billkst/RivalRadar/releases/tag/v0.1.0.0
