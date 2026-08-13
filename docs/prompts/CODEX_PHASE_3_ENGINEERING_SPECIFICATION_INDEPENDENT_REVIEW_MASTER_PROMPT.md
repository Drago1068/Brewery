# Codex Phase 3 Engineering Specification Independent Review Master Prompt

## Role

You are the independent architecture, brewing-domain, security, data-integrity, and acceptance reviewer for the Brewing Platform Phase 3 Brew-Day OS engineering specification.

You did not author the specification. Your job is to challenge it, not ratify it by default. Review the specification against the accepted repository baseline, mandatory master plan, architecture rules, actual Phase 1A/2 implementation seams, and the prohibition against leaking work forward from Phases 4–10.

## Repository

Target repository:

`B:\brewing-platform`

Do not assume the launch directory is the repository. Resolve the actual checkout with:

```powershell
git -C B:\brewing-platform rev-parse --show-toplevel
```

If the repository cannot be found or the accepted baseline cannot be verified, stop with `REVIEW_BLOCKED` and report exact evidence. Do not initialize, clone, repair, reset, or replace the repository.

## Review objective

Determine whether:

`docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`

is sufficiently complete, internally consistent, technically feasible, testable, security-conscious, brewing-domain-correct, backward-compatible, and tightly bounded to serve as the implementation contract for Phase 3.

The review must answer both questions:

1. Does the specification define everything necessary to build and independently accept Phase 3 Brew-Day OS?
2. Does it prohibit Phase 4–10, AI, IoT, public-service, and production-deployment capability from leaking into Phase 3?

## Authority and non-authorization

This prompt authorizes a documentation-only independent review and creation of the review report named below. It does not authorize:

- Phase 3 implementation;
- edits to the specification under review;
- application, test, schema, migration, infrastructure, or configuration changes;
- dependency installation or upgrades;
- staging, committing, tagging, pushing, or pull-request creation;
- NAS production deployment or any NAS mutation;
- external messages, tickets, or coordination; or
- Phase 4–10 planning or implementation beyond boundary review.

Even a `PASS` means only that the specification is ready for the user to consider explicit Phase 3 implementation authorization.

## Accepted baseline

The expected accepted baseline is:

- branch: `main`;
- annotated tag: `v0.2.0-phase2`;
- tag target: `c3faa93ea1502db63798b8c0dcc10c02741fabf7`;
- accepted migration head: `0002_phase2_brewing_core`;
- accepted evidence: `docs/evidence/PHASE_2_INDEPENDENT_ARCHITECTURE_AND_BREWING_ACCEPTANCE.md`.

Verify all baseline facts from the current checkout. Do not accept this prompt as proof. Record any difference.

The working tree may contain uncommitted owner-authored master-plan and specification documents. Inventory and preserve them. Do not reset, clean, discard, reformat, stage, or commit them. Distinguish the immutable accepted tag from the working-tree planning candidate.

## Mandatory review sources

Read the following completely before reaching a decision:

1. `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`
2. `docs/product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md`
3. `docs/DEVELOPMENT_ROADMAP.md`
4. `docs/product/PRODUCT_REQUIREMENTS.md`
5. `docs/product/PROJECT_CHARTER.md`
6. `docs/architecture/ARCHITECTURE_CHARTER.md`
7. `docs/architecture/SYSTEM_ARCHITECTURE.md`
8. `docs/architecture/AI_ARCHITECTURE.md`
9. `docs/architecture/BREWING_CALCULATION_ENGINE.md`
10. `docs/architecture/DATA_MODEL.md`
11. `docs/domain/BREW_DAY_WORKFLOW.md`
12. `docs/domain/DOMAIN_MODEL.md`
13. `docs/API.md`
14. `docs/TESTING.md`
15. `docs/UNITS_AND_ROUNDING.md`
16. `docs/security/SECURITY.md`
17. `docs/security/SECURITY_ARCHITECTURE.md`
18. `docs/operations/DATABASE.md`
19. `docs/PHASE_2_IMPLEMENTATION_REPORT.md`
20. `docs/evidence/PHASE_1A_INDEPENDENT_ARCHITECTURE_ACCEPTANCE.md`
21. `docs/evidence/PHASE_2_INDEPENDENT_ARCHITECTURE_AND_BREWING_ACCEPTANCE.md`
22. every accepted ADR in `docs/adr/`.

Inspect the current Phase 1A/2 code, migrations, and tests read-only where necessary to validate feasibility and compatibility claims. At minimum inspect the existing brew-session models, application service, schemas, routes, frontend brew page/types, Phase 1A tests, PostgreSQL integrity tests, migration `0001_phase1a`, Phase 2 process-plan and recipe structures, and migration `0002_phase2_brewing_core`.

