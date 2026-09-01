"""Unit tests for the Package E assessment scoring service."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.engine.outcomes import engine_outcome
from app.schemas.scoring import ScoreAssessmentRequest
from app.services.assessment_scoring import score_frozen_assessment


def _request() -> ScoreAssessmentRequest:
    return ScoreAssessmentRequest(
        assessment_id="assessment-id",
        run_id="run-id",
        assessed_at="2026-08-31T10:00:00Z",
        assessment_input={"track": "software_engineering"},
        evidence_facts=[{"evidence_id": "ev-001"}],
        scoring_context={"track": "software_engineering"},
        source_records=[{"source_id": "src-cv"}],
    )


def test_service_delegates_once_and_returns_engine_outcome_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = engine_outcome("COMPLETED", assessment_result={"final_score": 59})
    scoring = Mock(return_value=expected)
    monkeypatch.setattr("app.services.assessment_scoring.score_assessment", scoring)
    payload = _request()
    outcome = score_frozen_assessment(payload)
    scoring.assert_called_once_with(
        payload.assessment_input,
        payload.evidence_facts,
        payload.scoring_context,
        payload.source_records,
        assessment_id="assessment-id",
        run_id="run-id",
        assessed_at="2026-08-31T10:00:00Z",
    )
    assert outcome is expected
    assert outcome == expected
