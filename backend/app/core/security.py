"""Password verification and JWT helpers.

All JWT operations must go through this module — never import jose directly
outside of here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings
from app.core.errors import AuthError

_ph = PasswordHasher()


def verify_password(plain: str, hashed: str) -> bool:
    """Verifies argon2id hash. Returns False on any mismatch or format error."""
    try:
        _ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(data: dict[str, object]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, object]:
    """Raises AuthError if the token is invalid or expired."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise AuthError("Token inválido ou expirado") from exc
