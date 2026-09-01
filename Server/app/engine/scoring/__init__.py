"""Deterministic scoring engine.

Scoring rules live here and are driven by validated domain configuration.
No scoring logic may be implemented in `app.api` routes.
"""

from app.engine.qa import band_for
from app.engine.scoring.engine import canonical_result, score_assessment

__all__ = ["band_for", "canonical_result", "score_assessment"]
