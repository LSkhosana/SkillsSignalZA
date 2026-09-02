"""Package I higher-order project/work evidence classification."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.classification.context import (
    APPLICATION_TYPES,
    behaviour_and_role_facts,
    compile_context_patterns,
    document_quality_facts,
    selected_track_target_present,
)
from app.engine.classification.cues import (
    EVIDENCE_ID_RE,
    FROM_TO_RE,
    compile_group,
    has_cue,
    token_pattern,
)
from app.engine.classification.outcomes import (
    ACCESSIBLE,
    APPROVED_TRACKS,
    CLASSIFIER_VERSION,
    ERROR_CLASSIFIER_EXCEPTION,
    ERROR_DUPLICATE_EVIDENCE_ID,
    ERROR_DUPLICATE_SOURCE_ID,
    ERROR_INVALID_CV_EXTRACTION,
    ERROR_INVALID_EVIDENCE_FACT,
    ERROR_INVALID_LINK_RETRIEVAL,
    ERROR_INVALID_NORMALIZATION,
    ERROR_INVALID_TRACK,
    ERROR_NORMALIZATION_FAILED,
    ERROR_RULESET_INVALID,
    ERROR_SOURCE_MISMATCH,
    ERROR_UNKNOWN_SOURCE,
    SOURCE_TYPE_CV,
    ClassificationFailure,
    canonical_outcome,
    failed_outcome,
    ordered_unique_flags,
    review_state,
)
from app.engine.configuration import load_higher_order_rules_v1
from app.engine.evidence.matching import split_sentences
from app.engine.evidence.outcomes import NAMED_ONLY_BOUNDED_CHARS
from app.engine.extraction.text import normalize_extracted_text
from app.engine.schema_registry import draft_validator

LEVEL_RANK = {"demonstrated": 3, "documented": 2, "named_only": 1}
ATTR_RANK = {"attributed": 3, "unclear": 2, "conflicting": 1}


def classify_higher_order_evidence(
    *,
    track: str,
    normalization: dict[str, Any],
    cv_extraction: dict[str, Any],
    link_retrievals: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Append deterministic higher-order facts to a Package H bundle."""
    safe_track = track if isinstance(track, str) else ""
    try:
        outcome = _classify(
            track=track,
            normalization=normalization,
            cv_extraction=cv_extraction,
            link_retrievals=link_retrievals,
        )
    except ClassificationFailure as exc:
        outcome = failed_outcome(exc.error_code, track=exc.track)
    except Exception:
        outcome = failed_outcome(ERROR_CLASSIFIER_EXCEPTION, track=safe_track)
    draft_validator("higher_order_classification.schema.json").validate(outcome)
    return outcome


