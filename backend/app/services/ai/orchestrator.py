"""LLM Orchestrator — Sprint 2.

All LLM calls must go through LLMOrchestrator.complete(). Never call
OpenAI/Anthropic SDKs outside this module.

Pipeline per call:
  guardrails → redactor → token_map.store → fetch prompt → LLM
  → validate schema → token_map.restore → ai_call_log INSERT
"""

from __future__ import annotations

import time
from typing import TypeVar

import structlog
from openai import APIStatusError, AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import LLMError
from app.schemas.chat import TriageOutput
from app.services.ai import guardrails, redactor
from app.services.ai.token_map import TokenMap

log = structlog.get_logger()

_T = TypeVar("_T", bound=BaseModel)

_prompt_cache: dict[str, tuple[int, str, str, float]] = {}
_PROMPT_CACHE_TTL = 60.0


async def _fetch_prompt(prompt_key: str, db: AsyncSession) -> tuple[int, str, str]:
    """Return (version, sha256, body) for the published prompt. Cached 60 s."""
    now = time.monotonic()
    cached = _prompt_cache.get(prompt_key)
    if cached and (now - cached[3]) < _PROMPT_CACHE_TTL:
        return cached[0], cached[1], cached[2]

    result = await db.execute(
        text(
            "SELECT version, sha256, body FROM helpdesk.prompts "  # noqa: S608
            "WHERE prompt_key = :key AND published = true LIMIT 1"
        ),
        {"key": prompt_key},
    )
    row = result.fetchone()
    if row is None:
        raise LLMError(f"Prompt '{prompt_key}' not found or not published")

    _prompt_cache[prompt_key] = (int(row.version), str(row.sha256), str(row.body), now)
    return int(row.version), str(row.sha256), str(row.body)


async def _call_openai[T: BaseModel](
    messages: list[dict[str, str]],
    schema_type: type[T],
) -> tuple[T, int | None, int | None]:
    client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=settings.openai_max_retries)
    response = await client.beta.chat.completions.parse(
        model=settings.openai_model,
        messages=messages,  # type: ignore[arg-type]
        response_format=schema_type,
        max_tokens=512,
    )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise LLMError("OpenAI returned null structured output")
    usage = response.usage
    return (
        parsed,
        (usage.prompt_tokens if usage else None),
        (usage.completion_tokens if usage else None),
    )


async def _call_anthropic[T: BaseModel](
    messages: list[dict[str, str]],
    schema_type: type[T],
) -> tuple[T, int | None, int | None]:
    import json as _json

    import anthropic
    from anthropic.types import MessageParam, ToolParam
    from anthropic.types.tool_choice_tool_param import ToolChoiceToolParam

    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs: list[MessageParam] = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in messages
        if m["role"] != "system"
    ]
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    tool: ToolParam = {
        "name": "structured_output",
        "description": "Structured response",
        "input_schema": schema_type.model_json_schema(),
    }
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=system_msg,
        messages=user_msgs,
        tools=[tool],
        tool_choice=ToolChoiceToolParam(type="tool", name="structured_output"),
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    raw = tool_use.input if isinstance(tool_use.input, dict) else _json.loads(tool_use.input)
    result = schema_type.model_validate(raw)
    usage = response.usage
    return result, (usage.input_tokens if usage else None), (usage.output_tokens if usage else None)


async def _log_call(
    *,
    db: AsyncSession,
    conversation_id: str | None,
    user_id: str | None,
    prompt_key: str,
    prompt_version: int,
    prompt_sha256: str,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    latency_ms: int,
    http_status: int,
    guardrail_flags: list[str],
    was_fallback: bool,
    validation_status: str,
) -> None:
    total = (input_tokens or 0) + (output_tokens or 0) or None
    try:
        await db.execute(
            text(
                "INSERT INTO helpdesk.ai_call_log "  # noqa: S608
                "(conversation_id, user_id, prompt_key, prompt_version, prompt_sha256, "
                "provider, model, input_tokens, output_tokens, total_tokens, latency_ms, "
                "http_status, guardrail_flags, was_fallback, validation_status) "
                "VALUES (:conv_id, :user_id, :pkey, :pver, :psha, "
                ":provider, :model, :in_tok, :out_tok, :tot_tok, :latency, "
                ":http_status, :flags, :fallback, :vstatus)"
            ),
            {
                "conv_id": conversation_id,
                "user_id": user_id,
                "pkey": prompt_key,
                "pver": prompt_version,
                "psha": prompt_sha256,
                "provider": provider,
                "model": model,
                "in_tok": input_tokens,
                "out_tok": output_tokens,
                "tot_tok": total,
                "latency": latency_ms,
                "http_status": http_status,
                "flags": guardrail_flags,
                "fallback": was_fallback,
                "vstatus": validation_status,
            },
        )
        await db.commit()
    except Exception as exc:
        log.warning("orchestrator.log_failed", error=str(exc))


