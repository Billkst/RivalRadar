import json

from rivalradar.schema.doubao_schema import to_doubao_schema
from rivalradar.schema.models import CompetitorProfile, EvidenceRef


def test_evidence_ref_schema_has_properties():
    schema = to_doubao_schema(EvidenceRef)
    assert schema["type"] == "object"
    assert "evidence_id" in schema["properties"]
    assert "quote" in schema["properties"]


def test_nested_schema_has_no_refs_or_defs():
    schema = to_doubao_schema(CompetitorProfile)
    blob = json.dumps(schema)
    assert "$ref" not in blob
    assert "$defs" not in schema
    # 嵌套子模型被内联展开:features 的 item 仍带 evidence_refs 结构
    features = schema["properties"]["features"]
    assert features["type"] == "array"
    item_props = features["items"]["properties"]
    assert "parent_id" in item_props
    assert "evidence_refs" in item_props
