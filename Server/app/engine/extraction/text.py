"""Deterministic mechanical text normalization for CV extraction."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")


def normalize_extracted_text(value: str) -> str:
    """Normalize line endings and insignificant whitespace without rewriting wording."""
    text = value.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def split_non_empty_blocks(value: str) -> list[str]:
    """Return ordered non-empty text blocks after deterministic normalization."""
    normalized = normalize_extracted_text(value)
    if not normalized:
        return []
    return normalized.split("\n")
