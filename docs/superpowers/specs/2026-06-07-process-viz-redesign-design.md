# RivalRadar「调研进行时」过程可视化重设计 — 设计文档(spec)

> 日期:2026-06-07 · 分支:main · 阶段:brainstorming 产出的设计文档,下一步交 writing-plans 拆实现计划。
> 关系:本版是 **DESIGN.md v4 证据驾驶舱 → v5 的增量演进**,不是推翻重来。v4 的 paradigm(左决策+证据 / 右执行流)被保留并深化;新增 = 右栏升级为「看得见真实活儿的研究员工作台」+ agent 人格/工牌/技能子系统 + **反幻觉真收口** + 全量真实活儿 emit。

---

## 1. 背景与目标

### 1.1 问题
RivalRadar 是 AI 多 agent 竞品分析系统(采集员/分析员/撰写员/质检员)。用户判定:**「报告生成过程」的可视化太差**(不是报告产物可视化)。标杆是 **Kimi 深度研究 / OK Computer** —— 让用户看见机器在真实地干活。

### 1.2 四个目标(用户确认,验收锚点)
1. **看得见真实的活儿** —— 真实查询词、真实来源卡、逐格证据依据,不是状态计数。
2. **计划/大纲边做边勾** —— 研究计划随进度逐步勾选。
3. **产物边生成边长出** —— 决策/矩阵/报告随分析推进逐步生长。
4. **「一队研究员在干活」的叙事感** —— agent 作为可见的持证专家,有身份、有工牌、有技能。

### 1.3 与 v4 的关系
v4「证据驾驶舱」已经是同源 paradigm(`DESIGN.md` §Layout:左决策面 ~62% / 右实时分析流程 ~38%)。本版在它之上:
- 右栏从「等宽时间线日志」升级为**研究员工作台**(检索台/来源卡/逐格依据/重试环 + 计划勾选)。
- 新增 agent **人格层**(头像/工牌/可点查看)与**技能子系统**(可装删/版本/状态)。
- 把 v4 钦定但**后端从未实现**的 `support_verdict` 三色信任信号**真正算出来**(反幻觉收口)。
- 把 Kimi「真实活儿」所需的数据**真正 emit** 出来。

### 1.4 范围决策(已拍板,本 spec 的形状由此固定)

| 决策 | 选择 | 含义 |
|------|------|------|
| **D2 support_verdict** | **真算三级并回写** | 升级 QC entailment 为三级判定,回写每个 cell/决策的 support_verdict;真 run 也出真三色。真算后**移除所有「原型态·待后端实现」角标**(它们当初只为掩护假数据)。 |
| **D3 技能子系统** | **框架真·行为接入后续** | UI 可装/删/开关 + 版本 + 状态 + 持久化;但「装 skill 改 agent prompt 行为」留**二期**,本期诚实标注。 |
| **D4 首期范围** | **一次性全量真实化** | 数据/过程层全做真(下方后端 6 区)。**唯一例外**:技能行为接入(D3 已单独裁成二期)。 |

> **D3/D4 reconcile(写死)**:全量真实化 = 数据/过程层全做真;技能子系统按 D3 = 框架真、行为接入后续。两条不冲突 —— 「技能改 prompt」是独立大工程,不在本期。

### 1.5 明确不做(反幻觉边界,本期与未来都不做,除非推翻设计)
- **不复活** `provider` 字段(哪个搜索引擎)、数字 `confidence %` —— v4 已主动删,复活=违反 DESIGN.md(`evidence.py:15-33` 不拷贝、`db.py` 无列)。
- **不做** sentiment 量化打分(`review_sentiment` 只是搜索维度名,`models.py:22`)。
- **不做** 多源交叉验证、实时监控/趋势(后端零此逻辑)。
- 技能装删**本期不改变** agent 真实产出(D3)。

---

## 2. 关键真相(地基,均带 `文件:行号`)

> 这一节是反幻觉的根:spec 的每个后端改造点都建立在「代码里确实有什么」之上,不是凭记忆。

### 2.1 架构真相:SSE 发信号 + REST 拉产物
真 run 数据流 = **节点完成 → `save_*` 落库 → SSE 发轻量计数事件 → 前端按事件去 REST 拉完整产物**。
- SSE `node` event 的 summary 全是计数(`sse.py:60-99`:collect 只发 `evidence_added` 条数、analyze 只发 `competitors/comparison_rows` 数量、write 只发 `report_chars`)。
- 前端 `cockpitStore.ts:114-163` 渐进 fetch:analyze 完成拉 analysis,done 拉 qc/insight/decisions/evidence-list。
- **结论**:要让前端「看得见真实活儿」,要么把明细塞进 SSE 事件,要么 SSE 发信号触发前端 REST 拉明细。本 spec 两者并用(见 §5)。

### 2.2 `support_verdict` 三色是幻觉(铁证)
- `EvidenceRef.support_verdict: SupportVerdict = "supported"` 默认 supported(`schema/models.py:46`)。
- **没有任何 prompt 教 LLM 怎么判**它(`analyst.py:107-116` 的 `_REFS_RULE` 只讲挂 evidence_id+quote)→ 真 run 几乎恒为 supported。
- QC 的 `check_entailment` 算的是 `EntailmentVerdict{supported: bool}`(`qc.py:148-200`),用于 `curate_analysis` **丢弃**站不住的 cell(`qc.py:208-245`),**不回写** support_verdict。两者正交。
- `partial/unsupported` 真值只在 `frontend/src/lib/demoFixture.ts` 与测试里手写。
- 前端却把它当「唯一信任信号」三色大用:矩阵格三色点 + 头部聚合(`CompetitorComparison.tsx:36-47,158-173`)、StatusBar 全局三色(`DESIGN.md:150`)、EvidencePill/DecisionBoard 依据行(`EvidencePill.tsx:39`、`DecisionBoard.tsx:37,44,67`)、聚合逻辑 `lib/verdict.ts:31-46`。

