"""ARQ worker tasks for KB ingestion — Sprint 2."""

from __future__ import annotations

import structlog

from app.db.session import _Session
from app.services.rag.ingester import ingest_article

log = structlog.get_logger()


async def ingest_kb_article(ctx: dict, article_id: str) -> dict[str, object]:
    """ARQ task: chunk + embed a KB article and persist chunks to helpdesk_rag."""
    log.info("kb_worker.ingest_start", article_id=article_id)
    async with _Session() as db:
        chunks_inserted = await ingest_article(article_id, db)
    log.info("kb_worker.ingest_done", article_id=article_id, chunks=chunks_inserted)
    return {"article_id": article_id, "chunks_inserted": chunks_inserted}


# ARQ worker settings
class WorkerSettings:
    functions = [ingest_kb_article]
    # redis_settings loaded from app.core.config at runtime
