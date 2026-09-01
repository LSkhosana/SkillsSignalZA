"""Convert Package F/G text blocks into Contract 1.2 evidence facts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from app.engine.configuration import load_json
from app.engine.evidence.matching import (
    KIND_QUALIFICATION,
    KIND_SKILL,
    CompiledRegistry,
    find_matches,
    has_application_cue,
    load_compiled_registry,
    split_sentences,
)
from app.engine.evidence.outcomes import (
    ACCESSIBLE,
    APPROVED_TRACKS,
    ERROR_CLASSIFIER_EXCEPTION,
    ERROR_CV_NOT_EXTRACTABLE,
    ERROR_DUPLICATE_SOURCE_ID,
    ERROR_FACT_LIMIT_EXCEEDED,
    ERROR_INVALID_CV_EXTRACTION,
    ERROR_INVALID_LINK_RETRIEVAL,
    ERROR_INVALID_TRACK,
    ERROR_MALFORMED_SOURCE_STRUCTURE,
    ERROR_RULESET_INVALID,
    MAX_EVIDENCE_FACTS,
    NAMED_ONLY_BOUNDED_CHARS,
    OWNERSHIP_VALUES,
    REVIEW_FLAG_OWNERSHIP_UNCLEAR,
    SOURCE_TYPE_CV,
    NormalizationFailure,
    canonical_outcome,
    failed_outcome,
)
from app.engine.evidence.qualifications import (
    QUALIFICATION_EVIDENCE_LEVEL,
    QUALIFICATION_FACT_TYPE,
    emit_qualification_from_source,
    qualification_hits,
    sentence_has_qualification,
)
from app.engine.extraction.text import normalize_extracted_text

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
CV_SCHEMA_PATH = SCHEMA_DIR / "cv_extraction.schema.json"
LINK_SCHEMA_PATH = SCHEMA_DIR / "link_retrieval.schema.json"
FACT_SCHEMA_PATH = SCHEMA_DIR / "evidence_fact.schema.json"
OUTCOME_SCHEMA_PATH = SCHEMA_DIR / "evidence_normalization.schema.json"
LEVEL_RANK = {"demonstrated": 3, "documented": 2, "named_only": 1}
ATTRIBUTION_RANK = {"attributed": 3, "unclear": 2, "conflicting": 1}


def normalize_evidence(
    *,
    track: str,
    cv_extraction: dict[str, Any],
    link_retrievals: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Normalize explicit evidence from CV and link extraction outcomes."""
    safe_track = track if isinstance(track, str) else ""
    try:
        return _normalize_evidence(
            track=track,
            cv_extraction=cv_extraction,
            link_retrievals=link_retrievals,
        )
    except NormalizationFailure as exc:
        return failed_outcome(exc.error_code, track=exc.track)
    except Exception:
        return failed_outcome(ERROR_CLASSIFIER_EXCEPTION, track=safe_track)


def _normalize_evidence(
    *,
    track: object,
    cv_extraction: object,
    link_retrievals: object,
) -> dict[str, Any]:
    safe_track = track if isinstance(track, str) else ""
    if safe_track not in APPROVED_TRACKS:
        raise NormalizationFailure(ERROR_INVALID_TRACK, safe_track)
    try:
        registry = load_compiled_registry()
    except (OSError, TypeError, ValueError):
        raise NormalizationFailure(ERROR_RULESET_INVALID, safe_track) from None
    cv_outcome = _validated_cv(cv_extraction, safe_track)
    links = _validated_links(link_retrievals, safe_track)
    source_records, work_items = _collect_sources(cv_outcome, links, safe_track)
    facts = _collect_facts(work_items, registry, safe_track)
    facts = _deduplicate(facts)
    if len(facts) > MAX_EVIDENCE_FACTS:
        raise NormalizationFailure(ERROR_FACT_LIMIT_EXCEEDED, safe_track)
    assigned = [_with_evidence_id(fact, index) for index, fact in enumerate(facts, start=1)]
    review_flags: list[str] = []
    state: str = "COMPLETED"
    error_code: str | None = None
    if any(fact["attribution_status"] == "unclear" for fact in assigned):
        state = "REVIEW_REQUIRED"
        error_code = REVIEW_FLAG_OWNERSHIP_UNCLEAR
        review_flags = [REVIEW_FLAG_OWNERSHIP_UNCLEAR]
    outcome = canonical_outcome(
        state=state,  # type: ignore[arg-type]
        error_code=error_code,
        track=safe_track,
        source_records=source_records,
        evidence_facts=assigned,
        review_flags=review_flags,
    )
    _assert_outcome_valid(outcome, safe_track)
    return outcome


