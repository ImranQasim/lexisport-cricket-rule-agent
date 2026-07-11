"""FastAPI HTTP API wrapping the LangGraph agent from backend.agent.

Auth, request/response shaping, and process lifecycle only — no graph,
tool, judge, or prompt logic lives here; build_graph() is called
unchanged per request, scoped by the request body's association_id/
grade_scope instead of CLI flags.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Literal, Union

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from supabase import Client, create_client

from backend.agent import build_graph

load_dotenv()

# Makes backend.agent's existing logging.info(...) calls (agent_node,
# judge_node, retry_reformulate latency/token-usage lines) visible in
# Render's log stream. These calls already exist in agent.py; the CLI
# never configures logging, so they're silent there today.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

API_KEY = os.environ["API_KEY"]

# Interim, explicit allowlist. docs/submission.md's target end state is
# Supabase Auth (JWT); this is the approved interim step. Placeholder
# Vercel origin below must be replaced once the frontend has a real URL.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://REPLACE-ME-lexisport-frontend.vercel.app",
]


# ---------------------------------------------------------------------------
# Auth: static API key today, swappable for Supabase JWT verification later
# with zero route changes — every route depends on require_auth's return
# type (CallerIdentity), not on how it was derived.
# ---------------------------------------------------------------------------


class CallerIdentity(BaseModel):
    """The authenticated caller. Today: always the same static-key
    subject. Once auth is swapped for Supabase JWT verification, this
    becomes the JWT's `sub` claim — no route signature changes."""

    subject: str = Field(..., description="Stable identifier for the authenticated caller.")


_api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Static API key for this deployment. Send as the X-API-Key header.",
)


async def require_auth(api_key: str | None = Security(_api_key_header)) -> CallerIdentity:
    if api_key is None or not secrets.compare_digest(api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Missing or invalid API key. Send it as the X-API-Key header.")
    return CallerIdentity(subject="static-api-key-caller")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    association_id: uuid.UUID = Field(
        ..., description="associations.id (uuid). Validated to exist before the agent runs."
    )
    thread_id: str = Field(
        ...,
        min_length=1,
        description="Conversation thread id. Reuse the same value to continue a conversation; use a new value to start fresh.",
    )
    question: str = Field(..., min_length=1, description="The question or message for this turn.")
    grade_scope: Literal["junior", "senior_men", "senior_women"] | None = Field(
        default=None,
        description="Trusted, caller-supplied grade filter for this whole conversation. The model cannot set or change it. Omit to search all grades.",
    )


class RuleCitation(BaseModel):
    type: Literal["rule"] = "rule"
    section_number: str = Field(..., description="Section number as cited in the answer, e.g. '3.3' or 'J15'.")
    document: str | None = Field(
        default=None,
        description="Document name and version as one combined string, e.g. 'MYCA Senior Men's Playing Rules v2'. Null if the draft cited a section without naming a document.",
    )


class WebCitation(BaseModel):
    type: Literal["web"] = "web"
    url: str = Field(..., description="Source URL as cited in the answer.")


Citation = Annotated[Union[RuleCitation, WebCitation], Field(discriminator="type")]


class ChatResponse(BaseModel):
    thread_id: str = Field(..., description="Echoes the request's thread_id.")
    answer: str = Field(..., description="The agent's final answer text for this turn.")
    citations: list[Citation] = Field(
        default_factory=list, description="Structured citations extracted from the answer text, deduplicated."
    )
    needs_human_review: bool = Field(
        ..., description="True if the judge could not verify this answer after one retry."
    )
    flagged_claims: list[str] = Field(
        default_factory=list,
        description="Unsupported claims the judge flagged. Populated only when needs_human_review is true.",
    )
    flagged_citations: list[str] = Field(
        default_factory=list,
        description="Fabricated citations the judge flagged. Populated only when needs_human_review is true.",
    )
    judge_reasoning: str | None = Field(
        default=None,
        description="The judge's own explanation for its verdict, whenever the judge ran this turn. Null if the judge was skipped (a greeting).",
    )
    arithmetic_ok: bool | None = Field(
        default=None,
        description="True if the judge checked arithmetic in the answer and it was correct, false if checked and wrong, null if no arithmetic was present or the judge did not run this turn.",
    )


# ---------------------------------------------------------------------------
# Citation extraction — regex against AGENT_SYSTEM_PROMPT's fixed, unchanged
# citation format. Not a general parser: matches exactly the two formats
# the frozen prompt produces.
# ---------------------------------------------------------------------------

_RULE_CITATION_RE = re.compile(r"\(Section\s+([\w.]+)(?:,\s*([^)]+))?\)")
_WEB_CITATION_RE = re.compile(r"\(Source:\s*(\S+)\)")


def _extract_citations(answer_text: str) -> list[RuleCitation | WebCitation]:
    # section_number is bounded to word characters and dots only (matches
    # real section numbers like "5.3.1" or "J15") so the match stops at the
    # citation's own closing paren instead of a bare "(Section X)" (missing
    # the ", document" the prompt asks for, which happens occasionally)
    # spanning greedily into a second, unrelated citation later in the text.
    citations: list[RuleCitation | WebCitation] = []
    seen: set[tuple[str, str, str | None]] = set()

    for match in _RULE_CITATION_RE.finditer(answer_text):
        section_number = match.group(1).strip()
        document = match.group(2).strip() if match.group(2) else None
        key = ("rule", section_number, document)
        if key not in seen:
            seen.add(key)
            citations.append(RuleCitation(section_number=section_number, document=document))

    for url in _WEB_CITATION_RE.findall(answer_text):
        key = ("web", url.strip(), None)
        if key not in seen:
            seen.add(key)
            citations.append(WebCitation(url=url.strip()))

    return citations


# ---------------------------------------------------------------------------
# Trust boundary: association_id/grade_scope come from the request body,
# validated before the graph is built or invoked.
# ---------------------------------------------------------------------------


def _supabase_client() -> Client:
    # Deliberately duplicated 3-line construction, matching this repo's
    # existing convention (backend.retrieval._client()) of not sharing a
    # client helper across backend/ modules.
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])


