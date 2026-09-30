"""Live-pipeline ceiling: attributed repository evidence can reach the top band."""

from __future__ import annotations

import hashlib
from typing import Any

from app.engine.extraction.links.outcomes import (
    completed_link_outcome,
    link_metadata,
    link_source_record,
)
from app.services.assessment_pipeline import run_assessment_pipeline
from tests.fixtures.cv_extraction.documents import build_text_docx

ASSESSED_AT = "2026-09-14T10:30:00Z"
SUBMITTED_AT = "2026-09-14T10:29:00Z"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
REPO_URL = "https://github.com/ada/workflow"

CV_PARAGRAPHS = [
    "Ada Candidate",
    "Summary",
    "Seeking a junior software developer role.",
    "Skills",
    "Built Python services with Flask and PostgreSQL for a user workflow.",
    "Experience",
    "Used Git and wrote unit tests for an API service that solved an operations problem.",
    "Projects",
    "Documented the setup and the working result of a deployed service.",
    "Education",
    "Completed a Bachelor degree in Computer Science.",
]

REPO_PARAGRAPHS = [
    (
        "Built a Python service using object oriented programming, "
        "data structures, algorithms, and control flow."
    ),
    "Built a REST API over HTTP and used Flask.",
    (
        "Used SQL with a relational database, a database schema, "
        "database normalization, and database joins in PostgreSQL."
    ),
    (
        "Debugged defects and used pytest for unit testing, "
        "integration testing, and automated testing."
    ),
    "Used Git and GitHub.",
    "Deployed the API with Docker.",
    "Used the command line to run the tests.",
    "The user problem is an operations workflow to track requests.",
    "Built a Flask API with PostgreSQL. The architecture uses an API and a database.",
    "Documented the setup, installation, and README instructions.",
    "The working result is a deployed service.",
    "Explained the design to a stakeholder and wrote documentation.",
    "Worked with a reviewer on a code review.",
    "Responsible for a client internship and collaborated on the delivery.",
    "Independently built the personal project.",
    "Debugged the defect and resolved it before the deadline.",
]


def _repo(ownership: str) -> dict[str, Any]:
    body = "\n\n".join(REPO_PARAGRAPHS).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    link = link_metadata(
        link_id="link-1",
        submitted_url=REPO_URL,
        declared_type="repository",
        normalized_url=REPO_URL,
        final_url=REPO_URL,
        verified_content_type="text/markdown",
        http_status=200,
        byte_size=len(body),
        sha256=digest,
    )
    record = link_source_record(
        link_id="link-1",
        declared_type="repository",
        submitted_url=REPO_URL,
        retrieved_at=ASSESSED_AT,
        access_status="accessible",
        content_hash=digest,
        ownership_status=ownership,
    )
    blocks = [
        {"block_id": f"blk-{index}", "locator": f"text:p:{index}", "text": text}
        for index, text in enumerate(REPO_PARAGRAPHS, start=1)
    ]
    return completed_link_outcome(link=link, source_record=record, content_blocks=blocks)


def _run(ownership: str) -> dict[str, Any]:
    file_bytes = build_text_docx(paragraphs=CV_PARAGRAPHS)
    assessment_input = {
        "contract_version": "1.2.0",
        "rubric_version": "V2",
        "track": "software_engineering",
        "candidate_ref": "ceiling-candidate",
        "cv": {
            "document_id": "src-cv",
            "media_type": DOCX_MEDIA_TYPE,
            "sha256": hashlib.sha256(file_bytes).hexdigest(),
            "original_filename": "ceiling-cv.docx",
        },
        "links": [
            {
                "link_id": "link-1",
                "submitted_url": REPO_URL,
                "declared_type": "repository",
                "profile_handle": "ada",
            }
        ],
        "submitted_at": SUBMITTED_AT,
    }
    return run_assessment_pipeline(
        assessment_input=assessment_input,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-ceiling",
        run_id=f"run-ceiling-{ownership}",
        assessed_at=ASSESSED_AT,
        retrieve_link=lambda *_args, **_kwargs: _repo(ownership),
    )


def _shortfalls(outcome: dict[str, Any]) -> str:
    result = outcome.get("assessment_result") or {}
    rows = result.get("criterion_results") or []
    gaps = [
        f"{row['criterion_id']} {row['awarded_points']}/{row['max_points']} {row['anchor']}"
        for row in rows
        if row["awarded_points"] != row["max_points"]
    ]
    flags = outcome.get("review_flags")
    prefix = f"state={outcome.get('state')} error={outcome.get('error_code')} flags={flags}"
    return prefix + " " + "; ".join(gaps)


def test_attributed_repository_reaches_full_score() -> None:
    outcome = _run("attributed")
    result = outcome["assessment_result"]
    assert outcome["state"] == "COMPLETED", _shortfalls(outcome)
    assert result["final_score"] == 100, _shortfalls(outcome)
    assert result["band"] == "strong_application_evidence"


def test_unclear_repository_stays_below_the_top_band() -> None:
    outcome = _run("unclear")
    assert outcome["state"] == "COMPLETED", _shortfalls(outcome)
    score = outcome["assessment_result"]["final_score"]
    assert score < 80, _shortfalls(outcome)
    assert outcome["assessment_result"]["band"] != "strong_application_evidence"
