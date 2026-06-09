"""Integration tests for chat endpoints — Sprint 1.

Requires: running Postgres with migration applied (marks: integration).
OpenAI is mocked via respx so no real API key is needed.
Redis is mocked to avoid a live Redis dependency.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import AsyncClient, Response

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# OpenAI mock response
# ---------------------------------------------------------------------------

_TRIAGE_RESPONSE = {
    "assistant_text": "Olá! Em que posso ajudar?",
    "next_action": "ask_more",
    "suggestions": [],
    "ticket_draft": None,
    "guardrails_triggered": [],
}

_OPENAI_RESP = {
    "id": "chatcmpl-int-test",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps(_TRIAGE_RESPONSE),
                "refusal": None,
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
}

# CSRF token for all POST requests
_CSRF_TOKEN = "test-csrf-token-sprint1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_headers() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF_TOKEN}


def _csrf_cookies() -> dict[str, str]:
    return {"csrf_token": _CSRF_TOKEN}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_csrf_token_endpoint(client: AsyncClient) -> None:
    """GET /chat/csrf-token sets the cookie and returns token in body."""
    resp = await client.get("/api/v1/chat/csrf-token")
    assert resp.status_code == 200
    body = resp.json()
    assert "csrf_token" in body
    assert len(body["csrf_token"]) > 0


async def test_create_conversation(
    respx_mock: respx.MockRouter, authed_client: AsyncClient
) -> None:
    """POST /chat/conversations creates a conversation."""
    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json=_OPENAI_RESP)
    )

    with patch("app.api.v1.endpoints.chat._get_redis") as mock_get_redis:
        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)
        mock_get_redis.return_value = mock_redis

        resp = await authed_client.post(
            "/api/v1/chat/conversations",
            headers=_csrf_headers(),
            cookies=_csrf_cookies(),
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["status"] == "active"
    assert data["message_count"] == 0


async def test_send_message_returns_sse(
    respx_mock: respx.MockRouter, authed_client: AsyncClient
) -> None:
    """POST /chat/conversations/{id}/messages returns SSE stream."""
    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json=_OPENAI_RESP)
    )

    with patch("app.api.v1.endpoints.chat._get_redis") as mock_get_redis:
        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)
        mock_get_redis.return_value = mock_redis

        # Create conversation first
        conv_resp = await authed_client.post(
            "/api/v1/chat/conversations",
            headers=_csrf_headers(),
            cookies=_csrf_cookies(),
        )
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["id"]

        msg_resp = await authed_client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"content": "Meu VPN não conecta."},
            headers=_csrf_headers(),
            cookies=_csrf_cookies(),
        )

    assert msg_resp.status_code == 200
    assert "text/event-stream" in msg_resp.headers["content-type"]

    # Parse SSE events
    raw = msg_resp.text
    events = [line[6:] for line in raw.splitlines() if line.startswith("data: ")]
    assert len(events) >= 1

    final = json.loads(events[-1])
    assert final["done"] is True
    assert "result" in final
    assert final["result"]["next_action"] == "ask_more"


async def test_send_message_csrf_missing(client: AsyncClient) -> None:
    """POST without X-CSRF-Token returns 403."""
    resp = await client.post(
        "/api/v1/chat/conversations",
        json={},
        # No CSRF header
    )
    assert resp.status_code == 403


async def test_rate_limit(respx_mock: respx.MockRouter, authed_client: AsyncClient) -> None:
    """31st request returns 429."""
    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json=_OPENAI_RESP)
    )

    call_count = 0

    async def _fake_eval(*args: object, **kwargs: object) -> int:
        nonlocal call_count
        call_count += 1
        return call_count  # 1st → 1, 31st → 31

    with patch("app.api.v1.endpoints.chat._get_redis") as mock_get_redis:
        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(side_effect=_fake_eval)
        mock_get_redis.return_value = mock_redis

        # First 30 requests should work (we'll just check request 31)
        # For speed, skip straight to count > 30
        call_count = 30

        resp = await authed_client.post(
            "/api/v1/chat/conversations",
            headers=_csrf_headers(),
            cookies=_csrf_cookies(),
        )
        assert resp.status_code == 429


async def test_pii_not_stored_in_content(
    respx_mock: respx.MockRouter, authed_client: AsyncClient
) -> None:
    """User message stored with PII replaced by tokens (LGPD compliance)."""
    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json=_OPENAI_RESP)
    )

    with patch("app.api.v1.endpoints.chat._get_redis") as mock_get_redis:
        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)
        mock_get_redis.return_value = mock_redis

        conv_resp = await authed_client.post(
            "/api/v1/chat/conversations",
            headers=_csrf_headers(),
            cookies=_csrf_cookies(),
        )
        conv_id = conv_resp.json()["id"]

        await authed_client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"content": "Meu CPF é 111.444.777-35, preciso de ajuda com VPN."},
            headers=_csrf_headers(),
            cookies=_csrf_cookies(),
        )

        # Retrieve messages
        msgs_resp = await authed_client.get(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            cookies=_csrf_cookies(),
        )

    assert msgs_resp.status_code == 200
    messages = msgs_resp.json()
    user_msg = next(m for m in messages if m["role"] == "user")
    # PII must be tokenized
    assert "111.444.777-35" not in user_msg["content"]
    assert "[PII_CPF_1]" in user_msg["content"]
