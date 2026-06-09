import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// WSL2 + Clash 兜底:dev server 启动即清代理 env,让 /api 回环代理(→ localhost:8000)永不被
// Clash fake-ip 拦截 —— 无论 Clash 开/关、无论走 scripts/dev-frontend.sh 还是裸 `pnpm dev` 都成立。
for (const k of ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']) {
  delete process.env[k]
}
process.env.NO_PROXY = process.env.no_proxy =
  ['localhost', '127.0.0.1', process.env.NO_PROXY].filter(Boolean).join(',')

// Shared proxy config for both dev and preview servers.
// Vite 5+ stopped applying server.proxy to preview server — must declare both.
const apiProxy = {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    rewrite: (p: string) => p.replace(/^\/api/, ''),
  },
}

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // host: true 绑 0.0.0.0 —— WSL2 里 Windows 浏览器经 localhost / WSL2 IP 都能访问
    // (默认只绑 127.0.0.1,WSL2↔Windows localhost 转发不稳时打不开)。
    host: true,
    port: 3000,
    proxy: apiProxy,
  },
  preview: {
    host: true,
    port: 3000,
    proxy: apiProxy,
  },
})
