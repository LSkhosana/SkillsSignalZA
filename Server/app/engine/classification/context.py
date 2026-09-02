"""Role-alignment, professional-behaviour, and document-quality classification."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.engine.classification.cues import YEAR_RE, has_cue, token_pattern
from app.engine.classification.outcomes import SOURCE_TYPE_CV
from app.engine.extraction.text import normalize_extracted_text

APPLICATION_TYPES = frozenset({"skill_application", "tool_application"})
NAME_TYPES = frozenset({"skill_name", "tool_name"})
PROCESS_TYPES = frozenset({"project_process"})
CONTEXT_OR_OUTCOME = frozenset({"project_context", "project_outcome", "professional_behaviour"})


def behaviour_and_role_facts(
    *,
    track: str,
    source_type: str,
    source_id: str,
    locator: str,
    sentence: str,
    rules: dict[str, Any],
    compiled: dict[str, Any],
    make_fact: Callable[..., dict[str, Any]],
    flags: list[str],
) -> list[dict[str, Any]]:
    """Emit professional-behaviour and target-role facts from one sentence."""
    facts: list[dict[str, Any]] = []
    explicit = normalize_extracted_text(sentence)
    if not explicit:
        return facts
    if not _is_forbidden_label_only(explicit, compiled):
        facts.extend(
            _behaviour_facts(
                source_id=source_id,
                locator=locator,
                explicit=explicit,
                track=track,
                compiled=compiled,
                make_fact=make_fact,
            )
        )
    facts.extend(
        _target_role_facts(
            track=track,
            source_type=source_type,
            source_id=source_id,
            locator=locator,
            explicit=explicit,
            compiled=compiled,
            make_fact=make_fact,
            flags=flags,
        )
    )
    return facts


def document_quality_facts(
    *,
    cv_blocks: list[dict[str, str]],
    cv_source_id: str,
    h_facts: list[dict[str, Any]],
    appended: list[dict[str, Any]],
    compiled: dict[str, Any],
    make_fact: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    """Inspect CV structure and wording for document-quality facts."""
    if not cv_blocks:
        return []
    facts: list[dict[str, Any]] = []
    headings = _heading_hits(cv_blocks, compiled["heading"])
    first_locator = cv_blocks[0]["locator"]
    first_text = normalize_extracted_text(cv_blocks[0]["text"])
    readability = _readability_level(headings, cv_blocks)
    if readability is not None:
        facts.append(
            make_fact(
                source_id=cv_source_id,
                locator=first_locator,
                subject="structured_readability",
                explicit_text=first_text,
                evidence_level=readability,
                source_type=SOURCE_TYPE_CV,
                ownership="attributed",
            )
        )
    cv_h = [fact for fact in h_facts if fact["source_id"] == cv_source_id]
    specificity = _specificity_level(cv_h, cv_blocks)
    if specificity is not None:
        facts.append(
            make_fact(
                source_id=cv_source_id,
                locator=first_locator,
                subject="claim_specificity",
                explicit_text=first_text,
                evidence_level=specificity,
                source_type=SOURCE_TYPE_CV,
                ownership="attributed",
            )
        )
    combined = cv_h + [fact for fact in appended if fact["source_id"] == cv_source_id]
    description = _description_level(combined, cv_blocks)
    if description is not None:
        facts.append(
            make_fact(
                source_id=cv_source_id,
                locator=first_locator,
                subject="description_evidence",
                explicit_text=first_text,
                evidence_level=description,
                source_type=SOURCE_TYPE_CV,
                ownership="attributed",
            )
        )
    return facts


def selected_track_target_present(facts: list[dict[str, Any]], track: str) -> bool:
    """Return True when a selected-track target-role fact exists."""
    subject = (
        "software_engineering_target"
        if track == "software_engineering"
        else "data_analytics_target"
    )
    return any(
        fact["subject"] == subject and fact["fact_type"] == "role_alignment" for fact in facts
    )


def _behaviour_facts(
    *,
    source_id: str,
    locator: str,
    explicit: str,
    track: str,
    compiled: dict[str, Any],
    make_fact: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    pairs: list[tuple[str, Any]] = [
        ("collaboration", compiled["collaboration"]),
        ("communication", compiled["communication"]),
        ("initiative", compiled["initiative"]),
    ]
    if has_cue(explicit, compiled["professional_context"]) and (
        has_cue(explicit, compiled["collaboration"])
        or has_cue(explicit, compiled["communication"])
        or has_cue(explicit, compiled["initiative"])
        or has_cue(explicit, compiled["self_management"])
        or has_cue(explicit, compiled["problem_solving"])
        or "responsible for" in explicit.casefold()
    ):
        pairs.append(("professional_exposure", compiled["professional_context"]))
    if track == "software_engineering":
        if has_cue(explicit, compiled["self_management"]) or has_cue(
            explicit, compiled["problem_solving"]
        ):
            facts.append(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject="self_management_problem_solving",
                    explicit_text=explicit,
                    source_type="pending",
                    ownership="pending",
                )
            )
    else:
        if has_cue(explicit, compiled["problem_solving"]):
            pairs.append(("problem_solving", compiled["problem_solving"]))
        if has_cue(explicit, compiled["self_management"]):
            pairs.append(("self_management", compiled["self_management"]))
        if has_cue(explicit, compiled["attention"]):
            pairs.append(("attention_to_detail", compiled["attention"]))
    seen: set[str] = {fact["subject"] for fact in facts}
    for subject, pattern in pairs:
        if subject in seen:
            continue
        if has_cue(explicit, pattern):
            seen.add(subject)
            facts.append(
                make_fact(
                    source_id=source_id,
                    locator=locator,
                    subject=subject,
                    explicit_text=explicit,
                    source_type="pending",
                    ownership="pending",
                )
            )
    return facts


def _target_role_facts(
    *,
    track: str,
    source_type: str,
    source_id: str,
    locator: str,
    explicit: str,
    compiled: dict[str, Any],
    make_fact: Callable[..., dict[str, Any]],
    flags: list[str],
) -> list[dict[str, Any]]:
    selected = compiled["se_target"] if track == "software_engineering" else compiled["da_target"]
    opposite = compiled["da_target"] if track == "software_engineering" else compiled["se_target"]
    selected_subject = (
        "software_engineering_target"
        if track == "software_engineering"
        else "data_analytics_target"
    )
    opposite_subject = (
        "data_analytics_target"
        if track == "software_engineering"
        else "software_engineering_target"
    )
    has_target_cue = has_cue(explicit, compiled["target_cues"])
    has_selected = has_cue(explicit, selected)
    has_opposite = has_cue(explicit, opposite)
    if has_target_cue and has_opposite and not has_selected:
        flags.append("TRACK_MISMATCH")
        return [
            make_fact(
                source_id=source_id,
                locator=locator,
                subject=opposite_subject,
                explicit_text=explicit,
                evidence_level="documented" if source_type == SOURCE_TYPE_CV else None,
                source_type="pending",
                ownership="pending",
            )
        ]
    if has_selected and has_target_cue:
        return [
            make_fact(
                source_id=source_id,
                locator=locator,
                subject=selected_subject,
                explicit_text=explicit,
                evidence_level="documented" if source_type == SOURCE_TYPE_CV else None,
                source_type="pending",
                ownership="pending",
            )
        ]
    if has_selected and source_type == SOURCE_TYPE_CV and not _looks_like_employment(explicit):
        return [
            make_fact(
                source_id=source_id,
                locator=locator,
                subject=selected_subject,
                explicit_text=explicit,
                evidence_level="named_only",
                source_type=SOURCE_TYPE_CV,
                ownership="attributed",
            )
        ]
    return []


def _looks_like_employment(text: str) -> bool:
    lowered = f" {text.casefold()} "
    if YEAR_RE.search(text):
        return True
    return any(
        marker in lowered for marker in (" at ", "employed", "experience as", "work history")
    )


def _is_forbidden_label_only(text: str, compiled: dict[str, Any]) -> bool:
    if not has_cue(text, compiled["forbidden"]):
        return False
    action = (
        has_cue(text, compiled["collaboration"])
        or has_cue(text, compiled["communication"])
        or has_cue(text, compiled["initiative"])
        or has_cue(text, compiled["self_management"])
        or has_cue(text, compiled["problem_solving"])
        or has_cue(text, compiled["attention"])
    )
    return not action


def _heading_hits(blocks: list[dict[str, str]], heading_pattern: Any) -> set[str]:
    found: set[str] = set()
    if heading_pattern is None:
        return found
    for block in blocks:
        text = normalize_extracted_text(block["text"]).casefold()
        match = heading_pattern.search(text)
        if match and text == match.group(0).casefold():
            found.add(match.group(0).casefold())
    return found


def _readability_level(headings: set[str], blocks: list[dict[str, str]]) -> str | None:
    long_block = any(len(block["text"]) > 1200 for block in blocks)
    count = len(blocks)
    distinct = len(headings)
    if distinct >= 3 and count >= 6 and not long_block:
        return "demonstrated"
    if distinct >= 2 and count >= 4:
        return "documented"
    if distinct >= 1:
        return "named_only"
    return None


def _specificity_level(cv_h: list[dict[str, Any]], blocks: list[dict[str, str]]) -> str | None:
    applications = [fact for fact in cv_h if fact["fact_type"] in APPLICATION_TYPES]
    names = [fact for fact in cv_h if fact["fact_type"] in NAME_TYPES]
    qualifying = [fact for fact in applications if len(str(fact["explicit_text"]).split()) >= 6]
    locators = {fact["locator"] for fact in applications}
    if len(applications) >= 3 and len(locators) >= 2 and len(qualifying) >= 2:
        return "demonstrated"
    if qualifying:
        return "documented"
    if names or applications:
        return "named_only"
    return None


def _description_level(cv_facts: list[dict[str, Any]], blocks: list[dict[str, str]]) -> str | None:
    by_locator: dict[str, list[dict[str, Any]]] = {}
    for fact in cv_facts:
        by_locator.setdefault(fact["locator"], []).append(fact)
    qualifying = 0
    has_application = False
    for group in by_locator.values():
        has_app = any(
            fact["fact_type"] in APPLICATION_TYPES or fact["fact_type"] in PROCESS_TYPES
            for fact in group
        )
        has_extra = any(fact["fact_type"] in CONTEXT_OR_OUTCOME for fact in group)
        if has_app:
            has_application = True
        if has_app and has_extra:
            qualifying += 1
    if qualifying >= 2:
        return "demonstrated"
    if qualifying >= 1:
        return "documented"
    if has_application:
        return "named_only"
    return None


def compile_context_patterns(rules: dict[str, Any]) -> dict[str, Any]:
    """Compile role/behaviour/quality cue patterns."""
    return {
        "forbidden": token_pattern(list(rules["forbidden_labels"])),
        "collaboration": token_pattern(list(rules["collaboration_cues"])),
        "communication": token_pattern(list(rules["communication_cues"])),
        "professional_context": token_pattern(list(rules["professional_context_markers"])),
        "initiative": token_pattern(list(rules["initiative_cues"])),
        "self_management": token_pattern(list(rules["self_management_cues"])),
        "problem_solving": token_pattern(list(rules["problem_solving_cues"])),
        "attention": token_pattern(list(rules["attention_cues"])),
        "se_target": token_pattern(list(rules["se_target_phrases"])),
        "da_target": token_pattern(list(rules["da_target_phrases"])),
        "target_cues": token_pattern(list(rules["target_cues"])),
        "heading": token_pattern(list(rules["heading_cues"])),
    }
