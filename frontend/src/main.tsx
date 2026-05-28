import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Self-hosted IBM Plex via @fontsource (npmmirror-friendly, no Google Fonts CDN dependency).
// 4 weights for Sans (Regular/Medium/SemiBold/Bold per DESIGN.md hierarchy).
// Mono only needs Regular + Medium for code/timestamps/IDs.
// 中文 SC 走系统字体 fallback chain (PingFang SC / Microsoft YaHei / Noto Sans CJK SC) —
// Day-4 stretch will self-host subsetted IBM Plex Sans SC woff2 in public/fonts/.
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-sans/700.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
