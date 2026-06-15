"""Integration tests for the asset management endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app

pytestmark = pytest.mark.integration

_CSRF = "test-assets-csrf"


def _ch() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF}


def _cc() -> dict[str, str]:
    return {"csrf_token": _CSRF}


# ===========================================================================
# CREATE
# ===========================================================================


async def test_create_asset_notebook(admin_client: AsyncClient) -> None:
    res = await admin_client.post(
        "/api/v1/admin/assets",
        json={
            "asset_type": "notebook",
            "brand": "Dell",
            "model": "Inspiron 15 3511",
            "asset_tag": "TEST.001",
            "status": "active",
            "specs": {"computer_name": "DSMAN014", "os_version": "Windows 11 PRO", "ram": "8GB"},
            "compliance": {"antivirus": True, "fusion_inventory": True, "responsibility_term": True},
        },
        cookies=_cc(),
        headers=_ch(),
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["model"] == "Inspiron 15 3511"
    assert data["asset_tag"] == "TEST.001"
    assert data["specs"]["computer_name"] == "DSMAN014"
    assert data["compliance"]["antivirus"] is True
    assert len(data["history"]) == 1
    assert data["history"][0]["action"] == "created"


async def test_create_asset_smartphone(admin_client: AsyncClient) -> None:
    res = await admin_client.post(
        "/api/v1/admin/assets",
        json={
            "asset_type": "smartphone",
            "brand": "Samsung",
            "model": "Galaxy S24 FE",
            "asset_tag": "TEST.002",
            "status": "active",
            "specs": {"phone_number": "(43) 99153-4579"},
        },
        cookies=_cc(),
        headers=_ch(),
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["asset_type"] == "smartphone"
    assert data["specs"]["phone_number"] == "(43) 99153-4579"


async def test_create_asset_forbidden_for_employee() -> None:
    token = create_access_token(
        {"sub": "emp-001", "login": "emp", "name": "Emp", "email": "e@e.com", "role": "employee"}
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"sds_session": token},
    ) as c:
        res = await c.post(
            "/api/v1/admin/assets",
            json={"asset_type": "notebook", "model": "Test"},
            cookies=_cc(),
            headers=_ch(),
        )
    assert res.status_code == 403


# ===========================================================================
# LIST
# ===========================================================================


async def test_list_assets(admin_client: AsyncClient) -> None:
    await admin_client.post(
        "/api/v1/admin/assets",
        json={"asset_type": "tablet", "brand": "Apple", "model": "iPad Pro", "status": "active"},
        cookies=_cc(),
        headers=_ch(),
    )
    res = await admin_client.get("/api/v1/admin/assets")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


async def test_list_assets_filter_type(admin_client: AsyncClient) -> None:
    await admin_client.post(
        "/api/v1/admin/assets",
        json={"asset_type": "other", "model": "Projetor Epson"},
        cookies=_cc(),
        headers=_ch(),
    )
    res = await admin_client.get("/api/v1/admin/assets?asset_type=other")
    assert res.status_code == 200
    data = res.json()
    assert all(i["asset_type"] == "other" for i in data["items"])


# ===========================================================================
# GET SINGLE
# ===========================================================================


async def _create_nb(client: AsyncClient, tag: str = "TEST.003") -> str:
    res = await client.post(
        "/api/v1/admin/assets",
        json={"asset_type": "notebook", "brand": "Dell", "model": "G15 5530", "asset_tag": tag},
        cookies=_cc(),
        headers=_ch(),
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


async def test_get_asset(admin_client: AsyncClient) -> None:
    aid = await _create_nb(admin_client, "TEST.004")
    res = await admin_client.get(f"/api/v1/admin/assets/{aid}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == aid
    assert data["model"] == "G15 5530"


async def test_get_asset_not_found(admin_client: AsyncClient) -> None:
    res = await admin_client.get("/api/v1/admin/assets/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


# ===========================================================================
# UPDATE
# ===========================================================================


async def test_update_asset(admin_client: AsyncClient) -> None:
    aid = await _create_nb(admin_client, "TEST.005")
    res = await admin_client.patch(
        f"/api/v1/admin/assets/{aid}",
        json={"status": "maintenance", "notes": "Teclado defeituoso"},
        cookies=_cc(),
        headers=_ch(),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "maintenance"
    assert data["notes"] == "Teclado defeituoso"
    actions = [h["action"] for h in data["history"]]
    assert "status_changed" in actions


# ===========================================================================
# RETIRE (DELETE)
# ===========================================================================


async def test_retire_asset(admin_client: AsyncClient) -> None:
    aid = await _create_nb(admin_client, "TEST.006")
    res = await admin_client.delete(
        f"/api/v1/admin/assets/{aid}",
        cookies=_cc(),
        headers=_ch(),
    )
    assert res.status_code == 204

    detail = await admin_client.get(f"/api/v1/admin/assets/{aid}")
    assert detail.json()["status"] == "retired"


# ===========================================================================
# EXPORT
# ===========================================================================


async def test_export_csv(admin_client: AsyncClient) -> None:
    res = await admin_client.get("/api/v1/admin/assets/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert "patrimonio-ti.csv" in res.headers.get("content-disposition", "")
