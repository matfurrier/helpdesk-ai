"""Ticket schemas — Sprint 2."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TicketStatus = Literal[
    "NEW",
    "TRIAGE",
    "IN_PROGRESS",
    "WAITING_USER",
    "RESOLVED",
    "CLOSED",
    "AUTO_RESOLVED",
    "CANCELLED",
    "REOPENED",
]


class CategoryOut(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    slug: str
    name: str
    description: str | None = None
    sort_order: int


class SlaMatrixOut(BaseModel):
    model_config = ConfigDict(strict=True)

    priority: str
    first_response_hours: int
    resolution_hours: int
    description: str | None = None


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


class AgentOut(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    name: str


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
    category_name: str | None = None
    category_slug: str | None = None
    requester_id: str
    requester_name: str | None = None
    requester_login: str | None = None
    assignee_id: str | None = None
    assignee_name: str | None = None
    conversation_id: str | None
    tags: list[str]
    first_response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    transcript: str | None = None
    csat_rating: float | None = None
    csat_responded_at: datetime | None = None


class TicketListItem(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str
    number: int
    ticket_number: str
    title: str
    status: str
    priority: str
    category_slug: str | None = None
    category_name: str | None = None
    requester_id: str
    requester_name: str | None = None
    assignee_id: str | None
    assignee_name: str | None = None
    tags: list[str]
    resolution_due_at: datetime | None = None
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    csat_rating: float | None = None


class TicketListOut(BaseModel):
    model_config = ConfigDict(strict=True)

    items: list[TicketListItem]
    total: int


class TicketStatsOut(BaseModel):
    model_config = ConfigDict(strict=True)

    total_count: int = 0
    open_count: int
    pending_count: int
    resolved_today: int
    unassigned_count: int
    avg_first_response_minutes: float | None
    csat_avg_rating: float | None = None
    csat_total_responses: int = 0


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


class CategoryUpdateIn(BaseModel):
    model_config = ConfigDict(strict=True)

    category_slug: str | None


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


class FilterUser(BaseModel):
    model_config = ConfigDict(strict=False)

    id: str
    name: str


class FilterDept(BaseModel):
    model_config = ConfigDict(strict=False)

    id: int
    name: str


class FilterOptionsOut(BaseModel):
    model_config = ConfigDict(strict=False)

    years: list[int]
    departments: list[FilterDept]
    users: list[FilterUser]
    categories: list[CategoryOut] = Field(default_factory=list)
