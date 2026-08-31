# SkillSignalZA Package C Golden Candidate Fixtures — Product Decisions and Implementation Brief V1

**Status:** Approved under delegated product authority  
**Decision date:** 31 August 2026  
**Contract:** SkillSignalZA Readiness Report Engine Contract V1.2, version 1.2.0  
**Rubric:** V2 — Launch Candidate  
**Implementation target:** `Tests` branch in `LSkhosana/SkillsSignalZA`  

## 1. Purpose

Package C creates the immutable examples that the later pure scoring engine must reproduce. It does not implement scoring. Each fixture freezes a synthetic assessment input, source records, normalized evidence facts, and the exact expected outcome required by the approved contract.

The fixtures are an executable product specification. A later scoring implementation passes only when its canonical output matches these checked-in expectations; it may not update the fixtures merely to make new code pass.

## 2. Contract 1.2 correction that Package C depends on

Contract 1.1 minimum acceptance fixture 7 requested raw score 90 with no explicit SQL. That value is impossible: SQL is worth 15 of the DA track's 100 points, so a zero SQL criterion leaves a maximum raw total of 85. Contract 1.2 corrects that fixture to raw 85, final 79, with the band `developing_application_readiness`.

Contract 1.2 also closes selection-count ambiguity required for canonical expected results:

- Return at most five strengths with accepted non-zero evidence.
- Treat every criterion with a positive point gap as a material gap and retain the complete ordered list.
- Select priority actions for the first five material gaps, or fewer when fewer exist.
- Use the complete material-gap list for project coverage.

No rubric points, anchors, qualification values, category weights, caps, bands, evidence rules, action wording, project content, or scoring semantics change.

## 3. Package boundaries

Package C may add fixture JSON, a fixture-only JSON Schema, fixture validation tests, Contract 1.2 preservation/version tests, and metadata-only version updates required to activate Contract 1.2.

Package C must not add or change:

- Production scoring, cap, band, strength, gap, action-selection, or project-selection functions.
- Extraction, parsing, normalization, link retrieval, browser, model, or prompt code.
- FastAPI routes, request handlers, services, repositories, Supabase, migrations, authentication, or uploads.
- Customer report generation, PDF rendering, templates, or UI.
- Rubric V2 points, anchors, routes, category totals, caps, score bands, action content, project content, catalogue versions, or IDs.
- Expo or scraper code.

The checked-in fixtures must not call the public internet, a live database, Supabase, or any model.

## 4. Required repository artifacts

Create:

- `Server/tests/fixtures/golden_candidates/README.md`
- `Server/tests/fixtures/golden_candidates/manifest.json`
- `Server/tests/fixtures/golden_candidates/golden_fixture.schema.json`
- Exactly 22 fixture files named `c01_...json` through `c22_...json` as listed in section 8.
- `Server/tests/unit/engine/test_golden_candidate_fixtures.py`

Modify only as required:

- `Server/tests/fixtures/README.md`
- `Server/app/engine/configuration/rubric_v2.json` — `contract_version` only, from `1.1.0` to `1.2.0`.
- `Server/app/engine/configuration/action_catalog_v1.json` — `contract_version` only.
- `Server/app/engine/configuration/project_catalog_v1.json` — `contract_version` only.
- `Context/SkillSignalZA_Package_B_Product_Decisions_and_Implementation_Brief_V1.md` — active contract reference only.
- `.github/workflows/server-ci.yml` — include the Contract V1.2 and Package C brief paths in both `push.paths` and `pull_request.paths`.
- Existing configuration/contract/catalogue tests only where Contract 1.2 metadata or canonical hashes require it.

Do not modify Contracts 1.0 or 1.1. Preserve and continue testing their complete newline-normalized SHA-256 values. Add equivalent complete-hash protection for Contract 1.2.

## 5. Golden fixture envelope

Every fixture file is one UTF-8 JSON object with sorted keys and a trailing newline. The fixture-only schema must reject unknown top-level properties.

Required common fields:

