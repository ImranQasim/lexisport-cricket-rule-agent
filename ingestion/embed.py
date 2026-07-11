"""Batched embedding calls, routed through the local LiteLLM proxy.

Never calls OpenAI directly — base_url points at the local gateway
(gateway/config.yaml), which holds the real OPENAI_API_KEY. The api_key
passed to the client here is unused padding: the proxy has no master_key
configured, so it never checks it.
"""

from __future__ import annotations

import os

from openai import OpenAI

PROXY_BASE_URL = os.environ.get("LITELLM_PROXY_BASE_URL", "http://localhost:4000")
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 96


def _client() -> OpenAI:
    return OpenAI(base_url=PROXY_BASE_URL, api_key="routed-through-proxy")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in batches, preserving input order."""
    if not texts:
        return []

    client = _client()
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        # OpenAI's API guarantees response.data is returned in the same
        # order as the input batch.
        embeddings.extend(item.embedding for item in response.data)

    return embeddings