### 2.3 Kimi「真实活儿」数据三类
- **A 已存/已算、只是没 emit(低成本接通)**:
  - 真实查询词:`Query{competitor,dimension,language,query_text}`(`collect/queries.py:22-27`)由模板生成(`queries.py:36-53`),实际发给 provider(`collect/pipeline.py:16`),但**连 db 都没存**,只活在 collect 调用栈。
  - 来源卡明细:`Evidence{content,source_url,source_title,language,fetched_at}`(`schema/models.py:26-36`)**完整落库**(`storage/repository.py:134-144`、`db.py:14-27`),有 REST 端点(`api/reads.py:82-89`),SSE 只发条数。
  - 逐格 cell:`ComparisonCell{competitor,value_type,value,evidence_refs}`(`models.py:114-120`),每 cell 有 `evidence_refs`,**完整落库**,但 analyze **一次性 save**(`graph/nodes.py:194`),逐格「边算边出」要改造。
  - retry 增量:collect 节点手里有 `fresh` 列表(`graph/nodes.py:129`),可低成本 emit。
- **B 根本没有、要新增**:真 support_verdict 三级(§2.2)。
- **死能力**:`chunk` 逐字打字流 —— `stream_chat`(`llm/streaming.py:23-84`)能 emit chunk、schema 有(`api/schemas.py:128-139`)、前端全接了(typingStore/`runStore.ts:190-196` 累积 writerReport),**但生产链路从无节点调用 `stream_chat`**(唯一 caller 是 `tests/test_streaming.py`);真实 LLM 全走 `structured_call` 的 function-calling 一次性返回(`llm/structured.py:97-100`)。

### 2.4 前端已有可复用基建(不重建)
- 布局/组件:`CockpitLayout`(双栏响应式)、`StatusBar`、`DecisionSurface`+`DecisionBoard`、`CompetitorComparison`、`ContradictionPanel`、`SelfAuditTrace`、`EvidenceTimeline`、`ExecutionStream`、`EvidenceSlideOver`、`EvidencePill`、`VerdictDot`。
- 状态:`runStore.ts`(SSE 状态机,`handleEvent` reducer)+ `cockpitStore.ts`(渐进 fetch,LoadState 机)+ `evidenceStore.ts`(LRU 50)。
- SSE:`useSSE.ts` module-level AbortController + 双路径(live `POST /run` / replay `GET /stream/:id`)。
- demo:`demoFixture.ts` + `dev/fakeSSEPlayer.ts`(零网络/零 key)。
- 状态覆盖:loading/empty/error/done/degraded/insufficient/failed/cancelled **已全覆盖**(各面板有专属 skeleton/EmptyNote/ErrorNote)。
- 类型:`types/api.ts` 镜像后端 Pydantic,`SupportVerdict='supported'|'partial'|'unsupported'` 已定义。
- 构建/测试:`pnpm build` = `tsc -b && vite build`;`pnpm typecheck` = `tsc -b --noEmit`;**前端无 Vitest**(`test` 是占位)→ 验证靠 build + `/browse`。

---

## 3. Paradigm 与定位(承 v4,收口一处张力)

### 3.1 融合主轴(承 v4 + 2e 认可)
跑动时**同屏共存**:
- **左决策面**(主):研究计划 rail + 对比矩阵 + 决策建议 + 哪里可能错 —— 边分析边生长(目标 ③④)。
- **右研究员工作台**(可见引擎):roster 工牌 + 检索台(真实查询词逐字)+ 来源卡 + 逐格依据 + 执行时间轴 + 重试环 + 计划勾选(目标 ①②④)。

### 3.2 一处必须收口的张力:agent 人格 vs v4 废弃的「虚拟办公室」
v4 当年**废弃** v3 的虚拟办公室/拟物动物(`DESIGN.md:164`,理由:工程师视角、跟 ChatGPT 没区别)。2e 的「agent=持证员工+头像+工牌」是把人格叙事**部分带回**。**spec 立场(写死)**:
- 工牌 = **机构级持证专家身份**(职能名/工号/状态灯/当前任务),像彭博终端的分析师署名,**不是**卡通动物/虚拟工位/speech bubble。
- 头像 = 克制的**插画肖像**(统一风格、低饱和身份色描边),非卡通表情。当前 lorelei 为原型级占位,终稿可换定制插画(用户:头像后续再改)。
- 严禁回退:无 office 工位坐标语义、无 speech bubble、无拟物动物、无花哨代号(沿用 `DESIGN.md:126` 命名规范:采集员/分析员/撰写员/质检员)。
- 这是被授权的演进(用户:DESIGN.md v4 可更新、新需求优先)。

### 3.3 定位不变
仍是 **decision infrastructure**(不是更精致的报告生成器)。过程可视化强化的正是 paradigm signal:看得见的真实工作 + 自我纠错(重试环)+ 自我攻击(哪里可能错)+ 证据可溯源。

---

## 4. 整体数据流(改造后)

