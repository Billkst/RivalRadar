"""C-1 集成冒烟:真实 Tavily → collect() → Evidence。需 TAVILY_API_KEY。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rivalradar import config
from rivalradar.collect.pipeline import collect
from rivalradar.search.tavily_provider import TavilyProvider


def main() -> None:
    provider = TavilyProvider(api_key=config.tavily_api_key())
    evs = collect(["Notion"], ["pricing", "core_workflows"], provider=provider,
                  languages=("en",), max_results=3, max_workers=3)
    print(f"collected {len(evs)} evidence")
    for e in evs[:6]:
        body = (e.content or "")[:80].replace("\n", " ")
        print(f"  [{e.dimension}] {e.source_url}  | {body}")
    assert evs, "no evidence collected"
    assert all(e.source_url and e.fetched_at for e in evs), "missing source/fetched_at"
    print("SPIKE C OK: real evidence with source + timestamp")


if __name__ == "__main__":
    main()
