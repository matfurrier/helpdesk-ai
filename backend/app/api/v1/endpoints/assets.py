"""Asset management endpoints — IT-only CRUD with assignment history."""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.errors import ForbiddenError, NotFoundError
from app.db.session import get_db, get_security_db
from app.schemas.assets import (
    AssetAssignIn,
    AssetCreate,
    AssetListOut,
    AssetOut,
    AssetReturnIn,
    AssetUpdate,
)
from app.schemas.auth import UserOut

router = APIRouter(prefix="/admin/assets", tags=["assets"])
log = structlog.get_logger()

_IT_ROLES = frozenset({"it_agent", "it_lead", "it_admin"})


async def _it_user(user: UserOut = Depends(get_current_user)) -> UserOut:
    if user.role not in _IT_ROLES:
        raise ForbiddenError("Acesso restrito à equipe de TI")
    return user


async def _get_asset_row(asset_id: str, db: AsyncSession) -> object:
    res = await db.execute(
        text("SELECT * FROM helpdesk.assets WHERE id = CAST(:id AS uuid)"),
        {"id": asset_id},
    )
    row = res.fetchone()
    if row is None:
        raise NotFoundError("Patrimônio não encontrado")
    return row


def _row_to_list_item(r: object) -> dict[str, object]:
    return {
        "id": str(r.id),
        "asset_tag": r.asset_tag,
        "asset_type": r.asset_type,
        "brand": r.brand,
        "model": r.model,
        "status": r.status,
        "holder_id": r.holder_id,
        "holder_name": r.holder_name,
        "holder_dept": r.holder_dept,
        "acquired_at": r.acquired_at,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _row_to_full(r: object, history: list[dict[str, object]]) -> dict[str, object]:
    return {
        **_row_to_list_item(r),
        "serial_number": r.serial_number,
        "warranty_until": r.warranty_until,
        "specs": r.specs if isinstance(r.specs, dict) else json.loads(r.specs or "{}"),
        "compliance": (
            r.compliance if isinstance(r.compliance, dict) else json.loads(r.compliance or "{}")
        ),
        "notes": r.notes,
        "created_by": r.created_by,
        "history": history,
    }


async def _load_history(asset_id: str, db: AsyncSession) -> list[dict[str, object]]:
    res = await db.execute(
        text(
            "SELECT id, action, holder_name, holder_dept, changed_by, changed_at, "
            "       before_data, after_data, notes "
            "FROM helpdesk.asset_history "
            "WHERE asset_id = CAST(:id AS uuid) "
            "ORDER BY changed_at DESC"
        ),
        {"id": asset_id},
    )
    rows = res.fetchall()
    return [
        {
            "id": str(h.id),
            "action": h.action,
            "holder_name": h.holder_name,
            "holder_dept": h.holder_dept,
            "changed_by": h.changed_by,
            "changed_at": h.changed_at,
            "before_data": h.before_data if isinstance(h.before_data, dict) else None,
            "after_data": h.after_data if isinstance(h.after_data, dict) else None,
            "notes": h.notes,
        }
        for h in rows
    ]


async def _lookup_user(holder_id: str, sec_db: AsyncSession) -> tuple[str, str | None]:
    """Returns (holder_name, holder_dept) from security DB. Falls back to holder_id on error."""
    try:
        res = await sec_db.execute(
            text(
                "SELECT u.name, d.name AS dept_name "
                "FROM public.users u "
                "LEFT JOIN public.department d ON d.id = u.departmentid "
                "WHERE u.uuid::text = :uid"
            ),
            {"uid": holder_id},
        )
        row = res.fetchone()
        if row:
            return str(row.name or holder_id), row.dept_name
    except Exception as exc:
        log.warning("assets.lookup_user_error", holder_id=holder_id, error=str(exc))
    return holder_id, None


# ===========================================================================
# LIST
# ===========================================================================


@router.get("", response_model=AssetListOut)
async def list_assets(
    asset_type: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> AssetListOut:
    where = ["1=1"]
    params: dict[str, object] = {}

    if asset_type:
        where.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    if status:
        where.append("status = :status")
        params["status"] = status
    if search:
        where.append(
            "(model ILIKE :search OR asset_tag ILIKE :search "
            "OR holder_name ILIKE :search OR holder_dept ILIKE :search "
            "OR brand ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    clause = " AND ".join(where)
    res = await db.execute(
        text(
            f"SELECT id, asset_tag, asset_type, brand, model, status, "  # noqa: S608
            f"       holder_id, holder_name, holder_dept, acquired_at, "
            f"       created_at, updated_at "
            f"FROM helpdesk.assets WHERE {clause} "
            f"ORDER BY updated_at DESC"
        ),
        params,
    )
    rows = res.fetchall()
    count_res = await db.execute(
        text(f"SELECT COUNT(*) FROM helpdesk.assets WHERE {clause}"),  # noqa: S608
        params,
    )
    total = int(count_res.scalar() or 0)
    return AssetListOut(items=[_row_to_list_item(r) for r in rows], total=total)


# ===========================================================================
# EXPORT CSV
# ===========================================================================


@router.get("/export")
async def export_assets(
    asset_type: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    where = ["1=1"]
    params: dict[str, object] = {}
    if asset_type:
        where.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    if status:
        where.append("status = :status")
        params["status"] = status

    clause = " AND ".join(where)
    res = await db.execute(
        text(
            f"SELECT asset_tag, asset_type, brand, model, serial_number, status, "  # noqa: S608
            f"       holder_name, holder_dept, acquired_at, warranty_until, "
            f"       specs, compliance, notes, created_at "
            f"FROM helpdesk.assets WHERE {clause} ORDER BY asset_type, brand, model"
        ),
        params,
    )
    rows = res.fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Patrimônio",
            "Tipo",
            "Marca",
            "Modelo",
            "Serial",
            "Status",
            "Titular",
            "Setor",
            "Aquisição",
            "Garantia até",
            "Specs",
            "Compliance",
            "Observações",
            "Cadastrado em",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.asset_tag or "",
                r.asset_type,
                r.brand or "",
                r.model,
                r.serial_number or "",
                r.status,
                r.holder_name or "",
                r.holder_dept or "",
                r.acquired_at.isoformat() if r.acquired_at else "",
                r.warranty_until.isoformat() if r.warranty_until else "",
                json.dumps(r.specs, ensure_ascii=False) if r.specs else "",
                json.dumps(r.compliance, ensure_ascii=False) if r.compliance else "",
                r.notes or "",
                r.created_at.isoformat(),
            ]
        )

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=patrimonio-ti.csv"},
    )


# ===========================================================================
# GET SINGLE
# ===========================================================================


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: str,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> AssetOut:
    row = await _get_asset_row(asset_id, db)
    history = await _load_history(asset_id, db)
    return AssetOut(**_row_to_full(row, history))


# ===========================================================================
# CREATE
# ===========================================================================


@router.post("", response_model=AssetOut, status_code=201)
async def create_asset(
    payload: AssetCreate,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> AssetOut:

    res = await db.execute(
        text(
            "INSERT INTO helpdesk.assets "
            "(asset_tag, asset_type, brand, model, serial_number, status, "
            " acquired_at, warranty_until, specs, compliance, notes, created_by) "
            "VALUES (:tag, :atype, :brand, :model, :serial, :status, "
            "        :acquired, :warranty, CAST(:specs AS jsonb), CAST(:compliance AS jsonb), "
            "        :notes, :created_by) "
            "RETURNING id"
        ),
        {
            "tag": payload.asset_tag,
            "atype": payload.asset_type,
            "brand": payload.brand,
            "model": payload.model,
            "serial": payload.serial_number,
            "status": payload.status,
            "acquired": payload.acquired_at,
            "warranty": payload.warranty_until,
            "specs": json.dumps(payload.specs),
            "compliance": json.dumps(payload.compliance),
            "notes": payload.notes,
            "created_by": current_user.user_id,
        },
    )
    new_id = str(res.scalar_one())

    await db.execute(
        text(
            "INSERT INTO helpdesk.asset_history "
            "(asset_id, action, changed_by, after_data) "
            "VALUES (CAST(:aid AS uuid), 'created', :by, CAST(:data AS jsonb))"
        ),
        {
            "aid": new_id,
            "by": current_user.user_id,
            "data": json.dumps({"model": payload.model, "asset_type": payload.asset_type}),
        },
    )
    await db.commit()

    log.info("assets.created", asset_id=new_id, by=current_user.user_id)
    row = await _get_asset_row(new_id, db)
    return AssetOut(**_row_to_full(row, []))


# ===========================================================================
# UPDATE
# ===========================================================================


@router.patch("/{asset_id}", response_model=AssetOut)
async def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> AssetOut:
    row = await _get_asset_row(asset_id, db)

    before: dict[str, object] = {}
    after: dict[str, object] = {}
    sets: list[str] = []
    params: dict[str, object] = {"id": asset_id}

    def _maybe(field: str, col: str, val: object) -> None:
        if val is not None:
            before[field] = getattr(row, col, None)
            after[field] = val
            sets.append(f"{col} = :{field}")
            params[field] = val

    _maybe("asset_tag", "asset_tag", payload.asset_tag)
    _maybe("brand", "brand", payload.brand)
    _maybe("model", "model", payload.model)
    _maybe("serial_number", "serial_number", payload.serial_number)
    _maybe("status", "status", payload.status)
    _maybe("acquired_at", "acquired_at", payload.acquired_at)
    _maybe("warranty_until", "warranty_until", payload.warranty_until)
    _maybe("notes", "notes", payload.notes)

    if payload.specs is not None:
        before["specs"] = row.specs
        after["specs"] = payload.specs
        sets.append("specs = CAST(:specs AS jsonb)")
        params["specs"] = json.dumps(payload.specs)

    if payload.compliance is not None:
        before["compliance"] = row.compliance
        after["compliance"] = payload.compliance
        sets.append("compliance = CAST(:compliance AS jsonb)")
        params["compliance"] = json.dumps(payload.compliance)

    if sets:
        await db.execute(
            text(
                f"UPDATE helpdesk.assets SET {', '.join(sets)} "  # noqa: S608
                "WHERE id = CAST(:id AS uuid)"
            ),
            params,
        )
        action = "status_changed" if "status" in after else "updated"
        await db.execute(
            text(
                "INSERT INTO helpdesk.asset_history "
                "(asset_id, action, holder_name, holder_dept, changed_by, before_data, after_data) "
                "VALUES (CAST(:aid AS uuid), :action, :hname, :hdept, :by, "
                "        CAST(:before AS jsonb), CAST(:after AS jsonb))"
            ),
            {
                "aid": asset_id,
                "action": action,
                "hname": row.holder_name,
                "hdept": row.holder_dept,
                "by": current_user.user_id,
                "before": json.dumps(before, default=str),
                "after": json.dumps(after, default=str),
            },
        )
        await db.commit()

    row = await _get_asset_row(asset_id, db)
    history = await _load_history(asset_id, db)
    return AssetOut(**_row_to_full(row, history))


# ===========================================================================
# ASSIGN
# ===========================================================================


@router.post("/{asset_id}/assign", response_model=AssetOut)
async def assign_asset(
    asset_id: str,
    payload: AssetAssignIn,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
    sec_db: AsyncSession = Depends(get_security_db),
) -> AssetOut:
    row = await _get_asset_row(asset_id, db)

    holder_name, holder_dept = await _lookup_user(payload.holder_id, sec_db)

    await db.execute(
        text(
            "UPDATE helpdesk.assets "
            "SET holder_id = :hid, holder_name = :hname, holder_dept = :hdept "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "hid": payload.holder_id,
            "hname": holder_name,
            "hdept": holder_dept,
            "id": asset_id,
        },
    )
    await db.execute(
        text(
            "INSERT INTO helpdesk.asset_history "
            "(asset_id, action, holder_name, holder_dept, changed_by, "
            " before_data, after_data, notes) "
            "VALUES (CAST(:aid AS uuid), 'assigned', :hname, :hdept, :by, "
            "        CAST(:before AS jsonb), CAST(:after AS jsonb), :notes)"
        ),
        {
            "aid": asset_id,
            "hname": holder_name,
            "hdept": holder_dept,
            "by": current_user.user_id,
            "before": json.dumps({"holder_name": row.holder_name, "holder_dept": row.holder_dept}),
            "after": json.dumps(
                {
                    "holder_name": holder_name,
                    "holder_dept": holder_dept,
                    "holder_id": payload.holder_id,
                }
            ),
            "notes": payload.notes,
        },
    )
    await db.commit()

    log.info(
        "assets.assigned", asset_id=asset_id, holder_id=payload.holder_id, by=current_user.user_id
    )  # noqa: E501
    row = await _get_asset_row(asset_id, db)
    history = await _load_history(asset_id, db)
    return AssetOut(**_row_to_full(row, history))


# ===========================================================================
# RETURN
# ===========================================================================


@router.post("/{asset_id}/return", response_model=AssetOut)
async def return_asset(
    asset_id: str,
    payload: AssetReturnIn,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> AssetOut:
    row = await _get_asset_row(asset_id, db)

    await db.execute(
        text(
            "UPDATE helpdesk.assets "
            "SET holder_id = NULL, holder_name = NULL, holder_dept = NULL "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {"id": asset_id},
    )
    await db.execute(
        text(
            "INSERT INTO helpdesk.asset_history "
            "(asset_id, action, holder_name, holder_dept, changed_by, before_data, notes) "
            "VALUES (CAST(:aid AS uuid), 'returned', :hname, :hdept, :by, "
            "        CAST(:before AS jsonb), :notes)"
        ),
        {
            "aid": asset_id,
            "hname": row.holder_name,
            "hdept": row.holder_dept,
            "by": current_user.user_id,
            "before": json.dumps({"holder_name": row.holder_name, "holder_id": row.holder_id}),
            "notes": payload.notes,
        },
    )
    await db.commit()

    log.info(
        "assets.returned", asset_id=asset_id, prev_holder=row.holder_id, by=current_user.user_id
    )  # noqa: E501
    row = await _get_asset_row(asset_id, db)
    history = await _load_history(asset_id, db)
    return AssetOut(**_row_to_full(row, history))


# ===========================================================================
# DELETE (retire)
# ===========================================================================


@router.delete("/{asset_id}", status_code=204)
async def retire_asset(
    asset_id: str,
    request: Request,
    response: Response,
    current_user: UserOut = Depends(_it_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await _get_asset_row(asset_id, db)

    await db.execute(
        text(
            "UPDATE helpdesk.assets SET status = 'retired', "
            "holder_id = NULL, holder_name = NULL, holder_dept = NULL "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {"id": asset_id},
    )
    await db.execute(
        text(
            "INSERT INTO helpdesk.asset_history "
            "(asset_id, action, holder_name, holder_dept, changed_by, before_data, after_data) "
            "VALUES (CAST(:aid AS uuid), 'status_changed', :hname, :hdept, :by, "
            "        CAST(:before AS jsonb), CAST(:after AS jsonb))"
        ),
        {
            "aid": asset_id,
            "hname": row.holder_name,
            "hdept": row.holder_dept,
            "by": current_user.user_id,
            "before": json.dumps({"status": row.status}),
            "after": json.dumps({"status": "retired"}),
        },
    )
    await db.commit()
    log.info("assets.retired", asset_id=asset_id, by=current_user.user_id)
