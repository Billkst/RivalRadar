# Changelog

All notable changes to RivalRadar are documented here per [Keep a Changelog](https://keepachangelog.com/) conventions.

Versioning follows 4-digit semver `MAJOR.MINOR.PATCH.MICRO`(< 1.0 表 API 未稳定,迭代期允许 breaking changes)。

## [0.6.1.0] - 2026-06-10

**Supabase Postgres 持久化迁移**。后端存储层从「仅 SQLite」扩展为「SQLite + Postgres 双方言」:设 `DATABASE_URL=postgres://`(如 Supabase)即切到托管 Postgres 持久化,云端容器重启不丢数据;不设则零行为变化走本地 SQLite。SQLite 路径 402 pytest 全绿 + 真 Supabase 9 段 CRUD 冒烟全 PASS;ship 前 Claude + Codex 跨模型对抗评审收口 1 个 HIGH(PG 事务污染)+ 3 个 INFORMATIONAL。

### Added

- **Postgres 方言支持**(`rivalradar/storage/db.py`)— `PG_SCHEMA`(AUTOINCREMENT→BIGSERIAL、runs 内联全列)+ `_PgConnection` 薄封装(`?`→`%s` 占位符翻译、execute/executemany/commit/rollback/close、`dialect="pg"`)+ `connect()` 按 `DATABASE_URL` 分流(psycopg3 懒加载、dict_row、prepare_threshold=None 兼容 pgBouncer)+ `init_db()` PG 分支逐条建表。无 `DATABASE_URL` → 原 SQLite 路径,行为零变化。
- **PG 端到端冒烟脚本**(`spikes/spike_supabase_crud.py`)— 9 段真打 Supabase:连接/建表、runs CRUD、evidence 去重+排序、5×save_* upsert 覆盖、trace/queries/curation_drops、agent_skills、annotations RETURNING、delete_run 级联、事务污染恢复;首尾自清理不污染库。
- **`_RUN_SCOPED_TABLES` 完整性测试**(`tests/test_db.py`)— 把 `delete_run` 的人肉表清单变成机器不变量:schema 里每张带 run_id 的表都必须被覆盖,漏加即红(防孤儿行)。

### Changed

- **SQL 方言统一**(`rivalradar/storage/repository.py`)— 6 处 SQLite 私有 upsert(`INSERT OR IGNORE`/`OR REPLACE`)改标准 `ON CONFLICT … DO NOTHING/UPDATE`(SQLite≥3.24 与 PG 一套 SQL 通吃);`list_evidence` 排序、`insert_annotation` 取主键按方言分叉;`list_agent_skills` 位置访问改列名(dict_row 兼容);`delete_run` 用显式 `_RUN_SCOPED_TABLES` 取代 `sqlite_master`/`PRAGMA` 自省(PG 无此接口)。
- **依赖**(`pyproject.toml`)— 加 `psycopg[binary]>=3.1`(仅 Postgres 部署懒加载;本地 SQLite 不导入)。

### Fixed

- **PG 事务污染防 run 卡死**(`rivalradar/storage/db.py`;ship 前 Claude+Codex 跨模型一致 HIGH)— PG `autocommit=False` 下一条写失败会 abort 整条长生命周期事务,此后所有语句(含 `mark_run_failed`)报 `InFailedSqlTransaction` → run 永久卡 running(SQLite 不会)。修:`_PgConnection.execute/executemany` 失败即 `rollback()` 再抛(每写紧跟 commit = 单语句事务,rollback 只丢失败那条,并保 `delete_run`/`replace_curation_drops` 多语句原子性)。真 Supabase 故意造写失败验证恢复。
- **连接泄漏防护**(`rivalradar/api/deps.py`)— `init_db` 移进 `try/finally`,PG 上 init 失败也关连接,防 Supabase pooler 连接耗尽。

## [0.6.0.0] - 2026-06-09

**过程可视化重做(Plan A–D)+ 实时引擎 + 三级佐证策展 + replay 富回放**。把"调研过程"从黑盒做成用户可见的实时剧场:采集→分析→撰写→质检每步的中间产物逐条流式呈现;证据支持度做成 cell/决策级三色(充分/部分/已剔除),质检从"一票否决法官"翻成"策展人";`/stream` 回放从持久化状态重建完整过程事件。401 pytest 绿 + `tsc -b` + build 绿;ship 前 4 路 + Codex 跨模型对抗评审收口 3 个 finding。

### Added

- **实时引擎「此刻」追踪卡**(`frontend/.../workbench/LiveTracker.tsx`)— 钉在右栏顶部常驻、原地刷新(不依赖滚动):采集显最新检索词 + 命中来源逐条"播放";分析显对比矩阵 N/total 维进度条 + 抽取工作日志 feed;撰写显报告打字 tail + TTFB 脉冲骨架;质检显逐格校验流 + 三色汇总;含 decide 决策合成阶段计时(治长阶段冻结)。
- **研究员工作台**(`frontend/.../workbench/`)— ResearcherWorkbench 外壳 + 正序执行时间轴(绝对时刻 + 角色 + → 效果)+ 来源卡(真标题/域名/日期 + 陈旧标记 + 三色)+ 重试环动画 + agent 工牌(工号/状态灯/retry)+ 抽屉式证据/步骤/技能导览(navStack + focus trap a11y)。
- **三级佐证体系**(`rivalradar/`)— cell/决策级 `support_verdict`(充分/部分/不支撑);质检 `_judge_comparison_verdicts` 逐格裁决;`curate_analysis` 写回三色、丢弃不支撑格(策展人模型);`curation_drops` 表 + REST `/runs/:id/curation-drops` 结构化记录被丢格。
- **真检索词 + 富过程事件**(`rivalradar/`)— `queries` 表 + collect_node emit query/query_hit/source/evidence_delta;analyze emit cell_row 逐维;两步式 insight 流式起草(stream draft → structured,回退完整)。
- **replay 富回放**(`rivalradar/api/sse.py`)— `/stream` 从持久化 trace/evidence 重建过程事件(检索台/来源/矩阵/重试环),刷新/深链进历史 run 不丢"看得见的活儿"。
- **演示模式 fakeSSEPlayer**(`frontend/`)— 无后端可放完整过程剧场(Plan D 全平价),供 `/browse` 与离线演示。
- **StatusBar 计时器**(`frontend/.../cockpit/StatusBar.tsx`)— running 实时走表、终态显总耗时。

### Changed

- **质检信任模型翻转**(`rivalradar/agents/qc.py`)— 从"一票否决法官"(一弱格否决整 run → 假降级)→"策展人"(站得住留、站不住丢、缺的显「—」+ 覆盖说明);防虚构硬门不变。
- **降级判别收窄**(`rivalradar/graph/nodes.py`)— 仅"影响用户可见产出(对比矩阵 cell)"的降级才置 run 级 degraded;profile 辅助项(功能/定价/画像/SWOT)抽取失败只折进 trace、不污染整 run(真 run 钓出:一个 SWOT 截断曾误标满矩阵健康 run 降级)。
- **分析员对比 claim 收紧**(`rivalradar/agents/analyst.py`)— 新增对比纪律 `_COMPARE_RULE`:每格围绕单一产品/版本线写可比核心事实、禁跨产品口径混写、禁派生营销数字 → 真 run partial 50%→0(治"全部分佐证 + 空格");质检 entailment 闸一字未动。

### Fixed

- **replay 多轮 round 退化**(`frontend/.../workbench/ExecutionTimeline.tsx`)— evidence 表无 round 列致 replay source.round 全为 0,加 `roundsReliable` 判定:多采集轮却单一 round 时聚合显「共 N 来源」不谎报「本轮」。
- **replay 总耗时错误**(`frontend/.../stores/runStore.ts`)— replay 的 start/done 都是服务端 `_now()` → runStartTs 置 null,终态不显错误回放时长(ship 评审 Codex 抓)。
- **降级横幅文案误导**(`frontend/.../cockpit/DecisionSurface.tsx`)— degraded 可能来自决策溯源失败,文案不再写死"矩阵缺维"(ship 评审 Codex 抓)。
- 反幻觉清理(无 proto-tags、来源链真实)、a11y(focus order / 色盲双编码 / 对比度 / 44px / reduced-motion)、工作台全状态覆盖(loading / failed / cancelled / done)。

## [0.5.0.0] - 2026-06-06

**post-real-run-7 硬化 + 范文库 + analyze 卡死根治**。真 run 暴露 analyze 卡死无法完成,实证定位并根治时延 / 取消 / 墙钟 / 精准重跑;新增他人专业竞品分析范文库(原文配图 + 杂志排版 + PDF 在线阅览 + 北京时间全量);ship-time 跨模型(Claude + Codex)对抗评审收口 3 个 finding。350 pytest 绿 + `tsc -b` 绿。

### Added

- **竞品分析范文库**(`frontend/` + `public/samples/`)— 收录他人专业竞品分析报告(标明出处),含去原文(woshipm/36kr)抓回的配图、杂志式阅读排版 + 左侧粘性 TOC(scroll-spy)、PDF 在线 iframe 阅览(不止下载)。
- **协作式取消 + 全局墙钟**(`rivalradar/llm/runcontrol.py`)— `RunControl`(threading.Event + deadline)+ 包装 client 每次 LLM 调用前 `check()`:取消真能停掉 worker 线程在飞的 LLM(不再空磨整轮);每 run 默认 900s 墙钟预算(env `RIVALRADAR_RUN_BUDGET_S`)兜底卡死。
- **markdown 表格渲染**(`frontend/.../Markdown.tsx`)— `/report` 跨竞品对比表(核心交付物)正常渲染(此前散成段落,Codex 评审揪出)。
- **dev 启停脚本**(`scripts/`)— `dev-backend` / `dev-frontend` / `stop-dev`,内置 WSL2 Clash 代理兜底,改后端代码后一键重启。

### Changed

- **实时进度桥**(`rivalradar/api/sse.py`)— `emit` 改 `loop.call_soon_threadsafe`,worker 线程进度事件实时送达(此前憋到节点结束才到;实测延迟 101s→0s,等待不再像死机)。
- **对比阶段并发**(`rivalradar/agents/analyst.py`)— 对比池 4→8(6 维一波跑完不再分 2 波翻倍)+ per-dimension 进度逐维点亮;实测 analyze 161s→59s(小 run)。
- **坏维度精准重跑**(`rivalradar/graph/nodes.py`)— `retry_analyze` 时复用上轮竞品画像、只重对比矩阵(省 N×4 抽取),上轮 analysis 反序列化失败回退完整 analyze。
- **北京时间全量**(`frontend/`)— 时间显示统一 `Asia/Shanghai`(此前 7 处裸切 UTC)。
- **cockpit UX 打磨**(`frontend/`)— 报告导出/删除、StatusBar 绿点重设计、设计哲学、双滚动条。
- **取消 / 删除 API 改 async**(`rivalradar/api/runs.py`)— cancel/delete 异步化以线程安全地 `task.cancel`。

### Fixed

- **analyze 卡死无法完成**(`rivalradar/agents/analyst.py` + `graph/nodes.py` + `llm/structured.py`)— 真 run 根治:`max_retries` 5→3 缩短最坏墙钟、`PricingTier.features_included` str→list 兜底(消 Doubao 误返字符串导致的每次必重试)。
- **删除运行中 run 留孤儿**(`rivalradar/api/runs.py`)— 运行中拒删返 409(对抗审查 P1,Claude + Codex 跨模型一致):协作式取消挡不住正在写库的 worker 线程,删后会留无父 `runs` 行的孤儿数据;改为先取消再删。
- **报告 img src 信标向量**(`frontend/.../Markdown.tsx`)— `![](src)` 收紧为仅相对路径 + `data:image`,堵死 LLM 注入的外链/内网图被浏览器自动加载(referrer 泄漏 / SSRF 向量)。
- **删除失败吞整列表**(`frontend/`)— 独立 `deleteError` 行内提示,删除失败不再毁列表。

## [0.4.0.0] - 2026-05-30

**Evidence Cockpit — 从"报告生成器"跳到"决策基础设施"**。v0.4 把 RivalRadar 的输出范式从一份 markdown 报告,换成 Manus 式分屏驾驶舱:左决策面(有据决策流 + 对比矩阵 + 证据支持度三色)/ 右镜湖执行流(4 角色时间线 + 诚实自纠重试环)。配套把决策做成 LLM 产出 + QC 校验的一等公民(full-C),并把 QC 信任模型从"一票否决的法官"翻成"策展人"。真打真 run 双重验证 + ship-time 跨模型对抗评审。

### Added

- **Evidence Cockpit 驾驶舱**(`frontend/`)— `CockpitLayout` Manus 分屏(顶 StatusBar + 左决策面 / 右 `ExecutionStream`):4 角色时间线(采集员/分析员/撰写员/质检员/决策)+ **重试环青绿回环 SVG「↺ 第N轮·证据 X→Y」** money-shot;`DecisionBoard` 决策流 + 对比矩阵 + `EvidencePill` 三色支持度(supported/partial/unsupported,无虚构 confidence);DAG / 虚拟办公室双视图退役,cockpit 全宽。DESIGN.md v4 证据驾驶舱改写。
- **full-C 决策管道**(`rivalradar/schema/models.py` + `agents/decision.py` + `graph/nodes.py`)— `Decision` schema(stance/action/horizon/risk/watch validator)+ `generate_decisions` LLM 产出(不碰 `generate_insight` 守 24/30 rubric)+ QC-on-decisions 校验 + `decide` 节点(图拓扑 qc→decide→finalize,优雅降级)。真 migration(`qc_result`/`insight`/`decisions` 表 + `decision_context` 列)。
- **引导式 run setup**(`rivalradar/api/` + `frontend/`)— 种子竞品 → `discover-competitors` 自动发现 → 确认 chips → 决策处境卡片(把"我在为什么决策做调研"显式化)。
- **9 个 REST 端点 sanitized serve**(`GET /qc`/`/insight`/`/decisions`/`/run/:id`/`/evidence` 等)— `/qc` detail 罐装化(绝不回吐模型原文/越界维度名/KEY)。
- **eval 机械门**(`tests/test_evals.py`)— 可溯源 / 套话检测 / 结构锚 三类机械评分守 24/30 rubric。

### Changed

- **QC 信任模型:一票否决的法官 → 策展人**(`agents/qc.py` `curate_analysis`/`curate_decisions` + `graph/nodes.py`)— 站得住的(有据)留、站不住的(蕴含判无据)丢、缺的显「—」+ 轻量覆盖说明。防虚构硬门不变:策展后 `check_traceability(comparison_only=True)` 在 curated 输出上重跑,0 个无据结论 survive。覆盖度终态按 `_has_substantive_output` 判(有可交付产出→done,真空手才 insufficient/degraded)。
- **analyze 并行化**(`agents/analyst.py`)— 双层独立线程池(竞品间 ×4 + 单竞品 4 抽取 ×4,峰值 16),真 LLM 实测 **2.5-5× 提速**,输出零变化。
- **QC 重试空转修复 + 蕴含并行化**(`agents/qc.py`)— `check_coverage` 加 `evidence` 参数:只对**零证据**维度触发 `retry_collect`(broaden 能补且收敛),"采到了但 cell 被策展丢掉"的维度显「—」不重采(根治非确定策展导致的不收敛重试空转)。`check_entailment`/`curate_decisions` 逐项 LLM 判定改 `ThreadPoolExecutor` 并行(错误上抛契约 + cost-guard + 顺序不变)。真 run 实测同输入 3 轮 → 1 轮收敛,~490-615s → ~321s。

### Fixed

- **维度作用域 bug**(`agents/analyst.py` + `graph/nodes.py`,真 run 暴露)— analyze/check_coverage 不再硬编码全 6 维忽略用户请求维度;请求参数一路穿到所有下游消费点(289 单测全绿但真 run 必 insufficient 的根因)。
- **7 个管线真实性 bug**(真 run 钓出)+ silent-failure 降级可见性补强。
- **finalize 空-done 修复**(`graph/nodes.py`,ship-time Claude+Codex 双模型评审 MAJOR 共识)— verdict=pass 但策展后空手(每维有证据→无 coverage 缺口→pass,但所有 cell 被判不支撑全丢+无决策)不再出"看似通过实则空白"的 done,诚实改写 insufficient_evidence。

## [0.3.0.0] - 2026-05-28

**输出质量第一个 release — writer v2 + production hardening + rubric v1 评估框架**。本轮 RivalRadar 从"demo 跑通"推到"输出质量可量化"。基于 4 份中文 SaaS 竞品 reference baseline(飞书/钉钉/企业微信、文档协作赛道)倒推 10 条 × 0-3 分 rubric,真打两轮迭代:Round 1 写 18507 字真报告 = **18.5/30 Adequate 上端**,#1 市场锚定 / #7 战略推论 / #9 时间分层三块战略向失 7.5 分;改造 writer prompt v2 重跑 Round 2 写 15932 字 = **24/30 Good 中段,距 ref-01 (26/30) 仅 2 分**。同时修两个 production P0:Tavily 单 query timeout 不再 abort 整轮 + Doubao SDK 90s timeout 接住 25K-34K char input。Demo fixture 切到中国本土竞品(飞书 / 钉钉 / 企业微信)与 reference baseline 同赛道,demo 叙事与 evaluator 评分维度对齐。

### Added

- **Writer v2 — `generate_insight` 3 段执行洞察**(`rivalradar/agents/writer.py:135`)— Pydantic `ReportInsight(market_context, differentiation_thesis, actionable_takeaway)` schema-encode 3 段 strategic synthesis,取代 v1 单段 `ReportSummary` 事实概括。Prompt 显式负 example("严禁持续关注/深入研究/保持观察 套话")+ 「因为 X 所以 Y」推论链强制 + 短/中/长期 actionable 三时间桶。Body 仍 deterministic Python 模板保 100% 引用完整性,insight 显式标"AI 基于正文综合判断"评委可分辨 fact vs judgment。
- **Rubric v1 + 4 份中文 reference baseline**(`references/`)— 10 条 × 0-3 分 = 30 满分,分 A 组(5 条结构覆盖)+ B 组(5 条质量洞察);等级阈值 Excellent(25-30) / Good(20-24) / Adequate(15-19) / Weak(10-14) / Fail(<10)。Reference:`ref-01` 人人都是产品经理(飞书+钉钉+企微,26/30) / `ref-02` 36氪(钉钉vs飞书 5 年战略,25/30) / `ref-03` 人人都是产品经理(石墨+腾讯+金山,24/30) / `ref-04` 艾瑞 2024 协同办公 38 页 PDF(28/30,厂商权威)。每份 YAML frontmatter 记 source_url / author / fetched_at / quality_score。
- **RivalRadar 真打 evidence**(`references/rivalradar-output/`)— Round 1 `run-001-feishu-dingding/`(writer v1 baseline 18.5/30 + report.md 18507 字 + analysis.json + report-raw.json + trace.json)+ Round 2 `run-002-writer-v2/`(writer prompt v2 24/30 + report.md 15932 字 + analysis.json + report-raw.json)。配 `references/README.md` 自解释 rubric 评分 + iteration learning + 新 run 评估流程。
- **Pipeline graceful skip**(`rivalradar/collect/pipeline.py`)— `_run_query_safe` wrap `_run_query` 加 try/except + warning 日志 + 返 [],单 query 失败(Tavily 60s timeout / provider 全挂 / 网络抖)不再 `AllProvidersFailedError` abort 整轮采集。末尾 info 日志统计 failed_count / total queries,QC 自然识别 coverage 不足触发 retry_collect 或 insufficient_evidence。
- **`structured_call` SDK timeout=90s + 网络异常 retry**(`rivalradar/llm/structured.py`)— Doubao SDK 之前没 timeout(default 600s/无限),Clash fake-ip 偶发慢路径单 call hang 14 min(实测踩过)。`_DEFAULT_REQUEST_TIMEOUT = 90.0` calibrated:ping 4-5s(欺骗性)/ mock realistic 24s / production 25K-34K char input 35-70s / 60s 仍卡边缘 / 90s = 70s × 1.3x headroom + Clash 抖动 +20s。`APITimeoutError / APIConnectionError / APIError` 入 retry 循环,封顶后 `StructuredCallError` 让上层降级,绝不静默吞。
- **Demo fixture 切中国本土竞品**(`frontend/src/lib/demoFixture.ts` + `frontend/src/dev/fakeSSEPlayer.ts` + `frontend/src/pages/RunsPage.tsx`)— `DEMO_RUN_DETAIL.competitors` 从 `[Notion, Coda, Airtable]` 改 `[飞书, 钉钉, 企业微信]`;SAMPLE_EVENTS analyst chunk delta `Notion 和 Coda` → `飞书 和 钉钉` + writer chunk delta `Notion 在` → `飞书 在`;RunsPage input placeholder 同步对齐。Demo 叙事与 reference + 真打 evidence 同赛道。
- **测试覆盖**:218 pass(从 v0.2.0.0 214 +4 新)— `test_collect_graceful_skip_on_single_query_failure`(_PartialFailProvider mock + caplog 验 warning 日志)+ `test_passes_timeout_to_sdk_call`(timeout kwarg ∈ [30, 180])+ `test_recovers_from_transient_timeout_then_succeeds`(1 失败 + 1 成功)+ `test_raises_after_all_retries_exhausted_by_network_errors`(全 timeout → StructuredCallError 含 "timed out")+ `test_generate_insight_returns_three_fields`(Pydantic 3 字段 round-trip)+ `test_write_report_combines_insight_and_deterministic_body`(3 段 section + body 引用 + as_of)。

### Changed

- **Writer 报告结构**:`# 竞品分析报告` 顶部 `## 执行洞察(AI 基于下方正文综合)` 3 段 markdown — 市场格局 + 战略路径分歧 + 给企业产品团队的 takeaway(短/中/长期)— 替代 v1 `## 摘要(AI 生成,仅概括下方结论)`。Body 完全不动,引用完整性 100% 保留,#4 信息溯源 3/3 满分不退。
- **`generate_summary` → `generate_insight`**(API rename,v0.2.x → v0.3.0)。旧函数完全移除,`structured_call` 调用从 `ReportSummary` 改 `ReportInsight`。

### Iteration learning(本轮验证)

1. **Schema-encoded prompt > 自然语言 prompt** — Pydantic 3 字段强制比 prompt 里说"请分 3 段"可靠 5×。
2. **Negative example 比 positive 强** — "严禁持续关注/深入研究/保持观察"直接生效。
3. **Hybrid Python+LLM 架构是产品级输出标准** — Python 模板保 100% 引用完整性,LLM 担 strategic synthesis 显式标"AI 综合判断"。
4. **Doubao SDK timeout 必须基于 production payload 测** — ping vs mock vs production 是三个尺度,凭直觉算 5× 系数会踩。
5. **Pipeline graceful skip 是 production 必须** — 外部 API 在 thread pool 内必须 safe-wrap,Tavily/Doubao/Exa 任一抖动都不该 abort。

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
