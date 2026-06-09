"""Integration tests for the login flow.

Requires a running postgres on 5436 with the security stub tables.
Mark with @pytest.mark.integration and run via: pytest -m integration
"""

from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_PH = PasswordHasher()


def _build_test_db_url() -> str:
    import os

    user = os.environ.get("POSTGRES_USER", "helpdesk")
    pw = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "helpdesk")
    return f"postgresql+asyncpg://{user}:{pw}@db:5432/{db}"


@pytest.fixture
async def sec_db() -> AsyncSession:
    engine = create_async_engine(_build_test_db_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def test_user(sec_db: AsyncSession) -> dict[str, str]:
    """Insert a stub user and return credentials; clean up after test."""
    hashed = _PH.hash("testpassword123")
    await sec_db.execute(
        text("""
            INSERT INTO public.users (uuid, login, name, email, password, active)
            VALUES (:uuid, :login, :name, :email, :password, 1)
            ON CONFLICT DO NOTHING
        """),
        {
            "uuid": "00000000-0000-0000-0000-000000000001",
            "login": "test.user",
            "name": "Test User",
            "email": "test.user@example.com",
            "password": hashed,
        },
    )
    await sec_db.commit()
    yield {"credential": "test.user@example.com", "password": "testpassword123"}
    await sec_db.execute(
        text("DELETE FROM public.users WHERE uuid = '00000000-0000-0000-0000-000000000001'")
    )
    await sec_db.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: dict[str, str]) -> None:
    response = await client.post("/api/v1/auth/login", json=test_user)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "employee"
    # Cookie should be set
    assert "sds_session" in response.headers.get("set-cookie", "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_bad_password(client: AsyncClient, test_user: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"credential": test_user["credential"], "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_with_cookie(client: AsyncClient, test_user: dict[str, str]) -> None:
    login_resp = await client.post("/api/v1/auth/login", json=test_user)
    assert login_resp.status_code == 200
    # Cookie is set automatically by httpx via set-cookie header
    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == test_user["credential"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bootstrap_admin_promotes_user(
    client: AsyncClient, test_user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config as cfg

    monkeypatch.setattr(
        cfg.settings,
        "bootstrap_admin_uuid_set",
        frozenset(["00000000-0000-0000-0000-000000000001"]),
    )
    response = await client.post("/api/v1/auth/login", json=test_user)
    assert response.status_code == 200
    assert response.json()["role"] == "it_admin"
