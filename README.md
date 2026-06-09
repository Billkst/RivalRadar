# RivalRadar

> AI 多 Agent 竞品分析系统 — 输入产品名和竞品列表,自动采集、分析、撰写、质检,输出结构化竞品报告。

---

## 架构概览(6 节点 StateGraph · 全过程实时可见)

```
POST /run  ──►  SSE 实时流式返回(采集→分析→撰写→质检 全过程可见)
    │
    ▼
  LangGraph StateGraph · 6 节点
  collect ─► analyze ─► write ─► qc ─► decide ─► finalize
     ▲          ▲              │
     │  Doubao function-calling │  qc 不通过 → 重写 / 补采(闭环 ≤2 轮)
     │  Tavily 主 / Exa 兜底     │  qc 通过   → 策展(丢不支撑格)→ decide 合成决策
     └──────── 闭环重试 ◄───────┘
    │
    ▼  每步中间产物逐条实时推送(query · source · cell_row · verdict_recheck …)
GET /stream/:run_id  ──►  从持久化状态重建过程事件(刷新 / 深链回放)
```

**6 节点职责：**

| 节点 | 职责 |
|---|---|
| collect | 按维度 × 语言并行搜索(Tavily 主 / Exa 兜底),提取 Evidence,逐条 emit 检索词 / 来源 |
| analyze | Doubao function-calling 结构化抽取(features / pricing / personas / SWOT)+ 对比纪律(`_COMPARE_RULE`:禁跨产品口径混写 / 派生营销数字),逐维生成对比矩阵 cell |
| write | 确定性 Markdown 渲染 + LLM grounded 导语(两步式流式起草),生成完整报告 |
| qc | 策展人模型:逐格裁决 `support_verdict` 三色(充分 / 部分 / 不支撑),丢不支撑格记 `curation_drops`、缺格显「—」+ 覆盖说明(防虚构硬门不变) |
| decide | 基于策展后证据合成决策建议(决策级三色 + 因果桥) |

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
RIVALRADAR_RUN_BUDGET_S=  # 可选,默认 900,单 run 墙钟预算(秒);超时中止防卡死
```

> **KEY 纪律**:`.env` 已加入 `.gitignore`,绝不提交到仓库。泄露 API key 违反比赛规则且会被即刻取消资格。`/healthz` 端点只返回 `{"ok": true}`,绝不暴露 key 值。

### 3. 启动服务

仓库已封装好启动脚本(自动处理 WSL2 + Clash 代理兜底,从任意目录运行均可)。**前后端各开一个终端**:

```bash
# 终端 1 —— 后端 FastAPI(http://127.0.0.1:8000)
./scripts/dev-backend.sh

