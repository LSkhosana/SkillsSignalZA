"""Typed environment configuration for the SkillSignalZA API.

Settings are cached for process lifetime. The application must start
when Supabase variables are absent. Secret values must never be logged
or returned by endpoints.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def parse_cors_origins(value: object) -> list[str]:
    """Parse a comma-separated CORS origin string into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    raise TypeError("CORS_ORIGINS must be a comma-separated string or a list of origins.")


class Settings(BaseSettings):
    """Process configuration loaded from environment variables and optional `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="SkillSignalZA API", validation_alias="APP_NAME")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_publishable_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_PUBLISHABLE_KEY",
    )
    supabase_secret_key: SecretStr | None = Field(
        default=None,
        validation_alias="SUPABASE_SECRET_KEY",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        return parse_cors_origins(value)

    @field_validator(
        "supabase_url",
        "supabase_publishable_key",
        "supabase_secret_key",
        mode="before",
    )
    @classmethod
    def _empty_optional(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def allow_credentials(self) -> bool:
        """Credentials are allowed only when origins are explicit, never with `*`."""
        return bool(self.cors_origins) and "*" not in self.cors_origins

    @property
    def cors_allow_origins(self) -> list[str]:
        if "*" in self.cors_origins:
            return ["*"]
        return self.cors_origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings object."""
    return Settings()
