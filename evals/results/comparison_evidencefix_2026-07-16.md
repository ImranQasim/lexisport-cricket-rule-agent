# Comparison: citecheck vs. evidencefix

Baseline is frozen as the comparison point. Both runs use the same golden set, N-run protocol, generator/judge/prompts -- the only variable is retrieval mode. Deltas are B minus A (positive = hybrid better) unless noted.

## Aggregate

| metric | citecheck | evidencefix | delta |
|---|---|---|---|
| answer behavior_match | 28/31 (90.3%) | 29/31 (93.5%) | +3.2pp |
| web_answer behavior_match | 1/6 (16.7%) | 2/6 (33.3%) | +16.6pp |
| honest_fallback behavior_match | 3/7 (42.9%) | 2/7 (28.6%) | -14.3pp |
| flag_acceptable behavior_match | 7/22 (31.8%) | 7/22 (31.8%) | +0.0pp |
| overall behavior_match | 39/66 (59.1%) | 40/66 (60.6%) | +1.5pp |
| faithfulness (answer rows) | 0.747 | 0.73 | -0.017 |
| context_precision | 0.719 | 0.733 | +0.014 |
| context_recall | 0.822 | 0.801 | -0.021 |
| answer_relevancy | 0.597 | 0.705 | +0.108 |
| needs_human_review rate | 30/66 (45.5%) | 23/66 (34.8%) | -10.7pp |
| judge PASS rate | 36/66 (54.5%) | 43/66 (65.2%) | +10.7pp |
| citation check FAIL rate (mechanical layer) | 4/66 (6.1%) | 5/66 (7.6%) | +1.5pp |
| retrieval-miss count (search_rules_tool called, empty result) | 0 [] | 0 [] | -- |
| latency p50 / p95 (whole turn) | 10.93s / 18.4s | 11.0s / 21.74s | -- |
| retrieval-only latency mean (search_rules() call time) | 1.607s | 1.373s | -0.234 |

## Per category

| category | citecheck behavior_match | evidencefix behavior_match | delta | citecheck faithfulness | evidencefix faithfulness | delta |
|---|---|---|---|---|---|---|
| absence_claim | 2/5 (40.0%) | 1/5 (20.0%) | -20.0pp | None | None | n/a |
| ambiguous_phrasing | 5/10 (50.0%) | 5/10 (50.0%) | +0.0pp | 0.167 | 0.222 | +0.055 |
| cross_grade | 4/5 (80.0%) | 4/5 (80.0%) | +0.0pp | 1.0 | 0.9 | -0.1 |
| direct_rule_lookup | 16/18 (88.9%) | 18/18 (100.0%) | +11.1pp | 0.752 | 0.782 | +0.03 |
| formula_arithmetic | 7/7 (100.0%) | 6/7 (85.7%) | -14.3pp | 0.653 | 0.59 | -0.063 |
| general_knowledge | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp | None | None | n/a |
| table_lookup | 3/13 (23.1%) | 3/13 (23.1%) | +0.0pp | 0.714 | 0.685 | -0.029 |
| web_routing | 2/4 (50.0%) | 3/4 (75.0%) | +25.0pp | None | None | n/a |

## Named subgroups

| subgroup | citecheck behavior_match | evidencefix behavior_match | delta |
|---|---|---|---|
| production_miss | 2/7 (28.6%) | 2/7 (28.6%) | +0.0pp |
| tavily_web_answer | 1/6 (16.7%) | 2/6 (33.3%) | +16.6pp |
| general_knowledge_f3_contradiction | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp |
| ragas_synthetic | 6/6 (100.0%) | 6/6 (100.0%) | +0.0pp |

## Citation check (evidencefix)

Catches attributed to whichever check actually caused the flag -- mechanical_catch means the citation-provenance check itself FAILed (the judge may not have even run that pass, see route_after_citation_check); judge_only_catch means the citation check passed but the LLM judge still FAILed the row on semantic grounds.

- mechanical_catch: 5/66
- judge_only_catch: 18/66

False fires (citecheck-clean rows the mechanical check itself newly flags under evidencefix):

None found (comparing run_index 0 for every row).

## Regressions (citecheck-clean rows that got worse under evidencefix)

- **eval-001** (formula_arithmetic): needs_human_review False -> True, faithfulness 0.5 -> 1.0
- **eval-019** (table_lookup): needs_human_review False -> True, faithfulness 1.0 -> 0.6
- **eval-026** (absence_claim): needs_human_review False -> False, faithfulness None -> None
- **eval-039** (cross_grade): needs_human_review False -> True, faithfulness 1.0 -> 1.0
