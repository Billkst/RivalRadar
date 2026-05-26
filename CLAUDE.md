## 0. Response Language

**Always respond in Simplified Chinese.**

- All explanations, plans, clarifying questions, summaries, and final answers must be written in Simplified Chinese.
- Keep code, commands, file paths, API names, error messages, and quoted source text in their original language when necessary.
- If the user explicitly requests another language, follow the user's request for that response only.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. gstack

本项目使用 gstack 工具链。若本机尚未安装,先全局安装一次:

`git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup`(需要 bun;若缺可先 `npm install -g bun`)。

### 网页浏览(强制)

- 所有网页浏览、网页测试、截图、表单交互一律使用 gstack 的 `/browse` skill。
- **禁止**使用任何 `mcp__claude-in-chrome__*` 工具。

### 可用 skills

- `/office-hours` — YC 式头脑风暴,判断点子是否值得做(写代码前)
- `/plan-ceo-review` — CEO 视角的计划评审(野心与范围)
- `/plan-eng-review` — 工程经理视角的架构与执行计划评审
- `/plan-design-review` — 设计师视角的计划评审(实现前)
- `/design-consultation` — 设计系统/品牌规范,生成 DESIGN.md
- `/design-shotgun` — 生成多套设计变体并对比迭代
- `/design-html` — 把方案落成生产级 HTML/CSS
- `/review` — 落库前的 PR/diff 代码评审
- `/ship` — 跑测试、更新 CHANGELOG、提交、推送、建 PR
- `/land-and-deploy` — 合并 PR、等待 CI 与部署、校验生产健康
- `/canary` — 部署后金丝雀监控
- `/benchmark` — 网页性能回归检测
- `/browse` — 无头浏览器:导航、交互、截图、QA
- `/connect-chrome` — 启动可见的 GStack 浏览器窗口
- `/qa` — 系统化 QA 测试并修复 bug
- `/qa-only` — 只产出 QA 报告,不改代码
- `/design-review` — 线上视觉 QA 并修复
- `/setup-browser-cookies` — 导入真实浏览器 cookie 以测试登录态
- `/setup-deploy` — 配置部署设置并写入 CLAUDE.md
- `/setup-gbrain` — 配置 gbrain
- `/retro` — 工程周回顾
- `/investigate` — 系统化根因调试
- `/document-release` — 发版后文档同步
- `/document-generate` — 从零生成文档
- `/codex` — OpenAI Codex CLI 第二意见(评审/挑战/咨询)
- `/cso` — 安全审计(CSO 模式)
- `/autoplan` — 自动跑完 CEO/设计/工程/DX 全套计划评审
- `/plan-devex-review` — 开发者体验计划评审
- `/devex-review` — 线上开发者体验实测审计
- `/careful` — 危险命令安全护栏
- `/freeze` — 限制编辑范围到指定目录
- `/guard` — 全量安全模式(/careful + /freeze)
- `/unfreeze` — 解除 /freeze 的目录限制
- `/gstack-upgrade` — 升级 gstack 到最新版
- `/learn` — 管理项目的"学习记录"

## Design System

做任何视觉 / UI 决策前,先读 `DESIGN.md`。字体、配色、间距、布局、动效、美学方向都在那里定义。
未经用户明确同意不得偏离。QA 时标记任何不符合 `DESIGN.md` 的代码。

## Testing

**测试命令:**

```bash
.venv/bin/python -m pytest
```

198 个测试,约 7 秒通过。覆盖率 94%(58/62 路径)。

**测试哲学:**

- 目标 100% 路径覆盖。每个 bug 修复必须先写一个能复现 bug 的测试,再让测试通过。
- 分支必须两条都测:成功路径 + 失败路径,缺一不可。
- 新功能先写测试(TDD),不允许"以后补测试"。
- spike 文件(真打外部 API)放 `spikes/` 目录,不跑进 `pytest`。

**测试框架:**

- `pytest` + `pytest-asyncio`(asyncio_mode = auto)
- `monkeypatch` 打桩外部调用(Doubao、Tavily、Exa)
- `tmp_path` 隔离 SQLite db 文件,防测试间污染
- `bool(config.X)` 检查 key 是否配置,而非读取 key 值本身(KEY 纪律)

**测试目录布局:**

```
tests/
  test_config.py           # 配置层(环境变量读取)
  test_db.py               # SQLite schema + repository CRUD
  test_doubao_schema.py    # Pydantic schema + $ref 内联
  test_structured_call.py  # Doubao function-calling 包装器
  test_collect_pipeline.py # 采集管线(并行 + 速率限制)
  test_analyst_agent.py    # Analyst Agent 结构化抽取
  test_writer_agent.py     # Writer Agent Markdown 渲染
  test_qc_agent.py         # QC Agent 闸 + verdict
  test_graph_build.py      # LangGraph StateGraph 构建
  test_api_app.py          # FastAPI app 工厂 + 健康检查
  test_api_runs.py         # POST /run + GET /runs + GET /run/:id
  test_api_sse.py          # SSE 推流 + replay
  test_api_reads.py        # evidence / analysis / report / trace 端点
  test_api_annotations.py  # POST /annotations + run_id 存在校验
  test_api_concurrent.py   # WAL 并发写写安全
  ...                      # 其他单元 + 集成测试
```

**已知测试缺口(见 TODOS.md):**

- eval 框架(LLM 输出质量自动评测)
- 高强度并发写写(`busy_timeout` 竞争)
- SDK timeout / 熔断路径
- Lane F 前端 E2E 测试
