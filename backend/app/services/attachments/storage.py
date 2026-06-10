"""MinIO attachment storage helpers (sync SDK wrapped with asyncio.to_thread)."""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import timedelta

import structlog
from minio import Minio

from app.core.config import settings

log = structlog.get_logger()


def _client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


async def ensure_bucket() -> None:
    def _ensure() -> None:
        client = _client()
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
            log.info("minio.bucket_created", bucket=settings.minio_bucket)

    await asyncio.to_thread(_ensure)


async def put(data: bytes, ticket_id: str, original_name: str, mime_type: str) -> str:
    """Upload *data* to MinIO. Returns the stored object key."""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_name)[:100]
    key = f"tickets/{ticket_id}/{uuid.uuid4().hex}/{safe}"

    def _upload() -> None:
        _client().put_object(
            settings.minio_bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=mime_type,
        )

    await asyncio.to_thread(_upload)
    log.info("minio.put", key=key, size_bytes=len(data))
    return key


async def presigned_url(key: str, expires_seconds: int = 900) -> str:
    """Return a presigned GET URL valid for *expires_seconds* seconds."""

    def _presign() -> str:
        return _client().presigned_get_object(
            settings.minio_bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    return await asyncio.to_thread(_presign)
