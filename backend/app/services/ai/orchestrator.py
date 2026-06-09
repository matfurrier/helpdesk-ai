"""LLM orchestrator stub — Sprint 0.

All LLM calls in Sprint 1+ must go through LLMOrchestrator.complete().
Never call OpenAI/Anthropic SDKs outside this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class LLMOrchestrator:
    """Sprint 0 stub. Business logic implemented in Sprint 1."""

    async def complete(
        self,
        *,
        prompt_key: str,
        user_input: str,
        context_blocks: list[dict[str, object]] | None = None,
        schema: type | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, object]:
        raise NotImplementedError("LLM orchestrator not implemented in Sprint 0")


orchestrator = LLMOrchestrator()
