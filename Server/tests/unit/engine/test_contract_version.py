"""Active Engine Contract 1.1.0 metadata and preservation tests."""

import hashlib
from pathlib import Path

from app.engine.configuration import (
    load_action_catalog_v1,
    load_project_catalog_v1,
    load_rubric_v2,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_V1_PATH = REPO_ROOT / "Context" / "SkillSignalZA_Readiness_Report_Engine_Contract_V1.md"
CONTRACT_V1_1_PATH = (
    REPO_ROOT / "Context" / "SkillSignalZA_Readiness_Report_Engine_Contract_V1_1.md"
)
# Canonical LF digest of Contract 1.0.0. Raw Windows CRLF bytes hash differently.
LOCKED_CONTRACT_V1_SHA256 = "af5a56e67b4822f407cd8be3564179b025147067d074bb29e84b4d5b35ec6e69"
ACTIVE_CONTRACT_VERSION = "1.1.0"


def _canonical_text_sha256(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def test_rubric_declares_contract_1_1_0() -> None:
    rubric = load_rubric_v2()
    assert rubric["contract_version"] == ACTIVE_CONTRACT_VERSION
    assert rubric["rubric_version"] == "V2"


def test_action_catalog_declares_contract_1_1_0_and_catalog_1_0_0() -> None:
    catalog = load_action_catalog_v1()
    assert catalog["contract_version"] == ACTIVE_CONTRACT_VERSION
    assert catalog["catalog_version"] == "1.0.0"
    assert catalog["rubric_version"] == "V2"
    assert len(catalog["actions"]) == 212


def test_project_catalog_declares_contract_1_1_0_and_catalog_1_0_0() -> None:
    catalog = load_project_catalog_v1()
    assert catalog["contract_version"] == ACTIVE_CONTRACT_VERSION
    assert catalog["catalog_version"] == "1.0.0"
    assert catalog["rubric_version"] == "V2"
    assert len(catalog["projects"]) == 8
    assert {project["catalog_version"] for project in catalog["projects"]} == {"1.0.0"}


def test_active_configuration_shares_exactly_one_contract_version() -> None:
    versions = {
        load_rubric_v2()["contract_version"],
        load_action_catalog_v1()["contract_version"],
        load_project_catalog_v1()["contract_version"],
    }
    assert versions == {ACTIVE_CONTRACT_VERSION}


def test_canonical_text_sha256_is_newline_independent() -> None:
    lf = "line one\nline two\n"
    crlf = "line one\r\nline two\r\n"
    cr = "line one\rline two\r"
    digest = _canonical_text_sha256(lf)
    assert _canonical_text_sha256(crlf) == digest
    assert _canonical_text_sha256(cr) == digest


def test_contract_1_0_0_remains_present_and_unmodified() -> None:
    assert CONTRACT_V1_PATH.is_file()
    content = CONTRACT_V1_PATH.read_text(encoding="utf-8")
    assert "**Contract version:** 1.0.0" in content
    assert _canonical_text_sha256(content) == LOCKED_CONTRACT_V1_SHA256


def test_contract_1_1_0_records_action_rules_and_no_production_migration() -> None:
    content = CONTRACT_V1_1_PATH.read_text(encoding="utf-8")
    assert "**Contract version:** 1.1.0" in content
    assert (
        "Every non-qualification criterion must have a versioned action mapping "
        "for all four ordinary evidence states"
    ) in content
    assert "Qualification criteria do not use those four mappings." in content
    assert (
        "Each qualification criterion must instead have exactly one versioned action "
        "for every approved track-specific qualification route."
    ) in content
    assert "no historical assessment, report, or database migration is required" in content
    assert "No production assessments or customer reports exist under contract 1.0.0" in content
