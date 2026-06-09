/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 生产后端公网根地址(不带 /api 前缀);本地 dev 不设,回退到 vite 代理的 /api。 */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
