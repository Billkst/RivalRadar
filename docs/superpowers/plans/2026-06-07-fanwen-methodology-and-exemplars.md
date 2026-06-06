# 范文库扩充(方法论 + 4 篇新范例)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在范文库新增一篇原创《竞品分析报告方法论》(作为库的"标尺/库章"呈现)+ 4 篇结构互补的 2026/2025 范例,严守 DESIGN.md。

**Architecture:** 纯前端 + 静态资源,零后端改动。复用现有 `SampleView` 杂志渲染 + `Markdown` 渲染器;给 `Markdown` 加两处增强(站内/外链、三联锚定 chip);`lib/samples.ts` 加 `type/structure/sourceUrls` 字段区分方法论与范例;`SamplesPage` 把方法论渲成顶部标尺带、范例进分区网格;方法论与范例正文是 `frontend/public/samples/*.md` 静态资源,运行时 fetch 渲染。

**Tech Stack:** React 19 + react-router-dom 6 + Tailwind(DESIGN.md token)+ pnpm;无 JS 单测 runner —— 前端验证 = `pnpm build`(`tsc -b && vite build`)+ `/browse` 真打;`/browse` 抓取范例正文/配图。

**测试现实(重要):** 本仓前端无 Vitest(`package.json` 的 `test` 是占位 echo)。按 CLAUDE.md 测试哲学 + 项目记忆,前端的"测试"= **类型/构建门**(`cd frontend && pnpm build`,即 `tsc -b && vite build`,**不是** `tsc --noEmit`)+ **`/browse` 真打运行时验证**。本计划无后端改动,`pytest` 仅作回归 sanity(应保持 350 绿)。

---

## File Structure(决策锁定)

**新增静态资源:**
- `frontend/public/samples/methodology.md` —— 原创方法论正文(8 个 h2 段 + 三联锚定 chip + 文末 3 来源)。职责:方法论内容载体。
- `frontend/public/samples/ref-05.md` … `ref-08.md` + `ref-05-img/` … `ref-08-img/` —— 4 篇新范例正文 + 配图。职责:范例内容载体。

**改动(外科手术式,各文件单一职责):**
- `frontend/src/components/report/Markdown.tsx` —— 加两处增强:① 行内 `[text](url)` 链接(站内走 `<Link>`/外链走 `<a>`)② `锚定: ` 行 → 三联锚定 chip。职责:渲染器。
- `frontend/src/lib/samples.ts` —— `Sample` 接口加 `type/structure/sourceUrls` 字段 + 5 个新条目(methodology + ref-05..08)。职责:范文注册表。
- `frontend/src/pages/SamplesPage.tsx` —— 方法论渲成顶部标尺带;范例进分区网格 + 结构徽章。职责:范文库列表页。
- `frontend/src/pages/SampleView.tsx` —— `type==='methodology'` 报头分支 + 标尺速览卡。职责:范文阅读页。

**不动:** 后端全部、cockpit、`markdownHeadings.ts`(复用其 `headingId`/`parseHeadings`)、`globals.css`(token 已齐)。

---

## Task 1: Markdown 渲染器增强(站内/外链 + 三联锚定 chip)

**Files:**
- Modify: `frontend/src/components/report/Markdown.tsx`

> 为什么先做:方法论与范例都用 `[text](url)`,而现渲染器把它当字面文本输出;三联锚定 chip 也需此处支持。这是 A/C 两交付物的地基。

- [ ] **Step 1: 加入 react-router `Link` 引入 + 链接解析函数**

在 `Markdown.tsx` 顶部 import 区(`import * as React` 下方)加:

```tsx
import { Link } from 'react-router-dom'
```

在 `renderCitations` 函数**之后**、`renderInline` 之前,新增链接解析(站内 `/...` 走 router,`http(s)` 走新标签页,其他 scheme 退为字面以防注入):

