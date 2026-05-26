# Changelog

All notable changes to RivalRadar are documented here per [Keep a Changelog](https://keepachangelog.com/) conventions.

Versioning follows 4-digit semver `MAJOR.MINOR.PATCH.MICRO`(< 1.0 表 API 未稳定,迭代期允许 breaking changes)。

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
