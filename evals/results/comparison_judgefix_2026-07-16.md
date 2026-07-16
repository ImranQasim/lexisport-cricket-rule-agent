# Comparison: citecheck vs. judgefix

Baseline is frozen as the comparison point. Both runs use the same golden set, N-run protocol, generator/judge/prompts -- the only variable is retrieval mode. Deltas are B minus A (positive = hybrid better) unless noted.

## Aggregate

| metric | citecheck | judgefix | delta |
|---|---|---|---|
| answer behavior_match | 28/31 (90.3%) | 29/31 (93.5%) | +3.2pp |
| web_answer behavior_match | 1/6 (16.7%) | 1/6 (16.7%) | +0.0pp |
| honest_fallback behavior_match | 3/7 (42.9%) | 3/7 (42.9%) | +0.0pp |
| flag_acceptable behavior_match | 7/22 (31.8%) | 6/22 (27.3%) | -4.5pp |
| overall behavior_match | 39/66 (59.1%) | 39/66 (59.1%) | +0.0pp |
| faithfulness (answer rows) | 0.747 | 0.721 | -0.026 |
| context_precision | 0.719 | 0.732 | +0.013 |
| context_recall | 0.822 | 0.79 | -0.032 |
| answer_relevancy | 0.597 | 0.669 | +0.072 |
| needs_human_review rate | 30/66 (45.5%) | 19/66 (28.8%) | -16.7pp |
| judge PASS rate | 36/66 (54.5%) | 47/66 (71.2%) | +16.7pp |
| citation check FAIL rate (mechanical layer) | 4/66 (6.1%) | 3/66 (4.5%) | -1.6pp |
| retrieval-miss count (search_rules_tool called, empty result) | 0 [] | 0 [] | -- |
| latency p50 / p95 (whole turn) | 10.93s / 18.4s | 10.15s / 23.94s | -- |
| retrieval-only latency mean (search_rules() call time) | 1.607s | 1.704s | +0.097 |

## Per category

| category | citecheck behavior_match | judgefix behavior_match | delta | citecheck faithfulness | judgefix faithfulness | delta |
|---|---|---|---|---|---|---|
| absence_claim | 2/5 (40.0%) | 2/5 (40.0%) | +0.0pp | None | None | n/a |
| ambiguous_phrasing | 5/10 (50.0%) | 4/10 (40.0%) | -10.0pp | 0.167 | 0.2 | +0.033 |
| cross_grade | 4/5 (80.0%) | 5/5 (100.0%) | +20.0pp | 1.0 | 0.85 | -0.15 |
| direct_rule_lookup | 16/18 (88.9%) | 17/18 (94.4%) | +5.5pp | 0.752 | 0.794 | +0.042 |
| formula_arithmetic | 7/7 (100.0%) | 7/7 (100.0%) | +0.0pp | 0.653 | 0.583 | -0.07 |
| general_knowledge | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp | None | None | n/a |
| table_lookup | 3/13 (23.1%) | 2/13 (15.4%) | -7.7pp | 0.714 | 0.656 | -0.058 |
| web_routing | 2/4 (50.0%) | 2/4 (50.0%) | +0.0pp | None | None | n/a |

## Named subgroups

| subgroup | citecheck behavior_match | judgefix behavior_match | delta |
|---|---|---|---|
| production_miss | 2/7 (28.6%) | 2/7 (28.6%) | +0.0pp |
| tavily_web_answer | 1/6 (16.7%) | 1/6 (16.7%) | +0.0pp |
| general_knowledge_f3_contradiction | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp |
| ragas_synthetic | 6/6 (100.0%) | 6/6 (100.0%) | +0.0pp |

## Citation check (judgefix)

Catches attributed to whichever check actually caused the flag -- mechanical_catch means the citation-provenance check itself FAILed (the judge may not have even run that pass, see route_after_citation_check); judge_only_catch means the citation check passed but the LLM judge still FAILed the row on semantic grounds.

- mechanical_catch: 3/66
- judge_only_catch: 16/66

False fires (citecheck-clean rows the mechanical check itself newly flags under judgefix):

- eval-026
- eval-041

## Regressions (citecheck-clean rows that got worse under judgefix)

- **eval-006** (absence_claim): needs_human_review False -> True, faithfulness None -> None
- **eval-012** (direct_rule_lookup): needs_human_review False -> True, faithfulness 0.5 -> 0.6666666666666666
- **eval-019** (table_lookup): needs_human_review False -> False, faithfulness 1.0 -> 0.8571428571428571
- **eval-026** (absence_claim): needs_human_review False -> True, faithfulness None -> None