def _validated_cv(cv_extraction: object, track: str) -> dict[str, Any]:
    if not isinstance(cv_extraction, dict):
        raise NormalizationFailure(ERROR_INVALID_CV_EXTRACTION, track)
    try:
        _validator(CV_SCHEMA_PATH).validate(cv_extraction)
    except (ValidationError, TypeError, ValueError):
        raise NormalizationFailure(ERROR_INVALID_CV_EXTRACTION, track) from None
    if cv_extraction.get("state") != "COMPLETED":
        raise NormalizationFailure(ERROR_CV_NOT_EXTRACTABLE, track)
    return cv_extraction


def _validated_links(link_retrievals: object, track: str) -> list[dict[str, Any]]:
    if link_retrievals is None:
        raise NormalizationFailure(ERROR_INVALID_LINK_RETRIEVAL, track)
    if not isinstance(link_retrievals, (list, tuple)):
        raise NormalizationFailure(ERROR_INVALID_LINK_RETRIEVAL, track)
    validated: list[dict[str, Any]] = []
    validator = _validator(LINK_SCHEMA_PATH)
    for outcome in link_retrievals:
        if not isinstance(outcome, dict):
            raise NormalizationFailure(ERROR_INVALID_LINK_RETRIEVAL, track)
        candidate = deepcopy(outcome)
        record = candidate.get("source_record")
        if isinstance(record, dict) and "ownership_status" in record:
            record["ownership_status"] = "unclear"
        try:
            validator.validate(candidate)
        except (ValidationError, TypeError, ValueError):
            raise NormalizationFailure(ERROR_INVALID_LINK_RETRIEVAL, track) from None
        validated.append(outcome)
    return validated


def _collect_sources(
    cv_outcome: dict[str, Any],
    links: list[dict[str, Any]],
    track: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    work_items: list[dict[str, Any]] = []
    cv_record = _register_source(cv_outcome.get("source_record"), seen_ids, source_records, track)
    work_items.append(
        {
            "source_record": cv_record,
            "content_blocks": cv_outcome.get("content_blocks"),
            "emit_facts": True,
        }
    )
    for outcome in links:
        record = _register_source(outcome.get("source_record"), seen_ids, source_records, track)
        accessible = (
            outcome.get("state") == "COMPLETED"
            and isinstance(record, dict)
            and record.get("access_status") == ACCESSIBLE
        )
        work_items.append(
            {
                "source_record": record,
                "content_blocks": outcome.get("content_blocks") if accessible else [],
                "emit_facts": accessible,
            }
        )
    return source_records, work_items


def _register_source(
    record: object,
    seen_ids: set[str],
    source_records: list[dict[str, Any]],
    track: str,
) -> dict[str, Any] | None:
    if record is None:
        return None
    if not isinstance(record, dict):
        raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)
    source_id = record.get("source_id")
    ownership = record.get("ownership_status")
    source_type = record.get("source_type")
    if not isinstance(source_id, str) or not source_id:
        raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)
    if not isinstance(source_type, str) or not source_type:
        raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)
    if ownership not in OWNERSHIP_VALUES:
        raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)
    if source_id in seen_ids:
        raise NormalizationFailure(ERROR_DUPLICATE_SOURCE_ID, track)
    seen_ids.add(source_id)
    copied = deepcopy(record)
    source_records.append(copied)
    return copied


def _collect_facts(
    work_items: list[dict[str, Any]],
    registry: CompiledRegistry,
    track: str,
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for item in work_items:
        if not item["emit_facts"]:
            continue
        record = item["source_record"]
        if not isinstance(record, dict):
            raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)
        blocks = item["content_blocks"]
        if not isinstance(blocks, list):
            raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)
        source_type = str(record["source_type"])
        ownership = str(record["ownership_status"])
        attribution = "attributed" if source_type == SOURCE_TYPE_CV else ownership
        for block in blocks:
            _validate_block(block, track)
            block_text = str(block["text"])
            locator = str(block["locator"])
            source_id = str(record["source_id"])
            for sentence in split_sentences(block_text):
                matches = find_matches(sentence, registry)
                application = has_application_cue(sentence, registry)
                if emit_qualification_from_source(source_type):
                    for match in qualification_hits(matches):
                        facts.append(
                            _fact(
                                source_id=source_id,
                                locator=locator,
                                fact_type=QUALIFICATION_FACT_TYPE,
                                subject=match.subject,
                                explicit_text=normalize_extracted_text(sentence),
                                evidence_level=QUALIFICATION_EVIDENCE_LEVEL,
                                attribution_status=attribution,
                                rule_id=match.rule_id,
                            )
                        )
                        _enforce_limit(facts, track)
                if sentence_has_qualification(matches):
                    continue
                for match in matches:
                    if match.kind == KIND_QUALIFICATION:
                        continue
                    facts.append(
                        _technical_fact(
                            match=match,
                            source_id=source_id,
                            locator=locator,
                            block_text=block_text,
                            sentence=sentence,
                            application=application,
                            source_type=source_type,
                            attribution=attribution,
                        )
                    )
                    _enforce_limit(facts, track)
    return facts


