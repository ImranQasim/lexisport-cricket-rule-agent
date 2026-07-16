"""Unit tests for the 2026-07-16 judge evidence-gathering fix in
backend/agent.py -- no graph, no LLM, same discipline as
test_citation_check.py.

_gather_turn_evidence must include retry_retrieval_node's broadened-search
SystemMessage, not just ToolMessages -- the judge previously validated
post-retry answers against pre-retry evidence and flagged correct answers
(finding #35's bug class, second instance).

A companion verdict-normalization fix (treat a FAIL with empty
unsupported_claims/fabricated_citations as PASS) was built and evaluated
alongside this one, then dropped before shipping: full VERIFY tracing
found it silently converted eval-047's correct FAIL (golden
expected_behavior=flag_acceptable) into a PASS, a false negative worse
than the false-positive noise it was meant to remove. See
docs/findings-log.md for the full account. Only the evidence-gathering
fix ships.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.agent import _gather_turn_evidence

RETRY_EXCERPT = (
    "[Section 5.3.3, MYCA Senior Men's Playing Rules v2, similarity 0.71]\n"
    "5.3.3 Each team shall bat for a maximum of 35 overs."
)


def _turn_with_retry() -> list:
    """Message shape of a real post-retry pass: question, first tool
    round, first draft, retry instruction (SystemMessage carrying the
    broadened excerpts -- see retry_retrieval_node), revised draft."""
    return [
        HumanMessage(content="How many overs does each team bat?"),
        AIMessage(content="", tool_calls=[{"name": "search_rules_tool", "args": {"question": "overs"}, "id": "t1"}]),
        ToolMessage(content="[Section 5.4.1, MYCA Senior Men's Playing Rules v2, similarity 0.44]\n5.4.1 ...", tool_call_id="t1", name="search_rules_tool"),
        AIMessage(content="Each team bats 35 overs (Section 5.3.3)."),
        SystemMessage(content="A verification check found problems with your previous answer. Results below.\n\n" + RETRY_EXCERPT),
        AIMessage(content="Each team bats for a maximum of 35 overs (Section 5.3.3, MYCA Senior Men's Playing Rules v2)."),
    ]


def test_turn_evidence_includes_retry_system_message():
    evidence = _gather_turn_evidence(_turn_with_retry())
    assert RETRY_EXCERPT in evidence


def test_turn_evidence_includes_tool_messages():
    evidence = _gather_turn_evidence(_turn_with_retry())
    assert "Section 5.4.1" in evidence
    assert "search_rules_tool" in evidence


def test_turn_evidence_only_counts_since_last_human():
    earlier_turn = [
        HumanMessage(content="earlier question"),
        SystemMessage(content="stale retry evidence from an earlier turn"),
        AIMessage(content="earlier answer"),
    ]
    evidence = _gather_turn_evidence(earlier_turn + _turn_with_retry())
    assert "stale retry evidence" not in evidence