def _classify(
    *,
    track: object,
    normalization: object,
    cv_extraction: object,
    link_retrievals: object,
) -> dict[str, Any]:
    safe_track = track if isinstance(track, str) else ""
    if safe_track not in APPROVED_TRACKS:
        raise ClassificationFailure(ERROR_INVALID_TRACK, safe_track)
    try:
        rules = load_higher_order_rules_v1()
        compiled = _compile_rules(rules)
    except (OSError, TypeError, ValueError, KeyError):
        raise ClassificationFailure(ERROR_RULESET_INVALID, safe_track) from None
    bundle = _validated_normalization(normalization, safe_track)
    cv_outcome = _validated_cv(cv_extraction, safe_track)
    links = _validated_links(link_retrievals, safe_track)
    preserved = [deepcopy(fact) for fact in bundle["evidence_facts"]]
    source_records = deepcopy(list(bundle["source_records"]))
    _assert_source_integrity(source_records, cv_outcome, links, safe_track)
    _assert_facts_reference_sources(preserved, source_records, safe_track)
    _validate_facts(preserved, safe_track)
    flags = list(bundle.get("review_flags") or [])
    next_index = _next_evidence_index(preserved)
    appended: list[dict[str, Any]] = []

    def emit(fact: dict[str, Any]) -> None:
        appended.append(fact)

    _classify_cv(
        track=safe_track,
        cv_outcome=cv_outcome,
        h_facts=preserved,
        compiled=compiled,
        emit=emit,
        flags=flags,
    )
    for link in links:
        _classify_link(
            track=safe_track,
            link=link,
            h_facts=preserved,
            compiled=compiled,
            emit=emit,
            flags=flags,
        )
    _drop_screenshot_when_context_exists(appended)
    cv_record = cv_outcome.get("source_record") if isinstance(cv_outcome, dict) else None
    if isinstance(cv_record, dict):
        appended.extend(
            document_quality_facts(
                cv_blocks=list(cv_outcome.get("content_blocks") or []),
                cv_source_id=str(cv_record["source_id"]),
                h_facts=preserved,
                appended=appended,
                compiled=compiled,
                make_fact=_bound_make_fact(compiled, SOURCE_TYPE_CV, "attributed"),
            )
        )
    if selected_track_target_present(preserved + appended, safe_track):
        flags[:] = [flag for flag in flags if flag != "TRACK_MISMATCH"]
    deduped = _deduplicate_new(appended)
    assigned, next_index = _assign_ids(deduped, next_index)
    _validate_facts(assigned, safe_track)
    combined = preserved + assigned
    _assert_unique_ids(combined, safe_track)
    _assert_facts_reference_sources(combined, source_records, safe_track)
    _validate_facts(combined, safe_track)
    if any(fact["attribution_status"] == "unclear" for fact in assigned):
        flags.append("OWNERSHIP_UNCLEAR")
    unique_flags = ordered_unique_flags(flags)
    if selected_track_target_present(combined, safe_track):
        unique_flags = [flag for flag in unique_flags if flag != "TRACK_MISMATCH"]
    state, error_code = review_state(unique_flags)
    outcome = canonical_outcome(
        state=state,
        error_code=error_code,
        track=safe_track,
        source_records=source_records,
        evidence_facts=combined,
        review_flags=unique_flags,
    )
    draft_validator("higher_order_classification.schema.json").validate(outcome)
    return outcome


def _classify_cv(
    *,
    track: str,
    cv_outcome: dict[str, Any],
    h_facts: list[dict[str, Any]],
    compiled: dict[str, Any],
    emit: Any,
    flags: list[str],
) -> None:
    record = cv_outcome.get("source_record")
    if not isinstance(record, dict):
        return
    make_fact = _bound_make_fact(compiled, SOURCE_TYPE_CV, "attributed")
    for block in cv_outcome.get("content_blocks") or []:
        _classify_block(
            track=track,
            source_type=SOURCE_TYPE_CV,
            record=record,
            block=block,
            h_facts=h_facts,
            compiled=compiled,
            make_fact=make_fact,
            emit=emit,
            flags=flags,
            project_source=False,
        )


def _classify_link(
    *,
    track: str,
    link: dict[str, Any],
    h_facts: list[dict[str, Any]],
    compiled: dict[str, Any],
    emit: Any,
    flags: list[str],
) -> None:
    record = link.get("source_record")
    if not isinstance(record, dict):
        return
    if record.get("access_status") != ACCESSIBLE or link.get("state") != "COMPLETED":
        return
    source_type = str(record["source_type"])
    ownership = str(record["ownership_status"])
    make_fact = _bound_make_fact(compiled, source_type, ownership)
    project_like = source_type in compiled["project_source_types"]
    blocks = list(link.get("content_blocks") or [])
    if project_like and blocks:
        first = blocks[0]
        emit(
            make_fact(
                source_id=str(record["source_id"]),
                locator=str(first["locator"]),
                subject="accessible_submitted_work",
                explicit_text=_bounded_text(str(first["text"])),
            )
        )
    for block in blocks:
        _classify_block(
            track=track,
            source_type=source_type,
            record=record,
            block=block,
            h_facts=h_facts,
            compiled=compiled,
            make_fact=make_fact,
            emit=emit,
            flags=flags,
            project_source=project_like,
        )


