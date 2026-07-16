# RivalRadar Working Agreement

本文件是 Claude Code、Codex、人工维护者及其他 agent 的共享维护契约。
工具专属命令不得写入本文件；Claude/gstack 专属规则放在 `CLAUDE.md`。

## Communication

- 默认使用简体中文沟通；用户明确要求其他语言时按其要求。
- 命令、路径、API 名称、错误信息和源代码保持原文。
- 区分已验证事实、推断和未验证假设。
- 失败、超时、中断或未运行的检查不得描述为通过。

## Sources of truth

开始工作前，按任务范围阅读：

- 当前用户要求、GitHub Issue 或 spec：任务范围和验收标准。
- `CONTEXT.md`：领域词汇与系统边界。
- `docs/adr/`：已作出的长期技术决策。
- `DESIGN.md`：视觉和 UI 决策。
- `TESTING.md`：测试命令、边界与约定。
- `VERSION` 和 `CHANGELOG.md`：当前版本与发布历史。
- `TODOS.md`：候选积压项，不代表已授权实施。
- `docs/agents/issue-tracker.md`：Issue 工作流。
- `docs/agents/domain.md`：领域文档消费规则。

可执行代码、配置和本轮实际验证结果优先于叙述性文档中的过期数字。
不要在 agent 契约中复制测试数量、运行耗时或当前版本。

## Before changing files

1. 运行 `git status --short --branch`，并检查任务相关 diff。
2. 明确任务来源、范围、验收标准和不在范围内的内容。
3. 阅读相关代码、测试、spec 和 ADR；UI 工作必须先读 `DESIGN.md`。
4. 将已有修改和未知未跟踪文件视为用户资产，不覆盖、不清理、不暂存。
5. 调用真实外部 API、运行 `spikes/`、消耗额度或发送数据前，先取得明确授权。

## Scope and implementation

- 只修改完成当前任务所需的内容。
- 不顺手重构、格式化或清理无关代码。
- 保持现有代码风格；只清理本次修改产生的无用内容。
- Bug 修复先添加能复现问题的回归测试。
- 新功能为正常路径、失败路径和新增分支提供相称测试。
- 领域术语变化写入 `CONTEXT.md`；满足 ADR 条件的长期决策写入 `docs/adr/`。
- 不执行破坏性 Git 操作。
- 未经明确要求，不 commit、push、创建 PR、合并或部署。

## Privacy and secrets

- `.env`、API key、token、cookie、凭据和 endpoint identifier 不得提交或打印。
- 用户标记为隐私的本机材料只保留在本机，具体路径由 `.git/info/exclude`
  管理，不写入被跟踪文件。
- 无法判断的未跟踪文件默认按用户本地资产处理。
- 禁止在脏工作树中使用 `git add .` 或 `git add -A`。
- 需要提交时只暂存明确路径，并在提交前检查 `git diff --cached`。
- Issue、PR、日志和 handoff 必须脱敏，不复制隐私材料正文或可识别文件名。

## Verification

先运行最小相关检查，再按风险扩大范围。

后端基线：

```bash
.venv/bin/python -m pytest
```

前端按修改范围运行：

```bash
cd frontend
pnpm typecheck
pnpm lint
pnpm build
```

- 只有真实执行了检查才可以声称通过；占位脚本不算验证。
- 记录准确命令、结果、失败、超时和被跳过的检查。
- `spikes/` 会访问真实服务，不属于默认 pytest，未经授权不得运行。

## Design

任何视觉或 UI 决策前先读 `DESIGN.md`。字体、配色、间距、布局、动效和
美学方向以该文件为准；未经用户明确同意不得偏离。

## Documentation

- 行为、接口、配置或维护流程变化时，同步更新直接相关文档。
- 发布版本以 `VERSION` 为准，并同步 `CHANGELOG.md` 及用户可见版本说明。
- 不复制易漂移事实；优先引用权威文件或由命令现场生成。
- 历史 plan/spec 不自动覆盖当前 Issue、ADR 或用户要求。
- 发现无关文档漂移时记录下来，不擅自扩大当前任务范围。

## Network environment

- 尊重现有代理环境，不擅自清空代理变量或扩大 `NO_PROXY`。
- 网络失败先验证实际连接路径，再区分代码问题、工具命令和环境限制。

## Completion and takeover

交付时说明：

- 完成了什么。
- 修改了哪些文件。
- 执行了哪些验证及其结果。
- 仍有哪些风险、阻塞或未验证内容。
- 下一步唯一建议动作。

任务跨会话、暂停或更换 agent 时，按 `docs/agents/handoff.md` 生成本地
handoff。
