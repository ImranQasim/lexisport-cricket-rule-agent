"""Unit tests for backend.overs_calculations -- the deterministic, non-
LLM cricket time-lost overs arithmetic. No graph, no LLM: these test the
three arithmetic functions directly against the three pre-registered
acceptance-test rows (eval-017, eval-018, eval-019) plus boundary/
refusal cases. Every number is passed explicitly, matching how the
agent will supply them from that turn's retrieval -- no association-
specific constant lives in the module under test.
"""

from __future__ import annotations

from backend.overs_calculations import (
    calculate_halved_interruption_reduction,
    calculate_remaining_time_reduction,
    check_late_start_reduction,
)


def test_eval_019_late_start_10_minutes_3_overs_of_35_computes():
    result = check_late_start_reduction(overs_lost=3, total_overs_cap=35)

    assert result.status == "computed"
    assert result.value["revised_overs"] == 32


def test_eval_017_halved_interruption_45_minutes_halves_per_side():
    result = calculate_halved_interruption_reduction(
        minutes_lost=45, minutes_per_over=4, total_overs_cap=35
    )

    assert result.status == "computed"
    assert result.value["overs_lost_total"] == 12
    assert result.value["overs_off_each_side"] == 6
    assert result.value["revised_overs_each_side"] == 29


def test_eval_018_remaining_time_200_minutes_of_180_window_refuses():
    result = calculate_remaining_time_reduction(
        minutes_lost=200, minutes_per_over=4, match_window_minutes=180
    )

    assert result.status == "refused_impossible"
    assert "draw" not in result.explanation.lower()  # module stays association-agnostic; no rule citation
    assert result.value["remaining_minutes"] == -20


def test_halved_interruption_matches_source_worked_example_60_minutes():
    # MYCA Senior Men's Playing Rules v2, Section 5.3.2(B)'s own worked
    # example: "EG 60 minutes lost = 15 overs. Round up to 16 overs.
    # Divide overs and time lost by 2 = 8 overs/30 minutes. Each team to
    # receive 27 overs in 105 minutes."
    result = calculate_halved_interruption_reduction(
        minutes_lost=60, minutes_per_over=4, total_overs_cap=35
    )

    assert result.value["overs_lost_total"] == 16
    assert result.value["overs_off_each_side"] == 8
    assert result.value["revised_overs_each_side"] == 27


def test_late_start_boundary_6_minutes_2_overs_of_35_computes():
    # Sanity check against eval-001 (formula_arithmetic, out of session
    # scope, but same scenario/grade) -- must not regress.
    result = check_late_start_reduction(overs_lost=2, total_overs_cap=35)

    assert result.value["revised_overs"] == 33


def test_remaining_time_computes_when_time_remains():
    result = calculate_remaining_time_reduction(
        minutes_lost=100, minutes_per_over=4, match_window_minutes=180
    )

    assert result.status == "computed"
    assert result.value["remaining_minutes"] == 80
    assert result.value["revised_overs"] == 20


def test_late_start_reduction_exceeding_total_overs_refuses():
    result = check_late_start_reduction(overs_lost=35, total_overs_cap=35)

    assert result.status == "refused_impossible"


def test_halved_interruption_reduction_exceeding_total_overs_refuses():
    result = calculate_halved_interruption_reduction(
        minutes_lost=280, minutes_per_over=4, total_overs_cap=35
    )

    assert result.status == "refused_impossible"


def test_remaining_time_reduction_exactly_at_window_refuses():
    result = calculate_remaining_time_reduction(
        minutes_lost=180, minutes_per_over=4, match_window_minutes=180
    )

    assert result.status == "refused_impossible"


def test_functions_never_reference_myca_or_any_section_number():
    # Guards the module's own design invariant: no association-specific
    # fact leaks into a result's explanation text.
    results = [
        check_late_start_reduction(overs_lost=3, total_overs_cap=35),
        calculate_halved_interruption_reduction(minutes_lost=45, minutes_per_over=4, total_overs_cap=35),
        calculate_remaining_time_reduction(minutes_lost=200, minutes_per_over=4, match_window_minutes=180),
    ]
    for result in results:
        assert "MYCA" not in result.explanation
        assert "Section" not in result.explanation
