"""Shared fixtures for integration tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

import app.db.session as _db_session
from app.core.security import create_access_token
from app.main import app

_SESSION_COOKIE = "sds_session"
_ADMIN_UUID = "00000000-0000-0000-0000-000000000099"
_IT_LEAD_UUID = "00000000-0000-0000-0000-000000000098"


async def _grant_override(user_uuid: str, role: str) -> None:
    """Seed helpdesk.role_overrides so resolve_role (called fresh per request
    by get_current_user) actually grants *role* to *user_uuid* — the JWT's
    own role claim is no longer trusted, see auth.py."""
    async with _db_session._SecuritySession() as session:
        await session.execute(
            text(
                "INSERT INTO helpdesk.role_overrides (user_uuid, role, granted_by) "
                "VALUES (:uuid, :role, :uuid) "
                "ON CONFLICT (user_uuid) DO UPDATE SET role = EXCLUDED.role"
            ),
            {"uuid": user_uuid, "role": role},
        )
        await session.commit()


async def _revoke_override(user_uuid: str) -> None:
    async with _db_session._SecuritySession() as session:
        await session.execute(
            text("DELETE FROM helpdesk.role_overrides WHERE user_uuid = :uuid"),
            {"uuid": user_uuid},
        )
        await session.commit()


@pytest.fixture
async def admin_client() -> AsyncClient:
    await _grant_override(_ADMIN_UUID, "it_admin")
    token = create_access_token(
        {
            "sub": _ADMIN_UUID,
            "login": "admin",
            "name": "Admin User",
            "email": "admin@internal.example",
            "role": "it_admin",
        }
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={_SESSION_COOKIE: token},
    ) as ac:
        yield ac
    await _revoke_override(_ADMIN_UUID)


@pytest.fixture
async def it_lead_client() -> AsyncClient:
    await _grant_override(_IT_LEAD_UUID, "it_lead")
    token = create_access_token(
        {
            "sub": _IT_LEAD_UUID,
            "login": "itlead",
            "name": "IT Lead",
            "email": "itlead@internal.example",
            "role": "it_lead",
        }
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={_SESSION_COOKIE: token},
    ) as ac:
        yield ac
    await _revoke_override(_IT_LEAD_UUID)
