"""OpenAI text-embedding-3-small wrapper — Sprint 2."""

from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from app.core.config import settings

log = structlog.get_logger()

_BATCH_SIZE = 100


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings in batches. Returns a list of embedding vectors."""
    if not texts:
        return []

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = await client.embeddings.create(
            input=batch,
            model=settings.openai_embed_model,
        )
        all_embeddings.extend([item.embedding for item in response.data])
        log.debug("embedder.batch", batch_start=i, batch_size=len(batch))

    return all_embeddings


async def embed_one(text: str) -> list[float]:
    """Embed a single string. Convenience wrapper."""
    results = await embed_texts([text])
    return results[0]
