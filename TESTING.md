# RivalRadar 测试指南

## 快速运行

```bash
.venv/bin/python -m pytest
```

198 个测试,约 7 秒。无任何外部依赖(全部 mock)。

```bash
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
  test_db.py                  # SQLite 5 表 schema + repository CRUD + 复合 PK
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
  test_graph_regression.py    # ★★★ 真闭环回归(improve→pass + exhaust→insufficient)

  # API 层
  test_api_app.py             # app 工厂 + /healthz
  test_api_runs.py            # POST /run + GET /runs + GET /run/:id
  test_api_sse.py             # SSE live + replay,event 类型校验
  test_api_reads.py           # evidence / analysis / report / trace 端点
  test_api_annotations.py     # POST /annotations + run_id 404 校验
  test_api_concurrent.py      # WAL 并发读写安全
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

---

## 已知测试缺口

见 [`TODOS.md`](TODOS.md) 中"测试 / 质量 / 评测"节。主要:

- **eval 框架**:LLM 输出质量自动评测(当前靠人工看 spike 结果)
- **高强度并发写写**:`PRAGMA busy_timeout` 未设,高强度争用会 `OperationalError`
- **SDK timeout 路径**:Tavily/Exa/Doubao 超时映射成 sanitized error event 未覆盖
- **Lane F 前端 E2E**:React + SSE 集成测试,待 Lane F 实现后补
