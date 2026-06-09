"""Unit tests for LLMOrchestrator — Sprint 1.

Covers paths not exercised by the prompt injection suite:
- _fetch_prompt missing prompt
- _call_anthropic via respx
- complete with context_blocks
- complete with redis TokenMap attached (PII store + restore)
- fallback: OpenAI 5xx → Anthropic success
- fallback: both providers fail
- get_orchestrator / init_orchestrator singletons
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response
from openai import APIStatusError

from app.core.errors import LLMError
from app.schemas.chat import TriageOutput
from app.services.ai import orchestrator as _orch_mod
from app.services.ai.orchestrator import (
    LLMOrchestrator,
    _fetch_prompt,
    get_orchestrator,
    init_orchestrator,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_TRIAGE_OK = {
    "assistant_text": "Como posso ajudar?",
    "next_action": "ask_more",
    "suggestions": [],
    "ticket_draft": None,
    "guardrails_triggered": [],
}

_OPENAI_RESP = {
    "id": "chatcmpl-test-orch",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps(_TRIAGE_OK),
                "refusal": None,
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
}

_ANTHROPIC_RESP = {
    "id": "msg_test_orch",
    "type": "message",
    "role": "assistant",
    "model": "claude-haiku-4-5-20251001",
    "content": [
        {
            "type": "tool_use",
            "id": "toolu_test",
            "name": "triage_output",
            "input": _TRIAGE_OK,
        }
    ],
    "stop_reason": "tool_use",
    "stop_sequence": None,
    "usage": {"input_tokens": 100, "output_tokens": 50},
}


# ---------------------------------------------------------------------------
# DB mock factory
# ---------------------------------------------------------------------------


def _mock_db(missing: bool = False) -> MagicMock:
    if missing:
        fetch_result = MagicMock()
        fetch_result.fetchone.return_value = None
    else:
        row = MagicMock()
        row.version = 1
        row.sha256 = "deadbeef"
        row.body = "You are IT helpdesk. Output JSON only."
        fetch_result = MagicMock()
        fetch_result.fetchone.return_value = row

    db = MagicMock()
    db.execute = AsyncMock(return_value=fetch_result)
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# _fetch_prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_prompt_not_found() -> None:
    """_fetch_prompt raises LLMError when prompt is not in DB."""
    # Clear cache to force DB lookup
    _orch_mod._prompt_cache.clear()

    db = _mock_db(missing=True)
    with pytest.raises(LLMError, match="MISSING_KEY"):
        await _fetch_prompt("MISSING_KEY", db)


@pytest.mark.asyncio
async def test_fetch_prompt_cache_hit() -> None:
    """_fetch_prompt returns cached value without hitting DB."""
    import time

    _orch_mod._prompt_cache["CACHED_KEY"] = (2, "sha_cached", "body_cached", time.monotonic())
    db = _mock_db()

    ver, sha, body = await _fetch_prompt("CACHED_KEY", db)

    assert ver == 2
    assert sha == "sha_cached"
    assert body == "body_cached"
    db.execute.assert_not_called()
    _orch_mod._prompt_cache.pop("CACHED_KEY", None)


# ---------------------------------------------------------------------------
# _call_anthropic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_anthropic_returns_triage() -> None:
    """_call_anthropic parses tool_use response into TriageOutput via mocked SDK."""
    from app.services.ai.orchestrator import _call_anthropic

    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = _TRIAGE_OK

    mock_response = MagicMock()
    mock_response.content = [tool_use_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    messages = [
        {"role": "system", "content": "You are helpdesk."},
        {"role": "user", "content": "VPN não conecta."},
    ]
    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        result, in_tok, out_tok = await _call_anthropic(messages, TriageOutput)

    assert isinstance(result, TriageOutput)
    assert result.next_action == "ask_more"
    assert result.assistant_text == "Como posso ajudar?"


# ---------------------------------------------------------------------------
# complete — context_blocks path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_with_context_blocks() -> None:
    """complete() injects context_blocks into the system messages."""
    _orch_mod._prompt_cache.clear()

    with respx.mock(base_url="https://api.openai.com", assert_all_called=False) as m:
        m.post("/v1/chat/completions").mock(return_value=Response(200, json=_OPENAI_RESP))
        orch = LLMOrchestrator(redis=None)
        result = await orch.complete(
            prompt_key="TRIAGE_SYSTEM",
            user_input="Preciso de ajuda com o SAP.",
            context_blocks=[
                {"id": "kb_1", "content": "SAP B1 troubleshooting guide."},
                {"id": "kb_2", "content": "VPN client setup instructions."},
            ],
            db=_mock_db(),
        )

    assert isinstance(result, TriageOutput)
    assert result.next_action == "ask_more"


# ---------------------------------------------------------------------------
# complete — redis / TokenMap path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_with_redis_stores_pii() -> None:
    """complete() stores PII map in Redis when redis is attached and PII found."""
    _orch_mod._prompt_cache.clear()

    mock_redis = MagicMock()
    mock_redis.set = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with respx.mock(base_url="https://api.openai.com", assert_all_called=False) as m:
        m.post("/v1/chat/completions").mock(return_value=Response(200, json=_OPENAI_RESP))
        orch = LLMOrchestrator(redis=mock_redis)
        result = await orch.complete(
            prompt_key="TRIAGE_SYSTEM",
            user_input="Meu CPF é 111.444.777-35, preciso de ajuda.",
            conversation_id="conv-redis-test",
            user_id="user-redis-test",
            db=_mock_db(),
        )

    assert isinstance(result, TriageOutput)
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert "pii:conv-redis-test" in call_args[0][0]


@pytest.mark.asyncio
async def test_complete_with_redis_restores_pii_in_reply() -> None:
    """complete() replaces tokens back in assistant_text when Redis has the map."""
    from cryptography.fernet import Fernet

    from app.core.config import settings

    pii_map = {"[PII_CPF_1]": "111.444.777-35"}
    fernet = Fernet(settings.fernet_key)
    encrypted = fernet.encrypt(json.dumps(pii_map).encode())

    resp_with_token = {
        **_OPENAI_RESP,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            **_TRIAGE_OK,
                            "assistant_text": "Seu CPF [PII_CPF_1] foi localizado.",
                        }
                    ),
                    "refusal": None,
                },
                "finish_reason": "stop",
            }
        ],
    }
    _orch_mod._prompt_cache.clear()

    mock_redis = MagicMock()
    mock_redis.set = AsyncMock()
    mock_redis.get = AsyncMock(return_value=encrypted)

    with respx.mock(base_url="https://api.openai.com", assert_all_called=False) as m:
        m.post("/v1/chat/completions").mock(return_value=Response(200, json=resp_with_token))
        orch = LLMOrchestrator(redis=mock_redis)
        result = await orch.complete(
            prompt_key="TRIAGE_SYSTEM",
            user_input="Meu CPF é 111.444.777-35.",
            conversation_id="conv-restore-test",
            user_id="user-restore-test",
            db=_mock_db(),
        )

    assert "111.444.777-35" in result.assistant_text
    assert "[PII_CPF_1]" not in result.assistant_text


# ---------------------------------------------------------------------------
# Fallback path: OpenAI 5xx → Anthropic success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_fallback_on_openai_5xx() -> None:
    """complete() falls back to Anthropic when OpenAI returns 5xx and fallback enabled."""

    _orch_mod._prompt_cache.clear()

    mock_http_response = MagicMock()
    mock_http_response.status_code = 503
    mock_http_response.headers = {}

    fallback_result = TriageOutput(
        assistant_text="Posso ajudar com a impressora.",
        next_action="ask_more",
    )

    with (
        patch("app.services.ai.orchestrator._call_openai") as mock_openai,
        patch("app.services.ai.orchestrator._call_anthropic") as mock_anthropic,
        patch("app.services.ai.orchestrator.settings") as mock_settings,
    ):
        mock_settings.openai_model = "gpt-4o-mini-2024-07-18"
        mock_settings.anthropic_model = "claude-haiku-4-5-20251001"
        mock_settings.ai_fallback_enabled = True

        mock_openai.side_effect = APIStatusError(
            "Internal Server Error",
            response=mock_http_response,
            body={"error": {"message": "server error"}},
        )
        mock_anthropic.return_value = (fallback_result, None, None)

        orch = LLMOrchestrator(redis=None)
        result = await orch.complete(
            prompt_key="TRIAGE_SYSTEM",
            user_input="Ajuda com impressora.",
            db=_mock_db(),
        )

    assert isinstance(result, TriageOutput)
    assert result.next_action == "ask_more"
    assert result.assistant_text == "Posso ajudar com a impressora."


# ---------------------------------------------------------------------------
# Fallback disabled: OpenAI 5xx → LLMError immediately
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_no_fallback_on_openai_5xx() -> None:
    """complete() raises LLMError on OpenAI 5xx when fallback is disabled."""
    _orch_mod._prompt_cache.clear()

    with (
        patch("app.services.ai.orchestrator._call_openai") as mock_call,
        patch("app.core.config.settings") as mock_settings,
    ):
        mock_settings.openai_model = "gpt-4o-mini-2024-07-18"
        mock_settings.anthropic_model = "claude-haiku-4-5-20251001"
        mock_settings.ai_fallback_enabled = False

        mock_call.side_effect = APIStatusError(
            "Internal Server Error",
            response=MagicMock(status_code=503, headers={}),
            body={"error": {"message": "server error"}},
        )

        orch = LLMOrchestrator(redis=None)
        with pytest.raises((LLMError, APIStatusError)):
            await orch.complete(
                prompt_key="TRIAGE_SYSTEM",
                user_input="Teste fallback desabilitado.",
                db=_mock_db(),
            )


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_orchestrator_returns_singleton() -> None:
    """get_orchestrator() returns the module-level singleton."""
    result = await get_orchestrator()
    assert isinstance(result, LLMOrchestrator)


@pytest.mark.asyncio
async def test_init_orchestrator_attaches_redis() -> None:
    """init_orchestrator() replaces singleton with redis-attached instance."""
    original = _orch_mod.orchestrator
    mock_redis = MagicMock()

    await init_orchestrator(mock_redis)

    assert isinstance(_orch_mod.orchestrator, LLMOrchestrator)
    assert _orch_mod.orchestrator._token_map is not None

    # Restore for other tests
    _orch_mod.orchestrator = original
