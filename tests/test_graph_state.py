from rivalradar.graph.state import ResearchState, merge_evidence


def _e(eid):
    return {"id": eid, "competitor": "Notion", "dimension": "pricing", "content": "c",
            "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}


def test_merge_evidence_accumulates_new_ids():
    merged = merge_evidence([_e("a")], [_e("b")])
    assert [e["id"] for e in merged] == ["a", "b"]


def test_merge_evidence_dedups_same_id():
    # 同 id(同源重采)被丢弃 → 不增加(spec §8 不死磕)
    merged = merge_evidence([_e("a")], [_e("a"), _e("c")])
    assert [e["id"] for e in merged] == ["a", "c"]


def test_merge_evidence_keeps_left_on_conflict():
    left = [{"id": "a", "content": "first", "competitor": "Notion", "dimension": "pricing",
             "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    right = [{"id": "a", "content": "second", "competitor": "Notion", "dimension": "pricing",
              "source_url": "u", "source_title": "t", "language": "en", "fetched_at": "t0"}]
    merged = merge_evidence(left, right)
    assert len(merged) == 1 and merged[0]["content"] == "first"  # 累加不覆盖


def test_research_state_is_typeddict_with_reducer():
    # evidence 字段带 reducer 注解(Annotated),其余字段存在
    ann = ResearchState.__annotations__
    assert "evidence" in ann and "analysis" in ann and "qc_result" in ann
    assert "retry_count" in ann and "report" in ann
