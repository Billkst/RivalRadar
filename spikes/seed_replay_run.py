"""seed 一个完整 done run 到指定 db,供 replay 端到端验证(无 LLM,绕开 Doubao/Clash)。

用法:.venv/bin/python spikes/seed_replay_run.py /tmp/rivalradar_replay.db run_seed01

随后:RIVALRADAR_DB=/tmp/rivalradar_replay.db .venv/bin/python -m uvicorn \
        --factory rivalradar.api.app:create_app --port 8000
再 /browse 深链 http://localhost:3000/run/run_seed01 触发真 GET /stream replay。
spikes/ 不进 pytest(CLAUDE.md 测试纪律)。数据形态同 tests/test_replay_parity.py。
"""
import sys

from rivalradar.schema.models import (
    CompetitorAnalysis, ComparisonRow, ComparisonCell, EvidenceRef, Evidence, QCResult,
)
from rivalradar.storage import repository as repo
from rivalradar.storage.db import connect, init_db

db_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rivalradar_replay.db"
run_id = sys.argv[2] if len(sys.argv) > 2 else "run_seed01"

c = connect(db_path)
init_db(c)
repo.create_run(c, run_id, ["飞书", "钉钉", "企业微信"],
                ["pricing", "core_workflows", "review_sentiment"])

# 真查询词(含 round=1 retry 轮 + 一条 0 命中英文 query)
repo.insert_queries(c, run_id, [
    {"competitor": "飞书", "dimension": "pricing", "language": "zh",
     "query_text": "飞书 定价 套餐 价格", "round": 0, "hit_count": 4},
    {"competitor": "钉钉", "dimension": "pricing", "language": "zh",
     "query_text": "钉钉 专业版 价格 对比", "round": 0, "hit_count": 3},
    {"competitor": "企业微信", "dimension": "review_sentiment", "language": "en",
     "query_text": "WeCom enterprise review english", "round": 0, "hit_count": 0},
    {"competitor": "企业微信", "dimension": "review_sentiment", "language": "zh",
     "query_text": "企业微信 用户评价 优缺点", "round": 1, "hit_count": 2},
])

# 来源卡(真标题/域名/采集日期)
for ev in [
    Evidence(id="ev_1", competitor="飞书", dimension="pricing", content="商业版按人/月计费",
             source_url="https://www.feishu.cn/price", source_title="飞书定价 - 飞书官网",
             language="zh", fetched_at="2026-05-28T10:00:03Z"),
    Evidence(id="ev_2", competitor="钉钉", dimension="pricing", content="专业版年付含审批考勤",
             source_url="https://www.dingtalk.com/pricing", source_title="钉钉专业版对比 - 帮助中心",
             language="zh", fetched_at="2026-05-28T10:00:05Z"),
    Evidence(id="ev_3", competitor="飞书", dimension="review_sentiment", content="协作体验口碑佳",
             source_url="https://36kr.com/feishu-review", source_title="飞书口碑实测 - 36氪",
             language="zh", fetched_at="2026-05-28T10:00:30Z"),
]:
    repo.insert_evidence(c, run_id, ev)

# curated analysis（curate 后只含 supported/partial 保留格;企业微信·review_sentiment 被剔除→不在内）
repo.save_analysis(c, run_id, CompetitorAnalysis(comparison=[
    ComparisonRow(dimension="pricing", cells=[
        ComparisonCell(competitor="飞书", value_type="quote_text", value="商业版按人/月计费",
                       support_verdict="supported",
                       evidence_refs=[EvidenceRef(evidence_id="ev_1", quote="商业版 ¥/人/月")]),
        ComparisonCell(competitor="钉钉", value_type="quote_text", value="专业版年付含审批",
                       support_verdict="partial",
                       evidence_refs=[EvidenceRef(evidence_id="ev_2", quote="专业版 9800/年起")]),
    ]),
    ComparisonRow(dimension="core_workflows", cells=[
        ComparisonCell(competitor="飞书", value_type="quote_text", value="文档/多维表格一体化",
                       support_verdict="supported"),
        ComparisonCell(competitor="企业微信", value_type="quote_text", value="工作台+客户联系打通",
                       support_verdict="supported"),
    ]),
    ComparisonRow(dimension="review_sentiment", cells=[
        ComparisonCell(competitor="飞书", value_type="quote_text", value="协作体验口碑佳",
                       support_verdict="supported",
                       evidence_refs=[EvidenceRef(evidence_id="ev_3", quote="协作体验领先")]),
    ]),
]))

# 策展剔除清单（scope=cell）→ replay 还原 StatusBar 已剔除 1 + 矩阵「—」
repo.replace_curation_drops(c, run_id, "cell", [
    {"competitor": "企业微信", "dimension": "review_sentiment",
     "detail": "引用证据不支撑结论,策展剔除"},
])

# qc_result（让 replay 合成 qc node 注入 retryCount = max(queries.round) = 1）
repo.save_qc_result(c, run_id, QCResult(verdict="pass", issues=[]))

# trace（§11.4 Play + retry_count 推导)。2 个 qc 行 = 2 轮质检 = 自我纠错 1 次
# (retry_count 由 qc trace 行数推:qc_rounds - 1;与 round-1 queries 自洽)。
repo.append_trace(c, run_id, "collect", output_summary="+12", latency_ms=8000)
repo.append_trace(c, run_id, "analyze", output_summary="3 competitors", latency_ms=170000)
repo.append_trace(c, run_id, "qc", output_summary="verdict=retry_collect", latency_ms=18000)
repo.append_trace(c, run_id, "collect", output_summary="+2 broaden", latency_ms=5000)
repo.append_trace(c, run_id, "analyze", output_summary="3 competitors recheck", latency_ms=40000)
repo.append_trace(c, run_id, "qc", output_summary="verdict=pass", latency_ms=20000)

repo.update_run_status(c, run_id, "done")
print(f"seeded {run_id} into {db_path}")
