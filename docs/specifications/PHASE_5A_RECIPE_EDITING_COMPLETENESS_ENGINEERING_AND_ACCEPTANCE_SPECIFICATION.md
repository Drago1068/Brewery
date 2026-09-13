# Phase 5A Engineering and Acceptance Specification — Recipe-Editing Completeness

## 1. Purpose and executive scope

Phase 5A makes recipe formulation fully editable **before** immutable version
publication. The brewer can create a draft, add/edit/remove/reorder ingredient
additions (amount, unit, stage, timing), configure mash-step order, and publish
the result as a new immutable `RecipeVersion` whose deterministic calculations
are snapshotted under accepted rule versions.

Phase 5A changes no accepted architecture. It adds draft-editing behavior
(client working state plus server-validated publication) and one server-side
uniqueness guard. It does not alter Phase 0–4 contracts, reinterpret history,
or authorize any Phase 5B, packaging, automation, or deployment scope (§23).

Normative identifiers in this document are `P5A-FR-###` (functional
requirements), `P5A-AC-###` (acceptance criteria), and `P5A-ADV-###`
(adversarial scenarios). Every identifier is unique (§30); every FR maps to
acceptance evidence; every AC has a deterministic pass/fail oracle; every ADV
has a deterministic expected result.

## 2. Authoritative inputs and precedence

In descending precedence:

1. Project Charter (immutability principles 3 and 8; calculation principle 11).
2. Architecture Charter (server-side authorization, explicit units, UTC
   storage, deterministic calculation authority, mandatory migrations).
3. Master Plan (immutable recipe versioning and formulation lineage; AI may
   not silently mutate recipes).
4. `docs/RECIPE_DOMAIN.md` (version-owned formulation data; accepted
   PostgreSQL trigger blocks update/delete of versions used by brew sessions).
5. ADR-0003 (immutable history), ADR-0004 (deterministic calculations),
   ADR-0008 (canonical units and rounding), ADR-0010 (recipe calculation
   snapshots), ADR-0011 (inventory reservation semantics).
6. `UNITS_AND_ROUNDING`, `CALCULATION_ENGINE`, Phase 2 API schemas, `TESTING`.
7. The accepted Phase 5A implementation (`9dea54c`) and its tests, as
   **evidence of behavior**, never as authority over §§1–6.

Conflicts resolve upward. A conflict with an accepted ADR or the master plan
stops implementation pending an ADR or specification amendment.

## 3. Accepted baseline and compatibility boundary

- Accepted baseline: Phase 4 closure, tag `v0.4.0-phase4`; Phase 5A range
  begins at `8c4c8c3` (docs-only) with first implementation `9dea54c`.
- Phase 5A consumes accepted Phase 1A recipe flows, Phase 2 version/inventory
  facts, Phase 3 brew-day snapshots, and Phase 4 fermentation evidence without
  redefining them. Live `RecipeVersion`, `BrewSession`, inventory ledger, and
  fermentation rows are never rewritten by Phase 5A commands (§22).

## 4. Phase 5A domain vocabulary

- `Draft`: client-side working state (ingredient lines, mash steps, header
  fields). No persisted draft entity exists.
- `DraftLine`: `{ingredient_id, amount, unit, use_stage, timing_minutes?}`.
- `MashStepDraft`: `{name, duration_minutes, temperature_c}` (all strings
  pre-publication).
- `RecipeVersion`: immutable published formulation + calculation snapshot
  (unchanged meaning).
- `Publication`: the atomic command that validates a draft and persists a new
  version (create) or a successor version (clone/scale).
- Canonical units: `g | L | each` (ADR-0008).
- Use stages: `MASH, FIRST_WORT, BOIL, WHIRLPOOL, DRY_HOP, FERMENTATION,
  PACKAGING, MISCELLANEOUS` (accepted `RecipeIngredientInput` vocabulary).

## 5. Actor, ownership, and authorization model

- P5A-FR-001: Every recipe command requires an authenticated owner; anonymous
  recipe mutation is denied (`401`).
