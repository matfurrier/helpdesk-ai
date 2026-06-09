"""RAG retriever — cosine similarity search against helpdesk_rag.chunks — Sprint 2."""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag import embedder

log = structlog.get_logger()

_SIMILARITY_THRESHOLD = 0.68
_DEFAULT_TOP_K = 3


@dataclass
class RagChunk:
    chunk_id: str
    text: str
    section_path: str | None
    trust_level: str
    score: float


async def retrieve(
    query: str,
    db: AsyncSession,
    *,
    top_k: int = _DEFAULT_TOP_K,
    threshold: float = _SIMILARITY_THRESHOLD,
) -> list[RagChunk]:
    """Return top-k chunks for *query* by cosine similarity.

    Only returns chunks with similarity >= threshold and suspicious=false.
    Returns empty list on any error so the LLM proceeds without context.
    """
    if not query.strip():
        return []

    try:
        query_embedding = await embedder.embed_one(query)
    except Exception as exc:
        log.warning("retriever.embed_failed", error=str(exc))
        return []

    # pgvector: <=> is cosine distance (0 = identical, 2 = opposite)
    # similarity = 1 - distance; threshold on similarity → distance < (1 - threshold)
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    try:
        result = await db.execute(
            text(
                "SELECT id::text, text, section_path, trust_level, "  # noqa: S608
                "       1 - (embedding <=> CAST(:emb AS vector)) AS score "
                "FROM helpdesk_rag.chunks "
                "WHERE suspicious = false "
                "  AND 1 - (embedding <=> CAST(:emb AS vector)) >= :threshold "
                "ORDER BY embedding <=> CAST(:emb AS vector) "
                "LIMIT :k"
            ),
            {"emb": emb_str, "threshold": threshold, "k": top_k},
        )
        rows = result.fetchall()
    except Exception as exc:
        log.warning("retriever.query_failed", error=str(exc))
        return []

    chunks = [
        RagChunk(
            chunk_id=str(r.id),
            text=str(r.text),
            section_path=str(r.section_path) if r.section_path else None,
            trust_level=str(r.trust_level),
            score=float(r.score),
        )
        for r in rows
    ]
    log.debug("retriever.done", query_len=len(query), hits=len(chunks))
    return chunks


def chunks_to_context_blocks(chunks: list[RagChunk]) -> list[dict[str, object]]:
    """Convert RagChunks to context_blocks format for the orchestrator."""
    return [{"id": c.chunk_id, "content": c.text} for c in chunks]