```json
{
  "fixture_id": "c03.se.no_language_cap",
  "acceptance_requirement": 3,
  "title": "SE no-language cap",
  "fixture_kind": "completed_assessment",
  "contract_version": "1.2.0",
  "rubric_version": "V2",
  "track": "software_engineering",
  "description": "Synthetic evidence case for one locked contract behaviour.",
  "assessment_input": {},
  "source_records": [],
  "evidence_facts": [],
  "expected": {}
}
```

Allowed `fixture_kind` values:

- `completed_assessment`
- `review_required`
- `normalization_invariant`
- `band_table`
- `determinism_invariant`
- `technical_failure`
- `security_invariant`

For `completed_assessment`, `expected` must contain a complete `assessment_result` that validates against `assessment_result.schema.json`.

For non-completed fixtures, `expected.assessment_result` must be `null`; a technical failure or blocking review must never be represented as a zero-scored completed result. These fixtures must instead declare the exact expected state, error/review code, and absence-of-score assertions.

## 6. Synthetic-data and source rules

- Use only opaque candidate refs such as `golden-c03`; do not use real people or protected personal attributes.
- Use fixed UTC timestamps on 31 August 2026 and deterministic valid 64-character hexadecimal hashes.
- Use reserved example URLs under `https://example.com/`; never retrieve them.
- CV filenames may be synthetic but must use supported PDF or DOCX media types.
- Source IDs are stable within the fixture: `src-cv`, `src-link-01`, and so on.
- Every submitted CV and link has exactly one source record.
- Source records use only the fields and enums frozen in Contract 1.2 section 7.
- Every evidence fact validates against `evidence_fact.schema.json`.
- Every evidence ID is unique within a fixture and refers to an existing source record.
- Every non-zero criterion result references at least one accepted evidence fact.
- Repeated claims do not create repeated normalized facts.
- Frameworks do not create language facts; database products do not create SQL facts; qualifications do not create technical-skill facts; job titles do not create behaviour facts.
- Inaccessible sources contribute no verification fact. Separate defensible CV facts remain eligible.

## 7. Completed-result requirements

Every completed SE or DA result must be fully expanded, not a partial overlay:

- Exactly five category results in rubric order.
- Exactly 26 criterion results in rubric order.
- One criterion result for every selected-track criterion and none from the other track.
- Exact configured maxima, rule IDs, approved anchors, whole awarded points, evidence references, and auditable notes.
- Category pre-cap and final scores, triggered category caps, raw total, triggered overall caps, applicable strictest cap, final score, and band.
- At most five strengths in Contract 1.2 order.
- The complete ordered material-gap list.
- Zero to five priority actions with exact catalogue IDs/content and consecutive one-based `priority_order`.
- The deterministic project recommendation or `PROJECT_RECOMMENDATION_REVIEW_REQUIRED` where the catalogue rules require it.
- Flags and a deterministic QA block.

Checked-in expected results are static JSON. Do not add a fixture generator and do not calculate expected outputs by calling future production scoring code.

## 8. Locked fixture matrix

### C01 — `c01_se_full_score.json`

- Requirement: SE full-score configuration.
- Kind: `completed_assessment`.
- All 25 ordinary SE criteria are `demonstrated`; qualification route is `se.qual.completed`; an accessible candidate-submitted project link exists.
- Categories: 35, 20, 15, 20, 10.
- Raw 100; no category or overall cap; final 100; `strong_application_evidence`.
- No material gaps or priority actions. All-zero project coverage produces `PROJECT_RECOMMENDATION_REVIEW_REQUIRED`.

### C02 — `c02_da_full_score.json`

- Requirement: DA full-score configuration.
- Kind: `completed_assessment`.
- All 25 ordinary DA criteria are `demonstrated`; qualification route is `da.qual.completed`; explicit Excel, SQL, and Power BI evidence and an accessible project link exist.
- Categories: 40, 25, 10, 15, 10.
- Raw and final 100; no caps; `strong_application_evidence`.
- No material gaps or priority actions; project outcome is `PROJECT_RECOMMENDATION_REVIEW_REQUIRED`.

### C03 — `c03_se_no_language_cap.json`