- P5A-FR-002: Every referenced `EquipmentProfile`, `Ingredient`, and
  `IngredientLot` must be owned by the caller; cross-owner IDs return `404`
  nondisclosure and write nothing.
- P5A-FR-003: A cited lot must belong to the cited ingredient
  (`422` otherwise); lot linkage remains optional.

## 6. Recipe lifecycle and state model

States: `DRAFT` (client-only) → `PUBLISHED` (immutable version). There is no
server-side draft, no publish queue, and no version-edit operation.

- P5A-FR-004: `DRAFT` lives only in client memory; refresh or navigation may
  discard it. The server never stores, recovers, or merges drafts.
- P5A-FR-005: Publication (`POST /recipe-designs`) validates the full draft
  and atomically persists exactly one new `Recipe` with `version_number = 1`.
- P5A-FR-006: Continued editing after publication starts a new `DRAFT`
  (client-side copy); publishing it creates a **new** version lineage entry,
  never a mutation of the published version.
- P5A-FR-007: Clone/scale (`POST /recipe-designs/{id}/clone`) inserts the
  next version number and copies/scales lines and steps; the source version is
  byte-identical afterwards.
- P5A-FR-008: No command updates or deletes a published `RecipeVersion`. The
  accepted PostgreSQL trigger remains the backstop for versions referenced by
  brew sessions.
- P5A-FR-009: A `BrewSession` consumes the referenced version snapshot at
  session creation; later recipe publications do not alter that snapshot.

## 7. Draft-editing contract

- P5A-FR-010: Draft lines support create, amount/unit/stage/timing update,
  removal, and positional reorder; mash steps support add, edit, remove, and
  up/down reorder. All operations are pure client-state transitions until
  publication.
- P5A-FR-011: Rejected patches leave the draft line unchanged (no silent
  partial mutation); the UI surfaces the reason and blocks saving while any
  line or step error persists.
- P5A-FR-012: Removing a draft line or step affects only the unpublished
  draft; published versions and other drafts are untouched.

## 8. Immutable version-publication contract

- P5A-FR-013: Publication validates the entire draft first; any failure
  rejects the whole command with zero persisted rows (no partial version,
  lines, steps, snapshots, or audit).
- P5A-FR-014: Success persists version row, ingredient lines, process steps,
  equipment snapshot, calculation inputs/outputs with rule versions, and a
  `RECIPE_VERSION_CREATED` audit event in one database transaction.

## 9. Ingredient editing

- P5A-FR-015: Duplicate lines for one ingredient are permitted as separate
  draft lines; each persists as its own `RecipeIngredient` row.
- P5A-FR-016: Amount must be a positive `Decimal` (`gt=0`); zero, negative,
  and non-numeric amounts are rejected (`422`).
- P5A-FR-017: Unit must equal the ingredient's canonical unit; mismatches are
  rejected server-side (`400`) regardless of UI options.
- P5A-FR-018: `use_stage` must be a vocabulary member (§4); unknown stages
  are rejected (`422`).
- P5A-FR-019: `timing_minutes`, when supplied, must satisfy `0 ≤ t ≤ 10080`
  (`422` otherwise). A missing timing persists as null except where §13
  documents calculation defaults.

## 10. Process-step editing

- P5A-FR-020: The designer emits `MASH` steps plus one appended `BOIL` step
  derived from the boil duration. `FERMENTATION_FOUNDATION` and
  `PACKAGING_FOUNDATION` vocabulary remains reserved for accepted non-designer
  paths.
- P5A-FR-021: Step `sequence` values must be unique within one publication
  (`400` "Process step sequences must be unique"); the server persists
  submitted sequences verbatim and orders canonically by
  `(sequence ASC, id ASC)`.
- P5A-FR-022: Step `name` is required (`1–160` chars); `duration_minutes`, when
  supplied, must be `≥ 0`; `temperature_c`, when supplied, is a descriptive
  `Decimal` with no normative brewing range (see ADV-001).

## 11. Equipment-profile association

- P5A-FR-023: Publication requires an owned `EquipmentProfile`; its
  calculation-relevant fields are snapshotted per ADR-0010. Later profile
  edits never recalculate published versions.

