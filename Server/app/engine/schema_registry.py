"""Draft 2020-12 validators that can resolve frozen sibling schema $ids."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from app.engine.configuration import load_json

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


@lru_cache(maxsize=1)
def schema_registry() -> Registry:
    """Return a registry of every packaged engine JSON Schema."""
    resources: list[tuple[str, Resource]] = []
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        document = load_json(path)
        if not isinstance(document, dict) or "$id" not in document:
            continue
        resources.append((str(document["$id"]), Resource.from_contents(document)))
    return Registry().with_resources(resources)


def draft_validator(filename: str) -> Draft202012Validator:
    """Return a Draft 2020-12 validator for one packaged schema filename."""
    schema = load_json(SCHEMA_DIR / filename)
    if not isinstance(schema, dict):
        msg = f"{filename} must contain a JSON object"
        raise TypeError(msg)
    return Draft202012Validator(
        schema,
        registry=schema_registry(),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
