# RivalRadar

> AI 多 Agent 竞品分析系统 — 输入产品名和竞品列表,自动采集、分析、撰写、质检,输出结构化竞品报告。

---

## 架构概览(4 Agent 协作)

```
POST /run
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                     │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐  │
│  │ Collector│──►│ Analyst  │──►│  Writer  │──►│   QC   │  │
│  │  Agent   │   │  Agent   │   │  Agent   │   │  Agent │  │
│  └──────────┘   └──────────┘   └──────────┘   └────┬───┘  │
│       ▲              │                              │       │
│       │       Doubao function-calling               │       │
│       │       Tavily / Exa search                  │       │
│       │                                             │       │
│       └────────────── 闭环重试(最多 2 轮) ◄──────────┘       │
│                      QC 不通过 → 重写                        │
│                      QC 通过 → finalize                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
GET /stream/:run_id  (SSE 实时推流)
```

**4 个 Agent 职责：**

| Agent | 职责 |
|---|---|
| Collector | 按维度 × 语言并行搜索(Tavily 主 / Exa 兜底),提取 Evidence |
| Analyst | Doubao function-calling 结构化抽取(features / pricing / personas / SWOT),生成对比矩阵 |
| Writer | 确定性 Markdown 渲染 + LLM grounded 导语,生成完整报告 |
| QC | 确定性闸(traceability / ontology / coverage)+ LLM 蕴含校验,verdict 决策 |

---

## 快速开始

### 1. 克隆与安装

```bash
git clone https://github.com/Billkst/RivalRadar.git
cd RivalRadar
python -m venv .venv
.venv/bin/pip install -e .
```

### 2. 配置环境变量

在项目根目录新建 `.env` 文件,填入以下变量名对应的值:

```
ARK_API_KEY=          # 必填,Doubao API key(字节跳动 ARK 平台)
TAVILY_API_KEY=        # 必填(或 EXA_API_KEY)
EXA_API_KEY=           # 可选,Tavily 主 / Exa 兜底
RIVALRADAR_DB=         # 可选,默认 rivalradar.db
RIVALRADAR_PORT=       # 可选,默认 8000
RIVALRADAR_HOST=       # 可选,默认 127.0.0.1(跨主机访问设 0.0.0.0)
```

> **KEY 纪律**:`.env` 已加入 `.gitignore`,绝不提交到仓库。泄露 API key 违反比赛规则且会被即刻取消资格。`/healthz` 端点只返回 `{"ok": true}`,绝不暴露 key 值。

### 3. 启动服务

```bash
.venv/bin/python main.py
```

服务默认监听 `http://127.0.0.1:8000`。

---

## API 端点(9 个)

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/run` | 发起竞品分析任务,同步 SSE 流式返回 |
| `GET` | `/stream/{run_id}` | 重放已完成 run 的 SSE 事件(replay 路径) |
| `GET` | `/runs` | 列出所有 run 摘要(含 `degraded` 字段) |
| `GET` | `/run/{run_id}` | 获取单个 run 详情 |
| `GET` | `/evidence/{evidence_id}` | 获取单条证据 |
| `GET` | `/analysis/{run_id}` | 获取结构化分析结果 |
| `GET` | `/report/{run_id}` | 获取 Markdown 报告 |
| `GET` | `/trace/{run_id}` | 获取 LangGraph 节点执行 trace |
| `POST` | `/annotations` | 添加人工质疑标注(§17 质疑率统计) |
| `GET` | `/healthz` | 健康检查 |

**SSE 事件类型:**`start` / `node` / `error` / `done` / `trace`

**请求体示例(`POST /run`):**

```json
{
  "product": "我的 SaaS 产品",
  "competitors": ["竞品A", "竞品B"],
  "dimensions": ["features", "pricing"]
}
```

限制:`competitors` ≤ 5,`dimensions` ≤ 6,每个字符串 1-200 字符。

---

## 运行测试

```bash
.venv/bin/python -m pytest
```

198 个测试,约 7 秒。测试覆盖率 94%(58/62 路径)。

---

## 技术栈

| 层 | 技术 |
|---|---|
| API 框架 | FastAPI + sse-starlette(SSE 推流) |
| Agent 编排 | LangGraph `StateGraph`(5 节点 + 5 分支路由 + SqliteSaver checkpointer) |
| LLM | Doubao(字节跳动 ARK 平台,function-calling / tools 路径) |
| 搜索 | Tavily(主)+ Exa(兜底),`FallbackSearch` 自动切换 |
| 存储 | SQLite,WAL 模式,5 表 schema(`runs / evidence / analysis / report / trace`)+ `annotations` |
| 数据校验 | Pydantic v2,`Evidence / CompetitorAnalysis / QCResult` schema |
| 依赖管理 | `pyproject.toml`(PEP 517),Python ≥ 3.11 |

---

## 项目结构

```
rivalradar/
  agents/      # 4 个 Agent(collector / analyst / writer / qc)
  api/         # FastAPI 路由(runs / reads / annotations / sse)
  collect/     # 采集管线(搜索 + safe_fetch + 速率限制)
  graph/       # LangGraph StateGraph + 路由逻辑
  llm/         # Doubao structured_call 包装器
  schema/      # Pydantic schema(Evidence / CompetitorAnalysis / QCResult)
  search/      # SearchProvider 协议 + TavilyProvider + ExaProvider + FallbackSearch
  storage/     # SQLite repository + SqliteSaver checkpointer 工厂
  config.py    # 环境变量读取(永不暴露 key 值)
tests/         # 198 个测试
spikes/        # 真打 Doubao/Tavily 端到端 spike(含 SPIKE_RESULTS.md)
docs/superpowers/specs/  # 设计规格
main.py        # 服务入口
```

---

## 相关文档

| 文件 | 内容 |
|---|---|
| [`CHANGELOG.md`](CHANGELOG.md) | 版本历史,v0.1.0.0 首次发布 |
| [`TODOS.md`](TODOS.md) | 21 个非阻断遗留事项(P1-P4) |
| [`DESIGN.md`](DESIGN.md) | Lane F 前端设计系统(字体/配色/间距/动效) |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | 数据来源合规声明 |
| [`SKILLS.md`](SKILLS.md) | Claude Code skill 速查手册 |
| [`docs/superpowers/specs/2026-05-21-rivalradar-design.md`](docs/superpowers/specs/2026-05-21-rivalradar-design.md) | 完整设计规格 |

---

## 版本

当前版本: **v0.1.0.0**(首次完整发布,2026-05-26)

版本格式:`MAJOR.MINOR.PATCH.MICRO`(< 1.0 表 API 未稳定,允许 breaking changes)

---

## License

见 [`LICENSE`](LICENSE) 文件。
