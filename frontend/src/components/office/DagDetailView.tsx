/**
 * DagDetailView — DAG tab 详情视图(plan v3.2 §6)。
 *
 * 包装 Task 6 已有 DagCanvas + DagDrawer + QCIssuePanel,作为 ViewSwitcher
 * dag tab 内容。Office view 切换到 DAG 时显示完整工程深度,符合 plan §3 P0-3
 * 双视图叙事的次视图(intelligence desk 气质,DESIGN.md §Aesthetic Direction)。
 *
 * 后续 Epic 5.3 加 ObservabilityPanel(原 Codex #15 raw event timeline + retry
 * index 推导),完整工程视图。本 commit 只包当前 DAG + QC + Trace drawer。
 */
import * as React from 'react'
import { DagCanvas } from '@/components/dag/DagCanvas'
import { DagDrawer } from '@/components/dag/DagDrawer'
import { QCIssuePanel } from '@/components/QCIssuePanel'

interface DagDetailViewProps {
  runId: string | null
}

export function DagDetailView({ runId }: DagDetailViewProps) {
  const [drawerNode, setDrawerNode] = React.useState<string | null>(null)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8">
          <DagCanvas onNodeClick={setDrawerNode} />
        </div>
        <div className="col-span-12 lg:col-span-4">
          <QCIssuePanel />
        </div>
      </div>
      <DagDrawer
        runId={runId}
        nodeName={drawerNode}
        open={drawerNode !== null}
        onClose={() => setDrawerNode(null)}
      />
    </div>
  )
}
