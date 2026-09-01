"""HTTP schemas for the SkillSignalZA API."""

from app.schemas.health import HealthResponse
from app.schemas.scoring import ScoreAssessmentRequest

__all__ = ["HealthResponse", "ScoreAssessmentRequest"]
