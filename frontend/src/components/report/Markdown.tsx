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

const CITE_SPLIT = /(\[ev_[^\]]*\])/g

// 行内 [ev_xxx] → 弱化收据徽章(RivalRadar 报告专有;范文里不出现,透传为文本)。
function renderCitations(text: string, keyPrefix: string): React.ReactNode[] {
  return text.split(CITE_SPLIT).map((part, i) =>
    part.startsWith('[ev_') ? (
      <span
        key={`${keyPrefix}c${i}`}
        className="mx-0.5 rounded bg-surface-subtle px-1 align-baseline text-[10px] text-text-muted"
        title="证据收据"
      >
        {part}
      </span>
    ) : (
      <React.Fragment key={`${keyPrefix}t${i}`}>{part}</React.Fragment>
    ),
  )
}

// 行内渲染:**粗体**(范文大量使用)+ [ev_] 收据。先按 **bold** 切,段内再处理收据。
function renderInline(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = []
  text.split(/(\*\*[^*]+\*\*)/g).forEach((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      out.push(
        <strong key={`b${i}`} className="font-semibold text-text-primary">
          {renderCitations(part.slice(2, -2), `b${i}`)}
        </strong>,
      )
    } else {
      out.push(...renderCitations(part, `s${i}`))
    }
  })
  return out
}

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const blocks: React.ReactNode[] = []
  let items: { level: number; text: string; marker: string }[] = []

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

  for (const raw of lines) {
    const line = raw.trimEnd()
    const bulletMatch = /^(\s*)-\s+(.*)$/.exec(line)
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
    if (line.startsWith('### ')) {
      blocks.push(
        <h3 key={blocks.length} className="mb-1.5 mt-5 text-[16px] font-semibold text-text-primary">
          {renderInline(line.slice(4))}
        </h3>,
      )
    } else if (line.startsWith('## ')) {
      blocks.push(
        <h2
          key={blocks.length}
          className="mb-2 mt-7 border-b border-border pb-1 text-[20px] font-semibold text-text-primary"
        >
          {renderInline(line.slice(3))}
        </h2>,
      )
    } else if (line.startsWith('# ')) {
      blocks.push(
        <h1 key={blocks.length} className="mb-4 text-[26px] font-bold text-text-primary">
          {renderInline(line.slice(2))}
        </h1>,
      )
    } else if (line.startsWith('> ')) {
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

  return <div>{blocks}</div>
}
