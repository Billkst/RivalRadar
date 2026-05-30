"""竞品自动发现(Epic 1.1):种子产品 → LLM 建议直接竞品 + 一句话理由。

诚实原则(plan T4):**只建议,不替用户决定**。endpoint 返建议,前端让用户勾选
增删确认后才 run。后处理强约束:去掉种子自身、按名去重、封顶 8 条(LLM 可能不遵守)。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from rivalradar.llm.structured import structured_call


class DiscoveredCompetitor(BaseModel):
    """一条竞品建议:名字 + 为什么是竞品(定位/重叠场景一句话)。"""

    name: str
    rationale: str


class DiscoverySet(BaseModel):
    """LLM function-calling 顶层输出 + GET 端点响应模型。

    max_length=8:与 prompt「最多 8 个」对齐的硬上限,在 schema 源头封顶防 LLM 失控。
    """

    competitors: list[DiscoveredCompetitor] = Field(default_factory=list, max_length=8)


def _normalize(name: str) -> str:
    """名字归一化(去空白 + 小写)用于去重 / 比对种子;中文无大小写,英文统一小写。"""
    return name.strip().lower().replace(" ", "")


def discover_competitors(
    seed: str, industry_hint: str | None, *, client, model
) -> DiscoverySet:
    """种子产品 → 直接竞品建议(最多 8)。LLM 失败上抛 StructuredCallError(端点转 503)。"""
    hint = f"行业 / 使用场景提示:{industry_hint.strip()}\n" if industry_hint and industry_hint.strip() else ""
    msgs = [{
        "role": "user",
        "content": (
            "你是竞品调研助手。给定一个种子产品,列出与它最直接竞争的、**真实存在**的竞品"
            "(最多 8 个),每个配一句话理由(定位 / 重叠的核心场景)。\n"
            f"{hint}种子产品:{seed.strip()}\n\n"
            "规则:\n"
            "- 只列真实存在的产品,不要编造。\n"
            "- 不要把种子产品本身列进去。\n"
            "- 同一产品不同写法只列一次。\n"
            "- 按竞争直接程度从高到低排序。"
        ),
    }]
    raw = structured_call(DiscoverySet, msgs, client=client, model=model)

    seed_norm = _normalize(seed)
    seen: set[str] = set()
    cleaned: list[DiscoveredCompetitor] = []
    for c in raw.competitors:
        n = _normalize(c.name)
        if not n or n == seed_norm or n in seen:
            continue  # 空名 / 种子自身 / 重复 → 丢弃
        seen.add(n)
        cleaned.append(c)
        if len(cleaned) >= 8:
            break
    return DiscoverySet(competitors=cleaned)
