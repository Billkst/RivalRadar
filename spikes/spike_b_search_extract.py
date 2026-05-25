"""Spike B:搜索/抽取 API 对真实竞品的可达性 + 质量实测。

对 1 英(Notion)+ 1 中(飞书)竞品各跑 5 个维度查询,记录:
命中数 / 是否拿到正文(可抽取) / 是否命中官方域名(权威) / 是否有发布日期(新鲜度)。
默认用 Tavily(search + include_raw_content 一次拿到正文,省一个独立抽取层)。
"""
from __future__ import annotations

from tavily import TavilyClient

from rivalradar import config

PROBES = {
    "Notion (en)": [
        "Notion pricing plans 2026",
        "Notion features database views",
        "Notion integrations list",
        "Notion reviews G2",
        "Notion enterprise deployment SSO",
    ],
    "飞书 Lark (zh)": [
        "飞书 价格 套餐 2026",
        "飞书 功能 多维表格",
        "飞书 集成 应用",
        "飞书 用户评价 知乎",
        "飞书 企业版 部署 SSO",
    ],
}
OFFICIAL_DOMAINS = ("notion.so", "notion.com", "feishu.cn", "larksuite.com")


def run_probe(client: TavilyClient, query: str) -> dict:
    resp = client.search(query=query, max_results=5, include_raw_content=True)
    results = resp.get("results", [])
    return {
        "query": query,
        "hits": len(results),
        "extractable": sum(1 for r in results if r.get("raw_content")),
        "official": sum(1 for r in results if any(d in r.get("url", "") for d in OFFICIAL_DOMAINS)),
        "dated": sum(1 for r in results if r.get("published_date")),
        "top_url": results[0]["url"] if results else "—",
    }


def main() -> None:
    client = TavilyClient(api_key=config.tavily_api_key())
    for competitor, queries in PROBES.items():
        print(f"\n=== {competitor} ===")
        for q in queries:
            r = run_probe(client, q)
            print(f"  [{r['hits']}h {r['extractable']}ext {r['official']}off {r['dated']}dated] "
                  f"{r['query']}  ->  {r['top_url']}")
    print("\ndecision: GO if 每个竞品都拿到 >=1 官方权威源 + 评价面可抽取正文")


if __name__ == "__main__":
    main()