def _classify_block(
    *,
    track: str,
    source_type: str,
    record: dict[str, Any],
    block: dict[str, Any],
    h_facts: list[dict[str, Any]],
    compiled: dict[str, Any],
    make_fact: Any,
    emit: Any,
    flags: list[str],
    project_source: bool,
) -> None:
    text = str(block.get("text") or "")
    locator = str(block.get("locator") or "")
    source_id = str(record["source_id"])
    for sentence in split_sentences(text):
        artifact = has_cue(sentence, compiled["artifact"])
        bounded = project_source or artifact
        if source_type == SOURCE_TYPE_CV and artifact and _has_url_or_repo(sentence, compiled):
            emit(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject="cv_project_reference",
                    explicit_text=normalize_extracted_text(sentence),
                )
            )
        if bounded and has_cue(sentence, compiled["context"]):
            subject = (
                "software_project_context"
                if track == "software_engineering"
                else "analytics_project_context"
            )
            emit(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject=subject,
                    explicit_text=normalize_extracted_text(sentence),
                )
            )
        apps = _application_facts(h_facts, source_id, locator, sentence)
        if track == "software_engineering" and bounded and apps:
            emit(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject="se_technical_process",
                    explicit_text=normalize_extracted_text(sentence),
                )
            )
            subjects = {fact["subject"] for fact in apps}
            if len(subjects) >= 2 or has_cue(sentence, compiled["architecture"]):
                emit(
                    make_fact(
                        source_id=source_id,
                        locator=locator,
                        subject="se_technical_depth_ownership",
                        explicit_text=normalize_extracted_text(sentence),
                    )
                )
        if track == "data_analytics" and bounded:
            analysis_apps = [
                fact for fact in apps if fact["subject"] in compiled["da_analysis_subjects"]
            ]
            if analysis_apps:
                emit(
                    make_fact(
                        source_id=source_id,
                        locator=locator,
                        subject="da_analysis_process",
                        explicit_text=normalize_extracted_text(sentence),
                    )
                )
            tool_apps = [fact for fact in apps if fact["fact_type"] == "tool_application"]
            if len({fact["subject"] for fact in tool_apps}) >= 2 and _has_integration(
                sentence, compiled
            ):
                emit(
                    make_fact(
                        source_id=source_id,
                        locator=locator,
                        subject="da_tool_integration",
                        explicit_text=normalize_extracted_text(sentence),
                    )
                )
        if bounded and has_cue(sentence, compiled["documentation"]):
            subject = (
                "project_documentation"
                if track == "software_engineering"
                else "project_reproducibility"
            )
            emit(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject=subject,
                    explicit_text=normalize_extracted_text(sentence),
                )
            )
        if bounded and has_cue(sentence, compiled["outcome"]):
            subject = (
                "software_project_outcome"
                if track == "software_engineering"
                else "analytics_project_outcome"
            )
            emit(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject=subject,
                    explicit_text=normalize_extracted_text(sentence),
                )
            )
            if (
                track == "data_analytics"
                and has_cue(sentence, compiled["findings"])
                and has_cue(sentence, compiled["visual"])
            ):
                emit(
                    make_fact(
                        source_id=source_id,
                        locator=locator,
                        subject="analytics_findings_visual_communication",
                        explicit_text=normalize_extracted_text(sentence),
                    )
                )
        if track == "data_analytics" and _is_dashboard_screenshot(sentence) and bounded:
            emit(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject="context_free_dashboard_screenshot",
                    explicit_text=normalize_extracted_text(sentence),
                )
            )
        for fact in behaviour_and_role_facts(
            track=track,
            source_type=source_type,
            source_id=source_id,
            locator=locator,
            sentence=sentence,
            rules=compiled["raw"],
            compiled=compiled,
            make_fact=make_fact,
            flags=flags,
        ):
            emit(fact)


def _has_url_or_repo(text: str, compiled: dict[str, Any]) -> bool:
    return has_cue(text, compiled["url_prefixes"]) or has_cue(text, compiled["repository"])


def _has_integration(text: str, compiled: dict[str, Any]) -> bool:
    return has_cue(text, compiled["integration"]) or FROM_TO_RE.search(text) is not None


def _is_dashboard_screenshot(text: str) -> bool:
    lowered = text.casefold()
    return "dashboard" in lowered and "screenshot" in lowered


def _application_facts(
    h_facts: list[dict[str, Any]], source_id: str, locator: str, sentence: str
) -> list[dict[str, Any]]:
    normalized = normalize_extracted_text(sentence)
    found: list[dict[str, Any]] = []
    for fact in h_facts:
        if fact["source_id"] != source_id or fact["locator"] != locator:
            continue
        if fact["fact_type"] not in APPLICATION_TYPES:
            continue
        explicit = str(fact["explicit_text"])
        if explicit == normalized or explicit in sentence or normalized in explicit:
            found.append(fact)
    return found


