"""Fire-and-forget notification helpers called after DB commits.

Each public function is meant to be scheduled via asyncio.create_task().
They open their own DB sessions so they don't interfere with request sessions.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import text

from app.core.config import settings
from app.services.notifications import email as _email
from app.services.notifications.outbox import enqueue

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_user_email(user_id: str) -> str | None:
    from app.db.session import _SecuritySession  # noqa: PLC0415

    try:
        async with _SecuritySession() as s:
            row = await s.execute(
                text(
                    "SELECT email FROM public.users "  # noqa: S608
                    "WHERE uuid = CAST(:uid AS uuid) LIMIT 1"
                ),
                {"uid": user_id},
            )
            r = row.fetchone()
            return str(r.email) if r and r.email else None
    except Exception as exc:  # noqa: BLE001
        log.warning("hooks.email_lookup_failed", user_id=user_id, error=str(exc))
        return None


async def _get_ticket_info(ticket_id: str) -> dict[str, object] | None:
    from app.db.session import _Session  # noqa: PLC0415

    try:
        async with _Session() as db:
            row = await db.execute(
                text(
                    "SELECT t.number, t.title, t.status, t.priority, "  # noqa: S608
                    "       t.requester_id, t.assignee_id, c.name AS category_name "
                    "FROM helpdesk.tickets t "
                    "LEFT JOIN helpdesk.categories c ON c.id = t.category_id "
                    "WHERE t.id = CAST(:tid AS uuid) LIMIT 1"
                ),
                {"tid": ticket_id},
            )
            r = row.fetchone()
            if r is None:
                return None
            number = int(r.number)
            return {
                "number": number,
                "ticket_number": f"HD-{number:06d}",
                "title": str(r.title),
                "status": str(r.status),
                "priority": str(r.priority),
                "requester_id": str(r.requester_id),
                "assignee_id": str(r.assignee_id) if r.assignee_id else None,
                "category_name": str(r.category_name) if r.category_name else None,
            }
    except Exception as exc:  # noqa: BLE001
        log.warning("hooks.ticket_lookup_failed", ticket_id=ticket_id, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Public notification tasks
# ---------------------------------------------------------------------------


async def notify_ticket_opened(
    ticket_id: str,
    ticket_number: str,
    title: str,
    priority: str,
    category: str | None,
    requester_id: str,
    requester_email: str | None,
) -> None:
    """Notify IT team inbox + confirmation to requester."""
    from app.db.session import _Session  # noqa: PLC0415

    it_email = settings.it_team_email
    subject, body = _email.tpl_ticket_opened(
        ticket_number, title, requester_email or requester_id, priority, category
    )

    async with _Session() as db:
        # Always notify IT team
        await enqueue(
            db,
            user_id=requester_id,
            template_key="ticket_opened",
            to=[it_email],
            subject=subject,
            body_html=body,
        )
        # Confirmation to requester
        if requester_email:
            subj_conf = f"[{ticket_number}] Seu chamado foi registrado"
            body_conf = _email._BASE.format(  # noqa: SLF001
                content=(
                    f"<p>Seu chamado <b>{ticket_number}</b> foi registrado com sucesso!</p>"
                    f"<p><b>Título:</b> {title}</p>"
                    f"<p>Nossa equipe de TI entrará em contato em breve.</p>"
                )
            )
            await enqueue(
                db,
                user_id=requester_id,
                template_key="ticket_opened_requester",
                to=[requester_email],
                subject=subj_conf,
                body_html=body_conf,
            )
        await db.commit()

    log.info("hooks.ticket_opened_enqueued", ticket_id=ticket_id)


async def notify_new_message(
    ticket_id: str,
    author_id: str,
    author_name: str,
    is_agent: bool,
    message_body: str,
) -> None:
    """Notify relevant parties when a new public message is posted."""
    from app.db.session import _Session  # noqa: PLC0415

    info = await _get_ticket_info(ticket_id)
    if info is None:
        return

    ticket_number = str(info["ticket_number"])
    title = str(info["title"])
    requester_id = str(info["requester_id"])
    assignee_id = info["assignee_id"]

    subject, body = _email.tpl_ticket_message(
        ticket_number, title, author_name, message_body, base_url=settings.frontend_url
    )

    async with _Session() as db:
        if is_agent:
            # Agent replied → notify requester
            req_email = await _get_user_email(requester_id)
            if req_email:
                await enqueue(
                    db,
                    user_id=requester_id,
                    template_key="ticket_message",
                    to=[req_email],
                    subject=subject,
                    body_html=body,
                )
        else:
            # Requester replied → notify assignee or IT team
            if assignee_id:
                assign_email = await _get_user_email(str(assignee_id))
                to = [assign_email] if assign_email else [settings.it_team_email]
            else:
                to = [settings.it_team_email]
            await enqueue(
                db,
                user_id=author_id,
                template_key="ticket_message",
                to=to,
                subject=subject,
                body_html=body,
            )
        await db.commit()

    log.info("hooks.message_enqueued", ticket_id=ticket_id, is_agent=is_agent)


async def notify_status_changed(
    ticket_id: str,
    new_status: str,
    ticket_number: str,
    title: str,
    requester_id: str,
) -> None:
    """Notify requester of status change. On CLOSED, generate CSAT invitation."""
    from app.db.session import _Session  # noqa: PLC0415

    req_email = await _get_user_email(requester_id)
    subject, body = _email.tpl_ticket_status(ticket_number, title, new_status)

    csat_token: str | None = None

    async with _Session() as db:
        if req_email:
            await enqueue(
                db,
                user_id=requester_id,
                template_key="ticket_status",
                to=[req_email],
                subject=subject,
                body_html=body,
            )

        if new_status == "CLOSED":
            # Check if satisfaction row already exists (idempotent)
            existing = await db.execute(
                text(
                    "SELECT id FROM helpdesk.user_satisfaction "  # noqa: S608
                    "WHERE ticket_id = CAST(:tid AS uuid) LIMIT 1"
                ),
                {"tid": ticket_id},
            )
            if existing.fetchone() is None:
                csat_token = str(uuid.uuid4())
                await db.execute(
                    text(
                        "INSERT INTO helpdesk.user_satisfaction "  # noqa: S608
                        "(ticket_id, csat_token) "
                        "VALUES (CAST(:tid AS uuid), CAST(:token AS uuid))"
                    ),
                    {"tid": ticket_id, "token": csat_token},
                )

        await db.commit()

    if new_status == "CLOSED" and csat_token and req_email:
        csat_url = f"{settings.frontend_url}/csat/{csat_token}"
        csat_subj, csat_body = _email.tpl_csat_request(ticket_number, title, csat_url)

        async with _Session() as db:
            await enqueue(
                db,
                user_id=requester_id,
                template_key="csat_request",
                to=[req_email],
                subject=csat_subj,
                body_html=csat_body,
            )
            await db.commit()

    log.info(
        "hooks.status_changed_enqueued",
        ticket_id=ticket_id,
        new_status=new_status,
        csat_created=csat_token is not None,
    )


async def notify_assigned(
    ticket_id: str,
    assignee_id: str,
    ticket_number: str,
    title: str,
) -> None:
    """Notify assignee when a ticket is assigned to them."""
    from app.db.session import _Session  # noqa: PLC0415

    assign_email = await _get_user_email(assignee_id)
    if not assign_email:
        return

    # Get assignee name from security DB
    from app.db.session import _SecuritySession  # noqa: PLC0415

    assignee_name = assignee_id
    try:
        async with _SecuritySession() as s:
            row = await s.execute(
                text("SELECT name FROM public.users WHERE uuid = CAST(:uid AS uuid) LIMIT 1"),  # noqa: S608
                {"uid": assignee_id},
            )
            r = row.fetchone()
            if r and r.name:
                assignee_name = str(r.name)
    except Exception:  # noqa: BLE001, S110
        pass

    subject, body = _email.tpl_ticket_assigned(ticket_number, title, assignee_name)

    async with _Session() as db:
        await enqueue(
            db,
            user_id=assignee_id,
            template_key="ticket_assigned",
            to=[assign_email],
            subject=subject,
            body_html=body,
        )
        await db.commit()

    log.info("hooks.assigned_enqueued", ticket_id=ticket_id, assignee_id=assignee_id)
