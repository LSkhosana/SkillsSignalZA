"""Package Q unlocked-report delivery service tests. Fakes only; no network."""

from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.reporting.outcomes import REPORT_SCHEMA_VERSION
from app.engine.schema_registry import draft_validator
from app.repositories.records import AssessmentRecord, AssessmentRunRecord
from app.services.assessment_report import (
    ERROR_ASSESSMENT_NOT_COMPLETED,
    ERROR_ASSESSMENT_NOT_FOUND,
    ERROR_ASSESSMENT_NOT_OWNED,
    ERROR_AUTH_INVALID,
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_LOCKED,
    ERROR_REPORT_SERVICE_UNAVAILABLE,
    SCHEMA_VERSION,
    deliver_unlocked_readiness_report,
    report_failed_outcome,
    report_http_status,
    report_service_unavailable,
)
from tests.unit.engine.test_readiness_report import _golden
from tests.unit.services.test_anonymous_assessment import IDENTITY, RecordingRepository

SERVICE_PATH = Path(__file__).resolve().parents[3] / "app" / "services" / "assessment_report.py"
ASSESSED_AT = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
USER_A = "user-verified-a"
USER_B = "user-verified-b"
FORBIDDEN = {
    "owner_user_id",
    "claim_token",
    "claim_token_hash",
    "category_breakdown",
    "strengths",
    "material_gaps",
    "priority_actions",
    "project_recommendation",
    "criterion_breakdown",
    "score_summary",
    "cap_detail",
    "explicit_text",
    "evidence_facts",
    "source_records",
    "scoring_context",
    "storage_path",
    "assessment_result",
    "email",
    "access_token",
    "preview",
}
WRITE_METHODS = (
    "persist_bundle",
    "claim_assessment",
    "begin_checkout_attempt",
    "mark_checkout_initialized",
    "mark_checkout_initialization_failed",
    "fulfill_payment_and_unlock",
)


class _WriteTrackingRepository(RecordingRepository):
    def __init__(self) -> None:
        super().__init__()
        self.write_names: list[str] = []
        for name in WRITE_METHODS:
            original = getattr(self, name)

            async def wrapped(
                *args: Any,
                _name: str = name,
                _original: Any = original,
                **kwargs: Any,
            ):
                self.write_names.append(_name)
                return await _original(*args, **kwargs)

            setattr(self, name, wrapped)


def _completed_result() -> dict[str, Any]:
    result = deepcopy(_golden("c01_se_full_score.json"))
    result["assessment_id"] = IDENTITY.assessment_id
    result["run_id"] = IDENTITY.run_id
    return result


def _run_record(
    result: dict[str, Any] | None,
    *,
    state: str = "COMPLETED",
    error_code: str | None = None,
) -> AssessmentRunRecord:
    return AssessmentRunRecord(
        run_id=IDENTITY.run_id,
        assessment_id=IDENTITY.assessment_id,
        state=state,
        error_code=error_code,
        pipeline_version="assessment.pipeline.v1",
        contract_version="1.2.0",
        rubric_version="V2",
        track="software_engineering",
        assessment_input={"track": "software_engineering"},
        scoring_context=None,
        assessment_result=result,
        review_flags=[],
        stages=["score"],
        assessed_at=ASSESSED_AT,
        created_at=ASSESSED_AT,
        source_records=[],
        evidence_facts=[],
        document=None,
    )


def _seed(
    repository: RecordingRepository,
    *,
    owner_user_id: str | None = USER_A,
    access_state: str = "UNLOCKED",
    result: dict[str, Any] | None = None,
    run: AssessmentRunRecord | None = None,
) -> None:
    repository.assessments[IDENTITY.assessment_id] = AssessmentRecord(
        assessment_id=IDENTITY.assessment_id,
        candidate_ref=IDENTITY.candidate_ref,
        track="software_engineering",
        access_state=access_state,  # type: ignore[arg-type]
        claim_token_hash=None,
        claimed_at=ASSESSED_AT,
        latest_run_id=IDENTITY.run_id,
        expires_at=None,
        created_at=ASSESSED_AT,
        updated_at=ASSESSED_AT,
        owner_user_id=owner_user_id,
    )
    repository.runs[IDENTITY.run_id] = run if run is not None else _run_record(result)


