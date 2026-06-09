"""Ticket schemas — Sprint 2."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TicketStatus = Literal[
    "NEW", "TRIAGE", "IN_PROGRESS", "WAITING_USER",
    "RESOLVED", "CLOSED", "AUTO_RESOLVED", "CANCELLED", "REOPENED",
]


class TicketDraftOutput(BaseModel):
    """Structured output returned by TICKET_DRAFT_SYSTEM prompt."""

    model_config = ConfigDict(strict=True)

    title: str = Field(max_length=200)
    summary: str = Field(max_length=1000)
    category_slug: str
    priority: Literal["low", "normal", "high", "urgent"]
    tags: list[str] = Field(default_factory=list)


class ConvertOut(BaseModel):
    model_config = ConfigDict(strict=True)

    ticket_id: str
    ticket_number: str
    status: str


class TicketOut(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    number: int
    ticket_number: str
    title: str
    summary: str
    status: str
    priority: str
    category_id: str | None
    requester_id: str
    requester_name: str | None = None
    requester_login: str | None = None
    assignee_id: str | None = None
    conversation_id: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    transcript: str | None = None


class TicketListItem(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    number: int
    ticket_number: str
    title: str
    status: str
    priority: str
    requester_id: str
    assignee_id: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class TicketListOut(BaseModel):
    model_config = ConfigDict(strict=True)

    items: list[TicketListItem]
    total: int


class TicketStatsOut(BaseModel):
    model_config = ConfigDict(strict=True)

    open_count: int
    pending_count: int
    resolved_today: int
    unassigned_count: int
    avg_first_response_minutes: float | None


class TicketMessageOut(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    author_id: str
    author_role: str
    visibility: str
    body: str
    created_at: datetime


class AddMessageIn(BaseModel):
    model_config = ConfigDict(strict=True)

    body: str = Field(min_length=1, max_length=5000)
    visibility: Literal["public", "internal"] = "public"


class StatusUpdateIn(BaseModel):
    model_config = ConfigDict(strict=True)

    status: TicketStatus
    reason: str | None = None


class AssignUpdateIn(BaseModel):
    model_config = ConfigDict(strict=True)

    assignee_id: str | None


class KbArticleCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    slug: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=3, max_length=200)
    body_markdown: str = Field(min_length=10)
    tags: list[str] = Field(default_factory=list)
    trust_level: Literal[
        "internal_published", "internal_draft", "internal_only", "external_doc"
    ] = "internal_draft"
    category_slug: str | None = None


class KbArticleOut(BaseModel):
    model_config = ConfigDict(strict=True)

    article_id: str
    slug: str
    queued: bool


class RoleGrantCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    role: Literal["it_admin", "it_lead"]
