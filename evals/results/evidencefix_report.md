# Baseline Evaluation Report -- 2026-07-16

Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.

## Run metadata

- **change**: judge_node evidence-gathering fix only (_gather_turn_evidence) -- verdict normalization built and evaluated, then dropped before shipping: see docs/findings-log.md finding #40 (eval-047 false negative)
- **comparison_anchor**: citecheck_2026-07-15
- **compiled_at**: 2026-07-16T01:29:48.359161+00:00

## Coverage

- Golden set rows: 50
- Rows with at least one result: 50
- Total generation runs (including N-reruns): 66
- Missing ids: none
- Generation errors: 0 (none)

## Aggregate metrics

- **answer** rows (n=31): faithfulness=0.73, context_precision=0.733, context_recall=0.801, answer_relevancy=0.705, behavior_match=29/31 (94%)
- **web_answer** rows (n=6): answer_relevancy=0.101, behavior_match=2/6 (33%)
- **honest_fallback** rows (n=7): behavior_match=2/7 (29%), no_invented_citations=4/7 (57%)
- **flag_acceptable** rows (n=22): behavior_match=7/22 (32%)
- needs_human_review rate (all rows): 23/66 (35%)
- judge PASS rate (all rows): 43/66 (65%)

## Judge vs. Ragas agreement

Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n=30), where both our judge's structured verdict and a Ragas faithfulness score exist.
- Agreement rate: 16/30 (53%)
- Confusion matrix: {'judge_pass_ragas_pass': 12, 'judge_pass_ragas_fail': 11, 'judge_fail_ragas_pass': 3, 'judge_fail_ragas_fail': 4}

## Per category

| category | n | behavior_match | faithfulness_mean | needs_human_review |
|---|---|---|---|---|
| absence_claim | 5 | 1/5 (20%) | None | 1/5 (20%) |
| ambiguous_phrasing | 10 | 5/10 (50%) | 0.222 | 1/10 (10%) |
| cross_grade | 5 | 4/5 (80%) | 0.9 | 2/5 (40%) |
| direct_rule_lookup | 18 | 18/18 (100%) | 0.782 | 3/18 (17%) |
| formula_arithmetic | 7 | 6/7 (86%) | 0.59 | 3/7 (43%) |
| general_knowledge | 4 | 0/4 (0%) | None | 0/4 (0%) |
| table_lookup | 13 | 3/13 (23%) | 0.685 | 12/13 (92%) |
| web_routing | 4 | 3/4 (75%) | None | 1/4 (25%) |

## Named subgroups

### production_miss (n=7)
- ids: ['eval-014', 'eval-015', 'eval-016']
- behavior_match: 2/7 (29%)
- faithfulness_mean: 0.9

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
- faithfulness_mean: 0.764

## N-run outcome distributions (arithmetic-nondeterminism + grade-ambiguity rows)

### eval-015 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=True, error=None
- run 2: behavior_match=False, needs_human_review=True, error=None
- run 3: behavior_match=False, needs_human_review=True, error=None
- run 4: behavior_match=False, needs_human_review=True, error=None

### eval-018 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=True, error=None
- run 2: behavior_match=False, needs_human_review=True, error=None
- run 3: behavior_match=False, needs_human_review=True, error=None
- run 4: behavior_match=False, needs_human_review=True, error=None

### eval-033 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-034 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-035 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=True, error=None

### eval-047 -- direct_rule_lookup (N=3)
- run 0: behavior_match=True, needs_human_review=True, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=True, error=None

## Latency

- p50: 11.0s, p95: 21.74s, mean: 11.7s, max: 28.02s

## Cost

- Agent execution (measured, gpt-4o-mini pricing): $0.1213 (696511 in / 27996 out tokens)
- Ragas + rubric-classifier scoring (measured via httpx tap): $0.1357 (541 calls, 720062 in / 46132 out tokens)
- **Total: $0.257**

## 10 worst rows

Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge (a silent failure -- reached the user with no review banner) ranks above a row the judge correctly caught, even if the caught row looks more severe by needs_human_review alone.

- **eval-049** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); behavior_match=False (expected answer, content_label=honest_fallback); faithfulness=0.50
- **eval-022** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.00
- **eval-050** (run 0, ambiguous_phrasing): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.22
- **eval-012** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.29
- **eval-013** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.40
- **eval-004** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.43
- **eval-037** (run 0, cross_grade): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.50
- **eval-045** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.62
- **eval-048** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-005** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.75
