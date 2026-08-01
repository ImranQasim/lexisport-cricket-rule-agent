# Baseline Evaluation Report -- 2026-07-30

Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.

## Run metadata

- **compiled_at**: 2026-07-30T04:18:40.145799+00:00

## Coverage

- Golden set rows: 50
- Rows with at least one result: 50
- Total generation runs (including N-reruns): 66
- Missing ids: none
- Generation errors: 0 (none)

## Aggregate metrics

- **answer** rows (n=31): faithfulness=0.758, context_precision=0.788, context_recall=0.783, answer_relevancy=0.692, behavior_match=29/31 (94%)
- **web_answer** rows (n=6): answer_relevancy=0.104, behavior_match=2/6 (33%)
- **honest_fallback** rows (n=7): behavior_match=3/7 (43%), no_invented_citations=5/7 (71%)
- **flag_acceptable** rows (n=22): behavior_match=10/22 (45%)
- needs_human_review rate (all rows): 7/66 (11%)
- judge PASS rate (all rows): 59/66 (89%)

## Judge vs. Ragas agreement

Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n=26), where both our judge's structured verdict and a Ragas faithfulness score exist.
- Agreement rate: 15/26 (58%)
- Confusion matrix: {'judge_pass_ragas_pass': 14, 'judge_pass_ragas_fail': 10, 'judge_fail_ragas_pass': 1, 'judge_fail_ragas_fail': 1}

## Per category

| category | n | behavior_match | faithfulness_mean | needs_human_review |
|---|---|---|---|---|
| absence_claim | 5 | 2/5 (40%) | None | 1/5 (20%) |
| ambiguous_phrasing | 10 | 6/10 (60%) | 0.222 | 1/10 (10%) |
| cross_grade | 5 | 4/5 (80%) | 0.917 | 1/5 (20%) |
| direct_rule_lookup | 18 | 17/18 (94%) | 0.841 | 2/18 (11%) |
| formula_arithmetic | 7 | 7/7 (100%) | 0.607 | 1/7 (14%) |
| general_knowledge | 4 | 0/4 (0%) | None | 0/4 (0%) |
| table_lookup | 13 | 5/13 (38%) | 0.667 | 1/13 (8%) |
| web_routing | 4 | 3/4 (75%) | None | 0/4 (0%) |

## Named subgroups

### production_miss (n=7)
- ids: ['eval-014', 'eval-015', 'eval-016']
- behavior_match: 2/7 (29%)
- faithfulness_mean: 0.775

### tavily_web_answer (n=6)
- ids: ['eval-010', 'eval-011', 'eval-028', 'eval-029', 'eval-030', 'eval-031']
- behavior_match: 2/6 (33%)
- faithfulness_mean: None

### general_knowledge_f3_contradiction (n=4)
- ids: ['eval-028', 'eval-029', 'eval-030', 'eval-031']
- behavior_match: 0/4 (0%)
- faithfulness_mean: None
- **Pre-declared expected failure**: the golden set (corrected 2026-07-13) expects `web_answer` for these 4 rows per CLAUDE.md's Tavily-scope architecture decision, but the deployed `AGENT_SYSTEM_PROMPT`'s F3 paragraph implements `honest_fallback` instead (findings-log #19, confirmed still unresolved at this run's precondition check). Behavior-match failures here are the known, already-diagnosed spec contradiction -- not a new finding.

### ragas_synthetic (n=6)
- ids: ['eval-045', 'eval-046', 'eval-047', 'eval-048']
- behavior_match: 6/6 (100%)
- faithfulness_mean: 1.0

## N-run outcome distributions (arithmetic-nondeterminism + grade-ambiguity rows)

### eval-015 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None
- run 3: behavior_match=False, needs_human_review=False, error=None
- run 4: behavior_match=False, needs_human_review=False, error=None

### eval-018 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None
- run 3: behavior_match=True, needs_human_review=False, error=None
- run 4: behavior_match=False, needs_human_review=False, error=None

### eval-033 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-034 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-035 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-047 -- direct_rule_lookup (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

## Latency

- p50: 6.19s, p95: 14.75s, mean: 7.51s, max: 16.1s

## Cost

- Agent execution (measured, gpt-4o-mini pricing): $0.1051 (609423 in / 22788 out tokens)
- Ragas + rubric-classifier scoring (measured via httpx tap): $0.1131 (476 calls, 583377 in / 42656 out tokens)
- **Total: $0.2182**

## 10 worst rows

Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge (a silent failure -- reached the user with no review banner) ranks above a row the judge correctly caught, even if the caught row looks more severe by needs_human_review alone.

- **eval-013** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); behavior_match=False (expected answer, content_label=honest_fallback)
- **eval-046** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it)
- **eval-017** (run 0, table_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.00
- **eval-001** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.20
- **eval-022** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.33
- **eval-012** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.43
- **eval-021** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.43
- **eval-023** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.43
- **eval-008** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-004** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.71
