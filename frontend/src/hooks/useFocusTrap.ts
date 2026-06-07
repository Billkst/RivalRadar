/**
 * useFocusTrap — 抽屉 a11y:active 时把焦点 trap 在容器内 + Esc 关闭(DESIGN.md a11y)。
 *
 * 返回 ref 挂到抽屉容器(role="dialog")。active 翻 true 时聚焦首个可聚焦元素;
 * Tab/Shift+Tab 在首尾循环;Esc 调 onEscape。焦点恢复由 drawerStore.fullClose/goBack
 * 的 lastFocus.focus() 承担(此 hook 只管 trap + Esc)。
 */
import { useEffect, useRef } from 'react'

export function useFocusTrap(active: boolean, onEscape: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!active) return
    const el = ref.current
    if (!el) return
    const focusables = () =>
      Array.from(
        el.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])',
        ),
      ).filter((n) => n.offsetParent !== null)
    const first = focusables()[0]
    first?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onEscape()
        return
      }
      if (e.key !== 'Tab') return
      const f = focusables()
      if (!f.length) return
      const a = f[0]
      const z = f[f.length - 1]
      if (e.shiftKey && document.activeElement === a) {
        e.preventDefault()
        z.focus()
      } else if (!e.shiftKey && document.activeElement === z) {
        e.preventDefault()
        a.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [active, onEscape])
  return ref
}
