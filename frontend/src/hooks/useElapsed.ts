/**
 * useElapsed — per-agent 已工作时长 hook(spike P0 反馈:看不到工作时长)。
 *
 * 输入:startTs(ISO 8601 string 或 unix ms 数字,null 表示未开始 / 已结束)
 * 输出:current ms 差值,每 100ms tick 更新一次
 *
 * 用途:AgentCharacter / LiveFeedPanel 显示 "已工作 12.3s",从节点 start 计时。
 * 节点 done 后 caller 应该传 null(或 freeze 显示当时 elapsed)停止 tick。
 *
 * 性能:setInterval 100ms = 10Hz,4 agent 同时 tick = 40Hz total,React 18
 * automatic batching 合并 setState,实测无卡顿。
 */
import * as React from 'react'

export function useElapsed(startTs: string | number | null): number {
  const [elapsed, setElapsed] = React.useState(0)

  React.useEffect(() => {
    if (startTs === null) {
      // caller 停止计时时同步清零,避免下一次启动先闪旧值。
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setElapsed(0)
      return
    }
    const startMs = typeof startTs === 'number' ? startTs : new Date(startTs).getTime()
    if (Number.isNaN(startMs)) {
      // Defensive:invalid ts string fallback elapsed=0,不 throw 防 UI 崩
      setElapsed(0)
      return
    }
    const tick = () => setElapsed(Math.max(0, Date.now() - startMs))
    // 立即 tick 一次,避免计时器首帧固定显示 0。
    tick()
    const id = setInterval(tick, 100)
    return () => clearInterval(id)
  }, [startTs])

  return elapsed
}
