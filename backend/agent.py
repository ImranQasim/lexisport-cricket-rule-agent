"""LangGraph agent wrapping the baseline retrieval and Tavily web search
as tools, with Postgres-backed conversation memory.

Scope boundary: no judge node, no retry logic here — those get added to
this same graph in a later step. backend.retrieval.search_rules and
backend.web_search.web_search are called unchanged — no retrieval or
search logic lives in this file, only tool wrapping and graph wiring.
"""

from __future__ import annotations

import os
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from backend.agent_prompts import AGENT_SYSTEM_PROMPT
from backend.retrieval import search_rules
from backend.web_search import WebSearchError, web_search

PROXY_BASE_URL = os.environ.get("LITELLM_PROXY_BASE_URL", "http://localhost:4000")
CHAT_MODEL = "gpt-4o-mini"


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


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


def build_graph(association_id: str, checkpointer: BaseCheckpointSaver, grade_scope: str | None = None):
    """Builds and compiles the agent graph, scoped to one association_id
    (and optionally one grade_scope) via the tool closure above. Neither
    ever enters AgentState — only messages do, which is what the
    checkpointer persists. web_search_tool has no trusted parameter to
    hide (a search query isn't a scoping/permission value), so it's a
    plain module-level tool rather than a closure factory."""
    search_rules_tool = make_search_rules_tool(association_id, grade_scope=grade_scope)
    tools = [search_rules_tool, web_search_tool]

    llm = ChatOpenAI(model=CHAT_MODEL, base_url=PROXY_BASE_URL, api_key="routed-through-proxy")
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        # The system prompt is prepended fresh on every call, never
        # persisted into checkpointed state. Only human/AI/tool messages
        # accumulate in state["messages"] via the add_messages reducer,
        # since a node's return value is all that gets merged in.
        messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + list(state["messages"])
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
