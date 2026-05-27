# Design System — RivalRadar

> 由 `/design-consultation` 生成(Claude + Codex 跨模型收敛)。任何视觉/UI 决策前先读本文件。

## Product Context
- **What this is:** AI 多 Agent 竞品分析系统的轻量 Web 应用(报告 + 溯源 + 实时 Agent 协作可视化)。
- **Who it's for:** 企业产品 / 调研团队。
- **Space:** 竞品情报 / 分析师工具。
- **记忆点(驱动所有设计):** **可信** —— 点任何结论,立刻看到它的原始出处("点结论看收据")。
- **Project type:** 桌面优先的数据密集型 Web 应用(analyst console),需投影演示、中英文双语。

## Aesthetic Direction
**双气质叙事(v3 paradigm pivot)**:统一在"可信/溯源"记忆点下,双视图各承担一种气质:

- **主视图 — 虚拟办公室(office)**:角色化、温暖、看得见的工作。4 个拟物动物 agent 在 2x2 工位上 typing/searching/writing/checking。35% money shot 兑现"我请了一队员工正在为我工作"叙事。
- **次视图 — 流程图详情(DAG tab)**:沉稳、密集、精确、句句有据。研报 / 分析师控制台(intelligence desk)— 保留原 v2 的"实时情报台"气质,给评委看工程深度。
- **装饰:** 极简。**边框和层级承担结构,阴影只给浮层**(不要玻璃拟态/发光块)。两视图共用。
- **Mood:** 主视图"看得见的多 agent 协作"+ 次视图"克制的动效证明调研机器在运转"。

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

### Office tokens(v3 paradigm 新增,继承既有 24 vars,不引入新色板)
```css
/* Light */
--office-bg:#EFEEE9;     --speech-bg:#FFFFFF;     --typing-cursor:#0F6B5F;
--seat-1:#0F6B5F;        /* 收集员·夜枭(accent 青绿)   */
--seat-2:#A96F00;        /* 分析员·灵犀(warning 琥珀) */
--seat-3:#2F6F9F;        /* 撰稿员·灵巧(info 墨蓝)    */
--seat-4:#237A4B;        /* 质检员·镜湖(success 松绿) */

/* Dark — 同色阶 dark variant */
--office-bg:#1A201E;     --speech-bg:#242B28;     --typing-cursor:#4FB7A5;
--seat-1:#4FB7A5;        --seat-2:#D7A33D;
--seat-3:#78AEDA;        --seat-4:#62BA80;
```

## Spacing
- **Base:** 8px(4px 半步)
- **Density:** 紧凑偏舒适(数据密集但可读)
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** 桌面优先三栏控制台(analyst console),非居中。三栏框架 v3 仍保留(顶栏 + 左 AgentTeamRoster 替原"竞品/筛选"+ 主画布 + LiveFeedPanel)。
```
┌ 顶栏:项目 · 竞品 · 新鲜度 · 可信度摘要 ─────────────────┐
├ 左轨(~208px)│ 主画布(flex)│ 右侧 LiveFeed(~360px)──┤
│ AgentTeam     │ Office / DAG  │ 实时 agent narrative log ┤
│ 4 agent 头像  │ ViewSwitcher  │(原证据面板改 ReportSheet ┤
│ + 状态 chip   │ + CancelBtn   │ 触发的浮层 420–520px)   ┤
└──────────────────────────────────────────────────────┘
```

### 虚拟办公室 layout(主视图,v3 paradigm 新增)
```
┌ ViewSwitcher · 办公室 / 流程图 ───────────── CancelButton ┐
│  ┌─夜枭 工位─┐         ┌─灵犀 工位─┐    │ LiveFeedPanel │
│  │  🦉  💻   │         │  🦊  🔍   │    │ ────────────  │
│  │  speech.. │         │  speech.. │    │ [12:01 夜枭]  │
│  └───────────┘         └───────────┘    │  正在搜索...  │
│         ┌─── 会议区(handoff)───┐        │ [12:02 灵犀]  │
│         │  📄 → 📄 → 📄          │        │  我抽到 3 个 │
│  ┌─灵巧 工位─┐         ┌─镜湖 工位─┐    │  ...          │
│  │  🦝  ⌨️    │         │  🐢  📜   │    │               │
│  └───────────┘         └───────────┘    │               │
├─ ReportSheet(底部 drawer · 默认 collapsed 80px,click expand 60vh)─┤
└──────────────────────────────────────────────────────────────────┘
```
- **Office 区域:** 2x2 工位(每工位 ~280×220px)+ 中央会议区 ~160×120px(handoff 动画落点)
- **LiveFeedPanel:** 右侧 ~360px,从 plan v2"证据面板"位置迁移
- **ReportSheet:** 底部 drawer,默认 collapsed 80px(露标题 + 可信度徽章),click expand 60vh,floor 不挤压 office

- **Max content:** 主画布自适应;证据面板浮层 420–520px(由 ReportSheet 内引用 chip 触发,不再固定右栏)。
- **Border radius:** 6–8px(卡片 8、chip/角标 4–6,office SpeechBubble 12px)。

