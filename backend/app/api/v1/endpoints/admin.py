"""Admin endpoints — KB article ingestion, role management."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.errors import ForbiddenError, HelpdeskError
from app.db.session import get_db
from app.schemas.auth import UserOut
from app.schemas.kb import ArticleCreate, ArticleIngestOut
from app.services.rag import ingester

router = APIRouter(prefix="/admin", tags=["admin"])
log = structlog.get_logger()

_ADMIN_ROLES = frozenset({"it_admin", "it_lead"})


async def _check_csrf(request: Request) -> None:
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise ForbiddenError("CSRF token inválido ou ausente")


async def _admin_user(request: Request, response: Response) -> UserOut:
    await _check_csrf(request)
    user = await get_current_user(request, response)
    if user.role not in _ADMIN_ROLES:
        raise ForbiddenError("Acesso restrito a administradores")
    return user


@router.post("/kb/articles", status_code=201)
async def create_kb_article(
    body: ArticleCreate,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleIngestOut:
    """Create a KB article, store a version, chunk and embed synchronously."""
    art_result = await db.execute(
        text(
            "INSERT INTO helpdesk.kb_articles "  # noqa: S608
            "(slug, title, tags, trust_level, created_by) "
            "VALUES (:slug, :title, :tags, :trust, :created_by) "
            "RETURNING id"
        ),
        {
            "slug": body.slug,
            "title": body.title,
            "tags": body.tags,
            "trust": body.trust_level,
            "created_by": current_user.user_id,
        },
    )
    art_row = art_result.fetchone()
    if art_row is None:
        raise HelpdeskError("Falha ao criar artigo")
    article_id = str(art_row.id)

    await db.execute(
        text(
            "INSERT INTO helpdesk.kb_article_versions "  # noqa: S608
            "(article_id, version, body_markdown, edited_by) "
            "VALUES (CAST(:aid AS uuid), 1, :body, :edited_by)"
        ),
        {
            "aid": article_id,
            "body": body.body_markdown,
            "edited_by": current_user.user_id,
        },
    )
    await db.commit()

    chunks_created = await ingester.ingest_article(article_id, db)

    log.info(
        "admin.kb.article_created",
        article_id=article_id,
        slug=body.slug,
        chunks_created=chunks_created,
        user_id=current_user.user_id,
    )

    return ArticleIngestOut(
        article_id=article_id,
        slug=body.slug,
        chunks_created=chunks_created,
    )


# ---------------------------------------------------------------------------
# Role override management
# ---------------------------------------------------------------------------

_OVERRIDABLE_ROLES = frozenset({"it_admin", "it_lead"})


class RoleOverrideIn(BaseModel):
    model_config = ConfigDict(strict=True)

    role: str

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        if v not in _OVERRIDABLE_ROLES:
            raise ValueError(f"role must be one of {sorted(_OVERRIDABLE_ROLES)}")
        return v


class RoleOverrideOut(BaseModel):
    model_config = ConfigDict(strict=True)

    user_uuid: str
    role: str


@router.post("/roles/{user_uuid}", status_code=200)
async def upsert_role_override(
    user_uuid: str,
    body: RoleOverrideIn,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> RoleOverrideOut:
    """Insert or update an explicit role grant in helpdesk.role_overrides.

    Only it_admin can set it_admin; it_lead or it_admin can set it_lead.
    """
    if body.role == "it_admin" and current_user.role != "it_admin":
        raise ForbiddenError("Apenas it_admin pode conceder it_admin")

    await db.execute(
        text(
            "INSERT INTO helpdesk.role_overrides (user_uuid, role, granted_by) "  # noqa: S608
            "VALUES (:uuid, :role, :granted_by) "
            "ON CONFLICT (user_uuid) DO UPDATE "
            "SET role = EXCLUDED.role, granted_by = EXCLUDED.granted_by, granted_at = now()"
        ),
        {
            "uuid": user_uuid,
            "role": body.role,
            "granted_by": current_user.user_id,
        },
    )
    await db.commit()

    log.info(
        "admin.role_override.upserted",
        target_uuid=user_uuid,
        role=body.role,
        granted_by=current_user.user_id,
    )

    return RoleOverrideOut(user_uuid=user_uuid, role=body.role)
