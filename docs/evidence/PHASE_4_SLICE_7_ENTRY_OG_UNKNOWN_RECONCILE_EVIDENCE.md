# Phase 4 Slice 7 Evidence — Entry OG Unknown & Reconciliation

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `34cfcf0ec277befc477b665f07142c8d0fe75032` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_6_DELTA_REVIEW.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `ENTRY_OG_UNKNOWN_AND_RECONCILE` |
| Ancestry from `v0.4.0-phase4-spec` | PASS |

## Exact requirement extraction

| ID | SPEC_SECTION | NORMATIVE_RULE | DEPENDENCIES | CURRENT_PARTIAL | MISSING_BEFORE | SURFACE |
|---|---|---|---|---|---|---|
| P4-FR-004 | §6.2.1 / §28 | Absent accepted brew-side `ORIGINAL_GRAVITY` leaf → persist `og_availability=UNKNOWN` with null value/IDs; start still allowed; never treat `FERMENTATION_GRAVITY` as OG; no fabricated numeric sentinel. | ENTRY / BrewSession / measurement leaf | Start required KNOWN OG | UNKNOWN pin + entry path | `og_consumption.py::pin_og_at_start`, start command |
| P4-FR-005 | §6.2.1 / §28 | `ReconcileUpstreamOriginalGravity` appends a new pin for a later Phase 3 OG leaf; original pin remains historical; Phase 3 corrections do not auto-update Phase 4; allowed unless `CLOSED`/`ABORTED`; same owner/brew; completion-affecting if SG changes; never rewrites Phase 3. | measurement correction chain, completion invalidation | KNOWN-only single pin | append-only reconcile API | `reconcile_upstream_original_gravity`, `POST /{id}/og-consumption` |
| P4-AC-010 | §45 | PRECONDITION: Phase 3 OG corrected after pin. ACTION: read session; then reconcile. EXPECTED: original pin unchanged until reconcile; new pin current; Phase 3 row unchanged. | FR-003,005,012 | — | objective AC test | `test_ac010_reconcile_after_phase3_og_correction` |
| P4-ADV-021 | §46 | PRECONDITION: waived OG brew, first ferment gravity later. ACTION: start then read OG. EXPECTED: OG UNKNOWN, ferment gravity not OG. | FR-003,004 | — | adversarial test | `test_start_with_unknown_og_fr004_adv021` |

## Prior partial-gap analysis

Post–Slice-6 delta classified `ENTRY_OG_RECONCILE` as OPEN (FR-004/005, AC-010, ADV-021). Prior slices pinned KNOWN OG only (unique one-row-per-session). Slice 7 closes that gap without inventing a second OG authority.

## Unknown-OG representation

- Explicit enum-like string `og_availability ∈ {KNOWN, UNKNOWN}` on `fermentation_og_consumptions`.
- UNKNOWN rows store null `brew_measurement_id`, `consumed_value`, `consumed_unit`, `og_observed_at`.
- No numeric sentinel; zero/`1.000` never means unknown.
- `is_current` + `pin_ordinal` distinguish historical vs current pins after reconciliation.
- `FABRICATED_OG_DEFAULT=NO`.

## Entry behavior (P4-FR-004)

- `consume_original_gravity(..., required=False)` returns `None` when no brew OG leaf exists.
- `pin_og_at_start` writes UNKNOWN or KNOWN pin in the start transaction.
- Start journal `FERMENTATION_SESSION_STARTED.event_data.og_availability` records the pin class.
- Derived gravity / pitch-rate adapters require `og_availability == "KNOWN"`; UNKNOWN → not computed / undefined.

## Reconciliation (P4-FR-005)

- `POST /api/v1/fermentation-sessions/{id}/og-consumption` with closed body (`extra=forbid`).
- Resolves cited measurement to current brew-side OG leaf; cross-session/forged IDs → `404`.
- Marks prior pin `is_current=false`, appends new KNOWN pin with incremented `pin_ordinal`.
- SG change → `invalidate_after_fermentation_affecting_evidence` + `recompute_derived_gravity`.
- Journal/audit: `ORIGINAL_GRAVITY_RECONCILED` with prior/new IDs and values.
- Phase 3 measurement rows are never mutated by reconcile.

## Measurement / correction interaction

- Phase 3 correction after pin leaves Phase 4 pin unchanged until explicit reconcile (AC-010).
- Reconcile pins the correction leaf; `brew_correction_id` set when leaf is a correction row.
- `OG_CORRECTION_INTEGRATION=PASS` via Slice 2 correction-chain semantics.

## Derived-state behavior

| State | Behavior |
|---|---|
| UNKNOWN OG | attenuation / ABV / pitch-rate OG inputs unavailable (`NOT_COMPUTED` / undefined) |
| After reconcile | deterministic server recompute from current pin |