## 12. Units, Decimal precision, canonicalization, and rounding

- P5A-FR-024: Canonical units per ADR-0008; mixed-unit writes rejected.
- P5A-FR-025: Authoritative math uses `Decimal` throughout; intermediate
  results are never rounded.
- P5A-FR-026: Amounts persist at `Numeric(14,4)`; values beyond 4 fractional
  digits are **rounded at the persistence boundary** (documented, not
  rejected). The UI limits entry to 4 decimals as a convenience; the column
  rule is authoritative.
- P5A-FR-027: Display rounding (amounts 4dp, OG/FG 3dp, ABV/IBU/SRM/water
  1dp) is presentation-only and never feeds back into calculations.

## 13. Calculation inputs, outputs, provenance, and rule versions

- P5A-FR-028: "AI recommends and reasons; deterministic software calculates,
  validates, records, and enforces rules." No LLM output is numeric authority.
- P5A-FR-029: Snapshots persist normalized inputs, authoritative outputs,
  formula/model identifiers, and the unit/rounding policy version (ADR-0010).
- P5A-FR-030: Hop IBU follows the shared `tinseth_ibu` authority; the
  publication golden in §28 pins equivalence.
- P5A-FR-031: Recalculation occurs only on publication (create/clone/scale).
  Published versions are never recalculated in place.
- P5A-FR-032: Clarification of review wording: BOIL-timing "required" and
  four-decimal "maximum" are **UI-layer** rules. Server behavior is unchanged:
  a BOIL line without timing computes IBU with timing 0 (documented default),
  and amounts obey P5A-FR-026. Neither rule weakens an accepted invariant.

## 14. Validation and error semantics

- P5A-FR-033: Schema violations → deterministic `422`; domain violations →
  `400` by default (`DomainError`); ownership/not-found → `404`
  nondisclosure; unauthenticated → `401`; CSRF failure → `403`.
- P5A-FR-034: Every rejection path is zero-mutation (no version, line, step,
  snapshot, inventory, or audit rows).

## 15. Idempotency, optimistic concurrency, retries, and conflict handling

- P5A-FR-035: Recipe create/clone commands carry no idempotency keys and no
  expected revision in the accepted contract. A retried or double-submitted
  publication creates distinct versions; this is documented behavior, not
  silent duplication — versions are distinguishable by ID and timestamps.
- P5A-FR-036: Publication is atomic (§8); response loss is recovered by
  listing versions and reconciling, never by server-side replay.
- P5A-FR-037: Any **future** mutating recipe command (update/publish/revise
  semantics) MUST carry `operation_id` scoping plus `expected_revision`
  optimistic concurrency, with same-key replay and changed-payload conflict
  semantics defined in its authorizing specification before implementation.

### 15.1 Two-tab, stale-reference, and retry determinism

The following rules decide every concurrent-use case under P5A-FR-004,
P5A-FR-035, and P5A-FR-036 without introducing persisted drafts, operation
identities, catalog lifecycle states, or new architectural policy:

- T1: Each browser tab holds an independent client-only draft. Tabs share no
  state, take no lock, and carry no revision.
- T2: When tab A publishes, tab B observes nothing until it queries the
  server; B's draft is unchanged, and B's later publication creates an
  independent version. Publications never merge.
- T3: Equivalent concurrent submissions create distinct versions; different
  concurrent submissions create distinct versions. No conflict error exists
  between independent creates.
- T4: Duplicate submission and response loss follow P5A-FR-035 and P5A-FR-036:
  resubmission creates a new version; the client reconciles via the version
  list. No version is ever silently duplicated into one row.
- T5: Ownership and authorization are revalidated on every command per
  P5A-FR-001 and P5A-FR-002. Credentials revoked or lots/equipment
  reassigned mid-draft cause the next publication to fail (`401`/`404`)
  with zero writes; the draft itself is unaffected.
- T6: No publication path rewrites a published version or a BrewSession
  snapshot (P5A-FR-008, P5A-FR-009), including publications submitted from a
  second tab or after a retry.
