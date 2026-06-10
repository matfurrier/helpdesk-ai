"""Admin endpoints — KB, categories, users, SLA, reports, AI monitor."""

from __future__ import annotations

import csv
import io
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.errors import ForbiddenError, HelpdeskError, NotFoundError
from app.db.session import get_db, get_security_db
from app.schemas.auth import UserOut
from app.schemas.kb import ArticleCreate, ArticleIngestOut
from app.services.rag import ingester

router = APIRouter(prefix="/admin", tags=["admin"])
kb_router = APIRouter(prefix="/kb", tags=["kb"])
log = structlog.get_logger()

_ADMIN_ROLES = frozenset({"it_admin", "it_lead"})
_IT_ROLES = frozenset({"it_agent", "it_lead", "it_admin"})


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


async def _it_user(request: Request, response: Response) -> UserOut:
    user = await get_current_user(request, response)
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
        _TRUST = frozenset({"internal_published", "internal_draft", "internal_only", "external_doc"})
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
            text(f"UPDATE helpdesk.kb_articles SET {set_clause} WHERE slug = :slug"),
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
            {"aid": article_id, "version": new_version, "body": body.body_markdown, "edited_by": current_user.user_id},
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
        text("UPDATE helpdesk.kb_articles SET is_archived = false WHERE slug = :slug RETURNING id::text AS aid"),
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
            id=r.id, slug=r.slug, name=r.name, description=r.description,
            sort_order=int(r.sort_order), is_active=bool(r.is_active),
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
        id=r.id, slug=r.slug, name=r.name, description=r.description,
        sort_order=int(r.sort_order), is_active=bool(r.is_active),
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
            f"UPDATE helpdesk.categories SET {set_clause} "
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
        id=r.id, slug=r.slug, name=r.name, description=r.description,
        sort_order=int(r.sort_order), is_active=bool(r.is_active),
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
    log.info("admin.role_override.upserted", target_uuid=user_uuid, role=body.role, granted_by=current_user.user_id)
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
            "SELECT priority, first_response_hours, resolution_hours, description "
            "FROM helpdesk.sla_matrix "
            "ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END"
        )
    )
    return [
        SlaAdminOut(
            priority=r.priority,
            first_response_hours=int(r.first_response_hours),
            resolution_hours=int(r.resolution_hours),
            description=r.description,
        )
        for r in rows.fetchall()
    ]


@router.patch("/sla/{priority}", response_model=SlaAdminOut)
async def update_sla(
    priority: str,
    body: SlaUpdate,
    request: Request,
    current_user: UserOut = Depends(_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SlaAdminOut:
    _VALID = frozenset({"low", "normal", "high", "urgent"})
    if priority not in _VALID:
        raise HelpdeskError(f"Prioridade inválida: {priority}")
    res = await db.execute(
        text(
            "UPDATE helpdesk.sla_matrix "
            "SET first_response_hours = :frh, resolution_hours = :rh "
            "WHERE priority = :priority "
            "RETURNING priority, first_response_hours, resolution_hours, description"
        ),
        {"frh": body.first_response_hours, "rh": body.resolution_hours, "priority": priority},
    )
    r = res.fetchone()
    if r is None:
        raise NotFoundError("Prioridade não encontrada")
    await db.commit()
    log.info("admin.sla.updated", priority=priority, user_id=current_user.user_id)
    return SlaAdminOut(
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
            f"SELECT t.ticket_number, t.title, t.status, t.priority, "
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
    writer.writerow([
        "Número", "Título", "Status", "Prioridade", "Categoria",
        "Solicitante (UUID)", "Responsável (UUID)",
        "Criado em", "Resolvido em", "1ª Resposta em",
        "Prazo 1ª Resposta", "Prazo Resolução",
    ])
    for r in records:
        writer.writerow([
            r.ticket_number, r.title, r.status, r.priority, r.category or "",
            r.requester_id or "", r.assignee_id or "",
            r.created_at or "", r.resolved_at or "", r.first_response_at or "",
            r.first_response_due_at or "", r.resolution_due_at or "",
        ])

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
            f"SELECT t.ticket_number, t.title, us.rating, us.comment, "
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
            id=r.id, slug=r.slug, title=r.title,
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
        id=r.id, slug=r.slug, title=r.title,
        tags=list(r.tags) if r.tags else [],
        trust_level=str(r.trust_level),
        created_at=r.created_at,
        body_markdown=r.body_markdown,
    )
