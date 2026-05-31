/**
 * SampleView(/samples/:id)— 全屏阅读一份**他人**竞品分析范文。
 *
 * 顶部出处栏明确标注「非 RivalRadar 生成 + 来源/作者/日期/原文链接」。
 * 范文是 public/samples 静态资源,运行时 fetch + 去除 YAML frontmatter + Markdown 渲染。
 */
import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ExternalLink, Loader2 } from 'lucide-react'
import { getSample } from '@/lib/samples'
import { Markdown } from '@/components/report/Markdown'

function stripFrontmatter(md: string): string {
  return md.replace(/^---\n[\s\S]*?\n---\n?/, '')
}

export function SampleView() {
  const { id } = useParams<{ id: string }>()
  const sample = id ? getSample(id) : undefined
  const [md, setMd] = React.useState<string>('')
  const [state, setState] = React.useState<'loading' | 'ready' | 'error'>('loading')

  React.useEffect(() => {
    if (!sample || sample.kind !== 'md') {
      setState('error')
      return
    }
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
  }, [sample])

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
      <div className="report-toolbar sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2.5 print:hidden">
        <Link to="/samples" className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-accent">
          <ArrowLeft className="h-4 w-4" /> 返回范文库
        </Link>
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

      <div className="report-page mx-auto max-w-[820px] px-6 py-8">
        <div className="mb-5 rounded-lg border border-dashed border-border bg-surface-subtle p-3 text-[12px] leading-relaxed text-text-muted">
          <div>
            本文为<span className="text-text-primary">他人公开发表</span>的竞品分析范文,供参照「理想输出长什么样」——
            非 RivalRadar 生成,版权归原作者所有。
          </div>
          <div className="mt-1">
            出处:<span className="text-text-primary">{sample.publisher}</span> · {sample.author} · {sample.date}
            {sample.sourceUrl && (
              <>
                {' · '}
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
        </div>

        {state === 'loading' ? (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> 范文加载中…
          </div>
        ) : state === 'error' ? (
          <div className="text-sm text-error">范文加载失败。</div>
        ) : (
          <article>
            <Markdown source={md} />
          </article>
        )}
      </div>
    </div>
  )
}
