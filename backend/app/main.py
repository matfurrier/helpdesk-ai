from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.api.v1.router import router
from app.core.config import settings
from app.core.errors import HelpdeskError
from app.services.ai.orchestrator import init_orchestrator

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        __import__("logging").getLevelName(settings.log_level)
    ),
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.is_dev else structlog.processors.JSONRenderer(),
    ],
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    redis = Redis.from_url(settings.redis_url, decode_responses=False, protocol=2)
    application.state.redis = redis
    await init_orchestrator(redis)
    yield
    await redis.aclose()


app = FastAPI(
    title="helpdesk-ai",
    version=settings.version,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3004"] if settings.is_dev else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HelpdeskError)
async def domain_error_handler(request: Request, exc: HelpdeskError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": exc.code, "detail": exc.message},
    )


app.include_router(router)
