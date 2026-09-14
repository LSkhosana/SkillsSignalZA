"""Issue #38 review-gate hotfix: qualification year wording and default-unclear links."""

from __future__ import annotations

from typing import Any

from app.engine.context import assemble_scoring_context
from app.engine.context.provenance import rule_id_for
from app.engine.outcomes import BLOCKING_REVIEW_FLAGS
from app.engine.schema_registry import draft_validator

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _cv_source() -> dict[str, Any]:
    return {
        "source_id": "src-cv",
        "source_type": "cv",
        "submitted_by_candidate": True,
        "access_status": "accessible",
        "ownership_status": "attributed",
        "retrieved_at": "2026-09-01T12:00:00Z",
        "content_hash": EMPTY_SHA256,
        "extractor_version": "extract.cv.v1",
        "locator": "page 1",
        "notes": "cv",
    }


def _link_source() -> dict[str, Any]:
    return {
        "source_id": "src-link-1",
        "source_type": "repository",
        "submitted_by_candidate": True,
        "access_status": "accessible",
        "ownership_status": "unclear",
        "retrieved_at": "2026-09-01T12:00:00Z",
        "content_hash": EMPTY_SHA256,
        "extractor_version": "extract.link.v1",
        "locator": "https://example.com/project",
        "notes": "Candidate-submitted link retrieved without classification or scoring.",
    }


def _fact(
    evidence_id: str,
    *,
    subject: str,
    fact_type: str,
    evidence_level: str = "documented",
    explicit_text: str = "explicit",
    source_id: str = "src-cv",
    attribution_status: str = "attributed",
    rule_id: str | None = None,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "locator": "page 1, block 1",
        "fact_type": fact_type,
        "subject": subject,
        "explicit_text": explicit_text,
        "evidence_level": evidence_level,
        "attribution_status": attribution_status,
        "rule_id": rule_id if rule_id is not None else rule_id_for(subject, fact_type),
        "review_status": "accepted",
    }


def _assemble(
    facts: list[dict[str, Any]],
    *,
    sources: list[dict[str, Any]] | None = None,
    flags: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    outcome = assemble_scoring_context(
        track="software_engineering",
        evidence_facts=facts,
        source_records=sources or [_cv_source()],
        review_flags=flags,
    )
    draft_validator("scoring_context_assembly.schema.json").validate(outcome)
    return outcome


def _binding(outcome: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    return next(
        item
        for item in outcome["scoring_context"]["criterion_bindings"]
        if item["criterion_id"] == criterion_id
    )


def test_years_of_experience_is_not_qualification_ambiguity() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="react",
                fact_type="tool_name",
                evidence_level="named_only",
                explicit_text="3 years of React experience",
            )
        ]
    )
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" not in outcome["review_flags"]
    assert _binding(outcome, "se.alignment.qualification") == {
        "criterion_id": "se.alignment.qualification",
        "anchor": "se.qual.none",
        "evidence_ids": [],
    }
    assert outcome["state"] == "COMPLETED"
    assert not set(outcome["review_flags"]) & BLOCKING_REVIEW_FLAGS


def test_final_year_qualification_remains_in_progress() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="bachelor_degree",
                fact_type="qualification",
                explicit_text="final year BSc Computer Science",
            )
        ]
    )
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" not in outcome["review_flags"]
    assert _binding(outcome, "se.alignment.qualification")["anchor"] == "se.qual.in_progress"
    assert _binding(outcome, "se.alignment.qualification")["evidence_ids"] == ["ev-0001"]
    assert outcome["state"] == "COMPLETED"


def test_two_conflicting_qualification_routes_remain_review_required() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="bachelor_degree",
                fact_type="qualification",
                explicit_text="Completed BSc Computer Science",
            ),
            _fact(
                "ev-0002",
                subject="bachelor_degree",
                fact_type="qualification",
                explicit_text="BSc Computer Science in progress",
            ),
        ]
    )
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" in outcome["review_flags"]
    assert _binding(outcome, "se.alignment.qualification")["anchor"] == "se.qual.none"
    assert outcome["state"] == "REVIEW_REQUIRED"


def test_default_unclear_link_facts_do_not_block_assembly() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="python",
                fact_type="skill_application",
                source_id="src-link-1",
                attribution_status="unclear",
                explicit_text="Built a Flask API in Python",
            )
        ],
        sources=[_cv_source(), _link_source()],
    )
    assert "OWNERSHIP_UNCLEAR" not in outcome["review_flags"]
    assert outcome["state"] == "COMPLETED"
    assert _binding(outcome, "se.core.programming_language")["anchor"] == "documented"


def test_unclear_repo_content_does_not_credit_technical_depth_ownership() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="se_technical_depth_ownership",
                fact_type="project_process",
                source_id="src-link-1",
                attribution_status="unclear",
                explicit_text="Built a Flask API in Python",
            ),
            _fact(
                "ev-0002",
                subject="python",
                fact_type="skill_application",
                source_id="src-link-1",
                attribution_status="unclear",
                explicit_text="Built a Flask API in Python",
            ),
        ],
        sources=[_cv_source(), _link_source()],
    )
    assert _binding(outcome, "se.projects.depth_ownership")["anchor"] == "missing_unverifiable"
    assert _binding(outcome, "se.projects.depth_ownership")["evidence_ids"] == []
    assert _binding(outcome, "se.core.programming_language")["anchor"] == "documented"
    assert "OWNERSHIP_UNCLEAR" not in outcome["review_flags"]
    assert outcome["state"] == "COMPLETED"


def test_attributed_depth_ownership_still_binds() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="se_technical_depth_ownership",
                fact_type="project_process",
                attribution_status="attributed",
                explicit_text="I implemented the auth module and owned the API design",
            )
        ]
    )
    assert _binding(outcome, "se.projects.depth_ownership")["anchor"] == "documented"
    assert _binding(outcome, "se.projects.depth_ownership")["evidence_ids"] == ["ev-0001"]


def test_conflicting_attribution_remains_source_contradiction() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="python",
                fact_type="skill_application",
                attribution_status="conflicting",
                explicit_text="Wrote SQL queries for monthly reporting.",
            )
        ]
    )
    assert "MATERIAL_SOURCE_CONTRADICTION" in outcome["review_flags"]
    assert outcome["state"] == "REVIEW_REQUIRED"