- Requirement: SE no-language cap.
- Kind: `completed_assessment`.
- Programming language is `missing_unverifiable`; programming concepts, application systems, and version control are `documented`; every other ordinary criterion is `demonstrated`; route is `se.qual.completed`; project link accessible.
- Categories: core 19, tools 18, projects 15, alignment 20, readiness 10.
- Raw 82; trigger `rubric.v2.se.cap.no_language`; applicable cap 59; final 59; `foundation_visible`.
- The language gap is first. Remaining gaps follow Contract 1.2 ordering.

### C04 — `c04_se_named_language.json`

- Requirement: named language prevents the cap.
- Same as C03 except programming language is explicit `named_only`, awarding 4.
- Core 23; raw and final 86; no no-language cap; `strong_application_evidence`.

### C05 — `c05_se_framework_only.json`

- Requirement: framework is not language.
- Same numeric outcome as C03. Include explicit demonstrated framework evidence but no explicit programming-language fact.
- Raw 82; no-language cap 59; final 59; `foundation_visible`.
- Assert that no language evidence fact was inferred from the framework.

### C06 — `c06_se_cv_only_project.json`

- Requirement: SE CV-only project cap.
- All non-project criteria are at maximum. There is no accessible candidate-submitted project link. The five project anchors are documented and total 9 before the category cap: 1, 2, 3, 2, 1.
- Project category pre-cap 9, final 8; raw and final 93; `strong_application_evidence`.
- Trigger only `rubric.v2.se.cap.cv_only_projects` as the category cap.

### C07 — `c07_da_no_sql_cap.json`

- Requirement: DA no-SQL cap using the corrected possible maximum.
- All ordinary DA criteria are demonstrated except SQL, which is `missing_unverifiable`; route `da.qual.completed`; explicit Excel and accessible project evidence exist.
- Categories: core 25, tools 25, projects 10, alignment 15, readiness 10.
- Raw 85; trigger `rubric.v2.da.cap.no_sql`; final 79; `developing_application_readiness`.

### C08 — `c08_da_named_sql.json`

- Requirement: named SQL prevents the cap.
- Same as C07 except SQL is explicit `named_only`, awarding 5.
- Core 30; raw and final 90; no no-SQL cap; `strong_application_evidence`.

### C09 — `c09_da_database_only.json`

- Requirement: database product is not SQL.
- Same numeric outcome as C07. Include explicit demonstrated PostgreSQL database-environment evidence, but no explicit SQL competency fact.
- Raw 85; no-SQL cap 79; final 79; `developing_application_readiness`.
- Assert that PostgreSQL did not create a SQL fact.

### C10 — `c10_da_cv_only_project.json`

- Requirement: DA CV-only project cap.
- All non-project criteria are at maximum. The accessible CV contains directly inspectable embedded analytical artifacts, but no accessible candidate-submitted project link. Project accessibility is documented for 1; context, process, findings, and reproducibility are demonstrated for 2 each.
- Project pre-cap 9, final 6; raw and final 96; `strong_application_evidence`.
- Trigger only `rubric.v2.da.cap.cv_only_projects` as the category cap.

### C11 — `c11_da_google_sheets_ceiling.json`

- Requirement: Google Sheets ceiling.
- Full-score DA baseline except spreadsheet evidence demonstrates Google Sheets and contains no explicit Excel evidence.
- Spreadsheet anchor remains `demonstrated`, but awarded points are capped at 5 and its rule IDs include `rubric.v2.da.cap.google_sheets_ceiling`.
- Core 37; raw and final 97; `strong_application_evidence`.

### C12 — `c12_da_context_free_dashboard.json`

- Requirement: context-free dashboard.
- Full-score DA baseline except the submitted dashboard screenshot has no question, user, dataset, period, or business context. `da.projects.context` is `missing_unverifiable`, awards 0, and includes `rubric.v2.da.rule.context_free_dashboard`.
- Projects 8; raw and final 98; `strong_application_evidence`; a full project-category score is impossible.

### C13 — `c13_da_power_bi_alignment.json`

- Requirement: Power BI alignment.
- A scoreable CV explicitly names Power BI without application context; Power BI alignment is `named_only` and awards exactly 1. All other ordinary criteria are missing and qualification route is `da.qual.none`.
- Raw and final 1; `limited_application_evidence`.
- The no-SQL overall cap may be recorded as triggered but cannot increase or otherwise change the score.

### C14 — `c14_inaccessible_link.json`

