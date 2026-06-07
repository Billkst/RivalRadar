from rivalradar.api.schemas import (
    SSEQueryData, SSEQueryHitData, SSESourceData, SSEEvidenceDeltaData,
)


def test_sse_query_schema():
    d = SSEQueryData(competitor="飞书", dimension="pricing",
                     query_text="飞书 价格", language="zh", round=0, ts="t")
    assert d.query_text == "飞书 价格" and d.round == 0


def test_sse_source_and_delta_schema():
    s = SSESourceData(evidence_id="ev_1", competitor="飞书", dimension="pricing",
                      source_title="T", source_url="https://x", fetched_at="2026-06-01T00:00:00Z",
                      language="zh", round=0, ts="t")
    assert s.evidence_id == "ev_1" and s.fetched_at == "2026-06-01T00:00:00Z"
    e = SSEEvidenceDeltaData(round=1, added_count=3, total_count=12,
                             new_evidence_ids=["ev_1"], ts="t")
    assert e.added_count == 3 and e.new_evidence_ids == ["ev_1"]
    SSEQueryHitData(query_text="飞书 价格", hit_count=3, round=0, ts="t")


def test_sse_cell_row_schema():
    from rivalradar.api.schemas import SSECellRowData
    d = SSECellRowData(dimension="pricing", status="ok", cells=[
        {"competitor": "Notion", "value_type": "enum", "value": "v",
         "evidence_refs": [{"evidence_id": "ev_1", "quote": "q"}]}], ts="t")
    assert d.dimension == "pricing" and d.status == "ok" and d.cells[0].competitor == "Notion"
