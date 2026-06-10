"""Ticket endpoints — Sprint 2/3.

GET  /tickets/stats                 → KPIs (IT only)
GET  /tickets/                      → list (IT: all; employee: own)
GET  /tickets/{ticket_id}           → single ticket
GET  /tickets/{ticket_id}/messages  → message thread
POST /tickets/{ticket_id}/messages  → add reply or internal note
PATCH /tickets/{ticket_id}/status   → change status (IT only)
PATCH /tickets/{ticket_id}/assign   → assign/unassign (IT only)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError
from app.db.session import get_db, get_security_db
from app.schemas.auth import UserOut
from app.schemas.tickets import (
    AddMessageIn,
    AgentOut,
    AssignUpdateIn,
    CategoryOut,
    CategoryUpdateIn,
    SlaMatrixOut,
    StatusUpdateIn,
    TicketListOut,
    TicketMessageOut,
    TicketOut,
    TicketStatsOut,
)
from app.services.notifications import hooks as _hooks

router = APIRouter(prefix="/tickets", tags=["tickets"])
log = structlog.get_logger()

_IT_ROLES = frozenset({"it_agent", "it_lead", "it_admin"})


# ---------------------------------------------------------------------------
# GET /tickets/categories — list active categories (authenticated)
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryOut]:
    rows = await db.execute(
        text(
            "SELECT id, slug, name, description, sort_order "  # noqa: S608
            "FROM helpdesk.categories WHERE is_active = true "
            "ORDER BY sort_order, name"
        )
    )
    return [
        CategoryOut(
            id=str(r.id),
            slug=str(r.slug),
            name=str(r.name),
            description=str(r.description) if r.description else None,
            sort_order=int(r.sort_order),
        )
        for r in rows.fetchall()
    ]


# ---------------------------------------------------------------------------
# GET /tickets/sla — SLA matrix (authenticated)
# ---------------------------------------------------------------------------


@router.get("/sla", response_model=list[SlaMatrixOut])
async def list_sla(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SlaMatrixOut]:
    rows = await db.execute(
        text(
            "SELECT priority, first_response_hours, resolution_hours, description "  # noqa: S608
            "FROM helpdesk.sla_matrix "
            "ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 "
            "  WHEN 'normal' THEN 3 ELSE 4 END"
        )
    )
    return [
        SlaMatrixOut(
            priority=str(r.priority),
            first_response_hours=int(r.first_response_hours),
            resolution_hours=int(r.resolution_hours),
            description=str(r.description) if r.description else None,
        )
        for r in rows.fetchall()
    ]


_ACTIVE_STATUSES = ("NEW", "TRIAGE", "IN_PROGRESS", "WAITING_USER", "REOPENED")

# Status transitions allowed for IT agents
_TRANSITIONS: dict[str, list[str]] = {
    "NEW": ["TRIAGE", "IN_PROGRESS", "CANCELLED"],
    "TRIAGE": ["IN_PROGRESS", "WAITING_USER", "RESOLVED", "CANCELLED"],
    "IN_PROGRESS": ["WAITING_USER", "RESOLVED", "CANCELLED"],
    "WAITING_USER": ["IN_PROGRESS", "RESOLVED", "CLOSED"],
    "RESOLVED": ["CLOSED", "REOPENED"],
    "CLOSED": ["REOPENED"],
    "REOPENED": ["IN_PROGRESS", "WAITING_USER", "RESOLVED", "CANCELLED"],
    "AUTO_RESOLVED": ["CLOSED", "REOPENED"],
    "CANCELLED": ["REOPENED"],
}


async def _check_csrf(request: Request) -> None:
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise ForbiddenError("CSRF token inválido ou ausente")


async def _csrf_then_user(request: Request, response: Response) -> UserOut:
    await _check_csrf(request)
    return await get_current_user(request, response)


def _is_agent(user: UserOut) -> bool:
    return user.role in _IT_ROLES


# ---------------------------------------------------------------------------
# GET /tickets/filter-options — filter metadata (IT only, before /stats)
# ---------------------------------------------------------------------------


@router.get("/filter-options")
async def get_filter_options(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> dict[str, object]:
    if not _is_agent(current_user):
        raise ForbiddenError("Acesso restrito à equipe de TI")

    # Anos presentes nos tickets
    years_r = await db.execute(
        text(
            "SELECT DISTINCT EXTRACT(YEAR FROM created_at)::int AS y "  # noqa: S608
            "FROM helpdesk.tickets ORDER BY y DESC"
        )
    )
    years = [int(r.y) for r in years_r.fetchall()]

    # Todos os requester UUIDs distintos
    uuids_r = await db.execute(
        text("SELECT DISTINCT requester_id::text AS uid FROM helpdesk.tickets")  # noqa: S608
    )
    uuids = [r.uid for r in uuids_r.fetchall()]

    departments: dict[int, str] = {}
    users: list[dict[str, object]] = []
    if uuids:
        try:
            sec_r = await sec_db.execute(
                text(
                    "SELECT u.uuid::text, u.name, u.login, u.departmentid, "  # noqa: S608
                    "       d.name AS departmentname "
                    "FROM public.users u "
                    "LEFT JOIN public.department d ON d.id = u.departmentid "
                    "WHERE u.uuid::text = ANY(:uuids)"
                ),
                {"uuids": uuids},
            )
            for u in sec_r.fetchall():
                users.append({"id": str(u.uuid), "name": str(u.name or u.login or u.uuid)})
                if u.departmentid is not None:
                    departments[int(u.departmentid)] = str(
                        u.departmentname or f"Dept {u.departmentid}"
                    )
        except Exception:  # noqa: BLE001, S110
            pass

    # Categories
    cat_rows = await db.execute(
        text(
            "SELECT id, slug, name, description, sort_order "  # noqa: S608
            "FROM helpdesk.categories WHERE is_active = true ORDER BY sort_order, name"
        )
    )
    categories = [
        CategoryOut(
            id=str(c.id),
            slug=str(c.slug),
            name=str(c.name),
            description=str(c.description) if c.description else None,
            sort_order=int(c.sort_order),
        )
        for c in cat_rows.fetchall()
    ]

    from app.schemas.tickets import FilterDept, FilterOptionsOut, FilterUser  # local import

    return FilterOptionsOut(
        years=years,
        departments=sorted(
            [FilterDept(id=k, name=v) for k, v in departments.items()],
            key=lambda d: d.name,
        ),
        users=sorted(
            [FilterUser(id=u["id"], name=str(u["name"])) for u in users],
            key=lambda u: u.name,
        ),
        categories=categories,
    ).model_dump()


# ---------------------------------------------------------------------------
# GET /tickets/agents — IT staff available for assignment (IT only)
# ---------------------------------------------------------------------------


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> list[AgentOut]:
    if not _is_agent(current_user):
        raise ForbiddenError("Acesso restrito à equipe de TI")

    # UUIDs with explicit role overrides (it_admin, it_lead)
    override_rows = await db.execute(
        text("SELECT user_uuid::text AS uid FROM helpdesk.role_overrides")  # noqa: S608
    )
    override_uids = [str(r.uid) for r in override_rows.fetchall()]

    # UUIDs from IT department in security DB
    dept_uids: list[str] = []
    try:
        dept_rows = await sec_db.execute(
            text(
                f"SELECT uuid::text AS uid FROM {settings.security_schema}.users "  # noqa: S608
                "WHERE departmentid = :dept_id"
            ),
            {"dept_id": settings.it_department_id},
        )
        dept_uids = [str(r.uid) for r in dept_rows.fetchall()]
    except Exception:  # noqa: BLE001
        pass

    all_uids = list(
        set(override_uids + dept_uids + list(settings.bootstrap_admin_uuid_set))
    )
    if not all_uids:
        return []

    agents: list[AgentOut] = []
    try:
        name_rows = await sec_db.execute(
            text(
                f"SELECT uuid::text AS uid, name, login "  # noqa: S608
                f"FROM {settings.security_schema}.users "
                "WHERE uuid::text = ANY(:uids)"
            ),
            {"uids": all_uids},
        )
        agents = [
            AgentOut(id=str(nr.uid), name=str(nr.name or nr.login or nr.uid))
            for nr in name_rows.fetchall()
        ]
    except Exception:  # noqa: BLE001
        pass

    return sorted(agents, key=lambda a: a.name)


# ---------------------------------------------------------------------------
# Helper — resolve dept UUIDs via security DB
# ---------------------------------------------------------------------------


async def _resolve_dept_uuids(dept_id: int, sec_db: AsyncSession) -> list[str]:
    """Retorna todos os UUIDs de usuários de um departamento (security DB)."""
    try:
        r = await sec_db.execute(
            text("SELECT uuid::text FROM public.users WHERE departmentid = :dept"),  # noqa: S608
            {"dept": dept_id},
        )
        return [row.uuid for row in r.fetchall()]
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# GET /tickets/stats — KPIs (IT only, must be before /{ticket_id})
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=TicketStatsOut)
async def get_ticket_stats(
    year: Annotated[int | None, Query()] = None,
    month: Annotated[int | None, Query()] = None,
    dept_id: Annotated[int | None, Query()] = None,
    user_id: Annotated[str | None, Query()] = None,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> TicketStatsOut:
    if not _is_agent(current_user):
        raise ForbiddenError("Acesso restrito à equipe de TI")

    conditions = ["1=1"]
    params: dict[str, object] = {}

    if year:
        conditions.append("EXTRACT(YEAR FROM created_at) = :year")
        params["year"] = year
    if month:
        conditions.append("EXTRACT(MONTH FROM created_at) = :month")
        params["month"] = month
    if user_id:
        conditions.append("requester_id = CAST(:uid AS uuid)")
        params["uid"] = user_id
    if dept_id:
        dept_uuids = await _resolve_dept_uuids(dept_id, sec_db)
        if not dept_uuids:
            return TicketStatsOut(
                total_count=0,
                open_count=0,
                pending_count=0,
                resolved_today=0,
                unassigned_count=0,
                avg_first_response_minutes=None,
            )
        conditions.append("requester_id = ANY(:dept_uuids)")
        params["dept_uuids"] = dept_uuids

    where = " AND ".join(conditions)
    params["active"] = list(_ACTIVE_STATUSES)

    row = await db.execute(
        text(
            f"SELECT "  # noqa: S608
            f"  COUNT(*) AS total_count, "
            f"  COUNT(*) FILTER (WHERE status = ANY(:active)) AS open_count, "
            f"  COUNT(*) FILTER (WHERE status = 'WAITING_USER') AS pending_count, "
            f"  COUNT(*) FILTER (WHERE status IN ('RESOLVED','AUTO_RESOLVED') "
            f"    AND resolved_at >= CURRENT_DATE) AS resolved_today, "
            f"  COUNT(*) FILTER (WHERE assignee_id IS NULL "
            f"    AND status = ANY(:active)) AS unassigned_count, "
            f"  AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 60.0) "
            f"    FILTER (WHERE first_response_at IS NOT NULL) AS avg_first_response_minutes "
            f"FROM helpdesk.tickets WHERE {where}"
        ),
        params,
    )
    r = row.fetchone()

    # CSAT stats — separate query to avoid breaking the primary stats aggregation
    csat_conditions = [c for c in conditions if "assignee_id" not in c]
    csat_where = " AND ".join(csat_conditions) if csat_conditions else "1=1"
    csat_params = {k: v for k, v in params.items() if k not in ("active",)}
    csat_row = await db.execute(
        text(
            f"SELECT "  # noqa: S608
            f"  ROUND(AVG(us.rating)::numeric, 1) AS avg_rating, "
            f"  COUNT(us.id) FILTER (WHERE us.responded_at IS NOT NULL) AS total_responses "
            f"FROM helpdesk.user_satisfaction us "
            f"JOIN helpdesk.tickets t ON t.id = us.ticket_id "
            f"WHERE us.responded_at IS NOT NULL AND {csat_where}"
        ),
        csat_params,
    )
    cr = csat_row.fetchone()

    return TicketStatsOut(
        total_count=int(r.total_count or 0),
        open_count=int(r.open_count or 0),
        pending_count=int(r.pending_count or 0),
        resolved_today=int(r.resolved_today or 0),
        unassigned_count=int(r.unassigned_count or 0),
        avg_first_response_minutes=(
            float(r.avg_first_response_minutes) if r.avg_first_response_minutes else None
        ),
        csat_avg_rating=float(cr.avg_rating) if cr and cr.avg_rating else None,
        csat_total_responses=int(cr.total_responses or 0) if cr else 0,
    )


# ---------------------------------------------------------------------------
# GET /tickets/ — list
# ---------------------------------------------------------------------------


@router.get("/", response_model=TicketListOut)
async def list_tickets(
    status: Annotated[str | None, Query()] = None,
    priority: Annotated[str | None, Query()] = None,
    category_slug: Annotated[str | None, Query()] = None,
    unassigned: Annotated[bool, Query()] = False,
    year: Annotated[int | None, Query()] = None,
    month: Annotated[int | None, Query()] = None,
    dept_id: Annotated[int | None, Query()] = None,
    user_id: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> TicketListOut:
    agent = _is_agent(current_user)
    offset = (page - 1) * limit

    conditions = ["1=1"]
    params: dict[str, object] = {"limit": limit, "offset": offset}

    if not agent:
        conditions.append("t.requester_id = :uid")
        params["uid"] = current_user.user_id

    if status:
        conditions.append("t.status = :status")
        params["status"] = status.upper()

    if priority:
        conditions.append("t.priority = :priority")
        params["priority"] = priority.lower()

    if category_slug:
        conditions.append("c.slug = :cat_slug")
        params["cat_slug"] = category_slug

    if unassigned and agent:
        conditions.append("t.assignee_id IS NULL AND t.status = ANY(:active)")
        params["active"] = list(_ACTIVE_STATUSES)

    if agent:
        if year:
            conditions.append("EXTRACT(YEAR FROM t.created_at) = :year")
            params["year"] = year
        if month:
            conditions.append("EXTRACT(MONTH FROM t.created_at) = :month")
            params["month"] = month
        if user_id:
            conditions.append("t.requester_id = CAST(:filter_uid AS uuid)")
            params["filter_uid"] = user_id
        if dept_id:
            dept_uuids = await _resolve_dept_uuids(dept_id, sec_db)
            if not dept_uuids:
                return TicketListOut(items=[], total=0)
            conditions.append("t.requester_id = ANY(:dept_uuids)")
            params["dept_uuids"] = dept_uuids

    where = " AND ".join(conditions)
    base_from = (
        "FROM helpdesk.tickets t "
        "LEFT JOIN helpdesk.categories c ON c.id = t.category_id "
        "LEFT JOIN helpdesk.user_satisfaction us ON us.ticket_id = t.id"
    )

    count_row = await db.execute(
        text(f"SELECT COUNT(*) {base_from} WHERE {where}"),  # noqa: S608
        params,
    )
    total = int(count_row.scalar() or 0)

    rows = await db.execute(
        text(
            f"SELECT t.id, t.number, t.title, t.status, t.priority, "  # noqa: S608
            f"       t.requester_id, t.assignee_id, t.tags, "
            f"       t.resolution_due_at, t.first_response_at, t.resolved_at, "
            f"       t.created_at, t.updated_at, "
            f"       c.slug AS category_slug, c.name AS category_name, "
            f"       us.rating AS csat_rating "
            f"{base_from} WHERE {where} "
            f"ORDER BY "
            f"  CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            f"                  WHEN 'normal' THEN 2 ELSE 3 END, "
            f"  t.created_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    )

    raw = rows.fetchall()

    # Batch-lookup names from security DB for all unique user IDs
    all_uids: list[str] = list(
        {str(r.requester_id) for r in raw} | {str(r.assignee_id) for r in raw if r.assignee_id}
    )
    name_map: dict[str, str] = {}
    if all_uids:
        try:
            name_rows = await sec_db.execute(
                text(
                    "SELECT uuid::text AS uid, name FROM public.users "  # noqa: S608
                    "WHERE uuid::text = ANY(:uids)"
                ),
                {"uids": all_uids},
            )
            name_map = {str(nr.uid): str(nr.name) for nr in name_rows.fetchall() if nr.name}
        except Exception:  # noqa: BLE001, S110
            pass  # names stay empty on security-DB error

    from app.schemas.tickets import TicketListItem  # local to avoid circular

    items = [
        TicketListItem(
            id=str(r.id),
            number=int(r.number),
            ticket_number=f"HD-{int(r.number):06d}",
            title=str(r.title),
            status=str(r.status),
            priority=str(r.priority),
            category_slug=str(r.category_slug) if r.category_slug else None,
            category_name=str(r.category_name) if r.category_name else None,
            requester_id=str(r.requester_id),
            requester_name=name_map.get(str(r.requester_id)),
            assignee_id=str(r.assignee_id) if r.assignee_id else None,
            assignee_name=name_map.get(str(r.assignee_id)) if r.assignee_id else None,
            tags=list(r.tags) if r.tags else [],
            resolution_due_at=r.resolution_due_at,
            first_response_at=r.first_response_at,
            resolved_at=r.resolved_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
            csat_rating=float(r.csat_rating) if r.csat_rating is not None else None,
        )
        for r in raw
    ]
    return TicketListOut(items=items, total=total)


# ---------------------------------------------------------------------------
# Private helper — fetch ticket row without requester name lookup
# ---------------------------------------------------------------------------


async def _fetch_ticket(
    ticket_id: uuid.UUID,
    current_user: UserOut,
    db: AsyncSession,
) -> TicketOut:
    """Fetch a single ticket and enforce authorization. Does NOT populate requester_name."""
    row = await db.execute(
        text(
            "SELECT t.id, t.number, t.title, t.summary, t.status, t.priority, "  # noqa: S608
            "       t.category_id, t.requester_id, t.assignee_id, t.conversation_id, "
            "       t.tags, t.created_at, t.updated_at, "
            "       t.first_response_due_at, t.resolution_due_at, "
            "       t.first_response_at, t.resolved_at, "
            "       c.slug AS category_slug, c.name AS category_name, "
            "       tm.body AS transcript, "
            "       us.rating AS csat_rating, us.responded_at AS csat_responded_at "
            "FROM helpdesk.tickets t "
            "LEFT JOIN helpdesk.categories c ON c.id = t.category_id "
            "LEFT JOIN helpdesk.ticket_messages tm "
            "  ON tm.ticket_id = t.id AND tm.author_role = 'system' "
            "LEFT JOIN helpdesk.user_satisfaction us ON us.ticket_id = t.id "
            "WHERE t.id = CAST(:tid AS uuid) "
            "ORDER BY tm.created_at ASC "
            "LIMIT 1"
        ),
        {"tid": str(ticket_id)},
    )
    r = row.fetchone()
    if r is None:
        raise NotFoundError("Ticket não encontrado")

    if not _is_agent(current_user) and str(r.requester_id) != current_user.user_id:
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
        category_name=str(r.category_name) if r.category_name else None,
        category_slug=str(r.category_slug) if r.category_slug else None,
        requester_id=str(r.requester_id),
        requester_name=None,
        requester_login=None,
        assignee_id=str(r.assignee_id) if r.assignee_id else None,
        conversation_id=str(r.conversation_id) if r.conversation_id else None,
        tags=list(r.tags) if r.tags else [],
        first_response_due_at=r.first_response_due_at,
        resolution_due_at=r.resolution_due_at,
        first_response_at=r.first_response_at,
        resolved_at=r.resolved_at,
        created_at=r.created_at,
        updated_at=r.updated_at,
        transcript=str(r.transcript) if r.transcript else None,
        csat_rating=float(r.csat_rating) if r.csat_rating is not None else None,
        csat_responded_at=r.csat_responded_at,
    )


# ---------------------------------------------------------------------------
# GET /tickets/{ticket_id} — single ticket (with requester name lookup)
# ---------------------------------------------------------------------------


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> TicketOut:
    ticket = await _fetch_ticket(ticket_id, current_user, db)

    # Batch-lookup requester + assignee names from security DB (best-effort)
    try:
        uids_to_lookup = [ticket.requester_id]
        if ticket.assignee_id:
            uids_to_lookup.append(ticket.assignee_id)
        name_rows = await sec_db.execute(
            text(
                "SELECT uuid::text AS uid, name, login FROM public.users "  # noqa: S608
                "WHERE uuid::text = ANY(:uids)"
            ),
            {"uids": uids_to_lookup},
        )
        uid_info: dict[str, tuple[str | None, str | None]] = {
            str(nr.uid): (str(nr.name) if nr.name else None, str(nr.login) if nr.login else None)
            for nr in name_rows.fetchall()
        }
        req_info = uid_info.get(ticket.requester_id, (None, None))
        assign_info = (
            uid_info.get(ticket.assignee_id or "", (None, None))
            if ticket.assignee_id
            else (None, None)
        )
        ticket = ticket.model_copy(
            update={
                "requester_name": req_info[0],
                "requester_login": req_info[1],
                "assignee_name": assign_info[0],
            }
        )
    except Exception:  # noqa: BLE001, S110
        pass  # fallback: names stay None

    return ticket


# ---------------------------------------------------------------------------
# GET /tickets/{ticket_id}/messages
# ---------------------------------------------------------------------------


@router.get("/{ticket_id}/messages", response_model=list[TicketMessageOut])
async def list_messages(
    ticket_id: uuid.UUID,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TicketMessageOut]:
    agent = _is_agent(current_user)

    # Ownership check
    owner_row = await db.execute(
        text("SELECT requester_id FROM helpdesk.tickets WHERE id = CAST(:tid AS uuid)"),  # noqa: S608
        {"tid": str(ticket_id)},
    )
    ticket_owner = owner_row.fetchone()
    if ticket_owner is None:
        raise NotFoundError("Ticket não encontrado")
    if not agent and str(ticket_owner.requester_id) != current_user.user_id:
        raise ForbiddenError("Acesso negado")

    # Agents see all messages; requester sees only public ones
    vis_filter = "" if agent else "AND visibility = 'public'"
    rows = await db.execute(
        text(
            f"SELECT id, author_id, author_role, visibility, body, created_at "  # noqa: S608
            f"FROM helpdesk.ticket_messages "
            f"WHERE ticket_id = CAST(:tid AS uuid) {vis_filter} "
            f"ORDER BY created_at ASC"
        ),
        {"tid": str(ticket_id)},
    )
    return [
        TicketMessageOut(
            id=str(r.id),
            author_id=str(r.author_id),
            author_role=str(r.author_role),
            visibility=str(r.visibility),
            body=str(r.body),
            created_at=r.created_at,
        )
        for r in rows.fetchall()
    ]


# ---------------------------------------------------------------------------
# POST /tickets/{ticket_id}/messages — add reply or internal note
# ---------------------------------------------------------------------------


@router.post("/{ticket_id}/messages", status_code=201, response_model=TicketMessageOut)
async def add_message(
    ticket_id: uuid.UUID,
    body: AddMessageIn,
    request: Request,
    current_user: UserOut = Depends(_csrf_then_user),
    db: AsyncSession = Depends(get_db),
) -> TicketMessageOut:
    agent = _is_agent(current_user)
    tid = str(ticket_id)

    # Only IT agents can post internal notes
    if body.visibility == "internal" and not agent:
        raise ForbiddenError("Notas internas são restritas à equipe de TI")

    # Ownership / access check
    owner_row = await db.execute(
        text(
            "SELECT requester_id, status, first_response_at "  # noqa: S608
            "FROM helpdesk.tickets WHERE id = CAST(:tid AS uuid)"
        ),
        {"tid": tid},
    )
    ticket = owner_row.fetchone()
    if ticket is None:
        raise NotFoundError("Ticket não encontrado")
    if not agent and str(ticket.requester_id) != current_user.user_id:
        raise ForbiddenError("Acesso negado")

    # Block any message on a CSAT-evaluated ticket
    if str(ticket.status) == "CLOSED":
        csat_check = await db.execute(
            text(
                "SELECT 1 FROM helpdesk.user_satisfaction "  # noqa: S608
                "WHERE ticket_id = CAST(:tid AS uuid) AND responded_at IS NOT NULL LIMIT 1"
            ),
            {"tid": tid},
        )
        if csat_check.fetchone() is not None:
            raise ForbiddenError("Chamado já avaliado pelo usuário não pode ser alterado")

    author_role = "agent" if agent else "requester"

    msg_row = await db.execute(
        text(
            "INSERT INTO helpdesk.ticket_messages "  # noqa: S608
            "(ticket_id, author_id, author_role, visibility, body) "
            "VALUES (CAST(:tid AS uuid), :author_id, :author_role, :visibility, :body) "
            "RETURNING id, created_at"
        ),
        {
            "tid": tid,
            "author_id": current_user.user_id,
            "author_role": author_role,
            "visibility": body.visibility,
            "body": body.body,
        },
    )
    msg = msg_row.fetchone()

    # Set first_response_at if this is the first public agent reply
    if agent and body.visibility == "public" and ticket.first_response_at is None:
        await db.execute(
            text(
                "UPDATE helpdesk.tickets SET first_response_at = NOW(), updated_at = NOW() "  # noqa: S608
                "WHERE id = CAST(:tid AS uuid)"
            ),
            {"tid": tid},
        )

    await db.commit()
    log.info(
        "ticket.message_added",
        ticket_id=tid,
        author=current_user.user_id,
        visibility=body.visibility,
    )

    # Fire-and-forget email notification (only for public messages)
    if body.visibility == "public":
        asyncio.create_task(
            _hooks.notify_new_message(
                ticket_id=tid,
                author_id=current_user.user_id,
                author_name=current_user.name or current_user.user_id,
                is_agent=agent,
                message_body=body.body,
            )
        )

    return TicketMessageOut(
        id=str(msg.id),
        author_id=current_user.user_id,
        author_role=author_role,
        visibility=body.visibility,
        body=body.body,
        created_at=msg.created_at,
    )


# ---------------------------------------------------------------------------
# PATCH /tickets/{ticket_id}/status — change status (IT only)
# ---------------------------------------------------------------------------


@router.patch("/{ticket_id}/status", response_model=TicketOut)
async def update_status(
    ticket_id: uuid.UUID,
    body: StatusUpdateIn,
    request: Request,
    current_user: UserOut = Depends(_csrf_then_user),
    db: AsyncSession = Depends(get_db),
) -> TicketOut:
    if not _is_agent(current_user):
        raise ForbiddenError("Acesso restrito à equipe de TI")

    tid = str(ticket_id)
    row = await db.execute(
        text("SELECT id, status FROM helpdesk.tickets WHERE id = CAST(:tid AS uuid) FOR UPDATE"),  # noqa: S608
        {"tid": tid},
    )
    ticket = row.fetchone()
    if ticket is None:
        raise NotFoundError("Ticket não encontrado")

    current_status = str(ticket.status)
    new_status = body.status
    allowed = _TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ForbiddenError(f"Transição {current_status} → {new_status} não permitida")

    # Block reopening a ticket that has already been CSAT-evaluated
    if new_status == "REOPENED" and current_status == "CLOSED":
        csat_check = await db.execute(
            text(
                "SELECT 1 FROM helpdesk.user_satisfaction "  # noqa: S608
                "WHERE ticket_id = CAST(:tid AS uuid) AND responded_at IS NOT NULL LIMIT 1"
            ),
            {"tid": tid},
        )
        if csat_check.fetchone() is not None:
            raise ForbiddenError("Chamado já avaliado pelo usuário não pode ser reaberto")

    ts_fields = ""
    if new_status in ("RESOLVED", "AUTO_RESOLVED"):
        ts_fields = ", resolved_at = NOW()"
    elif new_status == "CLOSED":
        ts_fields = ", closed_at = NOW()"

    await db.execute(
        text(
            f"UPDATE helpdesk.tickets "  # noqa: S608
            f"SET status = :status, updated_at = NOW(){ts_fields} "
            f"WHERE id = CAST(:tid AS uuid)"
        ),
        {"status": new_status, "tid": tid},
    )
    await db.execute(
        text(
            "INSERT INTO helpdesk.ticket_status_history "  # noqa: S608
            "(ticket_id, from_status, to_status, changed_by, reason) "
            "VALUES (CAST(:tid AS uuid), :from_s, :to_s, :by, :reason)"
        ),
        {
            "tid": tid,
            "from_s": current_status,
            "to_s": new_status,
            "by": current_user.user_id,
            "reason": body.reason,
        },
    )
    await db.commit()
    log.info(
        "ticket.status_changed",
        ticket_id=tid,
        from_s=current_status,
        to_s=new_status,
        actor=current_user.user_id,
    )

    # Fetch ticket info for notification (number + title + requester)
    info_row = await db.execute(
        text(
            "SELECT number, title, requester_id FROM helpdesk.tickets "  # noqa: S608
            "WHERE id = CAST(:tid AS uuid) LIMIT 1"
        ),
        {"tid": tid},
    )
    info = info_row.fetchone()
    if info is not None:
        asyncio.create_task(
            _hooks.notify_status_changed(
                ticket_id=tid,
                new_status=new_status,
                ticket_number=f"HD-{int(info.number):06d}",
                title=str(info.title),
                requester_id=str(info.requester_id),
            )
        )

    return await _fetch_ticket(ticket_id, current_user, db)


# ---------------------------------------------------------------------------
# PATCH /tickets/{ticket_id}/assign — assign / unassign (IT only)
# ---------------------------------------------------------------------------


@router.patch("/{ticket_id}/assign", response_model=TicketOut)
async def assign_ticket(
    ticket_id: uuid.UUID,
    body: AssignUpdateIn,
    request: Request,
    current_user: UserOut = Depends(_csrf_then_user),
    db: AsyncSession = Depends(get_db),
) -> TicketOut:
    if not _is_agent(current_user):
        raise ForbiddenError("Acesso restrito à equipe de TI")

    tid = str(ticket_id)
    exists = await db.execute(
        text("SELECT id FROM helpdesk.tickets WHERE id = CAST(:tid AS uuid)"),  # noqa: S608
        {"tid": tid},
    )
    if exists.fetchone() is None:
        raise NotFoundError("Ticket não encontrado")

    await db.execute(
        text(
            "UPDATE helpdesk.tickets SET assignee_id = :assignee, updated_at = NOW() "  # noqa: S608
            "WHERE id = CAST(:tid AS uuid)"
        ),
        {"assignee": body.assignee_id, "tid": tid},
    )
    await db.commit()
    log.info(
        "ticket.assigned", ticket_id=tid, assignee=body.assignee_id, actor=current_user.user_id
    )

    if body.assignee_id:
        info_row = await db.execute(
            text(
                "SELECT number, title FROM helpdesk.tickets "  # noqa: S608
                "WHERE id = CAST(:tid AS uuid) LIMIT 1"
            ),
            {"tid": tid},
        )
        info = info_row.fetchone()
        if info is not None:
            asyncio.create_task(
                _hooks.notify_assigned(
                    ticket_id=tid,
                    assignee_id=body.assignee_id,
                    ticket_number=f"HD-{int(info.number):06d}",
                    title=str(info.title),
                )
            )

    return await _fetch_ticket(ticket_id, current_user, db)


# ---------------------------------------------------------------------------
# PATCH /tickets/{ticket_id}/category — change category (IT only)
# ---------------------------------------------------------------------------


@router.patch("/{ticket_id}/category", response_model=TicketOut)
async def update_category(
    ticket_id: uuid.UUID,
    body: CategoryUpdateIn,
    request: Request,
    current_user: UserOut = Depends(_csrf_then_user),
    db: AsyncSession = Depends(get_db),
) -> TicketOut:
    if not _is_agent(current_user):
        raise ForbiddenError("Acesso restrito à equipe de TI")

    tid = str(ticket_id)

    # Resolve slug → uuid
    new_cat_id: str | None = None
    if body.category_slug:
        cat_row = await db.execute(
            text(
                "SELECT id FROM helpdesk.categories "  # noqa: S608
                "WHERE slug = :slug AND is_active = true LIMIT 1"
            ),
            {"slug": body.category_slug},
        )
        cat = cat_row.fetchone()
        if cat is None:
            raise NotFoundError(f"Categoria '{body.category_slug}' não encontrada")
        new_cat_id = str(cat.id)

    exists = await db.execute(
        text("SELECT id FROM helpdesk.tickets WHERE id = CAST(:tid AS uuid)"),  # noqa: S608
        {"tid": tid},
    )
    if exists.fetchone() is None:
        raise NotFoundError("Ticket não encontrado")

    cat_cast = "CAST(:cat_id AS uuid)" if new_cat_id else "NULL"
    await db.execute(
        text(
            f"UPDATE helpdesk.tickets SET category_id = {cat_cast}, updated_at = NOW() "  # noqa: S608
            f"WHERE id = CAST(:tid AS uuid)"
        ),
        {"cat_id": new_cat_id, "tid": tid},
    )
    await db.commit()
    log.info(
        "ticket.category_changed",
        ticket_id=tid,
        category=body.category_slug,
        actor=current_user.user_id,
    )

    return await _fetch_ticket(ticket_id, current_user, db)
