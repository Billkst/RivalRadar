# Design System — RivalRadar

> 由 `/design-consultation` 生成(Claude + Codex 跨模型收敛),v4 经 `/plan-design-review` 锁定。任何视觉/UI 决策前先读本文件。
> **v4 paradigm pivot(2026-05-30):证据驾驶舱(Evidence Cockpit)。** 本版废弃 v3 虚拟办公室/拟物动物/双气质叙事,统一到单一机构级分析台。视觉规格以 `docs/superpowers/plans/2026-05-30-rivalradar-v0.4-evidence-cockpit.md` §12 为唯一来源。

## Product Context
- **What this is:** AI 多 Agent 竞品分析系统 —— 不只产出报告,还给出**下一步该做什么的决策建议**、每条建议的**证据收据**、以及它**可能错在哪**。
- **Who it's for:** 企业产品经理 / 竞品调研团队(选型 PM / 竞品 PM / 分析师)。
- **Space:** 竞品情报 / 决策支持工具。
- **记忆点(驱动所有设计):** **可信 + 可决策** —— 点任何结论立刻看到原始出处("点结论看收据"),每条建议自带"哪里可能错"的自我攻击。
- **Project type:** 桌面优先的数据密集型分析台(decision cockpit),需投影演示、中英文双语。

## Positioning(category 定位,驱动美学方向)
RivalRadar **不是**"更精致的竞品报告生成器"——那会和 ChatGPT 同档(都是 plain markdown 容器)。它是**决策基础设施(decision infrastructure)**:一个会展示自己工作过程、会攻击自己结论、会告诉 PM 下一步该做什么的 AI 分析师。
- 与"报告生成器"的差异不靠 typography polish,靠 **paradigm**:决策流(不是报告)+ 证据常驻可溯源 + 自我纠错可见(重试环)+ 自我攻击(反证)。
- 这些是 paradigm signal;IBM Plex 字体、配色只是 surface。**Polish 加分,paradigm shift 改命。**

## Aesthetic Direction
**机构级证据驾驶舱(v4)**:像彭博终端 / 顶级研报控制台 —— 严肃、信息密集、精确、可信。绝不是营销页、绝不卡通、绝不花哨。
- **单一 cockpit 界面(Manus 分屏)**:左栏决策与证据(~62%)/ 右栏实时分析流程(~38%)。决策与"看得见的机器在干活"同屏共存,不再切视图。
- **装饰:** 极简。**边框和层级承担结构,阴影只给浮层**(证据原文卡等)。不要玻璃拟态 / 发光块 / 装饰色块 / 彩色圆圈套图标 / emoji。
- **Mood:** "点结论就看到收据"的安心感 + 克制动效证明调研机器在自我纠错地运转。

## Typography(v3 100% 保留)
全部用 **IBM Plex 超级家族**(开源、为数据产品而生、覆盖中英文、支持 tabular-nums,一家族加载最轻)。已在 `main.tsx` 导入,无需新增字体。
- **Display / Body / Data:** `IBM Plex Sans`,中文 `IBM Plex Sans SC`
- **Mono(源 ID / 时间戳 / 引用 chip / 证据徽章 / 网址 / 执行流日志):** `IBM Plex Mono`,中文回退 `IBM Plex Sans SC`
- **数据/表格/指标:** `IBM Plex Sans` + `font-variant-numeric: tabular-nums`(全局给指标和矩阵单元格)
- **CDN:** Google Fonts `IBM+Plex+Sans` / `IBM+Plex+Sans+SC` / `IBM+Plex+Mono`
- **字号:** 12 / 13 / 15(UI 主)/ 18(卡片标题)/ 22(区块头)/ 28(页面标题)/ 36(投影标题)
- **行高:** 紧 1.18 · UI 1.35 · 阅读 1.55

## Color
暖纸白底 + 机构感青绿 accent(可信、非"AI 魔法紫")。**无紫/紫罗兰/渐变。** 边框优先于阴影。基础 24 色板 v3 全保留。

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
- **浮层阴影(仅证据原文卡 / slide-over):** `--shadow-panel:0 16px 40px rgba(20,24,23,.18)`