```
真 run:
 collect 节点 ──emit query(真实查询词)──► SSE ──► runStore ──► 右栏检索台逐字显示
   │         ──emit source(新增来源卡明细)──► SSE ──► evidenceStore seed ──► 右栏来源卡
   │         ──emit evidence_delta(retry 增量)──► SSE ──► 右栏「第N轮 +M源」
 analyze 节点 ──逐维 emit cell_row(每维算完)──► SSE ──► 左栏矩阵逐维填(目标③,接受乱序)
 write 节点 ──Step1 stream_chat 草稿──► SSE chunk ──► 报告台逐字;Step2 structured_call ──► ReportInsight 落库(§5.6)
 qc 节点 ──emit verdict_recheck(三级,独立于路由)──► SSE ──► support_verdict 真三色 + 重试环
 decide 节点 ──emit 决策──► 左栏决策卡逐条生长(目标③)

计划勾选:每个 plan step 由对应 SSE 事件驱动 doing→done/reopen(目标②)
demo/replay:fakeSSEPlayer + replay trace 必须产出与真 run 同形状的新事件(平价)
```

**核心原则**:SSE 事件**信号 + 轻量明细**并用 —— 计数/状态走 SSE,重产物(全文/全矩阵)仍 REST 拉;但「过程感」所需的**增量明细**(单条查询词、单条来源卡、单个 cell、单段 chunk)直接进 SSE 事件 payload。

---

## 5. 后端改造(全量真实化 · 6 区)

> 每区:现状(`文件:行号`)→ 改造 → 新/扩展 SSE 事件契约 → 持久化 → 验收(成功+失败路径)。

### 5.1 真实查询词 emit + 持久化
- **现状**:`generate_queries`(`queries.py:36-53`)生成 `Query.query_text`,在 `collect/pipeline.py` 内逐条发给 provider(`pipeline.py:61,66`),不落库不 emit。**collect 节点只拿到最终证据列表**(`nodes.py:109`),拿不到逐条 Query 与每 query 命中数(codex [P2])。
- **改造**:
  1. **改 pipeline 回调签名**(codex [P2]:不是只在 collect 节点补几行):让 `collect/pipeline.py` 接收 emit / 扩展回调签名,发起每条 query 时 emit `query`、命中后 emit `query_hit`。
  2. 持久化:新增 `queries` 表(`run_id, competitor, dimension, language, query_text, round, hit_count, created_at`)+ repository CRUD + REST `GET /runs/{id}/queries`(供 replay/事后查看)。
- **round 推导(codex [P1] 防造假)**:第一次 retry collect 进入 collect 时 `retry_count` 仍可能为 0(首轮 qc 无 prior,`new_rc` 不加一,`nodes.py:332`),但 collect 已因 `qc_result is not None` 走 broaden(`nodes.py:100,125`)。**round 必须由 `qc_result` 存在性 + retry_count 组合推导,不能直接用 `retry_count`。**
- **新 SSE 事件** `query`:`{competitor, dimension, query_text, language, round, ts}`;`query_hit`:`{query_text, hit_count, round, ts}`。
- **验收**:真 run 右栏检索台显示真实中文/英文查询词;成功路径=查询词逐条出现+命中数;失败路径=单 query provider 抛错时 graceful skip(`_run_query_safe` 已在 `pipeline.py`,记忆:upstream 抖动是常态)且检索台标「该查询无结果」,不中断整轮。

### 5.2 来源卡明细 emit
- **现状**:Evidence 完整落库 + REST(`reads.py:82-89`),SSE 只发 `evidence_added` 条数(`sse.py:62`)。
- **改造**:collect 节点对每条新 evidence,经 emit 发 `source` 事件(轻量:不发 content 全文,发卡片所需字段)。前端拿到即渲染来源卡 + seed evidenceStore;点击仍走 REST 拉全文(`GET /evidence/{id}`)。
- **新 SSE 事件** `source`:`{evidence_id, competitor, dimension, source_title, source_url(域名+path), language, fetched_at, round, ts}`(**不含** provider/confidence,§1.5)。
- **验收**:真 run 右栏来源卡含真实标题/域名/采集日期;stale(>90 天)由前端 `freshness.ts:7-20` 从 `fetched_at` 派生(后端不算,§2.3)。

### 5.3 逐格 cell emit(改 analyze,「边算边出」)
- **现状**:analyze 一次性 `save_analysis`(`nodes.py:194`);**按维度并行**跑对比(`build_comparison` `analyst.py:223-267`,内部并行 `analyst.py:261`,完成后按请求维度恢复顺序 `analyst.py:266`;单维 `_compare_one_dimension` 是 `analyst.py:203-220`,codex [P2] 行号修正),只发中文 progress 字符串。
- **改造**:`build_comparison` 每维算完,经 emit 发 `cell_row` 事件(该维度所有竞品的 cell)。前端左栏矩阵逐维揭示(目标③:数据真·逐维到达)。
- **乱序契约(codex [P2])**:维度并行 → `cell_row` 按**完成顺序**到达,**前端必须接受乱序**(按 dimension key 落位,不假设到达顺序)。
- **失败事件契约(codex [P2])**:单维失败现只 `degraded_sink.append` + 跳过(`analyst.py:252,256`)。需在 `cell_row` 加 `status:"ok"|"failed"`(或单独 `cell_row_failed`),失败维标「分析失败」。
- **新 SSE 事件** `cell_row`:`{dimension, status, cells:[{competitor, value_type, value, evidence_refs:[{evidence_id, quote}]}], ts}`。
- **注意**:此事件 cell **不带可信 support_verdict**;**真三色在 qc 阶段回写 cell 级字段**(§5.5/§7.2),前端在 qc 完成后用 `verdict_recheck` 刷新矩阵三色。

