"""LangGraph agent wrapping the baseline retrieval as a tool, with
Postgres-backed conversation memory.

Scope boundary: no web search, no judge node, no retry logic here. Those
get added to this same graph in later steps. This step delivers exactly
two things: the LLM decides when to call search_rules (instead of the
baseline's hardcoded retrieve-then-answer), and conversation memory via
the LangGraph Postgres checkpointer.

backend.retrieval.search_rules is called unchanged — no retrieval logic
lives in this file.
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


def build_graph(association_id: str, checkpointer: BaseCheckpointSaver, grade_scope: str | None = None):
    """Builds and compiles the agent graph, scoped to one association_id
    (and optionally one grade_scope) via the tool closure above. Neither
    ever enters AgentState — only messages do, which is what the
    checkpointer persists."""
    search_rules_tool = make_search_rules_tool(association_id, grade_scope=grade_scope)
    tools = [search_rules_tool]

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