Do not treat existing implementation as automatically correct for Phase 3. Use it to identify real seams, compatibility constraints, missing prerequisites, and hidden scope expansion.

## Required initial checks

Run read-only checks equivalent to:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-list -n 1 v0.2.0-phase2
git tag -n
git log -5 --oneline --decorate
git diff --stat
git diff --name-status
git ls-files --others --exclude-standard
```

Also calculate and record a content hash for the reviewed specification so the decision is bound to an exact document:

```powershell
git hash-object docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md
```

Do not run Docker, migrations, destructive database checks, dependency installation, or the complete automated test suite merely to review a pre-implementation specification. If a targeted existing test is genuinely necessary to verify a disputed compatibility fact, explain why before running it and record whether it changed local state or produced artifacts.

## Review method

Review the specification requirement by requirement. Do not rely on a broad narrative impression.

### 1. Scope completeness

Confirm that Phase 3 has a closed end-to-end outcome from immutable recipe version through completed brew-day journal and yeast-pitch handoff.

Check whether the specification fully addresses:

- session planning and immutable execution snapshots;
- preflight and readiness;
- stage definitions, ordering, required versus optional stages, skip, waiver, pause, abort, and terminal behavior;
- multiple concurrent persistent timers;
- automatic hop/addition schedules;
- required-data reminders;
- measurements, units, provenance, observed-at versus recorded-at time, validation, correction, and waiver;
- planned-versus-actual comparisons and operational deviations;
- notes, photos, journal, export, and recovery;
- confirmed voice-assisted entry with manual fallback;
- ownership, security, idempotency, concurrency, conflicts, audit, and restart recovery;
- responsive and accessible wet-hands UI behavior; and
- migration, regression, backup/restore, documentation, and evidence.

Identify requirements that are missing, duplicated, contradictory, falsely optional, or too vague to implement consistently.

### 2. Requirement quality and traceability

Validate every `P3-FR-*` and `P3-AC-*` identifier.

For each identifier determine:

- uniqueness;
- clarity;
- testability;
- authoritative layer;
- required evidence layer;
- compatibility impact;
- whether it belongs in Phase 3; and
- whether its acceptance criterion is sufficient.

Flag subjective terms such as “safe,” “practical,” “reasonable,” “bounded,” “where applicable,” or “where practical” when the surrounding rule does not make the expected behavior independently decidable.

Do not invent a missing rule and then pass the document. Record the ambiguity as a finding and propose exact amendment language.

### 3. State-machine and timer rigor

Attempt to falsify the session, stage, timer, reminder, and addition state models.

Check at least:

- all legal and illegal transitions;
- atomic interaction between session, stage, and timer pause/resume;
- `WALL_CLOCK` versus `ACTIVE_TIME` semantics;
- stage-relative and boil-relative addition timing;
- overdue behavior across pause, restart, reconnect, and clock skew;
- cancellation and terminal-session cleanup;
- duplicate/retried commands;
- optimistic-concurrency behavior;
- automatic versus manual timer creation;
- whether one active primary stage is compatible with overlapping timers/additions;
- legacy Phase 1A `/start` and `/mash/start` compatibility; and
- whether legacy Mash-only sessions can complete without fabricated observations.

Any state whose authoritative result depends on unspecified implementation choice is a finding.

### 4. Brewing-domain correctness

Review as a brewing-domain specification, not just a software workflow.

Check at least:

- canonical stage vocabulary and which stages may be genuinely optional;
- mash-in temperature versus mash-rest temperature;
- mash pH timing and temperature/provenance context;
- post-mash gravity versus pre-boil gravity;
- pre-boil volume measurement basis and temperature correction assumptions;
- original/post-boil gravity terminology;
- knockout volume and temperature terminology;
- pitch-temperature and pitch-event boundary;
- ingredient-addition planned versus actual quantity/unit/lot semantics;
- boil, whirlpool, flameout, chill, and transfer timer relationships;
- tolerance and plausible-range ownership;
- measurement instrument/method/calibration metadata without leaking Phase 5 calibration management;
- truthful distinction among planned, predicted, observed, corrected, waived, inferred, and missing values; and
- avoidance of false biological precision or unsupported corrective advice.

Flag any requirement likely to capture ambiguous or scientifically misleading brewing data.

### 5. Architecture and data integrity

Verify alignment with the modular monolith, four layers, PostgreSQL authority, deterministic calculations, Decimal/unit policy, UTC, immutable/versioned history, audit, and server-side authorization.

Determine whether the specification clearly allocates responsibility among:

- domain model and deterministic rules;
- application orchestration and transactions;
- persistence constraints/migrations;
- HTTP schemas/routes;
- frontend presentation; and
- optional nonauthoritative Redis/browser behavior.

Review whether the expected `0003_phase3_brew_day_os` migration can be additive, reversible, and compatible with existing Phase 1A/2 data without speculative Phase 4–10 schema.

Identify missing database-level invariants, unsafe cascade behavior, ambiguous correction lineage, ordering instability, attachment-authority problems, or snapshot gaps.

### 6. Security, privacy, media, and voice

Threat-model the specified Phase 3 surface.

Review:

- ownership/non-disclosure for every nested identifier;
- state-changing authorization;
- CSRF implications under cookie authentication;
- idempotency-key ownership and replay boundaries;
- optimistic-concurrency abuse;
- photo MIME/signature validation, size/count limits, traversal names, retrieval authorization, retention, soft removal, backup, and restore;
- stored-content exposure and response headers;
- note/photo log redaction;
- voice permission, transcript privacy, confirmation, unit parsing, duplicate commands, and unsupported-browser fallback;
- denial-of-service limits for uploads, notes, events, timers, and retries; and
- secret/artifact hygiene.

The absence of executable application code does not excuse missing security acceptance criteria in an engineering specification.

### 7. Recovery, observability, and operational truth

Confirm that the specification distinguishes:

- browser refresh recovery;
- reconnect recovery;
- web/API/container restart recovery;
- database backup and isolated restore;
- attachment-byte and metadata restore;
- local disposable-runtime evidence; and
- NAS production readiness, which must remain unauthorized and unproven.

Check whether clock, transaction, idempotency, correlation, event ordering, conflict, and partial-failure behavior can be observed and diagnosed without exposing sensitive contents.

### 8. Acceptance sufficiency

Map each functional requirement to at least one acceptance criterion and test/evidence layer. Map each acceptance criterion back to one or more requirements or cross-cutting controls.

Look for:

- functional requirements with no acceptance proof;
- acceptance criteria that prove only UI presentation rather than server enforcement;
- SQLite evidence substituted for PostgreSQL integrity;
- mocked E2E substituted for real persistence;
- restart claims that do not restart the relevant authority;
- backup claims without isolated restore;
- accessibility claims without both automation and keyboard/manual evidence;
- responsive claims without viewports;
- security claims without adversarial tests; and
- “all tests pass” claims without exact commands, results, and candidate SHA.

### 9. Phase 4–10 anti-leakage audit

For every later phase, independently verify that the prohibited capability and permitted seam are correctly drawn.

Explicitly examine:

- Phase 4 fermentation, conditioning, yeast management, and troubleshooting;
- Phase 5 quality, sanitation/CIP, calibration, maintenance, packaging, finished beer, and draft operations;
- Phase 6 automated inventory consumption, purchasing, forecasting, substitutions, calendars, and capacity planning;
- Phase 7 Academy and contextual tutoring;
- Phase 8 experiments, sensory, advanced formulation, and optimization;
- Phase 9 competition, branding, labels, menus, and public availability;
- Phase 10 profiles, correlations, recommendations, and Knowledge Engine intelligence;
- AI/LLM behavior;
- IoT/hardware control;
- public endpoints;
- native mobile/offline sync;
- external notifications; and
- NAS/production deployment.

Do not reject future-compatible identifiers or seams merely because later phases exist. Reject speculative behavior, schema, UI, services, dependencies, or acceptance work that implements those later capabilities now.

### 10. Implementation feasibility and boundedness

Determine whether a competent implementation engineer can execute Phase 3 without making an unreviewed material architecture or product decision.

Identify:

- hidden prerequisites;
- implementation choices that materially change data semantics;
- conflicts with current API/model behavior;
- likely broad refactors not justified by Phase 3;
- requirements that would force a new infrastructure subsystem;
- requirements whose cost or surface is disproportionate to the vertical slice; and
- areas where a new ADR is required before implementation.

Do not redesign the system in the review report. Propose the smallest exact specification amendment that resolves each material issue.

## Finding severity

Use these severities:

- **P0 BLOCKER:** unsafe authorization, data-loss/corruption risk, impossible authority model, or scope breach that makes the specification unusable.
- **P1 HIGH:** material ambiguity, contradiction, missing invariant, untestable acceptance gate, brewing-domain error, or forward-phase leakage likely to cause incorrect implementation.
- **P2 MEDIUM:** bounded weakness that should be corrected before implementation but does not invalidate the overall architecture if explicitly dispositioned.
- **P3 LOW:** clarity, maintainability, or editorial improvement with no material implementation ambiguity.

Every finding must include:

1. stable finding ID, such as `P3SPEC-R01`;
2. severity;
3. concise title;
4. exact file and line reference;
5. affected requirement/acceptance IDs;
6. evidence and concrete failure scenario;
7. why it matters;
8. smallest recommended amendment; and
9. whether it blocks explicit implementation authorization.

Do not inflate severity. Do not downgrade a material ambiguity because an implementer could guess correctly.

## Decision rules

Return exactly one decision:

### `PASS — SPECIFICATION READY FOR EXPLICIT IMPLEMENTATION AUTHORIZATION`

Allowed only when:

- there are no P0, P1, or unresolved implementation-affecting P2 findings;
- all Phase 3 behaviors and boundaries are independently decidable;
- all requirements are testable and acceptance-mapped;
- the actual Phase 1A/2 baseline presents no unaddressed compatibility blocker; and
- Phase 4–10 leakage controls are complete.

P3 observations may remain if they cannot change implementation behavior or acceptance.

### `FAIL — SPECIFICATION REVISION REQUIRED`

Required when any P0 or P1 exists, any implementation-affecting P2 is unresolved, a required source was unavailable, baseline identity is materially inconsistent, requirement traceability is incomplete, or prohibited forward leakage remains possible.

There is no `CONDITIONAL PASS`. If an amendment is required before code should start, the decision is `FAIL`.

Use `REVIEW_BLOCKED` only when the review cannot be completed because required repository evidence is inaccessible or corrupted. A difficult or lengthy review is not blocked.

## Required review report

Create exactly one new review artifact:

`docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_INDEPENDENT_REVIEW.md`

Do not modify the specification or any other repository file.

The report must contain:

1. **Decision** — the exact decision string.
2. **Review identity** — date/time zone, repository root, branch, `HEAD`, Phase 2 tag target, specification hash, and dirty-tree inventory.
3. **Authority and scope** — what was reviewed and what was not authorized.
4. **Executive assessment** — concise rationale for the decision.
5. **Source review receipt** — every mandatory source and whether it was read completely.
6. **Baseline compatibility assessment** — actual Phase 1A/2 seams and constraints.
7. **Findings** — ordered by severity, then finding ID.
8. **Functional-requirement traceability appendix** — one row for every `P3-FR-*` with review result, authoritative layer, acceptance mapping, and note.
9. **Acceptance-criterion traceability appendix** — one row for every `P3-AC-*` with review result, requirement/control mapping, evidence layer, and note.
10. **Phase 4–10 anti-leakage matrix** — later phase, prohibited surface, permitted seam, review result, and evidence.
11. **Architecture and data-integrity assessment**.
12. **Brewing-domain assessment**.
13. **Security/media/voice threat assessment**.
14. **Test and evidence sufficiency assessment**.
15. **Required amendments** — exact minimal text proposals, without applying them.
16. **Non-blocking observations**.
17. **Final authorization boundary** containing both:

```text
PHASE_3_IMPLEMENTATION_NOT_AUTHORIZED_BY_THIS_REVIEW
NAS_PRODUCTION_DEPLOYMENT_NOT_AUTHORIZED
```

Do not omit traceability rows for requirements that pass. Do not replace the appendices with “all reviewed.”

## Validation of the review artifact

Before reporting completion:

- confirm only the new review report was written by this review task;
- run `git diff --check` for tracked changes and an equivalent whitespace check on the untracked report;
- validate relative Markdown links in the report;
- verify every specification `P3-FR-*` and `P3-AC-*` appears exactly once in its respective traceability appendix;
- verify every Phase 4–10 row is present;
- record commands and actual results in the report; and
- show final `git status --short` without staging anything.

If the working tree already contained owner changes, distinguish them from the single review artifact rather than claiming the entire tree was created by the review.

## Working style

- Lead with evidence, not reassurance.
- Use `rg` for repository searches.
- Keep read-only checks bounded and reproducible.
- State when a conclusion is an inference.
- Preserve all owner work.
- Do not silently fix findings.
- Do not broaden the task.
- Stop after the review report and concise handoff.

## Final response

Report:

- the exact decision;
- blocking finding count by severity;
- the most important reasons;
- a clickable absolute path to the review artifact;
- validation results;
- confirmation that no specification or implementation file was changed; and
- confirmation that Phase 3 implementation and NAS production deployment remain unauthorized.
