import pytest

from rivalradar.schema.feature_tree import assemble_tree
from rivalradar.schema.models import FeatureItem


def _item(id_, parent=None):
    return FeatureItem(id=id_, name=id_, description="", category="core_workflows", parent_id=parent)


def test_assemble_nests_children_under_parents():
    items = [_item("root"), _item("child", parent="root"), _item("root2")]
    tree = assemble_tree(items)
    assert [n["item"].id for n in tree] == ["root", "root2"]
    assert tree[0]["children"][0]["item"].id == "child"
    assert tree[0]["children"][0]["children"] == []


def test_orphan_parent_id_becomes_root():
    items = [_item("a", parent="does-not-exist")]
    tree = assemble_tree(items)
    assert [n["item"].id for n in tree] == ["a"]


def test_cycle_raises_value_error():
    items = [_item("a", parent="b"), _item("b", parent="a")]
    with pytest.raises(ValueError):
        assemble_tree(items)
