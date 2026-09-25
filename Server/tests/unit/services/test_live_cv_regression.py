"""Regression for the realistic DOCX shape that failed live acceptance for Issue #38."""

from __future__ import annotations

import hashlib
from typing import Any

from app.engine.extraction.links.outcomes import (
    completed_link_outcome,
    link_metadata,
    link_source_record,
)
from app.engine.schema_registry import draft_validator
from app.services.assessment_pipeline import run_assessment_pipeline
from tests.fixtures.cv_extraction.documents import build_text_docx

ASSESSED_AT = "2026-09-14T10:30:00Z"
SUBMITTED_AT = "2026-09-14T10:29:00Z"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _accessible_repo(submitted_url: str, **payload: Any) -> dict[str, Any]:
    body = b"Built a Flask API in Python with PostgreSQL and tests"
    digest = hashlib.sha256(body).hexdigest()
    link = link_metadata(
        link_id=payload["link_id"],
        submitted_url=submitted_url,
        declared_type=payload["declared_type"],
        normalized_url=submitted_url,
        final_url=submitted_url,
        verified_content_type="text/html",
        http_status=200,
        byte_size=len(body),
        sha256=digest,
    )
    record = link_source_record(
        link_id=payload["link_id"],
        declared_type=payload["declared_type"],
        submitted_url=submitted_url,
        retrieved_at=payload["retrieved_at"],
        access_status="accessible",
        content_hash=digest,
    )
    return completed_link_outcome(
        link=link,
        source_record=record,
        content_blocks=[
            {
                "block_id": "lnk-1",
                "locator": "document order 1",
                "text": body.decode("utf-8"),
            }
        ],
    )


def test_realistic_docx_with_separate_education_dates_and_repo_completes() -> None:
    file_bytes = build_text_docx(
        paragraphs=[
            "Candidate Name",
            "Junior Software Developer",
            "Summary",
            (
                "Software developer with 3 years of React experience. Built REST APIs with "
                "Python and Flask, tested applications, and used Git and GitHub."
            ),
            "Experience",
            "Software Support Technician | 2025 - Present",
            (
                "Developed and maintained web application features, debugged production issues, "
                "built API integrations, and worked with PostgreSQL."
            ),
            "Projects",
            (
                "Built a Flask REST API with PostgreSQL. Added unit tests and deployment "
                "documentation."
            ),
            "Education",
            "BSc Computer Science",
            "2023 - Present",
        ]
    )
    assessment_input = {
        "contract_version": "1.2.0",
        "rubric_version": "V2",
        "track": "software_engineering",
        "candidate_ref": "live-regression-candidate",
        "cv": {
            "document_id": "src-cv",
            "media_type": DOCX_MEDIA_TYPE,
            "sha256": hashlib.sha256(file_bytes).hexdigest(),
            "original_filename": "realistic-cv.docx",
        },
        "links": [
            {
                "link_id": "link-1",
                "submitted_url": "https://example.com/candidate-repository",
                "declared_type": "repository",
            }
        ],
        "submitted_at": SUBMITTED_AT,
    }

    outcome = run_assessment_pipeline(
        assessment_input=assessment_input,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-live-regression",
        run_id="run-live-regression",
        assessed_at=ASSESSED_AT,
        retrieve_link=_accessible_repo,
    )
    draft_validator("assessment_pipeline.schema.json").validate(outcome)

    assert outcome["state"] == "COMPLETED"
    assert outcome["assessment_result"] is not None
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" not in outcome["review_flags"]
    assert "OWNERSHIP_UNCLEAR" not in outcome["review_flags"]
    assert "MATERIAL_SOURCE_CONTRADICTION" not in outcome["review_flags"]

    qualification = next(
        item
        for item in outcome["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "se.alignment.qualification"
    )
    # Status lives in a separate paragraph, so the conservative launch behavior is zero credit,
    # not a global review block or an invented in-progress qualification.
    assert qualification["anchor"] == "se.qual.none"
    assert qualification["awarded_points"] == 0

    repositories = [
        record for record in outcome["source_records"] if record["source_type"] == "repository"
    ]
    assert len(repositories) == 1
    assert repositories[0]["ownership_status"] == "unclear"