### support_verdict tokens(v4 新增 —— 唯一信任信号)
证据对结论的支持度是产品**唯一的信任信号**:三色 supported / partial / unsupported。**没有数字 confidence,没有 provider 字段**(二者在初稿中是虚构的,已删)。token 语义解耦于状态色(success/warning/error 是"操作状态",verdict 是"证据支持度"),用 alias 复用色相 + 自动跟随 dark:
```css
/* Light & Dark 自动跟随基础色板 */
--verdict-supported:  var(--success);  /* 佐证充分 — 绿 */
--verdict-partial:    var(--warning);  /* 部分佐证 — 琥珀 */
--verdict-unsupported:var(--error);    /* 佐证不足 — 红 */
--evidence-stale: #9aa39d;             /* Light:证据过期(fetched_at > 90 天)灰,中性不报警 */
/* .dark */ --evidence-stale: #6b746f;
```
- **统一圆点规格(§12.3 #10):** 8px 圆点,与来源名间距 4px;**色盲双编码** —— 颜色 + 形状(实心●充分 / 半填◐部分 / 空心○不足),或 `title` 充分/部分/不足。
- **三处复用同一 token/组件**:对比矩阵单元格、决策依据行、证据原文卡。
- **stale 阈值默认 >90 天**(可调),灰角标"采集于 N 天前",中性不报警。

## Spacing
- **Base:** 8px(4px 半步)
- **Density:** 紧凑偏舒适(数据密集但可读)
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** 桌面优先的 **Manus 分屏驾驶舱**,非居中。顶 StatusBar + 左决策面(~62%)+ 右执行流(~38%)。
```
┌ StatusBar:结论 N 条│关键风险 N 个│已打回 N 次│最新证据 日期│证据支持度 充分X·部分Y·不足Z│●状态 ┐
├──────────── 决策面(left ~62%)────────────┬──── 实时分析流程(right ~38%)────┤
│ ▸ 决策流(顶层,每条三件套)                 │ 09:12 采集员 搜索 +12 证据 ✓     │
│   1.1 做什么 ·为什么(依据行常驻)·哪里可能错 │ 09:24 分析员 比较定价 ✓          │
│   1.2 …  [查看原文 ↗]                        │ 09:37 撰写员 生成结论 ✓          │
│ ── 对比矩阵(独立支撑区)──                   │ 09:49 质检员 裁决:打回采集 ●     │
│   行=维度 列=竞品 · 每格值+证据徽章          │   ↺ 第2轮·证据 12→19(重试环)    │
└──────────────────────────────────────────┴──────────────────────────────────┘
```
- **断点(§12.3 #11,投影 1280×720 实测;宽度受 run 状态 × 视口双维度控制):**
  - **≥1280 运行中:** 双栏 决策面 62% / 执行流 38%(执行流 live 主秀,重试环全亮)。
  - **≥1280 已完成:** 左栏扩到 ~75%+ 成唯一焦点 / 右栏收窄 ~280px 或折叠"查看工作 ↗"摘要条(N 步·2 轮·自我纠错 1 次)。
  - **1024–1280:** 右执行流折叠为顶条 / 抽屉,决策面占满(running/done 同此布局,done 时右侧呈摘要条)。
  - **<1024:** 单栏纵堆,**决策面优先**(执行流降为可展开摘要)。
- **done 态两态主次(§12.3 #13):** 即上面 ≥1280 的 running/done 两行;1024–1280 与 <1024 的 done 行为见断点段对应行(同一坐标系,勿在别处另立宽度)。
- **Border radius:** 6–8px(卡片 8、chip/角标 4–6)。
- **证据原文卡:** slide-over 420–520px(`--evidence-panel-min/max`),不固定右栏。

## 决策流骨架(左栏顶层 · D9 / Epic 4.1)
**左栏顶层即决策流,不是先报告再单列建议。** market_context / differentiation_thesis 作顶部一句话语境。每条决策 = 一个三件套单元:
- **做什么** —— `action` 命令式动作句(如"本周评估飞书审批接入"),首屏第一眼。挂自解释 `stance` 标签 + `horizon`(短/中/长期)+ `risk_reversibility`(可逆/不可逆)+ `risk_cost`(低/中/高)。
- **为什么** —— `why` reasoning + **依据行常驻可见**(不点就见):最佳证据**原句** + 来源/日期/support_verdict 圆点同行 + "查看原文 ↗"。
- **哪里可能错** —— 反证可展开,写成**对结论的攻击**(`这个建议可能错,因为… 若为真,降级为持续观察`),非 QC 工程日志。
- **utility 标题**(弃内部系统词):下一步怎么做 / 为什么这么判断 / 哪里可能错 / 证据来自哪里。
- **`stance` 锁定值:建议采用 / 需要警惕 / 持续观察**(自解释标签,取代旧稿 下注/防守/观察)。backend enum、frontend TS mirror、UI 用同一字面值,**不加中间映射层**。
- **`持续观察`** 项必须渲染 `watch{metric + threshold + trigger}`(缺则 schema 拒绝,防套话)。
- **`通用浏览` 处境**(用户未设定具体决策):全决策流收敛为"市场观察"语气,命令式 action 降级,明示"你未设定处境,以下为通用判断"。
- **对比矩阵(下方独立支撑区)**,不抢决策流首屏。

## 对比矩阵(§12.3 #9)
- 行=维度(定价/集成/目标用户/核心工作流)、列=竞品;**header sticky 到左栏滚动容器顶 + 首列 sticky-left**。
- 竞品 >3:矩阵内横滚(左栏不横滚)+ 滚动渐隐提示。
- 值 max 2 行截断 + `title`;证据徽章固定挂格底;胜出格 accent 加粗(承融合稿 mockup §12.5)。
- **单元格四态:** 有据三色(support_verdict)/ 查无此项(斜体灰"未找到公开数据")/ 采集失败("—")/ stale(灰角标)。
- **因果桥(Codex 建议纳入):** 点决策 → 对比矩阵自动高亮相关行列。**数据契约:每个单元格的证据徽章携带其支撑 evidence id 列表;因果桥 = 决策 `evidence_refs` ∩ 单元格 evidence ids 求交命中 → 高亮对应行/列。** cell 必须带 evidence id 数组,否则该交互无法实现。

## 实时分析流程(右栏 · Manus 风 · Epic 3.2)
- 等宽字体纵向时间线,左侧带时间戳;**四个直白命名的角色**:采集员 / 分析员 / 撰写员 / 质检员(**严禁** 夜枭/灵犀/灵巧/镜湖 这种花哨代号)。每步右侧标"已完成"+ 证据数。
- **重试环拓扑(招牌时刻):** 一条清晰的青绿色回环箭头从"质检员"绕回"采集员",标注"第2轮 · 证据 12→19",直观显示系统自我纠错。**画成因果回环,不是平铺列表。**
- **每节点必须产出左侧可见变化**(新增证据 / 削弱结论 / 打回 / 更新建议),否则不展示(防 agent theater)。
- 4 角色身份色复用既有 `--seat-1..4`(采集=青绿 / 分析=琥珀 / 撰写=墨蓝 / 质检=松绿)。**`seat-*` 是 v3 office 遗留命名(座位语义),仅作 CSS 内部别名;Epic 3 re-skin 时改名为 `--role-collector/analyst/writer/qc` 去除座位语义。** 本轮不动,避免牵动尚未 re-skin 的组件(surgical)。

## Motion
- **Approach:** 克制、为投影。低强度"机器在运转"+ 单次脉冲式"招牌时刻"。
- **重试环(招牌时刻,§12.3 #7):** **实线青绿单回环**(self-correction 用 `--accent` 非 error 红;红只给质检"打回裁决"圆点);label pill 挂回环转角;沿用(已退役的)DAG 视图招牌动效时长 700–1100ms ease-in-out **单次不循环**;完成后归静态不无限抖动。
- **证据原文卡:** 180ms 从右滑入(opacity + translateX 12→0);引用 pill 与命中句短暂共用高亮,黄从强渐隐到浅 900ms。
- **Easing:** enter ease-out · exit ease-in · move ease-in-out。
- ~~office 角色/speech bubble/handoff 动效~~ —— v4 废弃。

## 命名规范(v4 锁定 · 严禁花哨)
- **角色:** 采集员 / 分析员 / 撰写员 / 质检员(功能直白)。**严禁** 夜枭/灵犀/灵巧/镜湖 等代号。
- **决策 stance:** 建议采用 / 需要警惕 / 持续观察。**严禁** 下注/防守/观察 等看不懂的抽象词。
- **面板标题:** utility 短语(下一步怎么做 / 为什么这么判断 / 哪里可能错 / 证据来自哪里)。**严禁** 内部系统词(镜湖工作台 / DecisionBoard 直译等)。

## Signature Patterns(让"可信+可决策"被记住的三个刻意冒险)
1. **源优先可信度徽章** —— 给**证据链**打标,不给生成答案打分。**双层信任信号(§12.3 #5):** ① 结论级 support_verdict 徽章(佐证充分/部分/不足)+ ② StatusBar **全局三色汇总**(`证据支持度:充分 X · 部分 Y · 不足 Z` 或三色条)。StatusBar 同时承载**用户价值计数口径(§12.3 #6):** `结论 N 条 │ 关键风险 N 个 │ 已打回 N 次 │ 最新证据 日期`,机器状态降 muted。常驻顶栏。
2. **打回可见** —— 执行流回流箭头是品牌时刻:质检否掉弱结论 → 退回重做(`第2轮 · 证据 12→19`),用户亲眼看到系统自我纠错。(右栏执行流招牌)
3. **决策可溯源 + 自我攻击(v4 新增,取代 office)** —— 点任一结论的证据 pill → slide-over 看原文收据;每条决策自带"哪里可能错"反证。30 秒内评委体感"这台机器给我决策、亮出收据、还告诉我它可能错在哪",而不是"AI 黑盒吐了篇报告"。(decision-infrastructure 的 paradigm signal)

## 状态覆盖(§12.4 · Epic 3/4 前必补,不留空不臆测)
每面板 × {loading 渐进 / empty / error / partial / degraded / insufficient_evidence / failed / cancelled} 都定义"用户看到什么":
- **运行中:** 左栏每面板专属 skeleton,由对应 SSE node-done 解锁(DecisionBoard←done / Comparison←analyze-done / EvidencePill←evidence-list seed / Contradiction←qc-done);解锁前显示进度提示(非通用 spinner),进度文案**随 `evidenceCountSnapshots` 实时跳数**(如 Comparison"分析员正在比较 3 个竞品定价…"计数动态更新)。loading 文案 ≠ empty 文案。
- **0 决策:** DecisionBoard 不隐藏 → 解释性空卡("本轮未形成可建议的行动"+ 原因 + 引导回证据)。
- **degraded:** StatusBar 琥珀/红 banner"证据不足,以下结论置信度下降";决策项视觉弱化 + 每条 caveat。
- **insufficient_evidence:** 决策面不留空 → 有温度"处境卡片"(为什么没结论 + 已有证据诚实总结 + 主操作 放宽竞品范围/重新发现竞品/查看 N 条证据)。灰条 + 虚线边 + 斜体不臆测。
- **原文卡三态:** quote 缺失("原文已抓取但未提取到命中引语"+仍给链接)/ source 不可达(禁用"查看原文"标"来源链接不可用"非死链)/ stale(灰角标"采集于 N 天前")。
- **执行流 failed/cancelled:** 失败节点红 + 可读原因(非 raw exception)+ 其后灰"未执行";cancelled 保留已完成节点、**未跑节点灰显"已停止"** + 顶"已停止·N 秒前";重试环中断箭头呈"中断"。左栏已填充面板保留(诚实展示已得),**未解锁面板标"因运行中断未生成"**。

## 关键组件基调
- **决策流单元(DecisionBoard 内):** 8px 圆角、16px 内边距、硬边框、无浮动玻璃;三件套垂直布局(做什么 / 为什么含依据行 / 哪里可能错折叠)。**排版映射(引 §Typography 档位,勿写"大字/小号"留空):做什么 = 22(区块头,首屏第一眼)/ 为什么 why 正文 = 15 / 依据行原句 = 15 / 哪里可能错折叠正文 = 15 / stance·horizon·risk 角标 = 12 mono / utility 标题 = 13 muted。**
- **依据行(视觉主角,§12.3 #4):** 浅 `--accent-soft` 底 或 2px `--accent` 竖条;support_verdict 圆点放大前置;**露最佳证据原句**(不只来源名);"查看原文"accent + 下划线。
- **EvidencePill:** `[1]` mono 小号、青绿描边;claim 级 inline;hover popover → quote / source_title / fetched_at / support_verdict;**无 provider / confidence**;点击 → 原文 slide-over。
- **证据原文 slide-over:** 420–520px 右滑;同时仅一条;引文区 max-height 内滚;ESC / 遮罩关;保留从 pill 引线提示。
- **对比矩阵:** header sticky + 首列 sticky-left;四态单元格;证据徽章挂格底。
- **StatusBar:** 顶栏,两组信息:(1) 用户价值计数口径(结论 N 条 │ 关键风险 N 个 │ 已打回 N 次 │ 最新证据 日期,§12.3 #6);(2) 全局 support_verdict 三色汇总(充分/部分/不足,§12.3 #5 第二层,与结论级徽章构成双层)。`●状态` = 运行态指示点(idle/running/done/degraded),muted 色置右;degraded 由它转琥珀/红 + 触发状态覆盖段的 banner(职责:●状态=点状态指示,banner=整条说明文案)。
- **ContradictionPanel(质检问题):** 复用 QC issue,用 sanitized `/qc` detail(**严禁** raw exception/model text)。
- **SelfAuditTrace:** 审计轨迹(放宽 → +N 证据 → 重新质检)。
- **insufficient_evidence 空态:** 灰条 + 虚线边 + 斜体"未找到公开数据",不留空不臆测。

## a11y(§12.3 #12)
- 键盘焦点序:证据 popover → 原文卡 → 矩阵 → 决策卡;原文卡焦点管理 + Esc 关。
- 对比度 ≥4.5:1(浅黄高亮上的字、灰字);触摸目标 44px;ARIA landmarks。
- support_verdict 色盲双编码(颜色 + 形状),不只靠色。

## Decisions Log
| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-21 | 初版设计系统 | `/design-consultation` 生成;记忆点=可信/溯源;Claude+Codex 跨模型收敛于"暖纸白+机构青绿+研报控制台+把溯源/打回做成视觉主角";字体取 IBM Plex 超级家族 |
| 2026-05-27 | v3 paradigm pivot:虚拟办公室 + 拟物动物 + 实时 streaming | 触发 = Task 6.5 spike user 反馈 DAG 节点过于工程师视角;**v4 已废弃此方向**(见下) |
| 2026-05-30 | **v4 paradigm pivot:证据驾驶舱(Evidence Cockpit)** | 触发 = user "跟 ChatGPT 没区别 / 要原子弹震撼";根因 = 输出 paradigm 同档(plain markdown 容器),4-agent 工程深度被扁平化。决策 = 从 report generator(同 category)跳到 **decision infrastructure**(different category):单一 Manus 分屏 cockpit(左决策流 / 右实时执行流)+ 证据常驻可溯源 + 重试环可见 + 自我攻击反证。**保留** = 字体 100% + 24 色板 100% + spacing 100% + Signature #1/#2;**废弃** = 双气质叙事 / office / 拟物动物 / 夜枭灵犀灵巧镜湖代号 / DAG 作 paradigm / 虚拟办公室 layout / office 组件与动效 / ReportSheet drawer;**新增** = support_verdict 三色 token + 决策流骨架 + Manus 执行流 + 重试环 motion + 响应式断点 + 状态覆盖矩阵 + 命名规范。评审 = `/plan-eng-review` + `/plan-design-review` + Codex outside-voice 双 CLEARED(见 `docs/superpowers/plans/2026-05-30-rivalradar-v0.4-evidence-cockpit.md` §12)|
