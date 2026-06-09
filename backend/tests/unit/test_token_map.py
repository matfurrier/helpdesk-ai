"""Unit tests for app.services.ai.token_map."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.services.ai.token_map import TokenMap, _redis_key

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_token_map() -> tuple[TokenMap, MagicMock]:
    redis_mock = MagicMock()
    redis_mock.set = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.delete = AsyncMock()
    tm = TokenMap(redis_mock)
    return tm, redis_mock


# ---------------------------------------------------------------------------
# store()
# ---------------------------------------------------------------------------


async def test_store_encrypts_and_sets_ttl() -> None:
    tm, redis = _make_token_map()
    pii_map = {"[PII_CPF_1]": "111.444.777-35"}

    await tm.store("conv-abc", pii_map)

    redis.set.assert_called_once()
    call_kwargs = redis.set.call_args
    key_arg = call_kwargs[0][0]
    assert key_arg == "pii:conv-abc"
    # TTL must be provided
    assert call_kwargs[1]["ex"] > 0 or call_kwargs[0][2] > 0 or "ex" in str(call_kwargs)


async def test_store_noop_for_empty_map() -> None:
    tm, redis = _make_token_map()
    await tm.store("conv-abc", {})
    redis.set.assert_not_called()


# ---------------------------------------------------------------------------
# restore()
# ---------------------------------------------------------------------------


async def test_restore_round_trip() -> None:
    """store → restore returns original text."""
    import json

    from cryptography.fernet import Fernet

    from app.core.config import settings

    fernet = Fernet(settings.fernet_key)
    pii_map = {"[PII_CPF_1]": "111.444.777-35"}
    encrypted = fernet.encrypt(json.dumps(pii_map).encode())

    tm, redis = _make_token_map()
    redis.get = AsyncMock(return_value=encrypted)

    restored = await tm.restore("conv-abc", "Seu CPF é [PII_CPF_1] mesmo?")
    assert "111.444.777-35" in restored
    assert "[PII_CPF_1]" not in restored


async def test_restore_no_token_skips_redis() -> None:
    """Text without PII tokens must not call Redis."""
    tm, redis = _make_token_map()
    text = "Preciso resetar minha senha."
    result = await tm.restore("conv-abc", text)
    redis.get.assert_not_called()
    assert result == text


async def test_restore_missing_key_returns_text_unchanged() -> None:
    tm, redis = _make_token_map()
    redis.get = AsyncMock(return_value=None)
    text = "Seu [PII_CPF_1] não encontrado."
    result = await tm.restore("conv-abc", text)
    assert result == text


async def test_restore_corrupted_payload_returns_text_unchanged() -> None:
    """Fernet InvalidToken must be swallowed — flow must not crash."""
    tm, redis = _make_token_map()
    redis.get = AsyncMock(return_value=b"corrupted-data-not-fernet")
    text = "Ver [PII_CPF_1] aqui."
    result = await tm.restore("conv-abc", text)
    assert result == text  # unchanged, no exception


# ---------------------------------------------------------------------------
# purge()
# ---------------------------------------------------------------------------


async def test_purge_deletes_key() -> None:
    tm, redis = _make_token_map()
    await tm.purge("conv-xyz")
    redis.delete.assert_called_once_with("pii:conv-xyz")


# ---------------------------------------------------------------------------
# Key format
# ---------------------------------------------------------------------------


def test_redis_key_format() -> None:
    assert _redis_key("abc-123") == "pii:abc-123"
