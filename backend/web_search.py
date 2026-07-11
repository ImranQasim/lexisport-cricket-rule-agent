"""Tavily web search: current/public information the rulebook can't
contain. Wraps the raw tavily-python client directly, not the
langchain-tavily prebuilt tool — see the approved plan for why (the
prebuilt tool's description, failure handling, and result shape would
all have needed overriding anyway to get what this project requires, so
wrapping the raw client keeps that logic visible and auditable here
instead of inside a third-party package).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from tavily import TavilyClient

MAX_RESULTS_DEFAULT = 5


@dataclass
class WebResult:
    title: str
    url: str
    content: str


class WebSearchError(Exception):
    """Raised on a Tavily API/network/auth failure. Deliberately distinct
    from a genuine zero-results outcome (which returns an empty list) so
    the tool layer can give an honest, accurate fallback message instead
    of collapsing "search is broken" and "search worked, found nothing"
    into the same misleading response."""


def web_search(query: str, max_results: int = MAX_RESULTS_DEFAULT) -> list[WebResult]:
    try:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
            include_raw_content=False,
        )
    except Exception as e:
        raise WebSearchError(str(e)) from e

    return [
        WebResult(title=r["title"], url=r["url"], content=r["content"])
        for r in response.get("results", [])
    ]
