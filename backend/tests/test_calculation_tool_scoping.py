"""Unit tests for the calculation-tool coverage map in backend.agent --
each tool must refuse to compute when the closure-captured grade_scope
isn't one it covers (built after eval-025: a Junior question reached
check_late_start_reduction_tool, built for a different grade's late-
start table, and got a rubber-stamped wrong number back)."""

from __future__ import annotations

from backend.agent import (
    make_calculate_halved_interruption_reduction_tool,
    make_calculate_remaining_time_reduction_tool,
    make_check_late_start_reduction_tool,
)


def test_check_late_start_reduction_out_of_scope_for_junior():
    tool = make_check_late_start_reduction_tool("junior")
    result = tool.invoke({"overs_lost": 2, "total_overs_cap": 60})
    assert "OUT OF SCOPE" in result


def test_check_late_start_reduction_computes_for_senior_men():
    tool = make_check_late_start_reduction_tool("senior_men")
    result = tool.invoke({"overs_lost": 3, "total_overs_cap": 35})
    assert "OUT OF SCOPE" not in result
    assert "32" in result


def test_halved_interruption_out_of_scope_for_senior_women():
    tool = make_calculate_halved_interruption_reduction_tool("senior_women")
    result = tool.invoke({"minutes_lost": 45, "minutes_per_over": 4, "total_overs_cap": 35})
    assert "OUT OF SCOPE" in result


def test_halved_interruption_computes_for_senior_men():
    tool = make_calculate_halved_interruption_reduction_tool("senior_men")
    result = tool.invoke({"minutes_lost": 45, "minutes_per_over": 4, "total_overs_cap": 35})
    assert "OUT OF SCOPE" not in result
    assert "29" in result


def test_remaining_time_out_of_scope_for_senior_men():
    tool = make_calculate_remaining_time_reduction_tool("senior_men")
    result = tool.invoke({"minutes_lost": 100, "minutes_per_over": 4, "match_window_minutes": 180})
    assert "OUT OF SCOPE" in result


def test_remaining_time_computes_for_senior_women():
    tool = make_calculate_remaining_time_reduction_tool("senior_women")
    result = tool.invoke({"minutes_lost": 100, "minutes_per_over": 4, "match_window_minutes": 180})
    assert "OUT OF SCOPE" not in result
    assert "20" in result


def test_no_grade_scope_stays_permissive():
    """grade_scope=None (ambiguous-grade sessions, e.g. eval-015) can't be
    scope-checked, so every tool stays computable rather than refusing."""
    tool = make_check_late_start_reduction_tool(None)
    result = tool.invoke({"overs_lost": 3, "total_overs_cap": 35})
    assert "OUT OF SCOPE" not in result
