/**
 * SampleView(/samples/:id)— 全屏阅读一份**他人**竞品分析范文。
 *
 * 顶部出处报头明确标注「非 RivalRadar 生成 + 来源/作者/日期/原文链接」。
 * - md 范文:public/samples 静态资源,运行时 fetch + 去 YAML frontmatter + 杂志式精排渲染。
 *   左侧粘性目录(从 h2/h3 自动生成,滚动高亮当前章节)填充留白 + 提供研报式导航。
 * - pdf 范文(如艾瑞研究报告):浏览器原生 <iframe> 内联阅览 + 下载兜底(唯一带图表的范文)。
 */
import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Download, ExternalLink, Loader2 } from 'lucide-react'
import { getSample } from '@/lib/samples'
import { Markdown } from '@/components/report/Markdown'
import { parseHeadings } from '@/components/report/markdownHeadings'

function stripFrontmatter(md: string): string {
  return md.replace(/^---\n[\s\S]*?\n---\n?/, '')
}

export function SampleView() {
  const { id } = useParams<{ id: string }>()
  const sample = id ? getSample(id) : undefined
  const [md, setMd] = React.useState<string>('')
  const [state, setState] = React.useState<'loading' | 'ready' | 'error'>('loading')
  const [activeId, setActiveId] = React.useState<string>('')

  const isMd = sample?.kind === 'md'
  const isMethodology = sample?.type === 'methodology'

  // 目录:只取 h2/h3(跳过 h1 标题与更深层级,保持精简可扫读)
  const toc = React.useMemo(
    () => parseHeadings(md).filter((h) => h.level === 2 || h.level === 3),
    [md],
  )

  React.useEffect(() => {
    if (!sample || !isMd) return
    setState('loading')
    fetch(sample.file)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status))
        return r.text()
      })
      .then((t) => {
        setMd(stripFrontmatter(t))
        setState('ready')
      })
      .catch(() => setState('error'))
  }, [sample, isMd])

  // 滚动高亮:观察各章节标题,进入视口上沿即设为当前
  React.useEffect(() => {
    if (state !== 'ready' || toc.length === 0) return
    const obs = new IntersectionObserver(
      (entries) => {
        const hit = entries.find((e) => e.isIntersecting)
        if (hit) setActiveId(hit.target.id)
      },
      { rootMargin: '0px 0px -75% 0px' },
    )
    toc.forEach((h) => {
      const el = document.getElementById(h.id)
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [state, toc])

  if (!sample) {
    return (
      <div className="p-6 text-sm text-text-muted">
        范文不存在。{' '}
        <Link to="/samples" className="text-accent hover:underline">
          返回范文库
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg text-text-primary">
      {/* 工具栏 */}
      <div className="report-toolbar sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2.5 print:hidden">
        <Link to="/samples" className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-accent">
          <ArrowLeft className="h-4 w-4" /> 返回范文库
        </Link>
        <div className="flex items-center gap-2">
          {!isMd && (
            <a
              href={sample.file}
              download
              className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-text-primary hover:bg-surface-subtle"
            >
              <Download className="h-3.5 w-3.5" /> 下载 PDF
            </a>
          )}
          {sample.sourceUrl && (
            <a
              href={sample.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-text-primary hover:bg-surface-subtle"
            >
              <ExternalLink className="h-3.5 w-3.5" /> 查看原文
            </a>
          )}
        </div>
      </div>

      <div className="mx-auto max-w-[1180px] px-6 py-8">
        {/* 杂志报头(全宽):导语标 + 出处署名行 + 青绿细分隔线 */}
        <header className="mb-7">
          <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
            {isMethodology ? '方法论 · 本库导览' : '竞品分析范文 · 他人公开发表'}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-text-muted">
            <span className="font-medium text-text-primary">{sample.publisher}</span>
            <span aria-hidden>·</span>
            <span>{sample.author}</span>
            <span aria-hidden>·</span>
            <span>{sample.date}</span>
            {sample.sourceUrl && (
              <>
                <span aria-hidden>·</span>
                <a
                  href={sample.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                >
                  原文
                </a>
              </>
            )}
          </div>
          <div className="mt-3 h-px w-full bg-gradient-to-r from-accent/50 to-transparent" />
          <p className="mt-3 text-[12px] leading-relaxed text-text-muted">
            {isMethodology
              ? '本文为 RivalRadar 原创方法论,综合公开资料编写,来源见文末。'
              : '供参照「理想输出长什么样」—— 非 RivalRadar 生成,版权归原作者所有。'}
          </p>
        </header>

        {/* 正文:md 走「目录栏 + 阅读栏」网格;pdf 全宽内联 */}
        {isMd ? (
          state === 'loading' ? (
            <div className="flex items-center gap-2 text-sm text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin" /> 范文加载中…
            </div>
          ) : state === 'error' ? (
            <div className="text-sm text-error">范文加载失败。</div>
          ) : (
            <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-10">
              {/* 左侧粘性目录(窄屏隐藏) */}
              {toc.length > 0 && (
                <nav className="hidden lg:block print:hidden">
                  <div className="sticky top-16">
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                      目录
                    </div>
                    <ul className="space-y-0.5 border-l border-border">
                      {toc.map((h) => {
                        const active = h.id === activeId
                        return (
                          <li key={h.id}>
                            <a
                              href={`#${h.id}`}
                              className={[
                                'block border-l-2 py-1 text-[12px] leading-snug transition-colors',
                                h.level === 3 ? 'pl-5' : 'pl-3',
                                active
                                  ? 'border-accent font-medium text-accent'
                                  : 'border-transparent text-text-muted hover:text-text-primary',
                              ].join(' ')}
                            >
                              {h.text}
                            </a>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                </nav>
              )}

              {/* 阅读栏 */}
              <article className="sample-reading min-w-0 max-w-[760px]">
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
                <Markdown source={md} />
              </article>
            </div>
          )
        ) : (
          <div>
            <iframe
              src={sample.file}
              title={sample.title}
              className="h-[calc(100vh-220px)] min-h-[560px] w-full rounded-lg border border-border bg-surface"
            />
            <p className="mt-2 text-[12px] text-text-muted">
              无法内联显示?
              <a href={sample.file} download className="ml-1 text-accent hover:underline">
                下载 PDF
              </a>
              （{sample.publisher} · 唯一带图表的范文,38 页赛道全景）
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
