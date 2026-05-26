# RivalRadar 设计文档

- 日期:2026-05-21
- 状态:已通过工程评审(plan-eng-review)+ 独立第二意见(Claude 子 agent),待用户最终确认
- 周期:2.5 周(0.5w 架构 + 1w 单体 Agent + 1w 联调与反馈闭环)

## 1. 背景与目标

RivalRadar 是一个多 Agent 协作的竞品分析系统,模拟"数字调研小组":由 4 个专职 Agent 自动完成从公开信息采集到结构化竞品报告的全链路产出,并通过 Agent 间交叉审查与反馈实现自我校验。

评分权重(优化目标):
- 35% 多 Agent 协作与输出可信度
- 25% 技术深度与可观测
- 20% 业务价值与产品体验
- 10% 代码质量与文档
- 10% 合规、材料与答辩

## 2. 范围

**In scope(v1)**
- 4 角色 Agent(采集 / 分析 / 撰写 / 质检)+ LangGraph 编排 + 条件边真闭环
- 真实数据采集(搜索 API + 读页抽取 + 证据链),跨语言(中英文)
- 知识 Schema 强制溯源(每条结论挂 evidence_ids)
- 轻量 Web 应用:报告查看 + 溯源跳转 + Agent 决策回放(Trace)
- 可观测:每个 Agent 的 prompt/输入/输出/token/耗时落库

**Not in scope / 已砍(评审决策)**
- ~~人工修正(改结论 + 重跑)~~ → 降级为**只读"标记质疑"桩**(只记日志,不写回)。理由:最高工时 / 最低权重,半成品写路径反伤演示(D10)
- 多模型对比、自适应任务拆分、动态 Schema 演化 → 文档列"未来扩展"
- 真实问卷 / 访谈 → 用"抓公开用户评价"替代(D 早期决策)

## 3. 已锁定关键决策(D1–D11)

| # | 决策 | 结论 |
|---|---|---|
| D1 | 范围姿态 | 全量推进(后经 D10 微调:砍人工修正) |
| 数据源 | 信息采集 | 真实采集:搜索 API + 读页抽取 + 证据链(非预置语料) |
| 演示域 | 竞品语言 | 跨语言(中英文)|
| 前端 | 产品门面 | 轻量 Web 应用 |
| 框架 | 编排 | LangGraph + 4 角色 + 条件边真闭环 |
| 访谈 | 用户声音 | 抓公开用户评价替代访谈 |
| D2 | 结构化输出 | 封装 `structured_call()`(校验+重试)+ 首日 Doubao spike |
| D3 | 反馈闭环 | 结构化 QCIssue + 定点重做 + 证据累加(经 D-外部意见强化:见 §8)|
| D4 | 存储 | SQLite + LangGraph SqliteSaver |
| D5 | 跨竞品对比 | 由分析 Agent 收尾产出 |
| D6 | 合规 | 搜索/抽取 API 为主 + robots/限速 + `DATA_SOURCES.md` |
| D7 | 测试 | 小型 golden eval 集 + 结构断言 + 真闭环回归 |
| D8 | 采集并行 | 并行 + 限并发/限速 |
| D10 | 人工修正 | 砍掉,降为只读"标记质疑"桩 |
| D11 | 功能树 Schema | **扁平邻接表**(非递归),Python 拼树 |
| AP-D1 | 协作可视化 | 实时动画 DAG + 轻量 SSE(money shot,见 §11.4)|
| AP-D2 | 业务价值 | 指标面板 + 一次 vs 人工小对照(见 §17)|

## 4. 系统架构

LangGraph 状态图,所有 Agent 共享 `ResearchState`,节点间传 **Pydantic 结构化对象**(function-calling 风格,非自然语言对话)。

```
ResearchState(共享状态)
  competitors      目标竞品列表
  dimensions       分析维度(功能/定价/评价/画像)
  evidence[]       证据块(append-only,reducer=add)
  analysis         结构化分析(符合 Schema)
  report           markdown 报告
  qc_result        质检结论 {verdict, issues[]}
  retry_count      打回计数(有界)
  trace[]          每节点 prompt/输入/输出/token/耗时
```

