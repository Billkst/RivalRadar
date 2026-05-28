import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { BackendDownBanner } from '@/components/BackendDownBanner'
import { RunsPage } from '@/pages/RunsPage'
import { RunPage } from '@/pages/RunPage'
import { CompetitorPage } from '@/pages/CompetitorPage'

/**
 * App root — BrowserRouter + Routes (plan v2 Task 3).
 *
 * Routes:
 *   /                                   → redirect to /runs
 *   /runs                               → RunsPage (list + create form)
 *   /run/:run_id                        → RunPage (Task 6 vertical slice)
 *   /run/:run_id/competitor/:idx        → CompetitorPage (Codex #12; Task 8 detail)
 *   *                                   → fallback inside Layout
 *
 * Global mounts:
 *   - <BackendDownBanner /> — sticky above all routes if /healthz unreachable
 *   - <Toaster />           — Task 11 (FlagButton 4 错误 + 通知)
 */
function App() {
  return (
    <BrowserRouter>
      <BackendDownBanner />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/runs" replace />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/run/:run_id" element={<RunPage />} />
          <Route path="/run/:run_id/competitor/:idx" element={<CompetitorPage />} />
          <Route path="*" element={<div className="p-6 text-sm text-text-muted">页面不存在</div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
