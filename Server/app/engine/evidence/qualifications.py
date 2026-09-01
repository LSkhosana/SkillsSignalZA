"""Qualification-only explicit evidence helpers for Package H."""

from __future__ import annotations

from app.engine.evidence.matching import KIND_QUALIFICATION, AliasMatch
from app.engine.evidence.outcomes import SOURCE_TYPE_CV

QUALIFICATION_FACT_TYPE = "qualification"
QUALIFICATION_EVIDENCE_LEVEL = "documented"


def qualification_hits(matches: list[AliasMatch]) -> list[AliasMatch]:
    """Return qualification alias hits from a sentence match list."""
    return [match for match in matches if match.kind == KIND_QUALIFICATION]


def sentence_has_qualification(matches: list[AliasMatch]) -> bool:
    """Return True when a sentence contains explicit credential wording."""
    return bool(qualification_hits(matches))


def emit_qualification_from_source(source_type: str) -> bool:
    """V1 emits qualification facts only from CV/credential context."""
    return source_type == SOURCE_TYPE_CV
