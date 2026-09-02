"""Package I higher-order evidence classification tests."""

from __future__ import annotations

import ast
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.engine.classification import CLASSIFIER_VERSION, classify_higher_order_evidence
from app.engine.configuration import load_higher_order_rules_v1, load_json
from app.engine.evidence import normalize_evidence

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "app" / "schemas"
CLASSIFICATION_DIR = Path(__file__).resolve().parents[3] / "app" / "engine" / "classification"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
EXTRACTED_AT = "2026-09-01T12:00:00Z"
APPROVED_HIGHER_ORDER_RULES_SHA256 = (
    "6499d57ec41ec8d1e2d41a9788ccc84fc78630bcb8ba636a34847a2134af2b72"
)


def _cv(*texts: str, source_id: str = "src-cv") -> dict[str, Any]:
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


def _link(
    *texts: str,
    link_id: str = "link-1",
    source_type: str = "project",
    access_status: str = "accessible",
    url: str = "https://example.com/project",
) -> dict[str, Any]:
    return {
        "state": "COMPLETED"
        if access_status == "accessible" and texts
        else "LINK_RETRIEVAL_FAILED",
        "error_code": None if access_status == "accessible" and texts else "UNSAFE_HOST",
        "extractor_version": "extract.link.v1",
        "link": {
            "link_id": link_id,
            "submitted_url": url,
            "normalized_url": url if access_status == "accessible" else None,
            "final_url": url if access_status == "accessible" else None,
            "declared_type": source_type,
            "verified_content_type": "text/html" if texts else None,
            "http_status": 200 if texts else None,
            "byte_size": 100 if texts else None,
            "sha256": EMPTY_SHA256 if texts else None,
        },
        "source_record": {
            "source_id": f"src-{link_id}",
            "source_type": source_type,
            "submitted_by_candidate": True,
            "access_status": access_status,
            "ownership_status": "unclear",
            "retrieved_at": EXTRACTED_AT,
            "content_hash": EMPTY_SHA256 if texts else None,
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


def _classify(
    cv: dict[str, Any],
    links: list[dict[str, Any]] | tuple = (),
    track: str = "software_engineering",
):
    normalization = normalize_evidence(track=track, cv_extraction=cv, link_retrievals=links)
    outcome = classify_higher_order_evidence(
        track=track,
        normalization=normalization,
        cv_extraction=cv,
        link_retrievals=links,
    )
    Draft202012Validator(
        load_json(SCHEMA_DIR / "higher_order_classification.schema.json"),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    ).validate(outcome)
    return normalization, outcome


def _facts(outcome: dict[str, Any], **filters: Any) -> list[dict[str, Any]]:
    return [
        fact
        for fact in outcome["evidence_facts"]
        if all(fact[key] == value for key, value in filters.items())
    ]


def test_schema_and_registry_are_packaged() -> None:
    packaged = files("app.schemas").joinpath("higher_order_classification.schema.json")
    assert packaged.is_file()
    Draft202012Validator.check_schema(json.loads(packaged.read_text(encoding="utf-8")))
    rules = load_higher_order_rules_v1()
    payload = json.dumps(rules, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert CLASSIFIER_VERSION == "classify.higher.v1"
    assert digest == APPROVED_HIGHER_ORDER_RULES_SHA256


def test_package_h_facts_are_preserved_unchanged() -> None:
    cv = _cv("Built a Flask API in Python")
    normalization, outcome = _classify(cv)
    h_ids = [fact["evidence_id"] for fact in normalization["evidence_facts"]]
    combined_prefix = outcome["evidence_facts"][: len(h_ids)]
    assert combined_prefix == normalization["evidence_facts"]
    assert outcome["source_records"] == normalization["source_records"]


def test_accessible_submitted_work_proof_is_documented_when_ownership_unclear() -> None:
    cv = _cv("Junior Software Engineer")
    link = _link("Repository README")
    _, outcome = _classify(cv, [link])
    proof = _facts(outcome, subject="accessible_submitted_work")[0]
    assert proof["fact_type"] == "project_proof"
    assert proof["evidence_level"] == "documented"
    assert proof["attribution_status"] == "unclear"
    assert outcome["state"] == "REVIEW_REQUIRED"
    assert outcome["review_flags"] == ["OWNERSHIP_UNCLEAR"]
    assert proof["explicit_text"] == "Repository README"


def test_cv_project_reference_requires_artifact_and_url_marker() -> None:
    with_ref, outcome = _classify(_cv("Portfolio project at https://github.com/example/app"))
    assert _facts(outcome, subject="cv_project_reference")
    assert _facts(outcome, subject="cv_project_reference")[0]["evidence_level"] == "documented"
    _, missing = _classify(_cv("Delivered a successful project internally"))
    assert not _facts(missing, subject="cv_project_reference")


def test_project_context_requires_explicit_context_wording() -> None:
    _, with_context = _classify(_cv("Built an API to solve a workflow problem"))
    assert _facts(with_context, subject="software_project_context")
    _, title_only = _classify(_cv("Payments dashboard"))
    assert not _facts(title_only, subject="software_project_context")


def test_se_process_requires_application_in_project_boundary() -> None:
    _, outcome = _classify(_cv("Built a Flask API in Python"))
    assert _facts(outcome, subject="se_technical_process")
    assert _facts(outcome, subject="se_technical_depth_ownership")
    _, named = _classify(_cv("Python, Flask"))
    assert not _facts(named, subject="se_technical_process")


def test_da_analysis_and_tool_integration_require_same_sentence_application() -> None:
    _, process = _classify(
        _cv("Cleaned the sales dataset in a Python analysis to analyse operations"),
        track="data_analytics",
    )
    assert _facts(process, subject="da_analysis_process")
    _, integrated = _classify(
        _cv("Integrated Power BI with Excel in a dashboard to analyse the sales dataset"),
        track="data_analytics",
    )
    assert _facts(integrated, subject="da_tool_integration")
    _, listed = _classify(_cv("Python, Power BI, SQL"), track="data_analytics")
    assert not _facts(listed, subject="da_tool_integration")


def test_documentation_cues_are_project_bounded() -> None:
    _, bounded = _classify(_cv("The service README documents how to run tests"))
    assert _facts(bounded, subject="project_documentation")
    _, generic = _classify(_cv("I have good documentation skills"))
    assert not _facts(generic, subject="project_documentation")


def test_outcome_wording_is_preserved_exactly() -> None:
    text = "Deployed the service and reduced failures"
    _, outcome = _classify(_cv(text))
    facts = _facts(outcome, subject="software_project_outcome")
    assert facts[0]["explicit_text"] == text
    _, findings = _classify(
        _cv("The dashboard report identified a finding and recommendation"),
        track="data_analytics",
    )
    assert _facts(findings, subject="analytics_findings_visual_communication")


def test_dashboard_screenshot_requires_wording_and_missing_context() -> None:
    _, signal = _classify(_cv("Uploaded a dashboard screenshot"), track="data_analytics")
    assert _facts(signal, subject="context_free_dashboard_screenshot")
    _, with_context = _classify(
        _cv("Uploaded a dashboard screenshot to analyse the sales dataset"),
        track="data_analytics",
    )
    assert not _facts(with_context, subject="context_free_dashboard_screenshot")
    assert _facts(with_context, subject="analytics_project_context")


def test_forbidden_labels_create_no_readiness_fact() -> None:
    _, outcome = _classify(_cv("Team player and good communicator, detail-oriented self-starter"))
    assert not _facts(outcome, fact_type="professional_behaviour")


def test_behaviour_requires_approved_action_context() -> None:
    _, outcome = _classify(_cv("Collaborated with the client team and presented the API"))
    assert _facts(outcome, subject="collaboration")
    assert _facts(outcome, subject="communication")


def test_job_title_alone_creates_no_duties() -> None:
    _, outcome = _classify(_cv("Junior Software Engineer"))
    assert not _facts(outcome, fact_type="professional_behaviour")


def test_target_role_is_not_inferred_from_work_history() -> None:
    _, history = _classify(_cv("Software Engineer at Acme in 2021"))
    assert not _facts(history, fact_type="role_alignment")
    _, seeking = _classify(_cv("Seeking a junior software engineer role"))
    assert (
        _facts(seeking, subject="software_engineering_target")[0]["evidence_level"] == "documented"
    )


def test_opposite_track_target_creates_track_mismatch() -> None:
    _, outcome = _classify(_cv("Seeking a data analyst role"))
    assert "TRACK_MISMATCH" in outcome["review_flags"]
    assert outcome["state"] == "REVIEW_REQUIRED"


def test_document_quality_thresholds_are_deterministic() -> None:
    blocks = [
        "Summary",
        "Skills",
        "Experience",
        "Projects",
        "Education",
        "Built a Flask API in Python to solve a workflow problem",
    ]
    _, outcome = _classify(_cv(*blocks))
    readability = _facts(outcome, subject="structured_readability")[0]
    assert readability["evidence_level"] in {"documented", "demonstrated"}
    assert readability["fact_type"] == "document_quality"


def test_unclear_link_higher_order_facts_stay_documented() -> None:
    _, outcome = _classify(
        _cv("Junior Software Engineer"),
        [_link("Built a Flask API in Python to solve a workflow problem")],
    )
    higher = [
        fact
        for fact in outcome["evidence_facts"]
        if fact["source_id"] == "src-link-1"
        and fact["fact_type"] != "skill_application"
        and fact["fact_type"] != "tool_application"
    ]
    assert higher
    for fact in higher:
        assert fact["evidence_level"] != "demonstrated"
        assert fact["attribution_status"] == "unclear"
    assert outcome["review_flags"] == ["OWNERSHIP_UNCLEAR"]


def test_classification_modules_do_not_import_scoring() -> None:
    forbidden = {"app.engine.scoring", "score_assessment", "golden_candidates", "httpx"}
    for path in CLASSIFICATION_DIR.glob("*.py"):
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


def test_invalid_track_and_envelopes_fail_safely() -> None:
    cv = _cv("Python")
    failed_track = classify_higher_order_evidence(
        track="unknown",
        normalization={"state": "COMPLETED"},
        cv_extraction=cv,
    )
    assert failed_track["state"] == "HIGHER_ORDER_CLASSIFICATION_FAILED"
    assert failed_track["error_code"] == "INVALID_TRACK"
    failed_cv = classify_higher_order_evidence(
        track="software_engineering",
        normalization=normalize_evidence(track="software_engineering", cv_extraction=cv),
        cv_extraction={"state": "COMPLETED"},
    )
    assert failed_cv["error_code"] == "INVALID_CV_EXTRACTION"
    failed_links = classify_higher_order_evidence(
        track="software_engineering",
        normalization=normalize_evidence(track="software_engineering", cv_extraction=cv),
        cv_extraction=cv,
        link_retrievals=[{"state": "COMPLETED"}],
    )
    assert failed_links["error_code"] == "INVALID_LINK_RETRIEVAL"
    failed_norm = classify_higher_order_evidence(
        track="software_engineering",
        normalization={"state": "COMPLETED"},
        cv_extraction=cv,
    )
    assert failed_norm["error_code"] == "INVALID_NORMALIZATION"
    _, inaccessible = _classify(cv, [_link(access_status="inaccessible")])
    assert inaccessible["state"] == "COMPLETED"
    assert not [
        fact for fact in inaccessible["evidence_facts"] if fact["source_id"] == "src-link-1"
    ]
