# SkillSignalZA Package B Product Decisions and Implementation Brief V1

**Status:** Approved under delegated product authority  
**Decision date:** 27 August 2026  
**Contract:** SkillSignalZA Readiness Report Engine Contract V1.2, version 1.2.0  
**Rubric:** V2 — Launch Candidate  
**Implementation target:** `Tests` branch in `LSkhosana/SkillsSignalZA`  

## 1. Purpose

Package B provides the deterministic customer-facing content used after scoring:

- `action_catalog_v1.json`: fixed improvement actions for rubric criteria and current evidence states.
- `project_catalog_v1.json`: fixed track-specific projects used to close the largest weighted evidence gaps.

These files are configuration and product content. They must not calculate scores, extract evidence, call a model, search for courses, or generate unrestricted recommendations.

## 2. Locked product decisions

1. Catalogue version is `1.0.0` and status is `approved`.
2. Every non-qualification criterion receives exactly four actions, one for each evidence level: `missing_unverifiable`, `named_only`, `documented`, and `demonstrated`.
3. Qualification criteria are route-based and receive exactly one action for every approved qualification route. Generic evidence-level actions are not used for qualification criteria because scored results use qualification-route anchors.
4. There are 50 non-qualification criteria and 12 qualification-route actions. The action catalogue therefore contains exactly 212 action records.
5. Actions are concise candidate-facing instructions. They must not recommend a named course or provider, promise a score change, invent metrics, or tell a candidate to claim work they did not perform.
6. Missing and named-only actions target at least `documented` evidence. Documented actions target `demonstrated` evidence. Demonstrated actions remain `demonstrated` and improve discoverability and packaging; they do not promise more points.
7. For project-category criteria, missing, named-only, and documented actions target `demonstrated` evidence because accessible project proof is the product goal.
8. A report may include at most five priority actions. Active hard-cap gaps come first. Do not force a minimum number when fewer than five material gaps exist.
9. Only one project is recommended per completed assessment.
10. Project selection uses core coverage only. Optional/stretch coverage is disclosed but does not increase the selection score.
11. Project coverage score is the sum of current `point_gap` values for the project's core-covered criteria that appear in the ordered material-gap list. The highest positive score wins; ties use stable `project_id` order.
12. If every eligible project has a coverage score of zero, return `PROJECT_RECOMMENDATION_REVIEW_REQUIRED`.
13. Required foundation skills are normally prerequisites rather than automatic exclusions. A candidate may receive a project recommendation with prerequisites, except where a project declares an explicit safety or complexity exclusion. The support-ticket classifier retains `python_not_explicit`, `api_foundation_missing_unverifiable`, and `safe_labelled_data_unavailable`.
14. Blocking assessment-review flags prevent report release before project selection, as required by the contract.
15. No time estimates are included in V1. Completion is evidence-gated, not date-gated.
16. V1 contains eight projects: four Software Engineering and four Data Analytics projects already approved in the Career Map Packs.

## 3. Action record contract

Each non-qualification action record must contain:

```json
{
  "action_id": "action.v1.se.core.programming_language.missing_unverifiable",
  "criterion_id": "se.core.programming_language",
  "current_anchor": "missing_unverifiable",
  "target_anchor": "documented",
  "candidate_instruction": "Create evidence for Programming language evidence: publish a small working feature in one explicitly named language and explain what the code does.",
  "required_output": "Accessible source code plus a short language-specific implementation note.",
  "completion_check": "The language is named explicitly and a reviewer can locate code that implements a working behaviour.",
  "action_type": "create_evidence",
  "project_addressable": true
}
```

Allowed `action_type` values:

- `create_evidence`
- `add_context`
- `demonstrate_evidence`
- `package_evidence`
- `package_qualification`
- `access_strategy`

Every action uses `current_anchor` and `target_anchor`. Those fields accept the four ordinary evidence anchors and all twelve approved qualification-route anchors. Qualification packaging actions keep the same qualification route for both anchors; packaging must not imply that the scored route changed.

Stable action IDs:

- Non-qualification: `action.v1.{criterion_id}.{current_anchor}`
- Qualification: `action.v1.{criterion_id}.{qualification_route_suffix}`

### 3.1 Locked action wording templates

Cursor/Codex must generate the action records from these exact templates and the criterion matrix in section 4. It may make grammatical substitutions only; it must not add new product advice.