`DETERMINISTIC_CALCULATION_AUTHORITY=PASS` (server adapters only; no React/LLM authority).

## Idempotency

- Same `operation_id` + payload → replay prior pin (`store_success` / `replay_or_conflict`).
- Same key + conflicting payload → `409 IDEMPOTENCY_KEY_REUSED`.
- Same leaf already current → no-op success without duplicate pin.

## Concurrency

- PostgreSQL: two concurrent reconciles → one winner / one `STALE_REVISION` (or conflict); exactly one `is_current` pin (`test_concurrent_reconcile_one_winner`).
- Partial unique index `uq_fermentation_og_consumption_current` where `is_current = true`.

## PostgreSQL integrity

- Nullable measurement/value for UNKNOWN.
- Dropped one-row-per-session unique; replaced with partial unique current index.
- FK to `measurements.id` for known pins; cross-session association rejected in application layer.

## Migration

- Forward only: `0009_phase4_og_unknown_reconcile` revises `0008_phase4_yeast_provenance`.
- Phase 1–3 and Phase 4 `0004`–`0008` unmodified.
- Round-trip on disposable DB + shared DB upgraded to `0009` head: PASS.

## API / security

| Case | Result |
|---|---|
| Forged measurement ID | `404` |
| Cross-brew measurement | `404` |
| Unknown fields / mass assignment | `422` (`extra=forbid`) |
| Stale revision | `409 STALE_REVISION` |
| CLOSED/ABORTED reconcile | `409 INVALID_TRANSITION` |

## Journal / recovery

- Start: `og_availability` in start journal event_data.
- Reconcile: `ORIGINAL_GRAVITY_RECONCILED` + audit row.
- Fresh GET after reconcile reconstructs current pin from PostgreSQL/SQLite (`test_recovery_after_reconcile_reread`).

## AC-010 evidence

| Step | Result |
|---|---|
| Pin at start to original leaf `1.052` | PASS |
| Phase 3 correction to `1.055` | Phase 3 leaf corrected; Phase 4 pin still original |
| Reconcile | new pin current (`pin_ordinal=2`); original historical; Phase 3 original value unchanged |
| Idempotent replay | same pin id |

## ADV-021 evidence

| Field | Value |
|---|---|
| ADV_ID | P4-ADV-021 |
| SETUP | Completed brew with pitch, no OG leaf; start fermentation |
| FAULT/ATTACK | Record `FERMENTATION_GRAVITY` after start; reread OG |
| EXPECTED_RESULT | `og_availability=UNKNOWN`; ferment gravity not treated as OG |
| ACTUAL_RESULT | PASS |
| TEST_ID | `test_start_with_unknown_og_fr004_adv021` |

## Regressions

| Suite | Result |
|---|---|
| PHASE_1A (`test_auth_and_recipe_api`) | PASS |
| PHASE_2 (`test_phase2_core`) | PASS |
| PHASE_3 (`test_phase3_api`) | PASS |
| PHASE_4_SLICE_2 (measurements api/matrix) | PASS |
| PHASE_4_SLICE_3 (lifecycle) | PASS |
| PHASE_4_SLICE_4 (timers/reminders) | PASS |
| PHASE_4_SLICE_5 (conditioning) | PASS |
| PHASE_4_SLICE_6 (yeast) | PASS |
| Slice 7 SQLite (`test_phase4_og_reconcile` + entry) | PASS |
| Slice 7 PostgreSQL (incl. concurrency + migration) | PASS (13 passed) |
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS (`0003`→…→`0009`) |

## Phase 5 / frontend / AI boundary

| Gate | Result |
|---|---|
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| PLAYWRIGHT_ACCEPTANCE | NOT_REQUIRED |
| SLICE_7_AI_AUTHORITY_VIOLATION | NO |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |

## Traceability

| ID | Implementation | Test | Evidence |
|---|---|---|---|
| P4-FR-004 | `pin_og_at_start` UNKNOWN path; start command | `test_start_with_unknown_og_fr004_adv021` | this artifact |
| P4-FR-005 | `reconcile_upstream_original_gravity` + route | `test_ac010_*`, `test_reconcile_unknown_then_later_og` | this artifact |
| P4-AC-010 | append-only pin + Phase 3 immutability | `test_ac010_reconcile_after_phase3_og_correction` | this artifact |
| P4-ADV-021 | UNKNOWN pin + gravity isolation | `test_start_with_unknown_og_fr004_adv021` | this artifact |

`SLICE_7_FR_IMPLEMENTED=2/2`  
`SLICE_7_AC_VERIFIED=1/1`  
`SLICE_7_ADV_VERIFIED=1/1`  
`TRACEABILITY=PASS`
