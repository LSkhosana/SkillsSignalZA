"""SkillSignalZA FastAPI application factory."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.schemas.health import RootResponse

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create the FastAPI application without opening network connections."""
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )
    application.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    @application.get("/", response_model=RootResponse)
    def get_root() -> RootResponse:
        return RootResponse(
            service=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
            health=f"{settings.api_v1_prefix}/health",
            docs="/docs",
        )

    logger.info(
        "Application created name=%s version=%s environment=%s",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )
    return application


app = create_app()