| Current anchor | Action type | Candidate instruction template | Target |
|---|---|---|---|
| `missing_unverifiable` | `create_evidence` | `Create evidence for {display_name}: {evidence_target}.` | `documented`, except project criteria target `demonstrated` |
| `named_only` | `add_context` | `Replace the isolated {display_name} label with contextual evidence: {evidence_target}.` | `documented`, except project criteria target `demonstrated` |
| `documented` | `demonstrate_evidence` | `Publish or attach direct proof for {display_name}: {evidence_target}.` | `demonstrated` |
| `demonstrated` | `package_evidence` | `Package the existing {display_name} proof so a reviewer can find and verify it quickly: {evidence_target}.` | `demonstrated` |

## 4. Criterion evidence matrix

The matrix supplies the exact evidence target, required output, completion check, and whether an approved project can address the criterion. Cursor/Codex must not broaden these claims.

### 4.1 Software Engineering

| Criterion ID | Evidence target | Required output | Completion check | Project-addressable |
|---|---|---|---|---:|
| `se.core.programming_language` | publish a small working feature in one explicitly named language and explain what the code does | Accessible source code plus a short language-specific implementation note | The language is named explicitly and a reviewer can locate code that implements a working behaviour | true |
| `se.core.programming_concepts` | show control flow, data handling, decomposition, and a technical decision inside working code | Focused code example plus a note explaining the problem and chosen approach | The example contains an inspectable implementation and the explanation matches the code | true |
| `se.core.application_systems` | show a complete input-to-result application or API flow, including one controlled failure | Working flow, request or screen evidence, and failure-path evidence | A reviewer can follow the normal path and trigger or inspect the failed path | true |
| `se.core.database_fundamentals` | show a relational model, deliberate relationships, constraints, and purposeful queries | Schema or migrations, seeded records, and query examples | Relationships and constraints are visible and the queries return explainable results | true |
| `se.core.debugging_testing` | record a defect or invalid case, the diagnosis, the fix, and the verification | Automated test or documented manual check plus a short debugging record | The original failure and successful verification are both reproducible or inspectable | true |
| `se.tools.version_control` | show Git used throughout the work through meaningful, traceable changes | Repository history with staged commits and a brief workflow note | Commit history reflects progressive work rather than a single bulk upload | true |
| `se.tools.framework_library` | use one explicitly named framework or library for a clear responsibility | Working framework/library implementation and dependency declaration | The named tool is visible in the project and its role is explained accurately | true |
| `se.tools.database_platform` | configure and use an explicitly named database platform in a working flow | Setup configuration, schema or migrations, and sample data | Another developer can identify the platform and initialise the data layer | true |
| `se.tools.dev_environment` | document the commands, dependencies, configuration, and environment needed to run the work | Reproducible setup section and safe example configuration | A clean setup can reach the documented start or test command without hidden steps | true |
| `se.tools.repository_platform` | use an accessible repository platform with inspectable collaboration or repository-management behaviour | Repository link plus issue, pull-request, review, or equivalent workflow evidence | The platform use shows more than the existence of a profile or repository | true |
| `se.tools.deployment_cloud` | publish a stable deployment, container setup, or documented cloud workflow with safe configuration | Deployed link or container/cloud configuration plus operating notes | The result starts reliably and secrets or private configuration are excluded | true |
| `se.projects.accessibility` | provide a direct candidate-submitted link that opens without special permission | Accessible repository, deployed project, or portfolio link | The submitted link opens and leads directly to the claimed project evidence | true |
| `se.projects.problem_relevance` | state the user, problem, scope, and Software Engineering relevance | Project brief or README problem section | The problem and main workflow are clear before reading the implementation | true |
| `se.projects.depth_ownership` | expose the central implementation decisions and identify the candidate's contribution | Architecture or decision note linked to working code | A reviewer can distinguish the candidate's work and reach meaningful implementation detail | true |
| `se.projects.documentation` | document setup, structure, decisions, normal use, failure paths, and current limits | Complete README or equivalent technical guide | Another developer can navigate and run or inspect the project from the documentation | true |
| `se.projects.outcome` | show the working result and the expected response to at least one failure | Short demo, screenshots, sample requests, or test output | The main outcome and a controlled failure are visible without relying on a CV claim | true |
| `se.alignment.target_role` | align the CV headline, evidence order, and selected stack to one Software Engineering direction | Updated CV section and target-role statement | The stated target and strongest evidence describe the same type of work | false |
| `se.alignment.claim_specificity` | replace broad skill claims with the exact tool, task, context, and contribution | Revised skills and experience wording | Each retained claim points to a specific use, responsibility, or evidence source | false |
| `se.alignment.description_evidence` | describe action, technical process, output, and verified outcome without invented metrics | Revised project or experience bullets | Every outcome is supported by submitted evidence and no unsupported number is added | false |
| `se.alignment.readability` | create a consistent reading order with clear headings, dates, spacing, and concise evidence-led content | Updated text-readable CV | A reviewer can find target role, recent experience, skills, and project links quickly | false |
| `se.readiness.communication` | publish a concise technical explanation written for another person | README section, handover note, user guide, or technical decision note | The document names its reader and explains the relevant process or decision clearly | true |
| `se.readiness.collaboration` | show an attributable team contribution, review exchange, requirement discussion, or shared delivery | Pull request, review, requirement record, or truthful experience bullet | The candidate's contribution and the other party's role are distinguishable | true |
| `se.readiness.professional_exposure` | document a real work, internship, freelance, volunteer, or client responsibility and its deliverable | Evidence-led experience entry or attributable work artifact | The organisation or context, responsibility, and output are stated without inflated seniority | false |
| `se.readiness.initiative` | show a self-directed improvement, recovery, or build decision carried through to an output | Decision note, issue history, or project improvement record | The starting gap, chosen action, and completed output are visible | true |
| `se.readiness.self_management` | show how a problem was scoped, investigated, resolved, and checked | Debugging, incident, task, or decision record | The record connects the problem, actions, result, and verification | true |

