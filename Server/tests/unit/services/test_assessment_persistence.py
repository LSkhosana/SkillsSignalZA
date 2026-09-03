"""Package L persistence service tests. No database or network."""

from __future__ import annotations

import ast
import asyncio
import hashlib
from pathlib import Path
from typing import Any

from app.repositories.records import PersistenceBundle, PersistWriteResult
from app.repositories.supabase import opaque_storage_path
from app.services.assessment_persistence import (
    persist_assessment_outcome,
    persist_assessment_outcome_async,
)
from tests.unit.services.test_assessment_pipeline import ASSESSED_AT, _input, _pdf, _run

PERSISTENCE_PATH = (
    Path(__file__).resolve().parents[3] / "app" / "services" / "assessment_persistence.py"
)
RAW_CLAIM = "raw-preview-claim-token-do-not-store"


class MemoryRepository:
    def __init__(self, result: PersistWriteResult | None = None) -> None:
        self.bundles: list[PersistenceBundle] = []
        self.result = result

    async def persist_bundle(self, bundle: PersistenceBundle) -> PersistWriteResult:
        self.bundles.append(bundle)
        if self.result is not None:
            return self.result
        return PersistWriteResult(
            "inserted", bundle.assessment_id, bundle.run_id, latest_run_id=bundle.run_id
        )

    async def get_assessment(self, assessment_id: str) -> None:
        return None

    async def get_run(self, run_id: str) -> None:
        return None

    async def get_latest_run(self, assessment_id: str) -> None:
        return None


def _document(
    assessment_id: str, assessment_input: dict[str, Any], byte_size: int
) -> dict[str, Any]:
    cv = assessment_input["cv"]
    return {
        "document_id": cv["document_id"],
        "storage_path": opaque_storage_path(assessment_id, cv["document_id"], cv["media_type"]),
        "original_filename": cv["original_filename"],
        "media_type": cv["media_type"],
        "sha256": str(cv["sha256"]).lower(),
        "byte_size": byte_size,
    }


def _persist(outcome: dict[str, Any], file_bytes: bytes, **overrides: Any) -> dict[str, Any]:
    assessment_input = overrides.pop("assessment_input", None) or _input(
        outcome["track"], file_bytes
    )
    document = overrides.pop("document_metadata", None) or _document(
        outcome["assessment_id"], assessment_input, len(file_bytes)
    )
    repository = overrides.pop("repository", MemoryRepository())
    return asyncio.run(
        persist_assessment_outcome_async(
            assessment_input=assessment_input,
            pipeline_outcome=outcome,
            document_metadata=document,
            assessed_at=overrides.pop("assessed_at", ASSESSED_AT),
            repository=repository,
            **overrides,
        )
    )


