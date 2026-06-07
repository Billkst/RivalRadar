/**
 * useFocusTrap — 抽屉 a11y:active 时把焦点 trap 在容器内 + Esc 关闭(DESIGN.md a11y)。
 *
 * 返回 ref 挂到抽屉容器(role="dialog")。active 翻 true 时聚焦首个可聚焦元素;
 * Tab/Shift+Tab 在首尾循环;Esc 调 onEscape。焦点恢复由 drawerStore.fullClose/goBack
 * 的 lastFocus.focus() 承担(此 hook 只管 trap + Esc)。
 *
 * depKey(Epic 6 review fix):初始聚焦只在 active false→true 跳变时跑,push 第 2/3 层
 * 抽屉(open 维持 true)不会把焦点移进新层内容。传 depKey(= 栈深度 / 栈顶 view key)
 * 让初始聚焦在每次新层入栈时重跑,焦点跟进新层。
 */
import { useEffect, useRef } from 'react'

const focusableSel =
  'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])'

export function useFocusTrap(active: boolean, onEscape: () => void, depKey?: string | number) {
  const ref = useRef<HTMLDivElement>(null)

  // 初始聚焦:active 翻 true 时,以及 depKey 变(push 新层)时,把焦点移进栈顶层内容。
  useEffect(() => {
    if (!active) return
    const el = ref.current
    if (!el) return
    const first = Array.from(el.querySelectorAll<HTMLElement>(focusableSel)).filter(
      (n) => n.offsetParent !== null,
    )[0]
    first?.focus()
  }, [active, depKey])

  // 键盘 trap + Esc(depKey 变不必重绑;focusables 每次按键实时取)。
  useEffect(() => {
    if (!active) return
    const el = ref.current
    if (!el) return
    const focusables = () =>
      Array.from(el.querySelectorAll<HTMLElement>(focusableSel)).filter(
        (n) => n.offsetParent !== null,
      )
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
