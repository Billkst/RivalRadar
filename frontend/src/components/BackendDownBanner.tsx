import { AlertTriangle, RotateCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useHealthz } from '@/hooks/useHealthz'

/**
 * 全局横幅:后端 /healthz 不可达时显示。
 * 提示用户启动后端,提供"重试"按钮(避免刷整页)。
 * Mounts under <BrowserRouter> in App.tsx so it can sit above all routes.
 */
export function BackendDownBanner() {
  const { backendDown, checking, retry } = useHealthz()
  if (checking || !backendDown) return null
  return (
    <div className="flex items-center justify-between gap-3 border-b border-warning bg-warning/10 px-4 py-2 text-xs text-warning">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 flex-shrink-0" />
        <span>
          后端未启动 · 请先在项目根运行 <code className="font-mono">.venv/bin/python main.py</code>{' '}
          · 见 README.md
        </span>
      </div>
      <Button variant="outline" size="sm" onClick={retry} className="gap-1.5">
        <RotateCw className="h-3 w-3" />
        重试
      </Button>
    </div>
  )
}
