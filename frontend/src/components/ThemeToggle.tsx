import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useThemeStore } from '@/stores/themeStore'

/**
 * Dark mode toggle. Backed by themeStore (持久化 + 系统偏好跟踪 + cleanup).
 * Layout 通过 themeStore.init() 在 mount 时挂载 matchMedia listener。
 */
export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme)
  const toggle = useThemeStore((s) => s.toggle)
  const isDark = theme === 'dark'
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={isDark ? '切换到浅色' : '切换到深色'}
      title={isDark ? '切换到浅色' : '切换到深色'}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  )
}
