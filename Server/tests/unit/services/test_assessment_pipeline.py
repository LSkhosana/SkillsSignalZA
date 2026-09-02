"""Package K in-memory assessment pipeline tests."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.engine.context import assemble_scoring_context
from app.engine.extraction.links.outcomes import (
    completed_link_outcome,
    failed_link_outcome,
    link_metadata,
    link_source_record,
)
from app.engine.schema_registry import draft_validator
from app.engine.scoring import score_assessment
from app.services.assessment_pipeline import run_assessment_pipeline
from tests.fixtures.cv_extraction.documents import build_text_pdf

PIPELINE_PATH = Path(__file__).resolve().parents[3] / "app" / "services" / "assessment_pipeline.py"
SECRET = "C:\\secret\\path traceback must not leak"
ASSESSED_AT = "2026-09-02T08:00:00Z"
SUBMITTED_AT = "2026-09-02T07:00:00Z"


def _pdf(lines: list[str]) -> bytes:
    return build_text_pdf([lines])


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


def _accessible_retrieve(submitted_url: str, **payload: Any) -> dict[str, Any]:
    digest = hashlib.sha256(b"x").hexdigest()
    link = link_metadata(
        link_id=payload["link_id"],
        submitted_url=submitted_url,
        declared_type=payload["declared_type"],
        normalized_url=submitted_url,
        final_url=submitted_url,
        verified_content_type="text/html",
        http_status=200,
        byte_size=12,
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
                "text": "Built a Flask API in Python",
            }
        ],
    )


def _run(
    track: str,
    lines: list[str],
    *,
    links: list[dict[str, Any]] | None = None,
    retrieve_link: Any = _blocked_retrieve,
) -> dict[str, Any]:
    file_bytes = _pdf(lines)
    outcome = run_assessment_pipeline(
        assessment_input=_input(track, file_bytes, links),
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=retrieve_link,
    )
    draft_validator("assessment_pipeline.schema.json").validate(outcome)
    return outcome


def test_successful_se_cv_only_reaches_completed() -> None:
    outcome = _run(
        "software_engineering",
        [
            "Summary",
            "Seeking a junior software engineer role",
            "Skills",
            "Experience",
            "Projects",
            "Education",
            "Built a Flask API in Python to solve a workflow problem",
        ],
    )
    assert outcome["state"] == "COMPLETED"
    assert outcome["error_code"] is None
    assert outcome["assessment_result"]["track"] == "software_engineering"
    assert outcome["assessment_result"]["final_score"] >= 0
    assert "extract_cv" in outcome["stages"]
    assert "score_assessment" in outcome["stages"]
    assert SECRET not in json.dumps(outcome)


def test_successful_da_cv_only_reaches_completed() -> None:
    outcome = _run(
        "data_analytics",
        [
            "Summary",
            "Seeking a junior data analyst role",
            "Skills",
            "Experience",
            "Education",
            "Used SQL to analyse the sales dataset",
        ],
    )
    assert outcome["state"] == "COMPLETED"
    assert outcome["assessment_result"]["track"] == "data_analytics"


def test_cv_hash_mismatch_fails_before_scoring() -> None:
    file_bytes = _pdf(["Python"])
    payload = _input("software_engineering", file_bytes)
    payload["cv"]["sha256"] = "ab" * 32
    outcome = run_assessment_pipeline(
        assessment_input=payload,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert outcome["state"] == "ASSESSMENT_PIPELINE_FAILED"
    assert outcome["error_code"] == "CV_HASH_MISMATCH"
    assert outcome["assessment_result"] is None
    assert "score_assessment" not in outcome["stages"]


def test_unreadable_cv_is_not_scorable() -> None:
    payload = b"%PDF-1.4 broken"
    outcome = run_assessment_pipeline(
        assessment_input=_input("software_engineering", payload),
        cv_file_bytes=payload,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert outcome["state"] == "NOT_SCORABLE"
    assert outcome["error_code"] == "CV_UNREADABLE"
    assert outcome["assessment_result"] is None


def test_missing_cv_bytes_are_not_scorable() -> None:
    file_bytes = _pdf(["Python"])
    outcome = run_assessment_pipeline(
        assessment_input=_input("software_engineering", file_bytes),
        cv_file_bytes=None,  # type: ignore[arg-type]
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert outcome["state"] == "NOT_SCORABLE"
    assert outcome["error_code"] == "CV_MISSING"


def test_invalid_assessment_input_fails() -> None:
    outcome = run_assessment_pipeline(
        assessment_input={"track": "software_engineering"},
        cv_file_bytes=_pdf(["Python"]),
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert outcome["state"] == "ASSESSMENT_PIPELINE_FAILED"
    assert outcome["error_code"] == "INVALID_ASSESSMENT_INPUT"


def test_weak_readable_cv_remains_scoreable() -> None:
    outcome = _run("software_engineering", ["Junior Software Engineer"])
    assert outcome["state"] == "COMPLETED"
    assert outcome["assessment_result"] is not None


def test_inaccessible_link_is_preserved_without_standalone_penalty() -> None:
    calls: list[str] = []

    def retrieve(submitted_url: str, **payload: Any) -> dict[str, Any]:
        calls.append(submitted_url)
        return _failed_retrieve(submitted_url, **payload)

    outcome = _run(
        "software_engineering",
        ["Junior Software Engineer"],
        links=[
            {
                "link_id": "link-1",
                "submitted_url": "https://example.com/private",
                "declared_type": "project",
            }
        ],
        retrieve_link=retrieve,
    )
    assert outcome["state"] == "COMPLETED"
    assert calls == ["https://example.com/private"]
    assert any(record["source_id"] == "src-link-1" for record in outcome["source_records"])
    assert outcome["assessment_result"] is not None


def test_accessible_unclear_link_is_review_required() -> None:
    outcome = _run(
        "software_engineering",
        ["Junior Software Engineer"],
        links=[
            {
                "link_id": "link-1",
                "submitted_url": "https://example.com/project",
                "declared_type": "project",
            }
        ],
        retrieve_link=_accessible_retrieve,
    )
    assert outcome["state"] == "REVIEW_REQUIRED"
    assert outcome["assessment_result"] is None
    assert "OWNERSHIP_UNCLEAR" in outcome["review_flags"]
    assert outcome["scoring_context"] is not None


def test_duplicate_url_same_type_is_retrieved_once() -> None:
    calls: list[str] = []

    def retrieve(submitted_url: str, **payload: Any) -> dict[str, Any]:
        calls.append(payload["link_id"])
        return _failed_retrieve(submitted_url, **payload)

    outcome = _run(
        "software_engineering",
        ["Junior Software Engineer"],
        links=[
            {
                "link_id": "link-a",
                "submitted_url": "https://Example.com/project",
                "declared_type": "project",
            },
            {
                "link_id": "link-b",
                "submitted_url": "https://example.com/project",
                "declared_type": "project",
            },
        ],
        retrieve_link=retrieve,
    )
    assert outcome["state"] == "COMPLETED"
    assert calls == ["link-a"]


def test_duplicate_url_conflicting_types_never_silently_chooses() -> None:
    outcome = _run(
        "software_engineering",
        ["Junior Software Engineer"],
        links=[
            {
                "link_id": "link-a",
                "submitted_url": "https://example.com/project",
                "declared_type": "project",
            },
            {
                "link_id": "link-b",
                "submitted_url": "https://example.com/project",
                "declared_type": "repository",
            },
        ],
    )
    assert outcome["state"] == "REVIEW_REQUIRED"
    assert outcome["error_code"] == "MATERIAL_CLASSIFICATION_AMBIGUITY"
    assert outcome["assessment_result"] is None


def test_framework_only_triggers_no_language_cap() -> None:
    outcome = _run(
        "software_engineering",
        [
            "Summary",
            "Skills",
            "Experience",
            "Built a React application to solve a workflow problem",
        ],
    )
    assert outcome["state"] == "COMPLETED"
    language = next(
        item
        for item in outcome["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "se.core.programming_language"
    )
    assert language["anchor"] == "missing_unverifiable"
    assert any(
        cap["rule_id"] == "rubric.v2.se.cap.no_language"
        for cap in outcome["assessment_result"]["overall_caps"]
    )


def test_database_product_only_triggers_no_sql_cap() -> None:
    outcome = _run(
        "data_analytics",
        ["Summary", "Skills", "Used PostgreSQL to analyse the sales dataset"],
    )
    assert outcome["state"] == "COMPLETED"
    sql = next(
        item
        for item in outcome["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "da.core.sql"
    )
    assert sql["anchor"] == "missing_unverifiable"
    assert any(
        cap["rule_id"] == "rubric.v2.da.cap.no_sql"
        for cap in outcome["assessment_result"]["overall_caps"]
    )


def test_cv_only_project_hits_project_category_cap() -> None:
    outcome = _run(
        "software_engineering",
        [
            "Projects",
            "Built a Flask API in Python to solve a workflow problem at https://github.com/example/app",
        ],
    )
    assert outcome["state"] == "COMPLETED"
    assert any(
        cap["rule_id"] == "rubric.v2.se.cap.cv_only_projects"
        for cap in outcome["assessment_result"]["category_caps"]
    )


def test_power_bi_special_point_survives_pipeline() -> None:
    outcome = _run(
        "data_analytics",
        ["Summary", "Skills", "Used Power BI to analyse the sales dataset"],
    )
    assert outcome["state"] == "COMPLETED"
    alignment = next(
        item
        for item in outcome["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "da.tools.power_bi_alignment"
    )
    assert alignment["anchor"] != "missing_unverifiable"
    assert alignment["awarded_points"] == 1


def test_google_sheets_ceiling_survives_scoring_boundary() -> None:
    file_bytes = _pdf(["Used Google Sheets"])
    source = {
        "source_id": "src-cv",
        "source_type": "cv",
        "submitted_by_candidate": True,
        "access_status": "accessible",
        "ownership_status": "attributed",
        "retrieved_at": ASSESSED_AT,
        "content_hash": hashlib.sha256(file_bytes).hexdigest(),
        "extractor_version": "extract.cv.v1",
        "locator": "page 1",
        "notes": "cv",
    }
    fact = {
        "evidence_id": "ev-0001",
        "source_id": "src-cv",
        "locator": "page 1, block 1",
        "fact_type": "tool_application",
        "subject": "google_sheets",
        "explicit_text": "Used Google Sheets",
        "evidence_level": "demonstrated",
        "attribution_status": "attributed",
        "rule_id": "normalize.v1.tool.google_sheets",
        "review_status": "accepted",
    }
    assembly = assemble_scoring_context(
        track="data_analytics",
        evidence_facts=[fact],
        source_records=[source],
    )
    assert "rubric.v2.da.cap.google_sheets_ceiling" in assembly["scoring_context"]["rule_triggers"]
    scored = score_assessment(
        _input("data_analytics", file_bytes),
        [fact],
        assembly["scoring_context"],
        [source],
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
    )
    assert scored["state"] == "COMPLETED"
    sheets = next(
        item
        for item in scored["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "da.core.spreadsheets"
    )
    assert sheets["awarded_points"] <= 5
    assert "rubric.v2.da.cap.google_sheets_ceiling" in sheets["rule_ids"]


def test_pipeline_is_byte_equivalent_for_identical_inputs() -> None:
    lines = ["Summary", "Skills", "Built a Flask API in Python"]
    first = _run("software_engineering", lines)
    second = _run("software_engineering", lines)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_unexpected_exception_leaks_no_candidate_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError(SECRET)

    monkeypatch.setattr("app.services.assessment_pipeline.extract_cv", boom)
    outcome = _run("software_engineering", ["Built a Flask API in Python"])
    serialized = json.dumps(outcome)
    assert outcome["error_code"] == "ORCHESTRATION_EXCEPTION"
    assert SECRET not in serialized
    assert "RuntimeError" not in serialized
    assert "Built a Flask API in Python" not in serialized


def test_pipeline_schema_is_packaged() -> None:
    from importlib.resources import files

    packaged = files("app.schemas").joinpath("assessment_pipeline.schema.json")
    assert packaged.is_file()
    Draft202012Validator.check_schema(json.loads(packaged.read_text(encoding="utf-8")))


def test_invalid_identity_fails() -> None:
    file_bytes = _pdf(["Python"])
    outcome = run_assessment_pipeline(
        assessment_input=_input("software_engineering", file_bytes),
        cv_file_bytes=file_bytes,
        assessment_id=" ",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert outcome["error_code"] == "INVALID_ASSESSMENT_INPUT"


def test_missing_track_and_empty_input_fail_without_raising() -> None:
    file_bytes = _pdf(["Python"])
    empty = run_assessment_pipeline(
        assessment_input={},
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert empty["state"] == "ASSESSMENT_PIPELINE_FAILED"
    assert empty["error_code"] == "INVALID_ASSESSMENT_INPUT"
    payload = _input("software_engineering", file_bytes)
    del payload["track"]
    missing = run_assessment_pipeline(
        assessment_input=payload,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at=ASSESSED_AT,
        retrieve_link=_blocked_retrieve,
    )
    assert missing["state"] == "ASSESSMENT_PIPELINE_FAILED"
    assert missing["error_code"] == "INVALID_ASSESSMENT_INPUT"


def test_assessed_at_rfc3339_variants() -> None:
    lines = ["Junior Software Engineer"]
    file_bytes = _pdf(lines)
    payload = _input("software_engineering", file_bytes)
    zulu = run_assessment_pipeline(
        assessment_input=payload,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at="2026-09-02T08:00:00Z",
        retrieve_link=_blocked_retrieve,
    )
    assert zulu["state"] == "COMPLETED"
    fractional = run_assessment_pipeline(
        assessment_input=payload,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at="2026-09-02T08:00:00.123Z",
        retrieve_link=_blocked_retrieve,
    )
    assert fractional["state"] == "COMPLETED"
    offset = run_assessment_pipeline(
        assessment_input=payload,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at="2026-09-02T10:00:00+02:00",
        retrieve_link=_blocked_retrieve,
    )
    assert offset["state"] == "COMPLETED"
    impossible = run_assessment_pipeline(
        assessment_input=payload,
        cv_file_bytes=file_bytes,
        assessment_id="assessment-1",
        run_id="run-1",
        assessed_at="2026-02-30T08:00:00Z",
        retrieve_link=_blocked_retrieve,
    )
    assert impossible["state"] == "ASSESSMENT_PIPELINE_FAILED"
    assert impossible["error_code"] == "INVALID_ASSESSMENT_INPUT"
    assert impossible["error_code"] != "CV_UNREADABLE"


def test_normalization_failure_maps_to_pipeline_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.assessment_pipeline.normalize_evidence",
        lambda **_kwargs: {"state": "EVIDENCE_NORMALIZATION_FAILED"},
    )
    outcome = _run("software_engineering", ["Python"])
    assert outcome["error_code"] == "NORMALIZATION_FAILED"


def test_classification_failure_maps_to_pipeline_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.assessment_pipeline.classify_higher_order_evidence",
        lambda **_kwargs: {"state": "HIGHER_ORDER_CLASSIFICATION_FAILED"},
    )
    outcome = _run("software_engineering", ["Python"])
    assert outcome["error_code"] == "CLASSIFICATION_FAILED"


def test_context_assembly_failure_maps_to_pipeline_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.assessment_pipeline.assemble_scoring_context",
        lambda **_kwargs: {"state": "SCORING_CONTEXT_ASSEMBLY_FAILED"},
    )
    outcome = _run("software_engineering", ["Python"])
    assert outcome["error_code"] == "CONTEXT_ASSEMBLY_FAILED"


def test_pipeline_module_does_not_use_real_network_clients() -> None:
    text = PIPELINE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "httpx" not in imported
    assert "socket" not in imported
    assert "golden_candidates" not in text
