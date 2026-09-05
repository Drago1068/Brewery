# Phase 4 Slice 10 Evidence — Deviations

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `3f9eb74ef43eeebc00df01f3e94962dd595a1ee3` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_9_DELTA_REVIEW.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `DEVIATIONS` |
| Ancestry from `v0.4.0-phase4-spec` | PASS |

## Exact normative extraction

| Field | Value |
|---|---|
| ID | `P4-FR-058` |
| SPEC_SECTION | §22 Deviations; §16 excursion rule; §23 correction row for Deviation; §26 journal vocabulary |
| NORMATIVE_RULE | Record **derived** deviations with §22 UUIDv5 identity and unique CURRENT leaf per `(session_id, class, source_evidence_id)`; recalculation appends successor and marks prior `SUPERSEDED`; historical rows remain. Classes: `TEMPERATURE_EXCURSION`, `MISSED_REMINDER_DEADLINE`, `GRAVITY_TRAJECTORY`, `STABLE_GRAVITY_BROKEN`. Temperature excursion when target exists and `\|measured - target\| > tolerance` at `observed_at` (§16 / §10.2). Correcting the causing temperature appends superseding comparison. |
| DEPENDENCIES | Fermentation session, plan snapshot, measurements/corrections, derived gravity, journal, actor, OCC/revision |
| CURRENT_IMPLEMENTATION (pre-slice) | Phase 2 brew-day `deviations` table only; no Phase 4 `FermentationDeviation` |
| CURRENT_STATUS | OPEN → CLOSED by this slice |
| MISSING_BEHAVIOR | §22 identity/supersession aggregate; temperature excursion derivation; stable-gravity-broken derivation; session read exposure; journal events |
| EXPECTED_DOMAIN_SURFACE | `FermentationDeviation` append-only with derived identity + supersession |
| EXPECTED_PERSISTENCE_SURFACE | `fermentation_deviations` + unique CURRENT partial index |
| EXPECTED_API_SURFACE | No dedicated CRUD; deviations appear on session GET via measurement write side-effects |
| EXPECTED_JOURNAL_SURFACE | `FERMENTATION_DEVIATION_RECORDED` / `FERMENTATION_DEVIATION_SUPERSEDED` |
| EXPECTED_TEST_SURFACE | `tests/test_phase4_deviations.py` (+ migration head) |

### What P4-FR-058 governs

- Authoritative **derived deviation records** (not unstructured journal text alone).
- **Identity + supersession** provenance for recalculation.
- **Planned vs actual** comparison for temperature (plan snapshot target at `observed_at` vs measured).
- Journal linkage for record/supersede.
- Does **not** invent user-recorded deviation CRUD, QMS workflows, packaging deviations, or brewing corrective instructions.
- Classes `MISSED_REMINDER_DEADLINE` / `GRAVITY_TRAJECTORY` are enumerated and persistable; no additional FR/AC in this slice defines their generators—only identity/supersession machinery + explicitly triggered classes (`TEMPERATURE_EXCURSION`, `STABLE_GRAVITY_BROKEN`) are closed here.

## Prior gap analysis

Post–Slice-9 delta: `DEVIATIONS` OPEN, FR `058` only, AC/ADV none. Measurement foundation and plan equipment already available for planned/actual comparison.

## Deviation domain model

| Attribute | Contract |
|---|---|
| Aggregate | `FermentationDeviation` (distinct from Phase 2 brew-day `Deviation`) |
| Classes / origins / statuses | Spec closed sets in `constants.py` |
| Derived identity | UUIDv5 `d81f0c2e-4a77-5b1d-9e08-3c55a91b7f10` / `phase4-deviation-v1:{session}:{class}:{source_evidence_id}:{plan_hash}` |
| CURRENT uniqueness | Partial unique index on `(fermentation_session_id, deviation_class, source_evidence_id)` where `status='CURRENT'` |
| Comparison facts | `exceeded`, measured/target/tolerance/variance, unit, `comparison_payload` |
| Chronology | `occurred_at` (event) vs `recorded_at` (server) |
| Provenance | `actor_user_id`, `operation_id`, `plan_hash`, `source_evidence_id`, `supersedes_id` |

`DEVIATION_DOMAIN_MODEL=PASS`  
`EXISTING_PHASE_4_AUTHORITY_REUSED=YES`

## Planned vs actual linkage

Temperature excursions resolve target from immutable `FermentationPlanSnapshot` (schedule piecewise-constant or single `fermentation_temperature_c` when `SPECIFIED`) plus `plan_hash` on the deviation row. No string matching.

`PLANNED_ACTUAL_DEVIATION_LINKAGE=PASS`

