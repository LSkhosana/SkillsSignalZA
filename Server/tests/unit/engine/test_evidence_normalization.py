"""Package H deterministic explicit evidence normalization tests."""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.engine.configuration import load_json
from app.engine.evidence import MAX_EVIDENCE_FACTS, NORMALIZER_VERSION, normalize_evidence
from app.engine.evidence.outcomes import (
    ERROR_CLASSIFIER_EXCEPTION,
    ERROR_CV_NOT_EXTRACTABLE,
    ERROR_DUPLICATE_SOURCE_ID,
    ERROR_FACT_LIMIT_EXCEEDED,
    ERROR_INVALID_CV_EXTRACTION,
    ERROR_INVALID_LINK_RETRIEVAL,
    ERROR_INVALID_TRACK,
    ERROR_MALFORMED_SOURCE_STRUCTURE,
    ERROR_RULESET_INVALID,
    REVIEW_FLAG_OWNERSHIP_UNCLEAR,
)

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "app" / "schemas"
EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "app" / "engine" / "evidence"
OUTCOME_SCHEMA_PATH = SCHEMA_DIR / "evidence_normalization.schema.json"
FACT_SCHEMA_PATH = SCHEMA_DIR / "evidence_fact.schema.json"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
EXTRACTED_AT = "2026-09-01T12:00:00Z"
SECRET = "C:\\secret\\path traceback must not leak https://example.com/body"
DEFERRED_FACT_TYPES = {
    "project_proof",
    "project_context",
    "project_process",
    "project_outcome",
    "professional_behaviour",
    "role_alignment",
    "document_quality",
}