- Requirement: inaccessible link.
- SE CV explicitly documents Python for 9 points and documents project relevance, depth, documentation, and outcome for 2, 3, 2, and 1. The submitted project link has `access_status: inaccessible`; project accessibility awards 0.
- Project pre-cap/final 8; raw and final 17; `limited_application_evidence`; language cap does not trigger.
- Assert no link-derived verification credit and no deduction beyond unavailable verification; the separate CV facts remain accepted.

### C15 — `c15_conflicting_sources_review.json`

- Requirement: conflicting sources.
- Kind: `review_required` on the DA track.
- CV and submitted repository materially conflict about SQL use or ownership. Freeze the lower defensible evidence classification and raise `MATERIAL_SOURCE_CONTRADICTION`.
- Expected state `REVIEW_REQUIRED`; expected error code `REVIEW_REQUIRED`; `assessment_result` is null; no raw or final score is present.

### C16 — `c16_unsupported_team_player.json`

- Requirement: unsupported behaviour label.
- Kind: `completed_assessment` on SE.
- The only behavioural text is `team player`, with no attributable example. Collaboration uses `named_only` and awards 0. All other ordinary criteria are missing; route `se.qual.none`.
- Raw/final 0; `limited_application_evidence`; no-language cap does not turn zero into 59.

### C17 — `c17_qualification_isolation.json`

- Requirement: qualification isolation.
- Kind: `completed_assessment` on SE.
- A completed relevant qualification awards 10 through `se.qual.completed`; no ordinary technical or behavioural evidence is present.
- Raw/final 10; `limited_application_evidence`; the no-language cap remains triggered but does not alter the lower score.
- Assert zero inferred technical-skill facts and zero qualification-derived avoidance of the language cap.

### C18 — `c18_duplicate_claim_normalization.json`

- Requirement: double-counting prevention.
- Kind: `normalization_invariant` on DA.
- The same explicit `Python` label appears twice in the CV. Store the two source occurrences in fixture provenance but exactly one normalized evidence fact.
- The single named-only programming fact awards 2 in the embedded completed expected result; raw/final 2; `limited_application_evidence`.
- Assert occurrence count 2, canonical fact count 1, and one evidence ID referenced by the criterion.

### C19 — `c19_band_boundaries.json`

- Requirement: every band boundary.
- Kind: `band_table`.
- Lock exactly: 0 and 39 → `limited_application_evidence`; 40 and 59 → `foundation_visible`; 60 and 79 → `developing_application_readiness`; 80 and 100 → `strong_application_evidence`.
- This is configuration-level table data, not eight fabricated candidate assessments.

### C20 — `c20_determinism.json`

- Requirement: deterministic output.
- Kind: `determinism_invariant` on SE.
- Use a self-contained copy of C04's frozen facts and two run envelopes.
- After removing only `assessment_id`, `run_id`, `submitted_at`, and `assessed_at`, canonical JSON from both expected results must be byte-equivalent. No other field may be excluded.

### C21 — `c21_technical_failure_isolation.json`

- Requirement: technical failure isolation.
- Kind: `technical_failure`.
- Include two cases: `CV_EXTRACTION_FAILED` and `RULESET_INVALID`.
- Each case has `assessment_result: null`, no raw/final score or band, and an explicit assertion that a technical failure cannot become a zero-score completed assessment.

### C22 — `c22_secret_exclusion.json`

- Requirement: secret exclusion.
- Kind: `security_invariant` on DA.
- Define the sentinel only in harness metadata: `SKILLSIGNALZA_GOLDEN_SECRET_DO_NOT_LEAK_7f9c2e`.
- Use a completed synthetic result and a minimal expected customer report-data projection. Neither public payload may contain the sentinel, credential-bearing URL, raw token, or internal exception text at any nesting depth.
- The fixture test recursively scans keys and string values. It does not implement report rendering.

## 9. Manifest and integrity lock

`manifest.json` must contain:

- Package version `1.0.0`, status `approved`, contract `1.2.0`, rubric `V2`.
- Exactly 22 entries in C01–C22 order.
- Unique fixture ID, requirement number, filename, kind, track where applicable, and canonical SHA-256 for every fixture.
- A complete `coverage_tags` list matching the 22 minimum acceptance requirements exactly once.

