"""Shared fixtures for integration tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app

_SESSION_COOKIE = "sds_session"
_ADMIN_UUID = "00000000-0000-0000-0000-000000000099"
_IT_LEAD_UUID = "00000000-0000-0000-0000-000000000098"


@pytest.fixture
async def admin_client() -> AsyncClient:
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


@pytest.fixture
async def it_lead_client() -> AsyncClient:
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
