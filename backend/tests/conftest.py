"""Global pytest fixtures for helpdesk-ai backend."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Force test env BEFORE app import so pydantic-settings picks up overrides.
# Security DB is redirected to the local stub (public.users in the helpdesk DB).
_pg_user = os.environ.get("POSTGRES_USER", "helpdesk")
_pg_pw = os.environ.get("POSTGRES_PASSWORD", "")
_pg_db = os.environ.get("POSTGRES_DB", "helpdesk")

os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{_pg_user}:{_pg_pw}@db:5432/{_pg_db}"
os.environ["SECURITY_DB_HOST"] = "db"
os.environ["SECURITY_DB_PORT"] = "5432"
os.environ["SECURITY_DB_USER"] = _pg_user
os.environ["SECURITY_DB_PASSWORD"] = _pg_pw
os.environ["SECURITY_DB_NAME"] = _pg_db
os.environ["SECURITY_SCHEMA"] = "public"
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production-32chars!!")
os.environ.setdefault("ENV", "development")

import app.db.session as _db_session  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402

# Cookie name: __Host- prefix is stripped in dev (secure=False in auth module)
_SESSION_COOKIE = "sds_session"

_TEST_JWT_PAYLOAD: dict[str, object] = {
    "sub": "00000000-0000-0000-0000-000000000001",
    "login": "testuser",
    "name": "Test User",
    "email": "test@internal.example",
    "role": "employee",
}

# Replace singleton engines with NullPool variants.
# NullPool creates a fresh connection per operation, so no futures leak
# between test function-scoped event loops.
_db_session._engine = create_async_engine(settings.database_url, poolclass=NullPool, echo=False)
_db_session._Session = async_sessionmaker(_db_session._engine, expire_on_commit=False)

_db_session._security_engine = create_async_engine(
    settings.security_db_url, poolclass=NullPool, echo=False
)
_db_session._SecuritySession = async_sessionmaker(
    _db_session._security_engine, expire_on_commit=False
)


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authed_client() -> AsyncClient:
    """AsyncClient with a pre-signed JWT cookie — skips login for integration tests."""
    token = create_access_token(_TEST_JWT_PAYLOAD)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={_SESSION_COOKIE: token},
    ) as ac:
        yield ac
