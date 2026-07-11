"""Baseline retrieval: filtered similarity search over rule_chunks.

association_id is filtered at the SQL level, inside the
match_rule_chunks RPC function (see
supabase/migrations/20260711043546_create_match_rule_chunks_function.sql)
— not a Python post-filter. This guarantees a query against an
association with zero chunks returns zero rows from the database
itself, and that ranking always happens within the correct
association's chunks only, never crowded out by another association's
chunks ranking higher globally.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI
from supabase import Client, create_client

PROXY_BASE_URL = os.environ.get("LITELLM_PROXY_BASE_URL", "http://localhost:4000")
EMBEDDING_MODEL = "text-embedding-3-small"

# Enough to cover a multi-clause answer (MYCA rules frequently need 2-3
# adjacent sub-clauses together) without diluting the prompt with chunks
# unlikely to be read. Named constant, not a magic number, since later
# evaluation varies this.
TOP_K_DEFAULT = 5


@dataclass
class RetrievedChunk:
    chunk: str
    section_number: str | None
    doc_name: str
    doc_version: str | None
    content_type: str
    grade_scope: str | None
    similarity: float


def _client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])


def _embed_query(question: str) -> list[float]:
    """Single-query embedding via the local LiteLLM proxy. Deliberately
    not shared with ingestion/embed.py — backend/ must not depend on
    ingestion/'s heavy Docling/torch dependency stack, since backend/ is
    what gets deployed as the FastAPI service and ingestion/ is a
    manually-run CLI tool."""
    client = OpenAI(base_url=PROXY_BASE_URL, api_key=os.environ.get("LITELLM_PROXY_API_KEY", "routed-through-proxy"))
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[question])
    return response.data[0].embedding


def search_rules(
    question: str,
    association_id: str,
    top_k: int = TOP_K_DEFAULT,
    grade_scope: str | None = None,
) -> list[RetrievedChunk]:
    """Embed the question, then run a hard-filtered similarity search
    over rule_chunks for exactly one association, via the
    match_rule_chunks RPC function (join to documents for
    doc_name/doc_version happens inside that function).

    grade_scope is optional. When given (junior | senior_men |
    senior_women), it filters to that grade's chunks plus grade-agnostic
    ones (the two operational forms). When omitted, searches across all
    of the association's grades — this was the only behavior available
    before more than one grade's documents were ingested for the same
    association, and cross-grade contamination becomes a real risk if
    grade_scope is left off once multiple grades exist."""
    embedding = _embed_query(question)
    response = (
        _client()
        .rpc(
            "match_rule_chunks",
            {
                "p_association_id": association_id,
                "p_query_embedding": embedding,
                "p_top_k": top_k,
                "p_grade_scope": grade_scope,
            },
        )
        .execute()
    )
    return [RetrievedChunk(**row) for row in response.data]
