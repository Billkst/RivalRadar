# TODOS

非阻断遗留与计划事项。按 gstack `TODOS-format`:`## <组件>` 分组,每项标 `**Priority:**`(P0 阻断→P4 nice-to-have),已完成移到底部 `## Completed`。

---

## 部署 / 投产硬化

### CI/CD pipeline(`.github/workflows/test.yml`)
**Priority:** P1
**详情:** 当前无 CI,PR 测试只靠本地 `.venv/bin/python -m pytest`。建议加 GitHub Actions workflow(setup-python 3.11 + 安装依赖 + 跑 pytest + 跑 coverage report)。模板:`ubuntu-latest` + `actions/setup-python@v5` + `pip install -e .` + `pytest`。
**触发:** push + pull_request。

### SQLite `PRAGMA busy_timeout` 设置
**Priority:** P1
**详情:** WAL 允许并发读 + 单写,但**两个**并发写在第二个 writer 上立即 `OperationalError: database is locked`(无超时等待)。`test_concurrent_two_posts_no_busy` 在低强度通过,高强度会触发。加 `conn.execute("PRAGMA busy_timeout=5000")` 在 `connect()` 内,让短暂争用透明 block 5s 后再 fail。

### SDK 调用 timeout
**Priority:** P2
**详情:** `TavilyProvider.search()` / `ExaProvider.search()` / `structured_call()`(OpenAI SDK)使用各 SDK 默认 timeout。一个挂死的 provider 会让 SSE 请求 + DB conn 长时间占用。加显式 `connect/read/request` 截止时间,超时统一映射成 sanitize 后的 `timeout` 错误事件(Codex Medium #5)。

### `safe_fetch` 接入采集管线 + `httpx.Client` 生命周期
**Priority:** P2
**详情:** `rivalradar/collect/fetch.py` 写了 `safe_fetch + RateLimiter`,但当前 pipeline 直接 `provider.search()` 不走自抓 — dead code(maintainability specialist + Codex 都揪到)。要么接入(`source_url` 抓回 raw_content fallback),要么用 module docstring 标"Day-4 待接入"。同时 `httpx.Client` 创建后没 `__exit__`,fd leak(Codex Medium #6)— 用 `with httpx.Client() as c:` 上下文管理。

### SSRF 私有 IP 段过滤
**Priority:** P2
**详情:** `safe_fetch + follow_redirects=True` 可能跟随重定向到 `169.254.169.254` 元数据服务等内网地址(security specialist Medium #2)。在 `is_self_fetch_allowed` 或 `safe_fetch` 内加私有 IP 段过滤(`127.x / 10.x / 192.168.x / 169.254.x`)。当前 demo 阶段 URL 来自 Tavily/Exa 不直接用户控制,风险低。

### 多 ThreadPool 单一失败不应 abort 整轮
**Priority:** P2
**详情:** `collect/pipeline.py` 用 `pool.map(...)`,一个 query 失败抛异常会让整个迭代器 abort,丢掉其他已成功结果(adversarial opus + Codex Medium #4 都揪到)。改用 `pool.submit + as_completed + try/except`,记 failed query summary,继续。

### POST /annotations auth
**Priority:** P3
**详情:** 当前 demo 走 localhost,无 token / session 校验(plan 已确认 acceptable for 比赛)。投产前加简单 header token(从 env 读 `RIVALRADAR_ANNOTATION_TOKEN`)。

### nginx `X-Accel-Buffering: no` 配置
**Priority:** P3
**详情:** sse-starlette 不会自动给 SSE 响应加 `X-Accel-Buffering: no` header。生产部署若过 nginx 反向代理需配 `proxy_buffering off`,否则 SSE 事件会被 buffer 直到响应结束(前端动画完全失效)。

---

## graph 编排

### SqliteSaver checkpointer 绑入 Lane E
**Priority:** P2
**详情:** Lane E 跳过 SqliteSaver(用 trace 表回放代替),Day-4 真要"中断恢复 / 时间旅行"再启用独立 `checkpointer.db` 文件或换 `PostgresSaver`。当前所有 9 端点 + SSE replay 都自洽。

### retry 换 provider(Tavily ↔ Exa)= CRAG `web_search` fallback
**Priority:** P3
**详情:** Lane D 计划中标 P2 TODO。当前 `retry_collect` 用 `broaden=True` 拓宽查询,但仍用同一 provider。多样化策略:retry 时强制切换备用 provider(`FallbackSearch` 内重排序),减少同源失败相关性。

### `make_finalize_node(max_retries)` 形参未使用
**Priority:** P3
**详情:** Lane D 计划遗留:`max_retries` 形参在 `finalize` 节点中保留但未被引用(router 已基于 `retry_count >= max_retries` 决策入 finalize)。要么用上(在 finalize 内做兜底 sanity check),要么删了避免误导读者。

### `evidence_runs` 关联表 + evidence 全局 dedup
**Priority:** P3
**详情:** 当前 schema `PRIMARY KEY (run_id, id)` 让 evidence 跨 run 各存一份(2 倍 storage 同源 URL)。更优:`evidence` 全局唯一 + `evidence_runs(run_id, evidence_id)` join 表,storage 节省。当前 surgical 修复(ship round-2)已 OK,Day-4 优化。

---

## QC + Agents

### `check_entailment` 多竞品并行/抽样降本
**Priority:** P3
**详情:** spec §13 ⑤ 必办项,Lane E plan 含 TODO(`rivalradar/graph/nodes.py:101` 注释)。当前 `check_entailment` 调用数 = 结论数 × 竞品数,N 个竞品 × M 个 pricing 维度 → N × M 次 LLM 调用。考虑:① 并行(`asyncio.gather` over chunks);② 抽样(每竞品抽 K 个结论)。Day-4 真跑大数据集再优化。

### LLM 输出 `quote` 字段未做 verbatim 校验
**Priority:** P3
**详情:** `check_traceability` 只验 `evidence_id` 存在,不校验 `quote` 是否真在 `evidence.content` 中(adversarial opus 揪到)。LLM 可绑真 `evidence_id` 但伪造 `quote`。修法:`check_traceability` 内加 `quote in evidence.content` 子串校验 — flag 为 `missing_evidence` if absent。低概率,Day-4。

### LLM prompt injection 边界标记
**Priority:** P3
**详情:** `build_evidence_block` 直接 f-string 注入 evidence content(可能含恶意网页 prompt 指令)。当前缓解:function-calling 强结构 + Pydantic 校验 + `check_traceability`。Day-4 加 XML-like 边界标记包裹 evidence content(`<EVIDENCE id=x>...</EVIDENCE>`),降低跨块注入难度。

### `PricingModel.model_type` 自由串
**Priority:** P3
**详情:** spec 已 acknowledged,可保持自由串(LLM 输出灵活),但前端展示时可能出现 `"按月订阅"` / `"按用户付费"` 等中文 vs 英文枚举不一致。Day-4 加映射表归一。

### 撰写 LLM 导语散文忠实度仅 prompt 约束
**Priority:** P4
**详情:** `writer._generate_summary` LLM 生成时只靠 prompt 约束"严格按数据写"。无 post-hoc 校验。Day-4 加 entailment-like 校验导语句对应 analysis 数据。

### dimensions enum 校验(API 边界拒非 CONTROLLED)
**Priority:** P3
**详情:** Codex High #3 提到:`RunRequest.dimensions` 不限定值在 `CONTROLLED_DIMENSIONS`,任意 dimension 触发 `_generic` query template 后被 QC `check_ontology` 捕获 → 浪费一轮 LLM 调用。修法:`Annotated[str, AfterValidator(lambda x: x if x in CONTROLLED_DIMENSIONS else raise)]` 或 Literal 枚举。

---

## API + SSE

### SSE 连接级 rate limit
**Priority:** P3
**详情:** `POST /run` 当前无限制(单 IP 可连发起 N 个 SSE,各自烧 LLM / 搜索)。加 `slowapi` 或简单 in-process per-IP counter,1 run / 60s。投产前必加。

### `GET /runs` 分页
**Priority:** P3
**详情:** repository 层 `list_runs` 已有 `limit=50` 上限,但 API 不暴露 `limit/offset` 参数,也不返回 total count。run 数超 50 客户端无法翻页。加 `limit: int = Query(50, le=200)` + 响应 `X-Total-Count` header。

### `GET /report/:run` 无 `response_model`
**Priority:** P3
**详情:** 当前返裸 `{"run_id", "markdown"}` dict,OpenAPI 文档该端点响应类型为空。加 `ReportOut(BaseModel)` 并声明 `response_model=ReportOut`(api-contract specialist 提议)。

### SSE 端点 `response_class` 声明
**Priority:** P4
**详情:** `POST /run` / `GET /stream` 无 `response_class=EventSourceResponse`,FastAPI OpenAPI 文档无法标 `text/event-stream` content-type。加 `response_class` 让 `/docs` 正确呈现。

### `_now()` DRY 提取
**Priority:** P4
**详情:** `rivalradar/api/sse.py:25` 和 `rivalradar/storage/repository.py:10` 都定义同一个 `datetime.now(timezone.utc).isoformat()`。提到 `rivalradar/utils.py` 或 `db.py` 共用。

### `runs.py` 内冗余 import
**Priority:** P4
**详情:** `from rivalradar.storage.repository import create_run` + `get_run as _get_run` 与 `from rivalradar.storage import repository as repo` 重复,合并成单 `repo.create_run` / `repo.get_run`。

### Magic numbers 提常量
**Priority:** P4
**详情:** `analyst.py:39` 的 `[:1200]`、`qc.py:106` 的 `[:600]`、`runs.py:49+63` 的 `ping=15` 都是裸字面量。提模块级常量(`_EVIDENCE_SNIPPET_CHARS / _ENTAILMENT_QUOTE_CHARS / _SSE_PING_SECONDS`)。

### 4 个 read endpoint 加 docstring
**Priority:** P4
**详情:** `reads.py` 的 `get_evidence / get_analysis / get_report / get_trace` 函数无 docstring。FastAPI 会把 docstring 渲染为 OpenAPI 端点描述,Swagger UI 当前为空。

---

## 测试

### 测试 flakiness
**Priority:** P3
**详情:** `test_api_concurrent.py:95` 用 40 × 50ms = 2s polling 找 run_id,慢 CI 上可能未来得及 `create_run`(testing specialist Flaky)。改为 `threading.Event` signal 消除时序依赖。`prev_len >= 1` 假设 600ms 窗口能看到至少 1 个 evidence,慢机可能 miss。

### LLM prompt 模板 eval framework
**Priority:** P2
**详情:** 项目无 eval framework,LLM prompt 改动只能手工评估输出质量。Day-4 加简单 eval suite(预设输入 → 期望输出 schema + 抽样断言)。

### 弱测试断言加强
**Priority:** P4
**详情:** testing specialist 揪到若干 `is not None` / `len > 0` 弱断言,可加值校验。已知具体点:
- `test_analyze_node`:`assert repo.get_analysis() is not None` → 加 `competitors[0].name == "Notion"`
- `test_post_run_persists_state_after_stream`:加 report content 校验
- `test_get_stream_replays_finished_run`:删 `len > 0` 弱前置(已被后续精确 for-n 检查覆盖)
- `test_evidence_builder.py:19`:`assert ev.fetched_at` → 加 `datetime.fromisoformat()` 验 ISO 格式

---

## 文档

### CLAUDE.md 加 `## Testing` section
**Priority:** P4
**详情:** ship 自动 bootstrap 检测到无 `## Testing` 但跳过(因为已有 pytest)。手工加一段:`.venv/bin/python -m pytest` 命令 + TESTING.md 链接 + 测试期望(100% coverage 目标、新功能加测试、修 bug 加回归测试、加分支加双路径测试)。

### TESTING.md 创建
**Priority:** P4
**详情:** 写测试 philosophy + 框架(pytest)+ 命令 + 分层(unit / integration / spike)+ conventions(naming / fixtures / monkeypatch / KEY 纪律)。

---

## Lane F frontend(post-ship review 发现 / 残留)

### Writer agent 真打 LLM 改 stream_chat — "招牌时刻 typing" production 体感
**Priority:** P1
**详情:** 当前 `rivalradar/agents/writer.py` 用 `structured_call`(JSON-mode);chunk events 只在 demo fixture 路径走 fakeSSEPlayer 替身才有。real backend 跑时 writer 不 emit chunks → ReportSheet 走 fetchReport fallback 一次性 pop full markdown,看不到 typing 动画。Demo day 若用 real backend 演示(Clash 通畅时),"招牌时刻 #3 typing" 体感缺失。改造方案:writer 把 narrative 段(导语)切到 `llm/streaming.py:stream_chat` + emit chunk per delta(structured 部分仍走 `structured_call`)。≈ 2h 工程,demo day 后 v0.2.x patch 加。

### Lane F frontend E2E test framework
**Priority:** P1
**详情:** 当前 `frontend/package.json` `"test": "echo \"Vitest TBD\" && exit 0"` 占位。tsc 抓不到 runtime bug(zustand selector 死循环 / fakeSSEPlayer ts 计算 / SpeechBubble fallback / etc 全 spike 才暴露)。Vitest + @testing-library/react + Playwright smoke 一套。≈ 8h bootstrap + 持续补测。demo day 后 v0.2.x 加。

### useSSE.ts parseSSE 漏 `'cancelled'` event 类型
**Priority:** P2
**详情:** backend `sse.py` 在 CancelledError 分支 yield `{"event": "cancelled", ...}`,但 `parseSSE` 只解析 `start|node|trace|progress|chunk|error|done`,unknown 静默 drop。今天 user-initiated cancel 走 CancelButton finally 的 `cancelStoreRun()` 让 UI 立即响应,所以不阻塞。但 server-initiated cancel(future:管理员强制停 / 第二个浏览器 tab 同步)看不到。修法:加 `case 'cancelled': return { type: 'cancelled', data }` + SSEEvent variant + runStore handler。或者文档明确舍弃 server 'cancelled' event,从 sse.py 移除 yield。

### dimensions enum API 边界拒非 CONTROLLED(提升优先级)
**Priority:** P2
**详情:** `rivalradar/api/schemas.py:27` validate 长度但不验值。frontend checkbox 限制 user 只能选 6 个 controlled value,但 `POST /run` 直接发 `{"dimensions": ["exploit"]}` 接受。defense-in-depth 改 `Literal[*CONTROLLED_DIMENSIONS]` 或 Pydantic validator。

### runStore.cancelRun 不清 running nodes / handoffQueue
**Priority:** P3
**详情:** cancel 后 `status='cancelled'` 但 `nodes[X]='running'` + `handoffQueue` 仍非空 → VirtualOfficeView ripple ring 继续转 / handoff 还能 mount。视觉跟 "已停止" 语义矛盾。修法:`cancelRun` action 同时把 running/retrying node force 'idle' + clear handoffQueue。

### ReportSheet useEffect status guard 减 404 噪音
**Priority:** P4
**详情:** `useEffect [runId, writerReport.length, status]` 在 real backend run idle→running 时触发一次,`fetchReport` 404(报告未生成)→ `.catch(() => {})` 静默 swallow。功能正常但每个 run 给后端日志加一条 bogus 404 + UI 一闪 "等待 writer agent 输出"。修法:`if (status !== 'done' && status !== 'degraded' && status !== 'insufficient_evidence') return` guard。

### perAgentNarrative 数组无界
**Priority:** P4
**详情:** `runStore.perAgentNarrative[agentId]` 数组只增不删。当前每 agent ~3-20 entry,demo 规模 OK。多次 retry storm 场景下值得 `slice(-50)` 兜底(对称 typingStore 限长 pattern)。

---

## Completed

- post-ship review 5 fix(demo fixture ai_features → target_users · DagDrawer demo bypass · CancelButton demo early-return · StatusBadge 'cancelled' 中文 label · finalize CAS guard 防 cancel race) — **Completed:** v0.2.0.0 (2026-05-28)
- Lane F frontend 完整交付(虚拟办公室 paradigm + Epic 0-7 + demo fixture + lighthouse 100 + codex 4 fix) — **Completed:** v0.2.0.0 (2026-05-28)
- 项目首次 ship + Lane A→E 完整发布 — **Completed:** v0.1.0.0 (2026-05-26)
