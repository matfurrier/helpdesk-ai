"""Public CSAT survey endpoints — no authentication required.

GET  /public/csat/{token}  → ticket info + response status
POST /public/csat/{token}  → submit rating (1-5) + optional comment
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ConflictError
from app.db.session import get_db

router = APIRouter(prefix="/public/csat", tags=["csat"])


class CsatStatusOut(BaseModel):
    ticket_id: str
    ticket_number: str
    title: str
    status: str
    already_responded: bool
    rating: int | None = None


class CsatSubmitIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v else None


class CsatSubmitOut(BaseModel):
    ok: bool
    message: str


@router.get("/{token}", response_model=CsatStatusOut)
async def get_csat(token: str, db: AsyncSession = Depends(get_db)) -> CsatStatusOut:
    row = await db.execute(
        text(
            "SELECT us.ticket_id, us.rating, us.responded_at, "  # noqa: S608
            "       t.number, t.title, t.status "
            "FROM helpdesk.user_satisfaction us "
            "JOIN helpdesk.tickets t ON t.id = us.ticket_id "
            "WHERE us.csat_token = CAST(:token AS uuid) "
            "LIMIT 1"
        ),
        {"token": token},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Pesquisa não encontrada ou link inválido")

    number = int(r.number)
    return CsatStatusOut(
        ticket_id=str(r.ticket_id),
        ticket_number=f"HD-{number:06d}",
        title=str(r.title),
        status=str(r.status),
        already_responded=r.responded_at is not None,
        rating=int(r.rating) if r.rating is not None else None,
    )


@router.post("/{token}", response_model=CsatSubmitOut)
async def submit_csat(
    token: str,
    body: CsatSubmitIn,
    db: AsyncSession = Depends(get_db),
) -> CsatSubmitOut:
    row = await db.execute(
        text(
            "SELECT id, responded_at FROM helpdesk.user_satisfaction "  # noqa: S608
            "WHERE csat_token = CAST(:token AS uuid) "
            "FOR UPDATE LIMIT 1"
        ),
        {"token": token},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Pesquisa não encontrada ou link inválido")
    if r.responded_at is not None:
        raise ConflictError("Avaliação já registrada para este chamado")

    await db.execute(
        text(
            "UPDATE helpdesk.user_satisfaction "  # noqa: S608
            "SET rating = :rating, comment = :comment, responded_at = NOW() "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {"rating": body.rating, "comment": body.comment, "id": str(r.id)},
    )
    await db.commit()

    return CsatSubmitOut(ok=True, message="Obrigado pela sua avaliação!")
