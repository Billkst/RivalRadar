/**
 * 时间显示工具。后端统一存 UTC ISO(datetime.now(timezone.utc)),前端按北京时间展示。
 *
 * 用 sv-SE 区域:它原生输出 `YYYY-MM-DD HH:mm` 形态,配 timeZone='Asia/Shanghai'
 * 即得「北京时间」友好串,免手工拼接月日补零。解析失败回退原串(不崩 UI)。
 */
export function formatBeijing(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}
