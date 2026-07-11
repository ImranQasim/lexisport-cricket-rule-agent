"""LangGraph agent wrapping the baseline retrieval and Tavily web search
as tools, with Postgres-backed conversation memory, a judge node, one
retry with broadened (multi-query) retrieval, and a human-review flag.

backend.retrieval.search_rules and backend.web_search.web_search are
called unchanged — no retrieval or search logic lives in this file,
only tool wrapping, judge/retry wiring, and graph wiring.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from backend.agent_prompts import AGENT_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, REFORMULATION_SYSTEM_PROMPT
from backend.retrieval import RetrievedChunk, search_rules
from backend.web_search import WebSearchError, web_search

PROXY_BASE_URL = os.environ.get("LITELLM_PROXY_BASE_URL", "http://localhost:4000")
CHAT_MODEL = "gpt-4o-mini"
JUDGE_MODEL = "gpt-4o-mini"  # distinct constant: same value today, judge may be upgraded independently later
REFORMULATION_COUNT = 2  # extra reformulated queries beyond the original, for the one retry
RETRY_TOP_K = 5  # top_k per query on retry — same as retrieval.TOP_K_DEFAULT, unchanged
RETRY_MERGED_CHUNK_CAP = 8  # cap on deduped/merged chunks across all retry queries


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    retry_count: int
    judge_verdict: dict | None
    needs_human_review: bool


class JudgeVerdict(BaseModel):
    """Structured verdict the judge LLM returns for one agent turn."""

    verdict: Literal["PASS", "FAIL"]
    unsupported_claims: list[str] = Field(default_factory=list)
    fabricated_citations: list[str] = Field(default_factory=list)
    arithmetic_ok: bool | None = None
    reasoning: str


def _messages_since_last_human(messages: list) -> list:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i + 1 :]
    return list(messages)


_GREETING_RE = re.compile(
    r"^(hi|hi there|hiya|hello|hello there|hey|hey there|yo|greetings|"
    r"good\s+(morning|afternoon|evening|day)|thanks|thank\s+you|cheers|"
    r"bye|goodbye|good\s*bye|see\s+you)[\s!.,]*$",
    re.IGNORECASE,
)


def _is_greeting(question: str) -> bool:
    """Narrow, deliberately conservative: only strings that are
    themselves just a greeting/farewell/thanks. Anything else, including
    broader small talk, an honest fallback, or a substantive answer with
    no tool call, now goes through judge — the judge must see every
    non-tool-call answer that isn't trivially a greeting, since a
    fabricated claim can appear even when the model never calls a tool
    (this is exactly what closes the F1 gap where an uncited "generally
    accepted" claim slipped through unflagged on a turn with zero tool
    calls)."""
    return bool(_GREETING_RE.match(question.strip()))


def _most_recent_human_question(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    raise ValueError("no HumanMessage found in state")


def _gather_tool_evidence(messages: list) -> str:
    return "\n\n".join(
        f"--- From {m.name or 'unknown tool'} ---\n{m.content}"
        for m in _messages_since_last_human(messages)
        if isinstance(m, ToolMessage)
    )


def make_search_rules_tool(association_id: str, grade_scope: str | None = None):
    """Closure-based tool factory. Both association_id and grade_scope
    are captured here, at graph-build time, from a trusted caller (the
    CLI's --association-id/--grade-scope arguments today; frontend-
    supplied values once this is behind an API). Neither is a parameter
    of the inner tool function, so neither appears in the tool's schema
    and the LLM can neither read nor set them — verified empirically
    during planning by printing the actual JSON schema LangChain
    generates for a tool built this way.

    grade_scope started out as an LLM-controlled parameter (the model
    could pass junior/senior_men/senior_women per call). VERIFY (a)'s
    trial runs showed why that was wrong: 3 of 7 trials asking a clearly
    senior-grade question retrieved and answered from the Junior
    document instead, because the model called the tool without setting
    grade_scope and cross-grade similarity search surfaced a
    superficially-matching but wrong-grade chunk. This is the exact
    cross-grade contamination risk the match_rule_chunks SQL filter was
    built to prevent, reintroduced at the agent layer by letting the
    model choose the filter. Same principle as association_id: a
    trusted scoping parameter comes from the caller, never the model. If
    grade is genuinely ambiguous in a future version, that's a
    clarifying question back to the user, not a model guess — not
    implemented here, out of this task's scope."""

    @tool
    def search_rules_tool(question: str) -> str:
        """Search this cricket association's official rule documents
        (playing conditions and operational procedures) for content
        relevant to the question.

        Call this for ANY question that depends on the association's
        rules, including specific playing conditions, fines,
        eligibility, and procedures, AND any calculation, adjustment, or
        numeric outcome that follows from those rules, for example overs
        lost to time, penalty runs, forfeit fines, or retirement scores.
        A question that requires arithmetic based on a rule still needs
        this tool first, to find the rule and its numbers — do not treat
        "this needs a calculation" as a reason to skip searching the
        rules. Only skip this tool for greetings, small talk, or
        questions with nothing to do with cricket rules at all.

        Returns the most relevant excerpts, each with its section,
        source document, and version.

        Args:
            question: the question or topic to search for.
        """
        chunks = search_rules(question, association_id, grade_scope=grade_scope)
        if not chunks:
            return "No matching rule excerpts were found."
        return "\n\n".join(
            f"[Section {c.section_number}, {c.doc_name} {c.doc_version or ''}, similarity {c.similarity:.2f}]\n{c.chunk}"
            for c in chunks
        )

    return search_rules_tool


