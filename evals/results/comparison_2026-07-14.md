# Comparison: baseline vs. hybrid

Baseline is frozen as the comparison point. Both runs use the same golden set, N-run protocol, generator/judge/prompts -- the only variable is retrieval mode. Deltas are B minus A (positive = hybrid better) unless noted.

## Aggregate

| metric | baseline | hybrid | delta |
|---|---|---|---|
| answer behavior_match | 29/31 (93.5%) | 28/31 (90.3%) | -3.2pp |
| web_answer behavior_match | 1/6 (16.7%) | 2/6 (33.3%) | +16.6pp |
| honest_fallback behavior_match | 3/7 (42.9%) | 2/7 (28.6%) | -14.3pp |
| flag_acceptable behavior_match | 7/22 (31.8%) | 6/22 (27.3%) | -4.5pp |
| overall behavior_match | 40/66 (60.6%) | 38/66 (57.6%) | -3.0pp |
| faithfulness (answer rows) | 0.749 | 0.763 | +0.014 |
| context_precision | 0.708 | 0.656 | -0.052 |
| context_recall | 0.797 | 0.777 | -0.02 |
| answer_relevancy | 0.655 | 0.63 | -0.025 |
| needs_human_review rate | 22/66 (33.3%) | 26/66 (39.4%) | +6.1pp |
| judge PASS rate | 44/66 (66.7%) | 40/66 (60.6%) | -6.1pp |
| retrieval-miss count (search_rules_tool called, empty result) | 0 [] | 0 [] | -- |
| latency p50 / p95 (whole turn) | 8.45s / 20.06s | 9.46s / 31.8s | -- |
| retrieval-only latency mean (search_rules() call time) | n/a (instrumentation added after this run) | 1.428s | n/a |

## Per category

| category | baseline behavior_match | hybrid behavior_match | delta | baseline faithfulness | hybrid faithfulness | delta |
|---|---|---|---|---|---|---|
| absence_claim | 2/5 (40.0%) | 2/5 (40.0%) | +0.0pp | None | None | n/a |
| ambiguous_phrasing | 4/10 (40.0%) | 4/10 (40.0%) | +0.0pp | 0.769 | 0.286 | -0.483 |
| cross_grade | 4/5 (80.0%) | 4/5 (80.0%) | +0.0pp | 0.777 | 0.867 | +0.09 |
| direct_rule_lookup | 17/18 (94.4%) | 16/18 (88.9%) | -5.5pp | 0.821 | 0.834 | +0.013 |
| formula_arithmetic | 7/7 (100.0%) | 7/7 (100.0%) | +0.0pp | 0.703 | 0.604 | -0.099 |
| general_knowledge | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp | None | None | n/a |
| table_lookup | 4/13 (30.8%) | 3/13 (23.1%) | -7.7pp | 0.47 | 0.738 | +0.268 |
| web_routing | 2/4 (50.0%) | 2/4 (50.0%) | +0.0pp | None | None | n/a |

## Named subgroups

| subgroup | baseline behavior_match | hybrid behavior_match | delta |
|---|---|---|---|
| production_miss | 3/7 (42.9%) | 2/7 (28.6%) | -14.3pp |
| tavily_web_answer | 1/6 (16.7%) | 2/6 (33.3%) | +16.6pp |
| general_knowledge_f3_contradiction | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp |
| ragas_synthetic | 6/6 (100.0%) | 6/6 (100.0%) | +0.0pp |

## Regressions (baseline-clean rows that got worse under hybrid)

- **eval-001** (formula_arithmetic): needs_human_review False -> True, faithfulness 0.8333333333333334 -> 0.875
- **eval-006** (absence_claim): needs_human_review False -> True, faithfulness None -> None
- **eval-008** (direct_rule_lookup): needs_human_review False -> True, faithfulness 0.6666666666666666 -> 1.0
- **eval-016** (direct_rule_lookup): needs_human_review False -> True, faithfulness 0.8181818181818182 -> 1.0
- **eval-021** (formula_arithmetic): needs_human_review False -> True, faithfulness 1.0 -> None
- **eval-023** (formula_arithmetic): needs_human_review False -> True, faithfulness 0.3333333333333333 -> 0.0
- **eval-026** (absence_claim): needs_human_review False -> False, faithfulness None -> None
- **eval-032** (web_routing): needs_human_review False -> False, faithfulness None -> None
- **eval-040** (cross_grade): needs_human_review False -> True, faithfulness 1.0 -> 1.0
- **eval-041** (direct_rule_lookup): needs_human_review False -> False, faithfulness 0.8 -> 0.7777777777777778
- **eval-047** (direct_rule_lookup): needs_human_review False -> True, faithfulness None -> None
