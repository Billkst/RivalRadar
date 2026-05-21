# RivalRadar · Skill 速查手册

本项目当前可用的全部 Claude Code skill 清单、用法,以及一条尽量串联所有 skill 的全生命周期工作流。

## 怎么用 skill

- **主动调用**:在输入框敲 `/<名字>`,例如 `/qa`、`/ship`。
- **自动触发**:很多 skill 是「描述清楚需求,我自动调用」——你不必记命令。例如你说"这个 bug 怎么回事",我会走 `/investigate`;你说"帮我想个新功能",我会先走 `/brainstorming`。
- **命名**:gstack 用**扁平名**(`/qa` 而非 `/gstack-qa`);插件 skill 用 `/名字`(同名冲突时才加 `插件:` 前缀)。
- **网页操作铁律**:所有浏览/截图/表单一律走 `/browse`,**禁用** `mcp__claude-in-chrome__*`(见 `CLAUDE.md`)。

图例:🟢 你主动触发 · 🔵 我通常会主动调用 · ⚙️ 一次性配置类

来源:**gstack**(`~/.claude/skills/gstack/`)· **插件**(`.claude/settings.json` 已固化 12 个)· **superpowers** · **内置/全局**。

---

## 1. gstack(约 46 个)

### 1.1 浏览 / QA / 网页
| 命令 | 性质 | 用途 |
|---|---|---|
| `/browse` | 🟢🔵 | 无头浏览器:导航、点击、截图、断言、响应式/表单/弹窗测试 |
| `/connect-chrome` | 🟢 | 打开可见的 GStack 浏览器窗口,实时观察操作 |
| `/scrape` | 🟢 | 抓取网页数据为 JSON(只读;改动用浏览器交互) |
| `/skillify` | 🟢 | 把一次成功的 `/scrape` 固化成永久脚本(~200ms 复用) |
| `/qa` | 🟢🔵 | 系统化 QA 并**修复** bug,逐个原子提交+复验 |
| `/qa-only` | 🟢 | 只产出 QA 报告,不改代码 |
| `/design-review` | 🟢 | 线上视觉 QA(间距/层级/AI slop)并修复 |
| `/devex-review` | 🟢 | 线上开发者体验实测(文档/上手流程/CLI 帮助)打分 |
| `/benchmark` | 🟢 | 网页性能回归(Core Web Vitals、加载、包体) |
| `/canary` | 🟢 | 部署后金丝雀监控(控制台错误/性能/页面失败) |
| `/setup-browser-cookies` | ⚙️ | 导入真实浏览器 cookie 测登录态 |
| `/pair-agent` | 🟢 | 把远程 AI agent 接入你的浏览器 |

### 1.2 计划与评审(写代码前 / PR 前)
| 命令 | 性质 | 用途 |
|---|---|---|
| `/office-hours` | 🔵 | YC 式头脑风暴,判断点子值不值得做(在任何计划评审之前) |
| `/plan-ceo-review` | 🟢 | CEO 视角:野心与范围,找"10 分产品" |
| `/plan-eng-review` | 🟢 | 工程经理视角:架构、数据流、边界、测试覆盖 |
| `/plan-design-review` | 🟢 | 设计师视角的计划评审(实现前) |
| `/plan-devex-review` | 🟢 | 开发者体验视角的计划评审(API/CLI/SDK) |
| `/autoplan` | 🟢 | 自动跑完 CEO/设计/工程/DX 全套评审,末尾统一决策 |
| `/review` | 🟢🔵 | 落库前 diff 评审(SQL 安全、信任边界、副作用) |
| `/codex` | 🟢 | OpenAI Codex CLI 第二意见(评审/挑战/咨询) |
| `/plan-tune` | 🟢 | 调节各 skill 的提问敏感度与开发者画像 |

### 1.3 设计
| 命令 | 性质 | 用途 |
|---|---|---|
| `/design-consultation` | 🟢 | 设计系统/品牌规范 → 生成 `DESIGN.md` |
| `/design-shotgun` | 🟢 | 生成多套设计变体,开对比板迭代 |
| `/design-html` | 🟢 | 把方案落成生产级 HTML/CSS |

