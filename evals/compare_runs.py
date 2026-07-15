"""Compares two compiled evaluation-harness runs (e.g. baseline vs. a
hybrid-retrieval experiment) and writes an honest delta report.

Reads compile_report.py's compiled JSON output for each run (which
embeds every scored row under "rows"), recomputes the same metrics
directly from those rows for both runs, and reports explicit deltas --
per category, per named subgroup, plus retrieval-miss counts and a
regression list (rows clean under run A that got worse under run B).

Does not judge which run is "better" beyond stating the numbers --
that decision belongs in VERIFY, written by a human reading this
table, not asserted here.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def mean_or_none(values: list[float | None]) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 3) if values else None


def frac(numerator: int, denominator: int) -> tuple[int, int, float | None]:
    pct = round(100 * numerator / denominator, 1) if denominator else None
    return numerator, denominator, pct


def fmt_frac(t: tuple[int, int, float | None]) -> str:
    n, d, p = t
    return f"{n}/{d} ({p}%)" if p is not None else "n/a"


def delta_pct(a: tuple[int, int, float | None], b: tuple[int, int, float | None]) -> str:
    if a[2] is None or b[2] is None:
        return "n/a"
    d = round(b[2] - a[2], 1)
    return f"{'+' if d >= 0 else ''}{d}pp"


def delta_num(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return "n/a"
    d = round(b - a, 3)
    return f"{'+' if d >= 0 else ''}{d}"


def retrieval_misses(rows: list[dict]) -> list[str]:
    """A genuine retrieval-empty case: search_rules_tool was actually
    called and came back with nothing -- distinct from the tool never
    being called at all (a tool-routing decision, not a retrieval miss;
    see findings-log's correction on eval-013/eval-028)."""
    return sorted(
        {r["id"] for r in rows if "search_rules_tool" in (r.get("tools_called") or []) and not r.get("rule_contexts")}
    )


def first_run_by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows if r["run_index"] == 0}


def has_citation_check(rows: list[dict]) -> bool:
    """A run predating this feature has no "citation_verdict" key at all
    (not merely None) -- distinct from a run where the check ran but
    found nothing to flag. Reported as n/a rather than a misleading 0%."""
    return any("citation_verdict" in r for r in rows)


def catch_attribution(rows: list[dict]) -> dict:
    """Attributes each flagged row to whichever check actually caused
    it: mechanical_catch if the citation check itself FAILed this turn
    (judge may not even have run, see route_after_citation_check);
    judge_only_catch if the citation check passed/didn't run but the
    judge FAILed. The distinct-fields requirement this answers: without
    citation_verdict living as its own sibling state field, this split
    wouldn't be computable at all."""
    ok_rows = [r for r in rows if not r.get("error")]
    mechanical = sum(1 for r in ok_rows if (r.get("citation_verdict") or {}).get("verdict") == "FAIL")
    judge_only = sum(
        1
        for r in ok_rows
        if (r.get("citation_verdict") or {}).get("verdict") != "FAIL"
        and (r.get("judge_verdict") or {}).get("verdict") == "FAIL"
    )
    return {"mechanical_catch": mechanical, "judge_only_catch": judge_only, "n": len(ok_rows)}


def false_fires(a_rows: list[dict], b_rows: list[dict]) -> list[str]:
    """Rows clean at baseline (a) that the mechanical check itself newly
    flags under b -- distinct from a general regression, since
    generator/judge/retrieval are frozen (one variable): any new flag
    whose citation_verdict says FAIL is unambiguously attributable to
    this change, not to noise elsewhere in the pipeline."""
    a_by_id = first_run_by_id(a_rows)
    b_by_id = first_run_by_id(b_rows)
    out = []
    for rid, a in a_by_id.items():
        b = b_by_id.get(rid)
        if b is None or a.get("error") or b.get("error"):
            continue
        a_clean = not a.get("needs_human_review")
        b_mechanical_fail = (b.get("citation_verdict") or {}).get("verdict") == "FAIL"
        if a_clean and b_mechanical_fail:
            out.append(rid)
    return sorted(out)


