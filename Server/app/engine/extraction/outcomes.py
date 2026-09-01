"""Canonical CV extraction outcomes, error codes, and safety limits."""

from __future__ import annotations

from typing import Any, Literal

ExtractionState = Literal["COMPLETED", "CV_EXTRACTION_FAILED"]

EXTRACTOR_VERSION = "extract.cv.v1"
MEDIA_TYPE_PDF = "application/pdf"
MEDIA_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SUPPORTED_MEDIA_TYPES = frozenset({MEDIA_TYPE_PDF, MEDIA_TYPE_DOCX})

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_DOCX_ZIP_ENTRIES = 256
MAX_DOCX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024

ERROR_EMPTY_FILE = "EMPTY_FILE"
ERROR_UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
ERROR_MEDIA_TYPE_MISMATCH = "MEDIA_TYPE_MISMATCH"
ERROR_MALFORMED_PDF = "MALFORMED_PDF"
ERROR_ENCRYPTED_PDF = "ENCRYPTED_PDF"
ERROR_MALFORMED_DOCX = "MALFORMED_DOCX"
ERROR_NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
ERROR_FILE_TOO_LARGE = "FILE_TOO_LARGE"
ERROR_PDF_PAGE_LIMIT_EXCEEDED = "PDF_PAGE_LIMIT_EXCEEDED"
ERROR_DOCX_UNSAFE_ARCHIVE = "DOCX_UNSAFE_ARCHIVE"
ERROR_DOCX_ENTRY_LIMIT_EXCEEDED = "DOCX_ENTRY_LIMIT_EXCEEDED"
ERROR_DOCX_UNCOMPRESSED_SIZE_LIMIT_EXCEEDED = "DOCX_UNCOMPRESSED_SIZE_LIMIT_EXCEEDED"
ERROR_ENVELOPE_INVALID = "ENVELOPE_INVALID"
ERROR_PARSER_EXCEPTION = "PARSER_EXCEPTION"


def document_metadata(
    *,
    document_id: str,
    original_filename: str,
    declared_media_type: str,
    verified_media_type: str | None,
    byte_size: int | None,
    sha256: str | None,
) -> dict[str, Any]:
    """Return safe document metadata for extraction outcomes."""
    return {
        "document_id": document_id,
        "original_filename": original_filename,
        "declared_media_type": declared_media_type,
        "verified_media_type": verified_media_type,
        "byte_size": byte_size,
        "sha256": sha256,
    }


def completed_outcome(
    *,
    document: dict[str, Any],
    source_record: dict[str, Any],
    content_blocks: list[dict[str, str]],
) -> dict[str, Any]:
    """Return a successful canonical extraction outcome."""
    return {
        "state": "COMPLETED",
        "error_code": None,
        "extractor_version": EXTRACTOR_VERSION,
        "document": document,
        "source_record": source_record,
        "content_blocks": content_blocks,
    }


def failed_outcome(
    error_code: str,
    *,
    document: dict[str, Any],
) -> dict[str, Any]:
    """Return a safe non-score extraction failure."""
    return {
        "state": "CV_EXTRACTION_FAILED",
        "error_code": error_code,
        "extractor_version": EXTRACTOR_VERSION,
        "document": document,
        "source_record": None,
        "content_blocks": [],
    }


def cv_source_record(
    *,
    document_id: str,
    retrieved_at: str,
    content_hash: str,
    locator: str,
) -> dict[str, Any]:
    """Return the Contract 1.2 CV source record for a successful extraction."""
    return {
        "source_id": document_id,
        "source_type": "cv",
        "submitted_by_candidate": True,
        "access_status": "accessible",
        "ownership_status": "attributed",
        "retrieved_at": retrieved_at,
        "content_hash": content_hash,
        "extractor_version": EXTRACTOR_VERSION,
        "locator": locator,
        "notes": "Candidate-submitted CV extracted without classification or scoring.",
    }