def _bound_make_fact(compiled: dict[str, Any], source_type: str, ownership: str) -> Any:
    def make_fact(
        *,
        source_id: str,
        locator: str,
        subject: str,
        explicit_text: str,
        evidence_level: str | None = None,
        **_ignored: Any,
    ) -> dict[str, Any]:
        spec = compiled["rules"][subject]
        level = evidence_level or _evidence_level(source_type, ownership, spec["fact_type"])
        attribution = "attributed" if source_type == SOURCE_TYPE_CV else ownership
        if source_type != SOURCE_TYPE_CV and attribution == "unclear" and level == "demonstrated":
            level = "documented"
        if source_type == SOURCE_TYPE_CV and spec["fact_type"] != "document_quality":
            if level == "demonstrated":
                level = "documented"
        return {
            "source_id": source_id,
            "locator": locator,
            "fact_type": spec["fact_type"],
            "subject": subject,
            "explicit_text": explicit_text,
            "evidence_level": level,
            "attribution_status": attribution,
            "rule_id": spec["rule_id"],
            "review_status": "accepted",
        }

    return make_fact


def _evidence_level(source_type: str, ownership: str, fact_type: str) -> str:
    if source_type == SOURCE_TYPE_CV:
        return "demonstrated" if fact_type == "document_quality" else "documented"
    if ownership == "attributed":
        return "demonstrated"
    return "documented"


def _drop_screenshot_when_context_exists(facts: list[dict[str, Any]]) -> None:
    contextual = {
        fact["source_id"] for fact in facts if fact["subject"] == "analytics_project_context"
    }
    facts[:] = [
        fact
        for fact in facts
        if not (
            fact["subject"] == "context_free_dashboard_screenshot"
            and fact["source_id"] in contextual
        )
    ]


def _bounded_text(text: str) -> str:
    normalized = normalize_extracted_text(text)
    if len(normalized) <= NAMED_ONLY_BOUNDED_CHARS:
        return normalized
    return normalized[:NAMED_ONLY_BOUNDED_CHARS].rstrip()


def _next_evidence_index(facts: list[dict[str, Any]]) -> int:
    highest = 0
    for fact in facts:
        match = EVIDENCE_ID_RE.fullmatch(str(fact.get("evidence_id") or ""))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _assign_ids(facts: list[dict[str, Any]], start: int) -> tuple[list[dict[str, Any]], int]:
    assigned: list[dict[str, Any]] = []
    index = start
    for fact in facts:
        item = dict(fact)
        item["evidence_id"] = f"ev-{index:04d}"
        assigned.append(item)
        index += 1
    return assigned, index


