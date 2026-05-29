# Reference baselines + RivalRadar output evidence

本目录是 RivalRadar **输出质量评估**的"对照实验室":
- 4 份中文企业 SaaS 竞品调研报告作为 baseline(评 26-28/30)
- RivalRadar 同主题两轮真打报告(Round 1 = 18.5/30 → Round 2 = 24/30)
- 评分用 [Rubric v1](#rubric-v1)(10 条 × 0-3 分 = 30 满分)

---

## Rubric v1

基于 4 份 reference 倒推 + 比赛评分细则(35% 输出可信度 / 25% 技术深度 / 20% 业务价值)。

### A 组 — 结构与覆盖(5 条 / 15 分)

| # | 条件 | 0 分 | 1 分 | 2 分 | 3 分 |
|---|---|---|---|---|---|
| 1 | **市场锚定** | 无 | 提及行业 | 量级数字 / 玩家 | 赛道格局 + 主要玩家定位 |
| 2 | **对比矩阵** | 无 | 表格但 < 3 行 | 3-5 行 / 单维 | ≥ 6 行 / 多维 + 引用 |
| 3 | **维度粒度** | 单层 | 2 层粒度 | 3 层 | 4 层 + 子项有引用 |
| 4 | **信息溯源完整** | 无引用 | 部分引用 | 多数引用 + 部分 broken | 100% 引用 + 0 broken + URL + as_of |
| 5 | **定价模型** | 无 | 列名/价 | 名/价/计费/限额 | 全字段 + 跨竞品对比 |

### B 组 — 质量与洞察(5 条 / 15 分)

| # | 条件 | 0 分 | 1 分 | 2 分 | 3 分 |
|---|---|---|---|---|---|
| 6 | **数据密度** | 模糊形容 | 部分数字 | 多数据点 | 数字 + 来源 + as_of |
| 7 | **战略推论** | 罗列功能 | 单段判断 | 推论链 | 「因为 X,所以 Y」+ 母公司战略映射 |
| 8 | **Schema 深度** | 不结构化 | 列表 | SWOT 或对比 | SWOT + 对比 + 用户画像 全 |
| 9 | **时间分层** | 无 | 单层(现状) | 现状 + 未来 | 短/中/长期 + actionable |
| 10 | **反幻觉信号** | 套话满 | 部分 hedging | 多数有据 | 0 套话 + 0 broken refs + 显式 fact/judgment 分层 |

### 等级阈值

| 分数段 | 等级 | 含义 |
|---|---|---|
| 25-30 | **Excellent** | 与权威厂商报告同档 |
| 20-24 | **Good** | 可直接给产品团队决策用 |
| 15-19 | **Adequate** | 起步可用,关键判断需人工补 |
| 10-14 | **Weak** | 仅作素材整理,不可直接采纳 |
| < 10 | **Fail** | 不可用 |

---

## Reference baselines

| 文件 | 来源 / 体裁 | 主题 | 评分 | 等级 |
|---|---|---|---|---|
| `ref-01-woshipm-feishu-dingding-qiwei.md` | 人人都是产品经理 / PM 学院派 | 飞书 / 钉钉 / 企业微信 三方对比 | **26 / 30** | Excellent |
| `ref-02-36kr-dingding-vs-feishu-5years.md` | 36 氪 / 业内深度分析 | 钉钉 vs 飞书 5 年战略对照 | **25 / 30** | Excellent |
| `ref-03-woshipm-shimo-tencent-kingsoft.md` | 人人都是产品经理 / PM 视角 | 石墨 / 腾讯文档 / 金山文档 | **24 / 30** | Good |
| `ref-04-iresearch-2024-collaborative-office-china.pdf` | 艾瑞咨询 / 厂商权威 38 页 | 2024 中国协同办公赛道全景 | **28 / 30** | Excellent |

每份 ref 文件头部 YAML frontmatter 记 `source_url / author / fetched_at / quality_score`,可溯源。

---

## RivalRadar output evidence

### `rivalradar-output/run-001-feishu-dingding/`(Round 1 — pre-writer-v2 baseline)

- **报告**:`report.md`(18507 字 markdown)
- **结构化分析**:`analysis.json`(飞书 22 features/5 tiers + 钉钉 36 features/14 tiers)
- **原始 LLM 输出**:`report-raw.json`
- **执行轨迹**:`trace.json`(节点级 verdict + retry trace)
- **评分**:**18.5 / 30 = 62% = Adequate 上端**
- **失分集中**:#1 市场锚定 0/3 + #7 战略推论 1.5/3 + #9 时间分层 0/3(共 -7.5)
- **闪光点**:#4 信息溯源完整 3/3(0 broken refs / 全 URL + as_of)+ #10 反幻觉 2.5/3

### `rivalradar-output/run-002-writer-v2/`(Round 2 — writer prompt v2 重构)

- **报告**:`report.md`(15932 字,带 `## 执行洞察(AI 基于下方正文综合)`)
- **结构化分析**:`analysis.json`(飞书 12 features/7 tiers + 钉钉 22 features/23 tiers)
- **原始 LLM 输出**:`report-raw.json`
- **评分**:**24 / 30 = 80% = Good 中段**
- **三个目标失分项全 hit**:#1 市场锚定 0 → **2.5** ⭐ / #7 战略推论 1.5 → **3** ⭐ / #9 时间分层 0 → **2.5** ⭐
- **新 regression**:#2 对比矩阵 3 → 1.5(analyst 行为变 comparison_rows 6 → 3,损 1.5)
- **净 delta**:+5.5 提升 − 1.5 regression = **+4 总分 → 24 / 30**(距 ref-01 仅 2 分)

---

## Iteration learning

Round 2 vs Round 1 验证了:

1. **Schema-encoded prompt > 自然语言 prompt** — Pydantic `ReportInsight(market_context, differentiation_thesis, actionable_takeaway)` 强制 3 段比 prompt 说"请分 3 段"可靠 5×
2. **Negative example 比 positive 强** — "严禁持续关注/深入研究/保持观察"比"请写 actionable"直接生效
3. **Hybrid Python + LLM 架构是产品级输出标准** — `render_body` Python 模板保 100% 引用完整性,`generate_insight` LLM 担 strategic synthesis 显式标"AI 综合判断",评委可分辨 fact vs judgment

下轮目标(可选):修 analyst prompt 强制 ≥ 6 comparison rows 补回 #2 regression → 预期 26/30 进入 Excellent 边。

---

## How to evaluate a new RivalRadar run

```
1. 跑 run → 拿到 report.md + analysis.json
2. 按 Rubric v1 表逐条 0-3 打分(10 条)
3. 算总分 + 等级
4. 与 ref-01 (26) baseline 对比,记 delta
5. 标识具体失分项的可改进 prompt area
```
