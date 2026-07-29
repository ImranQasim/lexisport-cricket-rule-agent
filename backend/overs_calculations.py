"""Deterministic, non-LLM cricket time-lost overs arithmetic.

Built after table_lookup's own eval traces showed two distinct failure
shapes that a single LLM call reproducing multi-step arithmetic in free
text cannot reliably avoid:

1. Wrong-scenario selection (eval-018): every fact used was real -- a
   real table, a real row, a real number -- but the rule was the wrong
   one for the scenario (a late-start table applied to a mid-match rain
   question), producing a reduction bigger than the format allows.
2. Arithmetic nondeterminism (the "33-minutes family", findings-log F2;
   eval-017): the same multi-step formula, applied by a single free-text
   LLM call to identical retrieved context, produced a different answer
   across repeated runs -- most often by silently dropping a step (e.g.
   the halving step in a "round up, then halve" procedure).

This module takes both classes of decision out of free-text generation.
It deliberately contains NO association-specific facts -- no overs
caps, no time windows, no per-minute rates, no section numbers or
document names. Every number these functions operate on is a required
parameter, supplied by the caller (backend.agent's tool wrappers) from
whatever was actually retrieved that turn. If an association's rules
change next season, nothing here needs to change -- the new numbers
flow through as arguments, sourced fresh from retrieval every time.
Only the arithmetic PROCEDURE lives in code, the same division of labor
backend.citations already uses (that module encodes a matching
algorithm, never an actual MYCA section number or fine amount).

Three operations are implemented, exactly the three exercised by the
table_lookup rows this module was built against (eval-017, eval-018,
eval-019):
- check_late_start_reduction: bounds-check only. The caller has already
  read the reduction figure off a retrieved table band (models are
  reliably accurate at this simple lookup -- eval-019, eval-020 both
  get it right today); this function's only job is the one step that
  gets silently skipped: does this reduction actually leave a playable
  match, or does it meet/exceed the format's own overs cap.
- calculate_halved_interruption_reduction: the "round up to a whole
  over, round up again to the next even number if odd, halve, subtract
  from a fixed cap" shape (matches MYCA Senior Men's Section 5.3.2(B),
  verified against its own worked example: 60 minutes lost -> 15 overs
  -> round up to 16 -> halved to 8 off each side, 35 down to 27).
- calculate_remaining_time_reduction: the "revised total = remaining
  time in the match window / minutes-per-over" shape (matches MYCA
  Senior Women's Section 5.3.2 -- no halving step, a different
  arithmetic shape entirely, not just different numbers).

Both interruption shapes are genuinely different cricket time-lost
arithmetic patterns, not MYCA inventions -- which one applies to a
given grade is a fact about that grade's own rule text, decided by the
caller from what it retrieves, not hardcoded here against a grade name.
That keeps this module reusable for any cricket association using
either pattern, and immune to a future rule change that swaps which
grade uses which shape.

Not implemented: over-rate penalties, fines, or a junior late-start
formula -- real, distinct scenarios that exist in MYCA's documents, but
no table_lookup row currently exercises them, so no formula for them is
built here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass
class CalculationResult:
    status: Literal["computed", "refused_impossible"]
    explanation: str
    value: dict | None = None


def check_late_start_reduction(overs_lost: int, total_overs_cap: int) -> CalculationResult:
    """overs_lost: the reduction figure the caller already read off a
    retrieved late-start table's matching band. total_overs_cap: this
    grade's own total-overs figure, read from retrieved rule text."""
    if overs_lost >= total_overs_cap:
        return CalculationResult(
            status="refused_impossible",
            explanation=(
                f"A {overs_lost}-over deduction against a {total_overs_cap}-over format leaves "
                "no overs to bowl. No numeric entitlement is possible for this input."
            ),
            value={"overs_lost": overs_lost, "total_overs_cap": total_overs_cap},
        )
    return CalculationResult(
        status="computed",
        explanation=(
            f"{overs_lost} overs deducted from the late side's entitlement "
            f"({total_overs_cap} overs down to {total_overs_cap - overs_lost})."
        ),
        value={
            "overs_lost": overs_lost,
            "total_overs_cap": total_overs_cap,
            "revised_overs": total_overs_cap - overs_lost,
        },
    )


def calculate_halved_interruption_reduction(
    minutes_lost: int, minutes_per_over: int, total_overs_cap: int
) -> CalculationResult:
    """minutes_per_over and total_overs_cap: this grade's own stated
    rate and overs cap, read from retrieved rule text -- not assumed."""
    raw_overs = minutes_lost / minutes_per_over
    overs_lost = math.ceil(raw_overs)
    if overs_lost % 2 != 0:
        overs_lost += 1
    overs_off_each_side = overs_lost // 2

    if overs_off_each_side >= total_overs_cap:
        return CalculationResult(
            status="refused_impossible",
            explanation=(
                f"{minutes_lost} minutes lost / {minutes_per_over} = {raw_overs:g}, rounded up to "
                f"{overs_lost} overs, halved to {overs_off_each_side} overs off each side -- but "
                f"this format is only {total_overs_cap} overs, so no overs remain for either side. "
                "No numeric reduction is possible for this input."
            ),
            value={"overs_off_each_side": overs_off_each_side, "total_overs_cap": total_overs_cap},
        )

    rounding_note = "" if raw_overs == overs_lost and overs_lost % 2 == 0 else " (rounded up to the next even number if needed)"
    return CalculationResult(
        status="computed",
        explanation=(
            f"{minutes_lost} minutes lost / {minutes_per_over} = {raw_overs:g}, rounded up to "
            f"{overs_lost} overs{rounding_note}, then halved to {overs_off_each_side} overs "
            f"deducted from each side's own maximum ({total_overs_cap} overs down to "
            f"{total_overs_cap - overs_off_each_side} overs each)."
        ),
        value={
            "overs_lost_total": overs_lost,
            "overs_off_each_side": overs_off_each_side,
            "total_overs_cap": total_overs_cap,
            "revised_overs_each_side": total_overs_cap - overs_off_each_side,
        },
    )


def calculate_remaining_time_reduction(
    minutes_lost: int, minutes_per_over: int, match_window_minutes: int
) -> CalculationResult:
    """minutes_per_over and match_window_minutes: this grade's own
    stated rate and total match-time window, read from retrieved rule
    text -- not assumed."""
    remaining_minutes = match_window_minutes - minutes_lost

    if remaining_minutes <= 0:
        return CalculationResult(
            status="refused_impossible",
            explanation=(
                f"{minutes_lost} minutes lost meets or exceeds the entire {match_window_minutes}-"
                "minute match window, leaving no remaining time to convert into overs. No numeric "
                "overs reduction is possible for this input."
            ),
            value={"remaining_minutes": remaining_minutes},
        )

    revised_overs = remaining_minutes // minutes_per_over
    return CalculationResult(
        status="computed",
        explanation=(
            f"Remaining time between commencement of play and the {match_window_minutes}-minute "
            f"match window: {remaining_minutes} minutes. Divided by {minutes_per_over}: "
            f"{revised_overs} overs -- the revised total overs each side is entitled to bat for."
        ),
        value={"remaining_minutes": remaining_minutes, "revised_overs": revised_overs},
    )
