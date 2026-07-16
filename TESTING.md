# RivalRadar 测试指南

## 统一验证入口

```bash
./scripts/verify.sh backend   # 版本一致性 + 后端测试
./scripts/verify.sh frontend  # typecheck + lint + production build
./scripts/verify.sh all       # 默认值;执行以上全部
```

后端测试的外部服务调用全部 mock,并显式只扫描 `tests/`;不会运行 `spikes/`。
验证脚本会清空 API / 数据库相关环境变量,但保留当前代理环境。
`tests/conftest.py` 会在导入应用前禁用本机 `.env`,注入公开测试占位配置,并把
默认数据库重定向到临时目录;直接运行 pytest 也不会读取私密 endpoint 或写项目数据库。

若运行环境禁止本地 `socketpair` 通信,AnyIO / Starlette `TestClient` 无法唤醒
事件循环。脚本会在 pytest 前明确退出,避免表现为测试永久卡住;请改在正常终端或
允许本地进程间 socket 通信的 CI 中运行。

```bash
# 直接运行 pytest(调试或传递额外参数时)
.venv/bin/python -m pytest tests -p no:cacheprovider

# 只跑某个模块
.venv/bin/python -m pytest tests/test_api_runs.py -v

# 只跑某个测试函数
.venv/bin/python -m pytest tests/test_db.py::test_create_run -v

# 查看覆盖率
.venv/bin/python -m pytest --cov=rivalradar --cov-report=term-missing
```

---

## 框架 & 配置

- **pytest ≥ 8** + **pytest-asyncio ≥ 0.23**(`asyncio_mode = auto`,无需手动 `@pytest.mark.asyncio`)
- 配置在 `pyproject.toml` `[tool.pytest.ini_options]`:
  - `pythonpath = ["."]` — 让 `rivalradar` 包在测试中可直接 import
  - `testpaths = ["tests"]` — 只扫 `tests/` 目录

---

## tests/ 目录布局

```
tests/
  # 配置与基础设施
  test_config.py              # 环境变量读取,KEY 纪律 bool 检查
  test_db.py                  # SQLite/Postgres schema + repository CRUD + 复合 PK + _RUN_SCOPED_TABLES 完整性
  test_checkpointer.py        # SqliteSaver checkpointer 工厂

  # LLM 层
  test_doubao_schema.py       # Pydantic schema + to_doubao_schema $ref 内联
  test_structured_call.py     # structured_call validate-retry + error 路径

  # 采集层
  test_tavily_provider.py     # TavilyProvider mock
  test_exa_provider.py        # ExaProvider mock
  test_fallback.py            # FallbackSearch 主→兜底切换逻辑
  test_fetch.py               # safe_fetch + RateLimiter 速率限制
  test_collect_pipeline.py    # 并行 collect() 管线
  test_search_base.py         # SearchProvider 协议 + 基础行为

  # Agent 层
  test_evidence_builder.py    # Evidence id 稳定性 + 域名优先级排序
  test_feature_tree.py        # features 结构化抽取辅助
  test_analyst_agent.py       # Analyst: 结构化抽取 + 对比矩阵
  test_writer_agent.py        # Writer: 确定性 Markdown 渲染 + LLM 导语
  test_collector_agent.py     # Collector Agent 集成

  # Graph 编排
  test_graph_build.py         # StateGraph 构建 + 节点注册
  test_graph_loop.py          # ★★★ 真闭环回归(improve→pass + exhaust→insufficient)

  # API 层
  test_api_app.py             # app 工厂 + /healthz
  test_api_runs.py            # POST /run + GET /runs + GET /run/:id
  test_api_sse.py             # SSE live + replay,event 类型校验
  test_api_reads.py           # evidence / analysis / report / trace 端点
  test_api_annotations.py     # POST /annotations + run_id 404 校验
  test_api_concurrent.py      # WAL 并发读写安全
  test_api_cancel.py          # POST /run/:id/cancel 取消路径

  # v0.6 过程可视化 / 三级佐证 / 技能子系统
  test_queries_repo.py        # queries 表 repository(真检索词 + 命中数)
  test_curation_drops_repo.py # curation_drops 策展丢弃记录(三级佐证)
  test_collect_node_emit.py   # 采集节点 SSE emit(query / source / evidence_delta)
  test_sse_schemas.py         # SSE 事件各类型 payload Pydantic schema
  test_replay_parity.py       # replay 与真 run 富过程事件等价
  test_agent_skills.py        # agent_skills 表 + REST 技能目录子系统
  test_runcontrol.py          # RunControl 墙钟预算 + 协作式取消
  test_evals.py               # LLM 输出质量评测框架(可溯源 / 反套话门)

  # (以上为代表性列举;以 tests/ 现场收集结果为准)
```

