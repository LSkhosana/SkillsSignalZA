"""Deterministic explicit-alias matching for Package H.

Regex is compiled only from escaped checked-in aliases and fixed token-boundary
patterns. Candidate text never supplies patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.engine.configuration import load_evidence_rules_v1

KIND_SKILL = "skill"
KIND_TOOL = "tool"
KIND_QUALIFICATION = "qualification"
ALLOWED_KINDS = frozenset({KIND_SKILL, KIND_TOOL, KIND_QUALIFICATION})
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN_PREFIX = r"(?<![A-Za-z0-9])"
_TOKEN_SUFFIX = r"(?![A-Za-z0-9])"


@dataclass(frozen=True)
class AliasMatch:
    """One non-overlapping explicit alias hit inside a sentence."""

    subject: str
    kind: str
    rule_id: str
    alias: str
    matched_text: str
    start: int
    end: int


@dataclass(frozen=True)
class CompiledAlias:
    """One checked-in alias compiled with token boundaries."""

    subject: str
    kind: str
    rule_id: str
    alias: str
    case_sensitive: bool
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class CompiledRegistry:
    """Loaded Package H rule registry ready for matching."""

    document: dict[str, Any]
    aliases: tuple[CompiledAlias, ...]
    cue_pattern: re.Pattern[str]


def load_compiled_registry(document: dict[str, Any] | None = None) -> CompiledRegistry:
    """Validate the checked-in registry and compile bounded alias patterns."""
    raw = document if document is not None else load_evidence_rules_v1()
    _validate_registry(raw)
    compiled: list[CompiledAlias] = []
    for entry in (*raw["subjects"], *raw["qualifications"]):
        for alias in entry["aliases"]:
            compiled.append(
                CompiledAlias(
                    subject=entry["subject"],
                    kind=entry["kind"],
                    rule_id=entry["rule_id"],
                    alias=alias["text"],
                    case_sensitive=bool(alias["case_sensitive"]),
                    pattern=_alias_pattern(alias["text"], bool(alias["case_sensitive"])),
                )
            )
    compiled.sort(key=lambda item: (-len(item.alias), item.subject, item.alias))
    cues = sorted({str(cue) for cue in raw["action_cues"]}, key=len, reverse=True)
    cue_body = "|".join(_TOKEN_PREFIX + re.escape(cue) + _TOKEN_SUFFIX for cue in cues)
    return CompiledRegistry(
        document=raw,
        aliases=tuple(compiled),
        cue_pattern=re.compile(cue_body, re.IGNORECASE),
    )


def split_sentences(text: str) -> list[str]:
    """Split a content block into deterministic sentences without NLP."""
    stripped = text.strip()
    if not stripped:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(stripped) if part.strip()]


def find_matches(text: str, registry: CompiledRegistry) -> list[AliasMatch]:
    """Return longest-first, non-overlapping alias matches in `text`."""
    found: list[AliasMatch] = []
    for alias in registry.aliases:
        for hit in alias.pattern.finditer(text):
            found.append(
                AliasMatch(
                    subject=alias.subject,
                    kind=alias.kind,
                    rule_id=alias.rule_id,
                    alias=alias.alias,
                    matched_text=hit.group(0),
                    start=hit.start(),
                    end=hit.end(),
                )
            )
    found.sort(key=lambda item: (item.start, -(item.end - item.start), item.subject))
    accepted: list[AliasMatch] = []
    occupied: list[tuple[int, int]] = []
    for match in found:
        if any(match.start < end and match.end > start for start, end in occupied):
            continue
        accepted.append(match)
        occupied.append((match.start, match.end))
    accepted.sort(key=lambda item: (item.start, item.subject))
    return accepted


def has_application_cue(text: str, registry: CompiledRegistry) -> bool:
    """Return True when an approved V1 action cue is present as a token."""
    return registry.cue_pattern.search(text) is not None


def _alias_pattern(alias: str, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(_TOKEN_PREFIX + re.escape(alias) + _TOKEN_SUFFIX, flags)


def _validate_registry(document: dict[str, Any]) -> None:
    if document.get("normalizer_version") != "normalize.evidence.v1":
        msg = "invalid evidence rules"
        raise ValueError(msg)
    cues = document.get("action_cues")
    subjects = document.get("subjects")
    qualifications = document.get("qualifications")
    if not isinstance(cues, list) or not cues:
        msg = "invalid evidence rules"
        raise ValueError(msg)
    if not isinstance(subjects, list) or not isinstance(qualifications, list):
        msg = "invalid evidence rules"
        raise ValueError(msg)
    if not all(isinstance(cue, str) and cue.strip() for cue in cues):
        msg = "invalid evidence rules"
        raise ValueError(msg)
    seen_subjects: set[str] = set()
    seen_rule_ids: set[str] = set()
    seen_aliases: dict[str, str] = {}
    for entry in (*subjects, *qualifications):
        _validate_entry(entry, seen_subjects, seen_rule_ids, seen_aliases)


def _validate_entry(
    entry: object,
    seen_subjects: set[str],
    seen_rule_ids: set[str],
    seen_aliases: dict[str, str],
) -> None:
    if not isinstance(entry, dict):
        msg = "invalid evidence rules"
        raise ValueError(msg)
    subject = entry.get("subject")
    kind = entry.get("kind")
    rule_id = entry.get("rule_id")
    aliases = entry.get("aliases")
    if not isinstance(subject, str) or not subject:
        msg = "invalid evidence rules"
        raise ValueError(msg)
    if kind not in ALLOWED_KINDS:
        msg = "invalid evidence rules"
        raise ValueError(msg)
    if not isinstance(rule_id, str) or not rule_id:
        msg = "invalid evidence rules"
        raise ValueError(msg)
    if not isinstance(aliases, list) or not aliases:
        msg = "invalid evidence rules"
        raise ValueError(msg)
    if subject in seen_subjects or rule_id in seen_rule_ids:
        msg = "invalid evidence rules"
        raise ValueError(msg)
    seen_subjects.add(subject)
    seen_rule_ids.add(rule_id)
    for alias in aliases:
        if not isinstance(alias, dict):
            msg = "invalid evidence rules"
            raise ValueError(msg)
        text = alias.get("text")
        case_sensitive = alias.get("case_sensitive")
        if not isinstance(text, str) or not text.strip():
            msg = "invalid evidence rules"
            raise ValueError(msg)
        if not isinstance(case_sensitive, bool):
            msg = "invalid evidence rules"
            raise ValueError(msg)
        key = text if case_sensitive else text.casefold()
        owner = seen_aliases.get(key)
        if owner is not None and owner != subject:
            msg = "invalid evidence rules"
            raise ValueError(msg)
        seen_aliases[key] = subject