## Motion
- **Approach:** 克制、为投影。主视图(office)= 持续低强度的"有生命迹象";次视图(DAG)= 单次脉冲式"招牌时刻"。
- **DAG:** 细线描边,每阶段切换脉冲一次;**打回 = 反向扫掠 + 上游节点重亮**(招牌时刻 #2);单次切换 700–1100ms(投影看得清);完成后归"上次运行"静态,不无限抖动。
- **Office(v3 新增):**
  - **AgentCharacter state 切换:** idle → working → thinking → handoff,每态 200ms cross-fade;working 状态有 800ms loop 微动画(头扇动 / 手敲键 / 眼眨)
  - **SpeechBubble:** 200ms 进(opacity + scale 0.95→1 from agent 头顶),内容 typing 速度 25–50 char/s(Day-3 spike 决,D19 polish),auto-fade 3s 退或被新 bubble 替换
  - **HandoffAnimation:** 文档 icon 沿 quadratic curve 800ms move(from agent → 会议区 → to agent),目标工位 `--seat-N` highlight pulse 一次(招牌时刻 #3)
  - **Typing cursor:** `--typing-cursor` 闪烁 1Hz(节点完成后变实色不再闪)
- **证据面板:** 180ms 从右滑入(opacity + translateX 12→0);引用 chip 与命中句短暂共用高亮,黄从强渐隐到浅 900ms。
- **Easing:** enter ease-out · exit ease-in · move ease-in-out。

## Signature Patterns(让"可信"被记住的三个刻意冒险)
1. **源优先可信度徽章** —— 给**证据链**打标,不是给生成答案打分:`7 来源 · 2 一手 · 1 过期 · 引语已匹配`。常驻顶栏 + 每张卡片头。
2. **打回可见** —— DAG 回流箭头是品牌时刻:质检否掉弱结论 → 退回重做(`retry 1 · 证据 12→19`),用户亲眼看到系统自我纠错。(DAG tab 内招牌)
3. **看得见的多 agent 协作(v3 新增)** —— 4 个拟物动物 agent 在虚拟办公室真实 typing + 实时 speech bubble + 文档移交动画。30 秒内评委体感"我请了一队员工正在为我工作",不是"AI 黑盒在转"。(office 主视图招牌)

## 关键组件基调

### 报告 / 证据组件(v2 + v3 共用)
- **报告卡:** 8px 圆角、16px 内边距、硬边框、无浮动玻璃;头部含标题 + 可信度徽章。
- **引用 chip:** `[1]` mono 小号、青绿描边;点击右侧证据面板滑出。
- **insufficient_evidence:** 灰条 + 虚线边 + 斜体"未找到公开数据",不留空不臆测。
- **对比矩阵:** 行=维度、列=竞品(列吸顶);✓/✗ 用 success/error,胜出项 accent 加粗;每格右挂 mono 证据角标。
- **KPI 条:** 紧凑卡片,数字 tabular-nums,good=success / warn=warning。

### Office 组件(v3 paradigm 新增)
- **AgentCharacter:** SVG sprite 64×64,4 state class(idle/working/thinking/handoff);头顶 16×16 头像 overlay;工位 `--seat-N` 色为身份标识。
- **SpeechBubble:** 圆角 12px,白底 `--speech-bg`,8px 阴影,左下尖角指向 agent;字 13px IBM Plex Sans + typing cursor `--typing-cursor` 闪烁;max-width 240px,溢出截到 … + LiveFeedPanel 看全文。
- **HandoffAnimation:** 文档 icon(20×20)沿 quadratic curve 800ms move,目标工位 highlight pulse 一次(`--seat-N` 透明度 0.2 → 0.6 → 0)。
- **LiveFeedPanel:** scroll log,agent role 4 色 chip(`--seat-1-4`)+ 13px mono timestamp + 15px body;auto-scroll bottom + 鼠标 hover 暂停;支持回放 jump-to-agent-event。
- **ReportSheet:** 底部 drawer,默认 collapsed 80px(露标题 + 可信度徽章),click expand 60vh;markdown 渲染报告 + 引用 chip 同 v2 行为;关闭后 office 全显。
- **AgentTeamRoster:** 左轨 4 agent 卡片(头像 48×48 + 名字 13px + 状态 chip `--seat-N`);click → focus 对应工位(office camera pan)。
- **CancelButton:** 顶部 ViewSwitcher 右侧,running 中亮红 `--error` "停止" + 8px hover 阴影;cancelled 后切灰 disabled + "已停止 N 秒前";支持 keyboard `Esc` 触发(D18 a11y baseline)。

## Decisions Log
| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-21 | 初版设计系统 | `/design-consultation` 生成;记忆点=可信/溯源;Claude+Codex 跨模型收敛于"暖纸白+机构青绿+研报控制台+把溯源/打回做成视觉主角";字体取 IBM Plex 超级家族(2.5 周落地最省事、覆盖中英文) |
| 2026-05-27 | v3 paradigm pivot:虚拟办公室 + 拟物动物 + 实时 streaming | 触发 = Task 6.5 spike 真后端 user 反馈 35% money shot DAG 节点过于工程师视角;决策 = 保留 intelligence desk 作为 DAG tab 气质 + 主视图 paradigm 切到 office(双视图叙事);保留 = 字体 100% + 24 色 vars 100% + spacing 100% + Signature Patterns 1-2;新增 = office tokens 7 个 + 7 office 组件 spec + office motion 段 + office layout 二级 § + 招牌时刻 #3;评审 = plan-eng-review + Codex outside voice + plan-design-review 三角全 CLEARED(plan v3.2 锁,见 `docs/superpowers/plans/2026-05-27-rivalradar-lane-f-frontend-v3-virtual-office.md`)|