```
            ┌───────────────────────── 真闭环 ─────────────────────────┐
            │                                                          │
START → [采集] ──→ [分析] ──→ [撰写] ──→ [质检] ──route──→ END (pass)
            ▲          ▲                            │
            │          └── retry_analyze(结论/Schema/证据问题)┘
            └───────────── retry_collect(覆盖度不足/缺源)──────┘
                       retry_count 超限 → END(降级:标注"未达质检标准")
```

`route` 是条件边路由函数,读 `qc_result.verdict` 决定:`pass→END` / `retry_collect→采集` / `retry_analyze→分析` / `insufficient_evidence→END`(如实标注"未找到公开数据")/ `retry_count` 超限→降级结束。

## 5. 四个 Agent(职责互不重叠)

| Agent | 职责 | 输入 → 输出 | 约束 |
|---|---|---|---|
| **采集** | 规划检索词(中/英)→搜索 API→读页抽取→切片;含公开评价抓取 | `competitors, dimensions`(+打回缺口) → `evidence[]` | 每证据块带 `source_url`+`fetched_at`;并行+限速;robots 检查 |
| **分析** | 证据→结构化结论(功能树/定价/画像/SWOT);收尾产出跨竞品对比 | `evidence[]` → `analysis` | 只引用 evidence;每结论挂 `evidence_refs`(含被引原句);无证据不写 |
| **撰写** | 结构化分析→人类可读报告 | `analysis` → `report` | 保留内联引用;数据标 "as of {date}" |
| **质检** | 校验 Schema 完整/覆盖度/`evidence_refs` 有效性(确定性)+ 引语支持判定(LLM 蕴含)| `analysis+report+evidence` → `qc_result` | 确定性校验是硬闸,LLM 判定尽力 |

## 6. 知识 Schema(扁平邻接表,溯源由 Schema 强制)

核心原则(经 Codex 评审强化):结论不只挂"证据块 id",而是挂 **`EvidenceRef{evidence_id, quote, support_verdict}`** —— 指向证据里**被引的那一句话** + 支持判定。质检既能机械判定"空引用=不合格",也能核对"引语是否真支撑结论"。功能树用**扁平邻接表**(D11),显示时 Python 拼树,避免 Doubao 对递归 `$ref` 的不稳定。

```python
Evidence:        # 证据块(采集产出)
  id, competitor, dimension, content, source_url, source_title, language, fetched_at

EvidenceRef:     # 句级引用(结论→证据的最小单元,Codex #2)
  evidence_id, quote(被引原句), start/end(可选偏移), support_verdict(supported/partial/unsupported)

FeatureItem:     # 功能项(扁平,parent_id 表达层级)
  id, name, description, category, parent_id (可空), evidence_refs[]

PricingModel:
  model_type, tiers[{name, price, billing_cycle, features_included[], limits}], evidence_refs[]

UserPersona:
  segment, needs[], pain_points[], praise[], evidence_refs[]

SWOT:
  四象限: list[Point{text, evidence_refs[]}]

CompetitorProfile:
  name, features: list[FeatureItem], pricing, personas[], swot

ComparisonCell:  # 类型化对比值,避免鸡同鸭比(Codex #3)
  competitor, value_type(bool/enum/number/quote_text), value, evidence_refs[]
ComparisonRow:
  dimension(受控本体), cells: list[ComparisonCell]

CompetitorAnalysis:
  competitors: list[CompetitorProfile]
  comparison: list[ComparisonRow]
```