### 5.4 retry 增量 emit
- **现状**:collect 节点有 `fresh` 列表(`nodes.py:129`);前端只从计数快照推 `evidenceCountSnapshots`(`runStore.ts:321-327`),无「本轮新增是哪几条」。
- **改造**:retry 轮的 collect 节点 emit `evidence_delta`:`{round, added_count, total_count, new_evidence_ids:[...], ts}`,并复用 §5.2 的 `source` 事件(带 `round>0`)推送本轮新来源。
- **新 SSE 事件** `evidence_delta`:如上。
- **round 同 §5.1 推导**(不能直接用 retry_count,codex [P1])。
- **验收**:重试环显示真实「第 N 轮 · 证据 X→Y」+ 本轮新来源卡;`max_retries=2`(`api/app.py:34`)不变。

### 5.5 support_verdict 真算三级 + 回写(D2,反幻觉核心 · codex [P1] 重写)
- **现状**:`EntailmentVerdict{supported: bool, reason}`(`qc.py:148-150`);`check_entailment` 把一个 cell/decision 的**全部 refs 合并判一次**,只返回 `QCIssue | None`(`qc.py:177,187,200`)—— **判定是 cell/decision 级,没有 per-ref verdict 细节**;`curate_analysis` 丢弃站不住 cell(`qc.py:208-245`),不回写任何 support_verdict。
- **改造**:
  1. `EntailmentVerdict` 升级:`{verdict: Literal["supported","partial","unsupported"], reason}`;`check_entailment`/`curate_analysis`/`check_decision_entailment`/`curate_decisions` 改为返回带 verdict 的结构(不再 `QCIssue|None`,否则丢 verdict)。entailment prompt(`qc.py:183-186`、决策 `qc.py:327-330`)教 LLM 判**三级**:
     - `supported`:证据直接、充分支撑。
     - `partial`:证据相关但不充分(单一来源/旁证/部分支撑)。
     - `unsupported`:不支撑或无关。
  2. **判定挂 cell/decision 级,不挂 ref**(codex [P1] 防新幻觉):check_entailment 是合并判一次,**严禁**把这一个判定复制到每个 `evidence_ref.support_verdict`(会伪造「每条 quote 的支持度」)。→ §7.2 给 `ComparisonCell`/`Decision` 新增 cell/decision 级 `support_verdict` 字段,信任信号一律读它;ref 级字段保持 LLM 原值且**不展示**。
  3. `curate_analysis`(`qc.py:208-245`):`unsupported` → **仍按策展人丢弃**(矩阵显「—」,记忆 [[qc-curator-not-judge]] 不回退);`supported`/`partial` → 保留并回写 cell 级 `support_verdict`。`curate_decisions`(`qc.py:340-385`)对称。
  4. **recheck 不进路由**(codex [P1]):partial/unsupported 的三级判定结果**绝不**写进 `qc_result.issues`(否则 `decide_verdict` 把 unsupported 当 hallucination → retry_analyze,破坏策展人模型,`nodes.py:273,318,330`)。三级判定是**独立的展示用 recheck**,与重试路由解耦。
  5. **返回值/调用点**(codex [P1]):若扩展 `curate_*` 返回值会打断现有二元解包(`nodes.py:273,391`)→ 要么同步改全部调用点,要么用结构化 side channel 挂 downgraded、不改签名。plan 里二选一并写死。
  6. **StatusBar 三色语义重定义**:`充分 X`(绿●,supported cell 数)· `部分 Y`(琥珀◐,partial cell 数)· `已剔除 Z`(红○,unsupported 被策展剔除数,点开看剔除清单)。红○ = 策展剔除计数,不再是矩阵格里的假数据。
- **新 SSE 事件** `verdict_recheck`(qc 完成):`{cell_verdicts:[{dimension, competitor, support_verdict}], decision_verdicts:[...], dropped:[...], downgraded:[...], summary:{supported, partial, dropped}, ts}`。**必须结构化持久化**(§7.3),否则 replay/刷新丢剔除与降级清单(现 dropped 只在局部变量 + trace 文本计数 `nodes.py:346-349`,codex [P2])。
- **验收(反幻觉关键,测病因不变量)**:
  - 真 run 也能出现 partial/剔除(不再只有 supported);单测断言「entailment 三级 → cell 级 `support_verdict` 被回写」+「三级判定不进 `qc_result.issues`」(测病因不变量,不是症状落点,记忆 [[same-disease-new-symptom-fools-tests]])。
  - **真 run 校准**:真打验证三级判定不误伤(把充分判成不足=假降级);门槛在真 run 上校准(记忆:真 run 抓 pipeline scoping bug)。
  - 移除前端所有「原型态·待后端实现」角标(2e 的 proto-tag),因三色不再假。
- **风险**:LLM 三级判定比 bool 更易抖动 → 需真 run 校准 + 可能 few-shot。降级:若三级不稳,临时回落「supported / 丢弃」二态(D2 选项 B 形态)而非展示假三色。

### 5.6 撰写员报告台 · insight 两步化真字符流(用户拍板纳入本期)
> 背景:codex [P1] 证明**不能直接**把 insight 换成 `stream_chat`(它是 `structured_call(ReportInsight)`,`writer.py:143,182`;落库 + REST 要 Pydantic,`nodes.py:226,229`)。用户坚持要「报告边写边长」的真打字感,故采纳 codex 点名的**唯一诚实路径:两步化**(stream 自由文本草稿喂 typing → 再 `structured_call` 抽成结构化 insight,契约不破)。
- **现状**:`generate_insight` 一次性 `structured_call(ReportInsight)`(`structured.py:76,97`);`stream_chat` 只读 `delta.content`(`streaming.py:60,80`),已定义 `chunk` 事件(`schemas.py:128-139`)+ 前端已接(typingStore/writerReport,`runStore.ts:190-196`),但生产链路从不调用(§2.3 死能力,本期复活)。
- **改造(write 节点两步)**:
  1. **Step 1 流式草稿**:`stream_chat` 生成 insight 自由文本草稿(市场格局 / 战略分歧 / 短中长 takeaway 三段散文),逐 delta emit `chunk` 事件 → 前端**报告台逐字**(撰写员在写报告的招牌时刻,目标③④)。
  2. **Step 2 结构化抽取**:`structured_call(ReportInsight)` 把草稿规范成三字段 Pydantic(`market_context`/`differentiation_thesis`/`actionable_takeaway`)→ `save_insight` + REST 不变(契约不破)。