def row_metrics(rows: list[dict]) -> dict:
    answer_rows = [r for r in rows if r["expected_behavior"] == "answer" and not r.get("error")]
    web_rows = [r for r in rows if r["expected_behavior"] == "web_answer" and not r.get("error")]
    fallback_rows = [r for r in rows if r["expected_behavior"] == "honest_fallback" and not r.get("error")]
    flag_rows = [r for r in rows if r["expected_behavior"] == "flag_acceptable" and not r.get("error")]
    ok_rows = [r for r in rows if not r.get("error")]

    def bm(rs: list[dict]) -> tuple[int, int, float | None]:
        return frac(sum(1 for r in rs if (r.get("scoring") or {}).get("behavior_match")), len(rs))

    def scoring_vals(rs: list[dict], key: str) -> list[float | None]:
        return [(r.get("scoring") or {}).get(key) for r in rs]

    retrieval_seconds = [r.get("retrieval_seconds") for r in ok_rows if r.get("retrieval_seconds") is not None]
    latency_seconds = sorted(r["latency_seconds"] for r in ok_rows if r.get("latency_seconds") is not None)

    def pctl(values: list[float], p: float) -> float | None:
        if not values:
            return None
        idx = min(len(values) - 1, int(round(p * (len(values) - 1))))
        return round(sorted(values)[idx], 2)

    return {
        "n": len(ok_rows),
        "answer_behavior_match": bm(answer_rows),
        "web_behavior_match": bm(web_rows),
        "fallback_behavior_match": bm(fallback_rows),
        "flag_behavior_match": bm(flag_rows),
        "overall_behavior_match": bm(ok_rows),
        "faithfulness_mean": mean_or_none(scoring_vals(answer_rows, "faithfulness")),
        "context_precision_mean": mean_or_none(scoring_vals(answer_rows, "context_precision")),
        "context_recall_mean": mean_or_none(scoring_vals(answer_rows, "context_recall")),
        "answer_relevancy_mean": mean_or_none(scoring_vals(answer_rows, "answer_relevancy")),
        "needs_human_review": frac(sum(1 for r in ok_rows if r.get("needs_human_review")), len(ok_rows)),
        "judge_pass": frac(sum(1 for r in ok_rows if (r.get("judge_verdict") or {}).get("verdict") == "PASS"), len(ok_rows)),
        "citation_check_fail": (
            frac(sum(1 for r in ok_rows if (r.get("citation_verdict") or {}).get("verdict") == "FAIL"), len(ok_rows))
            if has_citation_check(ok_rows)
            else None
        ),
        "retrieval_miss_ids": retrieval_misses(ok_rows),
        "latency_p50": pctl(latency_seconds, 0.5),
        "latency_p95": pctl(latency_seconds, 0.95),
        "retrieval_seconds_mean": mean_or_none(retrieval_seconds),
    }


def category_table(a_rows: list[dict], b_rows: list[dict]) -> list[dict]:
    a_by_cat: dict[str, list[dict]] = defaultdict(list)
    b_by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in a_rows:
        if not r.get("error"):
            a_by_cat[r["category"]].append(r)
    for r in b_rows:
        if not r.get("error"):
            b_by_cat[r["category"]].append(r)

    out = []
    for cat in sorted(set(a_by_cat) | set(b_by_cat)):
        a_rs, b_rs = a_by_cat.get(cat, []), b_by_cat.get(cat, [])
        a_bm = frac(sum(1 for r in a_rs if (r.get("scoring") or {}).get("behavior_match")), len(a_rs))
        b_bm = frac(sum(1 for r in b_rs if (r.get("scoring") or {}).get("behavior_match")), len(b_rs))
        a_faith = mean_or_none([(r.get("scoring") or {}).get("faithfulness") for r in a_rs])
        b_faith = mean_or_none([(r.get("scoring") or {}).get("faithfulness") for r in b_rs])
        out.append(
            {
                "category": cat,
                "a_behavior_match": fmt_frac(a_bm),
                "b_behavior_match": fmt_frac(b_bm),
                "delta_behavior_match": delta_pct(a_bm, b_bm),
                "a_faithfulness": a_faith,
                "b_faithfulness": b_faith,
                "delta_faithfulness": delta_num(a_faith, b_faith),
            }
        )
    return out