def _technical_fact(
    *,
    match: Any,
    source_id: str,
    locator: str,
    block_text: str,
    sentence: str,
    application: bool,
    source_type: str,
    attribution: str,
) -> dict[str, Any]:
    fact_type = _fact_type(match.kind, application)
    explicit = (
        normalize_extracted_text(sentence)
        if application
        else _named_only_text(block_text, match.matched_text)
    )
    return _fact(
        source_id=source_id,
        locator=locator,
        fact_type=fact_type,
        subject=match.subject,
        explicit_text=explicit,
        evidence_level=_evidence_level(source_type, attribution, application),
        attribution_status=attribution,
        rule_id=match.rule_id,
    )


def _fact(
    *,
    source_id: str,
    locator: str,
    fact_type: str,
    subject: str,
    explicit_text: str,
    evidence_level: str,
    attribution_status: str,
    rule_id: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "locator": locator,
        "fact_type": fact_type,
        "subject": subject,
        "explicit_text": explicit_text,
        "evidence_level": evidence_level,
        "attribution_status": attribution_status,
        "rule_id": rule_id,
        "review_status": "accepted",
    }


def _fact_type(kind: str, application: bool) -> str:
    if kind == KIND_SKILL:
        return "skill_application" if application else "skill_name"
    return "tool_application" if application else "tool_name"


def _evidence_level(source_type: str, ownership_status: str, application: bool) -> str:
    if source_type == SOURCE_TYPE_CV:
        return "documented" if application else "named_only"
    if application and ownership_status == "attributed":
        return "demonstrated"
    if application:
        return "documented"
    return "named_only"


def _named_only_text(block_text: str, matched_text: str) -> str:
    normalized = normalize_extracted_text(block_text)
    if len(normalized) <= NAMED_ONLY_BOUNDED_CHARS:
        return normalized
    return matched_text


def _validate_block(block: object, track: str) -> None:
    if not isinstance(block, dict):
        raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)
    for key in ("block_id", "locator", "text"):
        value = block.get(key)
        if not isinstance(value, str) or not value:
            raise NormalizationFailure(ERROR_MALFORMED_SOURCE_STRUCTURE, track)


def _enforce_limit(facts: list[dict[str, Any]], track: str) -> None:
    if len(facts) > MAX_EVIDENCE_FACTS:
        raise NormalizationFailure(ERROR_FACT_LIMIT_EXCEEDED, track)


def _deduplicate(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, str, str], int] = {}
    for fact in facts:
        key = (
            fact["subject"],
            fact["fact_type"],
            normalize_extracted_text(fact["explicit_text"]).casefold(),
        )
        existing = index_by_key.get(key)
        if existing is None:
            index_by_key[key] = len(kept)
            kept.append(fact)
            continue
        if _rank(fact) > _rank(kept[existing]):
            kept[existing] = fact
    return kept


def _rank(fact: dict[str, Any]) -> tuple[int, int]:
    return (LEVEL_RANK[fact["evidence_level"]], ATTRIBUTION_RANK[fact["attribution_status"]])


def _with_evidence_id(fact: dict[str, Any], index: int) -> dict[str, Any]:
    assigned = dict(fact)
    assigned["evidence_id"] = f"ev-{index:04d}"
    return assigned


def _assert_outcome_valid(outcome: dict[str, Any], track: str) -> None:
    try:
        fact_validator = _validator(FACT_SCHEMA_PATH)
        for fact in outcome["evidence_facts"]:
            fact_validator.validate(fact)
        _validator(OUTCOME_SCHEMA_PATH).validate(outcome)
    except (ValidationError, TypeError, ValueError):
        raise NormalizationFailure(ERROR_CLASSIFIER_EXCEPTION, track) from None


def _validator(path: Path) -> Draft202012Validator:
    schema = load_json(path)
    if not isinstance(schema, dict):
        msg = f"{path.name} must contain a JSON object"
        raise TypeError(msg)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
