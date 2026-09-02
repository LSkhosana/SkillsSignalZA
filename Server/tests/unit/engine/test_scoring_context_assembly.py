"""Package J scoring-context assembly tests."""

from __future__ import annotations

import ast
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from app.engine.configuration import (
    load_criterion_binding_rules_v1,
    load_evidence_rules_v1,
    load_rubric_v2,
)
from app.engine.context import ASSEMBLER_VERSION, assemble_scoring_context
from app.engine.context.provenance import load_provenance_allowlist, rule_id_for
from app.engine.schema_registry import draft_validator

CONTEXT_DIR = Path(__file__).resolve().parents[3] / "app" / "engine" / "context"
APPROVED_BINDING_RULES_SHA256 = "5d93ee05fa8c8dcff7b331eee04356ed085360bd1c0de93267c1ec307ffe1de3"
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
    track: str = "software_engineering",
    flags: list[str] | tuple[str, ...] = (),
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    outcome = assemble_scoring_context(
        track=track,
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


def test_registry_hash_and_packaging() -> None:
    packaged = files("app.schemas").joinpath("scoring_context_assembly.schema.json")
    assert packaged.is_file()
    rules = load_criterion_binding_rules_v1()
    payload = json.dumps(rules, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert ASSEMBLER_VERSION == "assemble.context.v1"
    assert digest == APPROVED_BINDING_RULES_SHA256


def test_exactly_26_bindings_in_rubric_order() -> None:
    rubric = load_rubric_v2()
    for track in ("software_engineering", "data_analytics"):
        outcome = _assemble([], track=track)
        expected = [item["id"] for item in rubric["tracks"][track]["criteria"]]
        got = [item["criterion_id"] for item in outcome["scoring_context"]["criterion_bindings"]]
        assert got == expected
        assert len(got) == 26
        draft_validator("scoring_context.schema.json").validate(outcome["scoring_context"])
    draft_validator("scoring_context.schema.json").validate(outcome["scoring_context"])


def test_missing_ordinary_criteria_are_missing_unverifiable() -> None:
    outcome = _assemble([])
    language = _binding(outcome, "se.core.programming_language")
    assert language["anchor"] == "missing_unverifiable"
    assert language["evidence_ids"] == []


def test_exactly_one_qualification_route() -> None:
    outcome = _assemble([])
    quals = [
        item
        for item in outcome["scoring_context"]["criterion_bindings"]
        if item["criterion_id"] == "se.alignment.qualification"
    ]
    assert len(quals) == 1
    assert quals[0]["anchor"] == "se.qual.none"


def test_react_does_not_satisfy_programming_language() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="react",
                fact_type="tool_application",
                evidence_level="documented",
            )
        ]
    )
    assert _binding(outcome, "se.core.programming_language")["anchor"] == "missing_unverifiable"
    assert _binding(outcome, "se.tools.framework_library")["anchor"] == "documented"


def test_database_products_do_not_satisfy_da_sql() -> None:
    outcome = _assemble(
        [_fact("ev-0001", subject="postgresql", fact_type="tool_application")],
        track="data_analytics",
    )
    assert _binding(outcome, "da.core.sql")["anchor"] == "missing_unverifiable"
    assert _binding(outcome, "da.tools.database_environment")["anchor"] == "documented"


def test_github_does_not_satisfy_git() -> None:
    outcome = _assemble(
        [_fact("ev-0001", subject="github", fact_type="tool_name", evidence_level="named_only")]
    )
    assert _binding(outcome, "se.tools.version_control")["anchor"] == "missing_unverifiable"
    assert _binding(outcome, "se.tools.repository_platform")["anchor"] == "named_only"


