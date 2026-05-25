from __future__ import annotations

from pydantic import BaseModel

# 每(维度, 语言)一个查询模板;{c} 处插竞品名。受控本体见 schema.models.CONTROLLED_DIMENSIONS。
_TEMPLATES: dict[tuple[str, str], str] = {
    ("pricing", "en"): "{c} pricing plans cost",
    ("pricing", "zh"): "{c} 价格 套餐 收费",
    ("deployment", "en"): "{c} deployment self-hosted SSO enterprise",
    ("deployment", "zh"): "{c} 部署 私有化 企业版 SSO",
    ("integrations", "en"): "{c} integrations API supported apps",
    ("integrations", "zh"): "{c} 集成 API 支持的应用",
    ("target_users", "en"): "{c} who is it for target users use cases",
    ("target_users", "zh"): "{c} 适合谁 目标用户 使用场景",
    ("core_workflows", "en"): "{c} key features core workflows",
    ("core_workflows", "zh"): "{c} 核心功能 主要特性",
    ("review_sentiment", "en"): "{c} reviews pros cons user feedback",
    ("review_sentiment", "zh"): "{c} 用户评价 优缺点 测评",
}


class Query(BaseModel):
    competitor: str
    dimension: str
    language: str
    query_text: str


def generate_queries(
    competitor: str,
    dimensions: list[str],
    *,
    languages: tuple[str, ...] = ("en", "zh"),
) -> list[Query]:
    out: list[Query] = []
    for dim in dimensions:
        for lang in languages:
            template = _TEMPLATES.get((dim, lang)) or _generic(lang)
            out.append(Query(
                competitor=competitor, dimension=dim, language=lang,
                query_text=template.format(c=competitor, dim=dim),
            ))
    return out


def _generic(lang: str) -> str:
    return "{c} {dim}" if lang == "en" else "{c} {dim} 介绍"
