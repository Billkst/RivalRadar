/**
 * ReportView — 全屏「完整报告」文档视图(#4 / Q9 范文)。
 *
 * 全屏(在 App.tsx 挂到 Layout 外,免应用外壳挤占,得「打开一份真文档」体感)。
 *   - 顶部工具栏(打印时隐藏):返回驾驶舱 / 下载 Markdown / 导出 PDF(浏览器打印)。
 *   - 正文:fetchReport 取**质检策展后**的 markdown,Markdown 组件精排渲染。
 *   - 导出 PDF 走 window.print() + globals.css @media print(零依赖,中文字体/分页最稳)。
 *
 * 范文入口复用同视图:首页指向成品种子 run 的 /run/:id/report。
 */
import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Download, Loader2, Printer } from 'lucide-react'
import { ApiError, fetchReport } from '@/lib/api'
import { Markdown } from '@/components/report/Markdown'

type LoadState = 'loading' | 'ready' | 'absent' | 'error'

export function ReportView() {
  const { run_id } = useParams<{ run_id: string }>()
  const [md, setMd] = React.useState<string>('')
  const [state, setState] = React.useState<LoadState>('loading')

  React.useEffect(() => {
    if (!run_id) return
    setState('loading')
    fetchReport(run_id)
      .then((r) => {
        setMd(r.markdown)
        setState('ready')
      })
      .catch((e) => setState(e instanceof ApiError && e.status === 404 ? 'absent' : 'error'))
  }, [run_id])

  const downloadMd = () => {
    if (!md) return
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `rivalradar-report-${run_id}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-bg text-text-primary">
      <div className="report-toolbar sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2.5 print:hidden">
        <Link
          to={run_id ? `/run/${run_id}` : '/runs'}
          className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-accent"
        >
          <ArrowLeft className="h-4 w-4" /> 返回驾驶舱
        </Link>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={downloadMd}
            disabled={state !== 'ready'}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-text-primary hover:bg-surface-subtle disabled:opacity-40"
          >
            <Download className="h-3.5 w-3.5" /> 下载 Markdown
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            disabled={state !== 'ready'}
            className="inline-flex items-center gap-1 rounded-md border border-accent bg-accent-soft px-2.5 py-1 text-xs text-accent hover:bg-accent-soft/70 disabled:opacity-40"
            title="弹出浏览器打印对话框,目标选「另存为 PDF」"
          >
            <Printer className="h-3.5 w-3.5" /> 导出 PDF
          </button>
        </div>
      </div>

      <div className="report-page mx-auto max-w-[820px] px-6 py-8">
        {state === 'loading' ? (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> 报告加载中…
          </div>
        ) : state === 'absent' ? (
          <div className="text-sm text-text-muted">
            该调研尚未生成报告(可能未跑完或证据不足)。
          </div>
        ) : state === 'error' ? (
          <div className="text-sm text-error">报告加载失败(网络或服务异常)。</div>
        ) : (
          <article>
            <Markdown source={md} />
          </article>
        )}
      </div>
    </div>
  )
}
