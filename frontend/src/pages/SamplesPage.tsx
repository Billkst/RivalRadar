/**
 * SamplesPage(/samples)— 范文库:网上下载的**他人专业竞品分析报告**,供参照。
 *
 * 明确标注「非 RivalRadar 生成 + 出处」。md 范文跳 /samples/:id 全屏阅读;PDF 直接下载。
 */
import { Link } from 'react-router-dom'
import { ArrowLeft, BookOpen, Download, ExternalLink } from 'lucide-react'
import { SAMPLES } from '@/lib/samples'

export function SamplesPage() {
  return (
    <div className="space-y-5">
      <div>
        <Link to="/runs" className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-accent">
          <ArrowLeft className="h-4 w-4" /> 返回首页
        </Link>
        <h1 className="mt-2 flex items-center gap-2 text-lg font-semibold text-text-primary">
          <BookOpen className="h-5 w-5 text-accent" /> 竞品分析范文库
        </h1>
        <p className="mt-1 text-[13px] leading-relaxed text-text-muted">
          以下是公开渠道下载的<span className="text-text-primary">他人</span>专业竞品分析报告,供参照「理想输出长什么样」——
          <span className="text-text-primary">非 RivalRadar 生成,均标明出处</span>。版权归原作者 / 媒体所有。
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {SAMPLES.map((s) => (
          <div key={s.id} className="flex flex-col rounded-lg border border-border bg-surface p-4">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-[15px] font-semibold leading-snug text-text-primary">{s.title}</h2>
              <span className="shrink-0 rounded bg-surface-subtle px-1.5 py-0.5 text-[10px] uppercase text-text-muted">
                {s.kind}
              </span>
            </div>
            <div className="mt-1 text-[12px] text-text-muted">
              出处:<span className="text-text-primary">{s.publisher}</span> · {s.author} · {s.date}
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {s.competitors.map((c) => (
                <span key={c} className="rounded border border-border px-1.5 py-0.5 text-[11px] text-text-muted">
                  {c}
                </span>
              ))}
            </div>
            <p className="mt-2 flex-1 text-[12px] leading-relaxed text-text-muted">{s.note}</p>
            <div className="mt-3 flex items-center gap-3 text-xs">
              <Link
                to={`/samples/${s.id}`}
                className="inline-flex items-center gap-1 rounded-md border border-accent bg-accent-soft px-2.5 py-1 font-medium text-accent hover:shadow-panel"
              >
                <BookOpen className="h-3.5 w-3.5" /> {s.kind === 'md' ? '阅读范文' : '在线阅览'}
              </Link>
              {s.kind === 'pdf' && (
                <a
                  href={s.file}
                  download
                  className="inline-flex items-center gap-1 text-text-muted hover:text-accent"
                >
                  <Download className="h-3.5 w-3.5" /> 下载 PDF
                </a>
              )}
              {s.sourceUrl && (
                <a
                  href={s.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-text-muted hover:text-accent"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> 原文链接
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
