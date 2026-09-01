"""Evidence extraction engine.

Deterministic CV text extraction lives here. Classification, scoring,
and HTTP transport must not be implemented in this package.
"""

from app.engine.extraction.cv import extract_cv
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
]
