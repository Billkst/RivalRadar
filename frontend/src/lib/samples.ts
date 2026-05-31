/**
 * 范文库注册表 —— 网上下载的**他人专业竞品分析报告**(非 RivalRadar 生成),
 * 作「理想输出长什么样」的参照。每份标明出处(来源 / 作者 / 日期 / 原文链接)。
 *
 * 文件作静态资源放 frontend/public/samples/,SampleView 运行时 fetch 渲染。
 * 元数据取自 references/ 各文件 frontmatter(source_url / author / publisher / date)。
 */
export interface Sample {
  id: string
  title: string
  publisher: string // 出处(媒体 / 机构)
  author: string
  date: string
  competitors: string[]
  kind: 'md' | 'pdf'
  file: string // /samples/ref-0X.(md|pdf)
  sourceUrl?: string // 原文链接(PDF 报告无公开直链)
  note: string // 一句话:为什么值得参照
}

export const SAMPLES: Sample[] = [
  {
    id: 'ref-01',
    title: '竞品分析报告:飞书 VS 钉钉 VS 企业微信,移动办公哪家强?',
    publisher: '人人都是产品经理',
    author: 'PM 大叔(互联网产品研究院)',
    date: '2020-05-08',
    competitors: ['飞书', '钉钉', '企业微信'],
    kind: 'md',
    file: '/samples/ref-01.md',
    sourceUrl: 'https://www.woshipm.com/evaluating/3821740.html',
    note: '7 维度对比(战略层 / 范围层 / 管理后台 / 特色功能 / 结构层 / 框架层 / 表现层)+ 3 类厂商横向 + 5 条建议,PM 学院派标准范式。',
  },
  {
    id: 'ref-02',
    title: '钉钉 VS 飞书,贴脸对打这五年',
    publisher: '36 氪',
    author: '一财商学院',
    date: '2025-07-23',
    competitors: ['钉钉', '飞书'],
    kind: 'md',
    file: '/samples/ref-02.md',
    sourceUrl: 'https://36kr.com/p/3391337145309573',
    note: '业内贴身分析,3 段式叙事(错位→对位 / 一号位变量 / 谁先盈利)+ 2025 ARR / MAU 硬数据 + AI 时代战略对位。',
  },
  {
    id: 'ref-03',
    title: '竞品分析:石墨文档 VS 腾讯文档 VS 金山文档',
    publisher: '人人都是产品经理',
    author: '不要睡懒觉',
    date: '2019-12-09',
    competitors: ['石墨文档', '腾讯文档', '金山文档'],
    kind: 'md',
    file: '/samples/ref-03.md',
    sourceUrl: 'https://www.woshipm.com/evaluating/1378039.html',
    note: '文档协作赛道经典对标,4 大维度 + 多人协作冲突 3 种技术路径 + B 端商业化方案对比。',
  },
  {
    id: 'ref-04',
    title: '2024 年中国协同办公市场研究报告',
    publisher: '艾瑞咨询 iResearch',
    author: '艾瑞咨询',
    date: '2024',
    competitors: ['赛道全景'],
    kind: 'pdf',
    file: '/samples/ref-04.pdf',
    note: '厂商权威 38 页赛道全景报告(PDF,点开下载查看)。',
  },
]

export function getSample(id: string): Sample | undefined {
  return SAMPLES.find((s) => s.id === id)
}
