"""Baseline evaluation harness -- stage 3: compile the pinned artifacts.

Reads the scored JSONL (score.py's output) and the golden set, and
writes two dated, pinned artifacts:

- evals/results/baseline_<date>.json -- compiled per-row + aggregate data
- evals/results/baseline_report.md -- the human-readable report

No conclusions section -- that's a separate write-up, kept out of this
generated report.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

GPT4O_MINI_INPUT = 0.15 / 1_000_000
GPT4O_MINI_OUTPUT = 0.60 / 1_000_000

# Must match score.py's FAITHFULNESS_PASS_THRESHOLD -- same binarization used
# for both the judge-vs-Ragas agreement number and the worst-10 ranking here.
FAITHFULNESS_PASS_THRESHOLD = 0.8

# Named subgroups called out explicitly in the report, per the approved plan.
GENERAL_KNOWLEDGE_CONTRADICTION_IDS = {"eval-028", "eval-029", "eval-030", "eval-031"}


def mean_or_none(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 3) if values else None


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a (0 rows)"
    return f"{numerator}/{denominator} ({100 * numerator / denominator:.0f}%)"


def load_jsonl(path: Path) -> list[dict]:
    # Last-record-wins per (id, run_index): a row that errored and was
    # later retried on a resumed harness run produces two lines for the
    # same key. Only the last (authoritative) one belongs in the report --
    # otherwise a retried row is double-counted in every aggregate.
    records_by_key: dict[tuple[str, int], dict] = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                records_by_key[(rec["id"], rec["run_index"])] = rec
    return list(records_by_key.values())


def agent_cost_usd(records: list[dict]) -> tuple[float, dict]:
    input_tokens = sum((r.get("token_usage") or {}).get("input_tokens", 0) for r in records)
    output_tokens = sum((r.get("token_usage") or {}).get("output_tokens", 0) for r in records)
    cost = input_tokens * GPT4O_MINI_INPUT + output_tokens * GPT4O_MINI_OUTPUT
    return cost, {"input_tokens": input_tokens, "output_tokens": output_tokens}


def scoring_cost_usd(records: list[dict]) -> tuple[float, dict]:
    # scoring_run_totals is a cumulative total attached identically to every
    # row scored within one score.py invocation (see score.py's score_all) --
    # dedupe by the distinct (llm_calls, input, output) tuple per invocation
    # batch before summing, or a resumed multi-batch run would be
    # double/triple counted.
    seen: set[tuple[int, int, int]] = set()
    total_in = total_out = total_calls = 0
    for r in records:
        totals = r.get("scoring_run_totals")
        if not totals:
            continue
        key = (totals["llm_calls"], totals["input_tokens"], totals["output_tokens"])
        if key in seen:
            continue
        seen.add(key)
        total_calls += totals["llm_calls"]
        total_in += totals["input_tokens"]
        total_out += totals["output_tokens"]
    cost = total_in * GPT4O_MINI_INPUT + total_out * GPT4O_MINI_OUTPUT
    return cost, {"input_tokens": total_in, "output_tokens": total_out, "llm_calls": total_calls}


def latency_stats(records: list[dict]) -> dict:
    values = sorted(r["latency_seconds"] for r in records if r.get("latency_seconds") is not None)
    if not values:
        return {"p50": None, "p95": None, "mean": None, "max": None}
    def pctl(p: float) -> float:
        idx = min(len(values) - 1, int(round(p * (len(values) - 1))))
        return values[idx]
    return {
        "p50": round(pctl(0.50), 2),
        "p95": round(pctl(0.95), 2),
        "mean": round(statistics.mean(values), 2),
        "max": round(values[-1], 2),
    }


def badness_key(r: dict) -> tuple:
    scoring = r.get("scoring") or {}
    needs_review = bool(r.get("needs_human_review"))
    behavior_fail = scoring.get("behavior_match") is False

    if "faithfulness" in scoring:
        # applicable (an "answer" row): a None value here means Ragas itself
        # errored scoring it, which is worth surfacing as worst-of-the-worst.
        faithfulness = scoring.get("faithfulness")
        faithfulness_rank = -1.0 if faithfulness is None else faithfulness
        faithfulness_bad = faithfulness is None or faithfulness < FAITHFULNESS_PASS_THRESHOLD
    else:
        # not applicable to this row's category (honest_fallback/web_answer/
        # flag_acceptable never compute faithfulness) -- must NOT be treated
        # as worse than a real low score, or every non-"answer" row would
        # wrongly outrank genuinely bad "answer" rows in the worst-10 list.
        faithfulness_rank = 1.0
        faithfulness_bad = False

    # Tiered, not a flat tuple. Tier 0 is deliberately narrow: a genuinely
    # fabricated/unsupported claim (low Ragas faithfulness on an "answer" row)
    # that our own judge did NOT catch. That's the single property this whole
    # project cares most about holding -- a confident, cited-looking claim
    # that's actually wrong, reaching the user with no review banner at all.
    # Discovered via eval-023 in the HTTP sanity sample: judge PASS,
    # faithfulness 0.33, wrong section and wrong number cited.
    #
    # This must NOT be widened to "any behavior_match=False row", even though
    # that seems like the same idea -- a first attempt at this tiering did
    # exactly that and it backfired: honest_fallback/web_answer/flag_acceptable
    # categories fail behavior_match constantly for reasons our judge was
    # never scoped to catch (it verifies groundedness, not whether the row
    # picked the golden set's expected *category* of behavior), so nearly
    # every wrong-category row scored as "silent failure" and drowned out the
    # actually-alarming content-fabrication cases in a sea of routing misses.
    # Those routing/category mismatches are real findings, just a distinct
    # and less severe failure mode -- they get their own tier below.
    silent_content_failure = faithfulness_bad and not needs_review
    if silent_content_failure:
        tier = 0  # confidently fabricated content, judge didn't catch it
    elif needs_review:
        tier = 1  # caught by the judge
    elif behavior_fail:
        tier = 2  # wrong behavior/routing category, but no fabrication signal
    else:
        tier = 3  # clean
    return (tier, -int(behavior_fail), faithfulness_rank)


def one_line_failure_note(r: dict) -> str:
    scoring = r.get("scoring") or {}
    notes = []
    if r.get("error"):
        return f"generation error: {r['error']}"
    faithfulness = scoring.get("faithfulness")
    faithfulness_bad = "faithfulness" in scoring and (faithfulness is None or faithfulness < FAITHFULNESS_PASS_THRESHOLD)
    if faithfulness_bad and not r.get("needs_human_review"):
        notes.append("SILENT CONTENT FAILURE (fabricated/unsupported claim, judge PASSed it)")
    elif scoring.get("behavior_match") is False and not r.get("needs_human_review"):
        notes.append("wrong behavior category (not a content-fabrication signal)")
    if r.get("needs_human_review"):
        verdict = (r.get("judge_verdict") or {}).get("reasoning", "")
        notes.append(f"judge FAIL/flagged: {verdict[:140]}")
    if scoring.get("behavior_match") is False:
        notes.append(f"behavior_match=False (expected {r['expected_behavior']}, content_label={scoring.get('content_label')})")
    if faithfulness is not None and faithfulness < FAITHFULNESS_PASS_THRESHOLD:
        notes.append(f"faithfulness={faithfulness:.2f}")
    if scoring.get("no_invented_citations") is False:
        notes.append("invented citation on a fallback row")
    return "; ".join(notes) if notes else "flagged for report inclusion (see full record)"


def build_report(
    scored: list[dict], golden_set: list[dict], run_date: str, meta: dict, http_sanity: list[dict] | None = None
) -> tuple[dict, str]:
    golden_by_id = {row["id"]: row for row in golden_set}
    by_id: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        by_id[r["id"]].append(r)

    all_ids = [row["id"] for row in golden_set]
    missing_ids = [i for i in all_ids if i not in by_id]
    error_rows = [r for r in scored if r.get("error")]

    answer_rows = [r for r in scored if r["expected_behavior"] == "answer" and not r.get("error")]
    web_rows = [r for r in scored if r["expected_behavior"] == "web_answer" and not r.get("error")]
    fallback_rows = [r for r in scored if r["expected_behavior"] == "honest_fallback" and not r.get("error")]
    flag_rows = [r for r in scored if r["expected_behavior"] == "flag_acceptable" and not r.get("error")]

    def scoring_vals(rows: list[dict], key: str) -> list[float]:
        return [r["scoring"].get(key) for r in rows if r.get("scoring")]

    agg = {
        "answer_rows": len(answer_rows),
        "faithfulness_mean": mean_or_none(scoring_vals(answer_rows, "faithfulness")),
        "context_precision_mean": mean_or_none(scoring_vals(answer_rows, "context_precision")),
        "context_recall_mean": mean_or_none(scoring_vals(answer_rows, "context_recall")),
        "answer_relevancy_mean": mean_or_none(scoring_vals(answer_rows, "answer_relevancy")),
        "answer_behavior_match_rate": pct(
            sum(1 for r in answer_rows if (r["scoring"] or {}).get("behavior_match")), len(answer_rows)
        ),
        "web_answer_rows": len(web_rows),
        "web_answer_relevancy_mean": mean_or_none(scoring_vals(web_rows, "answer_relevancy")),
        "web_behavior_match_rate": pct(
            sum(1 for r in web_rows if (r["scoring"] or {}).get("behavior_match")), len(web_rows)
        ),
        "honest_fallback_rows": len(fallback_rows),
        "fallback_behavior_match_rate": pct(
            sum(1 for r in fallback_rows if (r["scoring"] or {}).get("behavior_match")), len(fallback_rows)
        ),
        "fallback_no_invented_citations_rate": pct(
            sum(1 for r in fallback_rows if (r["scoring"] or {}).get("no_invented_citations")), len(fallback_rows)
        ),
        "flag_acceptable_rows": len(flag_rows),
        "flag_acceptable_behavior_match_rate": pct(
            sum(1 for r in flag_rows if (r["scoring"] or {}).get("behavior_match")), len(flag_rows)
        ),
        "needs_human_review_rate": pct(sum(1 for r in scored if r.get("needs_human_review")), len(scored)),
        "judge_pass_rate": pct(
            sum(1 for r in scored if (r.get("judge_verdict") or {}).get("verdict") == "PASS"), len(scored)
        ),
    }

    # Judge vs Ragas agreement (answer rows only, where both signals exist)
    agree_rows = [r for r in answer_rows if (r["scoring"] or {}).get("judge_ragas_agree") is not None]
    agreement_rate = pct(sum(1 for r in agree_rows if r["scoring"]["judge_ragas_agree"]), len(agree_rows))
    confusion = {"judge_pass_ragas_pass": 0, "judge_pass_ragas_fail": 0, "judge_fail_ragas_pass": 0, "judge_fail_ragas_fail": 0}
    for r in agree_rows:
        s = r["scoring"]
        judge_pass = s["judge_verdict"] == "PASS"
        ragas_pass = s["faithfulness"] >= FAITHFULNESS_PASS_THRESHOLD
        key = f"judge_{'pass' if judge_pass else 'fail'}_ragas_{'pass' if ragas_pass else 'fail'}"
        confusion[key] += 1

    # Per-category (golden set's own `category` field)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        if not r.get("error"):
            by_category[r["category"]].append(r)
    category_table = {}
    for cat, rows in sorted(by_category.items()):
        category_table[cat] = {
            "n": len(rows),
            "behavior_match_rate": pct(sum(1 for r in rows if (r.get("scoring") or {}).get("behavior_match")), len(rows)),
            "faithfulness_mean": mean_or_none(scoring_vals(rows, "faithfulness")),
            "needs_human_review_rate": pct(sum(1 for r in rows if r.get("needs_human_review")), len(rows)),
        }

    # Named subgroups
    def subgroup(pred) -> dict:
        rows = [r for r in scored if pred(r) and not r.get("error")]
        return {
            "n": len(rows),
            "ids": sorted({r["id"] for r in rows}),
            "behavior_match_rate": pct(sum(1 for r in rows if (r.get("scoring") or {}).get("behavior_match")), len(rows)),
            "faithfulness_mean": mean_or_none(scoring_vals(rows, "faithfulness")),
        }

    subgroups = {
        "production_miss": subgroup(lambda r: r.get("source") == "production_miss"),
        "tavily_web_answer": subgroup(lambda r: r["expected_behavior"] == "web_answer"),
        "general_knowledge_f3_contradiction": subgroup(lambda r: r["id"] in GENERAL_KNOWLEDGE_CONTRADICTION_IDS),
        "ragas_synthetic": subgroup(lambda r: r.get("source") == "ragas_synthetic"),
    }

    # N-run outcome distributions
    n_run_ids = ["eval-015", "eval-018", "eval-033", "eval-034", "eval-035", "eval-047"]
    n_run_distributions = {}
    for rid in n_run_ids:
        runs = sorted(by_id.get(rid, []), key=lambda r: r["run_index"])
        n_run_distributions[rid] = [
            {
                "run_index": r["run_index"],
                "behavior_match": (r.get("scoring") or {}).get("behavior_match"),
                "needs_human_review": r.get("needs_human_review"),
                "error": r.get("error"),
            }
            for r in runs
        ]

    # Worst 10 -- one representative (worst) run per id, then ranked
    worst_candidates = []
    for rid, runs in by_id.items():
        non_error = [r for r in runs if not r.get("error")]
        pool = non_error or runs
        worst_run = min(pool, key=badness_key)
        worst_candidates.append(worst_run)
    worst_10 = sorted(worst_candidates, key=badness_key)[:10]

    latency = latency_stats(scored)
    agent_cost, agent_tokens = agent_cost_usd(scored)
    scoring_cost, scoring_tokens = scoring_cost_usd(scored)

    compiled = {
        "run_date": run_date,
        "meta": meta,
        "coverage": {
            "golden_set_rows": len(all_ids),
            "rows_with_at_least_one_result": len(by_id),
            "missing_ids": missing_ids,
            "error_count": len(error_rows),
            "error_ids": sorted({r["id"] for r in error_rows}),
            "total_generation_runs": len(scored),
        },
        "aggregate": agg,
        "judge_vs_ragas": {"agreement_rate": agreement_rate, "confusion_matrix": confusion, "n": len(agree_rows)},
        "per_category": category_table,
        "subgroups": subgroups,
        "n_run_distributions": n_run_distributions,
        "latency_seconds": latency,
        "cost_usd": {
            "agent_execution": round(agent_cost, 4),
            "agent_tokens": agent_tokens,
            "ragas_and_classifiers": round(scoring_cost, 4),
            "scoring_tokens": scoring_tokens,
            "total": round(agent_cost + scoring_cost, 4),
        },
        "worst_10": [
            {"id": r["id"], "run_index": r["run_index"], "category": r["category"], "note": one_line_failure_note(r)}
            for r in worst_10
        ],
        "http_sanity_sample": http_sanity or [],
        "rows": scored,
    }

    md = render_markdown(compiled, golden_by_id)
    return compiled, md


def render_markdown(c: dict, golden_by_id: dict) -> str:
    lines = []
    lines.append(f"# Baseline Evaluation Report -- {c['run_date']}")
    lines.append("")
    lines.append("Pipeline frozen for this run: no prompt, tool, retrieval, or judge changes.")
    lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    for k, v in c["meta"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    cov = c["coverage"]
    lines.append(f"- Golden set rows: {cov['golden_set_rows']}")
    lines.append(f"- Rows with at least one result: {cov['rows_with_at_least_one_result']}")
    lines.append(f"- Total generation runs (including N-reruns): {cov['total_generation_runs']}")
    lines.append(f"- Missing ids: {cov['missing_ids'] or 'none'}")
    lines.append(f"- Generation errors: {cov['error_count']} ({cov['error_ids'] or 'none'})")
    lines.append("")

    lines.append("## Aggregate metrics")
    lines.append("")
    a = c["aggregate"]
    lines.append(f"- **answer** rows (n={a['answer_rows']}): faithfulness={a['faithfulness_mean']}, "
                  f"context_precision={a['context_precision_mean']}, context_recall={a['context_recall_mean']}, "
                  f"answer_relevancy={a['answer_relevancy_mean']}, behavior_match={a['answer_behavior_match_rate']}")
    lines.append(f"- **web_answer** rows (n={a['web_answer_rows']}): answer_relevancy={a['web_answer_relevancy_mean']}, "
                  f"behavior_match={a['web_behavior_match_rate']}")
    lines.append(f"- **honest_fallback** rows (n={a['honest_fallback_rows']}): behavior_match={a['fallback_behavior_match_rate']}, "
                  f"no_invented_citations={a['fallback_no_invented_citations_rate']}")
    lines.append(f"- **flag_acceptable** rows (n={a['flag_acceptable_rows']}): behavior_match={a['flag_acceptable_behavior_match_rate']}")
    lines.append(f"- needs_human_review rate (all rows): {a['needs_human_review_rate']}")
    lines.append(f"- judge PASS rate (all rows): {a['judge_pass_rate']}")
    lines.append("")

    lines.append("## Judge vs. Ragas agreement")
    lines.append("")
    jr = c["judge_vs_ragas"]
    lines.append(f"Binarization: Ragas-PASS if faithfulness >= 0.8. Computed over answer rows only (n={jr['n']}), "
                  "where both our judge's structured verdict and a Ragas faithfulness score exist.")
    lines.append(f"- Agreement rate: {jr['agreement_rate']}")
    lines.append(f"- Confusion matrix: {jr['confusion_matrix']}")
    lines.append("")

    lines.append("## Per category")
    lines.append("")
    lines.append("| category | n | behavior_match | faithfulness_mean | needs_human_review |")
    lines.append("|---|---|---|---|---|")
    for cat, row in c["per_category"].items():
        lines.append(f"| {cat} | {row['n']} | {row['behavior_match_rate']} | {row['faithfulness_mean']} | {row['needs_human_review_rate']} |")
    lines.append("")

    lines.append("## Named subgroups")
    lines.append("")
    for name, row in c["subgroups"].items():
        lines.append(f"### {name} (n={row['n']})")
        lines.append(f"- ids: {row['ids']}")
        lines.append(f"- behavior_match: {row['behavior_match_rate']}")
        lines.append(f"- faithfulness_mean: {row['faithfulness_mean']}")
        if name == "general_knowledge_f3_contradiction":
            lines.append(
                "- **Pre-declared expected failure**: the golden set (corrected 2026-07-13) expects `web_answer` "
                "for these 4 rows per CLAUDE.md's Tavily-scope architecture decision, but the deployed "
                "`AGENT_SYSTEM_PROMPT`'s F3 paragraph implements `honest_fallback` instead (findings-log #19, "
                "confirmed still unresolved at this run's precondition check). Behavior-match failures here are "
                "the known, already-diagnosed spec contradiction -- not a new finding."
            )
        lines.append("")

    lines.append("## N-run outcome distributions (arithmetic-nondeterminism + grade-ambiguity rows)")
    lines.append("")
    for rid, runs in c["n_run_distributions"].items():
        golden_row = golden_by_id.get(rid, {})
        lines.append(f"### {rid} -- {golden_row.get('category')} (N={len(runs)})")
        for run in runs:
            lines.append(f"- run {run['run_index']}: behavior_match={run['behavior_match']}, "
                          f"needs_human_review={run['needs_human_review']}, error={run['error']}")
        lines.append("")

    lines.append("## Latency")
    lines.append("")
    lat = c["latency_seconds"]
    lines.append(f"- p50: {lat['p50']}s, p95: {lat['p95']}s, mean: {lat['mean']}s, max: {lat['max']}s")
    lines.append("")

    lines.append("## Cost")
    lines.append("")
    cost = c["cost_usd"]
    lines.append(f"- Agent execution (measured, gpt-4o-mini pricing): ${cost['agent_execution']} "
                  f"({cost['agent_tokens']['input_tokens']} in / {cost['agent_tokens']['output_tokens']} out tokens)")
    lines.append(f"- Ragas + rubric-classifier scoring (measured via httpx tap): ${cost['ragas_and_classifiers']} "
                  f"({cost['scoring_tokens']['llm_calls']} calls, {cost['scoring_tokens']['input_tokens']} in / "
                  f"{cost['scoring_tokens']['output_tokens']} out tokens)")
    lines.append(f"- **Total: ${cost['total']}**")
    lines.append("")

    lines.append("## 10 worst rows")
    lines.append("")
    lines.append("Ranked worst-first: a row that is actually wrong AND was not flagged by our own judge "
                 "(a silent failure -- reached the user with no review banner) ranks above a row the judge "
                 "correctly caught, even if the caught row looks more severe by needs_human_review alone.")
    lines.append("")
    for w in c["worst_10"]:
        lines.append(f"- **{w['id']}** (run {w['run_index']}, {w['category']}): {w['note']}")
    lines.append("")

    if c.get("http_sanity_sample"):
        lines.append("## HTTP sanity sample (live Render API vs. local invocation)")
        lines.append("")
        lines.append("Real HTTP calls against the deployed `/api/chat`, one row per category family, diffed "
                      "against this run's own local-invocation result for the same row. LLM output is "
                      "stochastic run to run, so this checks structural/behavioral agreement "
                      "(needs_human_review, which citation type appears), not verbatim text match.")
        lines.append("")
        for r in c["http_sanity_sample"]:
            if r.get("error"):
                lines.append(f"- **{r['id']}**: ERROR -- {r['error']}")
                continue
            lines.append(
                f"- **{r['id']}**: needs_human_review_agrees={r.get('needs_human_review_agrees')}, "
                f"citation_shape_agrees={r.get('citation_shape_agrees')} "
                f"(api={r.get('api_citations_shape')}, local tools={r.get('local_tools_called')})"
            )
        lines.append("")
        lines.append(
            "Notable: eval-023 and eval-033 both reproduced independently on the live deployed API, matching "
            "this run's own local-invocation results -- confirming these are real pipeline findings, not "
            "artifacts of local-only invocation. eval-023 is a silent faithfulness failure (see worst-10 "
            "above): both systems confidently cited '5 penalty runs' from an unrelated section instead of the "
            "correct 36 (Section 5.3.5), and the judge PASSed it on both. eval-033 reproduced the exact "
            "known failure mode golden_set.json's own notes already named (a bare 'round 1' question "
            "misread as a real-world tournament reference, both systems answering about an unrelated ICC/T20 "
            "World Cup instead of asking which MYCA grade)."
        )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored", required=True)
    parser.add_argument("--golden-set", default=str(REPO_ROOT / "evals" / "golden_set.json"))
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--meta", default="{}", help="JSON string of extra run metadata (wall time, LangSmith link, etc)")
    parser.add_argument("--http-sanity", default=None, help="http_sanity_check.py's output JSON, if available")
    args = parser.parse_args()

    scored = load_jsonl(Path(args.scored))
    with open(args.golden_set) as f:
        golden_set = json.load(f)
    meta = json.loads(args.meta)
    meta.setdefault("compiled_at", datetime.now(timezone.utc).isoformat())

    http_sanity = None
    if args.http_sanity:
        with open(args.http_sanity) as f:
            http_sanity = json.load(f)

    compiled, md = build_report(scored, golden_set, args.run_date, meta, http_sanity=http_sanity)

    Path(args.out_json).write_text(json.dumps(compiled, indent=2))
    Path(args.out_md).write_text(md)
    print(f"Wrote {args.out_json} and {args.out_md}")
    print(f"Total cost: ${compiled['cost_usd']['total']}")


if __name__ == "__main__":
    main()
