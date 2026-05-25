from __future__ import annotations

from copy import deepcopy
from typing import Any


def to_doubao_schema(model_cls) -> dict[str, Any]:
    """把 Pydantic 模型转成 Doubao json_schema 能稳定消费的形状。

    Pydantic 默认把嵌套子模型抽成 $defs + $ref。我们的 Schema 是扁平的
    (FeatureItem 用 parent_id 表层级,而非自引用),所以非递归,可以安全地
    把所有 $ref 内联展开,送一份自包含、无 $ref/$defs 的 schema(spec §9 / D11)。
    """
    schema = model_cls.model_json_schema()
    defs = schema.get("$defs", {})
    inlined = _inline(schema, defs)
    inlined.pop("$defs", None)
    return inlined


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            return _inline(deepcopy(defs[name]), defs)
        return {k: _inline(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline(x, defs) for x in node]
    return node
