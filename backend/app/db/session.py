from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# --- Helpdesk database ---
_engine = create_async_engine(
    settings.database_url,
    echo=settings.is_dev,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

_Session = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _Session() as session:
        yield session


# --- Security database — shared user directory (public.users, department, applications) ---
_security_engine = create_async_engine(
    settings.security_db_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

_SecuritySession = async_sessionmaker(_security_engine, expire_on_commit=False)


async def get_security_db() -> AsyncGenerator[AsyncSession, None]:
    async with _SecuritySession() as session:
        yield session