NAMED_SUBGROUPS = {
    "production_miss": lambda r: r.get("source") == "production_miss",
    "tavily_web_answer": lambda r: r["expected_behavior"] == "web_answer",
    "general_knowledge_f3_contradiction": lambda r: r["id"] in {"eval-028", "eval-029", "eval-030", "eval-031"},
    "ragas_synthetic": lambda r: r.get("source") == "ragas_synthetic",
}


def subgroup_table(a_rows: list[dict], b_rows: list[dict]) -> list[dict]:
    out = []
    for name, pred in NAMED_SUBGROUPS.items():
        a_rs = [r for r in a_rows if pred(r) and not r.get("error")]
        b_rs = [r for r in b_rows if pred(r) and not r.get("error")]
        a_bm = frac(sum(1 for r in a_rs if (r.get("scoring") or {}).get("behavior_match")), len(a_rs))
        b_bm = frac(sum(1 for r in b_rs if (r.get("scoring") or {}).get("behavior_match")), len(b_rs))
        out.append(
            {
                "subgroup": name,
                "a_behavior_match": fmt_frac(a_bm),
                "b_behavior_match": fmt_frac(b_bm),
                "delta_behavior_match": delta_pct(a_bm, b_bm),
            }
        )
    return out


def regressions(a_rows: list[dict], b_rows: list[dict]) -> list[dict]:
    """Rows clean under run A (behavior_match True, not flagged) that
    got worse under run B (behavior_match False, or newly flagged, or a
    material faithfulness drop). Compares run_index 0 only -- the
    headline signal; N-run rows are read qualitatively in VERIFY."""
    a_by_id = first_run_by_id(a_rows)
    b_by_id = first_run_by_id(b_rows)
    out = []
    for rid, a in a_by_id.items():
        b = b_by_id.get(rid)
        if b is None or a.get("error") or b.get("error"):
            continue
        a_scoring, b_scoring = a.get("scoring") or {}, b.get("scoring") or {}
        a_clean = a_scoring.get("behavior_match") is not False and not a.get("needs_human_review")
        b_worse = b_scoring.get("behavior_match") is False or bool(b.get("needs_human_review"))
        if a_clean and b_worse:
            a_faith, b_faith = a_scoring.get("faithfulness"), b_scoring.get("faithfulness")
            out.append(
                {
                    "id": rid,
                    "category": a["category"],
                    "a_needs_human_review": a.get("needs_human_review"),
                    "b_needs_human_review": b.get("needs_human_review"),
                    "a_faithfulness": a_faith,
                    "b_faithfulness": b_faith,
                }
            )
    return sorted(out, key=lambda x: x["id"])