- **降级(契约保证)**:Step 1 stream 失败/超时 → 跳过 typing,直接走现有一次性 `structured_call`(数据正确、只是没打字感)。**结构化产物始终有保证,typing 是 best-effort。**
- **唯一信任契约**:insight 是 LLM 综合判断,渲染标「AI 综合判断」(承现有 `generate_insight` 语义);不引入新的未受控模型文本出口(质检裁决说明仍**不流式**,codex [P2] #14)。
- **风险 + spike(plan 第一任务,codex [P1] 修订口径)**:风险不是「streaming function-calling」,而是「Doubao(火山方舟,OpenAI 兼容)`stream_chat` 在 production-size payload 上能否稳定流 delta + 两步后产物是否忠实」。`spikes/` 真打验证(记忆:Doubao SDK timeout 必须基于 production payload 测;graceful 兜底)。spike 不过 → 回落一次性 + 前端揭示(数据真)。
- **其余「产物边生成边长」**仍由真实增量数据驱动:矩阵逐格(§5.3)、决策逐条、计划勾选(目标②)、查询词前端打字机(§2.3)。

---

## 6. 前端改造

### 6.1 融合主轴布局(2e 基线 + v4 done 态 reconcile)
- **基线 = 2e**(用户认可):顶 StatusBar(54px sticky)+ 左决策面(`1fr`)+ 右研究员工作台(固定 472px)。
- **reconcile v4 done 态**(`DESIGN.md:85-90`):running 时右栏 472px live 主秀;done 后右栏可收窄为「查看工作 ↗」摘要条(N 步·M 轮·自我纠错 K 次),左栏成唯一焦点。**采纳 v4 的 done 态收窄**(完成后决策是焦点),作为 2e 基线的补充。
- **响应式**(沿用 2e + v4):≥1280 双栏;1024–1280 右栏折叠为顶条/抽屉;<1024 单栏纵堆决策面优先;`prefers-reduced-motion` 禁动画。

### 6.2 agent 人格 / 头像 / 工牌 + 抽屉
- roster:右栏顶 2×2 工牌(`ROLE` 4 角色,身份色 青/赭/蓝/紫低饱和)。工牌字段:头像(身份色描边)+ 职能名 + 工号(RR-C01 等)+ 状态灯(待命灰/执行身份色/完成绿)+ 当前任务 + retry 角标。
- 点工牌 → agent 抽屉:大头像 + 角色名 + 工号/职能 + 当前/最近任务 + 技能管理区(§6.3)。
- 复用并扩展现有 `EvidenceSlideOver` 的抽屉机制;实现 §6.x 的导航栈。

### 6.3 技能子系统(框架真 · 行为接入后续 = D3)
- 技能卡 UI(2e 干净版):`name`(核心 skill 带低调「核心」标)+ 一行描述 + 版本(v1,mono tabular-nums)+ 状态(启用/停用)+ 开关 + 删除。**不展示** why_preset/boundary(用户:观感不好,已删;数据仅设计内部用)。
- 状态:单一 `skillState = {'<id>':{version, enabled}}`(2e 已有),**本期升级为后端持久化**(新增 `agent_skills` 表 / 配置存储 + REST),为后续迭代测效果打底。
- 技能市场:每 agent 可装的正交 skill(2e 的 `MARKET`,均诚实正交项,不含未实现的情感打分/趋势监控)。
- **四 agent 正交 skill 目录**(已过正交清单,本期作为「展示的真实能力」):
  - 采集员:证据检索 / 证据整备 / 缺口补采
  - 分析员:画像抽取 / 对比矩阵构建 / 溯源粒度纪律 / 抽取降级兜底
  - 撰写员:**有据报告综合〔核心〕** / 确定性正文渲染 / 执行洞察生成
  - 质检员:机械三闸 / 蕴含判定 / 证据策展 / 输出脱敏
- **撰写员核心 skill「有据报告综合」**= 封装 RivalRadar 真实报告逻辑(用户明确要求):总-分-总 + Hybrid(事实走 Python 模板 `render_body`=0 broken refs `writer.py:134-140`、判断走 LLM `generate_insight` 标「AI 综合」`writer.py:143-182`)+ ReportInsight 三段强制(`market_context`/`differentiation_thesis`/`actionable_takeaway` `models.py:210-221`,即真打 18.5→24/30 的三个失分项)+ 反套话黑名单。
- **诚实标注**:本期装/删/开关**不改变** agent 运行时行为,卡片或抽屉标「技能行为接入下一期」。**不假装已生效。**

### 6.4 右栏研究员工作台(目标①②④落地)
- 检索台:真实查询词逐字(§5.6 前端打字机)+ 命中「+N 源」(§5.1)。
- 来源卡:真实标题/域名/类型/日期 + 三色裁决(§5.2);可点开原文(REST)。
- 逐格依据:矩阵格的证据徽章携带 evidence id(§5.3);点决策 → 矩阵交叉高亮(v4 因果桥,`DESIGN.md:110`)。
- 执行时间轴:绝对时间(HH:MM,记忆/codex:绝对日期)+ 角色 + 「→ 导致变化」(每节点必产左侧可见变化,`DESIGN.md:115` 防 agent theater)。
- 重试环:唯一签名动画(青绿单回环 700–1100ms 单次,`DESIGN.md:120`);真实「第 N 轮 · 证据 X→Y」(§5.4)。
- 计划勾选:plan step 由 SSE 事件驱动 doing→done/reopen(目标②);done/reopen 可点开步骤详情(查询词+命中来源)。

### 6.5 store / SSE 接线(新事件)
- `runStore.handleEvent` 扩展处理新事件:`query`/`query_hit`/`source`/`cell_row`/`evidence_delta`/`verdict_recheck` + **复活 `chunk`**(insight 两步 step1 流式草稿,§5.6;typingStore/writerReport 已接)。
- 新增/扩展 store 切片:queries[]、逐格 cell 到达序列、retry 增量、回写后的 verdict map。
- **枚举防御**(记忆 [[enum guard]]):新事件 type 用「not 已知不 happy」防御,replay 终态不漏。
- demo/replay 平价:`fakeSSEPlayer` 与 replay trace **必须产出同形状的新事件**,否则 demo 看到的过程感真 run 没有(记忆:demo bullet-proof 必须 end-to-end URL spike)。

### 6.6 状态覆盖 + a11y
- 状态覆盖已全(§2.4),新组件(检索台/来源卡/逐格/技能卡)补齐 loading/empty/error/failed/cancelled/degraded/insufficient(`DESIGN.md:135-153`):
  - 检索台 running 显查询进行中,failed 显「该查询无结果」非 raw exception。
  - cancelled 保留已完成、未跑标「已停止」;失败节点红+可读原因。
- a11y(`DESIGN.md:155-158` + codex):抽屉 `role="dialog" aria-modal` + 焦点 trap + Esc 关 + 恢复触发焦点;support_verdict 色盲双编码(色+形状 ●◐○);对比度 ≥4.5:1;触摸目标 44px。

### 6.x 抽屉导航栈(2e 核心改造,保留)
- `navStack` + `renderEvidence/renderStep/renderAgent` + `showTop/openTop/pushView/goBack/fullClose`(2e 已验证):返回退回上一层(研究计划→步骤→命中来源,返回回步骤而非全关);✕/Esc 全关。React 实现:用 store 维护 navStack,抽屉组件按栈顶渲染。

### 6.7 反幻觉收口(因真算而清理)
- 移除 2e 的所有「原型态·待后端实现」proto-tag(§5.5 真算后三色为真)。
- 任何仍未真实的展示项(若有)必须显式标注或不展示 —— 全 spec 不留「展示后端没有的能力」。

---

## 7. 数据契约汇总

### 7.1 新增/扩展 SSE 事件(前后端同步)
| event | payload | 触发节点 | 前端消费 |
|------|---------|---------|---------|
| `query` | `{competitor,dimension,query_text,language,round,ts}` | collect | 检索台逐字 |
| `query_hit` | `{query_text,hit_count,round,ts}` | collect | 命中 +N 源 |
| `source` | `{evidence_id,competitor,dimension,source_title,source_url,language,fetched_at,round,ts}` | collect | 来源卡 + seed evidenceStore |
| `cell_row` | `{dimension,cells:[{competitor,value_type,value,evidence_refs}],ts}` | analyze | 矩阵逐维填 |
| `evidence_delta` | `{round,added_count,total_count,new_evidence_ids,ts}` | collect(retry) | 重试环 X→Y |
| `verdict_recheck` | `{cell_verdicts,decision_verdicts,dropped,downgraded,summary,ts}` | qc | 矩阵/决策真三色 + StatusBar |
> `chunk` 事件(`schemas.py:128-139` 已定义)本期**复活**用于 insight 两步化 step1 流式草稿(§5.6);前端 typingStore/writerReport 已接(`runStore.ts:190-196`)。质检裁决说明仍不流式(codex [P2] #14)。

> 所有事件经注入 emit 发出(emit 函数 `sse.py:143-156`,config 注入 `sse.py:158-166`,codex [P2] 行号修正;自动带 ts);新事件需在 `api/schemas.py` 加 Pydantic + `types/api.ts` 镜像(跨 layer enum 同步,记忆 [[silent CSS / type-domain 混淆]])。

### 7.2 schema 字段增量(codex [P1] 修订:cell/decision 缺 verdict 字段,必须新增)
- `EntailmentVerdict`:`{supported: bool, reason}` → `{verdict: Literal["supported","partial","unsupported"], reason}`(§5.5);`check_entailment`/`check_decision_entailment` 改为返回带 verdict 的结构(不再 `QCIssue|None`,否则丢 verdict,`qc.py:177-200`)。
- **新增 cell 级字段**:`ComparisonCell` 加 `support_verdict: SupportVerdict`(`models.py:114` 现无 cell 级,只在 refs 上)。
- **新增 decision 级字段**:`Decision` 加 `support_verdict: SupportVerdict`(`models.py:166` 现无)。
- **不回写 per-ref**:check_entailment 把一个 cell/decision 的全部 refs **合并判一次**(`qc.py:177-200`),只有 cell/decision 级 verdict;**严禁**复制到每个 ref(=伪造「每条 quote 支持度」新幻觉,codex [P1])。前端三色一律读 cell/decision 级字段;`EvidenceRef.support_verdict` 保留但**不作信任信号展示**(LLM 自报、不可信)。
- 持久化:dropped/downgraded 清单需结构化持久化(§7.3),否则 replay 丢剔除/降级信息(codex [P2])。
- `curate_analysis/curate_decisions` 返回值改动会打断现有二元解包调用点(`nodes.py:273,391`)→ 改签名须同步改全部调用点,或用结构化 side channel 挂 downgraded、不改签名(plan 二选一)。

### 7.3 持久化增量
- 新表 `queries`(§5.1)+ repository CRUD + REST `GET /runs/{id}/queries`。
- 新表 `agent_skills`(§6.3,run 无关的 agent 配置:`agent_id, skill_id, version, enabled, installed_at`)+ REST 读写。
- **verdict_recheck 结构化持久化**(codex [P2]):cell/decision 级 support_verdict 已随 analysis/decisions 落库(§7.2 新字段);**dropped/downgraded 剔除清单**需结构化存(随 trace 或新字段),否则 replay/刷新丢这些信息(现仅局部变量 + trace 文本计数 `nodes.py:346-349`)。
- `tmp_path` 隔离 SQLite 单测(CLAUDE.md 测试纪律),WAL 并发写写覆盖。

---

## 8. 设计系统增量(→ DESIGN.md v5)

写入 DESIGN.md(用户同意 v4 可更新):
1. **融合主轴 v5**:右栏从「时间线日志」升级为「研究员工作台」(检索台/来源卡/逐格/重试环/计划勾选)的规格;done 态右栏收窄(承 v4)。
2. **agent 人格层**:工牌规格(头像插画肖像/身份色/工号/状态灯/当前任务)+ 立场:机构级持证专家、非 office 拟物(§3.2);头像为可换占位。
3. **技能子系统**:技能卡 UI(name+描述+版本+开关+删除,无 why/boundary)+ skillState 数据模型 + 「行为接入二期」诚实标注。
4. **support_verdict 真算后的三色语义**(更新 `DESIGN.md:54-66`):supported●/partial◐ 真回写到矩阵/决策;unsupported○ = StatusBar 策展剔除计数;移除「原型态」概念。
5. **审计化文案 + 绝对日期 + 去廉价感**(承 codex findings):无渐变、阴影仅浮层、绝对日期 YYYY-MM-DD / HH:MM。
6. Decisions Log 加一行:v5 增量来源 = 本 spec。

---

## 9. 测试策略

- **后端单测**(CLAUDE.md:成功+失败两路必测,bug 先写复现测):
  - 新 emit 事件:每个节点 emit 被调用 + payload 形状(monkeypatch emit 收集)。
  - support_verdict 真算:entailment 三级 → 回写断言(测**病因不变量**:回写发生,不是断言某个症状色;记忆 [[same-disease-new-symptom-fools-tests]])。
  - graceful skip:单 query/单维抛错 → 不中断整轮(`_run_query_safe` 类保护,记忆:pipeline graceful skip 是 production 必须)。
  - 持久化:queries/agent_skills 表 CRUD + WAL 并发。
- **真 run 验证**(记忆强制:单测全绿 ≠ 真 run 对;尤其子集维度 case):真打 LLM,看 partial 是否真出现、是否误伤、逐格/检索台/重试环是否真动。
- **前端**:`cd frontend && pnpm build`(`tsc -b && vite build`,不是 `tsc --noEmit`,记忆 [[verify-with-real-project-script]])+ `/browse` 真打融合主轴/工牌/技能/抽屉/状态覆盖(浅深色)。
- **LLM 真流式 spike**:`spikes/` 真打 Doubao streaming function-calling 可行性(plan 第一任务)。
- **demo/replay 平价**:`/browse` 端到端跑 demo URL 验证新事件全产出、无 dead loop(记忆 [[demo bullet-proof]])。

---

## 10. 分期边界(写死)

**本期(全量过程真实化 + 反幻觉 + 技能框架)**:§5 全部(5 emit 区 + §5.6 insight 两步化字符流,spike gated)+ §6 全部 + §7 契约 + §8 DESIGN.md v5。
**二期**:技能真接入 prompt(装 skill 改 agent 行为,版本 A/B 测效果)。
**永不做(除非推翻设计,§1.5)**:provider/confidence 复活、sentiment、多源交叉验证、监控趋势。

---

## 11. 风险与未决

| 风险 | 影响 | 缓解 |
|------|------|------|
| **insight 两步化字符流**(用户纳入本期) | Doubao stream 稳定性 / 两步产物忠实度未验证 | plan 第一任务 spike;降级=一次性 structured_call + 前端揭示(数据真,契约保证) |
| **cell/decision 缺 verdict 字段**(codex [P1]) | §5.5 信任信号无处挂 | §7.2 新增 cell/decision 级 support_verdict;cell 级判定**不复制到 ref**(防新幻觉) |
| **recheck 误入路由**(codex [P1]) | unsupported 当 hallucination → retry_analyze,破坏策展人 | 三级判定独立于 `qc_result.issues`,不进 decide_verdict |
| **curate 返回值/调用点**(codex [P1]) | 打断 `nodes.py:273,391` 二元解包 | 同步改全调用点 或 side channel 挂 downgraded 不改签名 |
| **round 造假**(codex [P1]) | retry_count 首轮为 0 但已 broaden | round 由 qc_result 存在性 + retry_count 推导,单测锁死 |
| **support_verdict 三级误伤** | 假降级(把充分判成不足) | 真 run 校准门槛 + few-shot;降级=回二态 |
| **范围大** | 周期长 | 分期已切;技能行为接入已挪二期;字符流已砍;复用现成基建 |
| **WSL2 Clash 代理** | LLM/git 卡 | 每 bash unset 代理 + NO_PROXY(LLM/git push);codex 反而留代理 |
| **demo/真 run 不平价** | demo 有过程感真 run 没有 | fakeSSEPlayer/replay 必产同形状新事件 + 真 run 验证 |

**未决(plan/spike 解)**:
1. support_verdict 三级 prompt 是否需 few-shot、门槛在哪(真 run 校准)。
2. round 推导规则(qc_result 存在性 + retry_count)在 plan 写死并单测。
3. agent_skills 持久化放 SQLite 表还是配置文件(plan 定;倾向 SQLite 与现有一致)。
4. curate_* 返回值改签名 vs side channel(plan 二选一)。
5. insight 两步化 Doubao stream spike 结果(本期 plan 第一任务):稳定流 delta?两步产物忠实?不过则回落一次性。

---

## 12. Codex outside-voice 裁决(2026-06-07,逐条采纳)

> 跨模型评审真 grep 后端核验 spec 断言(记忆 [[outside-voice-adjudicate-not-wholesale]]:逐条裁决)。14 条 findings **全部采纳**(均有代码佐证,无驳回)。其中 2 条是本 spec 的实质错误,已纠。

| # | 级别 | finding | 裁决 | 落点 |
|---|------|---------|------|------|
| 1 | P1 | insight 是 `structured_call(ReportInsight)` 非自由文本,换 stream_chat 毁契约(`writer.py:143,182`/`nodes.py:226,229`) | 采纳(实质错误)→ 用户拍板走 codex 点名的诚实路径**两步化**(stream 草稿→structured_call 抽取,契约不破) | §5.6 重写:insight 两步化纳入本期 |
| 2 | P1 | Doubao 风险写偏:真风险是「stream 后能否恢复结构化」非「streaming function-calling」 | 采纳 | §5.6 风险口径修订 + spike |
| 3 | P1 | 回写每个 ref 会伪造「每条 quote 支持度」;check_entailment 合并判一次(`qc.py:177-200`) | 采纳(实质错误) | §5.5/§7.2:判定挂 cell/decision 级,不挂 ref |
| 4 | P1 | `ComparisonCell`(`models.py:114`)/`Decision`(`models.py:166`)无 cell/decision 级 support_verdict | 采纳(纠正「字段不动」) | §7.2 新增字段 |
| 5 | P1 | unsupported 若进 qc_result.issues → retry_analyze,破坏策展人(`nodes.py:273,318,330`) | 采纳 | §5.5:recheck 独立于路由 |
| 6 | P1 | curate 返回值改三元组打断二元解包(`nodes.py:273,391`) | 采纳 | §5.5/§7.2:同步调用点或 side channel |
| 7 | P1 | round>0 易造假:首轮 retry 时 retry_count 仍 0 但已 broaden(`nodes.py:100,125,332`) | 采纳 | §5.1/§5.4:round 由 qc_result+retry_count 推导 |
| 8 | P2 | emit query 要改 pipeline 回调签名(`nodes.py:109`/`pipeline.py:61,66`) | 采纳 | §5.1 改造修订 |
| 9 | P2 | §5.3 行号错:`_compare_one_dimension`=203-220,223-267 是 `build_comparison` | 采纳 | §5.3 行号修正 |
| 10 | P2 | 逐格并行 → cell_row 乱序到达(`analyst.py:261,266`) | 采纳 | §5.3 乱序契约 |
| 11 | P2 | 单维失败只 degraded_sink+跳过(`analyst.py:252,256`),缺失败事件契约 | 采纳 | §5.3 加 status 字段 |
| 12 | P2 | emit 注入行号:函数 143-156 / 注入 158-166 | 采纳 | §7.1 行号修正 |
| 13 | P2 | verdict_recheck 只 live 丢 replay 剔除清单(`nodes.py:346-349`) | 采纳 | §5.5/§7.3 持久化 |
| 14 | P2 | 质检流式裁决说明=新未受控模型文本出口(`schemas.py:68`/`reads.py:54`) | 采纳 | §5.6:不做 |

**净结论**:spec 反幻觉立场不变且更硬。两处实质修订:① 字符流不能直接换(契约),用户拍板走 codex 点名的诚实路径 **insight 两步化**(stream 草稿喂 typing → structured_call 抽取,契约不破)纳入本期、spike gated;② support_verdict 真算需给 cell/decision 新增字段、判定挂 cell 级、与重试路由解耦。其余「边生成边长」由真实增量数据(逐格/决策/计划/查询词打字机)驱动。

---

## 附:writing-plans 须知
- 任务顺序建议:① **insight 两步化 Doubao stream spike**(解最大风险,§5.6)→ ② 后端 emit 5 区(查询词 → 来源卡 → 逐格 cell_row → retry 增量 → support_verdict 真算)+ insight 两步化 → ③ schema 字段(EntailmentVerdict 三级 + cell/decision 级 support_verdict)→ ④ 持久化表(queries / agent_skills / dropped-downgraded)→ ⑤ 前端 store/SSE 接线(含 chunk 复活)→ ⑥ 融合主轴+工牌+技能框架+抽屉 → ⑦ 状态覆盖+a11y+反幻觉收口(删 proto-tag)→ ⑧ DESIGN.md v5 → ⑨ demo/replay 平价 → ⑩ 真 run 校准(support_verdict 三级门槛 + insight 两步)。
- insight 两步化字符流纳入本期(spike gated,§5.6);质检裁决说明仍**不**流式。
- 每任务双审(成功+失败路径单测先行,测病因不变量);ship 前真 run + /browse + outside voice(codex)。