Canonical fixture hashing uses parsed JSON serialized with UTF-8, sorted keys, and separators `,` and `:` with no insignificant whitespace. Hash the canonical bytes, not platform-specific file bytes.

Tests must fail when fixture content changes without the manifest hash changing. The manifest itself must also have a locked canonical SHA-256 constant in the fixture test. Intentional fixture changes require product review, a fixture-package version decision, updated hashes, and an explanation; future engine code may not rewrite golden expectations.

## 10. Required tests

Add focused tests proving:

1. The manifest and all 22 JSON files parse and validate against the fixture-only schema.
2. IDs, filenames, requirement numbers, kinds, hashes, and coverage tags are unique and complete.
3. Every embedded assessment input validates against `assessment_input.schema.json`.
4. Every embedded evidence fact validates against `evidence_fact.schema.json`.
5. Every embedded completed result validates against `assessment_result.schema.json`.
6. Every completed result contains exactly five categories and 26 selected-track criteria with exact configuration maxima/rule IDs.
7. Evidence/source references are closed, unique, attributable, and non-zero scores have accepted supporting evidence.
8. Criterion, category, raw, cap, final, and band arithmetic matches the locked matrix.
9. The 22 scenario-specific assertions in section 8 hold exactly.
10. Strength, material-gap, priority-action, and project ordering matches Contract 1.2 and Package B without implementing production engine functions.
11. Priority actions exactly match the approved catalogue records for their current anchors.
12. Project recommendations use existing project IDs or the exact review-required sentinel.
13. Canonical hashes and determinism assertions are newline- and platform-independent.
14. Contracts 1.0 and 1.1 remain byte-equivalent under their existing normalized hashes; Contract 1.2 receives a complete normalized hash lock.
15. Active rubric/action/project metadata is exactly Contract `1.2.0`; catalogue versions remain `1.0.0`; Rubric remains `V2`.
16. All 212 actions, eight projects, rubric values, caps, bands, routes, and customer-facing catalogue content remain unchanged apart from contract-version metadata.
17. Failure/review fixtures contain no completed result or score.
18. Secret sentinel and credential patterns do not appear in public expected payloads.

The tests may contain validation helpers and independent arithmetic assertions. They must not add reusable production scoring or selection implementation under `Server/app/`.

## 11. Dependencies and quality gates

Add no runtime or development dependency unless an existing dependency cannot validate ordinary JSON/JSON Schema. `jsonschema`, Python standard-library `json`, and `hashlib` are already sufficient.

Run from `Server/`:

```text
python -m pytest --cov-fail-under=90
python -m ruff check .
python -m ruff format --check .
```

Then require the PR's Docker build to pass. Do not weaken tests, lint, formatting, coverage, workflow path filters, or existing hashes to make Package C pass.

## 12. Branch and merge process

1. Implement on `Tests` only.
2. Commit all Package C work and push `Tests`.
3. Open a pull request from `Tests` to `main`.
4. Do not merge the PR.
5. Wait for independent contract, fixture, CI, and scope review.

## 13. Required completion report

Return:

1. Concise implementation summary.
2. Exact files created and modified.
3. Remote 40-character commit SHA and PR link.
4. Confirmation of exactly 22 fixture files and one manifest.
5. Fixture counts by kind and track.
6. Exact C01–C22 expected raw/final/cap/band or non-score outcome summary.
7. Contract 1.2 normalized SHA-256 and confirmation that 1.0/1.1 hashes are unchanged.
8. Manifest canonical SHA-256 and confirmation that all fixture hashes pass.
9. Confirmation that Rubric V2, both catalogue versions, 212 actions, eight projects, scoring values, caps, bands, routes, and content did not change.
10. Dependencies added or changed.
11. Pytest count, coverage, Ruff lint, Ruff format, and Docker/CI results.
12. Every ambiguity, assumption, or limitation encountered.
13. Confirmation that no production scoring, selection, API, database, extraction, link retrieval, report rendering, Expo, or scraper code was added.
14. Final `git status --short`.

Do not claim completion unless every required artifact and gate is complete. Do not merge the PR.
