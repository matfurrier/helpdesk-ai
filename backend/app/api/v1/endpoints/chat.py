"""Chat/triage endpoints — Sprint 1.

POST /chat/csrf-token             → issue CSRF cookie + body token
POST /chat/conversations          → create conversation, return ConversationOut
POST /chat/conversations/{id}/messages → send message, receive SSE stream
GET  /chat/conversations/{id}/messages → history

Rate limit: 30 req/min/user (Redis sliding window — atomic Lua).
CSRF:       X-CSRF-Token header required on all POSTs (Double Submit Cookie).
Auth:       cookie JWT via get_current_user dependency.

Security notes (audit 2026-06-09):
- User message content stored REDACTED (tokens) — never PII in plaintext.
- Rate limit uses Lua to avoid ZADD/ZCARD race condition.
- CSRF cookie secure flag follows settings.is_dev.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError, RateLimitError
from app.db.session import get_db
from app.schemas.auth import UserOut
from app.schemas.chat import ConversationOut, MessageCreate, MessageOut, TriageOutput
from app.services.ai import redactor as _redactor
from app.services.ai.orchestrator import LLMOrchestrator, get_orchestrator

router = APIRouter(prefix="/chat", tags=["chat"])
log = structlog.get_logger()

_RATE_LIMIT = 30
_RATE_WINDOW = 60  # seconds

# Atomic sliding-window rate limit via Lua — avoids ZADD/ZCARD race condition.
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]


async def _check_csrf(request: Request) -> None:
    """Verify Double Submit Cookie. Raises ForbiddenError on mismatch."""
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise ForbiddenError("CSRF token inválido ou ausente")


async def _check_rate_limit(user_id: str, redis: Redis) -> None:
    key = f"rl:chat:{user_id}"
    now = time.time()
    count = await redis.eval(
        _RATE_LIMIT_LUA,
        1,
        key,
        str(now),
        str(_RATE_WINDOW),
        str(_RATE_LIMIT),
    )
    if int(count) > _RATE_LIMIT:
        raise RateLimitError(f"Limite de {_RATE_LIMIT} requisições/min atingido")


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
# CSRF token endpoint
# ---------------------------------------------------------------------------


@router.get("/csrf-token")
async def get_csrf_token(response: Response) -> dict[str, str]:
    """Issue a CSRF token as a non-httponly cookie and return it in the body.

    Frontend must call this once per session, then send X-CSRF-Token header.
    """
    token = secrets.token_hex(32)
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,  # JavaScript must read this cookie
        samesite="lax",
        secure=not settings.is_dev,
        path="/",
    )
    return {"csrf_token": token}


# ---------------------------------------------------------------------------
# Conversation endpoints
# ---------------------------------------------------------------------------


@router.post("/conversations", status_code=201)
async def create_conversation(
    request: Request,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    await _check_csrf(request)
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
        id=str(row.id),
        status=str(row.status),
        started_at=row.started_at,
        message_count=0,
    )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    orch: LLMOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    await _check_csrf(request)
    redis = await _get_redis(request)
    await _check_rate_limit(current_user.user_id, redis)

    # Verify conversation exists and belongs to this user
    conv = await db.execute(
        text(
            "SELECT id, status FROM helpdesk.ai_conversations "  # noqa: S608
            "WHERE id = :cid AND user_id = :uid"
        ),
        {"cid": conversation_id, "uid": current_user.user_id},
    )
    if conv.fetchone() is None:
        raise NotFoundError("Conversa não encontrada")

    # Redact PII BEFORE persisting — never store plaintext PII (LGPD/C1).
    redacted_content, pii_map = _redactor.redact(body.content)

    await db.execute(
        text(
            # content stores the redacted version; content_redacted mirrors it
            # for schema compatibility. The original is never written to DB.
            "INSERT INTO helpdesk.ai_conversation_messages "  # noqa: S608
            "(conversation_id, role, content, content_redacted) "
            "VALUES (:cid, 'user', :content, :redacted)"
        ),
        {
            "cid": conversation_id,
            "content": redacted_content,
            "redacted": redacted_content,
        },
    )
    await db.commit()

    # Call LLM orchestrator with original text (redactor runs again internally,
    # but token_map.store is the authoritative PII vault for restoration).
    result: TriageOutput = await orch.complete(
        prompt_key="TRIAGE_SYSTEM",
        user_input=body.content,
        user_id=current_user.user_id,
        conversation_id=conversation_id,
        db=db,
    )

    # Persist assistant message
    asst_ins = await db.execute(
        text(
            "INSERT INTO helpdesk.ai_conversation_messages "  # noqa: S608
            "(conversation_id, role, content) "
            "VALUES (:cid, 'assistant', :content) "
            "RETURNING id"
        ),
        {"cid": conversation_id, "content": result.assistant_text},
    )
    await db.commit()
    asst_row = asst_ins.fetchone()

    # Persist ai_suggestions
    if asst_row is not None:
        await db.execute(
            text(
                "INSERT INTO helpdesk.ai_suggestions "  # noqa: S608
                "(message_id, next_action, suggestions, ticket_draft, citations) "
                "VALUES (:mid, :action, :suggestions::jsonb, :ticket::jsonb, :citations)"
            ),
            {
                "mid": str(asst_row.id),
                "action": result.next_action,
                "suggestions": json.dumps([s.model_dump() for s in result.suggestions]),
                "ticket": json.dumps(result.ticket_draft.model_dump())
                if result.ticket_draft
                else None,
                "citations": [c for s in result.suggestions for c in s.citations],
            },
        )
        await db.commit()

    log.info(
        "chat.message_sent",
        conversation_id=conversation_id,
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
    conversation_id: str,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    conv = await db.execute(
        text(
            "SELECT id FROM helpdesk.ai_conversations "  # noqa: S608
            "WHERE id = :cid AND user_id = :uid"
        ),
        {"cid": conversation_id, "uid": current_user.user_id},
    )
    if conv.fetchone() is None:
        raise NotFoundError("Conversa não encontrada")

    msgs = await db.execute(
        text(
            # Return content_redacted for user messages (tokens), content for assistant
            "SELECT id, role, "  # noqa: S608
            "COALESCE(content_redacted, content) AS content, created_at "
            "FROM helpdesk.ai_conversation_messages "
            "WHERE conversation_id = :cid "
            "ORDER BY created_at ASC"
        ),
        {"cid": conversation_id},
    )
    return [
        MessageOut(
            id=str(row.id),
            role=str(row.role),
            content=str(row.content),
            created_at=row.created_at,
        )
        for row in msgs.fetchall()
    ]