def _outcome_validator() -> Draft202012Validator:
    return Draft202012Validator(
        load_json(OUTCOME_SCHEMA_PATH),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def _fact_validator() -> Draft202012Validator:
    return Draft202012Validator(
        load_json(FACT_SCHEMA_PATH),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def _cv_completed(*texts: str, source_id: str = "src-cv") -> dict[str, Any]:
    return {
        "state": "COMPLETED",
        "error_code": None,
        "extractor_version": "extract.cv.v1",
        "document": {
            "document_id": source_id,
            "original_filename": "cv.pdf",
            "declared_media_type": "application/pdf",
            "verified_media_type": "application/pdf",
            "byte_size": 128,
            "sha256": EMPTY_SHA256,
        },
        "source_record": {
            "source_id": source_id,
            "source_type": "cv",
            "submitted_by_candidate": True,
            "access_status": "accessible",
            "ownership_status": "attributed",
            "retrieved_at": EXTRACTED_AT,
            "content_hash": EMPTY_SHA256,
            "extractor_version": "extract.cv.v1",
            "locator": "page 1",
            "notes": "Candidate-submitted CV extracted without classification or scoring.",
        },
        "content_blocks": [
            {
                "block_id": f"blk-{index}",
                "locator": f"page 1, block {index}",
                "text": text,
            }
            for index, text in enumerate(texts, start=1)
        ],
    }


def _cv_failed() -> dict[str, Any]:
    failed = _cv_completed("unused")
    failed["state"] = "CV_EXTRACTION_FAILED"
    failed["error_code"] = "NO_EXTRACTABLE_TEXT"
    failed["source_record"] = None
    failed["content_blocks"] = []
    failed["document"]["verified_media_type"] = None
    failed["document"]["byte_size"] = 12
    failed["document"]["sha256"] = EMPTY_SHA256
    return failed


def _link_completed(
    *texts: str,
    link_id: str = "link-1",
    ownership: str = "unclear",
    access_status: str = "accessible",
    source_type: str = "project",
    url: str = "https://example.com/project",
) -> dict[str, Any]:
    source_id = f"src-{link_id}"
    return {
        "state": "COMPLETED",
        "error_code": None,
        "extractor_version": "extract.link.v1",
        "link": {
            "link_id": link_id,
            "submitted_url": url,
            "normalized_url": url,
            "final_url": url,
            "declared_type": source_type,
            "verified_content_type": "text/html",
            "http_status": 200,
            "byte_size": 100,
            "sha256": EMPTY_SHA256,
        },
        "source_record": {
            "source_id": source_id,
            "source_type": source_type,
            "submitted_by_candidate": True,
            "access_status": access_status,
            "ownership_status": ownership,
            "retrieved_at": EXTRACTED_AT,
            "content_hash": EMPTY_SHA256,
            "extractor_version": "extract.link.v1",
            "locator": url,
            "notes": "Candidate-submitted link retrieved without classification or scoring.",
        },
        "content_blocks": [
            {
                "block_id": f"lnk-{index}",
                "locator": f"document order {index}",
                "text": text,
            }
            for index, text in enumerate(texts, start=1)
        ],
    }


def _link_failed(
    *,
    link_id: str = "link-unsafe",
    error_code: str = "UNSAFE_HOST",
    access_status: str = "unsafe",
    url: str = "https://example.com/private",
) -> dict[str, Any]:
    outcome = _link_completed(link_id=link_id, access_status=access_status, url=url)
    outcome["state"] = "LINK_RETRIEVAL_FAILED"
    outcome["error_code"] = error_code
    outcome["content_blocks"] = []
    outcome["link"]["normalized_url"] = None
    outcome["link"]["final_url"] = None
    outcome["link"]["verified_content_type"] = None
    outcome["link"]["http_status"] = None
    outcome["link"]["byte_size"] = None
    outcome["link"]["sha256"] = None
    outcome["source_record"]["content_hash"] = None
    return outcome


def _normalize(
    cv: dict[str, Any] | None = None,
    links: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    track: str = "software_engineering",
) -> dict[str, Any]:
    return normalize_evidence(
        track=track,
        cv_extraction=_cv_completed("Junior Software Engineer") if cv is None else cv,
        link_retrievals=links,
    )


def _assert_valid_outcome(outcome: dict[str, Any]) -> None:
    _outcome_validator().validate(outcome)
    fact_validator = _fact_validator()
    for fact in outcome["evidence_facts"]:
        fact_validator.validate(fact)
        assert fact["review_status"] == "accepted"
        assert fact["evidence_level"] != "missing_unverifiable"
        assert fact["fact_type"] not in DEFERRED_FACT_TYPES
    assert outcome["normalizer_version"] == NORMALIZER_VERSION
    serialized = json.dumps(outcome)
    assert "assessment_result" not in outcome
    assert "criterion_results" not in serialized
    assert "score_assessment" not in serialized
    assert "traceback" not in serialized.lower()
    assert SECRET not in serialized


def _facts(outcome: dict[str, Any], **filters: Any) -> list[dict[str, Any]]:
    found = []
    for fact in outcome["evidence_facts"]:
        if all(fact[key] == value for key, value in filters.items()):
            found.append(fact)
    return found


def test_schema_is_packaged_and_valid() -> None:
    packaged = files("app.schemas").joinpath("evidence_normalization.schema.json")
    assert packaged.is_file()
    schema = json.loads(packaged.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    assert MAX_EVIDENCE_FACTS == 5000


def test_flask_python_application_is_documented_from_cv() -> None:
    outcome = _normalize(_cv_completed("Built a Flask API in Python"))
    _assert_valid_outcome(outcome)
    assert outcome["state"] == "COMPLETED"
    python = _facts(outcome, subject="python", fact_type="skill_application")
    flask = _facts(outcome, subject="flask", fact_type="tool_application")
    assert python[0]["evidence_level"] == "documented"
    assert flask[0]["evidence_level"] == "documented"
    assert python[0]["attribution_status"] == "attributed"
    assert python[0]["explicit_text"] == "Built a Flask API in Python"
    assert python[0]["evidence_id"] == "ev-0001" or flask[0]["evidence_id"].startswith("ev-")


def test_named_list_is_named_only_without_application_upgrade() -> None:
    outcome = _normalize(_cv_completed("Python, SQL, Power BI"))
    _assert_valid_outcome(outcome)
    assert {fact["subject"] for fact in outcome["evidence_facts"]} == {"python", "sql", "power_bi"}
    for fact in outcome["evidence_facts"]:
        assert fact["evidence_level"] == "named_only"
        assert fact["fact_type"] in {"skill_name", "tool_name"}
        assert fact["explicit_text"] == "Python, SQL, Power BI"


def test_advanced_python_remains_named_only() -> None:
    outcome = _normalize(_cv_completed("Advanced Python"))
    _assert_valid_outcome(outcome)
    python = _facts(outcome, subject="python")
    assert python[0]["evidence_level"] == "named_only"
    assert python[0]["fact_type"] == "skill_name"


def test_react_does_not_create_javascript() -> None:
    outcome = _normalize(_cv_completed("Familiar with React"))
    _assert_valid_outcome(outcome)
    assert _facts(outcome, subject="react")
    assert not _facts(outcome, subject="javascript")
    assert _facts(outcome, subject="react")[0]["evidence_level"] == "named_only"


def test_javascript_does_not_create_java() -> None:
    outcome = _normalize(_cv_completed("JavaScript"))
    _assert_valid_outcome(outcome)
    assert _facts(outcome, subject="javascript")
    assert not _facts(outcome, subject="java")


def test_database_tools_do_not_imply_standalone_sql() -> None:
    outcome = _normalize(
        _cv_completed("PostgreSQL", "MySQL", "SQLite", "SQL Server", "SQL and Postgres")
    )
    _assert_valid_outcome(outcome)
    assert _facts(outcome, subject="postgresql")
    assert _facts(outcome, subject="mysql")
    assert _facts(outcome, subject="sqlite")
    assert _facts(outcome, subject="sql_server")
    sql_facts = _facts(outcome, subject="sql")
    assert len(sql_facts) == 1
    assert "SQL and Postgres" in sql_facts[0]["explicit_text"]


def test_hosting_platforms_do_not_create_git() -> None:
    outcome = _normalize(_cv_completed("GitHub", "GitLab", "Bitbucket"))
    _assert_valid_outcome(outcome)
    assert _facts(outcome, subject="github")
    assert _facts(outcome, subject="gitlab")
    assert _facts(outcome, subject="bitbucket")
    assert not _facts(outcome, subject="git")


def test_dotnet_and_aspnet_do_not_create_csharp() -> None:
    outcome = _normalize(_cv_completed(".NET", "ASP.NET"))
    _assert_valid_outcome(outcome)
    assert _facts(outcome, subject="dotnet")
    assert _facts(outcome, subject="aspnet")
    assert not _facts(outcome, subject="csharp")


def test_qualification_does_not_create_technical_skill() -> None:
    outcome = _normalize(_cv_completed("BSc Computer Science in Python"))
    _assert_valid_outcome(outcome)
    qualifications = _facts(outcome, fact_type="qualification", subject="bachelor_degree")
    assert qualifications[0]["evidence_level"] == "documented"
    assert not _facts(outcome, subject="python")
    assert all(fact["fact_type"] == "qualification" for fact in outcome["evidence_facts"])


def test_job_title_alone_produces_no_technical_or_behaviour_facts() -> None:
    outcome = _normalize(_cv_completed("Junior Software Engineer"))
    _assert_valid_outcome(outcome)
    assert outcome["state"] == "COMPLETED"
    assert outcome["evidence_facts"] == []
    assert outcome["error_code"] is None


def test_cv_application_is_never_demonstrated() -> None:
    outcome = _normalize(_cv_completed("Built a Flask API in Python"))
    _assert_valid_outcome(outcome)
    for fact in outcome["evidence_facts"]:
        assert fact["evidence_level"] != "demonstrated"


def test_attributed_non_cv_application_is_demonstrated() -> None:
    outcome = _normalize(
        _cv_completed("Junior Software Engineer"),
        [_link_completed("Built a Flask API in Python", ownership="attributed")],
    )
    _assert_valid_outcome(outcome)
    python = _facts(outcome, subject="python", fact_type="skill_application")
    flask = _facts(outcome, subject="flask", fact_type="tool_application")
    assert python[0]["evidence_level"] == "demonstrated"
    assert flask[0]["evidence_level"] == "demonstrated"
    assert python[0]["attribution_status"] == "attributed"
    assert outcome["state"] == "COMPLETED"


def test_unclear_link_application_is_documented_and_review_required() -> None:
    outcome = _normalize(
        _cv_completed("Junior Software Engineer"),
        [_link_completed("Built a Flask API in Python")],
    )
    _assert_valid_outcome(outcome)
    python = _facts(outcome, subject="python")[0]
    assert python["evidence_level"] == "documented"
    assert python["attribution_status"] == "unclear"
    assert python["evidence_level"] != "demonstrated"
    assert outcome["state"] == "REVIEW_REQUIRED"
    assert outcome["error_code"] == REVIEW_FLAG_OWNERSHIP_UNCLEAR
    assert outcome["review_flags"] == [REVIEW_FLAG_OWNERSHIP_UNCLEAR]


def test_inaccessible_link_creates_no_facts_and_preserves_source() -> None:
    failed = _link_failed()
    original = deepcopy(failed["source_record"])
    outcome = _normalize(_cv_completed("Junior Software Engineer"), [failed])
    _assert_valid_outcome(outcome)
    assert outcome["state"] == "COMPLETED"
    assert outcome["evidence_facts"] == []
    assert outcome["source_records"][1] == original
    assert outcome["source_records"][1] is not failed["source_record"]


def test_repeated_wording_deduplicates_with_precedence() -> None:
    cv = _cv_completed("Built a Flask API in Python")
    link = _link_completed("Built a Flask API in Python")
    outcome = _normalize(cv, [link])
    _assert_valid_outcome(outcome)
    python = _facts(outcome, subject="python", fact_type="skill_application")
    assert len(python) == 1
    assert python[0]["source_id"] == "src-cv"
    assert python[0]["attribution_status"] == "attributed"
    assert python[0]["evidence_level"] == "documented"
    assert outcome["state"] == "COMPLETED"
    assert outcome["review_flags"] == []


def test_later_demonstrated_replaces_earlier_documented_duplicate() -> None:
    cv = _cv_completed("Built a Flask API in Python")
    link = _link_completed("Built a Flask API in Python", ownership="attributed")
    outcome = _normalize(cv, [link])
    _assert_valid_outcome(outcome)
    python = _facts(outcome, subject="python", fact_type="skill_application")
    assert len(python) == 1
    assert python[0]["evidence_level"] == "demonstrated"
    assert python[0]["source_id"] == "src-link-1"
    assert python[0]["attribution_status"] == "attributed"


def test_different_wording_for_same_subject_stays_separate() -> None:
    outcome = _normalize(_cv_completed("Python", "Built services in Python"))
    _assert_valid_outcome(outcome)
    python_facts = _facts(outcome, subject="python")
    assert len(python_facts) == 2
    types = {fact["fact_type"] for fact in python_facts}
    assert types == {"skill_name", "skill_application"}


def test_ids_and_output_are_byte_equivalent_across_calls() -> None:
    cv = _cv_completed("Python, SQL, Power BI", "Built a Flask API in Python")
    links = (_link_completed("Used Docker"),)
    first = _normalize(cv, links)
    second = _normalize(deepcopy(cv), deepcopy(links))
    _assert_valid_outcome(first)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert [fact["evidence_id"] for fact in first["evidence_facts"]] == [
        f"ev-{index:04d}" for index in range(1, len(first["evidence_facts"]) + 1)
    ]


def test_source_records_are_preserved_byte_for_byte() -> None:
    cv = _cv_completed("Python")
    original = deepcopy(cv["source_record"])
    outcome = _normalize(cv)
    _assert_valid_outcome(outcome)
    assert outcome["source_records"][0] == original
    assert outcome["source_records"][0] is not cv["source_record"]


def test_named_only_long_block_uses_matched_term() -> None:
    padding = "Experience overview " * 20
    text = f"{padding} Python {padding}"
    assert len(text) > 240
    outcome = _normalize(_cv_completed(text))
    _assert_valid_outcome(outcome)
    python = _facts(outcome, subject="python")[0]
    assert python["explicit_text"] == "Python"
    assert python["evidence_level"] == "named_only"


def test_proficiency_and_study_wording_are_not_application_cues() -> None:
    outcome = _normalize(
        _cv_completed(
            "Knowledge of Git",
            "Learned Python",
            "Studied SQL",
            "Proficient in Excel",
            "Certified in AWS",
        )
    )
    _assert_valid_outcome(outcome)
    technical = [fact for fact in outcome["evidence_facts"] if fact["fact_type"] != "qualification"]
    assert technical
    for fact in technical:
        assert fact["evidence_level"] == "named_only"


def test_uppercase_r_matches_and_lowercase_r_does_not() -> None:
    outcome = _normalize(_cv_completed("Used R and the R language", "I used r daily"))
    _assert_valid_outcome(outcome)
    r_facts = _facts(outcome, subject="r")
    assert r_facts
    assert all(" r " not in f" {fact['explicit_text']} " for fact in r_facts)


def test_application_does_not_cross_content_block_boundary() -> None:
    outcome = _normalize(_cv_completed("Built several services.", "Python"))
    _assert_valid_outcome(outcome)
    python = _facts(outcome, subject="python")[0]
    assert python["fact_type"] == "skill_name"
    assert python["evidence_level"] == "named_only"


def test_invalid_track_fails_safely() -> None:
    outcome = _normalize(track="not_a_track")
    _assert_valid_outcome(outcome)
    assert outcome["state"] == "EVIDENCE_NORMALIZATION_FAILED"
    assert outcome["error_code"] == ERROR_INVALID_TRACK
    assert outcome["evidence_facts"] == []


def test_invalid_cv_envelope_fails_safely() -> None:
    outcome = normalize_evidence(track="software_engineering", cv_extraction={"state": "nope"})
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_INVALID_CV_EXTRACTION
    assert outcome["evidence_facts"] == []
    not_object = normalize_evidence(
        track="software_engineering",
        cv_extraction="nope",  # type: ignore[arg-type]
    )
    _assert_valid_outcome(not_object)
    assert not_object["error_code"] == ERROR_INVALID_CV_EXTRACTION


def test_failed_cv_is_not_extractable() -> None:
    outcome = _normalize(_cv_failed())
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_CV_NOT_EXTRACTABLE
    assert outcome["source_records"] == []


def test_invalid_link_envelope_fails_safely() -> None:
    outcome = _normalize(links=[{"state": "nope"}])
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_INVALID_LINK_RETRIEVAL
    missing = normalize_evidence(
        track="software_engineering",
        cv_extraction=_cv_completed("Junior Software Engineer"),
        link_retrievals=None,  # type: ignore[arg-type]
    )
    _assert_valid_outcome(missing)
    assert missing["error_code"] == ERROR_INVALID_LINK_RETRIEVAL
    not_object = _normalize(links=["nope"])  # type: ignore[arg-type]
    _assert_valid_outcome(not_object)
    assert not_object["error_code"] == ERROR_INVALID_LINK_RETRIEVAL


def test_duplicate_source_ids_fail_safely() -> None:
    link = _link_completed("Python")
    link["source_record"]["source_id"] = "src-cv"
    outcome = _normalize(_cv_completed("Python"), [link])
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_DUPLICATE_SOURCE_ID


def test_malformed_ownership_fails_safely() -> None:
    link = _link_completed("Python", ownership="invented")
    outcome = _normalize(_cv_completed("Junior Software Engineer"), [link])
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_MALFORMED_SOURCE_STRUCTURE


def test_ruleset_invalid_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> dict[str, Any]:
        raise ValueError("bad rules")

    monkeypatch.setattr("app.engine.evidence.normalizer.load_compiled_registry", boom)
    outcome = _normalize()
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_RULESET_INVALID
    serialized = json.dumps(outcome)
    assert "bad rules" not in serialized


def test_fact_limit_fails_without_partial_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engine.evidence.normalizer.MAX_EVIDENCE_FACTS", 1)
    outcome = _normalize(_cv_completed("Python, SQL"))
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_FACT_LIMIT_EXCEEDED
    assert outcome["evidence_facts"] == []
    assert outcome["source_records"] == []


def test_classifier_exception_leaks_no_candidate_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> list[Any]:
        raise RuntimeError(SECRET)

    monkeypatch.setattr("app.engine.evidence.normalizer.find_matches", boom)
    outcome = _normalize(_cv_completed("Built a Flask API in Python"))
    _assert_valid_outcome(outcome)
    assert outcome["error_code"] == ERROR_CLASSIFIER_EXCEPTION
    serialized = json.dumps(outcome)
    assert SECRET not in serialized
    assert "RuntimeError" not in serialized
    assert "Built a Flask API in Python" not in serialized


def test_units_perform_no_network_or_file_reopen_and_no_scoring() -> None:
    forbidden = {
        "socket",
        "httpx",
        "requests",
        "urllib",
        "http.client",
        "subprocess",
        "app.engine.scoring",
        "score_assessment",
        "golden_candidates",
        "openai",
        "fastapi",
    }
    for path in EVIDENCE_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not forbidden.intersection(imported)
        for token in forbidden:
            assert token not in text


def test_data_analytics_track_is_accepted() -> None:
    outcome = _normalize(_cv_completed("Python"), track="data_analytics")
    _assert_valid_outcome(outcome)
    assert outcome["track"] == "data_analytics"
    assert _facts(outcome, subject="python")
