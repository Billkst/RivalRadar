/**
 * Markdown — 针对 writer `render_body` 产出的**规整 markdown** 的轻量零依赖渲染器。
 *
 * 后端报告是 Python 模板生成的,构造可预测:`# / ## / ###` 标题、`- ` 列表(2 空格缩进
 * 表层级)、`> ` 引用块、行内 `[ev_xxx]` 证据收据,无表格 / 无 **粗体**。故用按行解析即可,
 * 不引 react-markdown(npm 安装受 Clash 影响,且通用渲染器样式不如此处可控)。
 *
 * 行内 `[ev_xxx]` / `[ev_a, ev_b]` 渲成弱化「收据」徽章,呼应「点结论看收据」的信任范式。
 */
import * as React from 'react'
import { Link } from 'react-router-dom'
import { useEvidenceStore } from '@/stores/evidenceStore'
import { HEADING_RE, headingId } from './markdownHeadings'

const CITE_SPLIT = /(\[ev_[^\]]*\])/g
const ANCHOR_PREFIX = '锚定: '

/** 全篇 id→序号映射(预扫描建,Citation 经 Context 读)→ [ev_长hash] 渲成脚注式 [1][2]。 */
const CiteContext = React.createContext<Map<string, number> | null>(null)

/**
 * Citation — 报告内 [ev_id] 行内引用 → 可点溯源徽章(#7)。
 *
 * ReportView 全屏独立(不在 cockpit 内,无全局证据 Drawer / 未 seed 证据)→ 本组件:
 *   - 显示脚注式序号(CiteContext 全篇统一编号,同一证据复用同号),取代丑陋长 hash。
 *   - hover/focus → lazy GET /evidence/:id 出来源预览(标题 + 域名 + 正文摘录)。
 *   - 点击 → 新标签打开原始 source_url(真·溯源)。**无 provider / confidence**(反幻觉)。
 */
