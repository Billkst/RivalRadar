/**
 * 受控对比维度中文映射(P0 spike 反馈 — 默认中文展示)。
 *
 * Backend `rivalradar.schema.models.CONTROLLED_DIMENSIONS` 是英文 key 元组,
 * 本文件提供 key → 中文 label 映射,frontend UI(RunsPage checkbox /
 * RunPage 维度行 / 未来对比矩阵列头)统一通过 dimensionLabel() 转中文。
 *
 * 同步规则:backend 加新 dim → 本表必须同步加(否则 fallback 显示原 key 不报错)。
 */
export const DIMENSION_LABELS: Record<string, string> = {
  pricing: '定价',
  deployment: '部署方式',
  integrations: '集成生态',
  target_users: '目标用户',
  core_workflows: '核心工作流',
  review_sentiment: '用户口碑',
}

export function dimensionLabel(key: string): string {
  return DIMENSION_LABELS[key] ?? key
}
