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
kb_router = APIRouter(prefix="/kb", tags=["kb"])
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


# ---------------------------------------------------------------------------
# Public KB read endpoints (any authenticated user)
# ---------------------------------------------------------------------------

class KbArticleItem(BaseModel):
    model_config = ConfigDict(strict=False)

    id: str
    slug: str
    title: str
    tags: list[str]
    trust_level: str
    created_at: str


class KbArticleDetail(KbArticleItem):
    body_markdown: str


@kb_router.get("/articles", response_model=list[KbArticleItem])
async def list_kb_articles(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[KbArticleItem]:
    rows = await db.execute(
        text(
            "SELECT a.id::text, a.slug, a.title, a.tags, a.trust_level, "  # noqa: S608
            "a.created_at::text "
            "FROM helpdesk.kb_articles a "
            "ORDER BY a.created_at DESC"
        )
    )
    return [
        KbArticleItem(
            id=r.id,
            slug=r.slug,
            title=r.title,
            tags=list(r.tags) if r.tags else [],
            trust_level=str(r.trust_level),
            created_at=r.created_at,
        )
        for r in rows.fetchall()
    ]


@kb_router.get("/articles/{slug}", response_model=KbArticleDetail)
async def get_kb_article(
    slug: str,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KbArticleDetail:
    from app.core.errors import NotFoundError

    row = await db.execute(
        text(
            "SELECT a.id::text, a.slug, a.title, a.tags, a.trust_level, "  # noqa: S608
            "a.created_at::text, v.body_markdown "
            "FROM helpdesk.kb_articles a "
            "JOIN helpdesk.kb_article_versions v ON v.article_id = a.id "
            "WHERE a.slug = :slug "
            "ORDER BY v.version DESC LIMIT 1"
        ),
        {"slug": slug},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Artigo não encontrado")
    return KbArticleDetail(
        id=r.id,
        slug=r.slug,
        title=r.title,
        tags=list(r.tags) if r.tags else [],
        trust_level=str(r.trust_level),
        created_at=r.created_at,
        body_markdown=r.body_markdown,
    )
