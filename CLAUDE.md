# Claude Code adapter

在本仓库开展任何工作前，必须先阅读并遵守
[`docs/agents/working-agreement.md`](docs/agents/working-agreement.md)。

恢复未完成工作时，同时阅读
[`docs/agents/handoff.md`](docs/agents/handoff.md) 和上一位维护者提供的本地
handoff 文件。

本文件只记录 Claude Code / gstack 专属规则及工程 skills 入口。通用工程规则
只维护在 `docs/agents/working-agreement.md`，不要在这里复制。

## gstack

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

## Agent skills

### Issue tracker

Issues 与 PRD 使用 GitHub Issues。见 `docs/agents/issue-tracker.md`。

### Triage labels

使用默认五类 triage 标签。见 `docs/agents/triage-labels.md`。

### Domain docs

本仓库采用 single-context：根目录 `CONTEXT.md`，系统级 ADR 位于
`docs/adr/`。见 `docs/agents/domain.md`。
