# Package C golden candidate fixtures

Immutable synthetic examples for Engine Contract 1.2.0. A later scoring
implementation must reproduce these checked-in expected results. It may
not rewrite the fixtures to make new code pass.

The fixtures do not call the public internet, a live database, Supabase,
or any model. They contain no production scoring or selection code.

## Contents

- `manifest.json` — package `1.0.0`, approved, contract `1.2.0`, rubric `V2`, exactly 22 entries.
- `golden_fixture.schema.json` — fixture-only schema; unknown top-level properties are rejected.
- `c01_...json` through `c22_...json` — one fixture per minimum acceptance requirement.

## Integrity

Canonical fixture hashing uses parsed JSON serialized with UTF-8, sorted
keys, and separators `,` and `:`. Hash the canonical bytes, not
platform-specific file bytes. Tests fail when fixture content changes
without the matching manifest hash.

Intentional fixture changes require product review, a fixture-package
version decision, updated hashes, and an explanation.
