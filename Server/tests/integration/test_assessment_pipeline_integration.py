"""End-to-end Package K integration tests with mocked link retrieval."""

from __future__ import annotations

import hashlib
from typing import Any

from app.engine.extraction.links.outcomes import (
    failed_link_outcome,
    link_metadata,
    link_source_record,
)
from app.services.assessment_pipeline import run_assessment_pipeline
from tests.fixtures.cv_extraction.documents import build_text_pdf

ASSESSED_AT = "2026-09-02T08:00:00Z"
SUBMITTED_AT = "2026-09-02T07:00:00Z"
SECRET = "C:\\secret\\path traceback must not leak"


def _input(
    track: str, file_bytes: bytes, links: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "contract_version": "1.2.0",
        "rubric_version": "V2",
        "track": track,
        "candidate_ref": "opaque-candidate",
        "cv": {
            "document_id": "src-cv",
            "media_type": "application/pdf",
            "sha256": hashlib.sha256(file_bytes).hexdigest(),
            "original_filename": "cv.pdf",
        },
        "links": links or [],
        "submitted_at": SUBMITTED_AT,
    }


def _blocked_retrieve(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise AssertionError("real link retrieval is not allowed")


def _failed_retrieve(submitted_url: str, **payload: Any) -> dict[str, Any]:
    link = link_metadata(
        link_id=payload["link_id"],
        submitted_url=submitted_url,
        declared_type=payload["declared_type"],
    )
    record = link_source_record(
        link_id=payload["link_id"],
        declared_type=payload["declared_type"],
        submitted_url=submitted_url,
        retrieved_at=payload["retrieved_at"],
        access_status="unsafe",
        content_hash=None,
    )
    return failed_link_outcome("UNSAFE_HOST", link=link, source_record=record)


def test_integration_se_pipeline_completed_without_network() -> None:
    file_bytes = build_text_pdf(
        [
            [
                "Summary",
                "Skills",
                "Projects",
                "Built a Flask API in Python to solve a workflow problem",
            ]
        ]
    )
    outcome = run_assessment_pipeline(
        assessment_input=_input("software_engineering", file_bytes),
        cv_file_bytes=file_bytes,
        assessment_id="assessment-int-1",
        run_id="run-int-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert outcome["state"] == "COMPLETED"
    assert outcome["assessment_result"]["qa"]["status"] == "PASS"
    assert SECRET not in str(outcome)


def test_integration_inaccessible_link_does_not_fail_assessment() -> None:
    file_bytes = build_text_pdf([["Junior Software Engineer"]])
    outcome = run_assessment_pipeline(
        assessment_input=_input(
            "software_engineering",
            file_bytes,
            [
                {
                    "link_id": "link-1",
                    "submitted_url": "https://example.com/x",
                    "declared_type": "project",
                }
            ],
        ),
        cv_file_bytes=file_bytes,
        assessment_id="assessment-int-2",
        run_id="run-int-2",
        assessed_at=ASSESSED_AT,
        retrieve_link=_failed_retrieve,
    )
    assert outcome["state"] == "COMPLETED"
    assert hashlib.sha256(file_bytes).hexdigest() == outcome["source_records"][0]["content_hash"]
