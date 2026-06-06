/**
 * 标题解析 —— Markdown 渲染器与范文目录(TOC)共用同一套规则,保证 heading id 不错位。
 *
 * 渲染器按文档顺序给每个标题分配 id(headingId(seq));TOC 用相同的正则与序号枚举标题,
 * 两边对同一份 markdown 跑同一逻辑 → id 必然一致,锚点跳转可靠。
 */
export interface Heading {
  id: string
  level: number
  text: string
}

// 1-5 级标题。与渲染器完全一致:必须 `#` 后跟空格再跟内容。
export const HEADING_RE = /^(#{1,5})\s+(.+)$/

export function headingId(seq: number): string {
  return `md-h-${seq}`
}

export function parseHeadings(md: string): Heading[] {
  const out: Heading[] = []
  let seq = 0
  for (const raw of md.replace(/\r\n/g, '\n').split('\n')) {
    const m = HEADING_RE.exec(raw.trimEnd())
    if (m) {
      out.push({ id: headingId(seq), level: m[1].length, text: m[2] })
      seq++
    }
  }
  return out
}
