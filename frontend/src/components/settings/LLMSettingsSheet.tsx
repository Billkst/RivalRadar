import * as React from 'react'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { pingLLM, type PingLLMResult } from '@/lib/api'
import {
  PROVIDER_PRESETS,
  clearLLMConfig,
  loadLLMConfig,
  saveLLMConfig,
  type LLMConfig,
} from '@/lib/llmConfig'
import { useLLMSettingsStore } from '@/stores/llmSettingsStore'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'

/**
 * LLMSettingsSheet — BYOK「模型设置」抽屉(右侧 slide-over)。
 *
 * 配置任意 OpenAI 兼容厂商的 base_url / API Key / 模型名;
 * key 只写 localStorage(lib/llmConfig 是唯一事实源),不进任何 store 状态树。
 * 「测试连接」用表单当前值(非已保存值)打 POST /llm/ping。
 */
export function LLMSettingsSheet() {
  const isOpen = useLLMSettingsStore((s) => s.isOpen)
  const close = useLLMSettingsStore((s) => s.close)
  return (
    <Sheet
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) close()
      }}
    >
      <SheetContent side="right" className="overflow-y-auto">
        {/* Radix 关闭即卸载 content → 表单每次打开重新从 localStorage 初始化 */}
        <SettingsForm />
      </SheetContent>
    </Sheet>
  )
}

// error_type → 中文分类文案(other → 直接显示后端脱敏 detail)
const PING_ERROR_TEXT: Record<string, string> = {
  auth: 'API Key 无效或已过期',
  not_found: '模型名不存在,检查拼写',
  timeout: '连接超时,检查 base_url 与网络',
  connection: '无法连接到该端点',
  unconfigured: '请先填写完整配置',
  bad_request: '参数被厂商拒绝 —— 多半是「输出上限」填得比该模型允许的大,按厂商文档调小',
  busy: '连通性测试并发已满,稍候几秒再点',
}

function pingFailText(res: PingLLMResult): string {
  if (res.error_type && res.error_type !== 'other') {
    return PING_ERROR_TEXT[res.error_type] ?? (res.detail || '未知错误')
  }
  return res.detail || '未知错误'
}