### 4.2 Data Analytics

| Criterion ID | Evidence target | Required output | Completion check | Project-addressable |
|---|---|---|---|---:|
| `da.core.sql` | publish explicit SQL that filters, joins, aggregates, and validates data for a named question | Ordered SQL files plus result or validation evidence | Queries run in the documented order and outputs reconcile to a stated check | true |
| `da.core.spreadsheets` | show spreadsheet analysis using formulas, lookups, pivots, controls, or validation appropriate to the question | Inspectable Excel or Google Sheets workbook with control notes | Key calculations are visible and an independent total or exception check is included | true |
| `da.core.analysis_statistics` | define the analytical unit, select defensible measures, compare results, and test an alternative view | Analysis note with measures, denominators, comparisons, and interpretation | Counts, rates, averages, or changes use the correct grain and the conclusion survives a stated check | true |
| `da.core.cleaning` | record explicit treatments for missing values, duplicates, categories, types, and extreme observations | Cleaning log plus before-and-after validation counts | Every material change maps to a written rule and rejected or changed records remain auditable | true |
| `da.core.reporting` | communicate the finding, its decision context, and its limitations to a named reader | Insight memo, report page, or dashboard narrative | The output separates observation, interpretation, recommendation, and limitation | true |
| `da.tools.bi_visualisation` | build an inspectable dashboard or visual report with a clear model, measures, filters, and reading order | BI file or equivalent artifact plus screenshots or PDF | Visuals answer the named question and filters preserve intended denominators | true |
| `da.tools.power_bi_alignment` | explicitly show Power BI in a submitted artifact or evidence description | Power BI file, published report evidence, screenshot, or specific project description | Power BI is named explicitly and its role in the workflow is clear | true |
| `da.tools.programming` | use explicitly named Python or R code to add repeatability, scale, or analytical depth | Reproducible script or notebook with dependency and run notes | The code performs a meaningful analytical step and produces an inspectable output | true |
| `da.tools.database_environment` | show an explicitly named database or data environment connected to the analytical workflow | Source description, connection-safe setup notes, and queries or model evidence | The environment and its role can be identified without exposing credentials | true |
| `da.tools.transformation_cloud` | implement repeatable transformation or platform steps in an explicitly named tool | Power Query, dbt, pipeline, cloud, Python, or R transformation artifact | A second input can pass through the documented transformation and quality checks | true |
| `da.tools.integration` | connect at least two named tools in one traceable data-to-output workflow | Workflow note showing source, transformation, analysis, and output hand-offs | A reviewer can trace the same records or measures across the tool boundary | true |
| `da.projects.accessibility` | provide a direct candidate-submitted link that opens without special permission | Accessible repository, dashboard, workbook, report, or portfolio link | The submitted link opens and leads directly to the claimed analytical evidence | true |
| `da.projects.context` | state the intended user, decision, dataset, reporting period, and analytical question | Project brief and dataset declaration | The question and unit of analysis are clear before the results are presented | true |
| `da.projects.process` | expose cleaning, exploration, calculation, and validation steps in a reproducible order | Queries, script, workbook, or transformation log | A reviewer can follow how raw records became the analytical result | true |
| `da.projects.findings` | present supported findings with useful visuals, denominator checks, and limitations | Insight memo and visual output | Findings match the calculations and do not turn correlation into an unsupported cause | true |
| `da.projects.reproducibility` | package source declarations, file order, dependencies, refresh steps, and expected outputs | README, refresh guide, and organised project files | Another reviewer can reproduce or audit the result from the included instructions | true |
| `da.alignment.target_role` | align the CV headline, evidence order, and selected tools to one Data Analytics direction | Updated CV section and target-role statement | The stated target and strongest evidence describe the same analytical work | false |
| `da.alignment.claim_specificity` | replace broad analytical claims with the exact tool, question, process, and contribution | Revised skills and experience wording | Each retained claim points to a specific use, responsibility, or evidence source | false |
| `da.alignment.description_evidence` | describe the question, analytical process, output, and supported decision context without invented metrics | Revised project or experience bullets | Every outcome is supported by submitted evidence and no unsupported number is added | false |
| `da.alignment.readability` | create a consistent reading order with clear headings, dates, spacing, and concise evidence-led content | Updated text-readable CV | A reviewer can find target role, analytical tools, recent experience, and project links quickly | false |
| `da.readiness.problem_solving` | show how an analytical problem was framed, investigated, checked, and resolved | Analysis, issue, or decision record | The record connects the question, method, result, and validation | true |
| `da.readiness.attention_detail` | expose a material data-quality, boundary, denominator, or reconciliation check | Validation table, exception report, or cleaning log | The check identifies what was tested and how discrepancies were handled | true |
| `da.readiness.collaboration` | show an attributable stakeholder, reviewer, or team interaction that changed or validated the work | Requirement note, review record, handover, or truthful experience bullet | The candidate's contribution and the other party's input are distinguishable | true |
| `da.readiness.communication` | explain a finding, metric, limitation, or action to a named non-technical reader | Insight memo, dashboard note, presentation, or handover | The output states what the reader should understand or investigate next | true |
| `da.readiness.self_management` | show how scope, files, assumptions, tasks, and validation were controlled through completion | Project log, issue history, analysis plan, or decision record | The record connects the starting question, work sequence, result, and completion check | true |