# 终端 2 —— 前端 Vite(http://localhost:3000,/api/* 自动代理到后端)
./scripts/dev-frontend.sh
```

打开 **http://localhost:3000** 即入口。停止两个服务:

```bash
./scripts/stop-dev.sh        # 按端口精确 kill :8000 与 :3000
```

> **两个要点**
> - **后端无 `--reload`**:改了 `rivalradar/**` 或 `main.py` 后,必须重启 `dev-backend.sh` 才生效(前端 HMR 会自动热更,无需重启)。
> - **WSL2 + Clash**:脚本已自动 `unset` 代理变量并把 `ark.cn-beijing.volces.com`(Doubao)/ `api.tavily.com` 加入 `NO_PROXY`,否则 LLM 调用会被 fake-ip 路由卡死。手动起服务时也需照此处理。
>
> 只跑后端也可直接:`.venv/bin/python main.py`(默认监听 `http://127.0.0.1:8000`)。

---

## API 端点(20 路由)

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/run` | 发起竞品分析任务,同步 SSE 流式返回 |
| `POST` | `/discover-competitors` | 由产品名发现候选竞品 |
| `GET` | `/stream/{run_id}` | 重放已完成 run 的富过程事件(replay 路径) |
| `GET` | `/runs` | 列出所有 run 摘要(含 `degraded` 字段) |
| `GET` | `/run/{run_id}` | 获取单个 run 详情 |
| `POST` | `/run/{run_id}/cancel` | 取消进行中的 run(协作式停掉在飞 LLM) |
| `GET` | `/runs/{run_id}/queries` | 真检索词列表(逐条 query + 命中数) |
| `GET` | `/runs/{run_id}/evidence` | 该 run 的全部证据 |
| `GET` | `/runs/{run_id}/curation-drops` | 质检策展丢弃的格子(三级佐证) |
| `GET` | `/evidence/{evidence_id}` | 获取单条证据 |
| `GET` | `/analysis/{run_id}` | 获取结构化分析结果(含 cell 三色) |
| `GET` | `/decisions/{run_id}` | 决策建议(决策级三色) |
| `GET` | `/insight/{run_id}` | AI 综合判断 headline(3 段) |
| `GET` | `/report/{run_id}` | 获取 Markdown 报告 |
| `GET` | `/qc/{run_id}` | 质检结果(verdict + 缺口) |
| `GET` | `/trace/{run_id}` | 获取 LangGraph 节点执行 trace |
| `GET`·`PUT`·`DELETE` | `/agent-skills[/{agent_id}/{skill_id}]` | Agent 技能目录子系统 |
| `POST` | `/annotations` | 添加人工质疑标注(§17 质疑率统计) |
| `GET` | `/healthz` | 健康检查 |

**SSE 事件类型:**
- Live `POST /run`:`start` / `node` / `query` / `query_hit` / `source` / `cell_row` / `verdict_recheck` / `error` / `cancelled` / `done`
- Replay `GET /stream/:run_id`:从持久化 trace / 证据重建 `start` / `trace` / 检索台 / 来源 / 矩阵 / 重试环 / `done`

**请求体示例(`POST /run`):**

```json
{
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

401 个测试,约 10 秒通过。

---

## 技术栈

| 层 | 技术 |
|---|---|
| API 框架 | FastAPI + sse-starlette(SSE 推流) |
| Agent 编排 | LangGraph `StateGraph`(6 节点 collect/analyze/write/qc/decide/finalize + 分支路由 + SqliteSaver checkpointer) |
| LLM | Doubao(字节跳动 ARK 平台,function-calling / tools 路径) |
| 搜索 | Tavily(主)+ Exa(兜底),`FallbackSearch` 自动切换 |
| 存储 | SQLite,WAL 模式,12 表 schema(`runs / evidence / analysis / decisions / insight / qc_result / report / trace / annotations / queries / curation_drops / agent_skills`) |
| 前端 | React 19 + Vite + Tailwind 3 + Zustand 5 + framer-motion(SSE 实时工作台 + 决策座舱) |
| 数据校验 | Pydantic v2,`Evidence / CompetitorAnalysis / QCResult` schema |
| 依赖管理 | `pyproject.toml`(PEP 517),Python ≥ 3.11 |

---

## 项目结构

```
rivalradar/
  agents/      # Agent 角色(collector / analyst / writer / qc;decide 决策合成见 graph/)
  api/         # FastAPI 路由(runs / reads / annotations / sse / agent_skills)
  collect/     # 采集管线(搜索 + safe_fetch + 速率限制)
  graph/       # LangGraph StateGraph + 路由逻辑
  llm/         # Doubao structured_call 包装器
  schema/      # Pydantic schema(Evidence / CompetitorAnalysis / QCResult)
  search/      # SearchProvider 协议 + TavilyProvider + ExaProvider + FallbackSearch
  storage/     # SQLite repository + SqliteSaver checkpointer 工厂
  config.py    # 环境变量读取(永不暴露 key 值)
tests/         # 401 个测试
spikes/        # 真打 Doubao/Tavily 端到端 spike(含 SPIKE_RESULTS.md)
docs/superpowers/specs/  # 设计规格
main.py        # 服务入口
```

---

## 相关文档

| 文件 | 内容 |
|---|---|
| [`CHANGELOG.md`](CHANGELOG.md) | 版本历史,最新 v0.6.0.0 |
| [`TODOS.md`](TODOS.md) | 非阻断遗留事项(按组 + P0-P4) |
| [`DESIGN.md`](DESIGN.md) | 前端设计系统 v5(字体 / 配色 / 间距 / 动效 / 决策座舱) |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | 数据来源合规声明 |
| [`SKILLS.md`](SKILLS.md) | Claude Code skill 速查手册 |
| [`docs/superpowers/specs/2026-05-21-rivalradar-design.md`](docs/superpowers/specs/2026-05-21-rivalradar-design.md) | 完整设计规格 |

---

## 版本

当前版本: **v0.6.0.0**(过程可视化重做 + 实时引擎 + 三级佐证策展,2026-06-09)

版本格式:`MAJOR.MINOR.PATCH.MICRO`(< 1.0 表 API 未稳定,允许 breaking changes)

---

## License

见 [`LICENSE`](LICENSE) 文件。
