from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.version)


@router.get("/health/ready", response_model=HealthResponse, tags=["infra"])
async def ready() -> HealthResponse:
    """Readiness probe — extend with real DB ping in Sprint 1."""
    return HealthResponse(status="ok", version=settings.version)