def _assert_safe_error(payload: dict[str, Any], error_code: str) -> None:
    draft_validator("assessment_report_error.schema.json").validate(payload)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["state"] == "FAILED"
    assert payload["error_code"] == error_code
    assert payload.get("schema_version") != REPORT_SCHEMA_VERSION
    for key in FORBIDDEN:
        assert key not in payload


def test_unlocked_owner_receives_canonical_report() -> None:
    repository = _WriteTrackingRepository()
    result = _completed_result()
    _seed(repository, result=result)
    outcome = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    draft_validator("readiness_report.schema.json").validate(outcome)
    assert outcome["schema_version"] == REPORT_SCHEMA_VERSION
    assert outcome["assessment_id"] == IDENTITY.assessment_id
    assert outcome["run_id"] == IDENTITY.run_id
    assert repository.write_names == []
    assert repository.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"
    assert report_http_status(outcome) == 200


def test_repeated_delivery_is_readonly_and_idempotent() -> None:
    repository = _WriteTrackingRepository()
    _seed(repository, result=_completed_result())
    first = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    second = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    assert first == second
    assert repository.write_names == []
    assert repository.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"
    assert repository.claim_calls == []
    assert repository.bundles == []
    assert repository.payments == {}


def test_missing_and_unowned_assessments_fail_closed() -> None:
    missing_repo = _WriteTrackingRepository()
    missing = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=missing_repo,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    _assert_safe_error(missing, ERROR_ASSESSMENT_NOT_FOUND)
    assert report_http_status(missing) == 404

    owned = _WriteTrackingRepository()
    _seed(owned, result=_completed_result())
    wrong = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=owned,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_B,
        )
    )
    _assert_safe_error(wrong, ERROR_ASSESSMENT_NOT_OWNED)
    assert report_http_status(wrong) == 403
    unclaimed = _WriteTrackingRepository()
    _seed(unclaimed, owner_user_id=None, result=_completed_result())
    denied = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=unclaimed,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    _assert_safe_error(denied, ERROR_ASSESSMENT_NOT_OWNED)


def test_preview_owner_is_locked_without_building_report() -> None:
    repository = _WriteTrackingRepository()
    _seed(repository, access_state="PREVIEW", result=_completed_result())
    calls: list[str] = []

    async def boom(**_kwargs: Any) -> dict[str, Any]:
        calls.append("load")
        raise AssertionError("locked assessments must not assemble a report")

    outcome = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            load_report=boom,
        )
    )
    _assert_safe_error(outcome, ERROR_REPORT_LOCKED)
    assert report_http_status(outcome) == 402
    assert calls == []
    assert repository.write_names == []
    assert repository.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"


def test_non_completed_run_is_409() -> None:
    repository = _WriteTrackingRepository()
    _seed(
        repository,
        run=_run_record(None, state="REVIEW_REQUIRED", error_code="REVIEW_REQUIRED"),
    )
    outcome = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    _assert_safe_error(outcome, ERROR_ASSESSMENT_NOT_COMPLETED)
    assert report_http_status(outcome) == 409
    assert repository.write_names == []


def test_missing_and_invalid_results_are_safe_build_failures() -> None:
    missing_repo = _WriteTrackingRepository()
    _seed(missing_repo, run=_run_record(None, state="COMPLETED"))
    missing = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=missing_repo,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    _assert_safe_error(missing, ERROR_REPORT_BUILD_FAILED)
    assert report_http_status(missing) == 500

    invalid = deepcopy(_completed_result())
    invalid.pop("criterion_results")
    invalid_repo = _WriteTrackingRepository()
    _seed(invalid_repo, result=invalid)
    invalid_outcome = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=invalid_repo,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    _assert_safe_error(invalid_outcome, ERROR_REPORT_BUILD_FAILED)