def test_persist_completed_se_and_da_outcomes() -> None:
    se_bytes = _pdf(
        [
            "Summary",
            "Seeking a junior software engineer role",
            "Skills",
            "Experience",
            "Projects",
            "Education",
            "Built a Flask API in Python to solve a workflow problem",
        ]
    )
    se = _run(
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
    se_repo = MemoryRepository()
    se_result = _persist(se, se_bytes, repository=se_repo)
    assert se_result["state"] == "PERSISTED"
    assert se_result["error_code"] is None
    assert se_result["access_state"] == "PREVIEW"
    assert se_repo.bundles[0].claim_token_hash is None
    sync_result = persist_assessment_outcome(
        assessment_input=_input("software_engineering", se_bytes),
        pipeline_outcome=se,
        document_metadata=_document(
            se["assessment_id"], _input("software_engineering", se_bytes), len(se_bytes)
        ),
        assessed_at=ASSESSED_AT,
        repository=MemoryRepository(),
    )
    assert sync_result["state"] == "PERSISTED"
    da_bytes = _pdf(
        [
            "Summary",
            "Seeking a junior data analyst role",
            "Skills",
            "Experience",
            "Education",
            "Used SQL to analyse the sales dataset",
        ]
    )
    da = _run(
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
    da_result = _persist(da, da_bytes)
    assert da_result["state"] == "PERSISTED"


def test_validation_failures_are_safe() -> None:
    file_bytes = _pdf(["Junior Software Engineer"])
    outcome = _run("software_engineering", ["Junior Software Engineer"])
    empty = asyncio.run(
        persist_assessment_outcome_async(
            assessment_input={},
            pipeline_outcome=outcome,
            document_metadata=_document(
                outcome["assessment_id"], _input(outcome["track"], file_bytes), 1
            ),
            assessed_at=ASSESSED_AT,
            repository=MemoryRepository(),
        )
    )
    assert empty["error_code"] == "INVALID_ASSESSMENT_INPUT"
    mismatched = _persist(
        outcome,
        file_bytes,
        assessment_input=_input("data_analytics", file_bytes),
    )
    assert mismatched["error_code"] == "IDENTITY_MISMATCH"
    failed = dict(outcome)
    failed["state"] = "ASSESSMENT_PIPELINE_FAILED"
    failed["error_code"] = "ORCHESTRATION_EXCEPTION"
    failed["assessment_result"] = None
    failed["scoring_context"] = None
    failed_result = _persist(failed, file_bytes)
    assert failed_result["error_code"] == "UNSUPPORTED_PIPELINE_STATE"
    raw_claim = _persist(outcome, file_bytes, claim_token_hash=RAW_CLAIM)
    assert raw_claim["error_code"] == "INVALID_CLAIM_TOKEN_HASH"
    wrong_hash = _document(
        outcome["assessment_id"], _input(outcome["track"], file_bytes), len(file_bytes)
    )
    wrong_hash["sha256"] = "0" * 64
    hash_mismatch = _persist(outcome, file_bytes, document_metadata=wrong_hash)
    assert hash_mismatch["error_code"] == "DOCUMENT_MISMATCH"
    bad_time = _persist(outcome, file_bytes, assessed_at="yesterday")
    assert bad_time["error_code"] == "INVALID_ASSESSMENT_INPUT"
    zero = _document(outcome["assessment_id"], _input(outcome["track"], file_bytes), 0)
    zero_size = _persist(outcome, file_bytes, document_metadata=zero)
    assert zero_size["error_code"] == "DOCUMENT_MISMATCH"


def test_claim_hash_is_accepted_and_raw_token_never_written() -> None:
    file_bytes = _pdf(["Junior Software Engineer"])
    outcome = _run("software_engineering", ["Junior Software Engineer"])
    digest = hashlib.sha256(b"high-entropy-token").hexdigest()
    repo = MemoryRepository()
    result = _persist(outcome, file_bytes, repository=repo, claim_token_hash=digest)
    assert result["state"] == "PERSISTED"
    assert repo.bundles[0].claim_token_hash == digest
    assert RAW_CLAIM not in str(repo.bundles[0])


def test_conflict_outcome_does_not_rerun_scoring() -> None:
    file_bytes = _pdf(["Junior Software Engineer"])
    outcome = _run("software_engineering", ["Junior Software Engineer"])
    repo = MemoryRepository(
        PersistWriteResult("conflict", outcome["assessment_id"], outcome["run_id"])
    )
    result = _persist(outcome, file_bytes, repository=repo)
    assert result["state"] == "PERSISTENCE_CONFLICT"
    assert result["error_code"] == "PERSISTENCE_CONFLICT"


def test_persistence_module_does_not_call_engine_or_network() -> None:
    text = PERSISTENCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "app.engine.scoring" not in imported
    assert "app.services.assessment_pipeline" not in imported
    assert "psycopg" not in imported
    assert "httpx" not in imported
    assert "run_assessment_pipeline" not in text
    assert "score_assessment" not in text


def test_engine_and_pipeline_remain_storage_free() -> None:
    engine_root = Path(__file__).resolve().parents[3] / "app" / "engine"
    for path in engine_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "psycopg" not in text
        assert "app.repositories" not in text
        assert "DATABASE_URL" not in text
    pipeline = (
        Path(__file__).resolve().parents[3] / "app" / "services" / "assessment_pipeline.py"
    ).read_text(encoding="utf-8")
    scoring = (
        Path(__file__).resolve().parents[3] / "app" / "engine" / "scoring" / "engine.py"
    ).read_text(encoding="utf-8")
    assert "psycopg" not in pipeline
    assert "app.repositories" not in pipeline
    assert "psycopg" not in scoring
    assert "app.repositories" not in scoring
