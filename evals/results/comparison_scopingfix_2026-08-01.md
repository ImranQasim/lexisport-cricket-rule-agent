# Comparison: prejudgeswap vs. scopingfix

Baseline is frozen as the comparison point. Both runs use the same golden set, N-run protocol, generator/judge/prompts -- the only variable is retrieval mode. Deltas are B minus A (positive = hybrid better) unless noted.

## Aggregate

| metric | prejudgeswap | scopingfix | delta |
|---|---|---|---|
| answer behavior_match | 29/31 (93.5%) | 28/31 (90.3%) | -3.2pp |
| web_answer behavior_match | 1/6 (16.7%) | 1/6 (16.7%) | +0.0pp |
| honest_fallback behavior_match | 4/7 (57.1%) | 2/7 (28.6%) | -28.5pp |
| flag_acceptable behavior_match | 8/22 (36.4%) | 10/22 (45.5%) | +9.1pp |
| overall behavior_match | 42/66 (63.6%) | 41/66 (62.1%) | -1.5pp |
| faithfulness (answer rows) | 0.718 | 0.735 | +0.017 |
| context_precision | 0.708 | 0.78 | +0.072 |
| context_recall | 0.812 | 0.847 | +0.035 |
| answer_relevancy | 0.708 | 0.671 | -0.037 |
| needs_human_review rate | 21/66 (31.8%) | 25/66 (37.9%) | +6.1pp |
| judge PASS rate | 45/66 (68.2%) | 41/66 (62.1%) | -6.1pp |
| citation check FAIL rate (mechanical layer) | 7/66 (10.6%) | 8/66 (12.1%) | +1.5pp |
| retrieval-miss count (search_rules_tool called, empty result) | 0 [] | 0 [] | -- |
| latency p50 / p95 (whole turn) | 8.66s / 15.93s | 9.38s / 19.47s | -- |
| retrieval-only latency mean (search_rules() call time) | 1.403s | 1.227s | -0.176 |

## Per category

| category | prejudgeswap behavior_match | scopingfix behavior_match | delta | prejudgeswap faithfulness | scopingfix faithfulness | delta |
|---|---|---|---|---|---|---|
| absence_claim | 3/5 (60.0%) | 1/5 (20.0%) | -40.0pp | None | None | n/a |
| ambiguous_phrasing | 4/10 (40.0%) | 5/10 (50.0%) | +10.0pp | 0.083 | 0.5 | +0.417 |
| cross_grade | 4/5 (80.0%) | 4/5 (80.0%) | +0.0pp | 0.792 | 0.871 | +0.079 |
| direct_rule_lookup | 16/18 (88.9%) | 17/18 (94.4%) | +5.5pp | 0.84 | 0.847 | +0.007 |
| formula_arithmetic | 7/7 (100.0%) | 7/7 (100.0%) | +0.0pp | 0.629 | 0.537 | -0.092 |
| general_knowledge | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp | None | None | n/a |
| table_lookup | 6/13 (46.2%) | 5/13 (38.5%) | -7.7pp | 0.444 | 0.528 | +0.084 |
| web_routing | 2/4 (50.0%) | 2/4 (50.0%) | +0.0pp | None | None | n/a |

## Named subgroups

| subgroup | prejudgeswap behavior_match | scopingfix behavior_match | delta |
|---|---|---|---|
| production_miss | 2/7 (28.6%) | 2/7 (28.6%) | +0.0pp |
| tavily_web_answer | 1/6 (16.7%) | 1/6 (16.7%) | +0.0pp |
| general_knowledge_f3_contradiction | 0/4 (0.0%) | 0/4 (0.0%) | +0.0pp |
| ragas_synthetic | 5/6 (83.3%) | 6/6 (100.0%) | +16.7pp |

## Citation check (scopingfix)

Catches attributed to whichever check actually caused the flag -- mechanical_catch means the citation-provenance check itself FAILed (the judge may not have even run that pass, see route_after_citation_check); judge_only_catch means the citation check passed but the LLM judge still FAILed the row on semantic grounds.

- mechanical_catch: 8/66
- judge_only_catch: 17/66

False fires (prejudgeswap-clean rows the mechanical check itself newly flags under scopingfix):

- eval-015
- eval-041
- eval-042
- eval-046
- eval-050

## Regressions (prejudgeswap-clean rows that got worse under scopingfix)

- **eval-003** (absence_claim): needs_human_review False -> False, faithfulness None -> None
- **eval-004** (direct_rule_lookup): needs_human_review False -> True, faithfulness 0.5 -> 0.8888888888888888
- **eval-005** (direct_rule_lookup): needs_human_review False -> True, faithfulness 0.75 -> 0.7
- **eval-010** (web_routing): needs_human_review False -> True, faithfulness None -> None
- **eval-023** (formula_arithmetic): needs_human_review False -> True, faithfulness 0.3333333333333333 -> 0.5
- **eval-035** (ambiguous_phrasing): needs_human_review False -> True, faithfulness None -> None
- **eval-039** (cross_grade): needs_human_review False -> True, faithfulness 1.0 -> 1.0
- **eval-041** (direct_rule_lookup): needs_human_review False -> True, faithfulness 1.0 -> 0.75
- **eval-042** (direct_rule_lookup): needs_human_review False -> True, faithfulness 1.0 -> 0.9333333333333333
- **eval-046** (direct_rule_lookup): needs_human_review False -> True, faithfulness 1.0 -> 1.0
- **eval-050** (ambiguous_phrasing): needs_human_review False -> True, faithfulness 0.08333333333333333 -> 0.5
