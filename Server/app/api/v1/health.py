"""Liveness endpoint for the SkillSignalZA API.

This route must remain free of Supabase calls, secret values and
dependency checks so Expo and Render can probe it safely.
"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
