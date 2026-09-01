"""Canonical link-retrieval outcomes, error codes, and safety limits."""

from __future__ import annotations

from typing import Any, Literal

LinkRetrievalState = Literal["COMPLETED", "LINK_RETRIEVAL_FAILED"]

LINK_EXTRACTOR_VERSION = "extract.link.v1"
LINK_SOURCE_TYPES = frozenset(
    {
        "repository",
        "portfolio",
        "project",
        "deployed_project",
        "kaggle",
        "dashboard",
        "other_professional",
    }
)
SUPPORTED_CONTENT_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "text/plain",
        "text/markdown",
    }
)

MAX_URL_LENGTH = 2048
MAX_REDIRECTS = 5
CONNECT_TIMEOUT_SECONDS = 3.0
READ_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BODY_BYTES = 2 * 1024 * 1024
MAX_CONTENT_BLOCKS = 5000
ALLOWED_PORTS = frozenset({80, 443})
ALLOWED_SCHEMES = frozenset({"http", "https"})

ERROR_ENVELOPE_INVALID = "ENVELOPE_INVALID"
ERROR_MALFORMED_URL = "MALFORMED_URL"
ERROR_UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
ERROR_URL_CREDENTIALS = "URL_CREDENTIALS"
ERROR_UNSAFE_HOST = "UNSAFE_HOST"
ERROR_URL_TOO_LONG = "URL_TOO_LONG"
ERROR_DNS_RESOLUTION_FAILED = "DNS_RESOLUTION_FAILED"
ERROR_UNSAFE_REDIRECT = "UNSAFE_REDIRECT"
ERROR_REDIRECT_LIMIT_EXCEEDED = "REDIRECT_LIMIT_EXCEEDED"
ERROR_TLS_FAILURE = "TLS_FAILURE"
ERROR_TIMEOUT = "TIMEOUT"
ERROR_CONNECT_FAILURE = "CONNECT_FAILURE"
ERROR_HTTP_CLIENT_ERROR = "HTTP_CLIENT_ERROR"
ERROR_HTTP_SERVER_ERROR = "HTTP_SERVER_ERROR"
ERROR_UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
ERROR_RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
ERROR_NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
ERROR_PARSER_EXCEPTION = "PARSER_EXCEPTION"
ERROR_CONTENT_BLOCK_LIMIT_EXCEEDED = "CONTENT_BLOCK_LIMIT_EXCEEDED"

ACCESS_STATUS_BY_ERROR = {
    ERROR_ENVELOPE_INVALID: "inaccessible",
    ERROR_MALFORMED_URL: "inaccessible",
    ERROR_UNSUPPORTED_SCHEME: "unsupported",
    ERROR_URL_CREDENTIALS: "unsafe",
    ERROR_UNSAFE_HOST: "unsafe",
    ERROR_URL_TOO_LONG: "unsafe",
    ERROR_DNS_RESOLUTION_FAILED: "inaccessible",
    ERROR_UNSAFE_REDIRECT: "unsafe",
    ERROR_REDIRECT_LIMIT_EXCEEDED: "unsafe",
    ERROR_TLS_FAILURE: "inaccessible",
    ERROR_TIMEOUT: "inaccessible",
    ERROR_CONNECT_FAILURE: "inaccessible",
    ERROR_HTTP_CLIENT_ERROR: "inaccessible",
    ERROR_HTTP_SERVER_ERROR: "inaccessible",
    ERROR_UNSUPPORTED_CONTENT_TYPE: "unsupported",
    ERROR_RESPONSE_TOO_LARGE: "unsafe",
    ERROR_NO_EXTRACTABLE_TEXT: "accessible",
    ERROR_PARSER_EXCEPTION: "inaccessible",
    ERROR_CONTENT_BLOCK_LIMIT_EXCEEDED: "unsafe",
}


def link_metadata(
    *,
    link_id: str,
    submitted_url: str,
    declared_type: str,
    normalized_url: str | None = None,
    final_url: str | None = None,
    verified_content_type: str | None = None,
    http_status: int | None = None,
    byte_size: int | None = None,
    sha256: str | None = None,
) -> dict[str, Any]:
    """Return safe link metadata for retrieval outcomes."""
    return {
        "link_id": link_id,
        "submitted_url": submitted_url,
        "normalized_url": normalized_url,
        "final_url": final_url,
        "declared_type": declared_type,
        "verified_content_type": verified_content_type,
        "http_status": http_status,
        "byte_size": byte_size,
        "sha256": sha256,
    }


def link_source_record(
    *,
    link_id: str,
    declared_type: str,
    submitted_url: str,
    retrieved_at: str,
    access_status: str,
    content_hash: str | None,
) -> dict[str, Any]:
    """Return a Contract 1.2 source record for one candidate-submitted link."""
    return {
        "source_id": f"src-{link_id}",
        "source_type": declared_type,
        "submitted_by_candidate": True,
        "access_status": access_status,
        "ownership_status": "unclear",
        "retrieved_at": retrieved_at,
        "content_hash": content_hash,
        "extractor_version": LINK_EXTRACTOR_VERSION,
        "locator": submitted_url,
        "notes": "Candidate-submitted link retrieved without classification or scoring.",
    }


def completed_link_outcome(
    *,
    link: dict[str, Any],
    source_record: dict[str, Any],
    content_blocks: list[dict[str, str]],
) -> dict[str, Any]:
    """Return a successful canonical link-retrieval outcome."""
    return {
        "state": "COMPLETED",
        "error_code": None,
        "extractor_version": LINK_EXTRACTOR_VERSION,
        "link": link,
        "source_record": source_record,
        "content_blocks": content_blocks,
    }


def failed_link_outcome(
    error_code: str,
    *,
    link: dict[str, Any],
    source_record: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a safe non-score link-retrieval failure."""
    return {
        "state": "LINK_RETRIEVAL_FAILED",
        "error_code": error_code,
        "extractor_version": LINK_EXTRACTOR_VERSION,
        "link": link,
        "source_record": source_record,
        "content_blocks": [],
    }
