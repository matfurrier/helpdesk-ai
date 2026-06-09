"""Chat/triage schemas — Sprint 1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SuggestionItem(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str
    steps: list[str]
    citations: list[str] = []


class TicketDraft(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str
    summary: str
    category_suggestion: str
    priority_suggestion: Literal["low", "normal", "high", "urgent"]
    tags: list[str] = []


class TriageOutput(BaseModel):
    """Structured output returned by the LLM triage orchestrator.

    Field names match the TRIAGE_SYSTEM prompt contract in PROMPTS.md.
    Do NOT rename without updating the prompt and migration 0002.
    """

    model_config = ConfigDict(strict=True)

    assistant_text: str
    next_action: Literal[
        "ask_more",
        "suggest_kb",
        "offer_open_ticket",
        "auto_resolve",
        "escalate_human",
    ]
    suggestions: list[SuggestionItem] = []
    ticket_draft: TicketDraft | None = None
    guardrails_triggered: list[str] = []


class ConversationOut(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    status: str
    started_at: datetime
    message_count: int


class MessageCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    content: str


class MessageOut(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    role: str
    content: str
    created_at: datetime
