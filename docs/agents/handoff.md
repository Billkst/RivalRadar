# Agent Handoff

Handoff 用于 Claude Code、Codex 或人工维护者之间接管未完成工作。

## Storage

- Handoff 是本机临时状态，不提交到仓库。
- 默认写入 `${TMPDIR:-/tmp}/rivalradar-handoff.md`。
- 交付回复中必须明确给出 handoff 路径。
- Issue、spec、ADR、commit 和 diff 已记录的内容只引用，不重复复制。

## Required contents

```markdown
# RivalRadar handoff

## Objective
当前目标、任务来源和验收标准。

## Repository state
- Working directory:
- Branch:
- HEAD:
- Base/reference:
- Worktree summary:
- Pre-existing user changes:

只概述隐私材料的数量和类别，不写敏感文件名或内容。

## Completed
已完成工作及对应文件、Issue、spec、ADR 或 commit 引用。

## Remaining
尚未完成的内容，以及不在本次范围内的内容。

## Verification
逐条记录实际命令、结果、失败、超时和未运行原因。

## Decisions and assumptions
只记录尚未进入 ADR、spec 或代码的必要上下文。

## Risks and blockers
已知风险、外部依赖和需要用户决定的事项。

## Next action
下一位维护者应执行的唯一首要动作。

## Suggested skills
建议下一位 agent 使用的 skill 或 Claude/gstack 流程。
```

## Privacy

- 删除 API key、token、cookie、个人信息和敏感 endpoint。
- 不粘贴隐私材料、完整环境变量或未经脱敏的 `git status`。
- 不重复仓库中已经存在的长文档。
