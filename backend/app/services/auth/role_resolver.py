"""Resolve the helpdesk role for a user UUID.

Priority chain (Sprint 2):
  1. BOOTSTRAP_ADMIN_UUIDS (env var) — provisional bootstrap escape hatch.
     See ADR-0003. Kept for emergency access even after role_overrides lands.
  2. helpdesk.role_overrides — explicit it_admin / it_lead grants.
  3. departmentid == IT_DEPARTMENT_ID (public.users) → it_agent.
  4. Default: employee.
"""

from __future__ import annotations

from enum import StrEnum

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

log = structlog.get_logger()


class Role(StrEnum):
    EMPLOYEE = "employee"
    IT_AGENT = "it_agent"
    IT_LEAD = "it_lead"
    IT_ADMIN = "it_admin"


async def resolve_role(user_uuid: str, sec_db: AsyncSession) -> Role:
    """Return the highest helpdesk role for *user_uuid*.

    Checks role_overrides in the helpdesk DB before falling back to the
    departmentid-based heuristic in the shared user directory.
    sec_db is accepted for the departmentid lookup; the helpdesk lookup
    uses a separate session derived from sec_db's engine to reach the
    helpdesk schema.  In practice both share the same DB in dev, so we
    reuse sec_db.
    """
    # Step 1 — bootstrap override (emergency access, always wins)
    if user_uuid.lower() in settings.bootstrap_admin_uuid_set:
        return Role.IT_ADMIN

    # Step 2 — explicit grant in helpdesk.role_overrides
    try:
        override_result = await sec_db.execute(
            text(
                "SELECT role FROM helpdesk.role_overrides "  # noqa: S608
                "WHERE user_uuid = :uuid LIMIT 1"
            ),
            {"uuid": user_uuid},
        )
        override_row = override_result.fetchone()
        if override_row is not None:
            role_str = str(override_row.role)
            if role_str == Role.IT_ADMIN:
                return Role.IT_ADMIN
            if role_str == Role.IT_LEAD:
                return Role.IT_LEAD
    except Exception as exc:
        log.debug("role_resolver.overrides_unavailable", error=str(exc))

    # Step 3 — departmentid lookup in the shared user directory
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
