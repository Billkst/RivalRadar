/**
 * Task 6 vertical slice 占位组件(Task 8/9/10 实装替换)。
 * 集中放一个文件方便后续 grep "PlaceholderForTask" 清理。
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function CompetitorOverviewPlaceholder() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">竞品速览(占位)</CardTitle>
      </CardHeader>
      <CardContent className="text-xs italic text-text-muted">
        Task 8 实装:CompetitorOverview + FeatureTree + Pricing + SWOT 4 卡。
      </CardContent>
    </Card>
  )
}

export function ComparisonMatrixRowPlaceholder() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">跨竞品对比矩阵(占位 1 行)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="py-2 text-left font-medium text-text-muted">维度</th>
                <th className="py-2 text-left font-medium text-text-muted">竞品 A</th>
                <th className="py-2 text-left font-medium text-text-muted">竞品 B</th>
                <th className="py-2 text-left font-medium text-text-muted">竞品 C</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="py-2 text-text-muted">pricing</td>
                <td className="py-2 italic text-text-muted">Task 10 实装</td>
                <td className="py-2 italic text-text-muted">…</td>
                <td className="py-2 italic text-text-muted">…</td>
              </tr>
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

export function EvidenceSheetPlaceholder() {
  return (
    <Card>
      <CardContent className="pt-4 text-xs italic text-text-muted">
        Evidence Sheet(右滑面板)Task 9 实装:点引用 chip → 滑出证据全文 + 标记质疑。
      </CardContent>
    </Card>
  )
}
