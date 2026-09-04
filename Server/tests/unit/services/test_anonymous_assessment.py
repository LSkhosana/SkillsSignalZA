"""Package N anonymous assessment orchestration tests. No database or network."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import hmac
import json
from datetime import UTC
from pathlib import Path
from typing import Any

from app.engine.schema_registry import draft_validator
from app.repositories.records import (
    AssessmentRecord,
    AssessmentRunRecord,
    ClaimWriteResult,
    PersistenceBundle,
    PersistWriteResult,
)
from app.repositories.supabase import (
    MAX_FILE_SIZE_BYTES,
    DocumentStorageError,
    opaque_storage_path,
)
from app.services.anonymous_assessment import (
    ERROR_ASSESSMENT_PIPELINE_FAILED,
    ERROR_ASSESSMENT_SERVICE_UNAVAILABLE,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_SUBMISSION,
    ERROR_PERSISTENCE_FAILED,
    ERROR_REPORTING_FAILED,
    ERROR_STORAGE_FAILED,
    ERROR_TOO_MANY_LINKS,
    ERROR_UNSUPPORTED_MEDIA_TYPE,
    SCHEMA_VERSION,
    AssessmentIdentity,
    hash_claim_token,
    submit_anonymous_assessment,
)
from tests.fixtures.cv_extraction.documents import build_text_docx, build_text_pdf
from tests.unit.services.test_assessment_pipeline import (
    ASSESSED_AT,
    _accessible_retrieve,
    _blocked_retrieve,
    _failed_retrieve,
)

SERVICE_PATH = Path(__file__).resolve().parents[3] / "app" / "services" / "anonymous_assessment.py"
IDENTITY = AssessmentIdentity(
    assessment_id="a-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    run_id="r-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    document_id="d-cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    candidate_ref="c-dddddddd-dddd-4ddd-8ddd-dddddddddddd",
)
RAW_CLAIM = "unit-test-claim-token-not-for-storage-at-all"
SE_LINES = [
    "Summary",
    "Seeking a junior software engineer role",
    "Skills",
    "Experience",
    "Projects",
    "Education",
    "Built a Flask API in Python to solve a workflow problem",
]
DA_LINES = [
    "Summary",
    "Seeking a junior data analyst role",
    "Skills",
    "Experience",
    "Education",
    "Used SQL to analyse the sales dataset",
]
PAID_KEYS = {
    "category_breakdown",
    "strengths",
    "material_gaps",
    "priority_actions",
    "project_recommendation",
    "criterion_breakdown",
    "cap_detail",
    "explicit_text",
    "evidence_facts",
    "evidence_ids",
    "source_records",
    "scoring_context",
    "storage_path",
    "assessment_result",
}


def _hashes_match(stored: str, presented: str) -> bool:
    stored_bytes = stored.encode("utf-8")
    presented_bytes = presented.encode("utf-8")
    if len(stored_bytes) != len(presented_bytes):
        return False
    return hmac.compare_digest(stored_bytes, presented_bytes)


class RecordingRepository:
    def __init__(self) -> None:
        self.bundles: list[PersistenceBundle] = []
        self.assessments: dict[str, AssessmentRecord] = {}
        self.runs: dict[str, AssessmentRunRecord] = {}
        self.persist_error: Exception | None = None
        self.persist_result: PersistWriteResult | None = None
        self.get_assessment_error: Exception | None = None
        self.store_on_persist = True
        self.claim_error: Exception | None = None
        self.claim_calls: list[dict[str, Any]] = []

    async def persist_bundle(self, bundle: PersistenceBundle) -> PersistWriteResult:
        if self.persist_error is not None:
            if self.store_on_persist:
                self._store(bundle)
            raise self.persist_error
        if self.store_on_persist:
            self._store(bundle)
        self.bundles.append(bundle)
        if self.persist_result is not None:
            return self.persist_result
        return PersistWriteResult(
            "inserted", bundle.assessment_id, bundle.run_id, latest_run_id=bundle.run_id
        )

    async def get_assessment(self, assessment_id: str) -> AssessmentRecord | None:
        if self.get_assessment_error is not None:
            raise self.get_assessment_error
        return self.assessments.get(assessment_id)

    async def get_run(self, run_id: str) -> AssessmentRunRecord | None:
        return self.runs.get(run_id)

    async def get_latest_run(self, assessment_id: str) -> AssessmentRunRecord | None:
        record = self.assessments.get(assessment_id)
        if record is None or record.latest_run_id is None:
            return None
        return self.runs.get(record.latest_run_id)

    async def claim_assessment(
        self,
        *,
        assessment_id: str,
        authenticated_user_id: str,
        presented_claim_token_hash: str,
        claimed_at: Any,
    ) -> ClaimWriteResult:
        self.claim_calls.append(
            {
                "assessment_id": assessment_id,
                "authenticated_user_id": authenticated_user_id,
                "presented_claim_token_hash": presented_claim_token_hash,
            }
        )
        if self.claim_error is not None:
            raise self.claim_error
        record = self.assessments.get(assessment_id)
        if record is None:
            return ClaimWriteResult("not_found", assessment_id)
        if record.owner_user_id is not None:
            if record.owner_user_id == authenticated_user_id:
                return ClaimWriteResult(
                    "idempotent",
                    assessment_id,
                    claimed_at=record.claimed_at,
                    access_state=record.access_state,
                )
            return ClaimWriteResult(
                "conflict",
                assessment_id,
                claimed_at=record.claimed_at,
                access_state=record.access_state,
            )
        stored = record.claim_token_hash
        if stored is None or not _hashes_match(stored, presented_claim_token_hash):
            return ClaimWriteResult("token_invalid", assessment_id)
        if record.expires_at is not None:
            expiry = (
                record.expires_at
                if record.expires_at.tzinfo is not None
                else record.expires_at.replace(tzinfo=UTC)
            )
            instant = (
                claimed_at if claimed_at.tzinfo is not None else claimed_at.replace(tzinfo=UTC)
            )
            if expiry <= instant:
                return ClaimWriteResult("expired", assessment_id)
        self.assessments[assessment_id] = AssessmentRecord(
            assessment_id=record.assessment_id,
            candidate_ref=record.candidate_ref,
            track=record.track,
            access_state=record.access_state,
            claim_token_hash=None,
            claimed_at=claimed_at,
            latest_run_id=record.latest_run_id,
            expires_at=record.expires_at,
            created_at=record.created_at,
            updated_at=claimed_at,
            owner_user_id=authenticated_user_id,
        )
        return ClaimWriteResult(
            "claimed",
            assessment_id,
            claimed_at=claimed_at,
            access_state=record.access_state,
        )

    def _store(self, bundle: PersistenceBundle) -> None:
        outcome = bundle.pipeline_outcome
        self.assessments[bundle.assessment_id] = AssessmentRecord(
            assessment_id=bundle.assessment_id,
            candidate_ref=bundle.candidate_ref,
            track=bundle.track,
            access_state="PREVIEW",
            claim_token_hash=bundle.claim_token_hash,
            claimed_at=None,
            latest_run_id=bundle.run_id,
            expires_at=bundle.expires_at,
            created_at=bundle.assessed_at,
            updated_at=bundle.assessed_at,
        )
        error_code = outcome.get("error_code")
        scoring_context = outcome.get("scoring_context")
        assessment_result = outcome.get("assessment_result")
        self.runs[bundle.run_id] = AssessmentRunRecord(
            run_id=bundle.run_id,
            assessment_id=bundle.assessment_id,
            state=str(outcome.get("state")),
            error_code=error_code if isinstance(error_code, str) else None,
            pipeline_version=str(outcome.get("pipeline_version") or "assessment.pipeline.v1"),
            contract_version=str(outcome.get("contract_version") or "1.2.0"),
            rubric_version=str(outcome.get("rubric_version") or "V2"),
            track=bundle.track,
            assessment_input=bundle.assessment_input,
            scoring_context=scoring_context if isinstance(scoring_context, dict) else None,
            assessment_result=assessment_result if isinstance(assessment_result, dict) else None,
            review_flags=list(outcome.get("review_flags") or []),
            stages=list(outcome.get("stages") or []),
            assessed_at=bundle.assessed_at,
            created_at=bundle.assessed_at,
            source_records=list(outcome.get("source_records") or []),
            evidence_facts=list(outcome.get("evidence_facts") or []),
            document=bundle.document,
        )


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []
        self.deletes: list[str] = []
        self.fail_put = False
        self.fail_delete = False
        self.mismatch_sha = False

    async def put_private_document(
        self,
        *,
        assessment_id: str,
        document_id: str,
        file_bytes: bytes,
        media_type: str,
        original_filename: str,
    ) -> dict[str, Any]:
        if self.fail_put:
            raise DocumentStorageError("STORAGE_PUT_FAILED")
        path = opaque_storage_path(assessment_id, document_id, media_type)
        digest = hashlib.sha256(file_bytes).hexdigest()
        if self.mismatch_sha:
            digest = "ab" * 32
        metadata = {
            "document_id": document_id,
            "storage_path": path,
            "original_filename": original_filename,
            "media_type": media_type,
            "sha256": digest,
            "byte_size": len(file_bytes),
            "file_bytes": file_bytes,
        }
        self.puts.append(metadata)
        return {key: value for key, value in metadata.items() if key != "file_bytes"}

    async def get_private_document(self, storage_path: str) -> bytes:
        raise DocumentStorageError("STORAGE_GET_FAILED")

    async def delete_private_document(self, storage_path: str) -> None:
        self.deletes.append(storage_path)
        if self.fail_delete:
            raise DocumentStorageError("STORAGE_DELETE_FAILED")


class PipelineSpy:
    def __init__(self, outcome: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.outcome = outcome

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.outcome is None:
            raise AssertionError("pipeline must not run")
        return self.outcome


def se_pdf() -> bytes:
    return build_text_pdf([SE_LINES])


def da_docx() -> bytes:
    return build_text_docx(paragraphs=DA_LINES)


def _submit(**overrides: Any) -> dict[str, Any]:
    payload = {
        "track": "software_engineering",
        "cv_file_bytes": se_pdf(),
        "original_filename": "cv.pdf",
        "media_type": "application/pdf",
        "links": [],
        "repository": RecordingRepository(),
        "storage": FakeStorage(),
        "assessed_at": ASSESSED_AT,
        "identity_factory": lambda: IDENTITY,
        "claim_token_factory": lambda: RAW_CLAIM,
        "retrieve_link": _blocked_retrieve,
    }
    payload.update(overrides)
    return asyncio.run(submit_anonymous_assessment(**payload))


def _paid_keys(payload: object) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in PAID_KEYS:
                found.add(key)
            if key == "schema_version" and value == "readiness.report.v1":
                found.add("readiness.report.v1")
            found.update(_paid_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            found.update(_paid_keys(item))
    return found


def test_completed_se_pdf_returns_persisted_preview() -> None:
    repository = RecordingRepository()
    storage = FakeStorage()
    file_bytes = se_pdf()
    outcome = _submit(repository=repository, storage=storage, cv_file_bytes=file_bytes)
    draft_validator("anonymous_assessment_response.schema.json").validate(outcome)
    assert outcome["schema_version"] == SCHEMA_VERSION
    assert outcome["state"] == "COMPLETED"
    assert outcome["assessment_id"] == IDENTITY.assessment_id
    assert outcome["run_id"] == IDENTITY.run_id
    assert outcome["access_state"] == "PREVIEW"
    assert outcome["claim_token"] == RAW_CLAIM
    assert outcome["error_code"] is None
    draft_validator("readiness_preview.schema.json").validate(outcome["preview"])
    assert outcome["preview"]["schema_version"] == "readiness.preview.v1"
    assert len(storage.puts) == 1
    assert len(repository.bundles) == 1
    assert _paid_keys(outcome) == set()


def test_completed_da_docx_returns_persisted_preview() -> None:
    file_bytes = da_docx()
    outcome = _submit(
        track="data_analytics",
        cv_file_bytes=file_bytes,
        original_filename="cv.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert outcome["state"] == "COMPLETED"
    assert outcome["preview"]["track"] == "data_analytics"
    draft_validator("readiness_preview.schema.json").validate(outcome["preview"])


def test_exact_cv_bytes_and_hash_cross_k_storage_and_persistence() -> None:
    repository = RecordingRepository()
    storage = FakeStorage()
    file_bytes = se_pdf()
    digest = hashlib.sha256(file_bytes).hexdigest()
    captured: dict[str, Any] = {}

    def spy_pipeline(**kwargs: Any) -> dict[str, Any]:
        captured["pipeline"] = kwargs
        from app.services.assessment_pipeline import run_assessment_pipeline

        return run_assessment_pipeline(**kwargs)

    outcome = _submit(
        repository=repository,
        storage=storage,
        cv_file_bytes=file_bytes,
        run_pipeline=spy_pipeline,
    )
    assert outcome["state"] == "COMPLETED"
    assert captured["pipeline"]["cv_file_bytes"] == file_bytes
    assert captured["pipeline"]["assessment_input"]["cv"]["sha256"] == digest
    assert storage.puts[0]["file_bytes"] == file_bytes
    assert storage.puts[0]["sha256"] == digest
    bundle = repository.bundles[0]
    assert bundle.document.sha256 == digest
    assert bundle.document.byte_size == len(file_bytes)
    assert bundle.assessment_input["cv"]["sha256"] == digest


def test_raw_claim_token_returned_once_and_only_hash_is_stored() -> None:
    repository = RecordingRepository()
    outcome = _submit(repository=repository)
    assert outcome["claim_token"] == RAW_CLAIM
    bundle = repository.bundles[0]
    expected_hash = hash_claim_token(RAW_CLAIM)
    assert bundle.claim_token_hash == expected_hash
    assert RAW_CLAIM not in json.dumps(bundle.assessment_input)
    assert bundle.claim_token_hash != RAW_CLAIM
    assert repository.assessments[IDENTITY.assessment_id].claim_token_hash == expected_hash
    assert RAW_CLAIM not in str(repository.assessments[IDENTITY.assessment_id])
    assert bundle.expires_at is None


def test_client_cannot_inject_identity_or_scoring_fields() -> None:
    repository = RecordingRepository()
    outcome = _submit(repository=repository)
    bundle = repository.bundles[0]
    assert bundle.assessment_id == IDENTITY.assessment_id
    assert bundle.assessment_input["candidate_ref"] == IDENTITY.candidate_ref
    assert bundle.assessment_input["contract_version"] == "1.2.0"
    assert bundle.assessment_input["rubric_version"] == "V2"
    assert bundle.assessment_input["cv"]["document_id"] == IDENTITY.document_id
    assert "scoring_context" not in bundle.assessment_input
    assert "evidence_facts" not in bundle.assessment_input
    assert outcome["assessment_id"] == IDENTITY.assessment_id


def test_links_receive_server_ids_and_preserve_url_and_type() -> None:
    repository = RecordingRepository()
    outcome = _submit(
        repository=repository,
        links=[
            {
                "submitted_url": "https://github.com/example/project",
                "declared_type": "repository",
            },
            {
                "submitted_url": "https://example.com/portfolio",
                "declared_type": "portfolio",
            },
        ],
        retrieve_link=_failed_retrieve,
    )
    assert outcome["state"] == "COMPLETED"
    stored_links = repository.bundles[0].assessment_input["links"]
    assert stored_links == [
        {
            "link_id": "link-001",
            "submitted_url": "https://github.com/example/project",
            "declared_type": "repository",
        },
        {
            "link_id": "link-002",
            "submitted_url": "https://example.com/portfolio",
            "declared_type": "portfolio",
        },
    ]


def test_more_than_five_links_rejected_before_pipeline_and_storage() -> None:
    storage = FakeStorage()
    spy = PipelineSpy()
    links = [
        {"submitted_url": f"https://example.com/{index}", "declared_type": "project"}
        for index in range(6)
    ]
    outcome = _submit(storage=storage, links=links, run_pipeline=spy)
    assert outcome["state"] == "FAILED"
    assert outcome["error_code"] == ERROR_TOO_MANY_LINKS
    assert outcome["claim_token"] is None
    assert spy.calls == []
    assert storage.puts == []


def test_unknown_link_fields_are_rejected() -> None:
    spy = PipelineSpy()
    outcome = _submit(
        links=[
            {
                "submitted_url": "https://example.com/project",
                "declared_type": "project",
                "link_id": "client-link",
            }
        ],
        run_pipeline=spy,
    )
    assert outcome["error_code"] == ERROR_INVALID_SUBMISSION
    assert spy.calls == []


def test_unsupported_media_type_rejected_before_pipeline() -> None:
    storage = FakeStorage()
    spy = PipelineSpy()
    outcome = _submit(media_type="text/plain", storage=storage, run_pipeline=spy)
    assert outcome["error_code"] == ERROR_UNSUPPORTED_MEDIA_TYPE
    assert spy.calls == []
    assert storage.puts == []


def test_file_over_limit_rejected_before_pipeline_and_storage() -> None:
    storage = FakeStorage()
    spy = PipelineSpy()
    outcome = _submit(
        cv_file_bytes=b"a" * (MAX_FILE_SIZE_BYTES + 1),
        storage=storage,
        run_pipeline=spy,
    )
    assert outcome["error_code"] == ERROR_FILE_TOO_LARGE
    assert spy.calls == []
    assert storage.puts == []


def test_invalid_track_is_rejected() -> None:
    spy = PipelineSpy()
    outcome = _submit(track="product_management", run_pipeline=spy)
    assert outcome["error_code"] == ERROR_INVALID_SUBMISSION
    assert spy.calls == []


def test_review_required_is_persisted_without_preview() -> None:
    repository = RecordingRepository()
    storage = FakeStorage()
    outcome = _submit(
        repository=repository,
        storage=storage,
        links=[
            {
                "submitted_url": "https://example.com/project",
                "declared_type": "project",
            }
        ],
        retrieve_link=_accessible_retrieve,
    )
    assert outcome["state"] == "REVIEW_REQUIRED"
    assert outcome["preview"] is None
    assert outcome["claim_token"] == RAW_CLAIM
    assert outcome["access_state"] == "PREVIEW"
    assert len(storage.puts) == 1
    assert len(repository.bundles) == 1
    assert _paid_keys(outcome) == set()


def test_not_scorable_is_persisted_without_preview() -> None:
    repository = RecordingRepository()
    storage = FakeStorage()
    outcome = _submit(
        repository=repository,
        storage=storage,
        cv_file_bytes=b"%PDF-1.4 broken",
    )
    assert outcome["state"] == "NOT_SCORABLE"
    assert outcome["preview"] is None
    assert outcome["claim_token"] == RAW_CLAIM
    assert outcome["error_code"] == "CV_UNREADABLE"
    assert len(storage.puts) == 1
    assert len(repository.bundles) == 1


def test_non_persistable_pipeline_failure_does_not_upload_or_persist() -> None:
    repository = RecordingRepository()
    storage = FakeStorage()
    spy = PipelineSpy(
        {
            "state": "ASSESSMENT_PIPELINE_FAILED",
            "error_code": "ORCHESTRATION_EXCEPTION",
            "assessment_id": IDENTITY.assessment_id,
            "run_id": IDENTITY.run_id,
        }
    )
    outcome = _submit(repository=repository, storage=storage, run_pipeline=spy)
    assert outcome["state"] == "FAILED"
    assert outcome["error_code"] == ERROR_ASSESSMENT_PIPELINE_FAILED
    assert outcome["claim_token"] is None
    assert storage.puts == []
    assert repository.bundles == []


def test_storage_failure_does_not_persist() -> None:
    repository = RecordingRepository()
    storage = FakeStorage()
    storage.fail_put = True
    outcome = _submit(repository=repository, storage=storage)
    assert outcome["error_code"] == ERROR_STORAGE_FAILED
    assert outcome["claim_token"] is None
    assert repository.bundles == []
    assert storage.deletes == []


def test_persistence_failure_without_row_deletes_uploaded_object() -> None:
    repository = RecordingRepository()
    repository.persist_error = RuntimeError("write failed")
    repository.store_on_persist = False
    storage = FakeStorage()
    outcome = _submit(repository=repository, storage=storage)
    assert outcome["error_code"] == ERROR_PERSISTENCE_FAILED
    assert outcome["claim_token"] is None
    assert len(storage.puts) == 1
    assert storage.deletes == [storage.puts[0]["storage_path"]]


def test_ambiguous_database_failure_does_not_delete_storage() -> None:
    repository = RecordingRepository()
    repository.persist_error = RuntimeError("write failed")
    repository.store_on_persist = False
    repository.get_assessment_error = RuntimeError("query failed")
    storage = FakeStorage()
    outcome = _submit(repository=repository, storage=storage)
    assert outcome["error_code"] == ERROR_PERSISTENCE_FAILED
    assert storage.deletes == []
    assert outcome["claim_token"] is None


def test_reporting_failure_never_exposes_full_report() -> None:
    repository = RecordingRepository()

    async def fail_report(*, assessment_id: str, repository: RecordingRepository) -> dict[str, Any]:
        return {
            "state": "FAILED",
            "error_code": "REPORT_BUILD_FAILED",
            "preview": None,
            "report": {"schema_version": "readiness.report.v1", "category_breakdown": []},
        }

    outcome = _submit(repository=repository, load_report=fail_report)
    assert outcome["state"] == "FAILED"
    assert outcome["error_code"] == ERROR_REPORTING_FAILED
    assert outcome["preview"] is None
    assert outcome["claim_token"] == RAW_CLAIM
    serialized = json.dumps(outcome)
    assert "readiness.report.v1" not in serialized
    assert "category_breakdown" not in serialized
    assert _paid_keys(outcome) == set()
    assert len(repository.bundles) == 1


def test_storage_metadata_mismatch_deletes_object_and_does_not_persist() -> None:
    repository = RecordingRepository()
    storage = FakeStorage()
    storage.mismatch_sha = True
    outcome = _submit(repository=repository, storage=storage)
    assert outcome["error_code"] == ERROR_STORAGE_FAILED
    assert repository.bundles == []
    assert storage.deletes == [storage.puts[0]["storage_path"]]


def test_empty_cv_is_invalid_submission() -> None:
    spy = PipelineSpy()
    outcome = _submit(cv_file_bytes=b"", run_pipeline=spy)
    assert outcome["error_code"] == ERROR_INVALID_SUBMISSION
    assert spy.calls == []


def test_service_unavailable_helper_validates() -> None:
    from app.services.anonymous_assessment import anonymous_service_unavailable

    payload = anonymous_service_unavailable()
    assert payload["error_code"] == ERROR_ASSESSMENT_SERVICE_UNAVAILABLE
    draft_validator("anonymous_assessment_response.schema.json").validate(payload)


def test_module_does_not_call_score_assessment_or_log_claim_token() -> None:
    text = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "app.engine.scoring" not in imported
    assert "from app.engine.scoring" not in text
    assert "psycopg" not in imported
    assert "httpx" not in imported
    for line in text.splitlines():
        if "logger." in line:
            assert "claim_token" not in line
    assert "expires_at=None" in text
    assert "run_assessment_pipeline" in text
    assert "persist_assessment_outcome_async" in text
    assert "get_readiness_report_async" in text


def test_default_identity_and_claim_token_are_opaque_and_hashed() -> None:
    from app.services.anonymous_assessment import (
        default_claim_token_factory,
        default_identity_factory,
        utc_timestamp,
    )

    identity = default_identity_factory()
    token = default_claim_token_factory()
    stamp = utc_timestamp()
    assert identity.assessment_id.startswith("a-")
    assert identity.candidate_ref.startswith("c-")
    assert identity.assessment_id != identity.candidate_ref
    assert len(token) >= 32
    assert hash_claim_token(token) != token
    assert stamp.endswith("Z") and "T" in stamp


def test_generic_storage_exception_is_storage_failed() -> None:
    class BoomStorage(FakeStorage):
        async def put_private_document(self, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("disk exploded")

    repository = RecordingRepository()
    outcome = _submit(repository=repository, storage=BoomStorage())
    assert outcome["error_code"] == ERROR_STORAGE_FAILED
    assert repository.bundles == []


def test_reporting_exception_is_reporting_failed_after_persist() -> None:
    repository = RecordingRepository()

    async def boom(*, assessment_id: str, repository: RecordingRepository) -> dict[str, Any]:
        raise RuntimeError("report exploded")

    outcome = _submit(repository=repository, load_report=boom)
    assert outcome["error_code"] == ERROR_REPORTING_FAILED
    assert outcome["claim_token"] == RAW_CLAIM
    assert len(repository.bundles) == 1


def test_persistence_failure_with_existing_row_does_not_delete() -> None:
    repository = RecordingRepository()
    repository.persist_error = RuntimeError("write failed after commit")
    repository.store_on_persist = True
    storage = FakeStorage()
    outcome = _submit(repository=repository, storage=storage)
    assert outcome["error_code"] == ERROR_PERSISTENCE_FAILED
    assert storage.deletes == []


def test_invalid_link_shapes_are_rejected() -> None:
    spy = PipelineSpy()
    assert _submit(links=["https://example.com"], run_pipeline=spy)["error_code"] == (
        ERROR_INVALID_SUBMISSION
    )
    assert (
        _submit(
            links=[{"submitted_url": "", "declared_type": "project"}],
            run_pipeline=spy,
        )["error_code"]
        == ERROR_INVALID_SUBMISSION
    )
    assert (
        _submit(
            links=[{"submitted_url": "https://example.com", "declared_type": "blog"}],
            run_pipeline=spy,
        )["error_code"]
        == ERROR_INVALID_SUBMISSION
    )
    assert spy.calls == []


def test_missing_filename_and_none_links_still_complete() -> None:
    outcome = _submit(original_filename="  ", links=None)
    assert outcome["state"] == "COMPLETED"
    assert outcome["preview"]["schema_version"] == "readiness.preview.v1"


def test_cleanup_failure_stays_safe() -> None:
    repository = RecordingRepository()
    repository.persist_error = RuntimeError("write failed")
    repository.store_on_persist = False
    storage = FakeStorage()
    storage.fail_delete = True
    outcome = _submit(repository=repository, storage=storage)
    assert outcome["error_code"] == ERROR_PERSISTENCE_FAILED
    assert "RuntimeError" not in json.dumps(outcome)
    assert storage.deletes == [storage.puts[0]["storage_path"]]
