# Baseline Evaluation Report -- 2026-07-13

Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.

## Run metadata

- **git_commit**: b44bf3d5c2db8a2ec11120f8e55e4dc20dd2afde
- **agent_and_judge_model**: gpt-4o-mini (via local LiteLLM gateway, gateway/config.yaml, unmodified)
- **ragas_version**: 0.4.3
- **ragas_evaluator_model**: gpt-4o-mini
- **ragas_embedding_model**: text-embedding-3-small
- **n_run_protocol**: N=5 on eval-015/eval-018 (arithmetic nondeterminism); N=3 on eval-033/034/035/047 (grade-ambiguity behavioral variance); N=1 on all other 44 rows
- **execution_path**: local backend.agent.build_graph() in-process, pointed at a locally-run instance of the unmodified gateway/config.yaml LiteLLM proxy and the real Supabase DB (no Render proxy credentials available locally), cross-checked by a 6-row HTTP sanity sample against the live deployed Render API (succeeded with the correct deployed API_KEY).
- **generation_wall_time**: 2026-07-13 23:10:35 to 23:22:55 local (~12m20s)
- **scoring_wall_time**: 2026-07-14 08:56:26 to 11:01:45 local (~2h5m, sequential by design, no concurrency)
- **http_sanity_wall_time**: 2026-07-14, ~2 minutes (6 live calls to the deployed Render API)
- **langsmith_project**: lexisport-baseline-2026-07-13
- **langsmith_session_id**: 6175b6b4-d02a-43f3-a206-f822109b01db
- **langsmith_evidence**: Confirmed via LangSmith runs/query API: every root run in this session carries tags ["baseline","baseline-2026-07-13"] and metadata (golden_set_id, category, run_index, thread_id), plus an auto-captured revision_id=b44bf3d matching this run's git commit.
- **compiled_at**: 2026-07-14T02:25:34.507516+00:00

## Coverage

- Golden set rows: 50
- Rows with at least one result: 50
- Total generation runs (including N-reruns): 66
- Missing ids: none
- Generation errors: 0 (none)

## Aggregate metrics

- **answer** rows (n=31): faithfulness=0.749, context_precision=0.708, context_recall=0.797, answer_relevancy=0.655, behavior_match=29/31 (94%)
- **web_answer** rows (n=6): answer_relevancy=0.13, behavior_match=1/6 (17%)
- **honest_fallback** rows (n=7): behavior_match=3/7 (43%), no_invented_citations=6/7 (86%)
- **flag_acceptable** rows (n=22): behavior_match=7/22 (32%)
- needs_human_review rate (all rows): 22/66 (33%)
- judge PASS rate (all rows): 44/66 (67%)

## Judge vs. Ragas agreement

Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n=30), where both our judge's structured verdict and a Ragas faithfulness score exist.
- Agreement rate: 17/30 (57%)
- Confusion matrix: {'judge_pass_ragas_pass': 13, 'judge_pass_ragas_fail': 10, 'judge_fail_ragas_pass': 3, 'judge_fail_ragas_fail': 4}

## Per category

| category | n | behavior_match | faithfulness_mean | needs_human_review |
|---|---|---|---|---|
| absence_claim | 5 | 2/5 (40%) | None | 1/5 (20%) |
| ambiguous_phrasing | 10 | 4/10 (40%) | 0.769 | 3/10 (30%) |
| cross_grade | 5 | 4/5 (80%) | 0.777 | 2/5 (40%) |
| direct_rule_lookup | 18 | 17/18 (94%) | 0.821 | 2/18 (11%) |
| formula_arithmetic | 7 | 7/7 (100%) | 0.703 | 1/7 (14%) |
| general_knowledge | 4 | 0/4 (0%) | None | 1/4 (25%) |
| table_lookup | 13 | 4/13 (31%) | 0.47 | 11/13 (85%) |
| web_routing | 4 | 2/4 (50%) | None | 1/4 (25%) |

## Named subgroups

### production_miss (n=7)
- ids: ['eval-014', 'eval-015', 'eval-016']
- behavior_match: 3/7 (43%)
- faithfulness_mean: 0.784

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
- faithfulness_mean: 0.833

## N-run outcome distributions (arithmetic-nondeterminism + grade-ambiguity rows)

### eval-015 -- table_lookup (N=5)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
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
- run 0: behavior_match=True, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-035 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=True, error=None

### eval-047 -- direct_rule_lookup (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=True, error=None

## Latency

- p50: 8.45s, p95: 20.06s, mean: 11.18s, max: 31.11s

## Cost

- Agent execution (measured, gpt-4o-mini pricing): $0.1128 (639336 in / 28123 out tokens)
- Ragas + rubric-classifier scoring (measured via httpx tap): $0.1218 (502 calls, 635154 in / 44199 out tokens)
- **Total: $0.2346**

## 10 worst rows

Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge (a silent failure -- reached the user with no review banner) ranks above a row the judge correctly caught, even if the caught row looks more severe by needs_human_review alone.

- **eval-013** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); behavior_match=False (expected answer, content_label=honest_fallback)
- **eval-023** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.33
- **eval-022** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.40
- **eval-004** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.50
- **eval-008** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-045** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-025** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.71
- **eval-005** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.75
- **eval-014** (run 0, cross_grade): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.75
- **eval-024** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.75

## HTTP sanity sample (live Render API vs. local invocation)

Real HTTP calls against the deployed `/api/chat`, one row per category family, diffed against this run's own local-invocation result for the same row. LLM output is stochastic run to run, so this checks structural/behavioral agreement (needs_human_review, which citation type appears), not verbatim text match.

- **eval-002**: needs_human_review_agrees=False, citation_shape_agrees=True (api=rule, local tools=['search_rules_tool', 'search_rules_tool'])
- **eval-003**: needs_human_review_agrees=True, citation_shape_agrees=True (api=rule, local tools=['search_rules_tool'])
- **eval-010**: needs_human_review_agrees=True, citation_shape_agrees=True (api=web, local tools=['web_search_tool'])
- **eval-017**: needs_human_review_agrees=True, citation_shape_agrees=True (api=rule, local tools=['search_rules_tool'])
- **eval-023**: needs_human_review_agrees=True, citation_shape_agrees=False (api=none, local tools=['search_rules_tool'])
- **eval-033**: needs_human_review_agrees=True, citation_shape_agrees=False (api=none, local tools=['web_search_tool', 'web_search_tool', 'web_search_tool', 'web_search_tool'])

Notable: eval-023 and eval-033 both reproduced independently on the live deployed API, matching this run's own local-invocation results -- confirming these are real pipeline findings, not artifacts of local-only invocation. eval-023 is a silent faithfulness failure (see worst-10 above): both systems confidently cited '5 penalty runs' from an unrelated section instead of the correct 36 (Section 5.3.5), and the judge PASSed it on both. eval-033 reproduced the exact known failure mode golden_set.json's own notes already named (a bare 'round 1' question misread as a real-world tournament reference, both systems answering about an unrelated ICC/T20 World Cup instead of asking which MYCA grade).
