# SkillSignalZA Package C.1 Scoring-Context Fixture Correction — Implementation Brief V1

**Status:** Approved under delegated product authority  
**Decision date:** 31 August 2026  
**Contract:** SkillSignalZA Readiness Report Engine Contract V1.2, version 1.2.0  
**Rubric:** V2 — Launch Candidate  
**Fixture package target:** 1.0.1  
**Implementation target:** Tests branch in LSkhosana/SkillsSignalZA

## 1. Purpose

Package C correctly freezes 22 expected outcomes, but the current fixture inputs do not contain every classification required to reproduce those outcomes.

Two examples prove the gap:

- Qualification evidence facts identify the qualification criterion but do not identify the approved qualification route, such as se.qual.completed or da.qual.completed.
- C12 expects rubric.v2.da.rule.context_free_dashboard to fire, but the input facts and source records contain no machine-readable trigger for that rule.

A production scorer must not recover either value from expected.assessment_result, fixture titles, descriptions, filenames, free-text guessing, or hard-coded fixture IDs.

Package C.1 adds the missing scoring-context input. It does not change a point, anchor, cap, band, catalogue item, expected outcome, or Contract 1.2 scoring rule.

## 2. Decision

Add one explicit, validated scoring_context object to every track-bearing golden fixture. It records the frozen classification decisions produced before the pure scoring layer begins.

The scoring layer receives:

1. assessment_input;
2. source_records;
3. normalized evidence_facts;
4. scoring_context;
5. run identity values.

The scoring layer maps the supplied classifications through the locked rubric. It does not inspect raw files, classify free text, infer a qualification route, or decide whether a special evidence-classification rule was observed.

## 3. Required scoring-context schema

Create:

- Server/app/schemas/scoring_context.schema.json

The schema must use JSON Schema draft 2020-12, reject unknown properties, and require:

- contract_version, exactly 1.2.0;
- rubric_version, exactly V2;
- track, exactly software_engineering or data_analytics;
- criterion_bindings;
- rule_triggers;
- review_flags;
- project_exclusion_ids.

Each criterion_bindings entry must contain only:

- criterion_id;
- anchor;
- evidence_ids.

Rules:

- criterion_id values are unique in the array.
- Every criterion belongs to the selected track.
- Ordinary anchors are demonstrated, documented, named_only, or missing_unverifiable.
- Qualification anchors are approved track-specific qualification route IDs.
- Exactly one qualification criterion binding is required, including the track-specific none route where no qualification evidence exists.
- An omitted ordinary criterion means missing_unverifiable with no evidence IDs.
- An explicit missing_unverifiable binding is allowed when needed to retain an audited lower-defensible classification.
- Every evidence ID refers to one evidence_fact in the same fixture.
- Every non-zero ordinary binding and every non-none qualification route references at least one accepted evidence fact.
- One evidence fact may appear in more than one binding only when the rubric measures distinct dimensions.
- The scorer must not parse evidence rule_id strings to discover criterion IDs.
- The scorer must not infer an anchor or qualification route from subject, explicit_text, filenames, descriptions, or expected output.

rule_triggers is an ordered unique array of approved configuration rule IDs observed by the upstream classification layer. In the current fixtures it is required for, at minimum:

- rubric.v2.da.cap.google_sheets_ceiling in C11;
- rubric.v2.da.rule.context_free_dashboard in C12.

Derived category and overall caps are not copied into rule_triggers. The scoring engine derives the SE CV-only project cap, DA CV-only project cap, SE no-language cap, and DA no-SQL cap from the scored classifications and source availability rules.

review_flags is an ordered unique array of approved blocking review flags. C15 must contain MATERIAL_SOURCE_CONTRADICTION. Completed fixtures contain no unresolved blocking review flag.

project_exclusion_ids is an ordered unique array of explicit upstream project-selection exclusions. Current fixtures default to an empty array unless a fixture explicitly tests an exclusion. Absence of a safe-data exclusion means that exclusion is not triggered; it is not evidence that a dataset exists.

## 4. Fixture changes

Update the fixture-only schema and the golden fixtures so scoring_context is:

- required for every fixture with a non-null track except where a technical-only fixture schema explicitly does not execute scoring;
- absent for C19 band-table and C21 technical-failure fixtures;
- stored once at the top level for C20 and applied identically to both run envelopes.

