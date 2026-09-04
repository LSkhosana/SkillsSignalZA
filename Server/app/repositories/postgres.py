"""PostgreSQL adapter for Package L assessment persistence.

Uses psycopg 3 with a small connection pool. Does not use PostgREST.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Self

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.repositories.records import (
    AssessmentRecord,
    AssessmentRunRecord,
    DocumentMetadata,
    PersistenceBundle,
    PersistWriteResult,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "postgres"
    / "0001_assessment_persistence.sql"
)
MIGRATION_0002_PATH = MIGRATION_PATH.with_name("0002_harden_immutable_function_search_path.sql")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _document_from_row(row: dict[str, Any] | None) -> DocumentMetadata | None:
    if row is None:
        return None
    return DocumentMetadata(
        document_id=str(row["document_id"]),
        storage_path=str(row["storage_path"]),
        original_filename=str(row["original_filename"]),
        media_type=str(row["media_type"]),
        sha256=str(row["sha256"]).strip(),
        byte_size=int(row["byte_size"]),
    )


def _source_from_row(row: dict[str, Any]) -> dict[str, Any]:
    retrieved = row["retrieved_at"]
    return {
        "source_id": str(row["source_id"]),
        "source_type": str(row["source_type"]),
        "submitted_by_candidate": bool(row["submitted_by_candidate"]),
        "access_status": str(row["access_status"]),
        "ownership_status": str(row["ownership_status"]),
        "retrieved_at": retrieved.isoformat().replace("+00:00", "Z") if retrieved else None,
        "content_hash": _text(row["content_hash"]),
        "extractor_version": str(row["extractor_version"]),
        "locator": str(row["locator"]),
        "notes": row["notes"],
    }


def _evidence_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": str(row["evidence_id"]),
        "source_id": str(row["source_id"]),
        "locator": str(row["locator"]),
        "fact_type": str(row["fact_type"]),
        "subject": str(row["subject"]),
        "explicit_text": str(row["explicit_text"]),
        "evidence_level": str(row["evidence_level"]),
        "attribution_status": str(row["attribution_status"]),
        "rule_id": str(row["rule_id"]),
        "review_status": str(row["review_status"]),
    }


def _run_equivalent(existing: dict[str, Any], bundle: PersistenceBundle) -> bool:
    outcome = bundle.pipeline_outcome
    return (
        str(existing["assessment_id"]) == bundle.assessment_id
        and str(existing["state"]) == str(outcome["state"])
        and _text(existing["error_code"]) == _text(outcome.get("error_code"))
        and str(existing["pipeline_version"]) == str(outcome["pipeline_version"])
        and str(existing["contract_version"]) == str(outcome["contract_version"])
        and str(existing["rubric_version"]) == str(outcome["rubric_version"])
        and str(existing["track"]) == bundle.track
        and _canonical(existing["assessment_input"]) == _canonical(bundle.assessment_input)
        and _canonical(existing["scoring_context"]) == _canonical(outcome.get("scoring_context"))
        and _canonical(existing["assessment_result"])
        == _canonical(outcome.get("assessment_result"))
        and _canonical(existing["review_flags"]) == _canonical(outcome.get("review_flags") or [])
        and _canonical(existing["stages"]) == _canonical(outcome.get("stages") or [])
    )


class PostgresAssessmentRepository:
    """Direct PostgreSQL implementation of AssessmentRepository."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    @classmethod
    async def connect(
        cls,
        dsn: str,
        *,
        min_size: int = 0,
        max_size: int = 5,
    ) -> Self:
        """Open a small pool. Callers must not invoke this at import time."""
        pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            open=False,
            kwargs={"row_factory": dict_row, "autocommit": False},
        )
        await pool.open()
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def persist_bundle(self, bundle: PersistenceBundle) -> PersistWriteResult:
        async with self._pool.connection() as connection:
            async with connection.transaction():
                async with connection.cursor() as cursor:
                    return await self._persist_in_transaction(cursor, bundle)

    async def get_assessment(self, assessment_id: str) -> AssessmentRecord | None:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT assessment_id, candidate_ref, track, access_state, claim_token_hash,
                           claimed_at, latest_run_id, expires_at, created_at, updated_at
                    FROM assessments
                    WHERE assessment_id = %s
                    """,
                    (assessment_id,),
                )
                row = await cursor.fetchone()
        if row is None:
            return None
        return AssessmentRecord(
            assessment_id=str(row["assessment_id"]),
            candidate_ref=str(row["candidate_ref"]),
            track=str(row["track"]),
            access_state=str(row["access_state"]),  # type: ignore[arg-type]
            claim_token_hash=_text(row["claim_token_hash"]),
            claimed_at=row["claimed_at"],
            latest_run_id=_text(row["latest_run_id"]),
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_run(self, run_id: str) -> AssessmentRunRecord | None:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                return await self._load_run(cursor, run_id)

    async def get_latest_run(self, assessment_id: str) -> AssessmentRunRecord | None:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT latest_run_id FROM assessments WHERE assessment_id = %s",
                    (assessment_id,),
                )
                row = await cursor.fetchone()
                if row is None or row["latest_run_id"] is None:
                    return None
                return await self._load_run(cursor, str(row["latest_run_id"]))

    async def _load_run(self, cursor: Any, run_id: str) -> AssessmentRunRecord | None:
        await cursor.execute(
            """
            SELECT run_id, assessment_id, state, error_code, pipeline_version, contract_version,
                   rubric_version, track, assessment_input, scoring_context, assessment_result,
                   review_flags, stages, assessed_at, created_at
            FROM assessment_runs
            WHERE run_id = %s
            """,
            (run_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        await cursor.execute(
            """
            SELECT source_id, source_type, submitted_by_candidate, access_status, ownership_status,
                   retrieved_at, content_hash, extractor_version, locator, notes
            FROM assessment_sources
            WHERE run_id = %s
            ORDER BY source_id
            """,
            (run_id,),
        )
        sources = [_source_from_row(item) for item in await cursor.fetchall()]
        await cursor.execute(
            """
            SELECT evidence_id, source_id, locator, fact_type, subject, explicit_text,
                   evidence_level, attribution_status, rule_id, review_status
            FROM assessment_evidence
            WHERE run_id = %s
            ORDER BY evidence_id
            """,
            (run_id,),
        )
        evidence = [_evidence_from_row(item) for item in await cursor.fetchall()]
        await cursor.execute(
            """
            SELECT document_id, storage_path, original_filename, media_type, sha256, byte_size
            FROM assessment_documents
            WHERE assessment_id = %s
            ORDER BY document_id
            """,
            (str(row["assessment_id"]),),
        )
        document_row = await cursor.fetchone()
        return AssessmentRunRecord(
            run_id=str(row["run_id"]),
            assessment_id=str(row["assessment_id"]),
            state=str(row["state"]),
            error_code=_text(row["error_code"]),
            pipeline_version=str(row["pipeline_version"]),
            contract_version=str(row["contract_version"]),
            rubric_version=str(row["rubric_version"]),
            track=str(row["track"]),
            assessment_input=dict(row["assessment_input"]),
            scoring_context=dict(row["scoring_context"])
            if row["scoring_context"] is not None
            else None,
            assessment_result=(
                dict(row["assessment_result"]) if row["assessment_result"] is not None else None
            ),
            review_flags=list(row["review_flags"] or []),
            stages=list(row["stages"] or []),
            assessed_at=row["assessed_at"],
            created_at=row["created_at"],
            source_records=sources,
            evidence_facts=evidence,
            document=_document_from_row(document_row),
        )

    async def _persist_in_transaction(
        self, cursor: Any, bundle: PersistenceBundle
    ) -> PersistWriteResult:
        await cursor.execute(
            """
            SELECT assessment_id, candidate_ref, track, latest_run_id
            FROM assessments
            WHERE assessment_id = %s
            FOR UPDATE
            """,
            (bundle.assessment_id,),
        )
        assessment_row = await cursor.fetchone()
        await cursor.execute(
            """
            SELECT run_id, assessment_id, state, error_code, pipeline_version, contract_version,
                   rubric_version, track, assessment_input, scoring_context, assessment_result,
                   review_flags, stages
            FROM assessment_runs
            WHERE run_id = %s
            FOR UPDATE
            """,
            (bundle.run_id,),
        )
        run_row = await cursor.fetchone()
        if run_row is not None:
            return await self._existing_run(cursor, bundle, assessment_row, run_row)
        if assessment_row is not None:
            if not await self._assessment_compatible(cursor, assessment_row, bundle):
                return PersistWriteResult("conflict", bundle.assessment_id, bundle.run_id)
            await self._insert_run_tree(cursor, bundle)
            await self._set_latest_run(cursor, bundle.assessment_id, bundle.run_id)
            return PersistWriteResult(
                "inserted", bundle.assessment_id, bundle.run_id, latest_run_id=bundle.run_id
            )
        await self._insert_assessment(cursor, bundle)
        await self._insert_document(cursor, bundle)
        await self._insert_run_tree(cursor, bundle)
        await self._set_latest_run(cursor, bundle.assessment_id, bundle.run_id)
        return PersistWriteResult(
            "inserted", bundle.assessment_id, bundle.run_id, latest_run_id=bundle.run_id
        )

    async def _existing_run(
        self,
        cursor: Any,
        bundle: PersistenceBundle,
        assessment_row: dict[str, Any] | None,
        run_row: dict[str, Any],
    ) -> PersistWriteResult:
        if str(run_row["assessment_id"]) != bundle.assessment_id:
            return PersistWriteResult("conflict", bundle.assessment_id, bundle.run_id)
        if assessment_row is None:
            return PersistWriteResult("conflict", bundle.assessment_id, bundle.run_id)
        if not await self._assessment_compatible(cursor, assessment_row, bundle):
            return PersistWriteResult("conflict", bundle.assessment_id, bundle.run_id)
        if not _run_equivalent(run_row, bundle):
            return PersistWriteResult("conflict", bundle.assessment_id, bundle.run_id)
        if not await self._children_equivalent(cursor, bundle):
            return PersistWriteResult("conflict", bundle.assessment_id, bundle.run_id)
        return PersistWriteResult(
            "noop",
            bundle.assessment_id,
            bundle.run_id,
            latest_run_id=_text(assessment_row.get("latest_run_id")) or bundle.run_id,
        )

    async def _assessment_compatible(
        self, cursor: Any, assessment_row: dict[str, Any], bundle: PersistenceBundle
    ) -> bool:
        if str(assessment_row["candidate_ref"]) != bundle.candidate_ref:
            return False
        if str(assessment_row["track"]) != bundle.track:
            return False
        await cursor.execute(
            """
            SELECT document_id, storage_path, original_filename, media_type, sha256, byte_size
            FROM assessment_documents
            WHERE assessment_id = %s AND document_id = %s
            """,
            (bundle.assessment_id, bundle.document.document_id),
        )
        document_row = await cursor.fetchone()
        if document_row is None:
            return False
        existing = _document_from_row(document_row)
        return existing == bundle.document

    async def _children_equivalent(self, cursor: Any, bundle: PersistenceBundle) -> bool:
        await cursor.execute(
            """
            SELECT source_id, source_type, submitted_by_candidate, access_status, ownership_status,
                   retrieved_at, content_hash, extractor_version, locator, notes
            FROM assessment_sources
            WHERE run_id = %s
            ORDER BY source_id
            """,
            (bundle.run_id,),
        )
        stored_sources = [_source_from_row(item) for item in await cursor.fetchall()]
        incoming_sources = [
            {
                **source,
                "retrieved_at": source.get("retrieved_at"),
                "content_hash": source.get("content_hash"),
                "notes": source.get("notes"),
            }
            for source in list(bundle.pipeline_outcome.get("source_records") or [])
        ]
        if _canonical(_normalize_sources(incoming_sources)) != _canonical(
            _normalize_sources(stored_sources)
        ):
            return False
        await cursor.execute(
            """
            SELECT evidence_id, source_id, locator, fact_type, subject, explicit_text,
                   evidence_level, attribution_status, rule_id, review_status
            FROM assessment_evidence
            WHERE run_id = %s
            ORDER BY evidence_id
            """,
            (bundle.run_id,),
        )
        stored_evidence = [_evidence_from_row(item) for item in await cursor.fetchall()]
        incoming_evidence = list(bundle.pipeline_outcome.get("evidence_facts") or [])
        return _canonical(incoming_evidence) == _canonical(stored_evidence)

    async def _insert_assessment(self, cursor: Any, bundle: PersistenceBundle) -> None:
        await cursor.execute(
            """
            INSERT INTO assessments (
                assessment_id, candidate_ref, track, access_state, claim_token_hash,
                claimed_at, latest_run_id, expires_at
            )
            VALUES (%s, %s, %s, 'PREVIEW', %s, NULL, NULL, %s)
            """,
            (
                bundle.assessment_id,
                bundle.candidate_ref,
                bundle.track,
                bundle.claim_token_hash,
                bundle.expires_at,
            ),
        )

    async def _insert_document(self, cursor: Any, bundle: PersistenceBundle) -> None:
        document = bundle.document
        await cursor.execute(
            """
            INSERT INTO assessment_documents (
                assessment_id, document_id, storage_path, original_filename, media_type,
                sha256, byte_size
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                bundle.assessment_id,
                document.document_id,
                document.storage_path,
                document.original_filename,
                document.media_type,
                document.sha256,
                document.byte_size,
            ),
        )

    async def _insert_run_tree(self, cursor: Any, bundle: PersistenceBundle) -> None:
        outcome = bundle.pipeline_outcome
        await cursor.execute(
            """
            INSERT INTO assessment_runs (
                run_id, assessment_id, state, error_code, pipeline_version, contract_version,
                rubric_version, track, assessment_input, scoring_context, assessment_result,
                review_flags, stages, assessed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                bundle.run_id,
                bundle.assessment_id,
                outcome["state"],
                outcome.get("error_code"),
                outcome["pipeline_version"],
                outcome["contract_version"],
                outcome["rubric_version"],
                bundle.track,
                Jsonb(bundle.assessment_input),
                Jsonb(outcome["scoring_context"])
                if outcome.get("scoring_context") is not None
                else None,
                Jsonb(outcome["assessment_result"])
                if outcome.get("assessment_result") is not None
                else None,
                Jsonb(list(outcome.get("review_flags") or [])),
                Jsonb(list(outcome.get("stages") or [])),
                bundle.assessed_at,
            ),
        )
        await self._bulk_insert_sources(
            cursor, bundle.run_id, list(outcome.get("source_records") or [])
        )
        await self._bulk_insert_evidence(
            cursor, bundle.run_id, list(outcome.get("evidence_facts") or [])
        )

    async def _bulk_insert_sources(
        self, cursor: Any, run_id: str, sources: list[dict[str, Any]]
    ) -> None:
        if not sources:
            return
        rows = [
            (
                run_id,
                str(source["source_id"]),
                str(source["source_type"]),
                bool(source["submitted_by_candidate"]),
                str(source["access_status"]),
                str(source["ownership_status"]),
                _as_timestamptz(source.get("retrieved_at")),
                _text(source.get("content_hash")),
                str(source["extractor_version"]),
                str(source["locator"]),
                source.get("notes"),
            )
            for source in sources
        ]
        await cursor.executemany(
            """
            INSERT INTO assessment_sources (
                run_id, source_id, source_type, submitted_by_candidate, access_status,
                ownership_status, retrieved_at, content_hash, extractor_version, locator, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )

    async def _bulk_insert_evidence(
        self, cursor: Any, run_id: str, facts: list[dict[str, Any]]
    ) -> None:
        if not facts:
            return
        rows = [
            (
                run_id,
                str(fact["evidence_id"]),
                str(fact["source_id"]),
                str(fact["locator"]),
                str(fact["fact_type"]),
                str(fact["subject"]),
                str(fact["explicit_text"]),
                str(fact["evidence_level"]),
                str(fact["attribution_status"]),
                str(fact["rule_id"]),
                str(fact["review_status"]),
            )
            for fact in facts
        ]
        await cursor.executemany(
            """
            INSERT INTO assessment_evidence (
                run_id, evidence_id, source_id, locator, fact_type, subject, explicit_text,
                evidence_level, attribution_status, rule_id, review_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )

    async def _set_latest_run(self, cursor: Any, assessment_id: str, run_id: str) -> None:
        await cursor.execute(
            """
            UPDATE assessments
            SET latest_run_id = %s, updated_at = now()
            WHERE assessment_id = %s
            """,
            (run_id, assessment_id),
        )


async def apply_postgres_migration(dsn: str, path: Path = MIGRATION_PATH) -> None:
    """Apply the checked-in Package L migration. Used by tests and operators."""
    from psycopg import AsyncConnection

    sql = path.read_text(encoding="utf-8")
    async with await AsyncConnection.connect(dsn, autocommit=True) as connection:
        await connection.execute(sql)


def _as_timestamptz(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        msg = "retrieved_at must be RFC 3339"
        raise TypeError(msg)
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        msg = "retrieved_at must be timezone-aware"
        raise ValueError(msg)
    return parsed


def _normalize_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for source in sources:
        retrieved = source.get("retrieved_at")
        if hasattr(retrieved, "isoformat"):
            retrieved = retrieved.isoformat().replace("+00:00", "Z")
        normalized.append(
            {
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "submitted_by_candidate": bool(source["submitted_by_candidate"]),
                "access_status": source["access_status"],
                "ownership_status": source["ownership_status"],
                "retrieved_at": retrieved,
                "content_hash": source.get("content_hash"),
                "extractor_version": source["extractor_version"],
                "locator": source["locator"],
                "notes": source.get("notes"),
            }
        )
    return sorted(normalized, key=lambda item: str(item["source_id"]))