## 5. Qualification-route action mappings

These actions package truthful market-access evidence. They never create technical-skill evidence and never instruct a candidate to start a qualification merely to increase a score.

Apply the same route-specific content to the corresponding SE or DA qualification criterion, using the track-specific route ID and points already stored in `rubric_v2.json`. Each qualification action sets `current_anchor` and `target_anchor` to that same route ID so packaging does not imply the scored route changed.

| Route suffix | Action type | Candidate instruction | Required output | Completion check |
|---|---|---|---|---|
| `completed` | `package_qualification` | State the completed relevant qualification precisely and place it where a reviewer can verify the award and field. | Qualification name, institution, completion status, and year; optional safe supporting link or document reference | The wording matches the submitted evidence and does not imply unverified technical skills |
| `in_progress` | `package_qualification` | State the relevant qualification as in progress, including the institution and expected or current study status without implying completion. | Qualification name, institution, in-progress status, and truthful date context | The status is unambiguous and consistent across the CV and submitted evidence |
| `experience` | `package_qualification` | Present the substantial equivalent experience through specific responsibilities, duration, and attributable technical or analytical outputs. | Evidence-led experience entries and linked work where safely available | The experience route is supported without converting the job title into assumed skills |
| `bootcamp` | `package_qualification` | Pair the relevant bootcamp or certification with accessible applied work that shows how the learning was used. | Training details plus linked applied project or work evidence | The training and applied evidence are both explicit and independently attributable |
| `adjacent` | `package_qualification` | State the adjacent qualification accurately and connect only the relevant upskilling or applied evidence that is actually present. | Adjacent qualification details plus truthful relevant training or project evidence | The relationship to the selected track is explained without re-labelling the qualification |
| `none` | `access_strategy` | Do not invent or obscure qualification status. Strengthen applied evidence and concentrate applications on roles whose wording accepts equivalent experience, training, or demonstrable work. | Truthful education section, stronger applied evidence, and a recorded vacancy-filter rule | The CV remains accurate and the target list does not depend on a qualification the candidate does not hold |

