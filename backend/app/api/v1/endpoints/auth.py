from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AuthError
from app.core.security import create_access_token, decode_token
from app.db.session import get_security_db
from app.schemas.auth import LoginRequest, UserOut
from app.services.auth.auth_service import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_OPTS: dict[str, object] = {
    "httponly": True,
    "samesite": "lax",
    # secure=True in production; __Host- prefix requires Secure
    # In dev we allow http so the prefix is stripped to the plain name
    "secure": False,
    "path": "/",
}


def _cookie_name() -> str:
    # __Host- prefix requires Secure=True; strip for local http dev
    name = settings.session_cookie_name
    if not _COOKIE_OPTS.get("secure") and name.startswith("__Host-"):
        return name[len("__Host-"):]
    return name


async def get_current_user(
    request: Request,
    response: Response,
) -> UserOut:
    """FastAPI dependency: extract and validate the session cookie."""
    cookie_name = _cookie_name()
    token = request.cookies.get(cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    try:
        payload = decode_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return UserOut(
        user_id=str(payload["sub"]),
        login=str(payload.get("login", "")),
        name=str(payload.get("name", "")),
        email=str(payload.get("email", "")),
        role=str(payload.get("role", "employee")),
    )


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest,
    response: Response,
    sec_db: AsyncSession = Depends(get_security_db),
) -> UserOut:
    user = await authenticate(body.credential, body.password, sec_db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial ou senha incorretos",
        )

    token = create_access_token({
        "sub": user.uuid,
        "login": user.login,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
    })

    response.set_cookie(
        key=_cookie_name(),
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        **_COOKIE_OPTS,  # type: ignore[arg-type]
    )

    return UserOut(
        user_id=user.uuid,
        login=user.login,
        name=user.name,
        email=user.email,
        role=user.role.value,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(key=_cookie_name(), path="/")


@router.get("/me", response_model=UserOut)
async def me(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    return current_user
