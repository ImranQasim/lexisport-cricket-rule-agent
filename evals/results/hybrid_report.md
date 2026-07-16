# Baseline Evaluation Report -- 2026-07-14

Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.

## Run metadata

- **git_commit**: a582904d50b437eba520803b03c2874f4684960a
- **retrieval_mode**: hybrid (match_rule_chunks_hybrid: dense + full-text, RRF fusion)
- **agent_and_judge_model**: gpt-4o-mini (via local LiteLLM gateway, gateway/config.yaml, unmodified)
- **ragas_version**: 0.4.3
- **ragas_evaluator_model**: gpt-4o-mini
- **ragas_embedding_model**: text-embedding-3-small
- **n_run_protocol**: N=5 on eval-015/eval-018 (arithmetic nondeterminism); N=3 on eval-033/034/035/047 (grade-ambiguity behavioral variance); N=1 on all other 44 rows -- identical to the baseline protocol
- **execution_path**: local backend.agent.build_graph() in-process, RETRIEVAL_MODE=hybrid, same local gateway and real Supabase DB as the baseline run
- **note**: One mid-run Postgres connection drop (5 rows) recovered via a resumed run after fixing a last-record-wins dedup gap in run_baseline.py/score.py/compile_report.py -- see findings-log. Final coverage: 50/50 rows, 66/66 runs, 0 residual errors.
- **langsmith_project**: lexisport-hybrid-2026-07-14
- **compiled_at**: 2026-07-14T07:25:28.793060+00:00

## Coverage

- Golden set rows: 50
- Rows with at least one result: 50
- Total generation runs (including N-reruns): 66
- Missing ids: none
- Generation errors: 0 (none)

## Aggregate metrics

- **answer** rows (n=31): faithfulness=0.763, context_precision=0.656, context_recall=0.777, answer_relevancy=0.63, behavior_match=28/31 (90%)
- **web_answer** rows (n=6): answer_relevancy=0.197, behavior_match=2/6 (33%)
- **honest_fallback** rows (n=7): behavior_match=2/7 (29%), no_invented_citations=4/7 (57%)
- **flag_acceptable** rows (n=22): behavior_match=6/22 (27%)
- needs_human_review rate (all rows): 26/66 (39%)
- judge PASS rate (all rows): 40/66 (61%)

## Judge vs. Ragas agreement

Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n=29), where both our judge's structured verdict and a Ragas faithfulness score exist.
- Agreement rate: 11/29 (38%)
- Confusion matrix: {'judge_pass_ragas_pass': 8, 'judge_pass_ragas_fail': 12, 'judge_fail_ragas_pass': 6, 'judge_fail_ragas_fail': 3}

## Per category

| category | n | behavior_match | faithfulness_mean | needs_human_review |
|---|---|---|---|---|
| absence_claim | 5 | 2/5 (40%) | None | 2/5 (40%) |
| ambiguous_phrasing | 10 | 4/10 (40%) | 0.286 | 2/10 (20%) |
| cross_grade | 5 | 4/5 (80%) | 0.867 | 4/5 (80%) |
| direct_rule_lookup | 18 | 16/18 (89%) | 0.834 | 5/18 (28%) |
| formula_arithmetic | 7 | 7/7 (100%) | 0.604 | 3/7 (43%) |
| general_knowledge | 4 | 0/4 (0%) | None | 0/4 (0%) |
| table_lookup | 13 | 3/13 (23%) | 0.738 | 10/13 (77%) |
| web_routing | 4 | 2/4 (50%) | None | 0/4 (0%) |

## Named subgroups

### production_miss (n=7)
- ids: ['eval-014', 'eval-015', 'eval-016']
- behavior_match: 2/7 (29%)
- faithfulness_mean: 0.875

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
- faithfulness_mean: 1.0

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
- run 0: behavior_match=False, needs_human_review=False, error=None
- run 1: behavior_match=False, needs_human_review=False, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-034 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=True, needs_human_review=False, error=None
- run 1: behavior_match=True, needs_human_review=False, error=None
- run 2: behavior_match=True, needs_human_review=False, error=None

### eval-035 -- ambiguous_phrasing (N=3)
- run 0: behavior_match=False, needs_human_review=True, error=None
- run 1: behavior_match=False, needs_human_review=True, error=None
- run 2: behavior_match=False, needs_human_review=False, error=None

### eval-047 -- direct_rule_lookup (N=3)
- run 0: behavior_match=True, needs_human_review=True, error=None
- run 1: behavior_match=True, needs_human_review=True, error=None
- run 2: behavior_match=True, needs_human_review=True, error=None

## Latency

- p50: 9.46s, p95: 31.8s, mean: 13.89s, max: 68.23s

## Cost

- Agent execution (measured, gpt-4o-mini pricing): $0.1193 (666566 in / 32135 out tokens)
- Ragas + rubric-classifier scoring (measured via httpx tap): $0.1229 (512 calls, 637268 in / 45541 out tokens)
- **Total: $0.2422**

## 10 worst rows

Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge (a silent failure -- reached the user with no review banner) ranks above a row the judge correctly caught, even if the caught row looks more severe by needs_human_review alone.

- **eval-041** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); behavior_match=False (expected answer, content_label=honest_fallback); faithfulness=0.78
- **eval-046** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it)
- **eval-050** (run 0, ambiguous_phrasing): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.29
- **eval-022** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.33
- **eval-012** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.40
- **eval-004** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.60
- **eval-025** (run 0, formula_arithmetic): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-044** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.67
- **eval-005** (run 0, direct_rule_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.71
- **eval-019** (run 0, table_lookup): SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it); faithfulness=0.71
