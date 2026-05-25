# SPIKE RESULTS

> Day-1 双 spike 的 go/no-go 结论记录。脚本已就绪并提交,**待用户带 API key 运行**后回填本文件。
> 运行前先 `cp .env.example .env` 并填好 `ARK_API_KEY`(spike A)/ `TAVILY_API_KEY`(spike B)。

## Spike A — Doubao 扁平 Schema 结构化输出(待运行)

运行:`.venv/bin/python spikes/spike_a_doubao_schema.py`

| 项 | 结果 |
|---|---|
| 解析成功率 | __ / 5 |
| 平均耗时 | __ s |
| 平均 token | __ |
| 判定 | GO / NO-GO |
| 采用的 response_format | json_schema(非 strict) / json_schema strict / json_object |
| 备注 | 是否需要 strict、是否需要 additionalProperties、踩到的坑 |

判定规则:
- **GO**(≥4/5 成功):扁平 Schema + `response_format=json_schema` 路线成立,`structured_call` 默认参数即用这套(已是当前实现)。
- **NO-GO / 部分**(<4/5):依次尝试 ① 给 `json_schema` 加 `"strict": True` 并让 `to_doubao_schema` 补 `additionalProperties: false` + 把可选字段并入 `required`;② 退化到 `response_format={"type":"json_object"}` + 在 prompt 内贴 schema;③ 进一步摊平模型。把实测结论回填到 `rivalradar/llm/structured.py`。

## Spike B — 搜索/抽取 API 可达性+质量(待运行)

运行:`.venv/bin/python spikes/spike_b_search_extract.py`

- 选定搜索/抽取 API:Tavily / Exa / Firecrawl
- Notion:官方源命中 __/5,可抽取 __/5
- 飞书:官方源命中 __/5,可抽取 __/5;中文评价站可达性:____
- 来源优先级(确认):官方页 > ____(可达评价面)> 搜索结果
- 新鲜度:是否普遍有 published_date ____
- demo 竞品名单(锁定):____
- 受控本体覆盖(锁定):pricing / deployment / integrations / target_users / core_workflows / review_sentiment 各能否取到源

判定规则(对照来源优先级:官方定价/功能页 > 评价平台 > 搜索结果):
- **GO**:每个竞品 ≥1 个官方权威源 + 评价面能拿到可抽取正文。
- **关注点**:中文评价站(知乎/小红书)很可能命中少或无正文(登录墙/反爬)——这是预期,改用 App Store/Google Play/G2 等可达评价面,知乎/小红书作尽力而为。
- **NO-GO**:若 Tavily 对中文竞品几乎全空,切 Exa(`exa-py`)或 Firecrawl 再跑同一组 PROBES 对比。