- T7: Ingredient, equipment, unit, and process-step references are
  revalidated server-side at publication. Deleted, deactivated, reassigned,
  or otherwise unavailable identities fail (`404` for foreign ownership or
  missing rows, `422` for broken lot→ingredient linkage); a changed
  ingredient canonical unit fails the line (`400`); catalog edits never alter
  already-published versions.
- T8: Calculation inputs are recomputed exclusively from the submitted
  payload plus the pinned equipment snapshot (P5A-FR-023, P5A-FR-029). Data
  from another tab's draft is never an input.
- T9: Rejected publications are atomic with zero partial writes (P5A-FR-013,
  P5A-FR-034).
- T10: On `4xx`, the UI preserves the draft, surfaces the server reason, and
  permits edit-and-retry. On network failure, the draft is preserved locally
  and retry resubmits as a new publication subject to T4; the UI directs the
  user to reconcile via the version list.

## 16. PostgreSQL authority, constraints, and transactions

- P5A-FR-038: PostgreSQL is authoritative; the accepted immutability triggers
  remain installed and enforced.
- P5A-FR-039: Publication (including clone/scale fan-out of lines and steps)
  commits in a single transaction; concurrent publications serialize on
  database constraints without interleaved partial structures.

## 17. Audit/event requirements

- P5A-FR-040: Successful creation persists `RECIPE_VERSION_CREATED`; clone
  persists `RECIPE_VERSION_CLONED`; each names the new version ID.
- P5A-FR-041: Rejected publications persist no audit rows.

## 18. API contract

- P5A-FR-042: `POST /recipe-designs` → `201` with version, lines, steps, and
  calculations; `POST /recipe-designs/{id}/clone` scales/clones; `GET`
  rereads are byte-stable across calls.
- P5A-FR-043: Mutations require CSRF + owner authentication. Recipe
  `RecipeDesignCreate`-family schemas do **not** declare closed semantics in
  the accepted contract: unknown fields follow Pydantic defaults (ignored,
  never mapped to domain fields). Closing them is deferred to a future
  specification; see P5A-ADV-013.

## 19. UI behavior and truthful presentation

- P5A-FR-044: Pre-save validation mirrors §9–§11 rules and blocks saving with
  per-field reasons; the server revalidates everything (UI is never
  authority).
- P5A-FR-045: The calculation summary displays the last **saved** version's
  persisted outputs (`aria-live="polite"`); draft edits are never presented
  as computed results.
- P5A-FR-046: Errors use exposed alert roles; save is disabled while busy or
  with zero lines.

## 20. Accessibility and responsive behavior

- P5A-FR-047: Every input has an accessible label; mash-step reorder controls
  are keyboard-operable buttons with disabled endpoints.
- P5A-FR-048: Formulation and mash-step grids collapse at the established
  `1050px / 860px / 600px` breakpoints without loss of controls.

## 21. Migration, upgrade, downgrade, backup, and restore expectations

- P5A-FR-049: Phase 5A recipe editing requires **no** migration; Alembic head
  remains `0015_phase4_journal_media_export`.
- P5A-FR-050: Any future 5A schema change requires an Alembic revision with
  upgrade **and** downgrade paths exercised on disposable PostgreSQL.
- P5A-FR-051: Backup/restore inherits platform behavior; there is no
  persisted draft state to preserve (P5A-FR-004).

## 22. Phase 1A–4 compatibility requirements

- P5A-FR-052: Accepted Phase 1A recipe flows, Phase 2 version/inventory facts,
  Phase 3 snapshots and history, and Phase 4 sessions/measurements/derived
  values/correction lineage MUST remain valid; proof is the unchanged
  regression suites (§30) plus the immutability trigger tests.

## 23. Explicit Phase 5B and later exclusions

Phase 5A does **not** authorize: fermentation-rule changes; packaging, kegging,
bottling, carbonation, taps, or menus; operational or purchasing automation;
Academy curriculum; sensory panels or experiments; competition or branding
systems; Knowledge Engine operation; autonomous AI mutation of recipes,
inventory, or history; or production deployment.