### 1.4 交付 / 部署
| 命令 | 性质 | 用途 |
|---|---|---|
| `/ship` | 🟢🔵 | 测试→评审 diff→改 CHANGELOG→提交→推送→建 PR |
| `/land-and-deploy` | 🟢 | 合并 PR→等 CI/部署→金丝雀校验生产健康 |
| `/setup-deploy` | ⚙️ | 探测部署平台、写部署配置进 `CLAUDE.md` |
| `/landing-report` | 🟢 | 发布队列看板(谁占了哪个版本槽、下一个该发什么) |

### 1.5 调试 / 质量 / 安全 / 复盘
| 命令 | 性质 | 用途 |
|---|---|---|
| `/investigate` | 🔵 | 系统化根因调试(四阶段;无根因不修) |
| `/cso` | 🟢 | 安全审计(密钥/供应链/CI/LLM/OWASP/STRIDE)——semgrep 停用后的安全主力 |
| `/health` | 🟢 | 代码质量仪表盘(类型/lint/测试/死代码,0–10 评分) |
| `/retro` | 🟢 | 工程周回顾(提交史、模式、人均贡献) |
| `/benchmark-models` | 🟢 | 跨模型对比(Claude/GPT/Gemini)同一 skill 的延迟/成本/质量 |

### 1.6 文档
| 命令 | 性质 | 用途 |
|---|---|---|
| `/document-release` | 🔵 | 发版后文档同步(对照 diff 更新 README/ARCH/CHANGELOG) |
| `/document-generate` | 🟢 | 从零生成文档(Diataxis 四象限) |
| `/make-pdf` | 🟢 | 任意 markdown → 出版级 PDF |

### 1.7 上下文 / 学习 / gbrain
| 命令 | 性质 | 用途 |
|---|---|---|
| `/context-save` | 🟢 | 保存工作状态(git 状态、决策、待办) |
| `/context-restore` | 🟢 | 恢复上次保存的状态,跨会话续上 |
| `/learn` | 🟢 | 管理项目"学习记录"(查/搜/裁剪/导出) |
| `/setup-gbrain` | ⚙️ | 给本机配置 gbrain(CLI+本地脑+MCP) |
| `/sync-gbrain` | 🟢 | 让 gbrain 跟上仓库代码、刷新搜索指引 |

### 1.8 安全护栏 / 维护
| 命令 | 性质 | 用途 |
|---|---|---|
| `/careful` | 🟢 | 危险命令告警(rm -rf、DROP TABLE、force-push…) |
| `/freeze` `/unfreeze` | 🟢 | 限制/解除编辑范围到指定目录 |
| `/guard` | 🟢 | 全量安全模式(= `/careful` + `/freeze`) |
| `/gstack-upgrade` | 🟢 | 升级 gstack 到最新版 |

---

## 2. 插件 skill(已固化进 `.claude/settings.json`,队友也会有)

| 来源 | 命令 | 用途 |
|---|---|---|
| commit-commands | `/commit` | 创建一次 git 提交 |
| commit-commands | `/commit-push-pr` | 提交 + 推送 + 开 PR |
| commit-commands | `/clean_gone` | 清理远端已删除的本地 `[gone]` 分支及 worktree |
| pr-review-toolkit | `/review-pr` | 多专家 agent 综合 PR 评审 |
| feature-dev | `/feature-dev` | 带代码库理解、面向架构的功能开发 |
| frontend-design | `/frontend-design` | 前端界面实现 |
| code-simplifier | `/simplify` | 复用/质量/效率角度简化刚改的代码 |
| agent-sdk-dev | `/new-sdk-app` | 新建并配置 Claude Agent SDK 应用 |
| playground | `/playground` | 实验/试验场 |
| claude-code-setup | `/claude-automation-recommender` | 推荐适合你的 Claude Code 自动化 |
| supabase | `/supabase` | Supabase 使用指引 |
| supabase | `/supabase-postgres-best-practices` | Supabase/Postgres 最佳实践 |
| context7 | (MCP) | 查任意库/框架的**最新**官方文档(非 slash,自动用) |