## Provenance / revision

Append-only: prior CURRENT → `SUPERSEDED`; successor carries same `derived_identity` and `supersedes_id`. Unchanged comparison is a no-op. §23 resolution-note field exists; no separate resolution write command invented (FR-058 is derived record/supersession).

`DEVIATION_PROVENANCE=PASS`  
`DEVIATION_REVISION_CONTRACT=PASS`

## Lifecycle / late entry

Deviation derivation is a side-effect of accepted measurement record/correct paths. It does not transition lifecycle. Late recording reuses measurement `BOUNDED_LATE_ENTRY` / stage windows; deviations inherit occurrence vs recording chronology.

`DEVIATION_LIFECYCLE_INTEGRATION=PASS`  
`DEVIATION_LATE_ENTRY_CONTRACT=PASS`

## Idempotency / concurrency

| Gate | Result |
|---|---|
| Same measurement operation_id replay | Single CURRENT leaf (`test_fr058_measurement_idempotency_no_duplicate_deviation`) |
| Concurrent temperature posts (PG) | One `201`, one `409`; single CURRENT excursion leaf |
| Unique CURRENT index | PostgreSQL/SQLite partial unique |

`IDEMPOTENCY_CONTRACT=PASS`  
`CONCURRENCY_CONTRACT=PASS`

## PostgreSQL / migration

| Item | Result |
|---|---|
| Migration | `0012_phase4_deviations` (revises `0011` only) |
| Phase 1–3 migrations | Unchanged |
| Round-trip | `test_phase4_migration` PASS |
| Table existence | `test_phase4_slice10_tables_exist` |

`POSTGRESQL_ACCEPTANCE=PASS`  
`MIGRATION_ACCEPTANCE=PASS`  
`PHASE_3_MIGRATIONS_UNCHANGED=YES`  
`PHASE_3_MIGRATION_ANCESTRY=PASS`

## API / read model

Session GET exposes ordered `deviations` via `serialize_deviation`. No generic deviation CRUD.

`API_ACCEPTANCE=PASS`  
`DEVIATION_READ_MODEL=PASS`

## Security

Cross-owner session GET → `404`. Deviations only created under owner-authorized measurement writes; forged session IDs follow existing nondisclosure.

`SECURITY_ACCEPTANCE=PASS`

## Journal / audit

| Event | When |
|---|---|
| `FERMENTATION_DEVIATION_RECORDED` | New CURRENT leaf appended |
| `FERMENTATION_DEVIATION_SUPERSEDED` | Prior CURRENT marked superseded |

Retries reuse measurement idempotency → no duplicate journal pairs for identical comparison.

`JOURNAL_ACCEPTANCE=PASS`

## Recovery

Fresh `TestClient` + login re-reads identical `deviations` array from persistence.

`RECOVERY_ACCEPTANCE=PASS`

## Frontend / AI / Phase 5

| Gate | Result |
|---|---|
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| PLAYWRIGHT_ACCEPTANCE | NOT_REQUIRED |
| SLICE_10_AI_AUTHORITY_VIOLATION | NO |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |

## AC / ADV

Assigned none by post–Slice-9 delta.

`SLICE_10_AC_VERIFIED=0/0`  
`SLICE_10_ADV_VERIFIED=0/0`

## Regressions

| Suite | Result |
|---|---|
| Slice 10 deviations (SQLite) | PASS (8 passed, 1 skipped concurrency) |
| Slice 10 deviations + migration (PostgreSQL) | PASS (16 passed incl. concurrency + round-trip) |
| Phase 4 slices 2–9 + pitch/entry + Phase 2 core + Phase 3 API sample | See `.pytest-p4s10-reg.txt` |
| Phase 1A / Phase 3 migrations | Unchanged; ancestry PASS |

## Traceability

| ID | Spec | Implementation | Persistence | API/query | Tests | Evidence |
|---|---|---|---|---|---|---|
| P4-FR-058 | §22 / §16 / §23 / §26 | `application/phase4/deviations.py`; hooks in `measurements.py`; `read_models.py` | `0012_phase4_deviations` / `FermentationDeviation` | Session GET `deviations` | `test_phase4_deviations.py` | this artifact |

`SLICE_10_FR_IMPLEMENTED=1/1`  
`TRACEABILITY=PASS`

## Self-review

Falsified: within-tolerance no-op; unspecified target no excursion; correction supersession; schedule target at offset; measurement idempotency duplicate leaf; concurrent OCC; cross-owner 404; restart reread; Phase 2 brew-day deviation table not reused as Phase 4 authority. No specification contradiction.

`IMPLEMENTATION_SELF_REVIEW=PASS`
