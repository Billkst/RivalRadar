/**
 * BYOK(Bring Your Own Key)模型配置 — localStorage 是唯一事实源。
 *
 * 安全铁律(KEY 纪律):API Key 只保存在浏览器本地(localStorage),
 * 调用时经 X-LLM-* 三个请求头带给后端做 per-request 转发,
 * 绝不进 zustand store 状态树 / 绝不落库 / 绝不打日志。
 *
 * 请求头契约(前后端共同遵守,全有或全无):
 *   X-LLM-Base-URL / X-LLM-API-Key / X-LLM-Model
 */

export interface LLMConfig {
  provider: string
  baseUrl: string
  apiKey: string
  model: string
  /**
   * 该厂商单次输出的 token 上限。0 / undefined = 不声明。
   *
   * 为什么需要:后端 structured_call 默认按 131072 要输出额度 —— 那是**火山方舟端点实测的
   * 硬上限**,对别家一律过大,DeepSeek / OpenAI / Kimi 都会直接 400。填上你所用厂商文档里的
   * 输出上限,后端会按 min(想要的, 这个值) 钳掉,厂商差异不外溢到上层。
   */
  maxTokens?: number
}

export interface ProviderPreset {
  id: string
  label: string
  /** custom 为空串 → 手填 */
  baseUrl: string
  /** 该厂商常用模型 id(**精确 API 字符串**,不是展示名)。第一个作默认值。custom 为空 → 手填 */
  models: string[]
  /** 获取 API Key 的控制台链接;custom 为空串 → 不显示 */
  consoleUrl: string
  /** 单次输出上限;0 = 未知(手填)。每个值的出处见预设里的注释。 */
  maxOutputTokens: number
}

// 常见 OpenAI 兼容厂商预设(写死,不做远端配置)。
//
// ⚠️ maxOutputTokens 与 models 都是**外部易变事实,必须查厂商文档,不能凭记忆推断**。
// 每个值都标了出处。两个方向都会出事:
//   - 填太大 → 厂商 400 拒绝请求(OpenAI/Gemini/Claude 的上限都 < 后端默认要的 131072);
//   - 填太小 → 大 JSON 被截断 → 三次重试全败 → 整个 run 死(这正是后端把默认额度设到
//     131072 的原因,见 llm/structured.py 的注释)。
// 「测试连接」发的就是真分析会发的那个 max_tokens,所以填错了点一下按钮当场就知道。
export const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: 'ark',
    label: '火山方舟(豆包)',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    models: ['doubao-seed-2-0-lite-251215'],
    consoleUrl: 'https://console.volcengine.com/ark',
    maxOutputTokens: 131072, // 本仓库实测硬上限(131073 报 400 InvalidParameter)
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1',
    // 官方文档(api-docs.deepseek.com):V4 两款,1M 上下文。旧的 deepseek-chat /
    // deepseek-reasoner 已宣布 2026-07-24 废弃,别再用。
    models: ['deepseek-v4-flash', 'deepseek-v4-pro'],
    consoleUrl: 'https://platform.deepseek.com',
    maxOutputTokens: 384000, // 官方文档:V4 两款输出上限均为 384K
  },
  {
    id: 'moonshot',
    label: 'Kimi(月之暗面)',
    baseUrl: 'https://api.moonshot.cn/v1',
    models: ['kimi-k2.6', 'kimi-k2.7-code'],
    consoleUrl: 'https://platform.moonshot.cn',
    // 官方文档**未公布 per-model 输出上限**(只说不传时默认给 1024)。这里给一个
    // 够本项目用且各家普遍接受的保守值 —— 标记为「未经文档确认」,填错以 ping 为准。
    maxOutputTokens: 32768,
  },
  {
    id: 'openai',
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol'],
    consoleUrl: 'https://platform.openai.com',
    maxOutputTokens: 128000, // 官方文档:GPT-5.6 三款输出上限均 128K
  },
  {
    id: 'anthropic',
    label: 'Anthropic Claude',
    baseUrl: 'https://api.anthropic.com/v1/',
    models: ['claude-opus-4-8', 'claude-sonnet-5'],
    consoleUrl: 'https://console.anthropic.com',
    maxOutputTokens: 128000, // 官方文档:Opus 4.8 同步调用输出上限 128K
  },
  {
    id: 'gemini',
    label: 'Google Gemini',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    models: ['gemini-2.5-flash', 'gemini-2.5-pro'],
    consoleUrl: 'https://aistudio.google.com',
    // 官方文档:2.5 Flash 输出上限 65535。注意 Gemini 把**思考 token 也算进这个额度**,
    // 额度给太紧会出现「只吐几十个 token 就停」的空响应。
    maxOutputTokens: 65535,
  },
  {
    id: 'custom',
    label: '自定义(OpenAI 兼容)',
    baseUrl: '',
    models: [],
    consoleUrl: '',
    maxOutputTokens: 0, // 未知 → 手填
  },
]

const STORAGE_KEY = 'rr.llmConfig.v1'

/** 读配置;缺任一必填字段 / 解析失败 → null(视同未配置)。 */
export function loadLLMConfig(): LLMConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const cfg = JSON.parse(raw) as Partial<LLMConfig>
    if (!cfg.baseUrl || !cfg.apiKey || !cfg.model) return null
    // maxTokens 是后加的可选字段:老配置没有它 → undefined → 不发该头 → 行为同旧版
    const maxTokens =
      typeof cfg.maxTokens === 'number' && cfg.maxTokens > 0 ? cfg.maxTokens : undefined
    return {
      provider: cfg.provider ?? 'custom',
      baseUrl: cfg.baseUrl,
      apiKey: cfg.apiKey,
      model: cfg.model,
      maxTokens,
    }
  } catch {
    return null
  }
}

export function saveLLMConfig(cfg: LLMConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg))
}

export function clearLLMConfig(): void {
  localStorage.removeItem(STORAGE_KEY)
}

/**
 * 配置 → X-LLM-* 头的**唯一**构造点(纯函数)。pingLLM 测「表单现值」、llmHeaders 读
 * 「已保存值」,两处共用这一个实现 —— 未来加第 5 个头只改这里,防两份手写副本漂移。
 * X-LLM-Max-Tokens 是第 4 个可选头,不进「全有或全无」契约 —— 缺它只是不钳输出上限。
 */
export function headersFromConfig(cfg: LLMConfig): Record<string, string> {
  const headers: Record<string, string> = {
    'X-LLM-Base-URL': cfg.baseUrl,
    'X-LLM-API-Key': cfg.apiKey,
    'X-LLM-Model': cfg.model,
  }
  if (cfg.maxTokens) headers['X-LLM-Max-Tokens'] = String(cfg.maxTokens)
  return headers
}

/** BYOK 请求头:未配置返回 {}(后端走 env fallback);配置了返回三头(契约:全有或全无)。 */
export function llmHeaders(): Record<string, string> {
  const cfg = loadLLMConfig()
  return cfg ? headersFromConfig(cfg) : {}
}
