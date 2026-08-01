# Baseline Evaluation Report -- 2026-08-01

Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.

## Run metadata

- **change**: Calculation-tool scoping fix: closure-captured grade_scope on the three overs-reduction tools, checked against a declarative tool->grade coverage map, refusing out-of-scope calls instead of computing (fixes eval-025 wrong-tool computation). rule_chunks was found empty in Supabase before this run (0 rows, unrelated to this change -- a different external pipeline had touched MYCA documents on 2026-07-31) and was restored via a fresh ingestion/run.py pass on the original 5 source PDFs pulled from Supabase Storage, 292 chunks, matching the original corpus size exactly.
- **comparison_anchor**: postjudgeswap_2026-07-30
- **compiled_at**: 2026-08-01T10:08:57.047578+00:00

## Coverage

- Golden set rows: 50
- Rows with at least one result: 50
- Total generation runs (including N-reruns): 66
- Missing ids: none
- Generation errors: 0 (none)

## Aggregate metrics

- **answer** rows (n=31): faithfulness=0.735, context_precision=0.78, context_recall=0.847, answer_relevancy=0.671, behavior_match=28/31 (90%)
- **web_answer** rows (n=6): answer_relevancy=0.09, behavior_match=1/6 (17%)
- **honest_fallback** rows (n=7): behavior_match=2/7 (29%), no_invented_citations=4/7 (57%)
- **flag_acceptable** rows (n=22): behavior_match=10/22 (45%)
- needs_human_review rate (all rows): 25/66 (38%)
- judge PASS rate (all rows): 41/66 (62%)

## Judge vs. Ragas agreement

Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n=24), where both our judge's structured verdict and a Ragas faithfulness score exist.
- Agreement rate: 12/24 (50%)
- Confusion matrix: {'judge_pass_ragas_pass': 9, 'judge_pass_ragas_fail': 8, 'judge_fail_ragas_pass': 4, 'judge_fail_ragas_fail': 3}

## Per category

| category | n | behavior_match | faithfulness_mean | needs_human_review |
|---|---|---|---|---|
| absence_claim | 5 | 1/5 (20%) | None | 1/5 (20%) |
| ambiguous_phrasing | 10 | 5/10 (50%) | 0.5 | 3/10 (30%) |
| cross_grade | 5 | 4/5 (80%) | 0.871 | 3/5 (60%) |
| direct_rule_lookup | 18 | 17/18 (94%) | 0.847 | 6/18 (33%) |
| formula_arithmetic | 7 | 7/7 (100%) | 0.537 | 3/7 (43%) |
| general_knowledge | 4 | 0/4 (0%) | None | 0/4 (0%) |
| table_lookup | 13 | 5/13 (38%) | 0.528 | 8/13 (62%) |
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
- faithfulness_mean: 0.857

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
- run 2: behavior_match=True, needs_human_review=False, error=None
- run 3: behavior_match=False, needs_human_review=True, error=None
- run 4: behavior_match=True, needs_human_review=True, error=None

### eval-033 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-034 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=True, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-035 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-047 -- direct_rule_lookup (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

## Latency

- p50: 9.38s, p95: 19.47s, mean: 10.16s, max: 26.27s

## Cost

- Agent execution (measured, gpt-4o-mini pricing): $0.1374 (811430 in / 26114 out tokens)
- Ragas + rubric-classifier scoring (measured via httpx tap): $0.1233 (513 calls, 646338 in / 43891 out tokens)
- **Total: $0.2607**

## 10 worst rows

Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge (a silent failure -- reached the user with no review banner) ranks above a row the judge correctly caught, even if the caught row looks more severe by needs_human_review alone.

- **eval-013** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); behavior_match=False (expected answer, content_label=honest_fallback)
- **eval-001** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.00
- **eval-017** (run 0, table_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.25
- **eval-019** (run 0, table_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.33
- **eval-022** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.43
- **eval-021** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.50
- **eval-048** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.57
- **eval-012** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-002** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.71
- **eval-050** (run 0, ambiguous_phrasing): judge FAIL/flagged: ; behavior_match=False (expected answer, content_label=honest_fallback); faithfulness=0.50
