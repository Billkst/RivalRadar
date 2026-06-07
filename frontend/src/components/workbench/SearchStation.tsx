/**
 * SearchStation — 检索台(2e §6,Plan C Task 14)。
 *
 * 逐条查询词(最新在前,来自 runStore.queries)+ 命中数(queryHits:query_text→hit_count)。
 * 最新一条字符级打字(14ms/char),旧条全显;prefers-reduced-motion 跳过打字。
 * selector 返 raw,空态用 module-level 稳定常量。
 */
import { useEffect, useState } from 'react'
import { useRunStore } from '@/stores/runStore'
import type { SSEQueryData } from '@/types/api'

const EMPTY_Q: SSEQueryData[] = []
const REDUCE =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function useTypewriter(text: string, on: boolean, ms = 14): string {
  const [n, setN] = useState(on ? 0 : text.length)
  useEffect(() => {
    if (!on) {
      setN(text.length)
      return
    }
    setN(0)
    let i = 0
    const t = setInterval(() => {
      i++
      setN(i)
      if (i >= text.length) clearInterval(t)
    }, ms)
    return () => clearInterval(t)
  }, [text, on, ms])
  return text.slice(0, n)
}

export function SearchStation() {
  const queries = useRunStore((s) => s.queries)
  const hits = useRunStore((s) => s.queryHits)
  const list = queries.length ? queries : EMPTY_Q
  if (!list.length) return null
  return (
    <div className="mt-[18px]">
      <div className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mb-2 flex items-center gap-[7px] before:content-[''] before:w-[14px] before:h-px before:bg-accent">
        检索台
      </div>
      <div className="flex flex-col gap-1.5">
        {list.map((q, i) => (
          <QueryLine
            key={`${q.round}-${q.query_text}-${i}`}
            q={q}
            hit={hits[q.query_text]}
            latest={i === 0}
          />
        ))}
      </div>
    </div>
  )
}

function QueryLine({
  q,
  hit,
  latest,
}: {
  q: SSEQueryData
  hit: number | undefined
  latest: boolean
}) {
  const shown = useTypewriter(q.query_text, latest && !REDUCE)
  const hasHit = hit !== undefined
  return (
    <div className="flex items-center gap-2 font-mono text-[11px] bg-surface border border-border rounded-md px-[9px] py-[6px] text-text-primary">
      <span className="text-accent flex-none">▸</span>
      <span className="flex-1 overflow-hidden whitespace-nowrap min-w-0">{shown}</span>
      {hasHit && (
        <span
          className={`flex-none text-[9.5px] whitespace-nowrap ${hit! > 0 ? 'text-v-sup' : 'text-text-faint'}`}
        >
          {hit! > 0 ? `+${hit} 源` : '无新增'}
        </span>
      )}
    </div>
  )
}
