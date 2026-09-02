"""Explicit evidence normalization.

Deterministic Package H conversion of Package F/G text blocks into Contract 1.2
evidence facts. Classification lives here, not in extraction, scoring, or routes.
"""

from app.engine.evidence.normalizer import normalize_evidence
from app.engine.evidence.outcomes import (
    MAX_EVIDENCE_FACTS,
    NORMALIZER_VERSION,
)

__all__ = ["MAX_EVIDENCE_FACTS", "NORMALIZER_VERSION", "normalize_evidence"]
