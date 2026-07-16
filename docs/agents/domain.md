# Domain Docs

本仓库采用 single-context 领域文档布局。

## Before exploring, read these

- 根目录 `CONTEXT.md`：领域术语与明确避免的同义词。
- `docs/adr/`：与当前工作区域有关的长期技术决策。

如果某个文件尚不存在，继续工作即可。只有在术语真正得到澄清时才更新
`CONTEXT.md`；只有满足 ADR 条件的决策才新增 ADR。

## File structure

```text
/
├── CONTEXT.md
└── docs/
    └── adr/
```

## Use the glossary vocabulary

Issue 标题、测试名、重构建议和用户文档应使用 `CONTEXT.md` 中的 canonical
term。不要漂移到 glossary 明确列入 `_Avoid_` 的同义词。

如果需要的概念尚未出现，应先判断它是通用编程概念、已有术语的别名，还是领域模型
中的真实缺口。只有最后一种情况才应通过 `domain-modeling` 更新 glossary。

## Flag ADR conflicts

如果提议与已有 ADR 冲突，必须明确指出冲突及重新开启决策的理由，不得静默覆盖。
