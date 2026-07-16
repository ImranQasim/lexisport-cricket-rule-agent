# Baseline Evaluation Report -- 2026-07-15

Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.

## Run metadata

- **compiled_at**: 2026-07-15T00:42:06.802925+00:00

## Coverage

- Golden set rows: 50
- Rows with at least one result: 50
- Total generation runs (including N-reruns): 66
- Missing ids: none
- Generation errors: 0 (none)

## Aggregate metrics

- **answer** rows (n=31): faithfulness=0.747, context_precision=0.719, context_recall=0.822, answer_relevancy=0.597, behavior_match=28/31 (90%)
- **web_answer** rows (n=6): answer_relevancy=0.08, behavior_match=1/6 (17%)
- **honest_fallback** rows (n=7): behavior_match=3/7 (43%), no_invented_citations=4/7 (57%)
- **flag_acceptable** rows (n=22): behavior_match=7/22 (32%)
- needs_human_review rate (all rows): 30/66 (45%)
- judge PASS rate (all rows): 36/66 (55%)

## Judge vs. Ragas agreement

Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n=28), where both our judge's structured verdict and a Ragas faithfulness score exist.
- Agreement rate: 15/28 (54%)
- Confusion matrix: {'judge_pass_ragas_pass': 10, 'judge_pass_ragas_fail': 7, 'judge_fail_ragas_pass': 6, 'judge_fail_ragas_fail': 5}

## Per category

| category | n | behavior_match | faithfulness_mean | needs_human_review |
|---|---|---|---|---|
| absence_claim | 5 | 2/5 (40%) | None | 1/5 (20%) |
| ambiguous_phrasing | 10 | 5/10 (50%) | 0.167 | 4/10 (40%) |
| cross_grade | 5 | 4/5 (80%) | 1.0 | 2/5 (40%) |
| direct_rule_lookup | 18 | 16/18 (89%) | 0.752 | 7/18 (39%) |
| formula_arithmetic | 7 | 7/7 (100%) | 0.653 | 5/7 (71%) |
| general_knowledge | 4 | 0/4 (0%) | None | 0/4 (0%) |
| table_lookup | 13 | 3/13 (23%) | 0.714 | 10/13 (77%) |
| web_routing | 4 | 2/4 (50%) | None | 1/4 (25%) |

## Named subgroups

### production_miss (n=7)
- ids: ['eval-014', 'eval-015', 'eval-016']
- behavior_match: 2/7 (29%)
- faithfulness_mean: 0.9

### tavily_web_answer (n=6)
- ids: ['eval-010', 'eval-011', 'eval-028', 'eval-029', 'eval-030', 'eval-031']
- behavior_match: 1/6 (17%)
- faithfulness_mean: None

### general_knowledge_f3_contradiction (n=4)
- ids: ['eval-028', 'eval-029', 'eval-030', 'eval-031']
- behavior_match: 0/4 (0%)
- faithfulness_mean: None
- **Pre-declared expected failure**: the golden set (corrected 2026-07-13) expects `web_answer` for these 4 rows per CLAUDE.md's Tavily-scope architecture decision, but the deployed `AGENT_SYSTEM_PROMPT`'s F3 paragraph implements `honest_fallback` instead (findings-log #19, confirmed still unresolved at this run's precondition check). Behavior-match failures here are the known, already-diagnosed spec contradiction -- not a new finding.

### ragas_synthetic (n=6)
- ids: ['eval-045', 'eval-046', 'eval-047', 'eval-048']
- behavior_match: 6/6 (100%)
- faithfulness_mean: 0.967

## N-run outcome distributions (arithmetic-nondeterminism + grade-ambiguity rows)

### eval-015 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=True, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None
- run 3: behavior_match=False, needs_human_review=True, error=None
- run 4: behavior_match=False, needs_human_review=True, error=None

### eval-018 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=True, error=None
- run 2: behavior_match=False, needs_human_review=True, error=None
- run 3: behavior_match=False, needs_human_review=True, error=None
- run 4: behavior_match=False, needs_human_review=True, error=None

### eval-033 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-034 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=True, needs_human_review=True, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-035 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-047 -- direct_rule_lookup (N=3)
- run 0: behavior_match=True, needs_human_review=True, error=None
- run 1: behavior_match=True, needs_human_review=True, error=None
- run 2: behavior_match=True, needs_human_review=True, error=None

## Latency

- p50: 10.93s, p95: 18.4s, mean: 10.67s, max: 26.79s

## Cost

- Agent execution (measured, gpt-4o-mini pricing): $0.1128 (631460 in / 30145 out tokens)
- Ragas + rubric-classifier scoring (measured via httpx tap): $0.1267 (516 calls, 658590 in / 46451 out tokens)
- **Total: $0.2395**

## 10 worst rows

Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge (a silent failure -- reached the user with no review banner) ranks above a row the judge correctly caught, even if the caught row looks more severe by needs_human_review alone.

- **eval-013** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); behavior_match=False (expected answer, content_label=honest_fallback)
- **eval-041** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); behavior_match=False (expected answer, content_label=honest_fallback); faithfulness=0.25
- **eval-002** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.00
- **eval-001** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.50
- **eval-012** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.50
- **eval-004** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-005** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-008** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.75
- **eval-011** (run 0, web_routing): judge FAIL/flagged: ; behavior_match=False (expected web_answer, content_label=honest_fallback)
- **eval-015** (run 0, table_lookup): judge FAIL/flagged: The arithmetic in the draft answer is incorrect. The claim that ‘for a 13-minute disruption, you would round up to 4 overs lost‘ is misleadi; behavior_match=False (expected flag_acceptable, content_label=None)
