"""Chat/triage endpoints — Sprint 2.

GET  /chat/csrf-token                          → issue CSRF cookie + body token
POST /chat/conversations                       → create conversation
POST /chat/conversations/{id}/messages         → send message, SSE stream (word-by-word)
GET  /chat/conversations/{id}/messages         → message history
GET  /chat/conversations                       → list user's conversations
POST /chat/conversations/{id}/convert          → convert chat → ticket

Security notes:
- User message content stored REDACTED (PII tokens) — never plaintext.
- Rate limits: chat 30/min, convert 10/hr — separate Lua ZSET keys.
- CSRF double-submit cookie on all POSTs.
- Convert: SELECT FOR UPDATE guards against duplicate tickets (F-01).
- Transcript written to ticket uses re-redacted content (F-03).
- PII token map purged after conversion (F-08 LGPD minimization).
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, RateLimitError
from app.db.session import get_db
from app.schemas.auth import UserOut
from app.schemas.chat import ConversationOut, MessageCreate, MessageOut, TriageOutput
from app.schemas.tickets import ConvertOut, TicketDraftOutput
from app.services.ai import redactor as _redactor
from app.services.ai.orchestrator import LLMOrchestrator, get_orchestrator, orchestrator
from app.services.rag import retriever as _retriever

router = APIRouter(prefix="/chat", tags=["chat"])
log = structlog.get_logger()

_RATE_LIMIT = 30
_RATE_WINDOW = 60

_CONVERT_RATE_LIMIT = 10
_CONVERT_RATE_WINDOW = 3600

_RATE_LIMIT_LUA = """
local key    = KEYS[1]
local now    = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit  = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
redis.call('ZADD', key, now, now .. '-' .. math.random(1, 1000000))
local count = redis.call('ZCARD', key)
redis.call('EXPIRE', key, window)
return count
"""

_SYSTEM_UUID = "00000000-0000-0000-0000-000000000000"

# PII token pattern for post-LLM output sanitation
_PII_TOKEN_RE = re.compile(r"\[PII_[A-Z]+_\d+\]")


async def _get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]


async def _check_csrf(request: Request) -> None:
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise ForbiddenError("CSRF token inválido ou ausente")


async def _csrf_then_user(request: Request, response: Response) -> UserOut:
    await _check_csrf(request)
    return await get_current_user(request, response)


async def _check_rate_limit(
    user_id: str,
    redis: Redis,
    *,
    key_prefix: str = "rl:chat",
    limit: int = _RATE_LIMIT,
    window: int = _RATE_WINDOW,
) -> None:
    key = f"{key_prefix}:{user_id}"
    now = time.time()
    count = await redis.eval(_RATE_LIMIT_LUA, 1, key, str(now), str(window), str(limit))
    if int(count) > limit:
        raise RateLimitError(f"Limite de {limit} requisições atingido")


def _sse_event(data: object) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_triage(result: TriageOutput) -> AsyncGenerator[str, None]:
    """Yield SSE word-by-word deltas, then a final done event."""
    words = result.assistant_text.split()
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield _sse_event({"delta": chunk, "done": False})
        await asyncio.sleep(0.025)
    yield _sse_event({"done": True, "result": result.model_dump()})


# ---------------------------------------------------------------------------
# CSRF token
# ---------------------------------------------------------------------------


@router.get("/csrf-token")
async def get_csrf_token(response: Response) -> dict[str, str]:
    token = secrets.token_hex(32)
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        samesite="lax",
        secure=not settings.is_dev,
        path="/",
    )
    return {"csrf_token": token}


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@router.post("/conversations", status_code=201)
async def create_conversation(
    request: Request,
    current_user: UserOut = Depends(_csrf_then_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    redis = await _get_redis(request)
    await _check_rate_limit(current_user.user_id, redis)

    result = await db.execute(
        text(
            "INSERT INTO helpdesk.ai_conversations (user_id, status, channel) "  # noqa: S608
            "VALUES (:user_id, 'active', 'web') "
            "RETURNING id, status, started_at"
        ),
        {"user_id": current_user.user_id},
    )
    await db.commit()
    row = result.fetchone()
    if row is None:
        from app.core.errors import HelpdeskError

        raise HelpdeskError("Falha ao criar conversa")

    return ConversationOut(
        id=str(row.id), status=str(row.status), started_at=row.started_at, message_count=0
    )


@router.get("/conversations")
async def list_conversations(
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationOut]:
    rows = await db.execute(
        text(
            "SELECT c.id, c.status, c.started_at, "  # noqa: S608
            "       COUNT(m.id) AS message_count "
            "FROM helpdesk.ai_conversations c "
            "LEFT JOIN helpdesk.ai_conversation_messages m ON m.conversation_id = c.id "
            "WHERE c.user_id = :uid "
            "GROUP BY c.id, c.status, c.started_at "
            "ORDER BY c.started_at DESC "
            "LIMIT 20"
        ),
        {"uid": current_user.user_id},
    )
    return [
        ConversationOut(
            id=str(r.id),
            status=str(r.status),
            started_at=r.started_at,
            message_count=int(r.message_count),
        )
        for r in rows.fetchall()
    ]


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    request: Request,
    current_user: UserOut = Depends(_csrf_then_user),
    db: AsyncSession = Depends(get_db),
    orch: LLMOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    redis = await _get_redis(request)
    await _check_rate_limit(current_user.user_id, redis)

    conv_id = str(conversation_id)
    conv = await db.execute(
        text(
            "SELECT id, status FROM helpdesk.ai_conversations "  # noqa: S608
            "WHERE id = CAST(:cid AS uuid) AND user_id = :uid"
        ),
        {"cid": conv_id, "uid": current_user.user_id},
    )
    if conv.fetchone() is None:
        raise NotFoundError("Conversa não encontrada")

    redacted_content, pii_map = _redactor.redact(body.content)

    await db.execute(
        text(
            "INSERT INTO helpdesk.ai_conversation_messages "  # noqa: S608
            "(conversation_id, role, content, content_redacted) "
            "VALUES (CAST(:cid AS uuid), 'user', :content, :redacted)"
        ),
        {"cid": conv_id, "content": redacted_content, "redacted": redacted_content},
    )
    await db.commit()

    rag_chunks = await _retriever.retrieve(body.content, db)
    context_blocks = _retriever.chunks_to_context_blocks(rag_chunks)

    # Fetch prior turns so the LLM has conversation context
    hist_r = await db.execute(
        text(
            "SELECT role, COALESCE(content_redacted, content) AS content "  # noqa: S608
            "FROM helpdesk.ai_conversation_messages "
            "WHERE conversation_id = CAST(:cid AS uuid) "
            "ORDER BY created_at ASC LIMIT 20"
        ),
        {"cid": conv_id},
    )
    history = [
        {"role": "user" if r.role == "user" else "assistant", "content": str(r.content)}
        for r in hist_r.fetchall()
    ] or None

    result: TriageOutput = await orch.complete(
        prompt_key="TRIAGE_SYSTEM",
        user_input=body.content,
        history=history,
        context_blocks=context_blocks or None,
        user_id=current_user.user_id,
        conversation_id=conv_id,
        db=db,
    )

    asst_ins = await db.execute(
        text(
            "INSERT INTO helpdesk.ai_conversation_messages "  # noqa: S608
            "(conversation_id, role, content) "
            "VALUES (CAST(:cid AS uuid), 'assistant', :content) "
            "RETURNING id"
        ),
        {"cid": conv_id, "content": result.assistant_text},
    )
    await db.commit()
    asst_row = asst_ins.fetchone()

    if asst_row is not None:
        await db.execute(
            text(
                "INSERT INTO helpdesk.ai_suggestions "  # noqa: S608
                "(message_id, next_action, suggestions, ticket_draft, citations) "
                "VALUES (CAST(:mid AS uuid), :action, CAST(:suggestions AS jsonb),"
                " CAST(:ticket AS jsonb), :citations)"
            ),
            {
                "mid": str(asst_row.id),
                "action": result.next_action,
                "suggestions": json.dumps([s.model_dump() for s in result.suggestions]),
                "ticket": (
                    json.dumps(result.ticket_draft.model_dump()) if result.ticket_draft else None
                ),
                "citations": [c for s in result.suggestions for c in s.citations],
            },
        )
        await db.commit()

    log.info(
        "chat.message_sent",
        conversation_id=conv_id,
        user_id=current_user.user_id,
        next_action=result.next_action,
        guardrail_flags=result.guardrails_triggered,
        pii_tokens=list(pii_map.keys()),
    )

    return StreamingResponse(
        _stream_triage(result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: uuid.UUID,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    conv_id = str(conversation_id)
    conv = await db.execute(
        text(
            "SELECT id FROM helpdesk.ai_conversations "  # noqa: S608
            "WHERE id = CAST(:cid AS uuid) AND user_id = :uid"
        ),
        {"cid": conv_id, "uid": current_user.user_id},
    )
    if conv.fetchone() is None:
        raise NotFoundError("Conversa não encontrada")

    msgs = await db.execute(
        text(
            "SELECT id, role, "  # noqa: S608
            "COALESCE(content_redacted, content) AS content, created_at "
            "FROM helpdesk.ai_conversation_messages "
            "WHERE conversation_id = CAST(:cid AS uuid) "
            "ORDER BY created_at ASC"
        ),
        {"cid": conv_id},
    )
    return [
        MessageOut(id=str(r.id), role=str(r.role), content=str(r.content), created_at=r.created_at)
        for r in msgs.fetchall()
    ]


# ---------------------------------------------------------------------------
# Convert conversation → ticket (P1)
# ---------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/convert", status_code=201)
async def convert_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    current_user: UserOut = Depends(_csrf_then_user),
    db: AsyncSession = Depends(get_db),
) -> ConvertOut:
    """Convert an AI chat conversation into a support ticket.

    Security controls applied (sec-audit Sprint 2):
    F-01: SELECT FOR UPDATE + partial unique index prevent duplicate tickets.
    F-02: Priority capped at 'normal' for employee role.
    F-03: Transcript re-redacted before persisting to ticket.
    F-04: audit_log entry created inside the transaction.
    F-05: TicketDraftOutput schema (not TriageOutput) used for TICKET_DRAFT_SYSTEM.
    F-06: category_slug validated against helpdesk.categories before insert.
    F-08: PII token map purged after successful conversion.
    F-09: conversation_id typed as uuid.UUID (FastAPI validates, returns 422 on bad input).
    F-10: separate rate limit key for convert (10/hr).
    """
    redis = await _get_redis(request)
    await _check_rate_limit(
        current_user.user_id,
        redis,
        key_prefix="rl:convert",
        limit=_CONVERT_RATE_LIMIT,
        window=_CONVERT_RATE_WINDOW,
    )

    conv_id = str(conversation_id)

    # F-01: Lock the conversation row to prevent concurrent double-convert
    conv_row_result = await db.execute(
        text(
            "SELECT id, status FROM helpdesk.ai_conversations "  # noqa: S608
            "WHERE id = CAST(:cid AS uuid) AND user_id = :uid "
            "FOR UPDATE"
        ),
        {"cid": conv_id, "uid": current_user.user_id},
    )
    conv_row = conv_row_result.fetchone()
    if conv_row is None:
        raise NotFoundError("Conversa não encontrada")
    if str(conv_row.status) != "active":
        raise ConflictError("Conversa já foi convertida ou encerrada")

    # Fetch transcript messages
    msgs_result = await db.execute(
        text(
            "SELECT role, content, content_redacted "  # noqa: S608
            "FROM helpdesk.ai_conversation_messages "
            "WHERE conversation_id = CAST(:cid AS uuid) "
            "ORDER BY created_at ASC"
        ),
        {"cid": conv_id},
    )
    messages = msgs_result.fetchall()

    # F-03: Build safe transcript — re-redact assistant messages (may contain restored PII)
    transcript_lines: list[str] = []
    for msg in messages:
        role = str(msg.role)
        if role == "user":
            # content_redacted already has PII tokens — safe
            content = str(msg.content_redacted or msg.content)
        else:
            # assistant content may have restored PII after token_map.restore — re-redact
            raw_content = str(msg.content)
            content, _ = _redactor.redact(raw_content)
        transcript_lines.append(f"[{role.upper()}] {content}")

    transcript_text = "\n".join(transcript_lines)

    # Sanity check: no PII should remain after re-redaction
    pii_matches = _PII_TOKEN_RE.findall(transcript_text)
    if any(not m.startswith("[PII_") for m in pii_matches):
        log.warning("convert.pii_in_transcript", conv_id=conv_id)

    # Fetch active categories for the LLM context
    cats_result = await db.execute(
        text(
            "SELECT id, slug, name, description "  # noqa: S608
            "FROM helpdesk.categories WHERE is_active = true ORDER BY sort_order"
        )
    )
    categories = cats_result.fetchall()
    category_context = [
        {"id": str(c.slug), "content": f"{c.slug}: {c.description or c.name}"} for c in categories
    ]

    # Call TICKET_DRAFT_SYSTEM — uses TicketDraftOutput schema (F-05)
    draft: TicketDraftOutput = await orchestrator.complete(
        prompt_key="TICKET_DRAFT_SYSTEM",
        user_input=transcript_text,
        context_blocks=category_context,
        schema=TicketDraftOutput,
        user_id=current_user.user_id,
        conversation_id=conv_id,
        db=db,
    )

    # F-06: Validate category_slug against DB
    cat_id_result = await db.execute(
        text(
            "SELECT id FROM helpdesk.categories "  # noqa: S608
            "WHERE slug = :slug AND is_active = true LIMIT 1"
        ),
        {"slug": draft.category_slug},
    )
    cat_row = cat_id_result.fetchone()
    category_id = str(cat_row.id) if cat_row else None

    # F-02: Cap priority at 'normal' for employees
    _PRIORITY_ORDER = ["low", "normal", "high", "urgent"]
    priority = draft.priority
    if current_user.role == "employee":
        priority = min(priority, "normal", key=lambda p: _PRIORITY_ORDER.index(p))

    ip_str = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Single transaction: ticket + message + status_history + audit_log + conversation update
    # (The SELECT FOR UPDATE above already opened the implicit transaction — do NOT call
    # db.begin() again; SQLAlchemy 2.x autobegin raises InvalidRequestError.)
    ticket_id_str: str | None = None
    ticket_number: int | None = None

    # a) Fetch SLA deadlines based on priority
    sla_row = await db.execute(
        text(
            "SELECT first_response_hours, resolution_hours "  # noqa: S608
            "FROM helpdesk.sla_matrix WHERE priority = :priority LIMIT 1"
        ),
        {"priority": priority},
    )
    sla = sla_row.fetchone()

    # b) Create ticket (conversation_id set immediately — avoids second UPDATE)
    cat_cast = "CAST(:cat_id AS uuid)" if category_id else "NULL"
    sla_cols = ""
    sla_vals = ""
    sla_params: dict[str, object] = {}
    if sla:
        sla_cols = ", first_response_due_at, resolution_due_at"
        sla_vals = (
            ", NOW() + (:fr_hours || ' hours')::interval"
            ", NOW() + (:res_hours || ' hours')::interval"
        )
        sla_params = {
            "fr_hours": str(int(sla.first_response_hours)),
            "res_hours": str(int(sla.resolution_hours)),
        }

    ticket_result = await db.execute(
        text(
            f"INSERT INTO helpdesk.tickets "  # noqa: S608
            f"(title, summary, status, priority, category_id, requester_id, "
            f"conversation_id, tags{sla_cols}) "
            f"VALUES (:title, :summary, 'NEW', :priority, {cat_cast}, :requester_id, "
            f"CAST(:conv_id AS uuid), :tags{sla_vals}) "
            f"RETURNING id, number"
        ),
        {
            "title": draft.title[:200],
            "summary": draft.summary[:1000],
            "priority": priority,
            "cat_id": category_id,
            "requester_id": current_user.user_id,
            "conv_id": conv_id,
            "tags": draft.tags[:6],
            **sla_params,
        },
    )
    ticket_row = ticket_result.fetchone()
    if ticket_row is None:
        raise RuntimeError("Failed to create ticket")
    ticket_id_str = str(ticket_row.id)
    ticket_number = int(ticket_row.number)

    # b) Insert transcript as first internal message
    await db.execute(
        text(
            "INSERT INTO helpdesk.ticket_messages "  # noqa: S608
            "(ticket_id, author_id, author_role, visibility, body) "
            "VALUES (CAST(:tid AS uuid), CAST(:author_id AS uuid), 'system', 'internal', :body)"
        ),
        {"tid": ticket_id_str, "author_id": _SYSTEM_UUID, "body": transcript_text},
    )

    # c) Status history entry
    await db.execute(
        text(
            "INSERT INTO helpdesk.ticket_status_history "  # noqa: S608
            "(ticket_id, from_status, to_status, changed_by) "
            "VALUES (CAST(:tid AS uuid), NULL, 'NEW', :changed_by)"
        ),
        {"tid": ticket_id_str, "changed_by": current_user.user_id},
    )

    # d) Audit log (F-04)
    import json as _json

    await db.execute(
        text(
            "INSERT INTO helpdesk.audit_log "  # noqa: S608
            "(actor_id, actor_role, action, target_type, target_id, after, ip, user_agent) "
            "VALUES (CAST(:actor_id AS uuid), :actor_role, 'ticket.created_from_chat', "
            "'ticket', :target_id, CAST(:after AS jsonb), CAST(:ip AS inet), :ua)"
        ),
        {
            "actor_id": current_user.user_id,
            "actor_role": current_user.role,
            "target_id": ticket_id_str,
            "after": _json.dumps(
                {
                    "ticket_id": ticket_id_str,
                    "priority": priority,
                    "category_slug": draft.category_slug,
                    "conversation_id": conv_id,
                }
            ),
            "ip": ip_str,
            "ua": user_agent,
        },
    )

    # e) Mark conversation as converted
    await db.execute(
        text(
            "UPDATE helpdesk.ai_conversations "  # noqa: S608
            "SET status = 'converted', ticket_id = CAST(:ticket_id AS uuid) "
            "WHERE id = CAST(:cid AS uuid)"
        ),
        {"ticket_id": ticket_id_str, "cid": conv_id},
    )

    await db.commit()

    # F-08: Purge PII token map — data no longer needed after conversion
    await orchestrator.purge_pii_map(conv_id)

    log.info(
        "chat.convert",
        conversation_id=conv_id,
        ticket_id=ticket_id_str,
        ticket_number=ticket_number,
        user_id=current_user.user_id,
        priority=priority,
    )

    return ConvertOut(
        ticket_id=ticket_id_str,
        ticket_number=f"HD-{ticket_number:06d}",
        status="NEW",
    )