Add scoring_context to:

- C01 through C18;
- C20;
- C22.

C15 remains REVIEW_REQUIRED and keeps assessment_result null. Its scoring context freezes the lower defensible SQL classification and MATERIAL_SOURCE_CONTRADICTION, but the production scorer must stop before producing any candidate score.

Do not add scoring_context inside expected. It is an input beside assessment_input, source_records, and evidence_facts.

## 5. Locked non-changes

The following must remain byte-equivalent after canonical comparison, except for fixture/package metadata explicitly listed in this brief:

- Every expected assessment result and non-score outcome.
- All raw totals, category scores, caps, final scores, bands, strengths, gaps, actions, recommendations, flags, and QA results.
- Rubric V2 scoring content.
- Action catalogue 1.0.0 content.
- Project catalogue 1.0.0 content.
- Contracts 1.0, 1.1, and 1.2.
- assessment_input.schema.json, assessment_result.schema.json, and evidence_fact.schema.json.
- Production API, services, repositories, database, extraction, reporting, Expo, and scraper code.

No contract-version or active configuration-version change is required. This patch makes the already-approved Contract 1.2 fixture inputs executable; it does not alter scoring semantics.

## 6. Fixture-package version and integrity

Change the manifest package_version from 1.0.0 to 1.0.1.

Recalculate:

- every changed fixture canonical SHA-256;
- the manifest canonical SHA-256;
- LOCKED_MANIFEST_SHA256.

Canonical JSON rules remain unchanged: UTF-8, sorted keys, separators comma and colon, and no insignificant whitespace.

Update the Package C fixture README with the scoring-context boundary and the 1.0.1 package version. Do not rewrite the original Package C decision history.

## 7. Validation tests

Add or strengthen tests proving:

1. Every applicable fixture validates against scoring_context.schema.json.
2. Criterion bindings reference only selected-track criteria.
3. Criterion IDs are unique.
4. Exactly one qualification criterion binding exists and uses a route valid for the selected track.
5. Every referenced evidence ID exists.
6. Non-zero ordinary anchors and non-none qualification routes have accepted evidence.
7. Omitted ordinary criteria resolve to missing_unverifiable only.
8. rule_triggers, review_flags, and project_exclusion_ids contain only approved IDs and contain no duplicates.
9. C11 declares the Google Sheets ceiling trigger.
10. C12 declares the context-free dashboard trigger.
11. C15 declares MATERIAL_SOURCE_CONTRADICTION and retains a null result.
12. C20 uses one identical scoring context for both runs.
13. No scoring context value is read from expected data.
14. All expected results and outcomes remain canonically unchanged from Package C 1.0.0.
15. All fixture and manifest integrity locks pass.
16. The secret sentinel remains only in C22 harness metadata.

## 8. Package D handoff

Package D may begin only after this correction is merged.

Its public pure-domain entry point will accept explicit scoring context rather than deriving classifications from prose. An implementation may use typed domain objects, but the semantic boundary is:

~~~
score_assessment(
    assessment_input,
    source_records,
    evidence_facts,
    scoring_context,
    assessment_id,
    run_id,
    assessed_at,
) -> engine_outcome
~~~

Package D must reproduce the locked expected outcomes without reading expected, fixture_id, title, description, filename, or acceptance_requirement.

## 9. Scope exclusions

Package C.1 must not implement:

- Production scoring or selection functions.
- CV or DOCX extraction.
- Link retrieval.
- Manual-review UI or persistence.
- FastAPI assessment endpoints.
- Supabase tables or migrations.
- Authentication or uploads.
- Customer report rendering or PDF generation.
- Frontend integration.

## 10. Required gates

From Server:

- python -m pytest --cov-fail-under=90
- python -m ruff check .
- python -m ruff format --check .

CI must also pass the Docker build on the exact PR head.

## 11. Completion report

Return:

1. Commit SHA and PR URL.
2. Files created and modified.
3. Fixture package version and manifest hash.
4. Count of fixtures containing scoring_context.
5. Qualification-route distribution by track.
6. Rule triggers by fixture.
7. Review flags and project exclusions by fixture.
8. Proof that expected outcomes are unchanged.
9. Pytest, coverage, Ruff, formatting, Docker, and CI results.
10. Confirmation that no production scoring, API, database, extraction, report, frontend, or scraper code was added.
