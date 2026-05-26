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
  Evidence,
  RunDetail,
  RunSummary,
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
export const fetchReport = (runId: string) =>
  fetch(`${API_BASE}/report/${runId}`).then((r) => {
    if (!r.ok) throw new ApiError(r.status, `HTTP ${r.status}`)
    return r.text()
  })
export const fetchTrace = (runId: string) => jsonFetch<TraceEntry[]>(`/trace/${runId}`)

// ─── Annotations ──────────────────────────────────────────────────────────
export const createAnnotation = (payload: AnnotationCreate) =>
  jsonFetch<AnnotationOut>('/annotations', { method: 'POST', body: JSON.stringify(payload) })
