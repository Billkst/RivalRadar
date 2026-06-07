/**
 * ReportStation — 报告台 typing(C-D7,Plan C Task 18)。
 *
 * 读 typingStore.byAgent['writer'] 实时显;首块前(后端 write_node 先发 progress
 * step="drafting",Spike H TTFB ~38s)显「起草中…」占位。判定:writer node running
 * (NodeName 'write')且 typing 空 → 占位;有 typing → 显文本 + 光标。
 * typing 是 best-effort;回落一次性(stream 失败)时无 chunk → 完成后组件隐藏,
 * 数据仍由左栏报告/insight 真展示。
 */
import { useTypingStore } from '@/stores/typingStore'
import { useRunStore } from '@/stores/runStore'

export function ReportStation() {
  const text = useTypingStore((s) => s.byAgent['writer']) ?? ''
  const writerState = useRunStore((s) => s.nodes['write']) // NodeName 'write'
  const drafting = writerState === 'running' || writerState === 'retrying'
  if (!drafting && !text) return null
  return (
    <div className="mt-[18px]">
      <div
        className="font-mono text-[10px] uppercase tracking-[.5px] text-text-muted mb-2 flex items-center gap-[7px] before:content-[''] before:w-[14px] before:h-px before:bg-[var(--tw)]"
        style={{ ['--tw' as string]: 'var(--id-writer)' }}
      >
        报告台 · 撰写员起草
      </div>
      <div className="bg-surface border border-border rounded-md px-[11px] py-[9px] text-[12px] leading-[1.6] text-text-primary whitespace-pre-wrap min-h-[40px]">
        {text ? (
          <>
            {text}
            <span
              className="inline-block w-[2px] h-[14px] align-[-2px] ml-px animate-pulse"
              style={{ background: 'var(--id-writer)' }}
            />
          </>
        ) : (
          <span className="text-text-muted italic">起草中…(撰写员正在综合判断,约 30–40 秒首段成型)</span>
        )}
      </div>
    </div>
  )
}
