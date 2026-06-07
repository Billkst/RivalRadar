from rivalradar.graph.nodes import _collect_round


def test_collect_round_first_pass_is_zero():
    # 首轮:无 qc_result → round 0
    assert _collect_round({"qc_result": None, "retry_count": 0}) == 0
    assert _collect_round({"retry_count": 0}) == 0


def test_collect_round_retry_derives_from_qc_presence():
    # 第一次 retry collect:qc_result 已存在但 retry_count 仍 0(qc 节点首轮不 +1)→ round 1
    assert _collect_round({"qc_result": {"verdict": "retry_collect"}, "retry_count": 0}) == 1
    # 第二次 retry:retry_count=1 → round 2
    assert _collect_round({"qc_result": {"verdict": "retry_collect"}, "retry_count": 1}) == 2