---

## 核心测试约定

### 1. KEY 纪律:绝不读 key 值

```python
# 正确:只检查是否配置
assert bool(config.ark_api_key())

# 错误:读取 key 并比较字符串(可能在日志里暴露)
assert config.ark_api_key() == "sk-..."
```

### 2. 外部调用全部 mock

```python
def test_tavily_search(monkeypatch):
    def fake_search(self, query, **kw):
        return [{"url": "https://example.com", "content": "fake"}]
    monkeypatch.setattr(TavilyClient, "search", fake_search)
    ...
```

Doubao、Tavily、Exa SDK 调用在单元测试中全部打桩。只有 `spikes/` 里的 spike 文件才真打外部 API。

### 3. SQLite 用 tmp_path 隔离

```python
def test_create_run(tmp_path):
    db = str(tmp_path / "test.db")
    repo = Repository(db)
    ...
```

每个测试函数独立 db 文件,防止测试间状态污染。

### 4. 条件分支两条都测

```python
def test_fallback_uses_primary(monkeypatch): ...     # 主成功,不用兜底
def test_fallback_switches_to_secondary(monkeypatch): ...  # 主失败,切兜底
def test_fallback_all_fail(monkeypatch): ...         # 主 + 兜底都失败 → 异常
```

### 5. Bug 修复先写回归测试

```python
# test_api_runs.py — evidence PRIMARY KEY 碰撞回归测试
def test_rerun_same_url_no_integrity_error(tmp_path):
    """复现 #fix: evidence composite PK — 第二次跑同 URL 不应 IntegrityError"""
    ...
```

---

## Spike vs 单元测试边界

| 位置 | 用途 | 是否进 pytest |
|---|---|---|
| `tests/` | 单元 + 集成测试,全 mock,CI 可跑 | 是 |
| `spikes/` | 真打外部 API,验证集成点 | 否(手动跑) |

spike 文件命名:如 `spikes/spike_doubao_e2e.py`。结果记录在 `spikes/SPIKE_RESULTS.md`。

**Postgres 方言路径**:repository 的方言统一(`ON CONFLICT`)在 SQLite 上由单测覆盖;Postgres 专属分支(`RETURNING id` / `fetched_at,id` 排序 / dict_row / 失败即 rollback / `PG_MIGRATIONS` 加列 + 进程内一次)由 `tests/test_token_usage.py` 的 fake-pg 连接单测校验语句序列,并由 `spikes/spike_supabase_crud.py` 真打 Supabase 验证(9 段 CRUD + 事务污染恢复,首尾自清理)。

---

## 前端验证边界

当前前端门禁是:

```bash
cd frontend
pnpm typecheck
pnpm lint
pnpm build
```

`pnpm test` 与 `pnpm lighthouse` 目前仍是成功退出的占位脚本,不属于有效验证,
统一脚本和 CI 都不会调用它们。真实 Vitest / E2E / Lighthouse 接入前,不得把占位
输出描述为测试或性能检查通过。

---

## CI

`.github/workflows/ci.yml` 在 push 到 `main` 和 pull request 时并行运行:

- Python 3.11 后端门禁(`./scripts/verify.sh backend`);
- Node 22.13 + pnpm 11.3.0 前端门禁(`./scripts/verify.sh frontend`)。

CI 不注入业务密钥,不访问真实 LLM、搜索服务或 Postgres。

---

## 已知测试缺口

见 [`TODOS.md`](TODOS.md) 中"测试 / 质量 / 评测"节。主要:

- **高强度并发写写**:`PRAGMA busy_timeout` 未设,高强度争用会 `OperationalError`
- **前端 E2E**:React + SSE 集成测试(实时工作台 / 决策座舱)仍无 E2E 框架

> 已闭合:eval 框架(`test_evals.py`:决策可溯源 / 反套话机械门)、SDK 超时 / 墙钟(`test_runcontrol.py` 墙钟预算 + 取消、`test_structured_call.py` SDK 错误路径)。
