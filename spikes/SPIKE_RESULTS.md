# SPIKE RESULTS

> Day-1 双 spike 的 go/no-go 结论(2026-05-25 实测)。两者均 **GO**。

## Spike A — Doubao 结构化输出 ✅ GO

运行:`.venv/bin/python spikes/spike_a_doubao_schema.py`

**实测发现(关键)**:EP `ep-20260514111325-xjmj7`(Doubao-Seed-2.0-lite)对三种结构化方式逐一实测:
- `response_format={"type":"json_schema"}` → **400 InvalidParameter: not supported**
- `response_format={"type":"json_object"}` → **400 InvalidParameter: not supported**
- plain 模式 + schema 写进 prompt → 可用(5/5,但 ~20.1s、~1799 token)
- **function-calling(tools):schema 作为工具 parameters + 强制 tool_choice → 最优 ✅**

| 路径 | 解析成功率 | 平均耗时 | 平均 token |
|---|---|---|---|
| plain + schema 注入 prompt | 5/5 | 20.1 s | 1799 |
| **tools / function-calling(采用)** | **5/5** | **4.6 s** | **1113** |

**结论:走 function-calling**——同样 5/5,但快 4 倍、省 1/3 token,且 schema 由工具参数原生约束。
判定 **GO**。

**后果(已落地)**:`rivalradar/llm/structured.py` 用 tools 路径(定义工具+强制 tool_choice+取
tool_call 参数+Pydantic 校验+带错重试);单测 5 项绿;真实 Doubao E2E 冒烟通过。
**模型可能不调用工具或参数不合 schema → 校验重试循环仍是兜底**(T6 已做扎实)。

**给 Lane C 的提醒**:单次 LLM 调用 ~4.6s(tools);维度 schema 仍宜精简;并行采集限并发;
spec §11.4 的"实时 DAG 把等待做成可看的协作"依旧成立(多 Agent×多竞品累加仍是数十秒级)。

## Spike B — 搜索/抽取 API 可达性+质量 ✅ GO

运行:`.venv/bin/python spikes/spike_b_search_extract.py`(Tavily,`include_raw_content`)

格式:`[命中数 可抽取数 官方源数 带日期数]`

**Notion (en)**
- pricing 2026:`[5h 4ext 0off 0dated]`(首条第三方博客,需靠来源优先级择官方)
- features:`[5h 4ext 2off 0dated]` ✓ 命中 notion.so
- integrations:`[5h 4ext 2off 0dated]` ✓
- reviews G2:`[5h 3ext 0off 0dated]` ✓ 评价面可抽取
- enterprise SSO:`[0h]` 空(查询太窄 → 需广搜重试)

**飞书 Lark (zh)**
- pricing:`[5h 2ext 2off 0dated]` ✓ 命中 feishu.cn
- features 多维表格:`[0h]` 空
- integrations:`[5h 3ext 4off 0dated]` ✓
- 用户评价 知乎:`[0h]` **空(反爬,如 spec 预测)**
- enterprise SSO:`[5h 3ext 3off 0dated]` ✓

**判定:GO**。两个竞品都拿到 ≥1 官方权威源 + 可抽取正文。
- **新鲜度**:Tavily 几乎不返回 `published_date`(全 0 dated)→ 新鲜度靠 `fetched_at` 的 "as of",或后续从正文抽日期。
- **印证 spec 预判**:知乎 0 命中(反爬);部分查询空(需广搜重试);pricing 首条常为第三方(需来源优先级)。

## Day-1 锁定决策(驱动 Lane C 计划)

经调研 + 用户拍板:

1. **搜索/抽取 API**:**Tavily 主 + Exa 备 + ~40 行 `SearchProvider` 适配层**(额度耗尽自动切换,解 Tavily 免费额度枯竭风险)。Firecrawl 暂不用(封堵中文社媒 + Extract 5× 计费)。
2. **采集源策略 = 黑名单(非白名单)**:默认采用搜索 API 返回的任意公开源(含长尾小站);自抓某 URL 时按诚实 UA 查 robots 并遵守 + 限并发限速 + UA 标识 + per-run 审计。
   - **可达评价面(种子)**:App Store 中国区评论、V2EX、36氪/虎嗅(文章页,经搜索取 URL 再 fetch)、酷安;linux.do(robots 通用允许,但 disallow AI 爬虫/标 ai-train=no → 诚实 UA 或优先 API 摘要)。
   - **小站长尾**:默认可入(robots 通常更宽松)。
