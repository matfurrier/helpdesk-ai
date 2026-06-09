"""Authenticate a user against the shared user directory.

Queries public.users in the security database (the shared user directory
used by all internal apps). Uses argon2id verification.

Authentication is by email only. The login column exists in public.users
but a query on infra_postgres (2026-06-09) confirmed 0 users have a login
value that differs from their email prefix — AD username login is Wontfix.
See Issue #1 (closed) and SPEC.md §Authentication.
"""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_password
from app.services.auth.role_resolver import Role, resolve_role

log = structlog.get_logger()


class AuthenticatedUser:
    __slots__ = ("uuid", "login", "name", "email", "role")

    def __init__(
        self,
        uuid: str,
        login: str,
        name: str,
        email: str,
        role: Role,
    ) -> None:
        self.uuid = uuid
        self.login = login
        self.name = name
        self.email = email
        self.role = role


async def authenticate(
    credential: str,
    password: str,
    sec_db: AsyncSession,
) -> AuthenticatedUser | None:
    """Return an AuthenticatedUser or None on failure.

    *credential* is matched against ``email`` only (case-insensitive).
    """
    result = await sec_db.execute(
        text(
            "SELECT id, uuid, login, name, email, password, active"  # noqa: S608
            f" FROM {settings.security_schema}.users"
            " WHERE lower(email) = lower(:credential)"
        ),
        {"credential": credential},
    )
    row = result.fetchone()

    if row is None:
        log.info("login.not_found", credential=credential)
        return None

    if not row.active:
        log.info("login.inactive", credential=credential)
        return None

    if not verify_password(password, row.password):
        log.info("login.bad_password", credential=credential)
        return None

    # Cast to str: uuid column is native uuid type in the real DB (asyncpg returns
    # asyncpg.pgproto.UUID, not str), which lacks .lower() and breaks role_resolver.
    user_uuid: str = str(row.uuid) if row.uuid is not None else str(row.id)
    role = await resolve_role(user_uuid, sec_db)

    log.info("login.success", uuid=user_uuid, role=role)
    return AuthenticatedUser(
        uuid=user_uuid,
        login=str(row.login) if row.login else "",
        name=str(row.name) if row.name else "",
        email=str(row.email) if row.email else "",
        role=role,
    )
