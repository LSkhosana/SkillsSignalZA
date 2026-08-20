"""Health and root service metadata schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Public liveness payload compatible with the Expo client."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: str
    version: str
    environment: str


class RootResponse(BaseModel):
    """Service discovery metadata for developers."""

    model_config = ConfigDict(extra="forbid")

    service: str
    version: str
    environment: str
    health: str = Field(description="Path to the liveness endpoint.")
    docs: str = Field(description="Path to the OpenAPI docs.")