3. **红名单(只经搜索 API 公开摘要间接用,不自爬原站)**:知乎、小红书、微博、脉脉、即刻、一切登录墙站。
   - 理由:robots 全站 Disallow + 2025.10.15《反不正当竞争法》第 13 条(绕过技术措施获取数据,最高罚 500 万)+ PIPL + 合规占比 10%。
   - 明确**不引入 MediaCrawler 等反爬工具**(需真实账号 cookie、违 ToS、易封号、易碎)。
4. **demo 竞品(锁定)**:Notion(en)+ 飞书 Lark(zh)。
5. **DATA_SOURCES.md**:Lane C 落地时创建,按 绿/灰/红 三级声明数据源与排除理由,运行时记录实际访问 URL 以备审计。

## Spike D — 分析 Agent 真实 E2E ✅ GO(2026-05-25,Lane C-2a)

运行:`.venv/bin/python spikes/spike_d_analyze_real.py`(对 2 条 canned Notion 证据真打 Doubao)

验证目标:`analyze()` 整条链(逐项抽取 features/pricing/personas/swot + 跨竞品对比)在**真实 Doubao**
上拿到合法 `CompetitorAnalysis`,且结论真挂上取自给定证据的 `evidence_refs`(不是 FakeClient 模拟)。

**实测输出(单竞品 = 5 次真实调用)**:
- features:抽出 5 项(模型自动归纳,英文证据→中文功能名)
- pricing:`model_type=Tiered subscription pricing`,tiers=`['Free','Plus','Business']`(正确取自证据)
- comparison:受控本体下产出 `['pricing','core_workflows']` 两行
- **cited evidence_ids:`{e1, e2}`** —— 两条证据都被引用

**结论:GO**。`tools` 结构化路径在四种业务 schema 上均通过 Pydantic 校验;**句级溯源契约在真模型上成立**
(`_REFS_RULE` + 编号证据块这套 prompt 设计 work),为 C-2b 的 QC Agent "结论是否有据" 判定打底。
判定 **GO**。

**给 C-2b/Lane D 的提醒**:`PricingModel.model_type` 实测返回自由串(非受控枚举),如需口径统一由 QC/本体校验把关;
单竞品 ~5 次调用串行累加(~十余秒),并行化留给 Lane D。

## Spike E — 撰写 + 质检 真实 E2E ✅ GO(2026-05-25,Lane C-2b)

运行:`.venv/bin/python spikes/spike_e_report_qc_real.py`(对 canned analysis 真打 Doubao 跑 `write_report` + `qc.check`)

验证目标:混合撰写(确定性正文 + LLM 导语)与质检(确定性闸 + LLM 蕴含)在**真实 Doubao** 上成稿/判定正确。

**实测输出**:
- 报告:`# 竞品分析报告` + `## 摘要(AI 生成)` + 确定性正文(`定价(freemium) [e1]`、`优势:生态强 [e1]`、对比表、来源、`as of 2026-05-25`)。**LLM 导语只概括正文已有事实,未编造新数字/竞品** —— 混合忠实度成立。
- 质检:verdict=`retry_collect`,7 issue = 5×`low_coverage`(canned 仅覆盖 pricing)+ LLM 蕴含抓出的 `hallucination`(canned 故意把"生态强"挂到只讲定价的证据 e1,蕴含判定识破张冠李戴)。

**结论:GO**。撰写混合 + 质检确定性闸 + LLM 蕴含在真模型上协同正确;**§17.3"同源自审"质疑得到实证反驳**(确定性量化拦截 + 蕴含抓语义不符);`decide_verdict` 让 coverage 优先于 hallucination → `retry_collect`,反馈环输入端正确。
判定 **GO**。

**给 Lane D 的提醒**:`check_entailment` 每条结论一次调用(本 spike 3 条结论 + 撰写导语 1 次 ≈ 4 次真实调用);Lane D 真闭环要按"issues 只补缺口、证据累加不覆盖"重跑,并对蕴含失败做降级 + trace。
