/**
 * Demo fixture — D6 demo day bullet-proof 兜底(plan v3.2 §10 D5 Epic 7.1 +
 * §11 R3 Clash demo day 风险 mitigation)。
 *
 * 目标:demo 当天 LLM 不通(Clash 卡 / API rate limit / 网络故障)仍能完整跑
 * 一遍 25s office UI 演示。**纯前端 fixture,零依赖**:
 *   - 不打 backend(GET /run/:id 用 DEMO_RUN_DETAIL 替代)
 *   - 不打 SSE(用 fakeSSEPlayer 直接 replay SAMPLE_EVENTS)
 *   - 不需 LLM key,不需 backend 进程,只要 vite dev server / 静态 build
 *
 * 入口:
 *   - RunsPage 顶部 "🎬 Demo 模式" 卡片 → /run/run_demo01
 *   - RunPage 检测 isDemoRun() → bypass fetchRun + SSE,自动 playFakeSSE Real
 *
 * 与 fakeSSEPlayer 的关系:
 *   fakeSSEPlayer 是 dev 模式的"手动按按钮 spike",demo fixture 是"用户进入
 *   demo URL 自动播放" — 复用同一份 SAMPLE_EVENTS,只是触发路径不同。
 */
import type { RunDetail } from '@/types/api'

/** demo 专用 run_id,RunPage / RunsPage 用它判断走 demo 路径还是真打 backend。 */
export const DEMO_RUN_ID = 'run_demo01'

/** Mock RunSummary —— 数据与 SAMPLE_EVENTS 里的竞品 / 维度 1:1 对齐让 demo
 *  叙事一致。created_at 用 mount 时刻,这样卡片时间戳是"今天此刻"。 */
export const DEMO_RUN_DETAIL: RunDetail = {
  run_id: DEMO_RUN_ID,
  competitors: ['飞书', '钉钉', '企业微信'],
  dimensions: ['pricing', 'core_workflows', 'integrations', 'target_users'],
  status: 'done',
  degraded: false,
  created_at: new Date().toISOString(),
}

/** RunPage / RunsPage 用这个判断当前 run 是否走 demo 路径。 */
export function isDemoRun(run_id: string | undefined | null): boolean {
  return run_id === DEMO_RUN_ID
}
