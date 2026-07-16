# RivalRadar Competitive Research

RivalRadar 将用户确认的竞品、对比维度与决策处境转化为可溯源的对比结论和
决策建议。领域原则是宁可明确缺失或剔除，也不以无据结论补齐结果。

## Language

**Seed Product（种子产品）**:
用于发现直接竞品的可选参考产品；实际调研对象仍需由用户另行确认。
_Avoid_: Target competitor, automatically selected competitor

**Candidate Competitor（候选竞品）**:
基于种子产品建议的真实直接竞品；只有经用户确认后才成为调研中的 Competitor。
_Avoid_: Confirmed competitor, generated product, seed product

**Competitor（竞品）**:
用户明确选入同一次调研、作为研究与横向比较对象的真实产品。
_Avoid_: Candidate competitor, seed product, company

**Research Run（调研）**:
一次由用户发起的完整竞品研究，包含确认的竞品、对比维度和决策处境，并产生证据、
分析、质量结论及决策建议。Report 只是调研的一项产物。
_Avoid_: Report, chat session, scan, request

**Analysis Dimension（对比维度）**:
研究和横向比较竞品时采用的受控业务轴。
_Avoid_: Arbitrary free-text category, SWOT category

**Decision Context（决策处境）**:
用户开展调研的目的和具体处境，用于约束最终建议的适用语境。
_Avoid_: Persona, role alone, prompt

**Evidence（证据）**:
关于某个竞品在某个对比维度上的公开信息快照，保留来源、原始内容、语言和获取时间。
_Avoid_: Search result, summary, conclusion, model output

**Evidence Reference（证据引用）**:
把一条结论连接到具体 Evidence 的被引原句，是结论溯源的最小单位。
_Avoid_: URL-only citation, evidence ID without a quote

**Comparison Cell（对比格）**:
某个竞品在一个对比维度上的单项结论，由可比较的值和支撑它的 Evidence References
构成。
_Avoid_: Competitor profile field, free-form paragraph, score

**Support Verdict（证据支持度）**:
对合并证据能否支撑一个 Comparison Cell 或 Decision Recommendation 的三级判断：
supported、partial 或 unsupported。
_Avoid_: Confidence percentage, source quality score, per-quote verdict

**Curation Drop（策展剔除）**:
因缺少有效引用或证据无法支撑而从最终对比或决策中移除的结论。它是正常质量行为，
本身不代表整个调研失败。
_Avoid_: Failed run, hidden error, deleted evidence

**Quality Issue（质检缺口）**:
与竞品和维度关联、可采取后续行动的质量问题，例如缺少证据、结构不完整或覆盖不足。
_Avoid_: Generic error, reviewer comment, curation drop

**Insufficient Evidence（证据不足）**:
在有限补充研究后仍无法从公开资料支撑所需覆盖范围的正式结果。
_Avoid_: System failure, empty result, unsupported completion

**Decision Recommendation（决策建议）**:
基于证据形成的行动或观察，包含立场、理由、适用条件和证据支持度。
_Avoid_: Generic takeaway, unsupported advice, confidence score

**Manual Challenge（人工质疑）**:
用户针对结论或证据记录的只读异议，用于审计；它不会直接修改结论或重新启动调研。
_Avoid_: Correction, override, human-in-the-loop rewrite
