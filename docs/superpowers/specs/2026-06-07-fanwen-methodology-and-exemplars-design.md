# 设计文档:范文库扩充 —— 竞品分析报告方法论 + 新范例

> 日期:2026-06-07
> 阶段:brainstorming → spec(待用户评审 → writing-plans)
> 关联:`DESIGN.md`(v4 证据驾驶舱)、`frontend/src/lib/samples.ts`、`references/README.md`(Rubric v1)

## 1. 背景与目标

范文库(`/samples`)目前只有 4 篇范例(ref-01..04),且时间偏旧(2019–2024)。用户反馈两点:
1. 范例需要补充——更新、更高质量、最好 2026 年。
2. **更重要的**:范文库不该只堆某个赛道的范例,而应沉淀一套**通用方法论**——"竞品分析报告到底该怎么写",作为读者读懂/对照范例的标尺,放进范文库展示。

**目标:**
- 新增一篇原创《竞品分析报告方法论》,综合 3 篇权威参考 + 对齐 RivalRadar 自己的 10 条 rubric,在范文库中作为"库章/标尺"呈现。
- 同时新增 4 篇结构互补的 2026/2025 高质量范例(已验证可达)。

**非目标(本轮不做):**
- 不改 cockpit 主流程 / 决策管道 / 后端。
- 不归档付费墙/海外样本全文(Gartner、QuestMobile)——仅在方法论内作"框架样本"外链引用。
- 不做范文库的搜索/筛选大改(分区标题 + 结构徽章即可)。

## 2. 交付物总览

| 交付物 | 内容 | 文件 |
|---|---|---|
| A | 《竞品分析报告方法论》原创长文(8 部分) | `frontend/public/samples/methodology.md`(新) |
| B | 前端呈现:标尺带 + 方法论详情页 + 三联锚定 + 标尺速览 | `SamplesPage.tsx` / `SampleView.tsx` / `lib/samples.ts` / `Markdown.tsx`(改) |
| C | 4 篇新范例(抓正文 + 配图 + 入库) | `frontend/public/samples/ref-05..08.md` + `ref-0X-img/`(新) |

## 3. 交付物 A —— 《竞品分析报告方法论》