function Citation({ id }: { id: string }) {
  const numbers = React.useContext(CiteContext)
  const index = numbers?.get(id) ?? 0
  const getEvidence = useEvidenceStore((s) => s.getEvidence)
  const ev = useEvidenceStore((s) => s.cache.get(id) ?? null)
  const [loading, setLoading] = React.useState(false)

  const ensure = () => {
    if (ev || loading) return
    setLoading(true)
    getEvidence(id)
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  const openSource = (e: React.MouseEvent) => {
    e.preventDefault()
    const go = (u?: string) => u && window.open(u, '_blank', 'noopener,noreferrer')
    if (ev?.source_url) go(ev.source_url)
    else getEvidence(id).then((x) => go(x.source_url)).catch(() => {})
  }
  const host = (() => {
    try {
      return ev?.source_url ? new URL(ev.source_url).hostname.replace(/^www\./, '') : ''
    } catch {
      return ''
    }
  })()

  return (
    <span className="group/cite relative mx-0.5 inline-block align-super leading-none">
      <button
        type="button"
        onClick={openSource}
        onMouseEnter={ensure}
        onFocus={ensure}
        className="rounded border border-accent/40 px-1 text-[10px] leading-tight text-accent hover:bg-accent-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        aria-label={`证据 ${index || ''} 来源`}
        title="点击打开原始来源"
      >
        {index || '·'}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-40 mt-1 hidden w-72 rounded-lg border border-border bg-surface p-3 text-left shadow-panel group-hover/cite:block group-focus-within/cite:block"
      >
        {ev ? (
          <>
            <span className="block truncate text-[12px] font-medium text-text-primary">
              {ev.source_title || '来源'}
            </span>
            {host ? (
              <span className="mt-0.5 block font-mono text-[10px] text-text-muted">{host} · 点击打开 ↗</span>
            ) : null}
            <span className="mt-1.5 block max-h-24 overflow-hidden text-[11px] leading-snug text-text-muted">
              {(ev.content || '').slice(0, 160)}
            </span>
          </>
        ) : (
          <span className="block text-[11px] text-text-muted">{loading ? '证据加载中…' : '悬停加载来源预览'}</span>
        )}
      </span>
    </span>
  )
}

// 图片 src 白名单(对抗审查 F4 / Codex P2):**只放行相对路径与 data:image**。范文配图全是
// 仓库本地相对路径(如 ref-01-img/x.png);生成报告本不产图。一律拒绝 http(s)/file: 等带网络
// 语义的 scheme —— 否则 /report 渲染 LLM 自由文本时,prompt-injection 出的独立成行外链/内网图
// (![x](http://内网/...) / 信标 gif)会被浏览器在用户会话里自动 GET(referrer 泄漏 / SSRF 向量)。
function isSafeImgSrc(src: string): boolean {
  const s = src.trim()
  if (!/^[a-z][a-z0-9+.-]*:/i.test(s)) return true // 无 scheme = 仓库相对路径,放行
  return /^data:image\//i.test(s) // 仅内联图(无网络请求);http(s)/file: 等一律不渲染 <img>
}

// markdown 表格(writer.render_comparison 产「| 维度 | 竞品A | … |」对比表):header 行 +
// 分隔行(|---|---|)+ body 行。Codex 评审 P2:此前 Markdown 无表格分支 → /report 的对比表
// (核心交付物)散成一行行独立段落。splitTableRow 去掉首尾 | 再按 | 切;isTableSep 认分隔行。
const splitTableRow = (line: string): string[] =>
  line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
const isTableSep = (line: string): boolean => {
  const s = line.trim()
  return s.includes('-') && /^[\s|:-]+$/.test(s)
}

// 行内 [ev_xxx] / [ev_a, ev_b] → 每个 id 一个可点溯源 Citation(脚注式序号 + hover 预览 +
// 点击开来源)。范文(samples)里不出现 [ev_],透传为文本。
function renderCitations(text: string, keyPrefix: string): React.ReactNode[] {
  return text.split(CITE_SPLIT).map((part, i) => {
    if (!part.startsWith('[ev_')) {
      return <React.Fragment key={`${keyPrefix}t${i}`}>{part}</React.Fragment>
    }
    const ids = part
      .slice(1, -1)
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    return (
      <React.Fragment key={`${keyPrefix}c${i}`}>
        {ids.map((id, j) => (
          <Citation key={`${id}-${j}`} id={id} />
        ))}
      </React.Fragment>
    )
  })
}

// 行内 markdown 链接 [label](href):站内 /samples/:id 走 react-router(SPA 不刷新),
// http(s) 外链走新标签页 + noopener;其余 scheme(javascript: 等)退为字面文本防注入。
// [ev_xxx] 无 `(`,不会被本正则吃到,仍由 renderCitations 处理。
// href 允许一层嵌套括号(如 wikipedia ..._(programming_language)),避免静默截断。
const LINK_RE = /\[([^\]]+)\]\(([^()]+(?:\([^()]*\)[^()]*)*)\)/g
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

// 行内渲染:**粗体**(范文大量使用)+ [ev_] 收据。先按 **bold** 切,段内再处理收据。
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

