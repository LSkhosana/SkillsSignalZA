"""Package H explicit evidence-rule registry tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Any

import pytest

from app.engine.configuration import (
    EVIDENCE_RULES_V1_PATH,
    load_evidence_rules_v1,
    load_json,
)
from app.engine.evidence.matching import KIND_SKILL, KIND_TOOL, load_compiled_registry

APPROVED_EVIDENCE_RULES_SHA256 = "cbdadd6ee1f73caf65679faf316c8a12ef75b2be6cf4af48e21186d5ca5a7a6d"
EXPECTED_SKILL_SUBJECTS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "csharp",
    "php",
    "r",
    "sql",
    "html",
    "css",
    "object_oriented_programming",
    "data_structures",
    "algorithms",
    "control_flow",
    "api",
    "rest_api",
    "http",
    "relational_database",
    "database_schema",
    "database_normalization",
    "database_joins",
    "debugging",
    "unit_testing",
    "integration_testing",
    "automated_testing",
    "data_analysis",
    "data_cleaning",
    "data_transformation",
    "statistics",
    "data_visualization",
    "data_modelling",
    "reporting",
    "dashboarding",
}
EXPECTED_TOOL_SUBJECTS = {
    "dotnet",
    "aspnet",
    "react",
    "angular",
    "vue",
    "nodejs",
    "express",
    "spring",
    "django",
    "flask",
    "fastapi",
    "postgresql",
    "mysql",
    "sqlite",
    "sql_server",
    "mongodb",
    "supabase",
    "git",
    "github",
    "gitlab",
    "bitbucket",
    "docker",
    "kubernetes",
    "azure",
    "aws",
    "gcp",
    "excel",
    "google_sheets",
    "power_bi",
    "tableau",
    "looker_studio",
    "power_query",
    "dax",
    "pandas",
    "numpy",
    "pytest",
    "jest",
    "vitest",
    "playwright",
    "cypress",
}
EXPECTED_QUALIFICATION_SUBJECTS = {
    "bachelor_degree",
    "diploma",
    "higher_certificate",
    "certificate",
    "bootcamp",
    "nqf",
}


@pytest.fixture(scope="module")
def registry() -> dict[str, Any]:
    return load_evidence_rules_v1()


def test_registry_is_packaged_and_loads() -> None:
    packaged = files("app.engine.configuration").joinpath("evidence_rules_v1.json")
    assert packaged.is_file()
    document = load_json(EVIDENCE_RULES_V1_PATH)
    assert document == load_evidence_rules_v1()
    assert document["normalizer_version"] == "normalize.evidence.v1"
    assert document["contract_version"] == "1.2.0"


def test_registry_subjects_and_aliases_are_exact(registry: Mapping[str, Any]) -> None:
    skills = {item["subject"] for item in registry["subjects"] if item["kind"] == KIND_SKILL}
    tools = {item["subject"] for item in registry["subjects"] if item["kind"] == KIND_TOOL}
    qualifications = {item["subject"] for item in registry["qualifications"]}
    assert skills == EXPECTED_SKILL_SUBJECTS
    assert tools == EXPECTED_TOOL_SUBJECTS
    assert qualifications == EXPECTED_QUALIFICATION_SUBJECTS
    assert len(registry["subjects"]) == 73
    assert len(registry["qualifications"]) == 6


def test_registry_has_no_alias_collisions(registry: Mapping[str, Any]) -> None:
    owners: dict[str, str] = {}
    alias_count = 0
    for entry in (*registry["subjects"], *registry["qualifications"]):
        assert entry["rule_id"] == f"normalize.v1.{entry['kind']}.{entry['subject']}"
        for alias in entry["aliases"]:
            alias_count += 1
            key = alias["text"] if alias["case_sensitive"] else alias["text"].casefold()
            owner = owners.get(key)
            assert owner is None or owner == entry["subject"]
            owners[key] = entry["subject"]
    assert alias_count == 130
    load_compiled_registry(dict(registry))


def test_approved_evidence_rules_canonical_hash_is_locked(registry: Mapping[str, Any]) -> None:
    assert _canonical_sha256(registry) == APPROVED_EVIDENCE_RULES_SHA256


def test_load_evidence_rules_v1_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engine.configuration.load_json", lambda path: ["not-an-object"])
    with pytest.raises(TypeError, match="JSON object"):
        load_evidence_rules_v1()


def test_compiled_registry_rejects_alias_collision() -> None:
    document = load_evidence_rules_v1()
    document["subjects"][0]["aliases"].append({"text": "Java", "case_sensitive": False})
    with pytest.raises(ValueError, match="invalid evidence rules"):
        load_compiled_registry(document)


def test_compiled_registry_rejects_invalid_structure() -> None:
    with pytest.raises(ValueError, match="invalid evidence rules"):
        load_compiled_registry({"normalizer_version": "nope", "action_cues": ["build"]})


def _canonical_sha256(document: Mapping[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