def _build_messages(
    prompt_body: str,
    clean_input: str,
    context_blocks: list[dict[str, object]] | None,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = [{"role": "system", "content": prompt_body}]
    if context_blocks:
        ctx_text = "\n".join(
            f"<source id='{b.get('id', '')}'>{b.get('content', '')}</source>"
            for b in context_blocks
        )
        msgs.append({"role": "system", "content": ctx_text})
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": clean_input})
    return msgs


class LLMOrchestrator:
    """Central LLM call gateway with guardrails, redaction, and audit logging."""

    def __init__(self, redis: object | None = None) -> None:
        self._token_map: TokenMap | None = None
        if redis is not None:
            self._token_map = TokenMap(redis)  # type: ignore[arg-type]

    async def complete(
        self,
        *,
        prompt_key: str,
        user_input: str,
        history: list[dict[str, str]] | None = None,
        context_blocks: list[dict[str, object]] | None = None,
        schema: type[_T] = TriageOutput,  # type: ignore[assignment]
        user_id: str | None = None,
        conversation_id: str | None = None,
        db: AsyncSession,
    ) -> _T:
        """Run the full pipeline and return a validated structured output."""
        start = time.monotonic()
        flags = guardrails.check(user_input)
        clean_input, pii_map = redactor.redact(user_input)

        if self._token_map is not None and conversation_id and pii_map:
            await self._token_map.store(conversation_id, pii_map)

        prompt_version, prompt_sha256, prompt_body = await _fetch_prompt(prompt_key, db)
        messages = _build_messages(prompt_body, clean_input, context_blocks, history)

        provider = "openai"
        model = settings.openai_model
        was_fallback = False
        http_status = 200
        validation_status = "ok"
        result: _T | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            result, input_tokens, output_tokens = await _call_openai(messages, schema)
            if hasattr(result, "guardrails_triggered"):
                result = result.model_copy(
                    update={"guardrails_triggered": flags or result.guardrails_triggered}
                )
        except APIStatusError as exc:
            http_status = exc.status_code
            if not settings.ai_fallback_enabled or exc.status_code < 500:  # noqa: PLR2004
                validation_status = "failed"
                await _log_call(
                    db=db,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    prompt_key=prompt_key,
                    prompt_version=prompt_version,
                    prompt_sha256=prompt_sha256,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    http_status=http_status,
                    guardrail_flags=flags,
                    was_fallback=False,
                    validation_status=validation_status,
                )
                raise LLMError(f"OpenAI error {exc.status_code}: {exc.message}") from exc

            log.warning("orchestrator.openai_5xx_fallback", status=exc.status_code)
            provider = "anthropic"
            model = settings.anthropic_model
            was_fallback = True
            http_status = 200
            try:
                result, input_tokens, output_tokens = await _call_anthropic(messages, schema)
                if hasattr(result, "guardrails_triggered"):
                    result = result.model_copy(
                        update={"guardrails_triggered": flags or result.guardrails_triggered}
                    )
            except Exception as anth_exc:
                validation_status = "failed"
                await _log_call(
                    db=db,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    prompt_key=prompt_key,
                    prompt_version=prompt_version,
                    prompt_sha256=prompt_sha256,
                    provider=provider,
                    model=model,
                    input_tokens=None,
                    output_tokens=None,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    http_status=502,
                    guardrail_flags=flags,
                    was_fallback=True,
                    validation_status=validation_status,
                )
                raise LLMError("Both OpenAI and Anthropic failed") from anth_exc

        if (
            self._token_map is not None
            and conversation_id
            and pii_map
            and result is not None
            and isinstance(result, TriageOutput)
        ):
            result = result.model_copy(
                update={
                    "assistant_text": await self._token_map.restore(
                        conversation_id, result.assistant_text
                    )
                }
            )

        assert result is not None  # noqa: S101
        latency_ms = int((time.monotonic() - start) * 1000)
        await _log_call(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            prompt_sha256=prompt_sha256,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            http_status=http_status,
            guardrail_flags=getattr(result, "guardrails_triggered", flags),
            was_fallback=was_fallback,
            validation_status=validation_status,
        )
        log.info(
            "orchestrator.complete",
            prompt_key=prompt_key,
            next_action=getattr(result, "next_action", None),
            latency_ms=latency_ms,
            provider=provider,
        )
        return result

    async def purge_pii_map(self, conversation_id: str) -> None:
        """Delete the PII token map after ticket conversion (LGPD data minimization)."""
        if self._token_map is not None:
            await self._token_map.purge(conversation_id)


orchestrator = LLMOrchestrator()


async def get_orchestrator() -> LLMOrchestrator:
    return orchestrator


async def init_orchestrator(redis: object) -> None:
    global orchestrator  # noqa: PLW0603
    orchestrator = LLMOrchestrator(redis=redis)
