"""Compile bounded cue patterns from the checked-in Package I registry."""

from __future__ import annotations

import re
from typing import Any

_TOKEN_PREFIX = r"(?<![A-Za-z0-9])"
_TOKEN_SUFFIX = r"(?![A-Za-z0-9])"
FROM_TO_RE = re.compile(r"(?<![A-Za-z0-9])from\s+\S.{0,80}?\s+to(?![A-Za-z0-9])", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
EVIDENCE_ID_RE = re.compile(r"^ev-(\d{4,})$")


def token_pattern(phrases: list[str], *, prefix_only: bool = False) -> re.Pattern[str] | None:
    """Compile escaped token-boundary alternatives from checked-in phrases."""
    unique = [phrase for phrase in dict.fromkeys(phrases) if phrase]
    if not unique:
        return None
    parts: list[str] = []
    for phrase in sorted(unique, key=len, reverse=True):
        escaped = re.escape(phrase)
        if prefix_only:
            parts.append(_TOKEN_PREFIX + escaped)
        else:
            parts.append(_TOKEN_PREFIX + escaped + _TOKEN_SUFFIX)
    return re.compile("|".join(parts), re.IGNORECASE)


def has_cue(text: str, pattern: re.Pattern[str] | None) -> bool:
    """Return True when a compiled cue pattern matches `text`."""
    return pattern is not None and pattern.search(text) is not None


def compile_group(
    rules: dict[str, Any], key: str, *, prefix_only: bool = False
) -> re.Pattern[str] | None:
    """Compile one registry phrase list."""
    values = rules.get(key) or []
    if not isinstance(values, list):
        msg = "invalid higher-order rules"
        raise ValueError(msg)
    return token_pattern([str(item) for item in values], prefix_only=prefix_only)
