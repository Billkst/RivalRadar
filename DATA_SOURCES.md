# 数据来源与合规声明(RivalRadar)

RivalRadar 仅采集**公开**竞品信息,遵守 robots.txt、限速、诚实 UA(`RivalRadarBot/0.1`),
并对每次运行记录实际访问的来源以备审计。

## 绿色(直接采集)
- 搜索 API(Tavily 主 / Exa 备)返回的公开搜索结果与摘要 —— 合规义务由 API 方承担
- 竞品官方网站 / 文档 / 定价页(robots 允许路径)
- Apple App Store 公开评论
- V2EX 公开帖子(robots 最宽松)
- 36氪 / 虎嗅 文章页(经搜索 API 取 URL 后 fetch,robots 允许)
- 酷安 应用详情与公开评论
- 其他公开站点(含长尾小站):按诚实 UA 查 robots 并遵守 + 限速

## 灰色(谨慎 / 间接)
- 掘金等:优先经搜索 API 或 RSS 间接获取
- linux.do:robots 通用允许但 disallow AI 爬虫并标 `ai-train=no` → 优先用搜索 API 摘要

## 红色(不自抓;仅经搜索 API 公开摘要间接引用)
- 知乎、小红书、微博、脉脉、即刻,以及一切登录墙站点
- 理由:robots 明确封锁 + 2025 年《反不正当竞争法》(2025.10.15 生效)禁止绕过技术措施获取数据
  + PIPL 个人信息合规义务 + 平台 ToS 禁止自动化访问
- 实现:见 `rivalradar/collect/policy.py` 的 `RED_DENYLIST`,自抓一律拒绝;这些来源只通过
  Tavily/Exa 返回的公开摘要间接呈现,并在报告中标注出处

## 不使用的手段
- 不使用任何反爬绕过工具(如 MediaCrawler 等),不使用他人账号 cookie 模拟登录
