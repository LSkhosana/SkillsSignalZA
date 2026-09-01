"""HTTP transport envelope for synchronous assessment scoring."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScoreAssessmentRequest(BaseModel):
    """Caller-supplied scoring envelope. Nested scoring rules stay in the engine."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    assessed_at: str = Field(
        min_length=1,
        description="RFC 3339 date-time supplied by the caller for reproducibility.",
        examples=["2026-08-31T10:00:00Z"],
    )
    assessment_input: dict
    evidence_facts: list[dict]
    scoring_context: dict
    source_records: list[dict]

    @field_validator("assessed_at")
    @classmethod
    def assessed_at_must_be_rfc3339(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("assessed_at must be an RFC 3339 date-time") from exc
        return value
