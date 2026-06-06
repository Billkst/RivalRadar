import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { BackendDownBanner } from '@/components/BackendDownBanner'
import { RunsPage } from '@/pages/RunsPage'
import { RunPage } from '@/pages/RunPage'
import { CompetitorPage } from '@/pages/CompetitorPage'
import { ReportView } from '@/pages/ReportView'
import { SamplesPage } from '@/pages/SamplesPage'
import { SampleView } from '@/pages/SampleView'

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
        {/* 全屏文档(Layout 外,免应用外壳挤占 + 打印隔离干净) */}
        <Route path="/run/:run_id/report" element={<ReportView />} />
        <Route path="/samples/:id" element={<SampleView />} />
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/runs" replace />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/samples" element={<SamplesPage />} />
          <Route path="/run/:run_id" element={<RunPage />} />
          <Route path="/run/:run_id/competitor/:idx" element={<CompetitorPage />} />
          <Route path="*" element={<div className="p-6 text-sm text-text-muted">页面不存在</div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