def render_markdown(
    a_label: str,
    b_label: str,
    a: dict,
    b: dict,
    cat_table: list[dict],
    sub_table: list[dict],
    regr: list[dict],
    catch: dict | None = None,
    false_fire_ids: list[str] | None = None,
) -> str:
    false_fire_ids = false_fire_ids or []
    lines = [f"# Comparison: {a_label} vs. {b_label}", ""]
    lines.append(
        "Baseline is frozen as the comparison point. Both runs use the same golden set, N-run protocol, "
        "generator/judge/prompts -- the only variable is retrieval mode. Deltas are B minus A (positive = "
        "hybrid better) unless noted."
    )
    lines.append("")

    lines.append("## Aggregate")
    lines.append("")
    lines.append("| metric | " + a_label + " | " + b_label + " | delta |")
    lines.append("|---|---|---|---|")
    lines.append(f"| answer behavior_match | {fmt_frac(a['answer_behavior_match'])} | {fmt_frac(b['answer_behavior_match'])} | {delta_pct(a['answer_behavior_match'], b['answer_behavior_match'])} |")
    lines.append(f"| web_answer behavior_match | {fmt_frac(a['web_behavior_match'])} | {fmt_frac(b['web_behavior_match'])} | {delta_pct(a['web_behavior_match'], b['web_behavior_match'])} |")
    lines.append(f"| honest_fallback behavior_match | {fmt_frac(a['fallback_behavior_match'])} | {fmt_frac(b['fallback_behavior_match'])} | {delta_pct(a['fallback_behavior_match'], b['fallback_behavior_match'])} |")
    lines.append(f"| flag_acceptable behavior_match | {fmt_frac(a['flag_behavior_match'])} | {fmt_frac(b['flag_behavior_match'])} | {delta_pct(a['flag_behavior_match'], b['flag_behavior_match'])} |")
    lines.append(f"| overall behavior_match | {fmt_frac(a['overall_behavior_match'])} | {fmt_frac(b['overall_behavior_match'])} | {delta_pct(a['overall_behavior_match'], b['overall_behavior_match'])} |")
    lines.append(f"| faithfulness (answer rows) | {a['faithfulness_mean']} | {b['faithfulness_mean']} | {delta_num(a['faithfulness_mean'], b['faithfulness_mean'])} |")
    lines.append(f"| context_precision | {a['context_precision_mean']} | {b['context_precision_mean']} | {delta_num(a['context_precision_mean'], b['context_precision_mean'])} |")
    lines.append(f"| context_recall | {a['context_recall_mean']} | {b['context_recall_mean']} | {delta_num(a['context_recall_mean'], b['context_recall_mean'])} |")
    lines.append(f"| answer_relevancy | {a['answer_relevancy_mean']} | {b['answer_relevancy_mean']} | {delta_num(a['answer_relevancy_mean'], b['answer_relevancy_mean'])} |")
    lines.append(f"| needs_human_review rate | {fmt_frac(a['needs_human_review'])} | {fmt_frac(b['needs_human_review'])} | {delta_pct(a['needs_human_review'], b['needs_human_review'])} |")
    lines.append(f"| judge PASS rate | {fmt_frac(a['judge_pass'])} | {fmt_frac(b['judge_pass'])} | {delta_pct(a['judge_pass'], b['judge_pass'])} |")
    a_ccf = fmt_frac(a["citation_check_fail"]) if a["citation_check_fail"] is not None else "n/a (no mechanical check)"
    b_ccf = fmt_frac(b["citation_check_fail"]) if b["citation_check_fail"] is not None else "n/a (no mechanical check)"
    ccf_delta = (
        delta_pct(a["citation_check_fail"], b["citation_check_fail"])
        if a["citation_check_fail"] is not None and b["citation_check_fail"] is not None
        else "n/a"
    )
    lines.append(f"| citation check FAIL rate (mechanical layer) | {a_ccf} | {b_ccf} | {ccf_delta} |")
    lines.append(f"| retrieval-miss count (search_rules_tool called, empty result) | {len(a['retrieval_miss_ids'])} {a['retrieval_miss_ids']} | {len(b['retrieval_miss_ids'])} {b['retrieval_miss_ids']} | -- |")
    lines.append(f"| latency p50 / p95 (whole turn) | {a['latency_p50']}s / {a['latency_p95']}s | {b['latency_p50']}s / {b['latency_p95']}s | -- |")
    def secs(v: float | None) -> str:
        return f"{v}s" if v is not None else "n/a (instrumentation added after this run)"

    lines.append(
        f"| retrieval-only latency mean (search_rules() call time) | {secs(a['retrieval_seconds_mean'])} | "
        f"{secs(b['retrieval_seconds_mean'])} | {delta_num(a['retrieval_seconds_mean'], b['retrieval_seconds_mean'])} |"
    )
    lines.append("")

    lines.append("## Per category")
    lines.append("")
    lines.append(f"| category | {a_label} behavior_match | {b_label} behavior_match | delta | {a_label} faithfulness | {b_label} faithfulness | delta |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in cat_table:
        lines.append(
            f"| {row['category']} | {row['a_behavior_match']} | {row['b_behavior_match']} | {row['delta_behavior_match']} | "
            f"{row['a_faithfulness']} | {row['b_faithfulness']} | {row['delta_faithfulness']} |"
        )
    lines.append("")

    lines.append("## Named subgroups")
    lines.append("")
    lines.append(f"| subgroup | {a_label} behavior_match | {b_label} behavior_match | delta |")
    lines.append("|---|---|---|---|")
    for row in sub_table:
        lines.append(f"| {row['subgroup']} | {row['a_behavior_match']} | {row['b_behavior_match']} | {row['delta_behavior_match']} |")
    lines.append("")

    if catch is not None:
        lines.append(f"## Citation check ({b_label})")
        lines.append("")
        lines.append(
            "Catches attributed to whichever check actually caused the flag -- mechanical_catch means the "
            "citation-provenance check itself FAILed (the judge may not have even run that pass, see "
            "route_after_citation_check); judge_only_catch means the citation check passed but the LLM judge "
            "still FAILed the row on semantic grounds."
        )
        lines.append("")
        lines.append(f"- mechanical_catch: {catch['mechanical_catch']}/{catch['n']}")
        lines.append(f"- judge_only_catch: {catch['judge_only_catch']}/{catch['n']}")
        lines.append("")
        lines.append(f"False fires ({a_label}-clean rows the mechanical check itself newly flags under {b_label}):")
        lines.append("")
        if not false_fire_ids:
            lines.append("None found (comparing run_index 0 for every row).")
        else:
            for rid in false_fire_ids:
                lines.append(f"- {rid}")
        lines.append("")

    lines.append(f"## Regressions ({a_label}-clean rows that got worse under {b_label})")
    lines.append("")
    if not regr:
        lines.append("None found (comparing run_index 0 for every row).")
    else:
        for r in regr:
            lines.append(
                f"- **{r['id']}** ({r['category']}): needs_human_review {r['a_needs_human_review']} -> {r['b_needs_human_review']}, "
                f"faithfulness {r['a_faithfulness']} -> {r['b_faithfulness']}"
            )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="compile_report.py's compiled JSON for the baseline run")
    parser.add_argument("--hybrid", required=True, help="compile_report.py's compiled JSON for the hybrid run")
    parser.add_argument("--baseline-label", default="baseline")
    parser.add_argument("--hybrid-label", default="hybrid")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.baseline) as f:
        baseline = json.load(f)
    with open(args.hybrid) as f:
        hybrid = json.load(f)

    a_rows, b_rows = baseline["rows"], hybrid["rows"]
    a_metrics, b_metrics = row_metrics(a_rows), row_metrics(b_rows)
    cat_table = category_table(a_rows, b_rows)
    sub_table = subgroup_table(a_rows, b_rows)
    regr = regressions(a_rows, b_rows)
    catch = catch_attribution(b_rows) if has_citation_check(b_rows) else None
    false_fire_ids = false_fires(a_rows, b_rows) if has_citation_check(b_rows) else []

    md = render_markdown(
        args.baseline_label, args.hybrid_label, a_metrics, b_metrics, cat_table, sub_table, regr, catch, false_fire_ids
    )
    Path(args.out).write_text(md)
    print(f"Wrote {args.out}")
    print(f"Regressions found: {len(regr)}")


if __name__ == "__main__":
    main()