```tsx
// 行内 markdown 链接 [label](href):站内 /samples/:id 走 react-router(SPA 不刷新),
// http(s) 外链走新标签页 + noopener;其余 scheme(javascript: 等)退为字面文本防注入。
// [ev_xxx] 无 `(`,不会被本正则吃到,仍由 renderCitations 处理。
const LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/g
function renderLinksAndCites(text: string, keyPrefix: string): React.ReactNode[] {
  const out: React.ReactNode[] = []
  let last = 0
  let i = 0
  LINK_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = LINK_RE.exec(text)) !== null) {
    if (m.index > last) out.push(...renderCitations(text.slice(last, m.index), `${keyPrefix}p${i}`))
    const label = m[1]
    const href = m[2].trim()
    if (href.startsWith('/')) {
      out.push(
        <Link key={`${keyPrefix}l${i}`} to={href} className="text-accent underline-offset-2 hover:underline">
          {label}
        </Link>,
      )
    } else if (/^https?:\/\//i.test(href)) {
      out.push(
        <a
          key={`${keyPrefix}l${i}`}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline-offset-2 hover:underline"
        >
          {label}
        </a>,
      )
    } else {
      out.push(<React.Fragment key={`${keyPrefix}l${i}`}>{m[0]}</React.Fragment>)
    }
    last = m.index + m[0].length
    i++
  }
  if (last < text.length) out.push(...renderCitations(text.slice(last), `${keyPrefix}pE`))
  return out
}
```

- [ ] **Step 2: 让 `renderInline` 走链接解析**

把 `renderInline` 里两处 `renderCitations(...)` 调用替换为 `renderLinksAndCites(...)`(粗体段内 + 普通段)。改后:

```tsx
function renderInline(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = []
  text.split(/(\*\*[^*]+\*\*)/g).forEach((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      out.push(
        <strong key={`b${i}`} className="font-semibold text-text-primary">
          {renderLinksAndCites(part.slice(2, -2), `b${i}`)}
        </strong>,
      )
    } else {
      out.push(...renderLinksAndCites(part, `s${i}`))
    }
  })
  return out
}
```

- [ ] **Step 3: 加「三联锚定 chip」块级分支**

在主循环里,**在 blockquote(`if (line.startsWith('> '))`)分支之前**插入(prefix 常量放文件顶层常量区,如 `CITE_SPLIT` 旁):

```tsx
const ANCHOR_PREFIX = '锚定: '
```

块分支(放 hr 分支之后、heading 分支附近均可,但务必在通用段落 `<p>` 之前):

```tsx
    // 三联锚定 chip(方法论专用):mono + accent 描边,内含站内/外链。
    if (line.startsWith(ANCHOR_PREFIX)) {
      blocks.push(
        <div
          key={blocks.length}
          className="my-3 rounded border border-accent/40 bg-accent-soft px-2.5 py-1.5 font-mono text-[12px] leading-relaxed text-text-muted"
        >
          {renderInline(line.slice(ANCHOR_PREFIX.length))}
        </div>,
      )
      continue
    }
```

- [ ] **Step 4: 类型/构建门**

Run: `cd frontend && pnpm build`
Expected: 退出码 0(`tsc -b && vite build` 全绿,无类型错误)。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/report/Markdown.tsx
git commit -m "feat(samples): Markdown 支持站内/外链 + 三联锚定 chip"
```

---

## Task 2: 撰写《竞品分析报告方法论》正文

**Files:**
- Create: `frontend/public/samples/methodology.md`

> 这是内容交付物。下面给出**精确的结构契约**(frontmatter + 8 个 h2 段标题 + 每段必含要素与三联锚定 chip + 第 7 段必嵌的 Rubric 表 + 文末 3 来源)。撰写时融合 3 篇参考(见 spec §3.1),用中文,语气克制专业,显式标注"AI 综合/原创",杜绝套话。

- [ ] **Step 1: 写 frontmatter + 引言**

文件开头(YAML frontmatter,北京时间;`type` 由 samples.ts 控制,这里仅留元信息):

```markdown
---
title: 竞品分析报告怎么写 —— RivalRadar 范文库方法论
author: RivalRadar(原创,综合公开方法论编写)
publisher: RivalRadar
published_date: 2026-06-07
language: zh-CN
kind: methodology
sources:
  - https://www.woshipm.com/evaluating/5672064.html
  - https://www.feishu.cn/template/competitive-product-analysis-report-key-aspects
  - https://zhuanlan.zhihu.com/p/668621286
---

# 竞品分析报告怎么写

> 范文库的"怎么读":先懂方法,再看范例。一份好的竞品分析报告不是功能罗列,而是**有据的决策建议** —— 每个判断都连得到证据,每条结论都经得起"哪里可能错"的追问。本文综合三篇业内方法论,并对齐 RivalRadar 自己的 10 条评分标尺。
```

- [ ] **Step 2: 写 8 个 h2 段(标题用纯名称,不带序号 —— 序号由「标尺速览」自动加)**

按以下 8 个 `##` 段撰写,每段末尾**必须有一行 `锚定: ` chip**(格式见 Step 3)。各段必含要素:

```markdown
## 先定目的与目标

(源:woshipm 张在旺)三类目的——决策支持 / 学习借鉴 / 市场预警——决定整篇取舍。用产品思维把报告当"产品":写前问清「给谁看、解决什么问题、什么场景用」。先用一页纸竞品画布跟需求方确认"选哪些竞品、比哪些维度",再动手,降低返工。

## 选对竞品

(源:飞书模板 + 范例)区分直接 / 间接 / 潜在竞品;优先同定位同体量(范例 ref-01 选钉钉、企业微信,正因三者都是超级移动办公平台且体量相当)。早期可用价格×模式四象限快速定位(Airbnb BP 案例)。

## 定分析维度

(源:飞书四方面 + ref-01 七层)通用四方面:产品功能 / 市场定位 / 客户反馈 / 价格策略。可深化为结构化层次(范例 ref-01 的战略层→范围层→…→表现层)。维度服务于目标,不是越多越好。

## 用分析模型,不止罗列

(源:知乎工具箱)SWOT(扬长/避短/趋利/避害)、波特五力、4P、波士顿矩阵、GE 矩阵、价值链、市场地图。模型是为了推出**策略与结论**,不是装饰;罗列功能而不给判断 = 失败的竞品分析。

## 报告结构:总-分-总

(源:woshipm)总述(背景/目的/目标/思路/目录)→ 分述(按维度逐项分析 + 每维小结,配对比矩阵)→ 总结(结论 + 可执行建议 + 附录)。总结篇幅虽短,却是画龙点睛、最有价值的部分。

## 写作铁律

(源:woshipm 四条 + RivalRadar 反幻觉)看用户选形式;多维度易协作;可执行可维护;**存素材、有来源——拿不到的数据要在报告里说明,绝不编造**;结论要可落地,拒绝"持续关注 / 加大力度 / 深入研究"这类套话。

## 怎么判断写得好

不是看内容多、PPT 精美,而是看是否达成目标、是否有据可信。RivalRadar 把"好"量化成 10 条评分标尺(下表),并用本库范例展示六种优秀骨架:对决型 / 全矩阵横评 / 批判视角 / 战略评论 / 框架范式 / 数据底座。

(此处嵌入 Step 4 的 Rubric 表)

## 参考来源

(此处写 Step 5 的来源列表)
```

- [ ] **Step 3: 每段末尾加三联锚定 chip(精确映射,见 spec §3.3)**

在对应 `##` 段正文之后各加一行(注意是 `锚定: ` 前缀,Task 1 已支持渲染):

```markdown
锚定: 参考 [woshipm 张在旺](https://www.woshipm.com/evaluating/5672064.html) · 对应标尺 全局目的 · 看范例 [战略评论](/samples/ref-08)
```
逐段映射:
- 选对竞品 → `对应标尺 #1 市场锚定` · 看范例 `[双雄对决](/samples/ref-05)`
- 定分析维度 → `对应标尺 #3 维度粒度` · 看范例 `[全矩阵横评](/samples/ref-06)`
- 用分析模型 → `对应标尺 #7 战略推论 · #8 Schema 深度` · 看范例 `[战略评论](/samples/ref-08)`
- 报告结构 → `对应标尺 #2 对比矩阵 · #5 定价模型` · 看范例 `[全矩阵横评](/samples/ref-06)`
- 写作铁律 → `对应标尺 #4 信息溯源 · #10 反幻觉信号` · 看范例 `[批判视角](/samples/ref-07)`
- 怎么判断写得好 → `对应标尺 全 10 条` · 看范例 `[双雄对决](/samples/ref-05)`
- 先定目的与目标 → `对应标尺 贯穿全篇` · 看范例 `[战略评论](/samples/ref-08)`

每个 chip 内的 `[...](https://woshipm...)`/`[...](https://feishu...)`/`[...](https://zhihu...)` 三处来源至少各出现一次(分散到相关段),保证三来源都被引用。

- [ ] **Step 4: 在「怎么判断写得好」段嵌入 Rubric v1 表(镜像 `references/README.md`,逐字一致)**

```markdown
**RivalRadar Rubric v1(10 条 × 0–3 分 = 30 满分)**

| # | 条件 | 0 分 | 1 分 | 2 分 | 3 分 |
|---|---|---|---|---|---|
| 1 | 市场锚定 | 无 | 提及行业 | 量级数字 / 玩家 | 赛道格局 + 主要玩家定位 |
| 2 | 对比矩阵 | 无 | 表格但 < 3 行 | 3-5 行 / 单维 | ≥ 6 行 / 多维 + 引用 |
| 3 | 维度粒度 | 单层 | 2 层粒度 | 3 层 | 4 层 + 子项有引用 |
| 4 | 信息溯源完整 | 无引用 | 部分引用 | 多数引用 + 部分 broken | 100% 引用 + 0 broken + URL + as_of |
| 5 | 定价模型 | 无 | 列名/价 | 名/价/计费/限额 | 全字段 + 跨竞品对比 |
| 6 | 数据密度 | 模糊形容 | 部分数字 | 多数据点 | 数字 + 来源 + as_of |
| 7 | 战略推论 | 罗列功能 | 单段判断 | 推论链 | 因为 X 所以 Y + 母公司战略映射 |
| 8 | Schema 深度 | 不结构化 | 列表 | SWOT 或对比 | SWOT + 对比 + 用户画像 全 |
| 9 | 时间分层 | 无 | 单层(现状) | 现状 + 未来 | 短/中/长期 + actionable |
| 10 | 反幻觉信号 | 套话满 | 部分 hedging | 多数有据 | 0 套话 + 0 broken refs + 显式 fact/judgment 分层 |

等级:25-30 Excellent(与权威厂商报告同档)/ 20-24 Good(可直接给产品团队决策用)/ 15-19 Adequate / 10-14 Weak / <10 Fail。
```

- [ ] **Step 5: 写「参考来源」段(必引用户指定的 3 个 URL)**

```markdown
本方法论综合以下公开方法论编写(原文链接):

- [如何写一份靠谱的竞品分析报告(张在旺,《有效竞品分析》作者)](https://www.woshipm.com/evaluating/5672064.html) —— 人人都是产品经理
- [竞品分析报告模板要点](https://www.feishu.cn/template/competitive-product-analysis-report-key-aspects) —— 飞书
- [竞品分析报告怎么写?保姆级写作模板](https://zhuanlan.zhihu.com/p/668621286) —— 知乎

评分标尺源自 RivalRadar `references/README.md` 的 Rubric v1(基于 4 份权威竞品报告倒推)。
```

- [ ] **Step 6: 校验结构契约**

Run: `cd frontend && node -e "const fs=require('fs');const md=fs.readFileSync('public/samples/methodology.md','utf8').replace(/^---\n[\s\S]*?\n---\n?/,'');const h2=(md.match(/^## .+$/gm)||[]).length;const chips=(md.match(/^锚定: /gm)||[]).length;const srcs=['woshipm.com/evaluating/5672064','feishu.cn/template/competitive','zhihu.com/p/668621286'].every(s=>md.includes(s));console.log('h2=',h2,'chips=',chips,'all3sources=',srcs);if(h2!==8||chips<7||!srcs)process.exit(1)"`
Expected: `h2= 8 chips= 7 all3sources= true`,退出码 0。

- [ ] **Step 7: Commit**

```bash
git add frontend/public/samples/methodology.md
git commit -m "feat(samples): 新增《竞品分析报告方法论》原创长文"
```

---

## Task 3: `lib/samples.ts` 接口字段 + 方法论条目

**Files:**
- Modify: `frontend/src/lib/samples.ts`

- [ ] **Step 1: 扩展 `Sample` 接口**

把 `kind` 字段下方加三个可选字段:

```ts
  kind: 'md' | 'pdf'
  type?: 'report' | 'methodology' // 默认 report;methodology = 范文库方法论(库章)
  structure?: string // 范例结构徽章:双雄对决 / 全矩阵横评 / 批判视角 / 战略评论
  file: string
  sourceUrl?: string
  sourceUrls?: string[] // 方法论多来源(3 篇参考)
  note: string
```

- [ ] **Step 2: 在 `SAMPLES` 数组**最前**插入方法论条目**

```ts
  {
    id: 'methodology',
    title: '竞品分析报告怎么写',
    publisher: 'RivalRadar',
    author: 'RivalRadar 原创',
    date: '2026-06-07',
    competitors: [],
    kind: 'md',
    type: 'methodology',
    file: '/samples/methodology.md',
    sourceUrls: [
      'https://www.woshipm.com/evaluating/5672064.html',
      'https://www.feishu.cn/template/competitive-product-analysis-report-key-aspects',
      'https://zhuanlan.zhihu.com/p/668621286',
    ],
    note: '8 步框架 + 对齐 RivalRadar 10 条评分标尺,综合 woshipm / 飞书 / 知乎三篇权威方法论。范文库的"怎么读"。',
  },
```

- [ ] **Step 3: 类型/构建门**

Run: `cd frontend && pnpm build`
Expected: 退出码 0。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/samples.ts
git commit -m "feat(samples): Sample 加 type/structure/sourceUrls + 方法论条目"
```

---

## Task 4: `SampleView` 方法论报头分支 + 标尺速览

**Files:**
- Modify: `frontend/src/pages/SampleView.tsx`

- [ ] **Step 1: 派生 methodology 标志**

在 `const isMd = sample?.kind === 'md'` 下方加:

```tsx
  const isMethodology = sample?.type === 'methodology'
```

- [ ] **Step 2: 报头分支(kicker / 副题 / 免责声明随 methodology 切换)**

把 `<header>` 内的固定文案改为条件分支。kicker:

```tsx
          <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
            {isMethodology ? '方法论 · 本库导览' : '竞品分析范文 · 他人公开发表'}
          </div>
```

署名行下方的免责声明 `<p>` 改为:

```tsx
          <p className="mt-3 text-[12px] leading-relaxed text-text-muted">
            {isMethodology
              ? '本文为 RivalRadar 原创方法论,综合公开资料编写,来源见文末。'
              : '供参照「理想输出长什么样」—— 非 RivalRadar 生成,版权归原作者所有。'}
          </p>
```

(方法论无外部 `author`,署名行已有 `sample.publisher · sample.author · sample.date`,methodology 条目里这三字段即 "RivalRadar · RivalRadar 原创 · 2026-06-07",无需改署名行结构。)

- [ ] **Step 3: 阅读栏顶部加「标尺速览」卡(仅 methodology)**

在 `<article className="sample-reading ...">` 内、`<Markdown source={md} />` **之前**插入:

```tsx
                {isMethodology && toc.filter((h) => h.level === 2).length > 0 && (
                  <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                    <div className="mb-2.5 font-mono text-[11px] uppercase tracking-wider text-accent">
                      标尺速览 · {toc.filter((h) => h.level === 2).length} 步
                    </div>
                    <ol className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                      {toc
                        .filter((h) => h.level === 2)
                        .map((h, i) => (
                          <li key={h.id}>
                            <a
                              href={`#${h.id}`}
                              className="flex items-baseline gap-2 text-[13px] text-text-muted hover:text-accent"
                            >
                              <span className="font-mono text-accent">{String(i + 1).padStart(2, '0')}</span>
                              <span>{h.text}</span>
                            </a>
                          </li>
                        ))}
                    </ol>
                  </div>
                )}
```

- [ ] **Step 4: 类型/构建门**

Run: `cd frontend && pnpm build`
Expected: 退出码 0。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SampleView.tsx
git commit -m "feat(samples): SampleView 方法论报头分支 + 标尺速览卡"
```

---

## Task 5: `SamplesPage` 标尺带 + 范例分区 + 结构徽章

**Files:**
- Modify: `frontend/src/pages/SamplesPage.tsx`

- [ ] **Step 1: 拆分方法论与范例**

在 `export function SamplesPage()` 体首行加:

```tsx
  const methodology = SAMPLES.find((s) => s.type === 'methodology')
  const reports = SAMPLES.filter((s) => s.type !== 'methodology')
```

- [ ] **Step 2: 顶部渲染标尺带(放介绍 `<p>` 之后、范例网格之前)**

```tsx
      {methodology && (
        <Link to={`/samples/${methodology.id}`} className="group block">
          <div className="relative overflow-hidden rounded-lg border border-border bg-surface p-5 pl-6">
            <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-accent" />
            <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-accent">
              方法论 · 本库的评判标尺
            </div>
            <h2 className="mt-2 text-[22px] font-semibold leading-snug text-text-primary">
              {methodology.title}
            </h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-text-muted">{methodology.note}</p>
            <div className="mt-3.5 inline-flex items-center gap-1 rounded-md border border-accent bg-accent-soft px-3 py-1 text-[13px] font-medium text-accent transition-shadow group-hover:shadow-panel">
              阅读方法论 →
            </div>
          </div>
        </Link>
      )}
```

- [ ] **Step 3: 范例区加分区标题,网格改用 `reports`**

把现有 `<div className="grid ...">{SAMPLES.map(...)}` 上方加分区标题,并将 `SAMPLES.map` 改为 `reports.map`:

```tsx
      <div className="text-[13px] font-semibold text-text-primary">
        范例报告 · 他人公开发表({reports.length})
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {reports.map((s) => (
          // …(保留现有卡片 JSX 不变)
        ))}
      </div>
```

- [ ] **Step 4: 卡片标题行加结构徽章(在现有 `{s.kind}` 徽章左侧)**

把卡片右上角的 `kind` 徽章 `<span>` 用一个 flex 容器包起来,前面加结构徽章:

```tsx
              <div className="flex shrink-0 items-center gap-1.5">
                {s.structure && (
                  <span className="rounded border border-accent/40 bg-accent-soft px-1.5 py-0.5 text-[10px] font-medium text-accent">
                    {s.structure}
                  </span>
                )}
                <span className="rounded bg-surface-subtle px-1.5 py-0.5 text-[10px] uppercase text-text-muted">
                  {s.kind}
                </span>
              </div>
```

(原本单独的 `<span>{s.kind}</span>` 被上面这段替换。)

- [ ] **Step 5: 类型/构建门**

Run: `cd frontend && pnpm build`
Expected: 退出码 0。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SamplesPage.tsx
git commit -m "feat(samples): SamplesPage 方法论标尺带 + 范例分区 + 结构徽章"
```

---

## Task 6: 方法论端到端 `/browse` 真打验证

**Files:** 无(验证 + 修缺)

- [ ] **Step 1: 起 dev server(无代理,WSL2 Clash 兜底)**

```bash
cd /home/liujunxi/project/RivalRadar/frontend
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1
pnpm dev &
sleep 4
```

- [ ] **Step 2: 真打 `/samples`(标尺带在场)**

```bash
B="$HOME/.claude/skills/gstack/browse/dist/browse"
"$B" goto "http://localhost:5173/samples"
"$B" js "!!document.body.textContent.includes('本库的评判标尺')"   # 期望 true
"$B" console --errors                                              # 期望无 error
"$B" screenshot /tmp/samples.png; # 然后用 Read 工具看图核对标尺带视觉
```
Expected:标尺带可见、青绿左竖条、无 React error。

- [ ] **Step 3: 真打方法论详情页(标尺速览 + 8 段 + chip + 内链 + 引用)**

```bash
"$B" goto "http://localhost:5173/samples/methodology"
"$B" js "!!document.body.textContent.includes('标尺速览')"           # true
"$B" js "document.querySelectorAll('a[href^=\"/samples/ref-\"]').length"  # >0(三联锚定内链)
"$B" js "['woshipm.com/evaluating/5672064','feishu.cn/template','zhihu.com/p/668621286'].every(s=>document.body.innerHTML.includes(s))"  # true(3 来源)
"$B" console --errors                                                # 无 error
"$B" screenshot /tmp/methodology.png; # Read 看图:报头 kicker、标尺速览卡、三联锚定 chip(mono+青绿描边)
```
Expected:全部断言为真;视觉符合 DESIGN.md(无 emoji/渐变/紫,边框承担结构)。

- [ ] **Step 4: 深色模式核对**

```bash
"$B" js "document.documentElement.classList.add('dark')"
"$B" screenshot /tmp/methodology-dark.png; # Read 看图:深色 token 正确跟随
```
Expected:深色下 accent/border/text 正确(token 自动跟随)。

- [ ] **Step 5: 若发现缺陷,回到对应 Task 修复后重跑 Step 2-4;通过后停 dev**

```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 6: Commit(若有修复)**

```bash
git add -A frontend/src
git commit -m "fix(samples): 方法论真打验证修缺" || echo "无修复,跳过"
```

---

## Task 7: 抓取 4 篇新范例正文 + 配图(ref-05..08)

**Files:**
- Create: `frontend/public/samples/ref-05.md` … `ref-08.md` + `ref-05-img/` … `ref-08-img/`

> 每篇按同一流程(下表 4 个目标)。抓取走 `/browse`(已验证可直连国内站)。frontmatter 沿用 ref-01 约定。**抓不全时降级**为"仅元数据 + 原文链接"卡(`note` 标注"正文受限,见原文"),绝不编造正文。

| id | url | publisher | author | date | competitors | structure |
|---|---|---|---|---|---|---|
| ref-05 | https://36kr.com/p/3697005094203910 | 36氪(听潮Ti) | 听潮Ti | 2026-02-25 | [钉钉, 飞书] | 双雄对决 |
| ref-06 | https://blog.csdn.net/s867859765/article/details/147877238 | CSDN | 靓男大师兄 | 2026-03-09 | [飞书, 企业微信, 钉钉] | 全矩阵横评 |
| ref-07 | https://www.21jingji.com/article/20251205/herald/7dd1dd58b4c6135a57b884a3e6758ba3.html | 21经济网 | 道总有理 | 2025-12-05 | [钉钉, 飞书, 企业微信] | 批判视角 |
| ref-08 | https://www.woshipm.com/ai/6361304.html | 人人都是产品经理 | 潘乱(乱翻书) | 2026-03-23 | [钉钉, 飞书, 企业微信] | 战略评论 |

- [ ] **Step 1: 起 browse、无代理(每篇开始前)**

```bash
cd /home/liujunxi/project/RivalRadar
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1,.woshipm.com,.36kr.com,.csdn.net,.21jingji.com
B="$HOME/.claude/skills/gstack/browse/dist/browse"
```

- [ ] **Step 2: 抓正文(以 ref-05 为例,其余同)**

```bash
"$B" goto "https://36kr.com/p/3697005094203910"
"$B" wait --networkidle 2>/dev/null || true
"$B" text   # 复制正文主体(去导航/页脚/推荐),整理为 markdown 段落
```

- [ ] **Step 3: 下载内联配图到 `ref-05-img/`**

```bash
mkdir -p frontend/public/samples/ref-05-img
"$B" scrape images --selector "article" --dir frontend/public/samples/ref-05-img --limit 30
ls -1 frontend/public/samples/ref-05-img   # 确认有图;无图则正文不插图
```

- [ ] **Step 4: 写 `ref-05.md`(frontmatter + 正文 + 本地图引用)**

```markdown
---
source_url: https://36kr.com/p/3697005094203910
title: 抢客户、战表格、押AI:钉钉和飞书继续贴身肉搏
author: 听潮Ti
publisher: 36氪
published_date: 2026-02-25
downloaded_at: 2026-06-07
language: zh-CN
competitors: [钉钉, 飞书]
report_group: B
quality_score: 9
quality_notes: 2026 双雄对决范式。三战线(抢客户/AI表格/押AI)+ ARR/份额硬数据 + 战略推论。
---

# 抢客户、战表格、押AI:钉钉和飞书继续贴身肉搏

> (导语)

![配图](/samples/ref-05-img/00.png)

## (按原文小节组织正文)…
```
其余 ref-06/07/08 重复 Step 2-4,各用上表对应元数据与目录名。

- [ ] **Step 5: 校验 4 篇 md 存在且非空**

Run: `for n in 05 06 07 08; do f=frontend/public/samples/ref-$n.md; test -s "$f" && echo "$f OK $(wc -l <"$f") lines" || echo "$f MISSING"; done`
Expected:四个 OK,行数 > 20。

- [ ] **Step 6: Commit**

```bash
git add frontend/public/samples/ref-05.md frontend/public/samples/ref-06.md frontend/public/samples/ref-07.md frontend/public/samples/ref-08.md frontend/public/samples/ref-05-img frontend/public/samples/ref-06-img frontend/public/samples/ref-07-img frontend/public/samples/ref-08-img
git commit -m "feat(samples): 新增 4 篇范例 ref-05..08(正文+配图)"
```

---

## Task 8: 注册 ref-05..08 到 `lib/samples.ts` + 真打验证

**Files:**
- Modify: `frontend/src/lib/samples.ts`

- [ ] **Step 1: 在 `SAMPLES` 数组(ref-04 之后)追加 4 条**

```ts
  {
    id: 'ref-05',
    title: '抢客户、战表格、押AI:钉钉和飞书继续贴身肉搏',
    publisher: '36氪(听潮Ti)',
    author: '听潮Ti',
    date: '2026-02-25',
    competitors: ['钉钉', '飞书'],
    kind: 'md',
    structure: '双雄对决',
    file: '/samples/ref-05.md',
    sourceUrl: 'https://36kr.com/p/3697005094203910',
    note: '2026 双雄对决:三战线(抢客户/AI表格/押AI)+ ARR/份额硬数据 + 战略推论。',
  },
  {
    id: 'ref-06',
    title: '飞书、企业微信、钉钉三款协同办公软件深度对比与行业洞察',
    publisher: 'CSDN',
    author: '靓男大师兄',
    date: '2026-03-09',
    competitors: ['飞书', '企业微信', '钉钉'],
    kind: 'md',
    structure: '全矩阵横评',
    file: '/samples/ref-06.md',
    sourceUrl: 'https://blog.csdn.net/s867859765/article/details/147877238',
    note: '2026 全矩阵横评:多张对比矩阵(市占/商业模式/痛点)+ 市场规模 + 多源引证。',
  },
  {
    id: 'ref-07',
    title: '协同办公概念"泛滥",中小企业和打工人真的需要吗?',
    publisher: '21经济网',
    author: '道总有理',
    date: '2025-12-05',
    competitors: ['钉钉', '飞书', '企业微信'],
    kind: 'md',
    structure: '批判视角',
    file: '/samples/ref-07.md',
    sourceUrl: 'https://www.21jingji.com/article/20251205/herald/7dd1dd58b4c6135a57b884a3e6758ba3.html',
    note: '2025 末批判视角:质疑真实需求 + QuestMobile 硬数据(满意度/付费率)+ 转向推论。',
  },
  {
    id: 'ref-08',
    title: '这次,钉钉领先半目',
    publisher: '人人都是产品经理',
    author: '潘乱(乱翻书)',
    date: '2026-03-23',
    competitors: ['钉钉', '飞书', '企业微信'],
    kind: 'md',
    structure: '战略评论',
    file: '/samples/ref-08.md',
    sourceUrl: 'https://www.woshipm.com/ai/6361304.html',
    note: '2026 战略评论:钉钉新平台「悟空」+ 从「人」到「AI」作为工作主体的范式判断。',
  },
```

- [ ] **Step 2: 类型/构建门**

Run: `cd frontend && pnpm build`
Expected: 退出码 0。

- [ ] **Step 3: 真打:范例区 8 卡 + 每篇可阅读**

```bash
cd /home/liujunxi/project/RivalRadar/frontend
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy; export NO_PROXY=localhost,127.0.0.1
pnpm dev & sleep 4
B="$HOME/.claude/skills/gstack/browse/dist/browse"
"$B" goto "http://localhost:5173/samples"
"$B" js "document.body.textContent.match(/范例报告 · 他人公开发表（8）|范例报告 · 他人公开发表\\(8\\)/)?[0]||'COUNT?'"  # 期望含 8
for n in 05 06 07 08; do "$B" goto "http://localhost:5173/samples/ref-$n"; "$B" js "document.querySelector('.sample-reading')?.textContent.length>200"; "$B" console --errors; done
kill %1 2>/dev/null || true
```
Expected:范例区显示 8;ref-05..08 正文渲染(>200 字)、配图加载、无 error。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/samples.ts
git commit -m "feat(samples): 注册 ref-05..08 到范文注册表"
```

---

## Task 9: 全量回归 + 收尾

**Files:** 无

- [ ] **Step 1: 后端回归 sanity(无后端改动,应保持绿)**

```bash
cd /home/liujunxi/project/RivalRadar
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy; export NO_PROXY=localhost,127.0.0.1
.venv/bin/python -m pytest -q
```
Expected:350 passed(与 main 一致,无新增失败)。

- [ ] **Step 2: 前端最终构建门**

```bash
cd frontend && pnpm build
```
Expected:退出码 0。

- [ ] **Step 3: 现有范例回归(ref-01..04 不受影响)**

```bash
pnpm dev & sleep 4
B="$HOME/.claude/skills/gstack/browse/dist/browse"
for id in ref-01 ref-02 ref-03; do "$B" goto "http://localhost:5173/samples/$id"; "$B" js "document.querySelector('.sample-reading')?.textContent.length>200"; done
"$B" goto "http://localhost:5173/samples/ref-04"; "$B" js "!!document.querySelector('iframe')"   # PDF iframe 仍在
kill %1 2>/dev/null || true
```
Expected:ref-01..03 正文渲染、ref-04 iframe 在场。

- [ ] **Step 4: 终态 commit(若 Step 1-3 触发任何修复)**

```bash
git add -A
git commit -m "chore(samples): 回归修缺" || echo "无修复"
```

---

## Self-Review(已对照 spec)

- **Spec 覆盖:** A 方法论 → Task 2(内容)+ Task 1(渲染)+ Task 4(报头/速览);B 前端 → Task 1/3/4/5;C 范例 → Task 7/8。Rubric 连接 → Task 2 Step 4 + 三联锚定 Step 3。3 个指定 URL → Task 2 Step 3/5 + 校验 Task 2 Step 6 / Task 6 Step 3。✓
- **占位扫描:** 无 TBD;内容任务(2/7)给了精确结构契约 + 校验命令,非"自由发挥"。✓
- **类型一致:** `type`/`structure`/`sourceUrls` 在 Task 3 定义,Task 4/5/8 一致引用;`isMethodology`/`methodology`/`reports` 命名前后一致;`headingId`/`parseHeadings` 复用现有。✓
- **测试现实:** 前端无单测 runner,验证统一为 `pnpm build` + `/browse`,已在每任务落实;后端无改动仅回归。✓
