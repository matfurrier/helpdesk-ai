"""Admin endpoints — KB, categories, users, SLA, reports, AI monitor."""

from __future__ import annotations

import csv
import io
import uuid as uuid_lib
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.errors import ForbiddenError, HelpdeskError, NotFoundError
from app.core.security import hash_password
from app.db.session import get_db, get_security_db
from app.schemas.auth import UserOut
from app.schemas.kb import ArticleCreate, ArticleIngestOut
from app.services.rag import ingester

router = APIRouter(prefix="/admin", tags=["admin"])
kb_router = APIRouter(prefix="/kb", tags=["kb"])
log = structlog.get_logger()

_ADMIN_ROLES = frozenset({"it_admin", "it_lead"})
_IT_ROLES = frozenset({"it_agent", "it_lead", "it_admin"})


async def _admin_user(user: UserOut = Depends(get_current_user)) -> UserOut:
    if user.role not in _ADMIN_ROLES:
        raise ForbiddenError("Acesso restrito a administradores")
    return user


async def _it_user(user: UserOut = Depends(get_current_user)) -> UserOut:
    if user.role not in _IT_ROLES:
        raise ForbiddenError("Acesso restrito a equipe de TI")
    return user


# ===========================================================================
# KB ADMIN — CRUD + re-ingest
# ===========================================================================


class KbArticleAdminItem(BaseModel):
    model_config = ConfigDict(strict=False)

    id: str
    slug: str
    title: str
    tags: list[str]
    trust_level: str
    is_archived: bool
    chunk_count: int
    created_at: str


class KbArticleAdminDetail(KbArticleAdminItem):
    body_markdown: str


class KbArticleUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str | None = None
    body_markdown: str | None = None
    tags: list[str] | None = None
    trust_level: str | None = None

    @field_validator("trust_level", mode="before")
    @classmethod
    def _validate_trust(cls, v: object) -> object:
        if v is None:
            return None
        _TRUST = frozenset(
            {"internal_published", "internal_draft", "internal_only", "external_doc"}
        )
        if v not in _TRUST:
            raise ValueError(f"trust_level must be one of {sorted(_TRUST)}")
        return v


async def _fetch_article_detail(slug: str, db: AsyncSession) -> KbArticleAdminDetail:
    row = await db.execute(
        text(
            "SELECT a.id::text, a.slug, a.title, a.tags, a.trust_level, "
            "       a.is_archived, a.created_at::text, v.body_markdown, "
            "       COALESCE(c.cnt, 0) AS chunk_count "
            "FROM helpdesk.kb_articles a "
            "JOIN helpdesk.kb_article_versions v ON v.article_id = a.id "
            "LEFT JOIN ("
            "  SELECT d.external_id, COUNT(ch.id) AS cnt "
            "  FROM helpdesk_rag.documents d "
            "  JOIN helpdesk_rag.chunks ch ON ch.document_id = d.id "
            "  GROUP BY d.external_id"
            ") c ON c.external_id = a.id::text "
            "WHERE a.slug = :slug "
            "ORDER BY v.version DESC LIMIT 1"
        ),
        {"slug": slug},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Artigo não encontrado")
    return KbArticleAdminDetail(
        id=r.id,
        slug=r.slug,
        title=r.title,
        tags=list(r.tags) if r.tags else [],
        trust_level=str(r.trust_level),
        is_archived=bool(r.is_archived),
        chunk_count=int(r.chunk_count),
        created_at=r.created_at,
        body_markdown=r.body_markdown,
    )


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
            "INSERT INTO helpdesk.kb_articles "
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
            "INSERT INTO helpdesk.kb_article_versions "
            "(article_id, version, body_markdown, edited_by) "
            "VALUES (CAST(:aid AS uuid), 1, :body, :edited_by)"
        ),
        {"aid": article_id, "body": body.body_markdown, "edited_by": current_user.user_id},
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
    return ArticleIngestOut(article_id=article_id, slug=body.slug, chunks_created=chunks_created)


