import type { Config } from 'tailwindcss'
import animatePlugin from 'tailwindcss-animate'

// DESIGN.md token injection.
// Colors map to CSS variables defined in src/styles/globals.css so utilities
// like `bg-accent text-accent` auto-follow light/dark theme without dark: prefix.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        'surface-subtle': 'var(--surface-subtle)',
        border: 'var(--border)',
        'text-primary': 'var(--text-primary)',
        'text-muted': 'var(--text-muted)',
        accent: 'var(--accent)',
        'accent-soft': 'var(--accent-soft)',
        success: 'var(--success)',
        warning: 'var(--warning)',
        error: 'var(--error)',
        info: 'var(--info)',
        'evidence-highlight': 'var(--evidence-highlight)',
        'source-line': 'var(--source-line)',
      },
      fontFamily: {
        sans: [
          'IBM Plex Sans',
          'IBM Plex Sans SC',
          'PingFang SC',
          'Microsoft YaHei',
          'Noto Sans CJK SC',
          'Source Han Sans SC',
          'system-ui',
          'sans-serif',
        ],
        mono: [
          'IBM Plex Mono',
          'IBM Plex Sans SC',
          'PingFang SC',
          'Microsoft YaHei',
          'Noto Sans CJK SC',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
      fontSize: {
        // DESIGN.md 8 sizes: 12 / 13 / 15(UI 主)/ 18(卡片标题)/ 22(区块头)/ 28(页面标题)/ 36(投影标题)
        '2xs': ['12px', { lineHeight: '1.18' }],
        xs: ['13px', { lineHeight: '1.35' }],
        sm: ['15px', { lineHeight: '1.35' }],
        base: ['15px', { lineHeight: '1.35' }],
        md: ['15px', { lineHeight: '1.55' }],
        lg: ['18px', { lineHeight: '1.35' }],
        xl: ['22px', { lineHeight: '1.35' }],
        '2xl': ['28px', { lineHeight: '1.18' }],
        '3xl': ['36px', { lineHeight: '1.18' }],
      },
      borderRadius: {
        // DESIGN.md: 6-8px (卡片 8, chip/角标 4-6)
        sm: '4px',
        DEFAULT: '6px',
        md: '6px',
        lg: '8px',
      },
      boxShadow: {
        // DESIGN.md: 浮层阴影(仅证据面板等)
        panel: '0 16px 40px rgba(20,24,23,.18)',
      },
      width: {
        // Left rail width (DESIGN.md spec §11.1 IA + Codex #13)
        rail: 'var(--rail-width)',
      },
      transitionTimingFunction: {
        // DESIGN.md Motion easings
        'enter-out': 'cubic-bezier(0, 0, 0.2, 1)',
        'exit-in': 'cubic-bezier(0.4, 0, 1, 1)',
        'move-in-out': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      transitionDuration: {
        // DESIGN.md DAG transitions: 700-1100ms (projection-readable)
        dag: '900ms',
      },
    },
  },
  plugins: [animatePlugin],
} satisfies Config