## 6. Project catalogue record contract

Each project record must contain:

```json
{
  "project_id": "se.project.01_operations_workflow",
  "catalog_version": "1.0.0",
  "track": "software_engineering",
  "title": "Operations workflow application",
  "scenario": "A small organisation needs one place to capture, assign, update, and close operational requests.",
  "required_foundations": [],
  "core_criterion_ids": [],
  "optional_criterion_ids": [],
  "required_outputs": [],
  "completion_checks": [],
  "exclusion_conditions": [],
  "source_blueprint": "SkillSignalZA SE Career Map Pack V1, Project Blueprint 1"
}
```

Global exclusion conditions for every project:

- `track_mismatch`
- `blocking_review_unresolved`
- `no_positive_core_gap_coverage`

Dataset-based projects must also require public, safely anonymised, or clearly declared synthetic data. Candidate or employer confidential data must never be recommended for publication.

## 7. Approved Software Engineering projects

### `se.project.01_operations_workflow`

- **Title:** Operations workflow application
- **Scenario:** A small organisation needs one place to capture, assign, update, and close operational requests.
- **Required foundations:** One explicit programming language; basic HTTP or application flow; basic relational data; basic Git.
- **Core criteria:** `se.core.programming_language`, `se.core.programming_concepts`, `se.core.application_systems`, `se.core.database_fundamentals`, `se.core.debugging_testing`, `se.tools.version_control`, `se.tools.framework_library`, `se.tools.database_platform`, `se.tools.dev_environment`, `se.tools.repository_platform`, all five `se.projects.*` criteria, `se.readiness.communication`, `se.readiness.initiative`, `se.readiness.self_management`.
- **Optional criteria:** `se.tools.deployment_cloud`, `se.readiness.collaboration`.
- **Required outputs:** Working request workflow; related data model; validation and invalid-transition handling; filters; loading, empty, success, and failure states; seeded data; audit entry on status change; central-rule test; README; architecture note; normal and invalid verification record; accessible project link.
- **Completion checks:** Main workflow works from clean setup; invalid state changes receive a specific response; relationships are preserved; failures are visible and recoverable; another developer can follow setup; layer boundaries can be explained.
- **Additional exclusions:** none.
- **Source:** SE Career Map Pack V1, Project Blueprint 1.

### `se.project.02_application_tracker_interface`

- **Title:** Application tracker interface
- **Scenario:** A job seeker needs to manage opportunities, deadlines, stages, and recurring skill gaps through a responsive interface.
- **Required foundations:** Explicit JavaScript or TypeScript; HTML and CSS fundamentals; basic asynchronous requests; basic Git.
- **Core criteria:** `se.core.programming_language`, `se.core.programming_concepts`, `se.core.application_systems`, `se.core.debugging_testing`, `se.tools.version_control`, `se.tools.framework_library`, `se.tools.dev_environment`, `se.tools.repository_platform`, all five `se.projects.*` criteria, `se.readiness.communication`, `se.readiness.initiative`, `se.readiness.self_management`.
- **Optional criteria:** `se.tools.deployment_cloud`, `se.readiness.collaboration`.
- **Required outputs:** Responsive list and detail views; create, edit, filter, and sort flows; loading, empty, error, and confirmation states; accessible labels, keyboard paths, and focus; reusable components; mock or API data; one interaction test; mobile layout; README; short demo; accessible project link.
- **Completion checks:** Main workflow works at narrow and wide widths; every asynchronous state is visible; keyboard users can complete the main task; essential actions remain available; failed requests offer recovery; decisions and limits are documented.
- **Additional exclusions:** none.
- **Source:** SE Career Map Pack V1, Project Blueprint 2.

### `se.project.03_service_request_api`

