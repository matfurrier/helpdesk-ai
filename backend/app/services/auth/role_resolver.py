"""Resolve the helpdesk role for a user UUID.

Priority chain (Sprint 0):
  1. BOOTSTRAP_ADMIN_UUIDS (env var) — provisional until role_overrides lands.
     See ADR-0003. Planned removal: Sprint 2, when helpdesk.role_overrides is
     implemented.
  2. departmentid == IT_DEPARTMENT_ID (public.users) → it_agent.
  3. Default: employee.

Role distinction between it_lead / it_admin is handled only via
BOOTSTRAP_ADMIN_UUIDS until the helpdesk.role_overrides table arrives.
"""
from __future__ import annotations

from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class Role(StrEnum):
    EMPLOYEE = "employee"
    IT_AGENT = "it_agent"
    IT_LEAD = "it_lead"
    IT_ADMIN = "it_admin"


async def resolve_role(user_uuid: str, sec_db: AsyncSession) -> Role:
    """Return the highest helpdesk role for *user_uuid*.

    Why: ADR-0003 — we derive role from departmentid because the shared
    user directory (public.users in the security database) does not have
    helpdesk-specific group tables. BOOTSTRAP_ADMIN_UUIDS is a provisional
    escape hatch for it_admin until helpdesk.role_overrides is built.
    """
    # Step 1 — bootstrap override (provisional, Sprint 0 only)
    if user_uuid.lower() in settings.bootstrap_admin_uuid_set:
        return Role.IT_ADMIN

    # Step 2 — departmentid lookup in the shared user directory
    try:
        result = await sec_db.execute(
            text(
                f"SELECT departmentid FROM {settings.security_schema}.users WHERE uuid = :uuid"  # noqa: S608
            ),
            {"uuid": user_uuid},
        )
        row = result.fetchone()
    except Exception:
        return Role.EMPLOYEE

    if row is not None and row.departmentid is not None:
        if str(row.departmentid) == str(settings.it_department_id):
            return Role.IT_AGENT

    return Role.EMPLOYEE