@router.get("/kb/articles", response_model=list[KbArticleAdminItem])
async def list_kb_articles_admin(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> list[KbArticleAdminItem]:
    """List all KB articles including archived, with chunk counts."""
    rows = await db.execute(
        text(
            "SELECT a.id::text, a.slug, a.title, a.tags, a.trust_level, "
            "       a.is_archived, a.created_at::text, "
            "       COALESCE(c.cnt, 0) AS chunk_count "
            "FROM helpdesk.kb_articles a "
            "LEFT JOIN ("
            "  SELECT d.external_id, COUNT(ch.id) AS cnt "
            "  FROM helpdesk_rag.documents d "
            "  JOIN helpdesk_rag.chunks ch ON ch.document_id = d.id "
            "  GROUP BY d.external_id"
            ") c ON c.external_id = a.id::text "
            "ORDER BY a.is_archived, a.created_at DESC"
        )
    )
    return [
        KbArticleAdminItem(
            id=r.id,
            slug=r.slug,
            title=r.title,
            tags=list(r.tags) if r.tags else [],
            trust_level=str(r.trust_level),
            is_archived=bool(r.is_archived),
            chunk_count=int(r.chunk_count),
            created_at=r.created_at,
        )
        for r in rows.fetchall()
    ]


@router.get("/kb/articles/{slug}", response_model=KbArticleAdminDetail)
async def get_kb_article_admin(
    slug: str,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> KbArticleAdminDetail:
    return await _fetch_article_detail(slug, db)


@router.patch("/kb/articles/{slug}", response_model=KbArticleAdminDetail)
async def update_kb_article(
    slug: str,
    body: KbArticleUpdate,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> KbArticleAdminDetail:
    """Update title/tags/trust and optionally body (new version + re-ingest)."""
    row = await db.execute(
        text(
            "SELECT a.id::text AS id, a.is_archived, v.version "
            "FROM helpdesk.kb_articles a "
            "JOIN helpdesk.kb_article_versions v ON v.article_id = a.id "
            "WHERE a.slug = :slug ORDER BY v.version DESC LIMIT 1"
        ),
        {"slug": slug},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Artigo não encontrado")

    article_id = str(r.id)
    needs_reingest = False

    updates: dict[str, object] = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.tags is not None:
        updates["tags"] = body.tags
    if body.trust_level is not None:
        updates["trust_level"] = body.trust_level
        needs_reingest = True

    if updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        updates["slug"] = slug
        await db.execute(
            text(f"UPDATE helpdesk.kb_articles SET {set_clause} WHERE slug = :slug"),  # noqa: S608
            updates,
        )

    if body.body_markdown is not None:
        new_version = int(r.version) + 1
        await db.execute(
            text(
                "INSERT INTO helpdesk.kb_article_versions "
                "(article_id, version, body_markdown, edited_by) "
                "VALUES (CAST(:aid AS uuid), :version, :body, :edited_by)"
            ),
            {
                "aid": article_id,
                "version": new_version,
                "body": body.body_markdown,
                "edited_by": current_user.user_id,
            },
        )
        needs_reingest = True

    await db.commit()

    if needs_reingest and not bool(r.is_archived):
        await ingester.ingest_article(article_id, db)

    log.info("admin.kb.article_updated", slug=slug, user_id=current_user.user_id)
    return await _fetch_article_detail(slug, db)


@router.post("/kb/articles/{slug}/archive", status_code=200)
async def archive_kb_article(
    slug: str,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    res = await db.execute(
        text("UPDATE helpdesk.kb_articles SET is_archived = true WHERE slug = :slug RETURNING id"),
        {"slug": slug},
    )
    if res.fetchone() is None:
        raise NotFoundError("Artigo não encontrado")
    await db.commit()
    log.info("admin.kb.article_archived", slug=slug, user_id=current_user.user_id)
    return {"status": "archived"}


@router.post("/kb/articles/{slug}/restore", status_code=200)
async def restore_kb_article(
    slug: str,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    res = await db.execute(
        text(
            "UPDATE helpdesk.kb_articles SET is_archived = false "
            "WHERE slug = :slug RETURNING id::text AS aid"
        ),
        {"slug": slug},
    )
    row = res.fetchone()
    if row is None:
        raise NotFoundError("Artigo não encontrado")
    await db.commit()
    await ingester.ingest_article(str(row.aid), db)
    log.info("admin.kb.article_restored", slug=slug, user_id=current_user.user_id)
    return {"status": "restored"}


# ===========================================================================
# CATEGORIES ADMIN
# ===========================================================================


class CategoryAdminOut(BaseModel):
    model_config = ConfigDict(strict=False)

    id: str
    slug: str
    name: str
    description: str | None
    sort_order: int
    is_active: bool


class CategoryCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    slug: str
    name: str
    description: str | None = None
    sort_order: int = 99


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


@router.get("/categories", response_model=list[CategoryAdminOut])
async def list_categories_admin(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryAdminOut]:
    rows = await db.execute(
        text(
            "SELECT id::text, slug, name, description, sort_order, is_active "
            "FROM helpdesk.categories ORDER BY sort_order, name"
        )
    )
    return [
        CategoryAdminOut(
            id=r.id,
            slug=r.slug,
            name=r.name,
            description=r.description,
            sort_order=int(r.sort_order),
            is_active=bool(r.is_active),
        )
        for r in rows.fetchall()
    ]


@router.post("/categories", status_code=201, response_model=CategoryAdminOut)
async def create_category(
    body: CategoryCreate,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryAdminOut:
    res = await db.execute(
        text(
            "INSERT INTO helpdesk.categories (slug, name, description, sort_order) "
            "VALUES (:slug, :name, :desc, :sort) "
            "RETURNING id::text, slug, name, description, sort_order, is_active"
        ),
        {"slug": body.slug, "name": body.name, "desc": body.description, "sort": body.sort_order},
    )
    r = res.fetchone()
    if r is None:
        raise HelpdeskError("Falha ao criar categoria")
    await db.commit()
    log.info("admin.category.created", slug=body.slug, user_id=current_user.user_id)
    return CategoryAdminOut(
        id=r.id,
        slug=r.slug,
        name=r.name,
        description=r.description,
        sort_order=int(r.sort_order),
        is_active=bool(r.is_active),
    )


@router.patch("/categories/{category_id}", response_model=CategoryAdminOut)
async def update_category(
    category_id: str,
    body: CategoryUpdate,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryAdminOut:
    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.sort_order is not None:
        updates["sort_order"] = body.sort_order
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if not updates:
        raise HelpdeskError("Nenhum campo para atualizar")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["cat_id"] = category_id
    res = await db.execute(
        text(
            f"UPDATE helpdesk.categories SET {set_clause} "  # noqa: S608
            f"WHERE id = CAST(:cat_id AS uuid) "
            f"RETURNING id::text, slug, name, description, sort_order, is_active"
        ),
        updates,
    )
    r = res.fetchone()
    if r is None:
        raise NotFoundError("Categoria não encontrada")
    await db.commit()
    log.info("admin.category.updated", category_id=category_id, user_id=current_user.user_id)
    return CategoryAdminOut(
        id=r.id,
        slug=r.slug,
        name=r.name,
        description=r.description,
        sort_order=int(r.sort_order),
        is_active=bool(r.is_active),
    )


# ===========================================================================
# ROLE MANAGEMENT
# ===========================================================================

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
    """Insert or update an explicit role grant. Only it_admin can grant it_admin."""
    if body.role == "it_admin" and current_user.role != "it_admin":
        raise ForbiddenError("Apenas it_admin pode conceder it_admin")

    await db.execute(
        text(
            "INSERT INTO helpdesk.role_overrides (user_uuid, role, granted_by) "
            "VALUES (:uuid, :role, :granted_by) "
            "ON CONFLICT (user_uuid) DO UPDATE "
            "SET role = EXCLUDED.role, granted_by = EXCLUDED.granted_by, granted_at = now()"
        ),
        {"uuid": user_uuid, "role": body.role, "granted_by": current_user.user_id},
    )
    await db.commit()
    log.info(
        "admin.role_override.upserted",
        target_uuid=user_uuid,
        role=body.role,
        granted_by=current_user.user_id,
    )
    return RoleOverrideOut(user_uuid=user_uuid, role=body.role)


@router.delete("/roles/{user_uuid}", status_code=200)
async def delete_role_override(
    user_uuid: str,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    res = await db.execute(
        text("DELETE FROM helpdesk.role_overrides WHERE user_uuid = :uuid RETURNING user_uuid"),
        {"uuid": user_uuid},
    )
    if res.fetchone() is None:
        raise NotFoundError("Override de papel não encontrado")
    await db.commit()
    log.info("admin.role_override.deleted", target_uuid=user_uuid, by=current_user.user_id)
    return {"status": "removed"}


# ===========================================================================
# USERS ADMIN — list users with role overrides
# ===========================================================================


class UserAdminOut(BaseModel):
    model_config = ConfigDict(strict=False)

    uuid: str
    name: str
    email: str
    override_role: str | None


@router.get("/users", response_model=list[UserAdminOut])
async def list_users_admin(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> list[UserAdminOut]:
    overrides_res = await db.execute(
        text("SELECT user_uuid::text, role FROM helpdesk.role_overrides")
    )
    overrides: dict[str, str] = {str(r.user_uuid): str(r.role) for r in overrides_res.fetchall()}

    try:
        users_res = await sec_db.execute(
            text("SELECT u.uuid::text AS uuid, u.name, u.email FROM public.users u ORDER BY u.name")
        )
        users = users_res.fetchall()
    except Exception as exc:
        log.warning("admin.users.sec_db_error", error=str(exc))
        users = []

    return [
        UserAdminOut(
            uuid=str(u.uuid),
            name=str(u.name),
            email=str(u.email),
            override_role=overrides.get(str(u.uuid)),
        )
        for u in users
    ]


# ===========================================================================
# SLA ADMIN
# ===========================================================================


class SlaUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    first_response_hours: int
    resolution_hours: int

    @field_validator("first_response_hours", "resolution_hours")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Must be positive")
        return v


class SlaAdminOut(BaseModel):
    model_config = ConfigDict(strict=False)

    ticket_type: str
    priority: str
    first_response_hours: int
    resolution_hours: int
    description: str | None


@router.get("/sla", response_model=list[SlaAdminOut])
async def list_sla_admin(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> list[SlaAdminOut]:
    rows = await db.execute(
        text(
            "SELECT ticket_type, priority, first_response_hours, resolution_hours, description "
            "FROM helpdesk.sla_matrix "
            "ORDER BY CASE ticket_type WHEN 'incident' THEN 1 WHEN 'service_request' THEN 2 ELSE 3 END, "
            "CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END"
        )
    )
    return [
        SlaAdminOut(
            ticket_type=r.ticket_type,
            priority=r.priority,
            first_response_hours=int(r.first_response_hours),
            resolution_hours=int(r.resolution_hours),
            description=r.description,
        )
        for r in rows.fetchall()
    ]


@router.patch("/sla/{ticket_type}/{priority}", response_model=SlaAdminOut)
async def update_sla(
    ticket_type: str,
    priority: str,
    body: SlaUpdate,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SlaAdminOut:
    _VALID_PRIORITY = frozenset({"low", "normal", "high", "urgent"})
    _VALID_TYPE = frozenset({"incident", "service_request", "change_request"})
    if priority not in _VALID_PRIORITY:
        raise HelpdeskError(f"Prioridade inválida: {priority}")
    if ticket_type not in _VALID_TYPE:
        raise HelpdeskError(f"Tipo inválido: {ticket_type}")
    res = await db.execute(
        text(
            "UPDATE helpdesk.sla_matrix "
            "SET first_response_hours = :frh, resolution_hours = :rh "
            "WHERE priority = :priority AND ticket_type = :ticket_type "
            "RETURNING ticket_type, priority, first_response_hours, resolution_hours, description"
        ),
        {"frh": body.first_response_hours, "rh": body.resolution_hours, "priority": priority, "ticket_type": ticket_type},
    )
    r = res.fetchone()
    if r is None:
        raise NotFoundError("Combinação não encontrada")
    await db.commit()
    log.info("admin.sla.updated", ticket_type=ticket_type, priority=priority, user_id=current_user.user_id)
    return SlaAdminOut(
        ticket_type=r.ticket_type,
        priority=r.priority,
        first_response_hours=int(r.first_response_hours),
        resolution_hours=int(r.resolution_hours),
        description=r.description,
    )


# ===========================================================================
# REPORTS
# ===========================================================================


@router.get("/reports/tickets")
async def export_tickets_csv(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    where = "WHERE 1=1"
    params: dict[str, object] = {}
    if date_from:
        where += " AND t.created_at >= :date_from"
        params["date_from"] = date_from
    if date_to:
        where += " AND t.created_at <= :date_to"
        params["date_to"] = date_to

    rows = await db.execute(
        text(
            f"SELECT t.ticket_number, t.title, t.status, t.priority, "  # noqa: S608
            f"       c.name AS category, t.requester_id::text, t.assignee_id::text, "
            f"       t.created_at::text, t.resolved_at::text, t.first_response_at::text, "
            f"       t.first_response_due_at::text, t.resolution_due_at::text "
            f"FROM helpdesk.tickets t "
            f"LEFT JOIN helpdesk.categories c ON c.id = t.category_id "
            f"{where} ORDER BY t.created_at DESC"
        ),
        params,
    )
    records = rows.fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Número",
            "Título",
            "Status",
            "Prioridade",
            "Categoria",
            "Solicitante (UUID)",
            "Responsável (UUID)",
            "Criado em",
            "Resolvido em",
            "1ª Resposta em",
            "Prazo 1ª Resposta",
            "Prazo Resolução",
        ]
    )
    for r in records:
        writer.writerow(
            [
                r.ticket_number,
                r.title,
                r.status,
                r.priority,
                r.category or "",
                r.requester_id or "",
                r.assignee_id or "",
                r.created_at or "",
                r.resolved_at or "",
                r.first_response_at or "",
                r.first_response_due_at or "",
                r.resolution_due_at or "",
            ]
        )

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tickets.csv"},
    )


class CsatReportItem(BaseModel):
    model_config = ConfigDict(strict=False)

    ticket_number: str
    title: str
    rating: int | None
    comment: str | None
    responded_at: str | None
    closed_at: str | None


@router.get("/reports/csat", response_model=list[CsatReportItem])
async def report_csat(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
) -> list[CsatReportItem]:
    where = "WHERE 1=1"
    params: dict[str, object] = {}
    if date_from:
        where += " AND us.responded_at >= :date_from"
        params["date_from"] = date_from
    if date_to:
        where += " AND us.responded_at <= :date_to"
        params["date_to"] = date_to

    rows = await db.execute(
        text(
            f"SELECT 'HD-' || LPAD(t.number::text, 6, '0') AS ticket_number, "  # noqa: S608
            f"       t.title, us.rating, us.comment, "
            f"       us.responded_at::text, t.resolved_at::text AS closed_at "
            f"FROM helpdesk.user_satisfaction us "
            f"JOIN helpdesk.tickets t ON t.id = us.ticket_id "
            f"{where} ORDER BY us.responded_at DESC NULLS LAST"
        ),
        params,
    )
    return [
        CsatReportItem(
            ticket_number=r.ticket_number,
            title=r.title,
            rating=r.rating,
            comment=r.comment,
            responded_at=r.responded_at,
            closed_at=r.closed_at,
        )
        for r in rows.fetchall()
    ]


# ===========================================================================
# AI MONITOR
# ===========================================================================


class AiCallLogItem(BaseModel):
    model_config = ConfigDict(strict=False)

    id: str
    prompt_key: str
    provider: str
    model_name: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    http_status: int | None
    guardrail_flags: list[str]
    was_fallback: bool
    validation_status: str
    created_at: str


class AiMonitorPage(BaseModel):
    model_config = ConfigDict(strict=False)

    items: list[AiCallLogItem]
    total: int
    page: int
    page_size: int


@router.get("/ai-monitor", response_model=AiMonitorPage)
async def ai_monitor(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=10, le=100)] = 25,
) -> AiMonitorPage:
    offset = (page - 1) * page_size
    count_res = await db.execute(text("SELECT COUNT(*) FROM helpdesk.ai_call_log"))
    total = int(count_res.scalar() or 0)

    rows = await db.execute(
        text(
            "SELECT id::text, prompt_key, provider, model, "
            "       input_tokens, output_tokens, latency_ms, http_status, "
            "       guardrail_flags, was_fallback, validation_status, created_at::text "
            "FROM helpdesk.ai_call_log "
            "ORDER BY created_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"limit": page_size, "offset": offset},
    )
    items = [
        AiCallLogItem(
            id=r.id,
            prompt_key=r.prompt_key,
            provider=r.provider,
            model_name=str(r.model),
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            latency_ms=r.latency_ms,
            http_status=r.http_status,
            guardrail_flags=list(r.guardrail_flags) if r.guardrail_flags else [],
            was_fallback=bool(r.was_fallback),
            validation_status=str(r.validation_status),
            created_at=r.created_at,
        )
        for r in rows.fetchall()
    ]
    return AiMonitorPage(items=items, total=total, page=page, page_size=page_size)


# ===========================================================================
# DEPARTMENTS ADMIN — source of truth: security DB (public.department)
# Sequelize column names: createdat / updatedat (no underscore)
# ===========================================================================


class DepartmentOut(BaseModel):
    model_config = ConfigDict(strict=False)

    id: int
    uuid: str
    name: str
    created_at: str


class DepartmentIn(BaseModel):
    name: str


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> list[DepartmentOut]:
    rows = await sec_db.execute(
        text(
            "SELECT id, uuid, name, createdat::text "
            "FROM public.department ORDER BY name"
        )
    )
    return [
        DepartmentOut(id=r.id, uuid=r.uuid, name=r.name, created_at=r.createdat)
        for r in rows.fetchall()
    ]


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    body: DepartmentIn,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> DepartmentOut:
    new_uuid = str(uuid_lib.uuid4())
    row = await sec_db.execute(
        text(
            "INSERT INTO public.department (uuid, name, createdat, updatedat) "
            "VALUES (:uuid, :name, NOW(), NOW()) "
            "RETURNING id, uuid, name, createdat::text"
        ),
        {"uuid": new_uuid, "name": body.name.strip()},
    )
    r = row.fetchone()
    await sec_db.commit()
    return DepartmentOut(id=r.id, uuid=r.uuid, name=r.name, created_at=r.createdat)


@router.patch("/departments/{dept_id}", response_model=DepartmentOut)
async def update_department(
    dept_id: int,
    body: DepartmentIn,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> DepartmentOut:
    row = await sec_db.execute(
        text(
            "UPDATE public.department SET name = :name, updatedat = NOW() WHERE id = :id "
            "RETURNING id, uuid, name, createdat::text"
        ),
        {"name": body.name.strip(), "id": dept_id},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Departamento não encontrado")
    await sec_db.commit()
    return DepartmentOut(id=r.id, uuid=r.uuid, name=r.name, created_at=r.createdat)


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: int,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> None:
    result = await sec_db.execute(
        text("DELETE FROM public.department WHERE id = :id RETURNING id"),
        {"id": dept_id},
    )
    if result.fetchone() is None:
        raise NotFoundError("Departamento não encontrado")
    await sec_db.commit()


# ===========================================================================
# APPLICATIONS ADMIN — source of truth: security DB (public.applications)
# user_applications links via user_id INTEGER; we map to/from UUID via users.
# ===========================================================================


class ApplicationOut(BaseModel):
    model_config = ConfigDict(strict=False)

    id: int
    app_name: str
    description: str | None
    created_at: str
    user_uuids: list[str]


class ApplicationIn(BaseModel):
    app_name: str
    description: str | None = None
    user_uuids: list[str] = []


class ApplicationUpdate(BaseModel):
    app_name: str | None = None
    description: str | None = None
    user_uuids: list[str] | None = None


async def _fetch_app_users(sec_db: AsyncSession, app_id: int) -> list[str]:
    """Return list of user UUIDs assigned to app_id via public.user_applications."""
    rows = await sec_db.execute(
        text(
            "SELECT u.uuid::text AS user_uuid "
            "FROM public.user_applications ua "
            "JOIN public.users u ON u.id = ua.user_id "
            "WHERE ua.app_id = :app_id ORDER BY u.name"
        ),
        {"app_id": app_id},
    )
    return [r.user_uuid for r in rows.fetchall()]


async def _sync_app_users(sec_db: AsyncSession, app_id: int, user_uuids: list[str]) -> None:
    """Replace user assignments for app_id with the provided UUID list."""
    await sec_db.execute(
        text("DELETE FROM public.user_applications WHERE app_id = :app_id"),
        {"app_id": app_id},
    )
    for u_uuid in user_uuids:
        result = await sec_db.execute(
            text("SELECT id FROM public.users WHERE uuid = :uuid"),
            {"uuid": u_uuid},
        )
        user_row = result.fetchone()
        if user_row:
            await sec_db.execute(
                text(
                    "INSERT INTO public.user_applications (user_id, app_id, createdat, updatedat) "
                    "VALUES (:user_id, :app_id, NOW(), NOW())"
                ),
                {"user_id": user_row.id, "app_id": app_id},
            )


async def _fetch_user_apps(sec_db: AsyncSession, user_uuid: str) -> list[int]:
    """Return app_ids assigned to a user."""
    rows = await sec_db.execute(
        text(
            "SELECT ua.app_id FROM public.user_applications ua "
            "JOIN public.users u ON u.id = ua.user_id WHERE u.uuid = :uuid"
        ),
        {"uuid": user_uuid},
    )
    return [r.app_id for r in rows.fetchall()]


async def _sync_user_apps(sec_db: AsyncSession, user_id: int, app_ids: list[int]) -> None:
    """Replace app assignments for a user."""
    await sec_db.execute(
        text("DELETE FROM public.user_applications WHERE user_id = :uid"),
        {"uid": user_id},
    )
    for aid in app_ids:
        await sec_db.execute(
            text(
                "INSERT INTO public.user_applications (user_id, app_id, createdat, updatedat) "
                "VALUES (:uid, :aid, NOW(), NOW())"
            ),
            {"uid": user_id, "aid": aid},
        )


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> list[ApplicationOut]:
    rows = await sec_db.execute(
        text(
            "SELECT id, app_name, description, createdat::text "
            "FROM public.applications ORDER BY app_name"
        )
    )
    result = []
    for a in rows.fetchall():
        uuids = await _fetch_app_users(sec_db, int(a.id))
        result.append(
            ApplicationOut(
                id=a.id,
                app_name=a.app_name,
                description=a.description,
                created_at=a.createdat,
                user_uuids=uuids,
            )
        )
    return result


@router.post("/applications", response_model=ApplicationOut, status_code=201)
async def create_application(
    body: ApplicationIn,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> ApplicationOut:
    row = await sec_db.execute(
        text(
            "INSERT INTO public.applications (app_name, description, createdat, updatedat) "
            "VALUES (:name, :desc, NOW(), NOW()) "
            "RETURNING id, app_name, description, createdat::text"
        ),
        {"name": body.app_name.strip(), "desc": body.description},
    )
    r = row.fetchone()
    app_id = int(r.id)
    await _sync_app_users(sec_db, app_id, body.user_uuids)
    await sec_db.commit()
    return ApplicationOut(
        id=app_id,
        app_name=r.app_name,
        description=r.description,
        created_at=r.createdat,
        user_uuids=body.user_uuids,
    )


@router.patch("/applications/{app_id}", response_model=ApplicationOut)
async def update_application(
    app_id: int,
    body: ApplicationUpdate,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> ApplicationOut:
    existing = await sec_db.execute(
        text(
            "SELECT id, app_name, description, createdat::text "
            "FROM public.applications WHERE id = :id"
        ),
        {"id": app_id},
    )
    r = existing.fetchone()
    if r is None:
        raise NotFoundError("Aplicação não encontrada")

    new_name = body.app_name.strip() if body.app_name is not None else str(r.app_name)
    new_desc = body.description if body.description is not None else r.description

    updated = await sec_db.execute(
        text(
            "UPDATE public.applications "
            "SET app_name = :name, description = :desc, updatedat = NOW() "
            "WHERE id = :id "
            "RETURNING id, app_name, description, createdat::text"
        ),
        {"name": new_name, "desc": new_desc, "id": app_id},
    )
    u = updated.fetchone()
    if body.user_uuids is not None:
        await _sync_app_users(sec_db, app_id, body.user_uuids)
    user_uuids = await _fetch_app_users(sec_db, app_id)
    await sec_db.commit()
    return ApplicationOut(
        id=app_id,
        app_name=u.app_name,
        description=u.description,
        created_at=u.createdat,
        user_uuids=user_uuids,
    )


@router.delete("/applications/{app_id}", status_code=204)
async def delete_application(
    app_id: int,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> None:
    result = await sec_db.execute(
        text("DELETE FROM public.applications WHERE id = :id RETURNING id"),
        {"id": app_id},
    )
    if result.fetchone() is None:
        raise NotFoundError("Aplicação não encontrada")
    await sec_db.commit()


# ===========================================================================
# USER MANAGEMENT CRUD — security DB (public.users) + helpdesk role_overrides
# active = smallint (0/1); uuid = native UUID type (cast to text on read)
# ===========================================================================


class UserMgmtOut(BaseModel):
    model_config = ConfigDict(strict=False)

    id: int | None = None
    uuid: str
    name: str
    email: str
    login: str | None
    jobtitle: str | None
    department_id: int | None
    department_name: str | None
    superior_id: int | None
    superior_name: str | None
    active: bool
    role: str | None
    sso_manager: bool
    sso_auditor: bool
    procure_manager: bool
    sso_limpeza: bool
    sso_guarita: bool
    dreadmin: bool
    dredepartmentadmin: bool
    supplier_docs_manager: bool
    supplier_docs_auditor: bool
    override_role: str | None
    created_at: str | None
    cpf: str | None = None
    rg: str | None = None
    matricula: str | None = None
    phone: str | None = None
    mobile: str | None = None
    app_ids: list[int] = []


class UserMgmtCreate(BaseModel):
    name: str
    email: str
    password: str
    login: str | None = None
    jobtitle: str | None = None
    department_id: int | None = None
    superior_id: int | None = None
    role: str | None = None
    sso_manager: bool = False
    sso_auditor: bool = False
    procure_manager: bool = False
    sso_limpeza: bool = False
    sso_guarita: bool = False
    dreadmin: bool = False
    dredepartmentadmin: bool = False
    supplier_docs_manager: bool = False
    supplier_docs_auditor: bool = False
    cpf: str | None = None
    rg: str | None = None
    matricula: str | None = None
    phone: str | None = None
    mobile: str | None = None
    app_ids: list[int] = []


class UserMgmtUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    password: str | None = None
    login: str | None = None
    jobtitle: str | None = None
    department_id: int | None = None
    superior_id: int | None = None
    active: bool | None = None
    role: str | None = None
    sso_manager: bool | None = None
    sso_auditor: bool | None = None
    procure_manager: bool | None = None
    sso_limpeza: bool | None = None
    sso_guarita: bool | None = None
    dreadmin: bool | None = None
    dredepartmentadmin: bool | None = None
    supplier_docs_manager: bool | None = None
    supplier_docs_auditor: bool | None = None
    cpf: str | None = None
    rg: str | None = None
    matricula: str | None = None
    phone: str | None = None
    mobile: str | None = None
    app_ids: list[int] | None = None


@router.get("/user-mgmt", response_model=list[UserMgmtOut])
async def list_users_mgmt(
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> list[UserMgmtOut]:
    overrides_res = await db.execute(
        text("SELECT user_uuid::text, role FROM helpdesk.role_overrides")
    )
    overrides: dict[str, str] = {r.user_uuid: r.role for r in overrides_res.fetchall()}

    profiles_res = await db.execute(
        text("SELECT user_uuid, cpf, rg, matricula, phone, mobile FROM helpdesk.user_profiles")
    )
    profiles: dict[str, object] = {r.user_uuid: r for r in profiles_res.fetchall()}

    rows = await sec_db.execute(
        text(
            "SELECT u.id, u.uuid::text, u.name, u.email, u.login, u.jobtitle, "
            "u.departmentid, d.name AS department_name, "
            "u.superiorid, s.name AS superior_name, "
            "u.active, u.role, u.sso_manager, u.sso_auditor, "
            "u.procure_manager, u.sso_limpeza, u.sso_guarita, "
            "u.dreadmin, u.dredepartmentadmin, "
            "u.supplier_docs_manager, u.supplier_docs_auditor, u.createdat::text "
            "FROM public.users u "
            "LEFT JOIN public.department d ON d.id = u.departmentid "
            "LEFT JOIN public.users s ON s.id = u.superiorid "
            "ORDER BY u.name"
        )
    )
    ua_rows = await sec_db.execute(
        text(
            "SELECT u.uuid::text AS user_uuid, ua.app_id "
            "FROM public.user_applications ua "
            "JOIN public.users u ON u.id = ua.user_id"
        )
    )
    user_apps: dict[str, list[int]] = {}
    for ua in ua_rows.fetchall():
        user_apps.setdefault(ua.user_uuid, []).append(ua.app_id)

    result = []
    for r in rows.fetchall():
        p = profiles.get(str(r.uuid))
        result.append(UserMgmtOut(
            id=r.id,
            uuid=r.uuid,
            name=r.name,
            email=r.email,
            login=r.login,
            jobtitle=r.jobtitle,
            department_id=r.departmentid,
            department_name=r.department_name,
            superior_id=r.superiorid,
            superior_name=r.superior_name,
            active=bool(r.active),
            role=r.role,
            sso_manager=bool(r.sso_manager),
            sso_auditor=bool(r.sso_auditor),
            procure_manager=bool(r.procure_manager),
            sso_limpeza=bool(r.sso_limpeza),
            sso_guarita=bool(r.sso_guarita),
            dreadmin=bool(r.dreadmin),
            dredepartmentadmin=bool(r.dredepartmentadmin),
            supplier_docs_manager=bool(r.supplier_docs_manager),
            supplier_docs_auditor=bool(r.supplier_docs_auditor),
            override_role=overrides.get(r.uuid),
            created_at=r.createdat,
            cpf=p.cpf if p else None,
            rg=p.rg if p else None,
            matricula=p.matricula if p else None,
            phone=p.phone if p else None,
            mobile=p.mobile if p else None,
            app_ids=user_apps.get(r.uuid, []),
        ))
    return result


async def _upsert_profile(db: AsyncSession, user_uuid: str, body: UserMgmtCreate | UserMgmtUpdate) -> None:
    """UPSERT helpdesk.user_profiles when any document field is present."""
    if not any([body.cpf, body.rg, body.matricula, body.phone, body.mobile]):
        return
    await db.execute(
        text(
            "INSERT INTO helpdesk.user_profiles (user_uuid, cpf, rg, matricula, phone, mobile) "
            "VALUES (:uuid, :cpf, :rg, :mat, :phone, :mobile) "
            "ON CONFLICT (user_uuid) DO UPDATE SET "
            "cpf = COALESCE(EXCLUDED.cpf, helpdesk.user_profiles.cpf), "
            "rg = COALESCE(EXCLUDED.rg, helpdesk.user_profiles.rg), "
            "matricula = COALESCE(EXCLUDED.matricula, helpdesk.user_profiles.matricula), "
            "phone = COALESCE(EXCLUDED.phone, helpdesk.user_profiles.phone), "
            "mobile = COALESCE(EXCLUDED.mobile, helpdesk.user_profiles.mobile), "
            "updated_at = now()"
        ),
        {"uuid": user_uuid, "cpf": body.cpf, "rg": body.rg,
         "mat": body.matricula, "phone": body.phone, "mobile": body.mobile},
    )


@router.post("/user-mgmt", response_model=UserMgmtOut, status_code=201)
async def create_user_mgmt(
    body: UserMgmtCreate,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> UserMgmtOut:
    login_val = body.login or body.email.split("@")[0]
    new_uuid = str(uuid_lib.uuid4())
    hashed = hash_password(body.password)

    row = await sec_db.execute(
        text(
            "INSERT INTO public.users "
            "(uuid, name, email, password, login, jobtitle, departmentid, superiorid, "
            "active, role, sso_manager, sso_auditor, procure_manager, sso_limpeza, "
            "sso_guarita, dreadmin, dredepartmentadmin, supplier_docs_manager, supplier_docs_auditor, "
            "createdat, updatedat) "
            "VALUES (:uuid, :name, :email, :password, :login, :jobtitle, :dept, :sup, "
            "1, :role, :sso_m, :sso_a, :proc_m, :sso_l, :sso_g, :dra, :drda, :sd_m, :sd_a, NOW(), NOW()) "
            "RETURNING id, uuid::text, name, email, login, jobtitle, "
            "departmentid, superiorid, active, role, sso_manager, sso_auditor, "
            "procure_manager, sso_limpeza, sso_guarita, dreadmin, dredepartmentadmin, "
            "supplier_docs_manager, supplier_docs_auditor, createdat::text"
        ),
        {
            "uuid": new_uuid,
            "name": body.name.strip(),
            "email": body.email.strip().lower(),
            "password": hashed,
            "login": login_val,
            "jobtitle": body.jobtitle,
            "dept": body.department_id,
            "sup": body.superior_id,
            "role": body.role,
            "sso_m": body.sso_manager,
            "sso_a": body.sso_auditor,
            "proc_m": body.procure_manager,
            "sso_l": body.sso_limpeza,
            "sso_g": body.sso_guarita,
            "dra": 1 if body.dreadmin else 0,
            "drda": 1 if body.dredepartmentadmin else 0,
            "sd_m": body.supplier_docs_manager,
            "sd_a": body.supplier_docs_auditor,
        },
    )
    r = row.fetchone()
    if body.app_ids:
        await _sync_user_apps(sec_db, r.id, body.app_ids)
    await sec_db.commit()

    await _upsert_profile(db, new_uuid, body)
    await db.commit()

    dept_row = None
    if r.departmentid:
        dr = await sec_db.execute(
            text("SELECT name FROM public.department WHERE id = :id"), {"id": r.departmentid}
        )
        dept_row = dr.fetchone()

    return UserMgmtOut(
        id=r.id,
        uuid=r.uuid,
        name=r.name,
        email=r.email,
        login=r.login,
        jobtitle=r.jobtitle,
        department_id=r.departmentid,
        department_name=dept_row.name if dept_row else None,
        superior_id=r.superiorid,
        superior_name=None,
        active=bool(r.active),
        role=r.role,
        sso_manager=bool(r.sso_manager),
        sso_auditor=bool(r.sso_auditor),
        procure_manager=bool(r.procure_manager),
        sso_limpeza=bool(r.sso_limpeza),
        sso_guarita=bool(r.sso_guarita),
        dreadmin=bool(r.dreadmin),
        dredepartmentadmin=bool(r.dredepartmentadmin),
        supplier_docs_manager=bool(r.supplier_docs_manager),
        supplier_docs_auditor=bool(r.supplier_docs_auditor),
        override_role=None,
        created_at=r.createdat,
        cpf=body.cpf,
        rg=body.rg,
        matricula=body.matricula,
        phone=body.phone,
        mobile=body.mobile,
        app_ids=body.app_ids,
    )


@router.patch("/user-mgmt/{user_uuid}", response_model=UserMgmtOut)
async def update_user_mgmt(
    user_uuid: str,
    body: UserMgmtUpdate,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> UserMgmtOut:
    existing = await sec_db.execute(
        text(
            "SELECT id, uuid::text, name, email, login, jobtitle, departmentid, superiorid, "
            "active, role, sso_manager, sso_auditor FROM public.users WHERE uuid = :uuid"
        ),
        {"uuid": user_uuid},
    )
    r = existing.fetchone()
    if r is None:
        raise NotFoundError("Usuário não encontrado")

    fields: dict[str, object] = {"uuid": user_uuid, "updatedat": "NOW()"}
    set_clauses = ["updatedat = NOW()"]

    def _set(col: str, val: object) -> None:
        fields[col] = val
        set_clauses.append(f"{col} = :{col}")

    if body.name is not None:
        _set("name", body.name.strip())
    if body.email is not None:
        _set("email", body.email.strip().lower())
    if body.login is not None:
        _set("login", body.login)
    if body.jobtitle is not None:
        _set("jobtitle", body.jobtitle)
    if body.department_id is not None:
        _set("departmentid", body.department_id)
    if body.superior_id is not None:
        _set("superiorid", body.superior_id)
    if body.active is not None:
        _set("active", 1 if body.active else 0)
    if body.role is not None:
        _set("role", body.role)
    if body.sso_manager is not None:
        _set("sso_manager", body.sso_manager)
    if body.sso_auditor is not None:
        _set("sso_auditor", body.sso_auditor)
    if body.procure_manager is not None:
        _set("procure_manager", body.procure_manager)
    if body.sso_limpeza is not None:
        _set("sso_limpeza", body.sso_limpeza)
    if body.sso_guarita is not None:
        _set("sso_guarita", body.sso_guarita)
    if body.dreadmin is not None:
        _set("dreadmin", 1 if body.dreadmin else 0)
    if body.dredepartmentadmin is not None:
        _set("dredepartmentadmin", 1 if body.dredepartmentadmin else 0)
    if body.supplier_docs_manager is not None:
        _set("supplier_docs_manager", body.supplier_docs_manager)
    if body.supplier_docs_auditor is not None:
        _set("supplier_docs_auditor", body.supplier_docs_auditor)
    if body.password:
        _set("password", hash_password(body.password))

    updated = await sec_db.execute(
        text(
            f"UPDATE public.users SET {', '.join(set_clauses)} WHERE uuid = :uuid "  # noqa: S608
            "RETURNING id, uuid::text, name, email, login, jobtitle, "
            "departmentid, superiorid, active, role, sso_manager, sso_auditor, "
            "procure_manager, sso_limpeza, sso_guarita, dreadmin, dredepartmentadmin, "
            "supplier_docs_manager, supplier_docs_auditor, createdat::text"
        ),
        fields,
    )
    u = updated.fetchone()
    if body.app_ids is not None:
        await _sync_user_apps(sec_db, u.id, body.app_ids)
    await sec_db.commit()

    await _upsert_profile(db, user_uuid, body)

    overrides_res = await db.execute(
        text("SELECT role FROM helpdesk.role_overrides WHERE user_uuid = :uuid"),
        {"uuid": user_uuid},
    )
    override_row = overrides_res.fetchone()

    profile_res = await db.execute(
        text("SELECT cpf, rg, matricula, phone, mobile FROM helpdesk.user_profiles WHERE user_uuid = :uuid"),
        {"uuid": user_uuid},
    )
    await db.commit()
    p = profile_res.fetchone()

    dept_row = None
    if u.departmentid:
        dr = await sec_db.execute(
            text("SELECT name FROM public.department WHERE id = :id"), {"id": u.departmentid}
        )
        dept_row = dr.fetchone()

    sup_row = None
    if u.superiorid:
        sr = await sec_db.execute(
            text("SELECT name FROM public.users WHERE id = :id"), {"id": u.superiorid}
        )
        sup_row = sr.fetchone()

    app_ids_out = await _fetch_user_apps(sec_db, user_uuid)

    return UserMgmtOut(
        id=u.id,
        uuid=u.uuid,
        name=u.name,
        email=u.email,
        login=u.login,
        jobtitle=u.jobtitle,
        department_id=u.departmentid,
        department_name=dept_row.name if dept_row else None,
        superior_id=u.superiorid,
        superior_name=sup_row.name if sup_row else None,
        active=bool(u.active),
        role=u.role,
        sso_manager=bool(u.sso_manager),
        sso_auditor=bool(u.sso_auditor),
        procure_manager=bool(u.procure_manager),
        sso_limpeza=bool(u.sso_limpeza),
        sso_guarita=bool(u.sso_guarita),
        dreadmin=bool(u.dreadmin),
        dredepartmentadmin=bool(u.dredepartmentadmin),
        supplier_docs_manager=bool(u.supplier_docs_manager),
        supplier_docs_auditor=bool(u.supplier_docs_auditor),
        override_role=override_row.role if override_row else None,
        created_at=u.createdat,
        cpf=p.cpf if p else None,
        rg=p.rg if p else None,
        matricula=p.matricula if p else None,
        phone=p.phone if p else None,
        mobile=p.mobile if p else None,
        app_ids=app_ids_out,
    )


@router.delete("/user-mgmt/{user_uuid}", status_code=204)
async def delete_user_mgmt(
    user_uuid: str,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_admin_user),
    sec_db: AsyncSession = Depends(get_security_db),
) -> None:
    result = await sec_db.execute(
        text("DELETE FROM public.users WHERE uuid = :uuid RETURNING id"),
        {"uuid": user_uuid},
    )
    if result.fetchone() is None:
        raise NotFoundError("Usuário não encontrado")
    await sec_db.commit()


# ===========================================================================
# PUBLIC KB READ — any authenticated user
# ===========================================================================


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
            "SELECT a.id::text, a.slug, a.title, a.tags, a.trust_level, "
            "a.created_at::text "
            "FROM helpdesk.kb_articles a "
            "WHERE a.is_archived = false "
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
    row = await db.execute(
        text(
            "SELECT a.id::text, a.slug, a.title, a.tags, a.trust_level, "
            "a.created_at::text, v.body_markdown "
            "FROM helpdesk.kb_articles a "
            "JOIN helpdesk.kb_article_versions v ON v.article_id = a.id "
            "WHERE a.slug = :slug AND a.is_archived = false "
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