- **Title:** Service request API
- **Scenario:** Several clients need a shared request service with assignment, status history, data integrity, and consistent errors.
- **Required foundations:** One explicit server-side language; HTTP fundamentals; basic relational data; basic Git.
- **Core criteria:** `se.core.programming_language`, `se.core.programming_concepts`, `se.core.application_systems`, `se.core.database_fundamentals`, `se.core.debugging_testing`, `se.tools.version_control`, `se.tools.framework_library`, `se.tools.database_platform`, `se.tools.dev_environment`, `se.tools.repository_platform`, all five `se.projects.*` criteria, `se.readiness.communication`, `se.readiness.initiative`, `se.readiness.self_management`.
- **Optional criteria:** `se.tools.deployment_cloud`, `se.readiness.collaboration`.
- **Required outputs:** REST endpoints for requests, users, and status changes; relational schema and migrations; request validation; consistent error responses; server-enforced transitions; structured logs; tests for central and invalid paths; seeded data; sample requests; one simulated dependency with defensive handling; API contract; data-model note; accessible project link.
- **Completion checks:** Another developer can start the service, run samples, inspect the model, trigger a controlled failure, and locate the matching test or log.
- **Additional exclusions:** none.
- **Source:** SE Career Map Pack V1, Project Blueprint 3.

### `se.project.04_support_ticket_classifier`

- **Title:** Support ticket classifier
- **Scenario:** A support team needs a proposed category and urgency for text requests while preserving human review.
- **Required foundations:** Explicit Python; basic API and structured-data handling; Git; testing; safe data handling.
- **Core criteria:** `se.core.programming_language`, `se.core.programming_concepts`, `se.core.application_systems`, `se.core.debugging_testing`, `se.tools.version_control`, `se.tools.framework_library`, `se.tools.dev_environment`, `se.tools.repository_platform`, all five `se.projects.*` criteria, `se.readiness.communication`, `se.readiness.initiative`, `se.readiness.self_management`.
- **Optional criteria:** `se.tools.deployment_cloud`, `se.tools.database_platform`, `se.readiness.collaboration`.
- **Required outputs:** De-identified labelled sample; rules, small model, or approved API baseline; endpoint or interface; held-out evaluation; suitable metric; confidence threshold; human-review fallback; privacy-safe logs; input validation; controlled failure; error-analysis note; accessible project link.
- **Completion checks:** The feature has one defined job; inputs and outputs are inspectable; evaluation is separated from training or design examples; low-confidence output follows review; private source text is excluded from logs; common failure patterns and limitations are documented.
- **Additional exclusions:** `python_not_explicit`, `api_foundation_missing_unverifiable`, `safe_labelled_data_unavailable`.
- **Source:** SE Career Map Pack V1, Project Blueprint 4.

## 8. Approved Data Analytics projects

### `da.project.01_kpi_dashboard`

- **Title:** Performance reporting and KPI dashboard
- **Scenario:** A service or retail organisation needs a monthly overview of volume, value, completion, exceptions, and period movement with traceable detail.
- **Required foundations:** Explicit SQL; spreadsheet inspection; basic Power BI or comparable BI use; metric and denominator awareness.
- **Core criteria:** `da.core.sql`, `da.core.spreadsheets`, `da.core.analysis_statistics`, `da.core.cleaning`, `da.core.reporting`, `da.tools.bi_visualisation`, `da.tools.power_bi_alignment`, `da.tools.database_environment`, `da.tools.transformation_cloud`, `da.tools.integration`, all five `da.projects.*` criteria, `da.readiness.problem_solving`, `da.readiness.attention_detail`, `da.readiness.communication`, `da.readiness.self_management`.
- **Optional criteria:** `da.tools.programming`, `da.readiness.collaboration`.
- **Required outputs:** Project brief; dataset declaration; KPI dictionary; ordered SQL; source and query validation table; clean model; Power BI or comparable report; overview and investigation pages; screenshots or PDF; refresh note; written findings; limitations; accessible project link.
- **Completion checks:** Totals reconcile; filters preserve denominators; period comparisons are consistent; overview and detail have distinct roles; exceptions trace to records; instructions reproduce the result.
- **Additional exclusions:** `safe_or_declared_dataset_unavailable`.
- **Source:** DA Career Map Pack V1, Project Blueprint 1.

### `da.project.02_sla_analysis`

