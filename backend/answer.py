"""Baseline answer: one search_rules() call, then exactly one chat
completion through the local LiteLLM proxy. No agent framework, no
judge node, no memory, no web search — this is the floor later
pipelines get measured against.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI

from backend.prompts import NO_RELEVANT_CONTEXT_PLACEHOLDER, SYSTEM_PROMPT
from backend.retrieval import RetrievedChunk, TOP_K_DEFAULT, search_rules

PROXY_BASE_URL = os.environ.get("LITELLM_PROXY_BASE_URL", "http://localhost:4000")
CHAT_MODEL = "gpt-4o-mini"

# Cosine similarity floor. Conservative on purpose: for a rules-citation
# tool, a false "not covered" (threshold too high) just costs a rephrase,
# while a false confident citation (threshold too low) is the real
# liability — someone could apply a wrong rule on the field believing
# it's grounded. Based on today's ingestion VERIFY (d): genuinely
# relevant chunks landed at 0.55-0.65 similarity for a clearly-covered
# question, so 0.3 admits "plausibly relevant, let the LLM judge" while
# still excluding near-random noise.
SIMILARITY_THRESHOLD = 0.3


@dataclass
class AnswerResult:
    answer: str
    retrieved_chunks: list[RetrievedChunk]


def _build_context(chunks: list[RetrievedChunk]) -> str:
    relevant = [c for c in chunks if c.similarity >= SIMILARITY_THRESHOLD]
    if not relevant:
        return NO_RELEVANT_CONTEXT_PLACEHOLDER
    return "\n\n".join(
        f"[Section {c.section_number}, {c.doc_name} {c.doc_version or ''}]\n{c.chunk}" for c in relevant
    )


def answer(
    question: str,
    association_id: str,
    top_k: int = TOP_K_DEFAULT,
    grade_scope: str | None = None,
) -> AnswerResult:
    chunks = search_rules(question, association_id, top_k=top_k, grade_scope=grade_scope)
    context = _build_context(chunks)

    prompt = SYSTEM_PROMPT.replace("{context}", context).replace("{question}", question)

    client = OpenAI(base_url=PROXY_BASE_URL, api_key="routed-through-proxy")
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    answer_text = response.choices[0].message.content

    return AnswerResult(answer=answer_text, retrieved_chunks=chunks)