### 2.1 vercel 插件(约 29 个)
**操作类**:`/deploy`(部署,加 `prod` 上生产)· `/env`(环境变量 list/pull/add/diff)· `/status`(项目/部署概览)· `/bootstrap`(初始化 Vercel 资源)· `/marketplace`(集成市场)· `/vercel-cli`

**知识/参考类**(写相关代码时按需查):`/nextjs` `/ai-sdk` `/ai-gateway` `/react-best-practices` `/shadcn` `/turbopack` `/routing-middleware` `/vercel-functions` `/vercel-storage` `/runtime-cache` `/next-cache-components` `/vercel-firewall` `/vercel-sandbox` `/vercel-agent` `/chat-sdk` `/workflow` `/auth` `/env-vars` `/next-forge` `/next-upgrade` `/deployments-cicd` `/verification` `/knowledge-update`

> claude-hud(`/setup`、`/configure`,状态栏)、两个 output-style、ts/py LSP 是**个人全局**插件,本机可用但**未**固化进项目(队友不会自动获得)。

---

## 3. superpowers(方法论,多为 🔵 自动触发)

| 命令 | 用途 |
|---|---|
| `/brainstorming` | **任何创造性工作前必走**:厘清意图、需求、设计 |
| `/writing-plans` | 有规格后、动代码前,写多步实现计划 |
| `/executing-plans` | 在独立会话按计划执行(带评审检查点) |
| `/subagent-driven-development` | 用子 agent 执行计划中相互独立的任务 |
| `/dispatching-parallel-agents` | 2+ 个无依赖任务时并行派发 agent |
| `/test-driven-development` | 任何功能/修复前先写测试 |
| `/systematic-debugging` | 遇到 bug/测试失败/异常,先于"提方案"使用 |
| `/verification-before-completion` | 声称"完成/修好/通过"前,先跑命令拿证据 |
| `/requesting-code-review` | 完成任务/大功能/合并前,核对是否达标 |
| `/receiving-code-review` | 收到评审意见后,带技术严谨地核实再落实 |
| `/using-git-worktrees` | 需要隔离工作区时(如执行计划前) |
| `/finishing-a-development-branch` | 实现完成后,决定合并/PR/清理的方式 |
| `/writing-skills` | 新建/修改/验证 skill |
| `/using-superpowers` | 会话起点:确立如何发现并使用 skill |

---

## 4. 内置 / 全局

| 命令 | 用途 |
|---|---|
| `/init` | 为代码库初始化 `CLAUDE.md` |
| `/review` | 评审一个 PR(内置) |
| `/security-review` | 对当前分支待提交改动做安全评审 |
| `/update-config` | 改 `settings.json`(权限/钩子/环境变量/插件) |
| `/fewer-permission-prompts` | 扫描历史,生成常用命令白名单减少打断 |
| `/keybindings-help` | 自定义快捷键 |
| `/loop` | 按固定间隔重复跑某个提示/命令 |
| `/schedule` | 创建/管理 cron 定时远程 agent |
| `/claude-api` | 构建/调试/优化 Claude API·Anthropic SDK 应用 |
| `/graphify` | (你的自定义)任意输入 → 知识图谱 |
| `/statusline-setup` | 配置状态栏 |

---

## 5. 全生命周期工作流(尽量串联所有 skill)

> 一条从 0 到 1、再到运维的主线。每一步标出**该用哪些 skill**;不是每个项目都要全跑,按需取用。

