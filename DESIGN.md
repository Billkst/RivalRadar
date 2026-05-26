# Design System — RivalRadar

> 由 `/design-consultation` 生成(Claude + Codex 跨模型收敛)。任何视觉/UI 决策前先读本文件。

## Product Context
- **What this is:** AI 多 Agent 竞品分析系统的轻量 Web 应用(报告 + 溯源 + 实时 Agent 协作可视化)。
- **Who it's for:** 企业产品 / 调研团队。
- **Space:** 竞品情报 / 分析师工具。
- **记忆点(驱动所有设计):** **可信** —— 点任何结论,立刻看到它的原始出处("点结论看收据")。
- **Project type:** 桌面优先的数据密集型 Web 应用(analyst console),需投影演示、中英文双语。

## Aesthetic Direction
- **方向:** 研报 / 分析师控制台(intelligence desk)。沉稳、密集、精确、句句有据。
- **装饰:** 极简。**边框和层级承担结构,阴影只给浮层**(不要玻璃拟态/发光块)。
- **Mood:** 像一张实时情报台,用最克制的动效证明"调研机器在运转"。

## Typography
全部用 **IBM Plex 超级家族**(开源、为数据产品而生、覆盖中英文、支持 tabular-nums,一家族加载最轻)。
- **Display / Body / Data:** `IBM Plex Sans`,中文 `IBM Plex Sans SC`
- **Mono(源 ID / 时间戳 / 引用 chip / agent 日志):** `IBM Plex Mono`,中文回退 `IBM Plex Sans SC`
- **数据/表格/指标:** 同 `IBM Plex Sans` + `font-variant-numeric: tabular-nums`(全局给指标和矩阵单元格)
- **CDN:** Google Fonts `IBM+Plex+Sans` / `IBM+Plex+Sans+SC` / `IBM+Plex+Mono`
- **字号:** 12 / 13 / 15(UI 主)/ 18(卡片标题)/ 22(区块头)/ 28(页面标题)/ 36(投影标题)
- **行高:** 紧 1.18 · UI 1.35 · 阅读 1.55

> 备选(若要更多层次):display `IBM Plex Sans` + body `Source Sans 3` + data `Aptos` 混搭 —— 但多字体加载更重、Aptos Web 可得性差,暂不用。

## Color
暖纸白底 + 机构感青绿 accent(可信、非"AI 魔法紫")。**无紫/紫罗兰/渐变。** 边框优先于阴影。

### Light
```css
--bg:#F6F5F1; --surface:#FFFFFF; --surface-subtle:#F0EFEA; --border:#D8D5CC;
--text-primary:#1E2428; --text-muted:#667178;
--accent:#0F6B5F; --accent-soft:#DDEBE7;
--success:#237A4B; --warning:#A96F00; --error:#B23A36; --info:#2F6F9F;
--evidence-highlight:#FFF1A8; --source-line:#C7A400;
```
### Dark
```css
--bg:#141817; --surface:#1C2220; --surface-subtle:#242B28; --border:#39423E;
--text-primary:#ECEBE4; --text-muted:#A8B0AB;
--accent:#4FB7A5; --accent-soft:#173B35;
--success:#62BA80; --warning:#D7A33D; --error:#E06B67; --info:#78AEDA;
--evidence-highlight:#5A4B10; --source-line:#D4B83F;
```
- **浮层阴影(仅证据面板等):** `--shadow-panel:0 16px 40px rgba(20,24,23,.18)`

## Spacing
- **Base:** 8px(4px 半步)
- **Density:** 紧凑偏舒适(数据密集但可读)
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** 桌面优先三栏控制台(analyst console),非居中。
```
┌ 顶栏:项目 · 竞品 · 新鲜度 · 可信度摘要 ─────────────────┐
├ 左轨(~208px)│ 主画布(flex)│ 右侧证据面板(420–520px)┤
│ 竞品/筛选     │ DAG状态条+KPI条+报告卡+对比矩阵 │ 点引用滑出 ┤
└──────────────────────────────────────────────────────┘
```
- **Max content:** 主画布自适应;证据面板固定 420–520px。
- **Border radius:** 6–8px(卡片 8、chip/角标 4–6)。

## Motion
- **Approach:** 克制、为投影。
- **DAG:** 细线描边,每阶段切换脉冲一次;**打回 = 反向扫掠 + 上游节点重亮**(招牌时刻);单次切换 700–1100ms(投影看得清);完成后归"上次运行"静态,不无限抖动。
- **证据面板:** 180ms 从右滑入(opacity + translateX 12→0);引用 chip 与命中句短暂共用高亮,黄从强渐隐到浅 900ms。
- **Easing:** enter ease-out · exit ease-in · move ease-in-out。

## Signature Patterns(让"可信"被记住的两个刻意冒险)
1. **源优先可信度徽章** —— 给**证据链**打标,不是给生成答案打分:`7 来源 · 2 一手 · 1 过期 · 引语已匹配`。常驻顶栏 + 每张卡片头。
2. **打回可见** —— DAG 回流箭头是品牌时刻:质检否掉弱结论 → 退回重做(`retry 1 · 证据 12→19`),用户亲眼看到系统自我纠错。

## 关键组件基调
- **报告卡:** 8px 圆角、16px 内边距、硬边框、无浮动玻璃;头部含标题 + 可信度徽章。
- **引用 chip:** `[1]` mono 小号、青绿描边;点击右侧证据面板滑出。
- **insufficient_evidence:** 灰条 + 虚线边 + 斜体"未找到公开数据",不留空不臆测。
- **对比矩阵:** 行=维度、列=竞品(列吸顶);✓/✗ 用 success/error,胜出项 accent 加粗;每格右挂 mono 证据角标。
- **KPI 条:** 紧凑卡片,数字 tabular-nums,good=success / warn=warning。

## Decisions Log
| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-21 | 初版设计系统 | `/design-consultation` 生成;记忆点=可信/溯源;Claude+Codex 跨模型收敛于"暖纸白+机构青绿+研报控制台+把溯源/打回做成视觉主角";字体取 IBM Plex 超级家族(2.5 周落地最省事、覆盖中英文) |
