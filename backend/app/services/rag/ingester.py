"""KB article ingestion pipeline — Sprint 2.

Reads body_markdown from helpdesk.kb_article_versions, chunks it,
embeds each chunk, and persists to helpdesk_rag.chunks.
"""

from __future__ import annotations

import hashlib

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.rag import chunker, embedder

log = structlog.get_logger()


async def ingest_article(article_id: str, db: AsyncSession) -> int:
    """Ingest all chunks for an article. Returns number of chunks inserted.

    Idempotent: deletes existing chunks for the article before re-inserting.
    """
    # Fetch article + latest version body
    art_result = await db.execute(
        text(
            "SELECT a.id, a.slug, a.title, a.trust_level, a.category_id, "  # noqa: S608
            "       v.body_markdown "
            "FROM helpdesk.kb_articles a "
            "JOIN helpdesk.kb_article_versions v ON v.article_id = a.id "
            "WHERE a.id = CAST(:aid AS uuid) AND a.is_archived = false "
            "ORDER BY v.version DESC LIMIT 1"
        ),
        {"aid": article_id},
    )
    art_row = art_result.fetchone()
    if art_row is None:
        log.warning("ingester.article_not_found", article_id=article_id)
        return 0

    body_markdown = str(art_row.body_markdown)
    slug = str(art_row.slug)
    trust_level = str(art_row.trust_level)

    # Ensure a source record exists for this article
    src_result = await db.execute(
        text(
            "INSERT INTO helpdesk_rag.sources "  # noqa: S608
            "(source_type, name, config, default_trust) "
            "VALUES ('internal_kb', :name, CAST(:config AS jsonb), :trust) "
            "ON CONFLICT DO NOTHING "
            "RETURNING id"
        ),
        {
            "name": f"kb:{slug}",
            "config": f'{{"article_id": "{article_id}"}}',
            "trust": trust_level,
        },
    )
    await db.commit()

    src_row = src_result.fetchone()
    if src_row is None:
        # Already existed — fetch it
        src_fetch = await db.execute(
            text("SELECT id FROM helpdesk_rag.sources WHERE name = :name LIMIT 1"),  # noqa: S608
            {"name": f"kb:{slug}"},
        )
        src_row = src_fetch.fetchone()
        if src_row is None:
            log.error("ingester.source_not_found", slug=slug)
            return 0

    source_id = str(src_row.id)

    # Ensure document record
    doc_result = await db.execute(
        text(
            "INSERT INTO helpdesk_rag.documents "  # noqa: S608
            "(source_id, external_id, title, trust_level) "
            "VALUES (CAST(:sid AS uuid), :ext_id, :title, :trust) "
            "ON CONFLICT (source_id, external_id) DO UPDATE "
            "SET title = EXCLUDED.title, last_seen = now() "
            "RETURNING id"
        ),
        {
            "sid": source_id,
            "ext_id": article_id,
            "title": str(art_row.title),
            "trust": trust_level,
        },
    )
    await db.commit()
    doc_row = doc_result.fetchone()
    if doc_row is None:
        doc_fetch = await db.execute(
            text(
                "SELECT id FROM helpdesk_rag.documents "  # noqa: S608
                "WHERE source_id = CAST(:sid AS uuid) AND external_id = :ext_id LIMIT 1"
            ),
            {"sid": source_id, "ext_id": article_id},
        )
        doc_row = doc_fetch.fetchone()
    if doc_row is None:
        return 0

    document_id = str(doc_row.id)

    # Chunk the markdown
    chunks = chunker.chunk_markdown(body_markdown)
    if not chunks:
        return 0

    # Embed all chunks
    texts = [c.text for c in chunks]
    try:
        embeddings = await embedder.embed_texts(texts)
    except Exception as exc:
        log.error("ingester.embed_failed", article_id=article_id, error=str(exc))
        return 0

    embedding_set_id = settings.openai_embed_model

    # Delete old chunks for this document before re-inserting (idempotent)
    await db.execute(
        text(
            "DELETE FROM helpdesk_rag.chunks "  # noqa: S608
            "WHERE document_id = CAST(:did AS uuid) AND embedding_set_id = :eset"
        ),
        {"did": document_id, "eset": embedding_set_id},
    )

    # Insert new chunks
    inserted = 0
    for chunk, emb in zip(chunks, embeddings, strict=True):
        text_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"
        await db.execute(
            text(
                "INSERT INTO helpdesk_rag.chunks "  # noqa: S608
                "(document_id, source_id, position, section_path, text, text_hash, "
                " trust_level, embedding_set_id, embedding, token_count) "
                "VALUES (CAST(:did AS uuid), CAST(:sid AS uuid), :pos, :section, "
                "        :txt, :hash, :trust, :eset, CAST(:emb AS vector), :tokens) "
                "ON CONFLICT (document_id, position, embedding_set_id) DO UPDATE "
                "SET text = EXCLUDED.text, text_hash = EXCLUDED.text_hash, "
                "    embedding = EXCLUDED.embedding, token_count = EXCLUDED.token_count"
            ),
            {
                "did": document_id,
                "sid": source_id,
                "pos": chunk.position,
                "section": chunk.section_path,
                "txt": chunk.text,
                "hash": text_hash,
                "trust": trust_level,
                "eset": embedding_set_id,
                "emb": emb_str,
                "tokens": chunk.token_count,
            },
        )
        inserted += 1

    await db.commit()
    log.info("ingester.done", article_id=article_id, chunks=inserted)
    return inserted