def test_sql_and_database_environment_are_distinct() -> None:
    facts = [
        _fact("ev-0001", subject="sql", fact_type="skill_application"),
        _fact("ev-0002", subject="postgresql", fact_type="tool_application"),
    ]
    outcome = _assemble(facts, track="data_analytics")
    sql = _binding(outcome, "da.core.sql")
    env = _binding(outcome, "da.tools.database_environment")
    assert sql["evidence_ids"] == ["ev-0001"]
    assert env["evidence_ids"] == ["ev-0002"]


def test_git_and_github_are_distinct() -> None:
    facts = [
        _fact("ev-0001", subject="git", fact_type="tool_application"),
        _fact("ev-0002", subject="github", fact_type="tool_name", evidence_level="named_only"),
    ]
    outcome = _assemble(facts)
    assert _binding(outcome, "se.tools.version_control")["evidence_ids"] == ["ev-0001"]
    assert _binding(outcome, "se.tools.repository_platform")["evidence_ids"] == ["ev-0002"]


def test_highest_defensible_level_wins_without_weaker_ids() -> None:
    facts = [
        _fact("ev-0001", subject="python", fact_type="skill_name", evidence_level="named_only"),
        _fact(
            "ev-0002", subject="python", fact_type="skill_application", evidence_level="documented"
        ),
    ]
    outcome = _assemble(facts)
    language = _binding(outcome, "se.core.programming_language")
    assert language["anchor"] == "documented"
    assert language["evidence_ids"] == ["ev-0002"]


def test_power_bi_binds_visualisation_and_alignment() -> None:
    outcome = _assemble(
        [_fact("ev-0001", subject="power_bi", fact_type="tool_application")],
        track="data_analytics",
    )
    assert _binding(outcome, "da.tools.bi_visualisation")["evidence_ids"] == ["ev-0001"]
    assert _binding(outcome, "da.tools.power_bi_alignment")["evidence_ids"] == ["ev-0001"]


def test_google_sheets_ceiling_trigger() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="google_sheets",
                fact_type="tool_application",
                evidence_level="demonstrated",
            )
        ],
        track="data_analytics",
    )
    assert "rubric.v2.da.cap.google_sheets_ceiling" in outcome["scoring_context"]["rule_triggers"]
    with_excel = _assemble(
        [
            _fact(
                "ev-0001",
                subject="google_sheets",
                fact_type="tool_application",
                evidence_level="demonstrated",
            ),
            _fact("ev-0002", subject="excel", fact_type="tool_name", evidence_level="named_only"),
        ],
        track="data_analytics",
    )
    assert (
        "rubric.v2.da.cap.google_sheets_ceiling"
        not in with_excel["scoring_context"]["rule_triggers"]
    )


def test_context_free_dashboard_trigger() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="context_free_dashboard_screenshot",
                fact_type="project_context",
            )
        ],
        track="data_analytics",
    )
    assert "rubric.v2.da.rule.context_free_dashboard" in outcome["scoring_context"]["rule_triggers"]


def test_language_sql_and_project_caps_are_not_duplicated_in_triggers() -> None:
    outcome = _assemble([])
    triggers = outcome["scoring_context"]["rule_triggers"]
    assert "rubric.v2.se.cap.no_language" not in triggers
    da = _assemble([], track="data_analytics")
    assert "rubric.v2.da.cap.no_sql" not in da["scoring_context"]["rule_triggers"]


def test_qualification_ambiguity_creates_review_flag() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="bachelor_degree",
                fact_type="qualification",
                explicit_text="Bachelor of Arts",
            )
        ]
    )
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" in outcome["review_flags"]
    assert _binding(outcome, "se.alignment.qualification")["anchor"] == "se.qual.none"
    assert outcome["state"] == "REVIEW_REQUIRED"


def test_blocking_flags_are_unique_and_ordered() -> None:
    outcome = _assemble(
        [],
        flags=("OWNERSHIP_UNCLEAR", "TRACK_MISMATCH", "OWNERSHIP_UNCLEAR"),
    )
    assert outcome["scoring_context"]["review_flags"] == ["TRACK_MISMATCH", "OWNERSHIP_UNCLEAR"]