@tool
def web_search_tool(query: str) -> str:
    """Search the public internet for current information that this
    association's rule documents cannot contain: fixtures, results,
    news, weather, other organizations' current policies (for example
    Cricket Australia, ICC, MCC), current officeholders, or anything
    that changes over time and isn't part of a fixed rule document.

    Do not use this for questions about the association's own playing
    conditions, fines, eligibility, procedures, formats, or any
    calculation derived from those rules, even if the question also
    names something public-sounding, a different organization, a date,
    a place. Those still go to search_rules_tool. If a question has
    both a rules component and a genuinely public component, call both
    tools.

    Returns a short list of web results, each with a title, source URL,
    and a content snippet. Cite the source URL for anything you state
    from these results.

    Args:
        query: the search query.
    """
    try:
        results = web_search(query)
    except WebSearchError:
        return "Web search is currently unavailable. Could not retrieve current information for this query."
    if not results:
        return "No current web results were found for this query."
    return "\n\n".join(f"[{r.title}]({r.url})\n{r.content}" for r in results)


def make_judge_node():
    judge_llm = ChatOpenAI(
        model=JUDGE_MODEL,
        base_url=PROXY_BASE_URL,
        api_key=os.environ.get("LITELLM_PROXY_API_KEY", "routed-through-proxy"),
    )
    judge_structured = judge_llm.with_structured_output(JudgeVerdict, include_raw=True)

    def judge_node(state: AgentState) -> dict:
        messages = state["messages"]
        question = _most_recent_human_question(messages)
        draft_answer = messages[-1].content
        evidence = _gather_tool_evidence(messages)
        judge_messages = [
            SystemMessage(content=JUDGE_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Question: {question}\n\n"
                    f"Retrieved evidence:\n{evidence or '(no retrieved evidence found for this turn)'}\n\n"
                    f"Draft answer to check:\n{draft_answer}\n\n"
                    "Check the draft answer against the retrieved evidence above using the three checks in "
                    "your instructions, and return your structured verdict."
                )
            ),
        ]

        t0 = time.monotonic()
        try:
            result = judge_structured.invoke(judge_messages)
        except Exception as exc:
            logging.info("judge_node ERROR model=%s latency=%.2fs error=%r", JUDGE_MODEL, time.monotonic() - t0, exc)
            return {
                "judge_verdict": {
                    "verdict": "FAIL",
                    "unsupported_claims": [],
                    "fabricated_citations": [],
                    "arithmetic_ok": None,
                    "reasoning": f"Judge call failed and could not be verified: {exc!r}",
                    "judge_error": True,
                }
            }

        elapsed = time.monotonic() - t0
        raw, parsed, parsing_error = result["raw"], result["parsed"], result["parsing_error"]
        usage = getattr(raw, "response_metadata", {}).get("token_usage", {})

        if parsing_error is not None or parsed is None:
            logging.info("judge_node PARSE_ERROR latency=%.2fs tokens=%s error=%r", elapsed, usage, parsing_error)
            return {
                "judge_verdict": {
                    "verdict": "FAIL",
                    "unsupported_claims": [],
                    "fabricated_citations": [],
                    "arithmetic_ok": None,
                    "reasoning": f"Judge output could not be parsed: {parsing_error!r}",
                    "judge_error": True,
                }
            }

        logging.info("judge_node verdict=%s latency=%.2fs tokens=%s", parsed.verdict, elapsed, usage)
        verdict_dict = parsed.model_dump()
        verdict_dict["judge_error"] = False
        return {"judge_verdict": verdict_dict}

    return judge_node