- **Title:** Service operations and SLA analysis
- **Scenario:** A service team needs to understand workload, response and resolution time, backlog, and SLA breaches from imperfect operational exports.
- **Required foundations:** Explicit SQL or Power Query; spreadsheet validation; date and status handling; basic dashboard use.
- **Core criteria:** `da.core.sql`, `da.core.spreadsheets`, `da.core.analysis_statistics`, `da.core.cleaning`, `da.core.reporting`, `da.tools.bi_visualisation`, `da.tools.power_bi_alignment`, `da.tools.database_environment`, `da.tools.transformation_cloud`, `da.tools.integration`, all five `da.projects.*` criteria, all five `da.readiness.*` criteria.
- **Optional criteria:** `da.tools.programming`.
- **Required outputs:** Process map; SLA and boundary rules; SQL or Power Query steps; data-quality log; Excel control workbook or validation sheet; Power BI operational report; record-level breach or backlog export; insight memo; accessible project link.
- **Completion checks:** Boundary cases follow the rule; open-record age is consistent; missing timestamps are visible; summary counts reconcile to the exception list; recommendations point to measurable issues; sensitive or synthetic treatment is declared.
- **Additional exclusions:** `safe_or_declared_dataset_unavailable`.
- **Source:** DA Career Map Pack V1, Project Blueprint 2.

### `da.project.03_customer_performance_investigation`

- **Title:** Customer or marketing performance investigation
- **Scenario:** A commercial team needs to understand which segments or channels contribute to conversion, repeat activity, or value without overstating cause.
- **Required foundations:** Explicit SQL; basic descriptive statistics; spreadsheet, Python, or R exploration; safe dataset handling.
- **Core criteria:** `da.core.sql`, `da.core.spreadsheets`, `da.core.analysis_statistics`, `da.core.cleaning`, `da.core.reporting`, `da.tools.bi_visualisation`, `da.tools.programming`, `da.tools.database_environment`, `da.tools.integration`, all five `da.projects.*` criteria, `da.readiness.problem_solving`, `da.readiness.attention_detail`, `da.readiness.communication`, `da.readiness.self_management`.
- **Optional criteria:** `da.tools.power_bi_alignment`, `da.tools.transformation_cloud`, `da.readiness.collaboration`.
- **Required outputs:** Analytical question; scope and unit of analysis; field guide; cleaning log; SQL with validation; script, notebook, or workbook; labelled visuals; denominator checks; alternate analysis; insight memo; limitations; accessible project link.
- **Completion checks:** Denominators are explicit; small segments are flagged; missing categories remain visible; observation and causation stay separate; an alternate definition tests stability; recommendations fit the evidence.
- **Additional exclusions:** `safe_or_declared_dataset_unavailable`.
- **Source:** DA Career Map Pack V1, Project Blueprint 3.

### `da.project.04_repeatable_data_quality_workflow`

- **Title:** Data-quality and repeatable reporting workflow
- **Scenario:** A team needs a controlled monthly-file transformation because headers, categories, and date formats change between deliveries.
- **Required foundations:** Spreadsheet or delimited-file handling; one explicit transformation tool such as Power Query, Python, or R; basic validation and reporting.
- **Core criteria:** `da.core.spreadsheets`, `da.core.analysis_statistics`, `da.core.cleaning`, `da.core.reporting`, `da.tools.bi_visualisation`, `da.tools.programming`, `da.tools.transformation_cloud`, `da.tools.integration`, all five `da.projects.*` criteria, `da.readiness.problem_solving`, `da.readiness.attention_detail`, `da.readiness.communication`, `da.readiness.self_management`.
- **Optional criteria:** `da.core.sql`, `da.tools.power_bi_alignment`, `da.tools.database_environment`, `da.readiness.collaboration`.
- **Required outputs:** Expected-schema document; unchanged raw input examples; synthetic-data declaration; transformation script or queries; quality exception report; clean output; reporting view; two-cycle refresh log; failure-handling guide; reproduction instructions; accessible project link.
- **Completion checks:** Raw inputs remain unchanged; every correction maps to a rule; failed records remain visible; a changed file refreshes successfully; control totals reconcile; optional classification includes measured error and human review.
- **Additional exclusions:** `safe_synthetic_variations_unavailable`.
- **Source:** DA Career Map Pack V1, Project Blueprint 4.

## 9. Cursor/Codex implementation task

Read completely before editing:

- `Context/SkillSignalZA_Readiness_Report_Engine_Contract_V1_1.md`
- This Package B decision brief.
- `Server/app/engine/configuration/rubric_v2.json`
- Existing Package A schemas and tests.

Create:

```text
Server/app/engine/configuration/action_catalog_v1.json
Server/app/engine/configuration/project_catalog_v1.json
Server/tests/unit/engine/test_action_catalog.py
Server/tests/unit/engine/test_project_catalog.py
```

Update package-data configuration only if the existing JSON glob does not already include the new files.

### 9.1 Required action-catalog tests

1. JSON parses and catalogue metadata matches contract `1.1.0`, rubric `V2`, catalogue `1.0.0`, status `approved`.
2. Exactly 50 rubric criteria are identified as non-qualification criteria.
3. Every non-qualification criterion has exactly four unique actions covering all approved evidence levels.
4. Exactly 12 qualification-route actions exist: six per track.
5. Total action count is exactly 212.
6. Every action references an existing rubric criterion.
7. Every qualification action references a route belonging to the same track.
8. Action IDs are unique and follow the locked format.
9. Missing and named-only actions never target a lower evidence anchor.
10. Documented actions target `demonstrated`.
11. Demonstrated actions remain `demonstrated` and use `package_evidence`.
12. Every action has non-empty instruction, required output, and completion check.
13. Project criteria target `demonstrated` for missing, named-only, and documented states.
14. `project_addressable` matches the criterion matrix.
15. No text contains hiring guarantees, score promises, invented achievements, named course providers, or instructions to misrepresent evidence.
16. Selection policy sets the priority-action limit to five, gives active cap gaps precedence, and does not force a minimum.
17. Ordinary evidence states use the locked action types: `create_evidence`, `add_context`, `demonstrate_evidence`, and `package_evidence`.
18. `target_anchor` follows the locked mapping, including the stronger `demonstrated` target for project criteria. Qualification packaging keeps the same route for current and target anchors.
19. Canonical SHA-256 hashes of both catalogues match the approved content, using normalized parsed JSON with stable key ordering and compact separators.

### 9.2 Required project-catalog tests

1. Exactly eight projects exist: four SE and four DA.
2. Project IDs are unique and use the locked IDs.
3. Every project references exactly one approved track.
4. Every core and optional criterion exists in Rubric V2 and belongs to the same track.
5. Core and optional coverage do not overlap within a project.
6. Every project has foundations, outputs, completion checks, exclusions, and a source blueprint.
7. All projects include every project-category criterion for their own track in core coverage.
8. Global exclusion conditions are present.
9. Dataset-based projects include a safe, anonymised, public, or declared-synthetic data requirement.
10. Selection policy uses only positive core-covered point gaps, returns one project, and resolves ties by stable `project_id`.
11. Optional criteria do not contribute to the project coverage score.
12. Zero positive coverage returns `PROJECT_RECOMMENDATION_REVIEW_REQUIRED`.
13. The classifier includes its Python, API-foundation, and safe-data exclusions.
14. No project promises employment, a score increase, or a guaranteed completion time.
15. Required foundations are not automatic exclusions except explicit safety or complexity exclusions declared on a project.

### 9.3 Prohibited work

Do not implement or modify:

- Scoring functions.
- Priority-selection functions.
- Project-selection functions.
- Extraction, CV parsing, or link retrieval.
- APIs, Supabase, authentication, uploads, or repositories.
- Report rendering or PDFs.
- Package C golden fixtures.
- Rubric points, anchors, qualification values, caps, bands, or Package A schemas except the approved priority-action `current_anchor` / `target_anchor` terminology.
- Expo or scraper code.

Do not create a second rubric copy inside either catalogue. Reference stable rubric criterion IDs.

### 9.4 Verification and completion report

From `Server/`, run the repository's full test, coverage, Ruff, formatting, and Docker checks. Do not weaken a gate.

Return:

1. Files created or modified.
2. Action count, criterion coverage, and qualification-route count.
3. Project count and track split.
4. Test, coverage, Ruff, formatting, Docker, and CI results.
5. Any contract ambiguity encountered.
6. Confirmation that prohibited work was not added.
7. Final `git status --short`.
8. Commit SHA on `Tests` and the pull-request URL targeting `main`.

## 10. Completion gate

Package B is complete only when:

- The repository files match this decision brief and Engine Contract V1.1.
- All new and existing tests pass without weakened gates.
- CI passes on a pull request from `Tests` to `main`.
- Contract review finds no invented recommendation behaviour.
- The pull request remains unmerged until review is complete.

