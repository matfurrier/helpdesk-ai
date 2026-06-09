"""Prompt injection test fixtures — Sprint 1.

Uses respx to mock OpenAI API calls so the suite runs without network access
or a real API key. The mock returns a valid TriageOutput JSON for all requests
unless overridden by a specific test.
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

_TRIAGE_SYSTEM_MOCK: dict[str, object] = {
    "assistant_text": "Entendido. Como posso ajudá-lo com esse problema de TI?",
    "next_action": "ask_more",
    "suggestions": [],
    "ticket_draft": None,
    "guardrails_triggered": [],
}

# OpenAI chat completions response envelope (beta.parse compatible)
_OPENAI_RESPONSE: dict[str, object] = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps(_TRIAGE_SYSTEM_MOCK),
                "refusal": None,
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
}

# Response where the LLM acknowledges a guardrail hit
_OPENAI_RESPONSE_PI_FLAGGED: dict[str, object] = {
    "id": "chatcmpl-test-pi",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps(
                    {
                        **_TRIAGE_SYSTEM_MOCK,
                        "assistant_text": (
                            "Detectei algo suspeito na sua mensagem. Como posso ajudá-lo com TI?"
                        ),
                        "next_action": "escalate_human",
                        "guardrails_triggered": ["prompt_injection"],
                    }
                ),
                "refusal": None,
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
}


@pytest.fixture
def mock_openai() -> respx.MockRouter:  # type: ignore[name-defined]
    """Active respx mock for all OpenAI API requests (returns clean triage response)."""
    with respx.mock(
        base_url="https://api.openai.com",
        assert_all_called=False,
    ) as mock:
        mock.post("/v1/chat/completions").mock(return_value=Response(200, json=_OPENAI_RESPONSE))
        yield mock


@pytest.fixture
def mock_openai_pi_flagged() -> respx.MockRouter:  # type: ignore[name-defined]
    """Mock where the LLM returns guardrails_triggered populated."""
    with respx.mock(
        base_url="https://api.openai.com",
        assert_all_called=False,
    ) as mock:
        mock.post("/v1/chat/completions").mock(
            return_value=Response(200, json=_OPENAI_RESPONSE_PI_FLAGGED)
        )
        yield mock
