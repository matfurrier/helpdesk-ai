"""Redis-backed encrypted PII token store — Sprint 1.

Stores the pii_map (token → original) produced by redactor.py, encrypted with
Fernet (AES-128-CBC + HMAC-SHA256) under the key derived from settings.SECRET_KEY.

Key: pii:{conversation_id}  TTL: settings.pii_map_ttl_seconds (default 24 h).
"""

from __future__ import annotations

import json

import structlog
from cryptography.fernet import Fernet, InvalidToken
from redis.asyncio import Redis

from app.core.config import settings

log = structlog.get_logger()

_TOKEN_RE_PREFIX = "[PII_"  # noqa: S105
_fernet_instance: Fernet | None = None


def _fernet() -> Fernet:
    global _fernet_instance  # noqa: PLW0603
    if _fernet_instance is None:
        _fernet_instance = Fernet(settings.fernet_key)
    return _fernet_instance


def _redis_key(conversation_id: str) -> str:
    return f"pii:{conversation_id}"


class TokenMap:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def store(self, conversation_id: str, pii_map: dict[str, str]) -> None:
        """Encrypt and store pii_map with TTL. No-op if pii_map is empty."""
        if not pii_map:
            return
        payload = json.dumps(pii_map).encode()
        encrypted = _fernet().encrypt(payload)
        key = _redis_key(conversation_id)
        await self._redis.set(key, encrypted, ex=settings.pii_map_ttl_seconds)

    async def restore(self, conversation_id: str, text: str) -> str:
        """Replace PII tokens in *text* with originals from Redis.

        Returns *text* unchanged if the key is missing or decryption fails
        (the content already went to the LLM without PII, so data is safe).
        """
        if _TOKEN_RE_PREFIX not in text:
            return text

        key = _redis_key(conversation_id)
        raw = await self._redis.get(key)
        if raw is None:
            return text

        try:
            decrypted = _fernet().decrypt(raw)
            pii_map: dict[str, str] = json.loads(decrypted)
        except (InvalidToken, json.JSONDecodeError) as exc:
            log.warning("token_map.restore_failed", conversation_id=conversation_id, error=str(exc))
            return text

        for token, original in pii_map.items():
            text = text.replace(token, original)
        return text

    async def purge(self, conversation_id: str) -> None:
        """Delete the token map before natural TTL expiry."""
        await self._redis.delete(_redis_key(conversation_id))