def _association_exists(association_id: str) -> bool:
    response = (
        _supabase_client().table("associations").select("id").eq("id", association_id).maybe_single().execute()
    )
    return response is not None and response.data is not None


# ---------------------------------------------------------------------------
# Lifecycle: one AsyncConnectionPool + one AsyncPostgresSaver opened once at
# startup, not per request and not the CLI's per-invocation open/close.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = AsyncConnectionPool(
        conninfo=os.environ["DATABASE_URL"],
        min_size=2,
        max_size=10,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
    )
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()  # idempotent

    app.state.pool = pool
    app.state.checkpointer = checkpointer
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="Lexi Sport Cricket Rules Agent API",
    description=(
        "HTTP API for the LangGraph cricket rules agent: retrieval-grounded answers with "
        "citations, a judge/retry loop, and a human-review flag. See docs/submission.md "
        "for the full architecture."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)


@app.get(
    "/health",
    tags=["health"],
    summary="Liveness check",
    description=(
        "Unauthenticated liveness check. Confirms the process is up and startup (opening the "
        "Postgres connection pool, running checkpointer setup) completed — it does not make a "
        "live database or LLM-gateway call on every request, so a transient downstream outage "
        "doesn't fail Render's health check and cycle this service."
    ),
)
async def health(request: Request) -> dict:
    checkpointer_ready = getattr(request.app.state, "checkpointer", None) is not None
    return {"status": "ok" if checkpointer_ready else "starting", "checkpointer_ready": checkpointer_ready}


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    tags=["chat"],
    summary="Send one turn of a conversation to the cricket rules agent",
    description=(
        "Runs one turn of the agent graph for a given association and thread. association_id "
        "must belong to an existing association (404 otherwise). Note: 'must belong to the "
        "authenticated caller' is not enforced — there is no per-user ownership model yet, since "
        "auth today is a single static key, not per-user."
    ),
)
async def chat(
    req: ChatRequest, request: Request, caller: CallerIdentity = Depends(require_auth)
) -> ChatResponse:
    association_id = str(req.association_id)

    if not _association_exists(association_id):
        raise HTTPException(status_code=404, detail=f"Unknown association_id: {association_id}")

    graph = build_graph(association_id, request.app.state.checkpointer, grade_scope=req.grade_scope)
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        result = await graph.ainvoke({"messages": [HumanMessage(content=req.question)]}, config=config)
    except Exception:
        logging.exception(
            "chat: graph.ainvoke failed association_id=%s thread_id=%s", association_id, req.thread_id
        )
        raise HTTPException(status_code=500, detail="The agent failed to produce an answer. Please try again.")

    needs_human_review = bool(result.get("needs_human_review", False))
    messages = result["messages"]
    # flag_and_finalize_node appends a banner-wrapped AIMessage last when
    # flagged; messages[-2] is the actual draft the judge evaluated, which
    # is what belongs in `answer` — the banner's information is already in
    # needs_human_review/flagged_claims/flagged_citations below.
    answer_text = messages[-2].content if needs_human_review else messages[-1].content

    verdict = result.get("judge_verdict") or {}

    return ChatResponse(
        thread_id=req.thread_id,
        answer=answer_text,
        citations=_extract_citations(answer_text),
        needs_human_review=needs_human_review,
        flagged_claims=verdict.get("unsupported_claims", []) if needs_human_review else [],
        flagged_citations=verdict.get("fabricated_citations", []) if needs_human_review else [],
        judge_reasoning=verdict.get("reasoning"),
        arithmetic_ok=verdict.get("arithmetic_ok"),
    )