### 3.1 参考来源(用户指定,方法论必须引用)
| 参考 | 贡献 | 读取状态 |
|---|---|---|
| [woshipm 张在旺《如何写一份靠谱的竞品分析报告》](https://www.woshipm.com/evaluating/5672064.html)(《有效竞品分析》作者) | 三类目的、产品思维写报告、一页纸竞品画布、**总-分-总结构**、4 条铁律(含"不编造数据") | ✅ 全文已读 |
| [飞书《竞品分析报告模板要点》](https://www.feishu.cn/template/competitive-product-analysis-report-key-aspects) | 通用维度(产品功能/市场定位/客户反馈/价格策略)+ 4 步流程 | ✅ 全文已读 |
| [知乎《保姆级竞品分析报告写作模板》](https://zhuanlan.zhihu.com/p/668621286) | 分析模型工具箱(SWOT/波特五力/4P/BCG/GE矩阵/价值链/市场地图) | ⚠️ 登录墙,经搜索取得框架 |

### 3.2 内容大纲(8 部分,三篇 + rubric + 范例融合,非抄单篇)
0. **引言** —— 范文库的"怎么读":先懂方法,再看范例;好报告 ≠ 功能罗列,是**有据的决策建议**(呼应 RivalRadar 定位)。
1. **先定目的与目标**(woshipm)—— 三类目的(决策支持/学习借鉴/市场预警)+ 产品思维 7 问 + 一页纸竞品画布 MVP 防返工。
2. **选对竞品**(飞书 + 范例)—— 直接/间接/潜在;同定位同体量优先(ref-01 选钉钉企微的理由);四象限定位(Airbnb 案例)。
3. **定分析维度**(飞书四方面 + ref-01 七层)—— 维度服务于目标,不是越多越好。
4. **用分析模型,不止罗列**(知乎工具箱)—— SWOT/波特五力/4P/BCG/价值链/市场地图;模型为推出**策略/结论**服务。
5. **报告结构:总-分-总**(woshipm)—— 总述/分述(配对比矩阵)/总结建议(最有价值,画龙点睛)。
6. **写作铁律**(woshipm 4 条 + RivalRadar 反幻觉)—— 看用户选形式、多维度易协作、可执行可维护、**存素材有来源·拿不到数据要说明绝不编造**、拒绝"持续关注/加大力度"套话。
7. **怎么判断写得好**(连接 RivalRadar Rubric v1)—— 直接呈现 10 条 rubric(A 组结构与覆盖 5 条 + B 组质量与洞察 5 条)+ 等级阈值,并对照本库范例六种优秀骨架(对决/横评/批判/评论/框架/数据)。
8. **参考来源** —— 显式引用上面 3 个 URL + 本库范例出处。

### 3.3 与 RivalRadar Rubric 的连接(用户已确认"连接")
- rubric 唯一来源:`references/README.md` 的 **Rubric v1**(10 条 × 0-3)。方法论第 7 部分镜像其 10 条 + 等级阈值。
- 映射关系(三联锚定 chip 用):
  | 方法论部分 | 对应 rubric 条目 |
  |---|---|
  | ② 选对竞品 | #1 市场锚定 |
  | ③ 定维度 | #3 维度粒度 |
  | ④ 分析模型 | #7 战略推论 · #8 Schema 深度 |
  | ⑤ 总-分-总结构 | #2 对比矩阵 · #5 定价模型 |
  | ⑥ 写作铁律 | #4 信息溯源 · #10 反幻觉信号 · #6 数据密度 |
  | ⑦ 判好坏 | 全 10 条 + 等级阈值 · #9 时间分层 |

## 4. 交付物 B —— 前端呈现设计

> 立意:方法论 = 范文库的**评判标尺 / 库章**,不是网格里一张卡。记忆点 = **三联锚定**(每条原则亮出 ① 参考来源 ② 对应 rubric 条目 ③ 库内活范例),把产品"决策连证据"范式映射到内容上。全部严守 DESIGN.md(IBM Plex / 暖纸白#F6F5F1 + 机构青绿#0F6B5F / 边框优先于阴影 / 禁 emoji·卡通·玻璃·渐变·紫)。

### 4.1 Surface A —— `/samples` 重构:顶部「标尺带」+ 下方「范例区」
```
← 返回首页
▦ 竞品分析范文库
公开渠道的他人专业竞品分析报告,外加一套「怎么写」的方法论标尺。

┃ 方法论 · 本库的评判标尺                                    (mono kicker, --accent)
┃ ┌──────────────────────────────────────────────────────┐
┃ │ 竞品分析报告怎么写                          〔库章〕   │  全宽 · --surface 底 · 1px --border
┃ │ 8 步框架 · 3 篇权威参考 · 对齐 RivalRadar 10 条评分     │  左 3px --accent 竖条(依据行母题)
┃ │ 目的→选竞品→维度→分析模型→总分总结构→反幻觉铁律→判好坏 │  视觉比范例卡"重"
┃ │ [ 阅读方法论 → ]      参考来源:woshipm · 飞书 · 知乎   │
┃ └──────────────────────────────────────────────────────┘

范例报告 · 他人公开发表(8 = 现有 4 + 新增 4)
┌───────────────┐ ┌───────────────┐
│ 双雄对决   2026│ │ 全矩阵横评 2026│   现有卡片网格不变,仅加分区标题 + 结构徽章
└───────────────┘ └───────────────┘
```
**规格:** 标尺带全宽、`--surface`、`1px --border`、`8px` 圆角、**左 3px `--accent` 竖条**;kicker `IBM Plex Mono` 12px uppercase `--accent`;标题 18–22px;8 步路径 `13px --text-muted` 单行;主按钮 `--accent` 描边 + `--accent-soft` 底。无阴影/渐变/emoji。范例区加分区标题「范例报告 · 他人公开发表(N)」+ 每卡结构徽章(双雄对决/全矩阵横评/批判视角/战略评论)。

### 4.2 Surface B —— 方法论详情页(复用 `SampleView` 杂志布局,换报头 + 两个招牌件)
```
← 返回范文库                                         查看 3 篇参考 ↗
─────────────────────────────────────────────────────────────
方法论 · 本库导览                              kicker 区别于范例的"他人公开发表"
竞品分析报告怎么写                              28px 页面标题
综合 woshipm/飞书/知乎 三篇权威 + 对齐 RivalRadar 10 条 rubric   副题 muted
──── accent rule(实线,非渐变)────

┌ 目录 ─┐  ┌─ 阅读栏 760px ──────────────────────────────────┐
│①目的  │  │ 〔标尺速览〕①定目的 ②选竞品 ③维度 ④模型          │ 招牌件1:8步一览卡
│②选竞品│  │           ⑤总分总 ⑥反幻觉铁律 ⑦判好坏 ⑧来源     │ 1px border·青绿 mono 编号·点跳锚
│ …     │  │ ## ① 先定目的与目标 … 正文 …                     │
│⑧来源  │  │ ┌ 参考 woshipm · rubric #1 市场锚定 · 范例 全矩阵横评↗ ┐│ 招牌件2:三联锚定 chip
│       │  │ └──────────────────────────────────────────────────┘│ mono 12px·--accent 描边(复用 EvidencePill)
└───────┘  └─────────────────────────────────────────────────┘
```
- **标尺速览卡**:阅读栏顶部,`1px --border` + `8px` 圆角,8 步用 `IBM Plex Mono` 青绿编号,点击锚跳(锚来自 `parseHeadings`)。给方法论"操作手册"气质。
- **三联锚定 chip**:每节末一行 `IBM Plex Mono 12px`、`--accent` 描边;三段 `参考来源 · 对应 rubric · 库内范例↗`。范例名为 react-router 站内链。
- 报头 kicker/副题随 `type==='methodology'` 切换文案;免责声明行替换为"本文为 RivalRadar 原创方法论,综合公开资料编写,来源见文末"。

### 4.3 数据模型变更(`lib/samples.ts`)
```ts
export interface Sample {
  id: string
  title: string
  publisher: string
  author: string
  date: string
  competitors: string[]
  kind: 'md' | 'pdf'
  type?: 'report' | 'methodology'   // 新增,默认 'report'
  structure?: string                 // 新增,范例结构徽章:双雄对决/全矩阵横评/批判视角/战略评论
  file: string
  sourceUrl?: string
  sourceUrls?: string[]              // 新增,方法论多来源(3 篇参考)
  note: string
}
```
- `SamplesPage`:`SAMPLES.filter(type==='methodology')` 渲染为顶部标尺带;其余进网格(加分区标题)。
- `SampleView`:`type==='methodology'` → 报头文案分支 + 标尺速览。
- `Markdown.tsx`:支持站内 `/samples/:id` 链接走 `react-router` `<Link>`(其余 markdown 即可表达三联锚定与正文)。其余渲染不动。

## 5. 交付物 C —— 4 篇新范例(结构互补)

| id | 标题 | 出处 / 日期 | 结构徽章 | sourceUrl |
|---|---|---|---|---|
| ref-05 | 抢客户、战表格、押AI:钉钉和飞书继续贴身肉搏 | 36氪(听潮Ti)/ 2026-02-25 | 双雄对决 | https://36kr.com/p/3697005094203910 |
| ref-06 | 飞书、企业微信、钉钉三款协同办公软件深度对比与行业洞察 | CSDN / 2026-03-09 | 全矩阵横评 | https://blog.csdn.net/s867859765/article/details/147877238 |
| ref-07 | 协同办公概念"泛滥",中小企业和打工人真的需要吗? | 21经济网 / 2025-12-05 | 批判视角 | https://www.21jingji.com/article/20251205/herald/7dd1dd58b4c6135a57b884a3e6758ba3.html |
| ref-08 | 这次,钉钉领先半目 | 人人都是产品经理(潘乱)/ 2026-03-23 | 战略评论 | https://www.woshipm.com/ai/6361304.html |

- 抓取约定沿用 ref-01..03:正文存 `public/samples/ref-0X.md`(带 YAML frontmatter:source_url/title/author/publisher/published_date/downloaded_at[北京时间]/language/length_chars/competitors/report_group/quality_score/quality_notes),内联配图下到 `ref-0X-img/`,markdown 用 `![配图](/samples/ref-0X-img/NN.png)`。
- 版权:与现有一致,明确标注出处 + "非 RivalRadar 生成,版权归原作者";仅作参照。
- 框架样本(不归档,方法论内外链):[Gartner 魔力象限](https://www.gartner.com/en/documents/7112430)、[QuestMobile 年度大报告](https://www.questmobile.com.cn/research/report/2031215896219979777/)。
- 抓取风险:woshipm/知乎反爬 + WSL2 Clash —— 抓取走 `/browse`(已验证可直连国内站,unset 代理 + NO_PROXY)。某篇正文/配图抓不全时,降级为"仅元数据 + 原文链接"卡(不编造)。

## 6. 文件清单

**新增:**
- `frontend/public/samples/methodology.md`(方法论正文 + 三联锚定 + 文末 3 来源)
- `frontend/public/samples/ref-05.md` .. `ref-08.md` + `ref-05-img/` .. `ref-08-img/`

**改动(外科手术式):**
- `frontend/src/lib/samples.ts`:加 `type`/`structure`/`sourceUrls` 字段 + 5 个新条目(methodology + ref-05..08)
- `frontend/src/pages/SamplesPage.tsx`:标尺带 + 范例分区标题 + 结构徽章
- `frontend/src/pages/SampleView.tsx`:methodology 报头分支 + 标尺速览
- `frontend/src/components/report/Markdown.tsx`:站内 `/samples/:id` 链接走 react-router

## 7. 设计系统对齐(DESIGN.md)
- 色:仅用 `--accent #0F6B5F` / `--accent-soft #DDEBE7` / `--bg` / `--surface` / `--surface-subtle` / `--border` / `--text-*`。无紫/渐变(方法论详情页分隔线用实线 accent,不沿用现有范例页的 accent→transparent 渐隐)。
- 字:IBM Plex Sans(SC)正文 / IBM Plex Mono(kicker / 编号 / 三联锚定 chip)。字号档 12/13/15/18/22/28。
- 间距:8px base。圆角:卡片 8 / chip 4–6。
- 边框承担结构,无阴影(范文库无浮层)。禁 emoji/卡通/玻璃。
- 时间:北京时间(`Asia/Shanghai`)署名。中文界面。

## 8. 验收标准
1. `/samples` 顶部出现标尺带,视觉明显区别于范例卡;范例区有分区标题 + 结构徽章。
2. 点"阅读方法论"进入详情页:methodology 报头 + 标尺速览(8 步锚跳)+ 8 部分正文 + 每节三联锚定 chip(范例名可点跳库内范例)+ 文末引用 3 个指定 URL。
3. 方法论第 7 部分完整呈现 Rubric v1(10 条 + 等级阈值),与 `references/README.md` 一致。
4. ref-05..08 可在范文库阅读(正文 + 配图渲染正常),各带出处与原文链接。
5. `tsc -b` 绿;`/browse` 真打 `/samples` 与方法论详情页:无 React error、TOC 滚动高亮正常、深浅色均符合 DESIGN.md、零 emoji/渐变/紫。
6. 现有 ref-01..04 与 cockpit 主流程不受影响(回归)。

## 9. 风险与取舍
- **知乎来源未读到全文**:方法论引用其框架(经搜索证实),文末如实标注"经公开检索整理"。
- **范例抓取受反爬/代理影响**:走 `/browse` 直连;抓不全则降级为元数据卡,绝不编造正文。
- **Markdown 站内链接增强**:仅新增对 `/samples/:id` 内链的 `<Link>` 处理,不动其余渲染,避免回归。
- **范围**:methodology + 4 范例同一轮(用户确认);Gartner/QuestMobile 仅外链不归档。

## 10. 参考来源(方法论必引)
- woshipm 张在旺《如何写一份靠谱的竞品分析报告》https://www.woshipm.com/evaluating/5672064.html
- 飞书《竞品分析报告模板要点》https://www.feishu.cn/template/competitive-product-analysis-report-key-aspects
- 知乎《竞品分析报告怎么写?请收下这份保姆级竞品分析报告写作模板!》https://zhuanlan.zhihu.com/p/668621286
- RivalRadar Rubric v1:`references/README.md`