export function Markdown({ source }: { source: string }) {
  // 预扫描全篇 [ev_id],按出现顺序给每个唯一 id 编号(同一证据全篇复用同号)→ 脚注式 [1][2]。
  const citeNumbers = React.useMemo(() => {
    const map = new Map<string, number>()
    let n = 0
    for (const m of source.matchAll(/\[ev_[^\]]*\]/g)) {
      for (const raw of m[0].slice(1, -1).split(',')) {
        const id = raw.trim()
        if (id && !map.has(id)) map.set(id, ++n)
      }
    }
    return map
  }, [source])
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const blocks: React.ReactNode[] = []
  let items: { level: number; text: string; marker: string }[] = []
  let headingSeq = 0

  const flushList = () => {
    if (items.length === 0) return
    const list = items
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="my-2 space-y-1">
        {list.map((b, i) => (
          <li
            key={i}
            className="flex gap-2 text-[14px] leading-relaxed text-text-primary"
            style={{ paddingLeft: b.level * 18 }}
          >
            <span aria-hidden className="min-w-[1.1em] select-none text-text-muted">
              {b.marker}
            </span>
            <span className="flex-1">{renderInline(b.text)}</span>
          </li>
        ))}
      </ul>,
    )
    items = []
  }

  for (let li = 0; li < lines.length; li++) {
    const line = lines[li].trimEnd()
    const bulletMatch = /^(\s*)[-*+]\s+(.*)$/.exec(line)
    if (bulletMatch) {
      const level = Math.floor(bulletMatch[1].length / 2)
      items.push({ level, text: bulletMatch[2], marker: level === 0 ? '•' : '◦' })
      continue
    }
    const orderedMatch = /^(\s*)(\d+)\.\s+(.*)$/.exec(line)
    if (orderedMatch) {
      const level = Math.floor(orderedMatch[1].length / 2)
      items.push({ level, text: orderedMatch[3], marker: `${orderedMatch[2]}.` })
      continue
    }
    flushList()
    if (line.trim() === '') continue
    // markdown 表格:当前行以 | 起 + 下一行是分隔行(|---|---|)→ 消费整块渲成 <table>。
    if (line.trim().startsWith('|') && li + 1 < lines.length && isTableSep(lines[li + 1])) {
      const header = splitTableRow(line)
      li += 1 // 跳过分隔行
      const body: string[][] = []
      while (li + 1 < lines.length && lines[li + 1].trim().startsWith('|')) {
        li += 1
        body.push(splitTableRow(lines[li]))
      }
      blocks.push(
        <div key={blocks.length} className="my-4 overflow-x-auto">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr>
                {header.map((c, i) => (
                  <th
                    key={i}
                    className="border border-border bg-surface-subtle px-3 py-1.5 text-left font-semibold text-text-primary"
                  >
                    {renderInline(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, r) => (
                <tr key={r}>
                  {row.map((c, i) => (
                    <td
                      key={i}
                      className="border border-border px-3 py-1.5 align-top text-text-primary"
                    >
                      {renderInline(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }
    const imgMatch = /^!\[([^\]]*)\]\(([^)]+)\)$/.exec(line)
    if (imgMatch && isSafeImgSrc(imgMatch[2])) {
      const [, alt, src] = imgMatch
      blocks.push(
        <figure key={blocks.length} className="my-4">
          <img
            src={src}
            alt={alt}
            loading="lazy"
            className="mx-auto max-w-full rounded-md border border-border"
          />
        </figure>,
      )
      continue
    }
    // 水平分隔线:--- / *** / ___(独立成行,≥3 个)。修复正文 `---` 渲成字面文本的 bug。
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
      blocks.push(<hr key={blocks.length} className="my-6 border-0 border-t border-border" />)
      continue
    }
    const headingMatch = HEADING_RE.exec(line)
    if (headingMatch) {
      const level = headingMatch[1].length
      const text = headingMatch[2]
      const id = headingId(headingSeq++)
      if (level === 1) {
        blocks.push(
          <h1 id={id} key={blocks.length} className="mb-4 text-[26px] font-bold text-text-primary">
            {renderInline(text)}
          </h1>,
        )
      } else if (level === 2) {
        blocks.push(
          <h2
            id={id}
            key={blocks.length}
            className="mb-2 mt-7 scroll-mt-20 border-b border-border pb-1 text-[20px] font-semibold text-text-primary"
          >
            {renderInline(text)}
          </h2>,
        )
      } else if (level === 3) {
        blocks.push(
          <h3
            id={id}
            key={blocks.length}
            className="mb-1.5 mt-5 scroll-mt-20 text-[16px] font-semibold text-text-primary"
          >
            {renderInline(text)}
          </h3>,
        )
      } else if (level === 4) {
        blocks.push(
          <h4
            id={id}
            key={blocks.length}
            className="mb-1 mt-4 scroll-mt-20 text-[15px] font-semibold text-text-primary"
          >
            {renderInline(text)}
          </h4>,
        )
      } else {
        blocks.push(
          <h5
            id={id}
            key={blocks.length}
            className="mb-1 mt-3 scroll-mt-20 text-[12px] font-semibold uppercase tracking-wide text-text-muted"
          >
            {renderInline(text)}
          </h5>,
        )
      }
      continue
    }
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
    if (line.startsWith('> ')) {
      blocks.push(
        <blockquote
          key={blocks.length}
          className="my-3 border-l-2 border-accent/40 pl-3 text-[13px] italic text-text-muted"
        >
          {renderInline(line.slice(2))}
        </blockquote>,
      )
    } else {
      blocks.push(
        <p key={blocks.length} className="my-2 text-[14px] leading-relaxed text-text-primary">
          {renderInline(line)}
        </p>,
      )
    }
  }
  flushList()

  return (
    <CiteContext.Provider value={citeNumbers}>
      <div>{blocks}</div>
    </CiteContext.Provider>
  )
}
