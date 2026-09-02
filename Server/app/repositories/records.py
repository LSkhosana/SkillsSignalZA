"""Vendor-neutral persistence records for Package L."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

PersistWriteStatus = Literal["inserted", "noop", "conflict"]
AccessState = Literal["PREVIEW", "UNLOCKED"]


@dataclass(frozen=True)
class DocumentMetadata:
    """CV metadata stored in PostgreSQL. Bytes never enter the database."""

    document_id: str
    storage_path: str
    original_filename: str
    media_type: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class PersistenceBundle:
    """One complete relational write for an anonymous assessment run."""

    assessment_id: str
    run_id: str
    candidate_ref: str
    track: str
    assessed_at: datetime
    claim_token_hash: str | None
    expires_at: datetime | None
    document: DocumentMetadata
    pipeline_outcome: dict[str, Any]
    assessment_input: dict[str, Any]


@dataclass(frozen=True)
class PersistWriteResult:
    """Relational write outcome without vendor types."""

    status: PersistWriteStatus
    assessment_id: str
    run_id: str
    latest_run_id: str | None = None


@dataclass(frozen=True)
class AssessmentRecord:
    """Mutable assessment lifecycle row."""

    assessment_id: str
    candidate_ref: str
    track: str
    access_state: AccessState
    claim_token_hash: str | None
    claimed_at: datetime | None
    latest_run_id: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AssessmentRunRecord:
    """Immutable Package K run snapshot plus child provenance."""

    run_id: str
    assessment_id: str
    state: str
    error_code: str | None
    pipeline_version: str
    contract_version: str
    rubric_version: str
    track: str
    assessment_input: dict[str, Any]
    scoring_context: dict[str, Any] | None
    assessment_result: dict[str, Any] | None
    review_flags: list[str]
    stages: list[str]
    assessed_at: datetime
    created_at: datetime
    source_records: list[dict[str, Any]]
    evidence_facts: list[dict[str, Any]]
    document: DocumentMetadata | None