def test_project_exclusions_follow_approved_rules() -> None:
    outcome = _assemble([], flags=("TRACK_MISMATCH",))
    exclusions = outcome["scoring_context"]["project_exclusion_ids"]
    assert "blocking_review_unresolved" in exclusions
    assert "track_mismatch" in exclusions
    assert "python_not_explicit" in exclusions
    assert "api_foundation_missing_unverifiable" in exclusions
    assert "no_positive_core_gap_coverage" not in exclusions


def test_package_j_does_not_call_scoring() -> None:
    forbidden = {"score_assessment", "app.engine.scoring", "golden_candidates"}
    for path in CONTEXT_DIR.glob("*.py"):
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
    _assemble(
        [_fact("ev-0001", subject="python", fact_type="skill_name", evidence_level="named_only")]
    )


def test_invalid_inputs_fail_without_scoring_context() -> None:
    failed_track = assemble_scoring_context(
        track="unknown",
        evidence_facts=[],
        source_records=[_cv_source()],
    )
    assert failed_track["state"] == "SCORING_CONTEXT_ASSEMBLY_FAILED"
    assert failed_track["error_code"] == "INVALID_TRACK"
    assert failed_track["scoring_context"] is None
    duplicate = assemble_scoring_context(
        track="software_engineering",
        evidence_facts=[
            _fact("ev-0001", subject="python", fact_type="skill_name"),
            _fact("ev-0001", subject="python", fact_type="skill_application"),
        ],
        source_records=[_cv_source()],
    )
    assert duplicate["error_code"] == "DUPLICATE_EVIDENCE_ID"
    unknown_flag = assemble_scoring_context(
        track="software_engineering",
        evidence_facts=[],
        source_records=[_cv_source()],
        review_flags=["NOT_A_FLAG"],
    )
    assert unknown_flag["error_code"] == "UNRECOGNIZED_REVIEW_FLAG"
    unknown_source = assemble_scoring_context(
        track="software_engineering",
        evidence_facts=[_fact("ev-0001", subject="python", fact_type="skill_name")],
        source_records=[],
    )
    assert unknown_source["error_code"] == "UNKNOWN_SOURCE"
    bootcamp = _assemble(
        [
            _fact(
                "ev-0001", subject="bootcamp", fact_type="qualification", explicit_text="Bootcamp"
            ),
            _fact("ev-0002", subject="python", fact_type="skill_application"),
        ]
    )
    assert _binding(bootcamp, "se.alignment.qualification")["anchor"] == "se.qual.bootcamp"
    assert _binding(bootcamp, "se.alignment.qualification")["evidence_ids"] == ["ev-0001"]


def test_provenance_allowlist_rejects_unknown_and_mismatched_facts() -> None:
    language_subjects = {"python", "java", "javascript", "typescript", "csharp", "php", "r"}
    mismatched = assemble_scoring_context(
        track="software_engineering",
        evidence_facts=[
            _fact(
                "ev-0001",
                subject="python",
                fact_type="professional_behaviour",
                rule_id="not.a.checked.in.rule",
            )
        ],
        source_records=[_cv_source()],
    )
    assert mismatched["state"] == "SCORING_CONTEXT_ASSEMBLY_FAILED"
    assert mismatched["error_code"] == "UNKNOWN_RULE_ID"
    assert mismatched["scoring_context"] is None
    wrong_combo = assemble_scoring_context(
        track="software_engineering",
        evidence_facts=[
            _fact(
                "ev-0001",
                subject="python",
                fact_type="professional_behaviour",
                rule_id=rule_id_for("collaboration", "professional_behaviour"),
            )
        ],
        source_records=[_cv_source()],
    )
    assert wrong_combo["error_code"] == "MISMATCHED_EVIDENCE_FACT"
    unknown_subject = assemble_scoring_context(
        track="software_engineering",
        evidence_facts=[
            _fact(
                "ev-0001",
                subject="not_a_subject",
                fact_type="skill_name",
                rule_id="normalize.v1.skill.python",
            )
        ],
        source_records=[_cv_source()],
    )
    assert unknown_subject["error_code"] == "UNKNOWN_SUBJECT"
    valid = _assemble(
        [
            _fact(
                "ev-0001",
                subject="python",
                fact_type="skill_application",
                evidence_level="documented",
            )
        ]
    )
    language = _binding(valid, "se.core.programming_language")
    assert language["anchor"] == "documented"
    assert language["evidence_ids"] == ["ev-0001"]
    assert language_subjects == {"python", "java", "javascript", "typescript", "csharp", "php", "r"}


