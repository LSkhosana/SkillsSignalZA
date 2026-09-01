"""Use-case service for synchronous assessment scoring.

This service forwards a validated HTTP envelope to the production
scoring entry point. It contains no scoring, cap, band, selection,
catalogue, or evidence-inference logic and performs no I/O.
"""

from __future__ import annotations

from typing import Any

from app.engine.scoring import score_assessment
from app.schemas.scoring import ScoreAssessmentRequest


def score_frozen_assessment(request: ScoreAssessmentRequest) -> dict[str, Any]:
    """Delegate one frozen assessment run to `score_assessment`."""
    return score_assessment(
        request.assessment_input,
        request.evidence_facts,
        request.scoring_context,
        request.source_records,
        assessment_id=request.assessment_id,
        run_id=request.run_id,
        assessed_at=request.assessed_at,
    )
