"""Integration tests for role override endpoint and role_resolver — Sprint 2.

Requires: running Postgres with migration applied (mark: integration).
admin_client / it_lead_client fixtures from tests/integration/conftest.py.
"""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.auth.role_resolver import Role, resolve_role

pytestmark = pytest.mark.integration

_CSRF = "test-roles-csrf"
_TARGET_UUID = "00000000-0000-0000-0000-000000000077"


def _db_url() -> str:
    user = os.environ.get("POSTGRES_USER", "helpdesk")
    pw = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "helpdesk")
    return f"postgresql+asyncpg://{user}:{pw}@db:5432/{db}"


def _csrf_h() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF}


def _csrf_c() -> dict[str, str]:
    return {"csrf_token": _CSRF}


@pytest.fixture
async def db_session():
    engine = create_async_engine(_db_url())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup_override(db_session) -> None:
    """Remove test override row before and after each test."""
    await db_session.execute(
        text("DELETE FROM helpdesk.role_overrides WHERE user_uuid = :uuid"),
        {"uuid": _TARGET_UUID},
    )
    await db_session.commit()
    yield
    await db_session.execute(
        text("DELETE FROM helpdesk.role_overrides WHERE user_uuid = :uuid"),
        {"uuid": _TARGET_UUID},
    )
    await db_session.commit()


async def test_upsert_role_override_it_lead(admin_client: AsyncClient) -> None:
    """it_admin can grant it_lead via POST /admin/roles/{uuid}."""
    resp = await admin_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_lead"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user_uuid"] == _TARGET_UUID
    assert data["role"] == "it_lead"


async def test_upsert_role_override_it_admin(admin_client: AsyncClient) -> None:
    """it_admin can grant it_admin via POST /admin/roles/{uuid}."""
    resp = await admin_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_admin"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "it_admin"


async def test_upsert_idempotent(admin_client: AsyncClient) -> None:
    """Second call updates the role (upsert semantics)."""
    await admin_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_lead"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    resp = await admin_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_admin"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "it_admin"


async def test_it_lead_cannot_grant_it_admin(it_lead_client: AsyncClient) -> None:
    """it_lead gets 403 when trying to grant it_admin."""
    resp = await it_lead_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_admin"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 403


async def test_it_lead_can_grant_it_lead(it_lead_client: AsyncClient) -> None:
    """it_lead can grant it_lead to another user."""
    resp = await it_lead_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_lead"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 200


async def test_employee_forbidden(authed_client: AsyncClient) -> None:
    """Employee gets 403 from the admin guard."""
    resp = await authed_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_lead"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 403


async def test_invalid_role_returns_422(admin_client: AsyncClient) -> None:
    """Unknown role value returns 422 from Pydantic validation."""
    resp = await admin_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "superuser"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 422


async def test_resolve_role_uses_override(admin_client: AsyncClient) -> None:
    """role_resolver returns override role after a grant is committed via endpoint.

    Uses a fresh engine so there is no stale connection or cached transaction
    state from the cleanup_override fixture.
    """
    resp = await admin_client.post(
        f"/api/v1/admin/roles/{_TARGET_UUID}",
        json={"role": "it_lead"},
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 200

    fresh_engine = create_async_engine(_db_url())
    try:
        factory = async_sessionmaker(fresh_engine, expire_on_commit=False)
        async with factory() as session:
            role = await resolve_role(_TARGET_UUID, session)
        assert role == Role.IT_LEAD
    finally:
        await fresh_engine.dispose()
