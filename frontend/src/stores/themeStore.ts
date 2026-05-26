/**
 * themeStore — dark mode 持久化 + 系统偏好跟踪 + cleanup pattern (CQ4)。
 *
 * 设计:
 *   - init() 返回 cleanup fn,Layout useEffect 调 `const c = init(); return c`
 *   - 防 React StrictMode 双 effect → 双 matchMedia listener 泄漏
 *   - localStorage 持久化用户显式选择;首次进入跟随 prefers-color-scheme
 *   - 直接 toggle <html class="dark"> 而非 inline style(配合 tailwind darkMode:'class')
 */
import { create } from 'zustand'

const THEME_KEY = 'rr-theme'
type Theme = 'light' | 'dark'

interface ThemeStore {
  theme: Theme
  setTheme: (t: Theme) => void
  toggle: () => void
  /** 初始化:挂载 matchMedia listener + 读 localStorage + apply 到 DOM. 返回 cleanup. */
  init: () => () => void
}

function applyToDom(theme: Theme) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

function readInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  const saved = localStorage.getItem(THEME_KEY)
  if (saved === 'dark' || saved === 'light') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useThemeStore = create<ThemeStore>((set, get) => ({
  theme: readInitialTheme(),

  setTheme: (theme) => {
    localStorage.setItem(THEME_KEY, theme)
    applyToDom(theme)
    set({ theme })
  },

  toggle: () => {
    const next: Theme = get().theme === 'dark' ? 'light' : 'dark'
    get().setTheme(next)
  },

  init: () => {
    // Apply current theme to DOM on mount (in case <html> was rendered before
    // store hydrated — e.g. SSR or test env).
    applyToDom(get().theme)

    if (typeof window === 'undefined') return () => {}
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => {
      // Only follow system if user hasn't explicitly chosen.
      if (localStorage.getItem(THEME_KEY) !== null) return
      const sysTheme: Theme = e.matches ? 'dark' : 'light'
      applyToDom(sysTheme)
      set({ theme: sysTheme })
    }
    mq.addEventListener('change', onChange)
    return () => {
      mq.removeEventListener('change', onChange)
    }
  },
}))