def test_package_m_failure_and_loader_exception_are_safe() -> None:
    repository = _WriteTrackingRepository()
    _seed(repository, result=_completed_result())

    async def failed(**_kwargs: Any) -> dict[str, Any]:
        return {
            "state": "FAILED",
            "error_code": "REPORT_BUILD_FAILED",
            "report": None,
            "preview": {"schema_version": "readiness.preview.v1"},
        }

    outcome = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            load_report=failed,
        )
    )
    _assert_safe_error(outcome, ERROR_REPORT_BUILD_FAILED)
    assert "preview" not in outcome

    async def boom(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("package m exploded")

    crashed = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            load_report=boom,
        )
    )
    _assert_safe_error(crashed, ERROR_REPORT_BUILD_FAILED)
    assert "package m exploded" not in str(crashed)

    async def not_mapping(**_kwargs: Any) -> dict[str, Any]:
        return "not-a-mapping"  # type: ignore[return-value]

    async def completed_invalid(**_kwargs: Any) -> dict[str, Any]:
        return {"state": "COMPLETED", "report": {"schema_version": REPORT_SCHEMA_VERSION}}

    async def completed_non_report(**_kwargs: Any) -> dict[str, Any]:
        return {"state": "COMPLETED", "report": {"schema_version": "readiness.preview.v1"}}

    async def raced_missing(**_kwargs: Any) -> dict[str, Any]:
        return {"state": "FAILED", "error_code": "ASSESSMENT_NOT_FOUND"}

    assert (
        asyncio.run(
            deliver_unlocked_readiness_report(
                repository=repository,
                assessment_id=IDENTITY.assessment_id,
                owner_user_id=USER_A,
                load_report=not_mapping,
            )
        )["error_code"]
        == ERROR_REPORT_BUILD_FAILED
    )
    assert (
        asyncio.run(
            deliver_unlocked_readiness_report(
                repository=repository,
                assessment_id=IDENTITY.assessment_id,
                owner_user_id=USER_A,
                load_report=completed_invalid,
            )
        )["error_code"]
        == ERROR_REPORT_BUILD_FAILED
    )
    assert (
        asyncio.run(
            deliver_unlocked_readiness_report(
                repository=repository,
                assessment_id=IDENTITY.assessment_id,
                owner_user_id=USER_A,
                load_report=completed_non_report,
            )
        )["error_code"]
        == ERROR_REPORT_BUILD_FAILED
    )
    missing = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            load_report=raced_missing,
        )
    )
    _assert_safe_error(missing, ERROR_ASSESSMENT_NOT_FOUND)


def test_repository_outage_and_blank_inputs() -> None:
    repository = _WriteTrackingRepository()
    repository.get_assessment_error = RuntimeError("database unavailable")
    _seed(repository, result=_completed_result())
    outage = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
        )
    )
    _assert_safe_error(outage, ERROR_REPORT_SERVICE_UNAVAILABLE)
    assert report_http_status(outage) == 503
    assert "database unavailable" not in str(outage)

    empty = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=_WriteTrackingRepository(),
            assessment_id="  ",
            owner_user_id=USER_A,
        )
    )
    _assert_safe_error(empty, ERROR_ASSESSMENT_NOT_FOUND)
    principal = asyncio.run(
        deliver_unlocked_readiness_report(
            repository=_WriteTrackingRepository(),
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=" ",
        )
    )
    _assert_safe_error(principal, ERROR_AUTH_INVALID)


def test_http_status_helpers() -> None:
    assert report_http_status({"schema_version": REPORT_SCHEMA_VERSION}) == 200
    assert report_http_status(report_failed_outcome(ERROR_REPORT_LOCKED)) == 402
    assert report_http_status({"state": "FAILED", "error_code": "NOPE"}) == 500
    assert report_http_status({"state": "FAILED"}) == 500
    assert report_service_unavailable()["error_code"] == ERROR_REPORT_SERVICE_UNAVAILABLE


def test_module_does_not_call_scoring_package_k_or_paystack() -> None:
    text = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    assert "app.engine.scoring" not in imported
    assert "app.services.assessment_pipeline" not in imported
    assert "app.commerce.paystack" not in imported
    assert "app.services.assessment_payment" not in imported
    assert "score_assessment" not in text
    assert "run_assessment_pipeline" not in text
    assert "initialize_transaction" not in called
    assert "persist_bundle" not in called
    assert "claim_assessment" not in called
    assert "begin_checkout_attempt" not in called
    assert "fulfill_payment_and_unlock" not in called
    assert "jwt" not in imported
    for line in text.splitlines():
        if "logger." in line:
            lowered = line.lower()
            assert "authorization" not in lowered
            assert "bearer" not in lowered
            assert "access_token" not in lowered
            assert "claim_token" not in lowered
