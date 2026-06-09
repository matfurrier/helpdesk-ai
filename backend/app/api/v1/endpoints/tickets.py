"""Ticket endpoints — Sprint 2.

GET /tickets/{ticket_id}  — read a single ticket (requester sees only their own)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.errors import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.schemas.auth import UserOut
from app.schemas.tickets import TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketOut:
    row = await db.execute(
        text(
            "SELECT t.id, t.number, t.title, t.summary, t.status, t.priority, "  # noqa: S608
            "       t.category_id, t.requester_id, t.conversation_id, t.tags, "
            "       t.created_at, t.updated_at, "
            "       tm.body AS transcript "
            "FROM helpdesk.tickets t "
            "LEFT JOIN helpdesk.ticket_messages tm "
            "  ON tm.ticket_id = t.id AND tm.author_role = 'system' "
            "WHERE t.id = CAST(:tid AS uuid) "
            "ORDER BY tm.created_at ASC "
            "LIMIT 1"
        ),
        {"tid": str(ticket_id)},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Ticket não encontrado")

    # IT agents/admins can view any ticket; employees only see their own
    is_agent = current_user.role in {"it_agent", "it_lead", "it_admin"}
    if not is_agent and str(r.requester_id) != current_user.user_id:
        raise ForbiddenError("Acesso negado")

    number = int(r.number)
    return TicketOut(
        id=str(r.id),
        number=number,
        ticket_number=f"HD-{number:06d}",
        title=str(r.title),
        summary=str(r.summary),
        status=str(r.status),
        priority=str(r.priority),
        category_id=str(r.category_id) if r.category_id else None,
        requester_id=str(r.requester_id),
        conversation_id=str(r.conversation_id) if r.conversation_id else None,
        tags=list(r.tags) if r.tags else [],
        created_at=r.created_at,
        updated_at=r.updated_at,
        transcript=str(r.transcript) if r.transcript else None,
    )
