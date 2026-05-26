/**
 * useSSE — imperative SSE driver for live (POST /run) + replay (GET /stream/:id).
 *
 * 设计要点(关键):
 *   1. **Module-level AbortController, NOT hook lifecycle bound** —
 *      RunsPage form submit 启动 live 流后,navigate 到 RunPage 时 RunsPage
 *      unmount 不能中断流。所以 controller 放 module-level,跨路由继承。
 *   2. **共用 runStore.handleEvent** — live + replay 同一 reducer 入口
 *      (Task 4 reducer 已 CQ1 normalize)。
 *   3. **openWhenHidden: true (A5)** — tab 切后台不断流(demo 投屏 + 切屏不掉链)。
 *   4. **onerror 不自动重试** — POST /run 重连会触发后端 create_run + 跑新一次
 *      graph,产生第二个 run(资源浪费 + 用户体验破)。throw → 立即终止。
 *   5. **Promise resolve 时机** — live: 收到第一个 start event 后(拿 run_id 给
 *      caller navigate);replay: queueMicrotask 立即(runId 已知)。
 */
import * as React from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useRunStore } from '@/stores/runStore'
import type { RunRequest, SSEEvent } from '@/types/api'

let activeController: AbortController | null = null

export interface StartLiveOpts {
  mode: 'live'
  request: RunRequest
}

export interface StartReplayOpts {
  mode: 'replay'
  runId: string
}

export type StartOpts = StartLiveOpts | StartReplayOpts

class StreamError extends Error {
  name = 'StreamError'
}

function parseSSE(msg: { event: string; data: string }): SSEEvent | null {
  if (!msg.event || !msg.data) return null
  try {
    const data = JSON.parse(msg.data)
    switch (msg.event) {
      case 'start':
        return { type: 'start', data }
      case 'node':
        return { type: 'node', data }
      case 'trace':
        return { type: 'trace', data }
      case 'error':
        return { type: 'error', data }
      case 'done':
        return { type: 'done', data }
      default:
        return null
    }
  } catch {
    return null
  }
}

async function startStream(opts: StartOpts): Promise<{ runId: string }> {
  // Abort previous stream (e.g. user launched a new run while old one streaming).
  activeController?.abort()
  const ctrl = new AbortController()
  activeController = ctrl

  const isLive = opts.mode === 'live'
  const url = isLive ? '/api/run' : `/api/stream/${opts.runId}`

  // Reset store before binding new stream. For replay, also seed runId so
  // store renders the loading shell immediately.
  useRunStore.getState().reset()
  if (!isLive) useRunStore.getState().startRun(opts.runId)

  return new Promise<{ runId: string }>((resolve, reject) => {
    let settled = false
    const doResolve = (runId: string) => {
      if (settled) return
      settled = true
      resolve({ runId })
    }
    const doReject = (err: Error) => {
      if (settled) return
      settled = true
      reject(err)
    }

    // Replay knows runId upfront — let caller await without waiting on server.
    if (!isLive) queueMicrotask(() => doResolve(opts.runId))

    fetchEventSource(url, {
      method: isLive ? 'POST' : 'GET',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: isLive ? JSON.stringify(opts.request) : undefined,
      signal: ctrl.signal,
      openWhenHidden: true,
      async onopen(response) {
        if (!response.ok) {
          const msg = `HTTP ${response.status}`
          doReject(new StreamError(msg))
          throw new StreamError(msg)
        }
        const ct = response.headers.get('content-type') ?? ''
        if (!ct.includes('text/event-stream')) {
          const msg = `bad content-type: ${ct || '(none)'}`
          doReject(new StreamError(msg))
          throw new StreamError(msg)
        }
      },
      onmessage(msg) {
        const ev = parseSSE(msg)
        if (!ev) return
        useRunStore.getState().handleEvent(ev)
        if (isLive && ev.type === 'start') {
          doResolve(ev.data.run_id)
        }
      },
      onerror(err) {
        // Disable fetch-event-source auto-retry — throwing stops the loop.
        const e = err instanceof Error ? err : new Error(String(err))
        doReject(e)
        throw e
      },
      onclose() {
        // Server-side clean close. If we never resolved (no 'start' event),
        // surface that as an error so caller doesn't hang.
        if (!settled) doReject(new StreamError('server closed before start event'))
      },
    }).catch(() => {
      // Swallow — settled via onopen/onerror/onclose paths. AbortError on
      // user-initiated stop() also lands here and is intentional.
    })
  })
}

function stopStream() {
  activeController?.abort()
  activeController = null
}

/**
 * Imperative SSE handle. Returns stable references via useMemo so the
 * `useEffect` deps work as expected when callers pass them to deps array.
 */
export function useSSE() {
  return React.useMemo(() => ({ start: startStream, stop: stopStream }), [])
}