def _deduplicate_new(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, str, str, str], int] = {}
    for fact in facts:
        key = (
            fact["fact_type"],
            fact["subject"],
            normalize_extracted_text(fact["explicit_text"]).casefold(),
            fact["locator"],
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
    return (LEVEL_RANK[fact["evidence_level"]], ATTR_RANK[fact["attribution_status"]])


def _assert_unique_ids(facts: list[dict[str, Any]], track: str) -> None:
    ids = [fact["evidence_id"] for fact in facts]
    if len(ids) != len(set(ids)):
        raise ClassificationFailure(ERROR_DUPLICATE_EVIDENCE_ID, track)


def _compile_rules(rules: dict[str, Any]) -> dict[str, Any]:
    if rules.get("classifier_version") != CLASSIFIER_VERSION:
        msg = "invalid higher-order rules"
        raise ValueError(msg)
    return {
        "raw": rules,
        "rules": rules["rules"],
        "project_source_types": set(rules["project_source_types"]),
        "da_analysis_subjects": set(rules["da_analysis_subjects"]),
        "artifact": compile_group(rules, "artifact_markers"),
        "url_prefixes": token_pattern(list(rules["url_prefixes"]), prefix_only=True),
        "repository": compile_group(rules, "repository_markers"),
        "context": compile_group(rules, "context_markers"),
        "architecture": compile_group(rules, "architecture_cues"),
        "integration": compile_group(rules, "integration_cues"),
        "documentation": compile_group(rules, "documentation_cues"),
        "outcome": compile_group(rules, "outcome_markers"),
        "findings": compile_group(rules, "findings_cues"),
        "visual": compile_group(rules, "visual_cues"),
        **compile_context_patterns(rules),
    }


def _validated_normalization(normalization: object, track: str) -> dict[str, Any]:
    if not isinstance(normalization, dict):
        raise ClassificationFailure(ERROR_INVALID_NORMALIZATION, track)
    try:
        draft_validator("evidence_normalization.schema.json").validate(normalization)
    except (ValidationError, TypeError, ValueError):
        raise ClassificationFailure(ERROR_INVALID_NORMALIZATION, track) from None
    if normalization.get("state") == "EVIDENCE_NORMALIZATION_FAILED":
        raise ClassificationFailure(ERROR_NORMALIZATION_FAILED, track)
    if normalization.get("track") != track:
        raise ClassificationFailure(ERROR_INVALID_TRACK, track)
    return normalization


def _validated_cv(cv_extraction: object, track: str) -> dict[str, Any]:
    if not isinstance(cv_extraction, dict):
        raise ClassificationFailure(ERROR_INVALID_CV_EXTRACTION, track)
    try:
        draft_validator("cv_extraction.schema.json").validate(cv_extraction)
    except (ValidationError, TypeError, ValueError):
        raise ClassificationFailure(ERROR_INVALID_CV_EXTRACTION, track) from None
    if cv_extraction.get("state") != "COMPLETED":
        raise ClassificationFailure(ERROR_INVALID_CV_EXTRACTION, track)
    if not isinstance(cv_extraction.get("source_record"), dict):
        raise ClassificationFailure(ERROR_INVALID_CV_EXTRACTION, track)
    return cv_extraction


def _validated_links(link_retrievals: object, track: str) -> list[dict[str, Any]]:
    if link_retrievals is None:
        return []
    if not isinstance(link_retrievals, (list, tuple)):
        raise ClassificationFailure(ERROR_INVALID_LINK_RETRIEVAL, track)
    validator = draft_validator("link_retrieval.schema.json")
    validated: list[dict[str, Any]] = []
    for outcome in link_retrievals:
        if not isinstance(outcome, dict):
            raise ClassificationFailure(ERROR_INVALID_LINK_RETRIEVAL, track)
        try:
            validator.validate(outcome)
        except (ValidationError, TypeError, ValueError):
            raise ClassificationFailure(ERROR_INVALID_LINK_RETRIEVAL, track) from None
        validated.append(outcome)
    return validated


def _assert_source_integrity(
    source_records: list[dict[str, Any]],
    cv_outcome: dict[str, Any],
    links: list[dict[str, Any]],
    track: str,
) -> None:
    expected: list[dict[str, Any]] = [cv_outcome["source_record"]]
    for outcome in links:
        record = outcome.get("source_record")
        if record is None:
            continue
        if not isinstance(record, dict):
            raise ClassificationFailure(ERROR_INVALID_LINK_RETRIEVAL, track)
        expected.append(record)
    seen: set[str] = set()
    for record in expected:
        source_id = str(record.get("source_id") or "")
        if not source_id:
            raise ClassificationFailure(ERROR_SOURCE_MISMATCH, track)
        if source_id in seen:
            raise ClassificationFailure(ERROR_DUPLICATE_SOURCE_ID, track)
        seen.add(source_id)
    if source_records != expected:
        raise ClassificationFailure(ERROR_SOURCE_MISMATCH, track)


def _assert_facts_reference_sources(
    facts: list[dict[str, Any]], source_records: list[dict[str, Any]], track: str
) -> None:
    known = {str(record["source_id"]) for record in source_records}
    for fact in facts:
        if str(fact.get("source_id") or "") not in known:
            raise ClassificationFailure(ERROR_UNKNOWN_SOURCE, track)


def _validate_facts(facts: list[dict[str, Any]], track: str) -> None:
    validator = draft_validator("evidence_fact.schema.json")
    for fact in facts:
        try:
            validator.validate(fact)
        except (ValidationError, TypeError, ValueError):
            raise ClassificationFailure(ERROR_INVALID_EVIDENCE_FACT, track) from None
