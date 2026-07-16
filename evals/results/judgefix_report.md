# Baseline Evaluation Report -- 2026-07-16

Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.

## Run metadata

- **change**: judge_node evidence-gathering fix (_gather_turn_evidence) + verdict normalization (problem-free FAIL -> PASS)
- **comparison_anchor**: citecheck_2026-07-15
- **compiled_at**: 2026-07-15T22:49:07.623126+00:00

## Coverage

- Golden set rows: 50
- Rows with at least one result: 50
- Total generation runs (including N-reruns): 66
- Missing ids: none
- Generation errors: 0 (none)

## Aggregate metrics

- **answer** rows (n=31): faithfulness=0.721, context_precision=0.732, context_recall=0.79, answer_relevancy=0.669, behavior_match=29/31 (94%)
- **web_answer** rows (n=6): answer_relevancy=0.105, behavior_match=1/6 (17%)
- **honest_fallback** rows (n=7): behavior_match=3/7 (43%), no_invented_citations=2/7 (29%)
- **flag_acceptable** rows (n=22): behavior_match=6/22 (27%)
- needs_human_review rate (all rows): 19/66 (29%)
- judge PASS rate (all rows): 47/66 (71%)

## Judge vs. Ragas agreement

Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n=28), where both our judge's structured verdict and a Ragas faithfulness score exist.
- Agreement rate: 15/28 (54%)
- Confusion matrix: {'judge_pass_ragas_pass': 11, 'judge_pass_ragas_fail': 11, 'judge_fail_ragas_pass': 2, 'judge_fail_ragas_fail': 4}

## Per category

| category | n | behavior_match | faithfulness_mean | needs_human_review |
|---|---|---|---|---|
| absence_claim | 5 | 2/5 (40%) | None | 2/5 (40%) |
| ambiguous_phrasing | 10 | 4/10 (40%) | 0.2 | 1/10 (10%) |
| cross_grade | 5 | 5/5 (100%) | 0.85 | 2/5 (40%) |
| direct_rule_lookup | 18 | 17/18 (94%) | 0.794 | 2/18 (11%) |
| formula_arithmetic | 7 | 7/7 (100%) | 0.583 | 3/7 (43%) |
| general_knowledge | 4 | 0/4 (0%) | None | 0/4 (0%) |
| table_lookup | 13 | 2/13 (15%) | 0.656 | 9/13 (69%) |
| web_routing | 4 | 2/4 (50%) | None | 0/4 (0%) |

## Named subgroups

### production_miss (n=7)
- ids: ['eval-014', 'eval-015', 'eval-016']
- behavior_match: 2/7 (29%)
- faithfulness_mean: 0.804

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
- faithfulness_mean: 0.806

## N-run outcome distributions (arithmetic-nondeterminism + grade-ambiguity rows)

### eval-015 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=True, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None
- run 3: behavior_match=False, needs_human_review=True, error=None
- run 4: behavior_match=False, needs_human_review=False, error=None

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
- run 0: behavior_match=True, needs_human_review=True, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-035 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-047 -- direct_rule_lookup (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

## Latency

- p50: 10.15s, p95: 23.94s, mean: 12.16s, max: 28.47s

## Cost

- Agent execution (measured, gpt-4o-mini pricing): $0.1141 (653942 in / 26696 out tokens)
- Ragas + rubric-classifier scoring (measured via httpx tap): $0.1352 (543 calls, 711967 in / 47314 out tokens)
- **Total: $0.2493**

## 10 worst rows

Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge (a silent failure -- reached the user with no review banner) ranks above a row the judge correctly caught, even if the caught row looks more severe by needs_human_review alone.

- **eval-042** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it)
- **eval-022** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.17
- **eval-050** (run 0, ambiguous_phrasing): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.20
- **eval-008** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.33
- **eval-045** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.42
- **eval-004** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.50
- **eval-020** (run 0, table_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-039** (run 0, cross_grade): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-001** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.75
- **eval-014** (run 0, cross_grade): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.75
