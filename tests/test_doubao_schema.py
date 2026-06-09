import json

from rivalradar.schema.doubao_schema import to_doubao_schema
from rivalradar.schema.models import CompetitorProfile, DecisionSet, EvidenceRef


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


def test_decision_set_schema_inlines_nested_decision_and_watch():
    """DecisionSet → function-calling schema:无 $ref/$defs,decisions[].watch /
    evidence_refs 嵌套结构内联展开(Doubao tools 路径要自包含 schema)。"""
    schema = to_doubao_schema(DecisionSet)
    blob = json.dumps(schema)
    assert "$ref" not in blob
    assert "$defs" not in schema
    decisions = schema["properties"]["decisions"]
    assert decisions["type"] == "array"
    dprops = decisions["items"]["properties"]
    assert "stance" in dprops and "action" in dprops and "why" in dprops
    assert "risk_reversibility" in dprops and "risk_cost" in dprops
    assert "evidence_refs" in dprops          # 句级溯源内联
    assert "watch" in dprops                   # Optional[Watch] 也在


def test_comparison_cell_has_support_verdict_default_supported():
    from rivalradar.schema.models import ComparisonCell
    c = ComparisonCell(competitor="Notion", value_type="enum", value="v")
    assert c.support_verdict == "supported"
    c2 = ComparisonCell(competitor="Notion", value_type="enum", value="v", support_verdict="partial")
    assert c2.support_verdict == "partial"


def test_decision_has_support_verdict_default_supported():
    from rivalradar.schema.models import Decision
    d = Decision(stance="建议采用", action="A", horizon="短期", risk_reversibility="可逆",
                 risk_cost="低", why="w")
    assert d.support_verdict == "supported"
