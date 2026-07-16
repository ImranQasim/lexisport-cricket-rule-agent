# Comparison: baseline vs. citecheck

Baseline is frozen as the comparison point. Both runs use the same golden set, N-run protocol, generator/judge/prompts -- the only variable is retrieval mode. Deltas are B minus A (positive = hybrid better) unless noted.

## Aggregate

| metric | baseline | citecheck | delta |
|---|---|---|---|
| answer behavior_match | 29/31 (93.5%) | 28/31 (90.3%) | -3.2pp |
| web_answer behavior_match | 1/6 (16.7%) | 1/6 (16.7%) | +0.0pp |
| honest_fallback behavior_match | 3/7 (42.9%) | 5/7 (71.4%) | +28.5pp |
| flag_acceptable behavior_match | 7/22 (31.8%) | 6/22 (27.3%) | -4.5pp |
| overall behavior_match | 40/66 (60.6%) | 40/66 (60.6%) | +0.0pp |
| faithfulness (answer rows) | 0.749 | 0.773 | +0.024 |
| context_precision | 0.708 | 0.693 | -0.015 |
| context_recall | 0.797 | 0.831 | +0.034 |
| answer_relevancy | 0.655 | 0.639 | -0.016 |
| needs_human_review rate | 22/66 (33.3%) | 30/66 (45.5%) | +12.2pp |
| judge PASS rate | 44/66 (66.7%) | 36/66 (54.5%) | -12.2pp |
| citation check FAIL rate (mechanical layer) | n/a (no mechanical check) | 14/66 (21.2%) | n/a |
| retrieval-miss count (search_rules_tool called, empty result) | 0 [] | 0 [] | -- |
| latency p50 / p95 (whole turn) | 8.45s / 20.06s | 9.92s / 24.43s | -- |
| retrieval-only latency mean (search_rules() call time) | n/a (instrumentation added after this run) | 1.555s | n/a |

## Per category

| category | baseline behavior_match | citecheck behavior_match | delta | baseline faithfulness | citecheck faithfulness | delta |
|---|---|---|---|---|---|---|
| absence_claim | 2/5 (40.0%) | 3/5 (60.0%) | +20.0pp | None | None | n/a |
| ambiguous_phrasing | 4/10 (40.0%) | 4/10 (40.0%) | +0.0pp | 0.769 | 0.2 | -0.569 |
| cross_grade | 4/5 (80.0%) | 4/5 (80.0%) | +0.0pp | 0.777 | 0.925 | +0.148 |
| direct_rule_lookup | 17/18 (94.4%) | 17/18 (94.4%) | +0.0pp | 0.821 | 0.843 | +0.022 |
| formula_arithmetic | 7/7 (100.0%) | 7/7 (100.0%) | +0.0pp | 0.703 | 0.653 | -0.05 |
| general_knowledge | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp | None | None | n/a |
| table_lookup | 4/13 (30.8%) | 2/13 (15.4%) | -15.4pp | 0.47 | 0.667 | +0.197 |
| web_routing | 2/4 (50.0%) | 3/4 (75.0%) | +25.0pp | None | None | n/a |

## Named subgroups

| subgroup | baseline behavior_match | citecheck behavior_match | delta |
|---|---|---|---|
| production_miss | 3/7 (42.9%) | 2/7 (28.6%) | -14.3pp |
| tavily_web_answer | 1/6 (16.7%) | 1/6 (16.7%) | +0.0pp |
| general_knowledge_f3_contradiction | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp |
| ragas_synthetic | 6/6 (100.0%) | 6/6 (100.0%) | +0.0pp |

## Citation check (citecheck)

Catches attributed to whichever check actually caused the flag -- mechanical_catch means the citation-provenance check itself FAILed (the judge may not have even run that pass, see route_after_citation_check); judge_only_catch means the citation check passed but the LLM judge still FAILed the row on semantic grounds.

- mechanical_catch: 14/66
- judge_only_catch: 16/66

False fires (baseline-clean rows the mechanical check itself newly flags under citecheck):

- eval-007
- eval-010
- eval-035
- eval-040
- eval-045
- eval-047
- eval-048

## Regressions (baseline-clean rows that got worse under citecheck)

- **eval-007** (direct_rule_lookup): needs_human_review False -> True, faithfulness 1.0 -> 0.9
- **eval-023** (formula_arithmetic): needs_human_review False -> True, faithfulness 0.3333333333333333 -> 0.4
- **eval-040** (cross_grade): needs_human_review False -> True, faithfulness 1.0 -> 1.0
- **eval-045** (direct_rule_lookup): needs_human_review False -> True, faithfulness 0.6666666666666666 -> 0.7
- **eval-047** (direct_rule_lookup): needs_human_review False -> True, faithfulness None -> None
- **eval-048** (direct_rule_lookup): needs_human_review False -> True, faithfulness 0.8333333333333334 -> 1.0