def make_retry_retrieval_node(association_id: str, grade_scope: str | None = None):
    reformulate_llm = ChatOpenAI(
        model=CHAT_MODEL,
        base_url=PROXY_BASE_URL,
        api_key=os.environ.get("LITELLM_PROXY_API_KEY", "routed-through-proxy"),
    )

    def _reformulate(question: str) -> list[str]:
        t0 = time.monotonic()
        try:
            response = reformulate_llm.invoke(
                [SystemMessage(content=REFORMULATION_SYSTEM_PROMPT), HumanMessage(content=question)]
            )
            logging.info(
                "retry_reformulate latency=%.2fs tokens=%s",
                time.monotonic() - t0,
                response.response_metadata.get("token_usage", {}),
            )
            lines = [line.strip() for line in response.content.splitlines() if line.strip()]
            return lines[:REFORMULATION_COUNT]
        except Exception as exc:
            logging.info("retry_reformulate ERROR latency=%.2fs error=%r", time.monotonic() - t0, exc)
            return []

    def retry_retrieval_node(state: AgentState) -> dict:
        question = _most_recent_human_question(state["messages"])
        queries = [question] + _reformulate(question)

        merged: dict[tuple[str | None, str], RetrievedChunk] = {}
        for q in queries:
            for c in search_rules(q, association_id, grade_scope=grade_scope, top_k=RETRY_TOP_K):
                key = (c.section_number, c.doc_name)
                if key not in merged or c.similarity > merged[key].similarity:
                    merged[key] = c
        chunks = sorted(merged.values(), key=lambda c: c.similarity, reverse=True)[:RETRY_MERGED_CHUNK_CAP]

        formatted = (
            "\n\n".join(
                f"[Section {c.section_number}, {c.doc_name} {c.doc_version or ''}, similarity {c.similarity:.2f}]\n{c.chunk}"
                for c in chunks
            )
            if chunks
            else "No matching rule excerpts were found, even after searching with reformulated phrasings."
        )

        verdict = state.get("judge_verdict") or {}
        problems = "; ".join(verdict.get("unsupported_claims", []) + verdict.get("fabricated_citations", []))
        instruction = SystemMessage(
            content=(
                "A verification check found problems with your previous answer"
                + (f" ({problems})" if problems else "")
                + f". The rules were searched again using {len(queries)} different phrasings of the question "
                "(broadened search, not just the same query repeated) — results below. Revise your answer using "
                "ONLY what is supported by these excerpts or by web results already retrieved this turn. Do not "
                "restate the earlier unsupported claim in different words, and do not answer from general cricket "
                "knowledge if these excerpts still don't cover it — say so honestly instead.\n\n" + formatted
            )
        )
        return {"messages": [instruction], "retry_count": state.get("retry_count", 0) + 1}

    return retry_retrieval_node


def flag_and_finalize_node(state: AgentState) -> dict:
    verdict = state.get("judge_verdict") or {}
    draft_answer = state["messages"][-1].content
    unsupported = verdict.get("unsupported_claims", [])
    fabricated = verdict.get("fabricated_citations", [])

    lines = [
        "[NEEDS HUMAN REVIEW] This answer could not be fully verified and should be checked by a person "
        "before being relied on.",
        "",
        draft_answer,
    ]
    if unsupported or fabricated:
        lines += ["", "Flagged during verification:"]
        lines += [f"- [UNVERIFIED CLAIM] {c}" for c in unsupported]
        lines += [f"- [UNVERIFIED CITATION] {c}" for c in fabricated]
    else:
        lines += ["", f"Flagged during verification: {verdict.get('reasoning', 'no reasoning available')}"]

    return {"messages": [AIMessage(content="\n".join(lines))], "needs_human_review": True}


def route_after_agent(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    if _is_greeting(_most_recent_human_question(state["messages"])):
        return END
    return "judge"


def route_after_judge(state: AgentState) -> str:
    verdict = state.get("judge_verdict") or {}
    if verdict.get("judge_error"):
        return "flag_and_finalize"
    if verdict.get("verdict") == "PASS":
        return END
    if state.get("retry_count", 0) == 0:
        return "retry_retrieval"
    return "flag_and_finalize"


def build_graph(association_id: str, checkpointer: BaseCheckpointSaver, grade_scope: str | None = None):
    """Builds and compiles the agent graph, scoped to one association_id
    (and optionally one grade_scope) via the tool closures above. Neither
    ever enters AgentState — only messages (and the judge/retry
    bookkeeping fields) do, which is what the checkpointer persists.
    web_search_tool has no trusted parameter to hide (a search query
    isn't a scoping/permission value), so it's a plain module-level tool
    rather than a closure factory."""
    search_rules_tool = make_search_rules_tool(association_id, grade_scope=grade_scope)
    tools = [search_rules_tool, web_search_tool]

    llm = ChatOpenAI(
        model=CHAT_MODEL,
        base_url=PROXY_BASE_URL,
        api_key=os.environ.get("LITELLM_PROXY_API_KEY", "routed-through-proxy"),
    )
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        # The system prompt is prepended fresh on every call, never
        # persisted into checkpointed state. Only human/AI/tool/retry
        # messages accumulate in state["messages"] via the add_messages
        # reducer, since a node's return value is all that gets merged in.
        messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + list(state["messages"])
        t0 = time.monotonic()
        response = llm_with_tools.invoke(messages)
        logging.info(
            "agent_node latency=%.2fs tokens=%s",
            time.monotonic() - t0,
            response.response_metadata.get("token_usage", {}),
        )
        return {"messages": [response]}

    judge_node = make_judge_node()
    retry_retrieval_node = make_retry_retrieval_node(association_id, grade_scope=grade_scope)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("judge", judge_node)
    graph.add_node("retry_retrieval", retry_retrieval_node)
    graph.add_node("flag_and_finalize", flag_and_finalize_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "judge": "judge", END: END})
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges(
        "judge",
        route_after_judge,
        {"retry_retrieval": "retry_retrieval", "flag_and_finalize": "flag_and_finalize", END: END},
    )
    graph.add_edge("retry_retrieval", "agent")
    graph.add_edge("flag_and_finalize", END)

    return graph.compile(checkpointer=checkpointer)