## 24. Security and privacy requirements

- P5A-FR-053: Owner isolation on every recipe read and write; cross-user IDs
  return `404` without disclosing existence.
- P5A-FR-054: No new personal data is collected; recipe payloads contain only
  formulation data already covered by the platform privacy posture.

## 25. Observability and failure behavior

- P5A-FR-055: Recipe commands travel the existing structured request-logging
  and correlation-ID middleware; no new metrics are required.
- P5A-FR-056: Unexpected failures return deterministic `500` without partial
  writes; validation failures never fabricate versions.

## 26. Performance expectations

- P5A-FR-057: Draft editing performs zero per-keystroke server calls (local
  state). Publication cost stays within the existing suite envelope; no new
  server-side performance gate is introduced.

## 27. Functional requirements (registry)

P5A-FR-001 through P5A-FR-057 as declared in §§5–26. Counts are descriptive,
not targets.

## 28. Acceptance criteria

- P5A-AC-001: Publish edited amounts/units/stages/timings + ordered mash
  steps → `201`, `version_number = 1`, persisted lines/steps/calculations
  match input. Oracle: `test_recipe_addition_edits_persist_on_immutable_version`
  green.
- P5A-AC-002: Clone with new batch size → next version number; source version
  reread byte-identical including calculations. Oracle: same test, clone
  section green.
- P5A-AC-003: Zero amount, unknown unit, unknown stage, negative timing each
  → deterministic rejection with zero mutation. Oracle: validation test green.
- P5A-AC-004: Duplicate step sequences → `400` naming uniqueness with zero
  mutation. Oracle: duplicate-sequence test green.
- P5A-AC-005: Unit mismatch → `400` naming the canonical unit. Oracle:
  mismatch test green.
- P5A-AC-006: Hop IBU equals shared `tinseth_ibu` on identical inputs.
  Oracle: IBU golden test green.
- P5A-AC-007: Draft helpers accept/reject exactly the documented vectors
  (amount, unit, stage, timing, mash CRUD/order). Oracle:
  `designer.test.ts` 9/9 green.
- P5A-AC-008: Full production build compiles with the designer route
  present. Oracle: `next build` exit 0.
- P5A-AC-009: Phase 1A–4 regression sample green (no compatibility break).
  Oracle: §30 suite list green.
- P5A-AC-010: PostgreSQL publication + migration head green. Oracle: 5A tests
  on disposable PG green; single Alembic head verified.
- P5A-AC-011: Lint/type gates green. Oracle: ESLint clean, `tsc --noEmit`
  clean, ruff clean on changed backend files.

## 29. Adversarial scenarios

- P5A-ADV-001: Negative mash-step temperature via forged payload → accepted
  as descriptive data (documented P5A-FR-022 boundary) OR rejected if a future
  range rule is adopted; never feeds calculations. Expected: `201` today with
  value persisted verbatim.
- P5A-ADV-002: Amount with 6 fractional digits via forged payload →
  persisted rounded to 4dp per P5A-FR-026; response echoes persisted value.
  Expected: `201`, stored `amount` has ≤ 4dp.
- P5A-ADV-003: BOIL line without timing via forged payload → `201`;
  IBU computed with timing 0 per P5A-FR-032. Expected: deterministic output,
  no rejection.
- P5A-ADV-004: Duplicate sequences via forged payload. Expected: `400`,
  zero rows.
- P5A-ADV-005: Cross-user equipment/ingredient/lot IDs. Expected: `404`,
  zero rows.
- P5A-ADV-006: Unknown `use_stage`. Expected: `422`, zero rows.
- P5A-ADV-007: Non-integer timing (`"1.5"`). Expected: `422`, zero rows.
- P5A-ADV-008: Empty ingredient list. Expected: `422` (`min_length=1`),
  zero rows.
- P5A-ADV-009: Double-submit identical payload. Expected: two distinct
  versions, no partial rows (P5A-FR-035 documented behavior).
- P5A-ADV-010: Refresh mid-edit → draft lost client-side; server holds no
  draft (P5A-FR-004). Expected: fresh empty draft, no server error.
