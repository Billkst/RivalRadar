/**
 * Strict TypeScript mirror of the backend Pydantic schema.
 *
 * Source files (DO NOT diverge — Codex #2 enforcement; grep these when modifying):
 *   - rivalradar/schema/models.py  (domain entities)
 *   - rivalradar/api/schemas.py    (HTTP boundary models)
 *
 * Conventions:
 *   - Field names match Python `snake_case` 1:1 (no camelCase translation).
 *   - Literal unions mirror Python `Literal[...]` types.
 *   - Optional fields use `field?: T` only when Python has `Optional[T] = None`;
 *     fields with defaults but non-optional types stay required.
 */

// ─── Literal types (mirror Python Literal[...]) ────────────────────────────
export type Language = 'zh' | 'en'
export type SupportVerdict = 'supported' | 'partial' | 'unsupported'
export type ValueType = 'bool' | 'enum' | 'number' | 'quote_text'
export type ProblemType =
  | 'missing_evidence'
  | 'schema_incomplete'
  | 'hallucination'
  | 'low_coverage'
export type QCVerdict = 'pass' | 'retry_collect' | 'retry_analyze' | 'insufficient_evidence'

// ─── Controlled vocabulary (mirror Python CONTROLLED_DIMENSIONS tuple) ─────
export const CONTROLLED_DIMENSIONS = [
  'pricing',
  'deployment',
  'integrations',
  'target_users',
  'core_workflows',
  'review_sentiment',
] as const
export type ControlledDimension = (typeof CONTROLLED_DIMENSIONS)[number]

// ─── Domain entities (models.py) ───────────────────────────────────────────
export interface Evidence {
  id: string
  competitor: string
  dimension: string
  content: string
  source_url: string
  source_title: string
  language: Language
  fetched_at: string // ISO 8601
}

export interface EvidenceRef {
  evidence_id: string
  quote: string
  start?: number | null
  end?: number | null
  support_verdict: SupportVerdict
}

export interface FeatureItem {
  id: string
  name: string
  description: string
  category: string
  parent_id?: string | null
  evidence_refs: EvidenceRef[]
}

export interface PricingTier {
  name: string
  price: string // 字符串自由格式(Codex #2 — 不要假设是 number)
  billing_cycle: string
  features_included: string[]
  limits: string
}

export interface PricingModel {
  model_type: string
  tiers: PricingTier[]
  evidence_refs: EvidenceRef[]
}

export interface UserPersona {
  segment: string
  needs: string[]
  pain_points: string[]
  praise: string[]
  evidence_refs: EvidenceRef[]
}

export interface SWOTPoint {
  text: string
  evidence_refs: EvidenceRef[]
}

export interface SWOT {
  strengths: SWOTPoint[]
  weaknesses: SWOTPoint[]
  opportunities: SWOTPoint[]
  threats: SWOTPoint[]
}

export interface CompetitorProfile {
  name: string
  features: FeatureItem[]
  pricing: PricingModel
  personas: UserPersona[]
  swot: SWOT
}

export interface ComparisonCell {
  competitor: string
  value_type: ValueType
  value: string // 一律字符串,由 value_type 决定解读
  evidence_refs: EvidenceRef[]
}

export interface ComparisonRow {
  dimension: string
  cells: ComparisonCell[] // NOT "values" — Codex #2
}

export interface CompetitorAnalysis {
  competitors: CompetitorProfile[]
  comparison: ComparisonRow[]
}

export interface QCIssue {
  competitor: string
  dimension: string
  problem_type: ProblemType
  detail: string
}

export interface QCResult {
  verdict: QCVerdict
  issues: QCIssue[]
}

// ─── HTTP boundary models (schemas.py) ─────────────────────────────────────
export interface RunRequest {
  competitors: string[] // 1-5
  dimensions: string[] // 1-6 (controlled)
}

export interface RunSummary {
  run_id: string
  competitors: string[]
  dimensions: string[]
  status: string // running / done / insufficient_evidence / degraded / failed
  created_at: string
  degraded: boolean
}

// RunDetail extends RunSummary with no extra fields currently.
export type RunDetail = RunSummary

export interface AnnotationCreate {
  run_id: string
  evidence_id?: string | null
  conclusion_path?: string | null
  note: string
  // NO `kind` field — Codex #2
}

export interface AnnotationOut extends AnnotationCreate {
  id: number
  created_at: string
}

export interface TraceEntry {
  id: number
  run_id: string
  node: string
  prompt: string
  input_summary: string
  output_summary: string
  tokens: number // 单字段,NOT token_in/token_out — Codex #2
  latency_ms: number
  ts: string
  // NO retry_index — derive from trace.filter(t => t.node === N).length - 1
}

// ─── SSE event shapes (mirror rivalradar/api/sse.py) ───────────────────────
export interface SSEStartData {
  run_id: string
  ts: string
  replay?: boolean
}

// Live "node" event summary (per-node shape from _summarize_delta in sse.py)
export interface NodeSummary {
  node: string
  // node-specific extras
  evidence_added?: number // collect
  competitors?: number // analyze
  comparison_rows?: number // analyze
  report_chars?: number // write
  verdict?: QCVerdict // qc | finalize
  issues?: number // qc
  issue_types?: Record<string, number> // qc
  retry_count?: number // qc
  degraded?: boolean // qc
  status?: string // finalize
}

export interface SSENodeData {
  node: string
  summary: NodeSummary
  ts: string
}

// Replay "trace" event (sse.py _replay_from_trace shape)
export interface SSETraceData {
  node: string
  summary: {
    input: string
    output: string
    latency_ms: number
  }
  ts: string
}

export interface SSEErrorData {
  error: string
  ts: string
}

export interface SSEDoneData {
  run_id: string
  status: string
  ts: string
}

// ── v2 新增:progress + chunk(plan v3.2 §5 + backend api/schemas.py mirror)──
// backend SSEProgressData + SSEChunkData 同字段同结构,DO NOT diverge。

export interface SSEProgressData {
  agent_id: string                       // collector / analyst / writer / qc
  step: string                           // 节点内 step 名:search / extract / write / validate
  summary: string                        // 用户可见 narrative,中文已 i18n
  metric?: Record<string, number>        // 可选进度:{ current: 3, total: 7 }
  ts: string
}

export interface SSEChunkData {
  agent_id: string
  step: string                           // thinking / drafting / reasoning
  delta: string                          // LLM 增量 token(几个字符)
  ts: string
}

export type SSEEvent =
  | { type: 'start'; data: SSEStartData }
  | { type: 'node'; data: SSENodeData }
  | { type: 'trace'; data: SSETraceData }
  | { type: 'progress'; data: SSEProgressData }
  | { type: 'chunk'; data: SSEChunkData }
  | { type: 'error'; data: SSEErrorData }
  | { type: 'done'; data: SSEDoneData }