function SettingsForm() {
  const close = useLLMSettingsStore((s) => s.close)
  const bumpVersion = useLLMSettingsStore((s) => s.bumpVersion)

  // 读已保存配置作初始值(抽屉每次打开重新 mount;useState 只取首帧值,重渲染多读无妨)
  const saved = loadLLMConfig()
  const initialPreset =
    PROVIDER_PRESETS.find((p) => p.id === (saved?.provider ?? 'ark')) ?? PROVIDER_PRESETS[0]

  const [provider, setProvider] = React.useState(initialPreset.id)
  const [baseUrl, setBaseUrl] = React.useState(saved?.baseUrl ?? initialPreset.baseUrl)
  const [apiKey, setApiKey] = React.useState(saved?.apiKey ?? '')
  // 模型名默认就填好(预设第一款)—— 让用户去猜厂商的精确 model id 字符串是不合理的
  const [model, setModel] = React.useState(saved?.model ?? initialPreset.models[0] ?? '')
  // 输出上限:字符串态,允许清空(空 = 不声明)。老配置无此字段 → 落回预设默认值;
  // custom 预设的默认值是 0(未知)—— `?? ''` 对 0 不生效(0 非 nullish),必须 `|| ''`
  // 落空串,否则会渲染出 "0"、maxOk 判假、保存按钮被锁死(评审实测)。
  const [maxTokens, setMaxTokens] = React.useState(
    String(saved?.maxTokens ?? (initialPreset.maxOutputTokens || '')),
  )
  // 模型名用真下拉(不是 datalist —— datalist 会拿输入框现值去过滤候选,预填了 flash 就
  // 只剩 flash,pro 永远看不见)。手填模式作逃生口:厂商随时上新模型,写死下拉会把人挡在门外。
  const [customModel, setCustomModel] = React.useState(
    () => !initialPreset.models.includes(saved?.model ?? initialPreset.models[0] ?? ''),
  )
  const [showKey, setShowKey] = React.useState(false)
  const [testing, setTesting] = React.useState(false)
  const [testResult, setTestResult] = React.useState<{ ok: boolean; text: string } | null>(null)
  // 单调递增的测试序号:表单在 ping 进行中仍可编辑,旧请求晚到会用**上一套配置**的结果
  // 覆盖当前显示,谎称当前配置已测通(评审 P2)。每次发起自增,回来时只认最新那次。
  const testSeq = React.useRef(0)
  // 任何改动配置的编辑都作废进行中的 ping(自增序号)+ 清掉旧结果 —— 编辑后那条「连通」
  // 是对**旧配置**说的,留着就是误导。
  const invalidateTest = () => {
    testSeq.current += 1
    setTesting(false)
    setTestResult(null)
  }

  const preset = PROVIDER_PRESETS.find((p) => p.id === provider) ?? PROVIDER_PRESETS[0]

  const onProviderChange = (id: string) => {
    const next = PROVIDER_PRESETS.find((p) => p.id === id) ?? PROVIDER_PRESETS[0]
    setProvider(next.id)
    // 换厂商 → baseUrl / 模型名 / 输出上限**三个一起**跟着换。只换 baseUrl 会留下上一家的
    // 模型名和上限,那是最容易出错的半配置状态。custom 三个都清空手填。
    setBaseUrl(next.baseUrl)
    setModel(next.models[0] ?? '')
    setMaxTokens(next.maxOutputTokens ? String(next.maxOutputTokens) : '')
    setCustomModel(next.models.length === 0)
    // **必须清空 API Key**:一家的 key 属于一家。不清会把上一家(如 OpenAI)的 key 在下次
    // 测试/运行时发给新选的厂商端点 —— 换到自定义 URL 时就是把 key 送进别人的服务器(评审 P1)。
    setApiKey('')
    invalidateTest()
  }

  const MODEL_CUSTOM = '__custom__'
  const onModelSelect = (v: string) => {
    if (v === MODEL_CUSTOM) {
      setCustomModel(true)
    } else {
      setCustomModel(false)
      setModel(v)
    }
    invalidateTest()
  }

  // 全串数字校验,不用裸 parseInt —— parseInt("32,768")===32 会**静默**把从厂商文档粘贴
  // 的上限截成 32:ping 照样通过(吐 1 个 token 也合法),真 run 却必因 JSON 截断而死。
  // 上界镜像后端 _parse_max_tokens 的 1_048_576,超了在这里就拦,不必等 422。
  const MAX_TOKENS_CEILING = 1_048_576
  const maxDigitsOk = /^\d+$/.test(maxTokens.trim())
  const parsedMax = maxDigitsOk ? Number.parseInt(maxTokens.trim(), 10) : Number.NaN
  const maxOk =
    maxTokens.trim() === '' || (maxDigitsOk && parsedMax > 0 && parsedMax <= MAX_TOKENS_CEILING)

  const trimmed: LLMConfig = {
    provider,
    baseUrl: baseUrl.trim(),
    apiKey: apiKey.trim(),
    model: model.trim(),
    maxTokens: maxOk && parsedMax > 0 ? parsedMax : undefined,
  }
  const allFilled = !!(trimmed.baseUrl && trimmed.apiKey && trimmed.model)
  // 只认 https:明文 http 会让 API Key 在网线上裸奔(评审 P1)。所有真实厂商端点都是 https,
  // 后端也只放行 https(deps._validate_base_url),两端一致。
  const urlOk = /^https:\/\//.test(trimmed.baseUrl)
  const canSave = allFilled && urlOk && maxOk

  const runTest = async () => {
    if (testing) return
    if (!allFilled) {
      setTestResult({ ok: false, text: PING_ERROR_TEXT.unconfigured })
      return
    }
    if (!urlOk) {
      setTestResult({ ok: false, text: 'base_url 需以 https:// 开头(明文 http 会泄漏 API Key)' })
      return
    }
    const seq = ++testSeq.current
    const stale = () => seq !== testSeq.current // 期间又发起了新测试 → 本次结果作废
    setTesting(true)
    setTestResult(null)
    try {
      const res = await pingLLM(trimmed)
      if (stale()) return
      setTestResult(
        res.ok
          ? {
              ok: true,
              text:
                `连通 · ${res.latency_ms ?? '?'}ms` +
                (res.completion_tokens != null ? ` · 输出 ${res.completion_tokens} tok` : '') +
                (res.thinking ? '(含思考)' : ''),
            }
          : { ok: false, text: pingFailText(res) },
      )
    } catch (err) {
      if (stale()) return
      // /llm/ping 恒 200;走到这里是网络层 / 后端不可达
      setTestResult({
        ok: false,
        text: `测试请求失败:${err instanceof Error ? err.message : String(err)}`,
      })
    } finally {
      if (!stale()) setTesting(false)
    }
  }

  const save = () => {
    if (!canSave) return
    saveLLMConfig(trimmed)
    bumpVersion()
    close()
  }

  const clear = () => {
    clearLLMConfig()
    bumpVersion()
    setApiKey('') // 只清 key;模型名/上限回落预设默认,省得重配一遍
    setModel(preset.models[0] ?? '')
    setMaxTokens(preset.maxOutputTokens ? String(preset.maxOutputTokens) : '')
    invalidateTest()
  }

  const inputCls =
    'w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50'
  const labelCls = 'text-xs font-medium text-text-muted'

  return (
    <div className="flex h-full flex-col gap-5">
      <SheetHeader>
        <SheetTitle>模型设置</SheetTitle>
        <SheetDescription>
          API Key 仅保存在你的浏览器本地(localStorage),不会上传或存储到服务器;调用时经 HTTPS
          直达后端转发给所选厂商。
        </SheetDescription>
      </SheetHeader>

      {/* 厂商 */}
      <div>
        <label htmlFor="llm-provider" className={labelCls}>
          厂商(OpenAI 兼容)
        </label>
        <select
          id="llm-provider"
          value={provider}
          onChange={(e) => onProviderChange(e.target.value)}
          className={`${inputCls} mt-1`}
        >
          {PROVIDER_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        {preset.consoleUrl && (
          <a
            href={preset.consoleUrl}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-block text-xs text-accent hover:underline"
          >
            前往控制台获取 API Key ↗
          </a>
        )}
      </div>

      {/* base_url */}
      <div>
        <label htmlFor="llm-base-url" className={labelCls}>
          base_url
        </label>
        <input
          id="llm-base-url"
          type="text"
          value={baseUrl}
          onChange={(e) => {
            setBaseUrl(e.target.value)
            invalidateTest()
          }}
          placeholder="https://api.example.com/v1"
          autoComplete="off"
          spellCheck={false}
          className={`${inputCls} mt-1 font-mono text-xs`}
        />
        {trimmed.baseUrl.length > 0 && !urlOk && (
          <div className="mt-1 text-xs text-warning">需以 http:// 或 https:// 开头</div>
        )}
      </div>

      {/* API Key */}
      <div>
        <label htmlFor="llm-api-key" className={labelCls}>
          API Key
        </label>
        <div className="mt-1 flex gap-2">
          <input
            id="llm-api-key"
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value)
              invalidateTest()
            }}
            placeholder="sk-..."
            autoComplete="off"
            spellCheck={false}
            className={`${inputCls} font-mono text-xs`}
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => setShowKey((v) => !v)}
            aria-label={showKey ? '隐藏 API Key' : '显示 API Key'}
            title={showKey ? '隐藏 API Key' : '显示 API Key'}
            className="shrink-0"
          >
            {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* 模型名 */}
      <div>
        {/* htmlFor 跟着当前实际渲染的控件走 —— 指向不存在的 id 时点 label 无反应,
            屏幕阅读器也读不到 select 的名字(评审 a11y 抓出) */}
        <label
          htmlFor={customModel || preset.models.length === 0 ? 'llm-model' : 'llm-model-select'}
          className={labelCls}
        >
          模型名
        </label>
        {preset.models.length > 0 && (
          <select
            id="llm-model-select"
            aria-label="模型名"
            value={customModel ? MODEL_CUSTOM : model}
            onChange={(e) => onModelSelect(e.target.value)}
            className={`${inputCls} mt-1 font-mono text-xs`}
          >
            {preset.models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
            <option value={MODEL_CUSTOM}>其他(手填)…</option>
          </select>
        )}
        {(customModel || preset.models.length === 0) && (
          <input
            id="llm-model"
            type="text"
            value={model}
            onChange={(e) => {
              setModel(e.target.value)
              invalidateTest()
            }}
            placeholder="模型 id(厂商文档里的精确字符串)"
            autoComplete="off"
            spellCheck={false}
            className={`${inputCls} mt-1 font-mono text-xs`}
          />
        )}
      </div>

      {/* 输出上限 */}
      <div>
        <label htmlFor="llm-max-tokens" className={labelCls}>
          单次输出上限(max_tokens)
        </label>
        <input
          id="llm-max-tokens"
          type="text"
          inputMode="numeric"
          value={maxTokens}
          onChange={(e) => {
            setMaxTokens(e.target.value)
            invalidateTest()
          }}
          placeholder="留空 = 不声明"
          autoComplete="off"
          spellCheck={false}
          className={`${inputCls} mt-1 font-mono text-xs`}
        />
        <p className="mt-1 text-xs text-text-muted">
          各家的输出上限不同,填你所用模型文档里的值。填太大会被厂商拒(「测试连接」发的就是真
          分析时会发的那个值,当场就能看出来)。
        </p>
        {!maxOk && (
          <div className="mt-1 text-xs text-warning">
            需为纯数字正整数(≤ 1048576,不带逗号/单位),或留空
          </div>
        )}
      </div>

      {/* 测试连接 */}
      <div>
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void runTest()}
            disabled={testing}
            className="gap-1"
          >
            {testing && <Loader2 className="h-3 w-3 animate-spin" />}
            测试连接
          </Button>
          {testResult && (
            <span
              className={`text-xs ${testResult.ok ? 'text-success' : 'text-error'} ${
                testResult.ok ? 'font-mono tabular-nums' : ''
              }`}
            >
              {testResult.text}
            </span>
          )}
        </div>
      </div>

      {/* 保存 / 清除 */}
      <div className="mt-auto flex items-center justify-between border-t border-border pt-4">
        <button
          type="button"
          onClick={clear}
          className="text-xs text-text-muted hover:text-error"
          title="从浏览器 localStorage 删除已保存的配置"
        >
          清除配置
        </button>
        <Button type="button" onClick={save} disabled={!canSave}>
          保存
        </Button>
      </div>
    </div>
  )
}
