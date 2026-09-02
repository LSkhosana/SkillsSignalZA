"""Validated evidence-fact provenance allowlist for Package J."""

from __future__ import annotations

from functools import lru_cache
from typing import NamedTuple

from app.engine.configuration import load_evidence_rules_v1, load_higher_order_rules_v1

KIND_FACT_TYPES = {
    "skill": ("skill_name", "skill_application"),
    "tool": ("tool_name", "tool_application"),
    "qualification": ("qualification",),
}
HIGHER_ORDER_FACT_TYPES = frozenset(
    {
        "project_proof",
        "project_context",
        "project_process",
        "project_outcome",
        "professional_behaviour",
        "role_alignment",
        "document_quality",
    }
)


class ProvenanceAllowlist(NamedTuple):
    """Frozen (subject, fact_type, rule_id) combinations from H and I registries."""

    triples: frozenset[tuple[str, str, str]]
    subjects: frozenset[str]
    rule_ids: frozenset[str]
    fact_types_by_subject: dict[str, frozenset[str]]


@lru_cache(maxsize=1)
def load_provenance_allowlist() -> ProvenanceAllowlist:
    """Build the validated H+I provenance allowlist."""
    triples: set[tuple[str, str, str]] = set()
    subjects: set[str] = set()
    rule_ids: set[str] = set()
    types_by_subject: dict[str, set[str]] = {}
    evidence = load_evidence_rules_v1()
    for entry in (*evidence["subjects"], *evidence["qualifications"]):
        subject = str(entry["subject"])
        rule_id = str(entry["rule_id"])
        kind = str(entry["kind"])
        fact_types = KIND_FACT_TYPES[kind]
        subjects.add(subject)
        rule_ids.add(rule_id)
        types_by_subject.setdefault(subject, set()).update(fact_types)
        for fact_type in fact_types:
            triples.add((subject, fact_type, rule_id))
    higher = load_higher_order_rules_v1()
    for subject, spec in higher["rules"].items():
        fact_type = str(spec["fact_type"])
        rule_id = str(spec["rule_id"])
        subjects.add(subject)
        rule_ids.add(rule_id)
        types_by_subject.setdefault(subject, set()).add(fact_type)
        triples.add((subject, fact_type, rule_id))
    return ProvenanceAllowlist(
        triples=frozenset(triples),
        subjects=frozenset(subjects),
        rule_ids=frozenset(rule_ids),
        fact_types_by_subject={key: frozenset(value) for key, value in types_by_subject.items()},
    )


def rule_id_for(subject: str, fact_type: str) -> str:
    """Return the unique checked-in rule_id for one allowed subject/type pair."""
    allowlist = load_provenance_allowlist()
    matches = [
        rule_id
        for candidate_subject, candidate_type, rule_id in allowlist.triples
        if candidate_subject == subject and candidate_type == fact_type
    ]
    if len(matches) != 1:
        msg = f"no unique provenance rule for {subject}/{fact_type}"
        raise KeyError(msg)
    return matches[0]
