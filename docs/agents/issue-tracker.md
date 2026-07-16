# Issue tracker: GitHub

本仓库的 Issue 和 PRD 使用 GitHub Issues。默认通过仓库内的 `gh` CLI 操作，
仓库由当前 clone 的 `origin` 自动推断。

## Conventions

- 创建：`gh issue create --title "..." --body "..."`
- 阅读：`gh issue view <number> --comments`
- 列表：`gh issue list --state open --json number,title,body,labels,comments`
- 评论：`gh issue comment <number> --body "..."`
- 添加或移除标签：`gh issue edit <number> --add-label "..."` /
  `--remove-label "..."`
- 关闭：`gh issue close <number> --comment "..."`

多行 Issue 正文应使用临时文件或经过审阅的 heredoc。发送前必须检查正文中
没有密钥、个人信息、本机隐私路径或未经脱敏的日志。

## Pull requests as a triage surface

**PRs as a request surface: no.**

外部 PR 默认不进入与 Issue 相同的 triage 队列。如果以后需要，可把上面的值改为
`yes`，再使用 `gh pr view`、`gh pr diff`、`gh pr edit` 等对应命令。

GitHub 的 Issue 与 PR 共用编号空间。遇到裸编号时，先尝试
`gh pr view <number>`，失败后再读取 `gh issue view <number>`。

## Skill vocabulary

- “publish to the issue tracker”：创建 GitHub Issue。
- “fetch the relevant ticket”：运行 `gh issue view <number> --comments`。
- `/to-spec`、`/to-tickets`、`/triage` 和 `/wayfinder` 均以本文件为准。

## Wayfinding operations

- Map：一个带 `wayfinder:map` 标签的 Issue。
- Child ticket：GitHub sub-issue；不可用时在正文顶部写 `Part of #<map>`。
- Blocking：优先使用 GitHub 原生 issue dependencies；不可用时在正文顶部写
  `Blocked by: #<n>`。
- Claim：`gh issue edit <number> --add-assignee @me`。
- Resolve：把结论评论到 Issue，关闭它，并在 map 的 Decisions-so-far 中加入引用。