- P5A-ADV-011: Clone of a version already used by a brew session. Expected:
  new version; source and session snapshot unchanged.
- P5A-ADV-012: Reordered mash steps with swapped sequences. Expected:
  persisted in submitted order; canonical read-back ordered by
  `(sequence, id)`.
- P5A-ADV-013: Unknown top-level field on `POST /recipe-designs` → ignored
  per P5A-FR-043; publication proceeds on documented fields only. Expected:
  deterministic `201` with unknown field absent from persisted rows.

## 30. Requirement-to-test traceability

| Requirement(s) | Acceptance | Test |
|---|---|---|
| P5A-FR-004–P5A-FR-007, P5A-FR-010–P5A-FR-023, P5A-FR-027–P5A-FR-031 | P5A-AC-001, P5A-AC-002 | `test_recipe_addition_edits_persist_on_immutable_version` |
| P5A-FR-013–P5A-FR-019, P5A-FR-021, P5A-FR-024, P5A-FR-033–P5A-FR-034 | P5A-AC-003–P5A-AC-005 | `test_recipe_addition_validation_rejects_invalid_amount_unit_stage_timing` (status paths) + required zero-mutation DB-count test |
| P5A-FR-025, P5A-FR-028, P5A-FR-030 | P5A-AC-006 | `test_valid_canonical_unit_and_boil_timing_feed_calculations` |
| P5A-FR-010–P5A-FR-012, P5A-FR-016–P5A-FR-019, P5A-FR-025, P5A-FR-044, P5A-FR-046 | P5A-AC-007 | `designer.test.ts` (9 vectors) |
| P5A-FR-042–P5A-FR-043, P5A-FR-047–P5A-FR-048 | P5A-AC-008, P5A-AC-011 | `next build`, `tsc`, ESLint |
| P5A-FR-001–P5A-FR-003, P5A-FR-008–P5A-FR-009, P5A-FR-022, P5A-FR-038–P5A-FR-041, P5A-FR-045, P5A-FR-049–P5A-FR-057 | P5A-AC-009, P5A-AC-010 | Phase 1A–4 suites, PG suites, trigger/migration/backup suites + required audit-row test |
| P5A-FR-026, P5A-FR-032 | P5A-AC-003, P5A-AC-006 | ADV-002/ADV-003 required forged-payload tests |
| P5A-FR-035–P5A-FR-036 | P5A-AC-009 | ADV-009 required double-submit test |
| P5A-FR-043 | P5A-AC-003 | ADV-013 required unknown-field test |
| P5A-FR-037 | §31 future-work gate (no implementation permitted yet) | specification review at next 5A work package |

### 30.1 Adversarial traceability matrix

Each row names the mapped FR, mapped AC, enforcement layer, required test
type, uniquely identifiable required test, deterministic pass oracle, and
required evidence. "Existing" tests are accepted behavior evidence;
"required" tests must be green before the gate in §31 closes.