### 阶段 0 · 环境与一次性配置 ⚙️
`/init`(建 CLAUDE.md)→ `/update-config`(权限/钩子)→ `/fewer-permission-prompts`(白名单)→ `/keybindings-help` · `/statusline-setup` · claude-hud `/setup`·`/configure` → `/setup-deploy`(部署配置)→ `/setup-gbrain`(可选,代码记忆)→ `/setup-browser-cookies`(测登录态)→ `/claude-automation-recommender`(推荐自动化)。新建 SDK 应用时:`/new-sdk-app`。

### 阶段 1 · 想法验证 🔵
`/office-hours`(值不值得做)→ `/brainstorming`(厘清意图与设计)。

### 阶段 2 · 计划与评审
`/writing-plans`(写计划)→ 单视角:`/plan-ceo-review` · `/plan-eng-review` · `/plan-design-review` · `/plan-devex-review`,或一键 `/autoplan` 跑全套 → `/plan-tune`(嫌问得多就调)。

### 阶段 3 · 设计
`/design-consultation`(出 DESIGN.md)→ `/design-shotgun`(多变体对比)→ `/design-html` 或 `/frontend-design`(落成 HTML/CSS)。

### 阶段 4 · 实现
`/using-git-worktrees`(隔离工作区)→ `/test-driven-development`(先写测试)→ `/feature-dev`(主力开发)→ 多任务:`/executing-plans` · `/subagent-driven-development` · `/dispatching-parallel-agents` → 查文档:context7(MCP) + vercel 参考库(`/nextjs` `/ai-sdk` `/react-best-practices` `/shadcn` …)+ `/supabase`·`/supabase-postgres-best-practices` + `/claude-api` → 取数据:`/scrape`(→ `/skillify` 固化)。

### 阶段 5 · 自查与简化
`/simplify`(简化刚写的)→ `/health`(质量评分)→ `/requesting-code-review` → `/verification-before-completion`(拿证据再说"完成")。

### 阶段 6 · 评审
`/review`(gstack diff 评审)· `/review-pr`(多 agent)· 内置 `/review` · `/codex`(对抗式第二意见)→ `/receiving-code-review`(严谨落实意见)。

### 阶段 7 · QA 与测试
`/qa`(测+修)或 `/qa-only`(只报告)→ 网页:`/connect-chrome`·`/browse` → 视觉:`/design-review` → 开发者体验:`/devex-review` → 性能:`/benchmark`。卡住时:`/systematic-debugging` → `/investigate`(根因)。

### 阶段 8 · 安全
`/security-review`(待提交改动)→ `/cso`(纵深安全审计)。

### 阶段 9 · 交付
危险操作前开 `/careful` 或 `/guard`(含 `/freeze`,完事 `/unfreeze`)→ `/commit` 或 `/ship`(测试+CHANGELOG+PR)或 `/commit-push-pr` → `/finishing-a-development-branch`(决定合并/PR/清理)→ `/landing-report`(看队列)。Vercel 项目:`/bootstrap` → `/env` → `/deploy prod`。

### 阶段 10 · 部署后
`/land-and-deploy`(合并+CI+校验)→ `/canary`(金丝雀监控)→ `/status`(Vercel 概览)→ `/benchmark`(生产性能)→ `/sync-gbrain`(刷新代码记忆)。

### 阶段 11 · 文档与收尾
`/document-release`(同步文档)/ `/document-generate`(补缺)→ `/make-pdf`(导出)→ `/learn`(沉淀经验)→ `/retro`(周回顾)→ `/context-save`(存状态,下次 `/context-restore`)。

### 跨阶段 · 随时可用
- **清理**:`/clean_gone`(删 [gone] 分支)
- **维护**:`/gstack-upgrade`(升级工具链)· `/writing-skills`(造/改 skill)
- **自动化**:`/loop`(轮询)· `/schedule`(定时 agent)
- **协作/对比**:`/pair-agent`(共享浏览器)· `/benchmark-models`(选模型)
- **知识**:`/graphify`(任意输入→知识图谱)
- **元**:`/using-superpowers`(怎么发现并用 skill)

---

_本文件由会话生成;skill 集合随插件增删而变化,新增/停用插件后可让 Claude 重新生成本表。_
