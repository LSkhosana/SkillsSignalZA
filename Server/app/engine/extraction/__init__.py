"""Evidence extraction engine.

Deterministic CV text extraction and candidate-submitted link retrieval
live here. Classification, scoring, and FastAPI routes must not implement
extraction rules.
"""

from app.engine.extraction.cv import extract_cv
from app.engine.extraction.links import normalize_submitted_url, retrieve_candidate_link
from app.engine.extraction.outcomes import (
    EXTRACTOR_VERSION,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_DOCX_ZIP_ENTRIES,
    MAX_FILE_SIZE_BYTES,
    MAX_PDF_PAGES,
)

__all__ = [
    "EXTRACTOR_VERSION",
    "MAX_DOCX_UNCOMPRESSED_BYTES",
    "MAX_DOCX_ZIP_ENTRIES",
    "MAX_FILE_SIZE_BYTES",
    "MAX_PDF_PAGES",
    "extract_cv",
    "normalize_submitted_url",
    "retrieve_candidate_link",
]
