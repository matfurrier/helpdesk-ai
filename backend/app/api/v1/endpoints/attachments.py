"""Ticket attachment endpoints — upload, list, download."""

from __future__ import annotations

import hashlib
import uuid
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.schemas.auth import UserOut
from app.services.attachments import scanner, storage

log = structlog.get_logger()

router = APIRouter(prefix="/tickets", tags=["attachments"])

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

_ALLOWED_MIME: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }
)

_IT_ROLES: frozenset[str] = frozenset({"it_agent", "it_lead", "it_admin"})


class AttachmentOut(BaseModel):
    id: str
    original_name: str
    mime_type: str
    size_bytes: int
    scanned_status: str
    created_at: str


async def _assert_ticket_access(ticket_id: str, user: UserOut, db: AsyncSession) -> None:
    res = await db.execute(
        text(
            "SELECT requester_id FROM helpdesk.tickets "  # noqa: S608
            "WHERE id = CAST(:tid AS uuid)"
        ),
        {"tid": ticket_id},
    )
    row = res.fetchone()
    if row is None:
        raise NotFoundError("Chamado não encontrado")
    if user.role not in _IT_ROLES and str(row.requester_id) != user.user_id:
        raise ForbiddenError("Sem acesso a este chamado")


@router.post("/{ticket_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    ticket_id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
) -> AttachmentOut:
    await _assert_ticket_access(ticket_id, current_user, db)

    data = await file.read()
    if len(data) > _MAX_BYTES:
        mb_limit = _MAX_BYTES // 1024 // 1024
        raise HTTPException(413, detail=f"Arquivo muito grande (máx {mb_limit} MB)")

    mime = file.content_type or "application/octet-stream"
    if mime not in _ALLOWED_MIME:
        raise HTTPException(415, detail=f"Tipo de arquivo não permitido: {mime}")

    # ClamAV scan — fail open in dev or when CLAMAV_FAIL_OPEN=true
    try:
        is_clean, scan_result = await scanner.scan(data)
    except OSError as exc:
        if settings.is_dev or settings.clamav_fail_open:
            log.warning("clamav.unreachable_skip", error=str(exc), fail_open=settings.clamav_fail_open)
            is_clean, scan_result = True, "skipped"
        else:
            raise HTTPException(503, detail="Antivírus indisponível — tente mais tarde") from exc

    if not is_clean:
        raise HTTPException(422, detail=f"Arquivo bloqueado pelo antivírus: {scan_result}")

    await storage.ensure_bucket()
    stored_key = await storage.put(data, ticket_id, file.filename or "arquivo", mime)

    attachment_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO helpdesk.ticket_attachments "
            "(id, ticket_id, uploader_id, original_name, stored_key, "
            " mime_type, size_bytes, sha256, scanned_status) "
            "VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :uid, :name, "
            "        :key, :mime, :size, :sha256, :status)"
        ),
        {
            "id": attachment_id,
            "tid": ticket_id,
            "uid": current_user.user_id,
            "name": file.filename or "arquivo",
            "key": stored_key,
            "mime": mime,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "status": "clean",
        },
    )
    await db.commit()

    res = await db.execute(
        text(
            "SELECT id::text, original_name, mime_type, size_bytes, "  # noqa: S608
            "       scanned_status, created_at::text "
            "FROM helpdesk.ticket_attachments WHERE id = CAST(:id AS uuid)"
        ),
        {"id": attachment_id},
    )
    row = res.fetchone()
    return AttachmentOut(**dict(row._mapping))  # noqa: SLF001


@router.get("/{ticket_id}/attachments", response_model=list[AttachmentOut])
async def list_attachments(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
) -> list[AttachmentOut]:
    await _assert_ticket_access(ticket_id, current_user, db)
    res = await db.execute(
        text(
            "SELECT id::text, original_name, mime_type, size_bytes, "  # noqa: S608
            "       scanned_status, created_at::text "
            "FROM helpdesk.ticket_attachments "
            "WHERE ticket_id = CAST(:tid AS uuid) AND scanned_status = 'clean' "
            "ORDER BY created_at"
        ),
        {"tid": ticket_id},
    )
    return [AttachmentOut(**dict(r._mapping)) for r in res.fetchall()]  # noqa: SLF001


@router.get("/{ticket_id}/attachments/{attachment_id}/download")
async def download_attachment(
    ticket_id: str,
    attachment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserOut = Depends(get_current_user),
) -> Response:
    await _assert_ticket_access(ticket_id, current_user, db)
    res = await db.execute(
        text(
            "SELECT stored_key, original_name, mime_type "  # noqa: S608
            "FROM helpdesk.ticket_attachments "
            "WHERE id = CAST(:aid AS uuid) "
            "  AND ticket_id = CAST(:tid AS uuid) "
            "  AND scanned_status = 'clean'"
        ),
        {"aid": attachment_id, "tid": ticket_id},
    )
    row = res.fetchone()
    if row is None:
        raise NotFoundError("Arquivo não encontrado")
    data = await storage.get(str(row.stored_key))
    filename = quote(str(row.original_name))
    return Response(
        content=data,
        media_type=str(row.mime_type),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
