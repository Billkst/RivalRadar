# SPIKE RESULTS

> Day-1 双 spike 的 go/no-go 结论(2026-05-25 实测)。两者均 **GO**。

## Spike A — Doubao 结构化输出 ✅ GO

运行:`.venv/bin/python spikes/spike_a_doubao_schema.py`

**实测发现(关键)**:EP `ep-20260514111325-xjmj7`(Doubao-Seed-2.0-lite)
- `response_format={"type":"json_schema"}` → **400 InvalidParameter: not supported**
- `response_format={"type":"json_object"}` → **400 InvalidParameter: not supported**
- **plain 模式(不带 response_format)+ schema 写进 prompt → 可用**

| 项 | 结果 |
|---|---|
| 解析成功率 | **5 / 5** |
| 平均耗时 | 20.1 s/次 |
| 平均 token | 1799/次(schema 进 prompt 撑大输出) |
| 采用路径 | plain + schema 注入 system prompt + 去 markdown 围栏 + Pydantic 校验 + 带错重试 |
| 判定 | **GO** |

**后果(已落地)**:`rivalradar/llm/structured.py` 已从 `response_format=json_schema` 改为上述路径;
单测 6 项绿;并对真实 Doubao 做了 E2E 冒烟(返回合法 EvidenceRef)。
**没有原生强制 → 可靠性全靠校验重试循环**(T6 已做扎实)。

**给 Lane C 的提醒**:单次 LLM 调用 ~20s,维度 schema 要精简;并行采集必须限并发;
spec §11.4 的"实时 DAG 把等待做成可看的协作"由此被实测数据支持(确实要等)。

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
