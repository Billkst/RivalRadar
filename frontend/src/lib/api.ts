/**
 * Typed fetch wrappers over backend `/api/*` endpoints.
 * Proxy is configured in vite.config.ts: `/api/*` → `http://localhost:8000/*`.
 *
 * SSE streaming (POST /run + GET /stream/:id) lives in `@/hooks/useSSE` —
 * this file only owns one-shot JSON requests.
 */
import { headersFromConfig, llmHeaders, type LLMConfig } from '@/lib/llmConfig'
import type {
  AgentSkillRow,
  AnnotationCreate,
  AnnotationOut,
  CompetitorAnalysis,
  CurationDrop,
  DecisionSet,
  DiscoverySet,
  Evidence,
  QueryRecord,
  ReportInsight,
  RunDetail,
  RunSummary,
  SanitizedQCResult,
  TraceEntry,
} from '@/types/api'

// 生产(Vercel)把 VITE_API_BASE 设为后端公网根地址(不带 /api 前缀);
// 本地 dev 不设 → 回退 '/api' → vite 代理剥 /api 前缀转 localhost:8000(行为不变)。
export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // init.headers 必须先解构出来:若把 `...init` 放在 headers 键之后展开,
  // init 自带的 headers 会整体覆盖刚合入的 Content-Type,带自定义头(如
  // BYOK llmHeaders())的请求就丢掉 application/json → 后端按 text/plain 拒解 → 422。
  const { headers: initHeaders, ...restInit } = init ?? {}
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(initHeaders ?? {}) },
    ...restInit,
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

// ─── Plan C 检索台 / 策展剔除清单(GET /runs/:id/queries|curation-drops)──────
// codex P1#4:jsonFetch 已自动前缀 /api → 路径不要再写 /api,否则 /api/api/...
export const fetchQueries = (runId: string) => jsonFetch<QueryRecord[]>(`/runs/${runId}/queries`)
export const fetchCurationDrops = (runId: string) =>
  jsonFetch<CurationDrop[]>(`/runs/${runId}/curation-drops`)

// ─── Plan C agent 技能(GET/PUT/DELETE /agent-skills,run 无关)──────────────
// codex P1#4:jsonFetch 已前缀 /api → 勿写 /api。
export const fetchAgentSkills = () => jsonFetch<AgentSkillRow[]>('/agent-skills')
export const putAgentSkill = (body: { agent_id: string; skill_id: string; version: string; enabled: boolean }) =>
  jsonFetch<{ ok: boolean }>('/agent-skills', { method: 'PUT', body: JSON.stringify(body) })
export const deleteAgentSkill = (agentId: string, skillId: string) =>
  jsonFetch<{ ok: boolean }>(`/agent-skills/${agentId}/${skillId}`, { method: 'DELETE' })

// ─── Discover competitors (Epic 1.1 引导式 setup)──────────────────────────
// LLM 不通 → 后端 503;调用方 catch 提示手动输入(非静默)。
// BYOK:带用户模型三头(未配置为 {},后端走 env fallback)。
export const discoverCompetitors = (seed: string, industryHint?: string) =>
  jsonFetch<DiscoverySet>('/discover-competitors', {
    method: 'POST',
    headers: llmHeaders(),
    body: JSON.stringify({ seed, industry_hint: industryHint || null }),
  })

// ─── BYOK 连通性测试(POST /llm/ping)──────────────────────────────────────
// 头直接用传入 cfg 构造 —— 测「表单当前值」而非已保存值。后端响应恒 200,
// 成功 {ok:true, latency_ms};失败 {ok:false, error_type, detail(已脱敏)}。
export interface PingLLMResult {
  ok: boolean
  latency_ms?: number
  completion_tokens?: number // 本次测试实际吐了多少输出 token(思考 token 计入)
  thinking?: boolean // 厂商默认开了思考模式(响应带 reasoning_content)—— 延迟主因的归因线索
  error_type?: 'auth' | 'not_found' | 'bad_request' | 'timeout' | 'connection' | 'unconfigured' | 'other'
  detail?: string
}
// 注意:测试用的是**表单当前值**(不是已保存值),所以这里不能复用 llmHeaders(),
// 但头的构造共用 headersFromConfig 单一真源(防两份手写副本漂移)。
// max_tokens 必须一起送 —— 后端的 ping 会按真 run 的额度发请求,上限填错了当场 400,
// 而不是等你花几分钟跑一个必死的 run 才发现。
export const pingLLM = (cfg: LLMConfig) =>
  jsonFetch<PingLLMResult>('/llm/ping', { method: 'POST', headers: headersFromConfig(cfg) })

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

// ─── Delete run(历史列表手动删除,前端带二次确认)──────────────────────────
// DELETE /run/:id — 级联删所有关联表;run 不存在 → 404。
export const deleteRun = (runId: string) =>
  jsonFetch<{ run_id: string; deleted: boolean }>(`/run/${runId}`, { method: 'DELETE' })
