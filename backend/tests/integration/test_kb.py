"""Integration tests for admin KB article endpoint — Sprint 2.

Requires: running Postgres with migration applied (mark: integration).
OpenAI embeddings are mocked via respx.
admin_client fixture is provided by tests/integration/conftest.py.
"""

from __future__ import annotations

import uuid

import pytest
import respx
from httpx import AsyncClient, Response

pytestmark = pytest.mark.integration

_CSRF = "test-kb-admin-csrf"
# Unique per test-run to avoid duplicate-slug conflicts in a persistent DB
_SLUG = f"ci-vpn-{uuid.uuid4().hex[:8]}"

_EMBED_RESP = {
    "object": "list",
    "data": [{"object": "embedding", "index": 0, "embedding": [0.1] * 1536}],
    "model": "text-embedding-3-small",
    "usage": {"prompt_tokens": 5, "total_tokens": 5},
}


def _csrf_h() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF}


def _csrf_c() -> dict[str, str]:
    return {"csrf_token": _CSRF}


async def test_create_kb_article_success(
    respx_mock: respx.MockRouter, admin_client: AsyncClient
) -> None:
    """POST /admin/kb/articles returns 201 with article_id and chunks_created >= 1."""
    respx_mock.post("https://api.openai.com/v1/embeddings").mock(
        return_value=Response(200, json=_EMBED_RESP)
    )

    resp = await admin_client.post(
        "/api/v1/admin/kb/articles",
        json={
            "slug": _SLUG,
            "title": "Como configurar a VPN",
            "body_markdown": "# VPN\n\nInstale o cliente e configure o servidor.",
            "tags": ["vpn", "rede"],
            "trust_level": "internal_published",
        },
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["slug"] == _SLUG
    assert len(data["article_id"]) == 36  # UUID format
    assert data["chunks_created"] >= 1


async def test_create_kb_article_forbidden_employee(authed_client: AsyncClient) -> None:
    """Employee role (not admin) receives 403."""
    resp = await authed_client.post(
        "/api/v1/admin/kb/articles",
        json={
            "slug": "should-be-blocked",
            "title": "Blocked",
            "body_markdown": "noop",
            "trust_level": "internal_draft",
        },
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 403


async def test_create_kb_article_no_csrf(admin_client: AsyncClient) -> None:
    """POST without CSRF header/cookie returns 403."""
    resp = await admin_client.post(
        "/api/v1/admin/kb/articles",
        json={
            "slug": "no-csrf-slug",
            "title": "No CSRF",
            "body_markdown": "noop",
            "trust_level": "internal_draft",
        },
    )
    assert resp.status_code == 403


async def test_create_kb_article_invalid_trust_level(admin_client: AsyncClient) -> None:
    """Invalid trust_level returns 422 before hitting the DB."""
    resp = await admin_client.post(
        "/api/v1/admin/kb/articles",
        json={
            "slug": "bad-trust",
            "title": "Bad Trust",
            "body_markdown": "noop",
            "trust_level": "totally_wrong",
        },
        headers=_csrf_h(),
        cookies=_csrf_c(),
    )
    assert resp.status_code == 422