> **受控本体**(per demo 垂类,Codex #3):pricing / deployment / integrations / target_users / core_workflows / review_sentiment。对比值尽量类型化(布尔/枚举/数值/引语支撑文本),避免自由文本语义漂移。

## 7. 数据采集流水线

参考 deep-research 标准做法(plan→search→fetch/extract→evidence):

```
对竞品 → 按维度生成检索词(中/英)
       → 搜索 API 找源(返回 URL+摘要)
       → 读页抽取正文(清洗 HTML)→ 切片
       → 存证据块 {原文, source_url, fetched_at, competitor, dimension, language}
```

- **并行**:`asyncio.gather` 跑竞品×维度,**限并发 + 限速**避免被封(D8)
- **跨语言**:规划环节按竞品生成对应语言检索词;抽取层与语言无关;Doubao 中英文皆可
- **合规(D6)**:优先用合规友好的搜索/抽取 API(Tavily/Exa/Firecrawl);自抓页面时查 robots.txt + 限速 + UA 标识;`DATA_SOURCES.md` 公开声明数据来源与策略
- **数据可达性(外部意见)**:知乎/小红书等中文评价站登录墙+反爬,API 可能取回空。**Day-1 spike 实测**;优先选可达评价面(App Store / Google Play / G2 / Capterra);知乎/小红书作**尽力而为**,不强制纳入覆盖度
- **数据质量 > 可达性(Codex #4)**:Day-1 spike 不仅验"能否抓到",还验"是否权威/最新/可比/可抽取"。**来源优先级**:官方定价/功能页 > 评价平台 > 搜索结果;加**新鲜度评分**;demo 只用通过**质量 spike** 的源(定价页常因地区/套餐/JS 渲染而异)

## 8. 反馈闭环(真闭环,非伪闭环)

35% 的命门。质检的 `issues[]` 是结构化、可执行的缺口,被打回节点据此**只补缺口**,证据**累加不覆盖** → 第二遍因证据更多而真改善(D3)。

```python
QCIssue:
  competitor, dimension, problem_type (missing_evidence / schema_incomplete / hallucination / low_coverage), detail
QCVerdict ∈ {pass, retry_collect, retry_analyze, insufficient_evidence}
```

**外部意见强化**:
- 重试时采集**广搜**(换查询/换源),不死磕同一缺口(否则源头本就无该数据时会空转)
- `insufficient_evidence`(查无公开数据)是**一等质检结论**,报告如实写"未找到公开数据",而非无限重试 —— 诚实本身就是可信度加分
- **有界重试**:`retry_count` 封顶(建议单次/最多 2 次),超限走降级

## 9. 结构化输出层(D2)

```
structured_call(model, schema, messages):
  1) 调 Doubao 原生 json_schema(扁平 Schema,无递归 $ref)
  2) Pydantic 校验
  3) 不合格 → 把校验错误回喂,重试(instructor 式自纠)
  4) 封顶重试次数 → 仍失败则显式报错(非静默)
```

被 4 个 Agent 复用(DRY)。**首日 spike**:用真实竞品数据实测 Doubao 能否稳定吐扁平 Schema。

## 10. 存储与可观测(D4 + 25%)

- **存储**:SQLite(零运维),表:evidence / analysis / report / trace / runs
- **状态持久化**:LangGraph SqliteSaver checkpointer(打回重跑可恢复)
- **可观测**:每节点写 trace 记录(prompt/输入/输出摘要/token/耗时/时间戳);前端按 run_id 拉取做决策回放

## 11. 前端(轻量 Web 应用,20% + 承载 35%/25% 的展示面)

经 autoplan 评审:前端是过半权重的兑现面,按信息架构 + 溯源 + 协作可视化 + 状态展开。

### 11.1 信息架构(放弃"一篇 markdown 长文",用结构化卡片)
- 顶层 IA:run 列表 → 竞品列表 → 单竞品报告 → 证据/Trace
- 单竞品报告三屏式:① 竞品速览卡 + 可信度徽章(N 条证据 · 覆盖 X 维度 · as of {date} · 质检通过/未达标)② 维度切片(功能树/定价/画像/SWOT,结构化卡片)③ 跨竞品对比矩阵
- 报告用**结构化组件**渲染,markdown 仅富文本兜底
- 功能树:可折叠 tree view,叶子挂证据 chip

### 11.2 溯源体验(签名功能,就地对照,不跳走)
- 每条叶子结论挂**内联引用 chip** `[1][2]`(来自 evidence_ids)
- 点 chip → **右侧滑出证据面板**(side panel),左报告右证据**同屏对照**
- 面板内容:原文片段(高亮命中句)+ source_title + source_url(此处才外链,新标签打开)+ fetched_at + 语言
- 反向高亮:点结论时,同源支撑的其他结论一并微高亮
- URL 降为面板内次级,**不做"点结论跳走"**

### 11.3 跨竞品对比矩阵
- 行=维度,列=竞品(对应 `ComparisonRow.values`)
- 视觉编码:定价数字条/色阶,功能 ✓/✗,胜出项高亮;每格右下角**证据角标**可点开溯源

### 11.4 协作可视化 = 实时动画 DAG(AP-D1,money shot)
- 4 节点有向图(采集→分析→撰写→质检),复刻 §4 架构
- 打回画成**醒目回流箭头**(对比色弧线),"环"在视觉上是环
- **轻量 SSE 流式**:跑批时实时点亮当前节点 + 证据滚动计数;走到打回时回流箭头亮、retry_count+1、被打回节点重亮
- 跑完可 Play 回放;打回前后**并排 diff 徽章**(证据 12→19 / qc fail→pass)= §13 回归测试的视觉版
- 节点点开抽屉:prompt/输入/输出摘要/token/耗时(trace 表字段)
- 同一组件兼任 **loading 主舞台**(把数分钟等待变"看小组干活")
- **强制一条可见的"分歧→解决"(Codex #5)**:demo 脚本里质检指出一条无支撑结论 → 采集广搜 → 分析改写 → 报告 **diff** 显示结论变化 + 新增引语。让闭环不只"看得见",还"有内容可看"(否则 4 角色像流水线而非协作)

### 11.5 状态设计
- loading:用 11.4 的 DAG 实时进度,不转圈黑屏
- insufficient_evidence:该结论位置标"未找到公开数据"灰条,不留空不编造
- 降级(retry 超限):报告顶部警示横幅"未通过质检(原因)",存疑 section 标黄
- error / empty / 标记桩"已记录" toast

### 11.6 只读"标记质疑"桩(D10)
- 用户对某结论打标记,仅记日志(喂 §17 人工质疑率),不写回不重跑;点击有"已记录"反馈

### 11.7 视觉基调
- 写前端前先跑 `DESIGN.md`(`/design-consultation`):克制、数据感、研报/dashboard 风,避免紫渐变 AI slop
- 桌面优先,为投影优化对比度与字号

## 12. 技术栈

- 后端:Python + LangGraph + FastAPI
- LLM:Doubao-Seed-2.0-lite(火山方舟,OpenAI SDK 兼容,EP `${DOUBAO_MODEL}`)
- 存储:SQLite + LangGraph SqliteSaver
- 采集:搜索 API(Tavily/Exa/Firecrawl,Day-1 定)+ 抽取(Crawl4AI/Firecrawl)
- 校验:Pydantic
- 前端:React / Next.js

## 13. 测试策略(D7)

```
必测路径
[单测] router.route:pass/retry_collect/retry_analyze/insufficient_evidence/超限    ★纯逻辑
[单测] structured_call:不合法→带错重试→成功;超限→显式报错                        ★关键
[单测] collector:中/英查询生成;robots 分支;证据带 source_url+fetched_at
[E2E ] 真实 1 源走通 search→fetch→extract
[eval] analyst:输出符合 Schema;每结论挂 evidence_ids;comparison 有证据
[单测] qc.check_traceability:空 evidence_ids→issue                              ★确定性
[eval] qc.check_hallucination:证据不支撑→issue
[单测] backend API:GET /evidence/:id /report/:run /trace/:run

★★★ 真闭环回归(35% 的机器可验证铁证):
  注入"某竞品定价缺证据"的初始 state → 跑图 → 断言第二版 evidence 增加 且 qc=pass
```

- **golden eval 集**:3-5 个固定竞品案例 + 预期结构/覆盖,改 prompt 后跑一遍即知质量升降
- **结论支持度 eval(Codex #6)**:10-15 条标注的原子结论(supported/unsupported 标签)+ 3-5 条预期对比事实,**评分"结论是否真被证据支持""对比是否准确",而非仅形状**

## 14. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Doubao 结构化输出(beta)对递归不稳 | 扁平 Schema(D11)+ structured_call 校验重试 + Day-1 spike |
| 中文评价站抓不动(登录墙/反爬) | Day-1 数据可达性 spike;优先可达评价面;知乎/小红书尽力而为 |
| 伪闭环 / 死循环 | 结构化缺口 + 广搜重试 + `insufficient_evidence` 一等结论 + 有界重试 |
| 并行 fan-out 的 token/成本/限流 | 限并发 + 限速;补一份成本估算;beta 端点演示前压测 |
| 数据陈旧 | 报告标 "as of {date}" |
| 合规自相矛盾(robots vs 抓评价) | `DATA_SOURCES.md` 写明策略,禁用路径不抓 |

## 15. 2.5 周里程碑

```
Day 1（双 spike 并行,go/no-go）
  - spike A:Doubao 扁平 Schema 结构化输出实测
  - spike B:搜索/抽取 API 对真实竞品(1 中 1 英)各 5 查询的**可达性 + 质量**(权威/最新/可比/可抽取,Codex #4)
  - 产出:锁定 Schema 形态 + 竞品名单 + 搜索/抽取 API 选型 + 来源优先级
周 1（架构 0.5w + 单体 Agent 起步）
  - LLM 层 structured_call + Pydantic Schema + SQLite/SqliteSaver
  - 4 个 Agent 单体(可并行开发)
  - **Day 4 纵向切片门(Codex #1)**:1 run、2 竞品、2 维度,打通 采集→分析→撰写→质检 + 可见 DAG + 句级引用 + trace 抽屉;通了再扩广度
周 2（联调 + 反馈闭环）
  - LangGraph 图编排 + 路由 + 真闭环 + 真闭环回归测试
  - 后端 API + 可观测 trace
周 2.5（前端 + 指标 + 材料）
  - 先出 DESIGN.md 定基调 → 结构化报告 + 证据侧栏溯源 + 对比矩阵 + 实时动画 DAG(SSE)+ 状态设计
  - 指标面板 + vs 人工小对照;预跑 run_id 作演示兜底
  - golden eval、文档、演示视频、答辩材料
```

## 16. 实现并行泳道

```
Lane A: LLM 层(structured_call) + Pydantic Schema   ┐ 先并行
Lane B: 存储(SQLite + SqliteSaver)                  ┘
   → Lane C: 4 个 Agent(依赖 A+B,4 个可再并行)
      → Lane D: 图编排 + 路由 + 反馈闭环
         → Lane E: 后端 API(含 SSE 进度流)→ Lane F: 前端
```

## 17. 业务价值与指标(20%,AP-D2)

评分要"vs 人工的可量化提升 + 业务闭环指标"。这些数字大多是 golden eval 与标记桩的副产品,近乎免费。

### 17.1 指标面板(一页对外展示)
- **准确率**:结论与人工标注一致比例(golden eval)
- **覆盖率**:命中预期维度比例
- **溯源率**:挂了有效 evidence 的结论比例
- **人工质疑率**:标记桩统计 N 条被标记 / M 条总数
- **真闭环提升**:第一遍 vs 第二遍(覆盖/证据数/qc 通过)
- **结论支持度**:被证据真正支撑的结论比例(来自 §13 结论支持度 eval,Codex #6)

### 17.2 vs 人工小对照(N=2)
- 人手查 vs 系统跑,记时间与覆盖维度:"人工 ~X 小时 → 系统 ~Y 分钟,覆盖维度 +Z"
- 这一句是 20% 的命门

### 17.3 质检可信度(回应"同源自审"质疑)
- **确定性闸**(evidence_ids 非空、source_url 可达、Schema 完整)是主角,**量化拦截率**
- LLM 蕴含判定为辅助;**异源交叉**(换不同模型做蕴含判定)列入 TODOS,非 2.5 周必须
