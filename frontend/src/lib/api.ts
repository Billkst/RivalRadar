/**
 * Typed fetch wrappers over backend `/api/*` endpoints.
 * Proxy is configured in vite.config.ts: `/api/*` → `http://localhost:8000/*`.
 *
 * SSE streaming (POST /run + GET /stream/:id) lives in `@/hooks/useSSE` —
 * this file only owns one-shot JSON requests.
 */
import type {
  AnnotationCreate,
  AnnotationOut,
  CompetitorAnalysis,
  DecisionSet,
  Evidence,
  ReportInsight,
  RunDetail,
  RunSummary,
  SanitizedQCResult,
  TraceEntry,
} from '@/types/api'

const API_BASE = '/api'

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    let detail: string
    try {
      const body = (await res.json()) as { detail?: string }
      detail = body.detail ?? `HTTP ${res.status}`
    } catch {
      detail = `HTTP ${res.status}`
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

// `erasableSyntaxOnly` (TS 6 strict mode default) forbids parameter properties.
// Declare `status` explicitly + assign in body.
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

// ─── healthz probe (A2: BackendDownBanner) ────────────────────────────────
export async function ping(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/healthz`, { method: 'GET' })
    if (!res.ok) return false
    const body = (await res.json()) as { ok?: boolean }
    return body.ok === true
  } catch {
    return false
  }
}

// ─── Reads ────────────────────────────────────────────────────────────────
export const fetchRuns = () => jsonFetch<RunSummary[]>('/runs')
export const fetchRun = (runId: string) => jsonFetch<RunDetail>(`/run/${runId}`)
export const fetchAnalysis = (runId: string) => jsonFetch<CompetitorAnalysis>(`/analysis/${runId}`)
export const fetchEvidence = (evidenceId: string) => jsonFetch<Evidence>(`/evidence/${evidenceId}`)
// Backend 返 {run_id, markdown},不是 text。原实现用 r.text() 拿 JSON 字符串
// 没 caller 触发是 silent bug — codex review 第一次用 ReportSheet fetchReport
// fallback 时暴露。修法:用 jsonFetch 解 JSON 然后 caller 取 .markdown。
export const fetchReport = (runId: string) =>
  jsonFetch<{ run_id: string; markdown: string }>(`/report/${runId}`)
export const fetchTrace = (runId: string) => jsonFetch<TraceEntry[]>(`/trace/${runId}`)

// ─── full-C 决策管道只读端点(Epic 2.4 → cockpit Epic 4/5 消费)─────────────
// 老 run / 进行中 run 无对应表行 → 后端 404;cockpitStore catch ApiError(404)
// 当作 'absent'(空态),区别于 'error'(网络/5xx)。
export const fetchDecisions = (runId: string) => jsonFetch<DecisionSet>(`/decisions/${runId}`)
export const fetchInsight = (runId: string) => jsonFetch<ReportInsight>(`/insight/${runId}`)
export const fetchQc = (runId: string) => jsonFetch<SanitizedQCResult>(`/qc/${runId}`)
// 批量证据(GET /runs/:id/evidence)— evidenceStore 一次性 seed 防 per-pill N+1。
export const fetchRunEvidence = (runId: string) => jsonFetch<Evidence[]>(`/runs/${runId}/evidence`)

// ─── Annotations ──────────────────────────────────────────────────────────
export const createAnnotation = (payload: AnnotationCreate) =>
  jsonFetch<AnnotationOut>('/annotations', { method: 'POST', body: JSON.stringify(payload) })

// ─── Cancel (F4 修订:真中断 in-flight LLM) ─────────────────────────────
// POST /run/:id/cancel — backend task.cancel() 中断 in-flight LLM/network
// + CAS mark run cancelled。前端 F4 mitigation 不必 await 此响应即可切 UI。
export interface CancelRunResponse {
  run_id: string
  cancelled: boolean      // 是否实际 cancel 了 in-flight task
  db_cancelled: boolean   // 是否实际写了 cancelled 状态(CAS)
}
export const cancelRun = (runId: string) =>
  jsonFetch<CancelRunResponse>(`/run/${runId}/cancel`, { method: 'POST' })
