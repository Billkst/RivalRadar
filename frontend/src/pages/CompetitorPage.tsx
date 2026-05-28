import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * /run/:run_id/competitor/:idx — 单竞品详情(Codex #12 spec §11.1 IA)。
 * Task 8 会在此挂载:CompetitorOverview / FeatureTree / Pricing / SWOT 单竞品视图。
 */
export function CompetitorPage() {
  const { run_id, idx } = useParams<{ run_id: string; idx: string }>()
  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" asChild>
        <Link to={`/run/${run_id}`} className="gap-1">
          <ArrowLeft className="h-3 w-3" />
          返回 Run
        </Link>
      </Button>
      <Card>
        <CardHeader>
          <CardTitle>
            竞品 #{idx} · <span className="font-mono text-sm text-text-muted">{run_id}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs italic text-text-muted">
          单竞品详情(CompetitorOverview / FeatureTree / Pricing / SWOT)将在 Task 8 实装。
        </CardContent>
      </Card>
    </div>
  )
}