| ADV | FR | AC | Enforcement layer | Required test type | Required test | Pass oracle and evidence |
|---|---|---|---|---|---|---|
| P5A-ADV-001 | P5A-FR-022 | P5A-AC-003 | API schema (accepts, descriptive) | Forged-payload API test (required) | `test_recipe_mash_step_negative_temperature_persists_verbatim` | `201`; DB `temperature_c` equals input; calculations unchanged; test green |
| P5A-ADV-002 | P5A-FR-026 | P5A-AC-003, P5A-AC-006 | PostgreSQL `Numeric(14,4)` boundary | Forged-payload API test (required) | `test_recipe_amount_rounds_at_persistence_boundary` | `201`; stored amount has ≤ 4dp; response echoes stored value; test green |
| P5A-ADV-003 | P5A-FR-030, P5A-FR-032 | P5A-AC-006 | Calculation default | Forged-payload API test (required) | `test_recipe_boil_missing_timing_defaults_zero` | `201`; IBU equals shared-authority value at timing 0; test green |
| P5A-ADV-004 | P5A-FR-021 | P5A-AC-004 | Application validation | API contract test (existing) | Duplicate-sequence case in `test_recipe_addition_validation_rejects_invalid_amount_unit_stage_timing` | `400` naming uniqueness; zero rows; suite green |
| P5A-ADV-005 | P5A-FR-002, P5A-FR-003 | P5A-AC-009 | Ownership scoping | API security test (required) | `test_recipe_cross_user_ids_rejected_nondisclosure` (equipment, ingredient, lot) | `404` each; zero rows; test green |
| P5A-ADV-006 | P5A-FR-018 | P5A-AC-003 | API schema | API contract test (existing) | Unknown-stage case in `test_recipe_addition_validation_rejects_invalid_amount_unit_stage_timing` | `422`; zero rows; suite green |
| P5A-ADV-007 | P5A-FR-019 | P5A-AC-003 | API schema | API contract test (required) | `test_recipe_fractional_timing_rejected` | `422`; zero rows; test green |
| P5A-ADV-008 | P5A-FR-005 | P5A-AC-003 | API schema | API contract test (required) | `test_recipe_empty_ingredients_rejected` | `422`; zero rows; test green |
| P5A-ADV-009 | P5A-FR-035, P5A-FR-036 | P5A-AC-009 | Application + client reconcile | API idempotency test (required) | `test_recipe_double_submit_creates_distinct_versions` | Two `201`s with distinct IDs, both rows complete, no partial rows; test green |
| P5A-ADV-010 | P5A-FR-004 | P5A-AC-007 | Client state | Frontend unit test (required) | `test_draft_does_not_persist_across_remount` | Fresh mount yields default draft; zero network calls; test green |
| P5A-ADV-011 | P5A-FR-007, P5A-FR-009 | P5A-AC-002 | Application + trigger | API compatibility test (required) | `test_clone_used_version_preserves_source_and_snapshot` | New version number; source byte-identical; session snapshot unchanged; test green |
| P5A-ADV-012 | P5A-FR-021 | P5A-AC-001 | Application + canonical order | API contract test (existing) | Ordered-steps DB assertion in `test_recipe_addition_edits_persist_on_immutable_version` | Read-back ordered by `(sequence, id)`; suite green |
| P5A-ADV-013 | P5A-FR-043 | P5A-AC-003 | API schema defaults | API contract test (required) | `test_recipe_unknown_field_ignored_deterministically` | Deterministic `201`; unknown field absent from rows; test green |

## 31. Implementation and acceptance gates

1. All P5A-AC oracles green on SQLite and (where PG-gated) disposable
   PostgreSQL; single Alembic head verified.
2. `designer.test.ts`, ESLint, `tsc --noEmit`, `next build` green.
3. Ruff clean on changed backend files.
4. No P0/P1/P2 findings; P3/advisory dispositions recorded.
5. Independent review artifact committed before any integration.
6. No main merge, tag, release, or deployment.

## 32. Deferred items and ADR boundaries

- Phase 4 F-008 (correction composite FK): DEFERRED, unchanged.
- Phase 4 F-009 (derived-gravity tie-break): DEFERRED, unchanged.
- Phase 4 F-010 (temperature-sensitive method taxonomy): ADR_REQUIRED_
  NONBLOCKING, unchanged.
- Phase 5A review P3-GOV-001: closed for the bounded 5A-1 scope by this
  specification's explicit authorization language (§§1, 23, 31). This spec
  authorizes **only** the recipe-editing contract herein; it does not
  authorize Phase 5B, later phases, main integration, or deployment.
- Phase 5A review P3-TRUTH-001: clarified by P5A-FR-026 and P5A-FR-032
  (server contract stated exactly; UI scoping explicit).
- Phase 5A advisories ADV-001 (descriptive step bounds) and ADV-002 (updater
  purity): DEFERRED with acceptance conditions in §29 ADV-001 and future
  frontend hygiene respectively.
- Persisted drafts, publish queues, recipe update/delete semantics, and any
  `operation_id`/`expected_revision` recipe protocol are deferred to a future
  specification (anticipated by P5A-FR-037); inventing them now is prohibited.