def test_qualification_is_evaluated_per_fact_without_concatenation() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="bachelor_degree",
                fact_type="qualification",
                explicit_text="Completed Bachelor of Arts",
            ),
            _fact(
                "ev-0002",
                subject="bachelor_degree",
                fact_type="qualification",
                explicit_text="BSc Computer Science in progress",
            ),
        ]
    )
    qualification = _binding(outcome, "se.alignment.qualification")
    assert qualification["anchor"] == "se.qual.in_progress"
    assert qualification["evidence_ids"] == ["ev-0002"]
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" not in outcome["review_flags"]


def test_conflicting_qualification_status_is_review_required() -> None:
    outcome = _assemble(
        [
            _fact(
                "ev-0001",
                subject="bachelor_degree",
                fact_type="qualification",
                explicit_text="Completed BSc Computer Science in progress",
            )
        ]
    )
    assert "MATERIAL_CLASSIFICATION_AMBIGUITY" in outcome["review_flags"]
    assert _binding(outcome, "se.alignment.qualification")["anchor"] == "se.qual.none"
    assert _binding(outcome, "se.alignment.qualification")["evidence_ids"] == []


def test_binding_registry_structure_and_h1_dev_environment_gap() -> None:
    rules = load_criterion_binding_rules_v1()
    rubric = load_rubric_v2()
    allowlist = load_provenance_allowlist()
    assert rules["assembler_version"] == "assemble.context.v1"
    assert rules["flag_order"] == list(dict.fromkeys(rules["flag_order"]))
    assert set(rules["flag_order"]) == set(rules["recognized_flags"])
    for track, spec in rules["tracks"].items():
        ids = [item["criterion_id"] for item in spec["criteria"]]
        expected = [item["id"] for item in rubric["tracks"][track]["criteria"]]
        assert ids == expected
        assert len(ids) == len(set(ids)) == 26
        for item in spec["criteria"]:
            for subject in item.get("subjects") or []:
                assert subject in allowlist.subjects
            for subject in item.get("fallback_subjects") or []:
                assert subject in allowlist.subjects
    se_dev = next(
        item
        for item in rules["tracks"]["software_engineering"]["criteria"]
        if item["criterion_id"] == "se.tools.dev_environment"
    )
    assert se_dev["subjects"] == []
    assert _binding(_assemble([]), "se.tools.dev_environment")["anchor"] == "missing_unverifiable"


def test_provenance_allowlist_is_unique() -> None:
    allowlist = load_provenance_allowlist()
    assert len(allowlist.triples) == len(set(allowlist.triples))
    assert allowlist.subjects
    assert allowlist.rule_ids
    assert ("python", "skill_application", "normalize.v1.skill.python") in allowlist.triples
    assert (
        "python",
        "professional_behaviour",
        "normalize.v1.skill.python",
    ) not in allowlist.triples
    evidence = load_evidence_rules_v1()
    subjects = [item["subject"] for item in (*evidence["subjects"], *evidence["qualifications"])]
    rule_ids = [item["rule_id"] for item in (*evidence["subjects"], *evidence["qualifications"])]
    assert len(subjects) == len(set(subjects))
    assert len(rule_ids) == len(set(rule_ids))
