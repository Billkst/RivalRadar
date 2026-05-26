import * as React from 'react'
import { Loader2 } from 'lucide-react'
import { fetchTrace } from '@/lib/api'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import type { TraceEntry } from '@/types/api'

interface DagDrawerProps {
  runId: string | null
  nodeName: string | null
  open: boolean
  onClose: () => void
}

/**
 * 节点点击 → trace drawer(Task 6.3)。
 * 拉 GET /trace/:run,filter 当前节点,按 ts 倒序(最新在最上)。
 * Tab "最新" / "历史":显示 input_summary / output_summary / tokens / latency_ms。
 * **tokens 单字段**(Codex #2,不是 token_in/out)。**retry_index 从同节点出现次数推导**。
 */
export function DagDrawer({ runId, nodeName, open, onClose }: DagDrawerProps) {
  const [traces, setTraces] = React.useState<TraceEntry[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [tab, setTab] = React.useState<'latest' | 'history'>('latest')

  React.useEffect(() => {
    if (!open || !runId || !nodeName) return
    // Intentional reset on drawer open (re-fetch fresh trace each open).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTraces(null)
    setError(null)
    fetchTrace(runId)
      .then((all) =>
        setTraces(all.filter((t) => t.node === nodeName).sort((a, b) => (a.ts < b.ts ? 1 : -1))),
      )
      .catch((err) => setError(String(err)))
  }, [open, runId, nodeName])

  const latest = traces?.[0]
  const history = traces ?? []

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>节点 · {nodeName ?? ''}</SheetTitle>
          <SheetDescription>
            {history.length > 0 ? `${history.length} 条 trace(最新在最上)` : 'trace 加载中或为空'}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 flex gap-2 border-b border-border">
          <TabBtn active={tab === 'latest'} onClick={() => setTab('latest')}>
            最新
          </TabBtn>
          <TabBtn active={tab === 'history'} onClick={() => setTab('history')}>
            历史{history.length > 0 ? ` (${history.length})` : ''}
          </TabBtn>
        </div>

        <div className="mt-4 overflow-y-auto pr-1" style={{ maxHeight: 'calc(100vh - 240px)' }}>
          {error && <div className="text-xs text-error">加载失败:{error}</div>}
          {!error && traces === null && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <Loader2 className="h-3 w-3 animate-spin" />
              加载 trace...
            </div>
          )}
          {tab === 'latest' && latest && <TraceCard t={latest} retryIndex={history.length - 1} />}
          {tab === 'latest' && traces !== null && !latest && (
            <div className="text-xs italic text-text-muted">该节点暂无 trace 数据</div>
          )}
          {tab === 'history' && history.length > 0 && (
            <ol className="space-y-3 border-l-2 border-border pl-4">
              {history.map((t, i) => (
                <li key={t.id}>
                  <TraceCard t={t} retryIndex={history.length - 1 - i} />
                </li>
              ))}
            </ol>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs ${
        active ? 'border-b-2 border-accent font-medium text-accent' : 'text-text-muted'
      }`}
    >
      {children}
    </button>
  )
}

function TraceCard({ t, retryIndex }: { t: TraceEntry; retryIndex: number }) {
  return (
    <div className="rounded-md border border-border bg-surface-subtle p-3 text-xs">
      <div className="mb-2 flex items-center justify-between font-mono text-text-muted">
        <span>{t.ts.slice(0, 19)}</span>
        <span>
          retry #{retryIndex} · {t.tokens} tok · {t.latency_ms} ms
        </span>
      </div>
      <Field label="input_summary">{t.input_summary || '(empty)'}</Field>
      <Field label="output_summary">{t.output_summary || '(empty)'}</Field>
      {t.prompt && (
        <Field label="prompt">
          <pre className="whitespace-pre-wrap break-words font-mono text-[10px] text-text-muted">
            {t.prompt.slice(0, 200)}
            {t.prompt.length > 200 ? '…' : ''}
          </pre>
        </Field>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-2">
      <div className="text-text-muted">{label}</div>
      <div className="mt-0.5 text-text-primary">{children}</div>
    </div>
  )
}
