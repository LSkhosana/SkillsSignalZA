"""Regression for the post-#41 live CV's generic qualification evidence."""

from __future__ import annotations

from app.engine.configuration import load_criterion_binding_rules_v1, load_rubric_v2
from app.engine.context.assembly import _qualification_route

TRACK = "software_engineering"


def _qualification(evidence_id: str, subject: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "fact_type": "qualification",
        "subject": subject,
        "explicit_text": text,
    }


def _route(facts: list[dict[str, str]]) -> tuple[str, list[str], list[str]]:
    flags: list[str] = []
    anchor, ids = _qualification_route(
        TRACK,
        facts,
        flags,
        load_criterion_binding_rules_v1(),
        load_rubric_v2(),
    )
    return anchor, ids, flags


def test_generic_degree_and_certificate_do_not_block_entire_assessment() -> None:
    """Mirror the live incident's two generic, unrouteable qualification facts."""
    anchor, ids, flags = _route(
        [
            _qualification("ev-0026", "bachelor_degree", "Bachelor"),
            _qualification("ev-0027", "certificate", "Certificate"),
        ]
    )
    assert (anchor, ids, flags) == ("se.qual.none", [], [])


def test_generic_qualification_alone_is_neither_credit_nor_review() -> None:
    assert _route([_qualification("ev-1", "bachelor_degree", "Bachelor")]) == (
        "se.qual.none",
        [],
        [],
    )


def test_generic_qualification_does_not_obscure_separate_supported_route() -> None:
    assert _route(
        [
            _qualification("ev-1", "bachelor_degree", "Bachelor"),
            _qualification("ev-2", "bachelor_degree", "Completed BSc Computer Science"),
        ]
    ) == ("se.qual.completed", ["ev-2"], [])


def test_genuinely_conflicting_status_within_one_qualification_still_blocks() -> None:
    qualification = _qualification(
        "ev-1", "bachelor_degree", "Completed BSc Computer Science, currently studying"
    )
    anchor, ids, flags = _route([qualification])
    assert anchor == "se.qual.none"
    assert ids == []
    assert flags == ["MATERIAL_CLASSIFICATION_AMBIGUITY"]
