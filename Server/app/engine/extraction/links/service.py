"""Public deterministic candidate-submitted link retrieval."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from app.engine.extraction.links.html import extract_visible_blocks
from app.engine.extraction.links.http import (
    HopResponse,
    RetrievalError,
    content_type_of,
    decode_body,
    retrieve_validated_resource,
)
from app.engine.extraction.links.outcomes import (
    ACCESS_STATUS_BY_ERROR,
    ERROR_CONTENT_BLOCK_LIMIT_EXCEEDED,
    ERROR_ENVELOPE_INVALID,
    ERROR_HTTP_CLIENT_ERROR,
    ERROR_HTTP_SERVER_ERROR,
    ERROR_MALFORMED_URL,
    ERROR_NO_EXTRACTABLE_TEXT,
    ERROR_PARSER_EXCEPTION,
    ERROR_UNSUPPORTED_CONTENT_TYPE,
    LINK_SOURCE_TYPES,
    MAX_CONTENT_BLOCKS,
    SUPPORTED_CONTENT_TYPES,
    completed_link_outcome,
    failed_link_outcome,
    link_metadata,
    link_source_record,
)
from app.engine.extraction.links.url import normalize_submitted_url

_HASH_ON_FAILURE = frozenset({ERROR_NO_EXTRACTABLE_TEXT, ERROR_CONTENT_BLOCK_LIMIT_EXCEEDED})


def retrieve_candidate_link(
    submitted_url: str,
    *,
    link_id: str,
    declared_type: str,
    retrieved_at: str,
) -> dict[str, Any]:
    """Retrieve and freeze one candidate-submitted web link.

    This entry point performs no persistence, scoring, evidence classification,
    or caller-controlled header injection. Redirects are revalidated hop by hop.
    """
    original_url = submitted_url if isinstance(submitted_url, str) else ""
    safe_link_id = link_id if isinstance(link_id, str) else ""
    safe_type = declared_type if isinstance(declared_type, str) else ""
    link = link_metadata(
        link_id=safe_link_id,
        submitted_url=original_url,
        declared_type=safe_type,
    )
    try:
        envelope_error = _envelope_error(
            submitted_url=submitted_url,
            link_id=link_id,
            declared_type=declared_type,
            retrieved_at=retrieved_at,
        )
        if envelope_error is not None:
            return _failure(envelope_error, link=link, retrieved_at=retrieved_at)

        try:
            normalized = normalize_submitted_url(original_url)
        except (ValueError, TypeError):
            return _failure(ERROR_MALFORMED_URL, link=link, retrieved_at=retrieved_at)
        link["normalized_url"] = normalized
        response = retrieve_validated_resource(normalized)
        return _complete_from_response(
            response,
            link=link,
            link_id=safe_link_id,
            declared_type=safe_type,
            submitted_url=original_url,
            retrieved_at=retrieved_at,
        )
    except RetrievalError as exc:
        return _failure(exc.error_code, link=link, retrieved_at=retrieved_at)
    except Exception:
        return _failure(ERROR_PARSER_EXCEPTION, link=link, retrieved_at=retrieved_at)


def _complete_from_response(
    response: HopResponse,
    *,
    link: dict[str, Any],
    link_id: str,
    declared_type: str,
    submitted_url: str,
    retrieved_at: str,
) -> dict[str, Any]:
    link["final_url"] = response.url
    link["http_status"] = response.status_code
    if 400 <= response.status_code <= 499:
        return _failure(ERROR_HTTP_CLIENT_ERROR, link=link, retrieved_at=retrieved_at)
    if response.status_code >= 500:
        return _failure(ERROR_HTTP_SERVER_ERROR, link=link, retrieved_at=retrieved_at)
    if response.status_code != 200:
        return _failure(ERROR_HTTP_CLIENT_ERROR, link=link, retrieved_at=retrieved_at)

    media_type = content_type_of(response.headers)
    link["verified_content_type"] = media_type
    if media_type not in SUPPORTED_CONTENT_TYPES:
        return _failure(ERROR_UNSUPPORTED_CONTENT_TYPE, link=link, retrieved_at=retrieved_at)

    digest = hashlib.sha256(response.content).hexdigest()
    link["byte_size"] = len(response.content)
    link["sha256"] = digest
    body = decode_body(response.content, response.headers)
    blocks = extract_visible_blocks(media_type, body)
    if not blocks:
        return _failure(
            ERROR_NO_EXTRACTABLE_TEXT,
            link=link,
            retrieved_at=retrieved_at,
            content_hash=digest,
        )
    if len(blocks) > MAX_CONTENT_BLOCKS:
        return _failure(
            ERROR_CONTENT_BLOCK_LIMIT_EXCEEDED,
            link=link,
            retrieved_at=retrieved_at,
            content_hash=digest,
        )
    record = link_source_record(
        link_id=link_id,
        declared_type=declared_type,
        submitted_url=submitted_url,
        retrieved_at=retrieved_at,
        access_status="accessible",
        content_hash=digest,
    )
    return completed_link_outcome(link=link, source_record=record, content_blocks=blocks)


def _failure(
    error_code: str,
    *,
    link: dict[str, Any],
    retrieved_at: object,
    content_hash: str | None = None,
) -> dict[str, Any]:
    timestamp = retrieved_at if isinstance(retrieved_at, str) else ""
    record = None
    if _can_build_source_record(link):
        hash_value = content_hash if error_code in _HASH_ON_FAILURE else None
        record = link_source_record(
            link_id=link["link_id"],
            declared_type=link["declared_type"],
            submitted_url=link["submitted_url"],
            retrieved_at=timestamp,
            access_status=ACCESS_STATUS_BY_ERROR.get(error_code, "inaccessible"),
            content_hash=hash_value,
        )
    return failed_link_outcome(error_code, link=link, source_record=record)


def _can_build_source_record(link: dict[str, Any]) -> bool:
    return (
        isinstance(link.get("link_id"), str)
        and bool(link["link_id"].strip())
        and link.get("declared_type") in LINK_SOURCE_TYPES
        and isinstance(link.get("submitted_url"), str)
        and bool(link["submitted_url"].strip())
    )


def _envelope_error(
    *,
    submitted_url: object,
    link_id: object,
    declared_type: object,
    retrieved_at: object,
) -> str | None:
    if not _non_empty_string(submitted_url):
        return ERROR_ENVELOPE_INVALID
    if not _non_empty_string(link_id):
        return ERROR_ENVELOPE_INVALID
    if not isinstance(declared_type, str) or declared_type not in LINK_SOURCE_TYPES:
        return ERROR_ENVELOPE_INVALID
    if not _non_empty_string(retrieved_at):
        return ERROR_ENVELOPE_INVALID
    try:
        datetime.fromisoformat(str(retrieved_at).replace("Z", "+00:00"))
    except ValueError:
        return ERROR_ENVELOPE_INVALID
    return None


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
