"""Notification outbox: enqueue + async worker that drains pending rows."""

from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.notifications.email import send_email

log = structlog.get_logger()

_POLL_INTERVAL = 60  # seconds
_BATCH_SIZE = 20


async def enqueue(
    db: AsyncSession,
    *,
    user_id: str,
    template_key: str,
    to: list[str],
    subject: str,
    body_html: str,
) -> None:
    """Insert one row into notification_outbox (email channel, will be drained by worker)."""
    payload = {"to": to, "subject": subject, "body_html": body_html}
    await db.execute(
        text(
            "INSERT INTO helpdesk.notification_outbox "  # noqa: S608
            "(id, user_id, channel, template_key, payload) "
            "VALUES (CAST(:id AS uuid), :user_id, 'email', :template_key, CAST(:payload AS jsonb))"
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "template_key": template_key,
            "payload": json.dumps(payload),
        },
    )


async def _process_batch(db: AsyncSession) -> int:
    """Fetch up to _BATCH_SIZE pending rows, send emails, update status. Returns count sent."""
    rows_result = await db.execute(
        text(
            "SELECT id, payload FROM helpdesk.notification_outbox "  # noqa: S608
            "WHERE status = 'pending' AND scheduled_for <= NOW() "
            "ORDER BY scheduled_for ASC "
            f"LIMIT {_BATCH_SIZE} "
            "FOR UPDATE SKIP LOCKED"
        )
    )
    rows = rows_result.fetchall()
    if not rows:
        return 0

    sent = 0
    for row in rows:
        row_id = str(row.id)
        try:
            payload: dict[str, object] = (
                row.payload if isinstance(row.payload, dict) else json.loads(row.payload)
            )
            to = payload.get("to", [])
            subject = str(payload.get("subject", ""))
            body_html = str(payload.get("body_html", ""))
            ok = await send_email(to=list(to), subject=subject, body_html=body_html)  # type: ignore[arg-type]
            new_status = "sent" if ok else "failed"
            await db.execute(
                text(
                    "UPDATE helpdesk.notification_outbox "  # noqa: S608
                    "SET status = :st, attempts = attempts + 1, "
                    "sent_at = CASE WHEN :st = 'sent' THEN NOW() ELSE sent_at END "
                    "WHERE id = CAST(:id AS uuid)"
                ),
                {"st": new_status, "id": row_id},
            )
            if ok:
                sent += 1
        except Exception as exc:  # noqa: BLE001
            log.error("outbox.row_error", row_id=row_id, error=str(exc))
            await db.execute(
                text(
                    "UPDATE helpdesk.notification_outbox "  # noqa: S608
                    "SET status = 'failed', attempts = attempts + 1, last_error = :err "
                    "WHERE id = CAST(:id AS uuid)"
                ),
                {"err": str(exc)[:500], "id": row_id},
            )

    await db.commit()
    return sent


async def run_worker(stop_event: asyncio.Event) -> None:
    """Background worker — polls notification_outbox every _POLL_INTERVAL seconds."""
    from app.db.session import _Session  # noqa: PLC0415

    log.info("outbox_worker.started")
    while not stop_event.is_set():
        try:
            async with _Session() as db:
                sent = await _process_batch(db)
                if sent:
                    log.info("outbox_worker.batch_sent", count=sent)
        except Exception as exc:  # noqa: BLE001
            log.error("outbox_worker.error", error=str(exc))
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL)
        except TimeoutError:
            pass
    log.info("outbox_worker.stopped")
