from __future__ import annotations

from rivalradar.schema.models import FeatureItem


def assemble_tree(items: list[FeatureItem]) -> list[dict]:
    """把扁平 FeatureItem 列表拼成嵌套树。

    返回根节点列表,每个节点为 {"item": FeatureItem, "children": [...]}。
    - parent_id 指向不存在的项 → 视为根(防御 LLM 漏输出父项)。
    - 检测到环 → 抛 ValueError(LLM 可能产出 a->b->a)。
    """
    by_id = {it.id: {"item": it, "children": []} for it in items}
    roots: list[dict] = []
    for it in items:
        node = by_id[it.id]
        parent = by_id.get(it.parent_id) if it.parent_id else None
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)

    _assert_acyclic(by_id)
    return roots


def _assert_acyclic(by_id: dict[str, dict]) -> None:
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node: dict) -> None:
        nid = node["item"].id
        if nid in visiting:
            raise ValueError(f"feature tree has a cycle at {nid!r}")
        if nid in done:
            return
        visiting.add(nid)
        for child in node["children"]:
            walk(child)
        visiting.discard(nid)
        done.add(nid)

    for node in by_id.values():
        walk(node)
