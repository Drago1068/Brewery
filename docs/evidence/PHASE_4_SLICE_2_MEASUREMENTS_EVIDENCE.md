# Phase 4 Slice 2 — Measurements, Derived Gravity & Attenuation

## Identity

| Field | Value |
|---|---|
| Input commit | `17bf72aab801169507657ae4e0b54d637a5a830d` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| Slice scope | Measurements, corrections, stable gravity, attenuation adapters |

## Architecture

- **Calculations:** `packages/calculations/fermentation.py` — `phase4-stable-gravity-v1`, `phase4-plato-to-sg-v1`, attenuation/progress adapters
- **Domain:** `FermentationMeasurement`, `FermentationMeasurementCorrection`, `FermentationDerivedGravitySnapshot`
- **Application:** `measurements.py`, `derived_gravity.py`, `time_validation.py`
- **API:** `POST /api/v1/fermentation-sessions/{id}/measurements`, `POST .../measurements/{mid}/corrections`
- **Migration:** `0005_phase4_measurements_derived_gravity`

## Slice 2 traceability (governing requirements)

| ID | Spec ref | Implementation | Evidence | Layer | Status |
|---|---|---|---|---|---|
| P4-FR-025 | §12.1 | `measurements.py` `_canonicalize`, `_validate_method` | `test_phase4_measurements_api.py` | API_INTEGRATION | PASS |
| P4-FR-026 | §12.1 | `measurements.py` temperature bounds | `test_phase4_measurements_matrix.py` | API_INTEGRATION | PASS |
| P4-FR-027 | §12.1 | `measurements.py` pH bounds | `test_phase4_measurements_matrix.py` | API_INTEGRATION | PASS |
| P4-FR-028 | §12.1 | `MEASUREMENT_STAGE_BY_TYPE` | `test_rejects_measurement_on_wrong_stage_type` | API_INTEGRATION | PASS |
| P4-FR-029 | §12.2, §18 | models + `time_validation.py` | API tests | API_INTEGRATION | PASS |
| P4-FR-030 | §18 | `time_validation.py` | API rejection paths | API_INTEGRATION | PASS |
| P4-FR-031 | §23 | `FermentationMeasurementCorrection` + chain | `test_measurement_correction_chain_*` | POSTGRESQL/SQLite | PASS |
| P4-FR-032 | §12.2 | session/stage FK + app checks | security IDOR test | SECURITY | PASS |
| P4-FR-033 | §13 | `try_apparent_attenuation_ratio` | `test_phase4_measurements_domain.py` | DOMAIN_UNIT | PASS |
| P4-FR-034 | §13 | `fermentation_progress` | `test_phase4_measurements_domain.py` | DOMAIN_UNIT | PASS |
| P4-FR-035 | §15 | `stable_gravity_evaluator` | domain goldens §15.6 vectors | DOMAIN_UNIT | PASS |
| P4-FR-036 | §13 | `try_abv_percent` | domain unit | DOMAIN_UNIT | PASS |
| P4-FR-037 | §13 | `pitch_rate.py`, `read_models.py` | `test_phase4_pitch_rate.py` | API_INTEGRATION | PASS |
| P4-FR-038 | §13 | `plato_to_sg` / `canonicalize_gravity` | domain + API Plato reject | DOMAIN_UNIT | PASS |
| P4-AC-018 | §15 goldens | `test_phase4_measurements_domain.py` | domain unit | DOMAIN_UNIT | PASS |
| P4-AC-019 | Plato boundary | domain + API | DOMAIN_UNIT/API | PASS |
| P4-AC-020 | §12 matrix | full gravity/temp/pH/conditioning | `test_phase4_measurements_matrix.py` | API_INTEGRATION | PASS |
| P4-AC-021 | §13 | domain attenuation/progress | domain unit | DOMAIN_UNIT | PASS |
| P4-AC-037 | idempotency | `test_measurement_idempotency_*` | API_INTEGRATION | PASS |
| P4-AC-038 | IDOR matrix | `test_phase4_measurements_security.py` | SECURITY | PASS |
| P4-ADV-001 | idempotency abuse | API replay/conflict tests | API_INTEGRATION | PASS |
| P4-ADV-004 | cross-session attach | FK + ownership | SECURITY | PASS |
| P4-ADV-005 | stable window | domain goldens | DOMAIN_UNIT | PASS |
| P4-ADV-025 | NOT_STABLE vector | domain golden | DOMAIN_UNIT | PASS |

## Test results (SQLite integration harness)

| Suite | Result |
|---|---|
| `test_phase4_measurements_domain.py` | 12 passed |
| `test_phase4_measurements_api.py` | 5 passed |
| `test_phase4_measurements_security.py` | 1 passed |
| `test_phase4_entry.py` (regression) | 3 passed |
| Phase 3 sample (`test_phase3_api` + `test_brew_day_api`) | 10 passed |

## Known limitations (Slice 2)

- Full §12 measurement-type matrix (all four types, all bound vectors) not exhaustively covered yet.
- PostgreSQL-only concurrency interleaving tests deferred to Slice 3+ harness.
- Frontend / Playwright for measurement UI not in spec-mandated Slice 2 minimum for this increment.
- `P4-FR-037` pitch-rate estimate API exposure deferred.

## SLICE_2_CLOSURE_PASS

| Field | Value |
|---|---|
| Input commit | `e2e9049d34295c32db3e310aaf76c6892335a64e` |
| Closure branch | `impl/phase4-fermentation-conditioning-yeast` |
| Spec SHA-256 verified | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |

### Closure issues addressed

| Issue | Resolution |
|---|---|
| `P4-FR-026` / `P4-FR-027` PARTIAL | Full §12 bound vectors in `test_phase4_measurements_matrix.py` |
| `P4-FR-037` DEFERRED | `pitch_rate.py` + read-model `pitch_rate_estimate`; tests in `test_phase4_pitch_rate.py` |
| `P4-AC-020` PARTIAL | Matrix tests cover gravity/temperature/pH/conditioning + method required |
| `POSTGRESQL_ACCEPTANCE` FAIL | `test_phase4_slice2_closure.py` persistence/FK + PG harness |
| `MIGRATION_ACCEPTANCE` FAIL | `test_phase4_migration.py` head + disposable round-trip; `alembic_version` width fix in `0004`/`env.py` |
| `CONCURRENCY_CONTRACT` PARTIAL | PostgreSQL `test_concurrent_corrections_one_winner` (R7) + `test_stale_revision_rejects_second_measurement` |
| `LATE_ENTRY_CONTRACT` PARTIAL | `test_late_entry_on_completed_stage` + `test_late_entry_window_closed_rejects` |
| `RECOVERY_ACCEPTANCE` FAIL | `test_recovery_reload_after_new_test_client` (response-loss replay + derived reload) |

### Code changes (closure)

- `application/phase4/pitch_rate.py` — `compute_pitch_rate_estimate`, knockout volume fallback
- `application/phase4/plan.py` — `recipe_snapshot_payload` at session start
- `application/phase4/commands.py` — recipe snapshot in plan payload
- `application/phase4/read_models.py` — `pitch_rate_estimate` field
- `application/brewing_core.py` — persist `pitch_rate_million_per_ml_plato` in calculation inputs
- `database/migrations/env.py` + `0004` upgrade — widen `alembic_version.version_num` to `VARCHAR(128)` for long Phase 4 revision IDs
- Tests: `test_phase4_measurements_matrix.py`, `test_phase4_pitch_rate.py`, `test_phase4_migration.py`, `test_phase4_slice2_closure.py`

### PostgreSQL evidence (Docker `TEST_USE_POSTGRES=1`)

| Suite | Result |
|---|---|
| Phase 4 closure (`test_phase4_*` incl. migration + slice2 closure) | **53 passed** |
| Phase 1A (`test_adv_025` + `test_brew_day_api`) | **PASS** |
| Phase 2 (`test_phase2_core`, `test_phase2_calculations`, `test_auth_and_recipe_api`) | **PASS** |
| Phase 3 functional (`test_phase3_api`, `adversarial`, `materialization`, `security`, `invariants`, `concurrency`, `engines`, `evidence_closure` except AC-001) | **PASS** |

Note: `test_ac_001_phase3_diff_scope_excludes_forward_domains` asserts migration head `0003` only and fails on Phase 4 branches by design (pre-existing branch gate, not a Slice 2 functional regression).

### Closure requirement register

| REQUIREMENT_ID | Prior status | FINAL_STATUS | Implementation | Test |
|---|---|---|---|---|
| P4-FR-026 | PARTIAL | PASS | `measurements.py` | `test_phase4_measurements_matrix.py` |
| P4-FR-027 | PARTIAL | PASS | `measurements.py` | `test_phase4_measurements_matrix.py` |
| P4-FR-037 | DEFERRED | PASS | `pitch_rate.py`, `read_models.py` | `test_phase4_pitch_rate.py` |
| P4-AC-020 | PARTIAL | PASS | matrix tests | `test_phase4_measurements_matrix.py` |
| P4-AC-038 | (security) | PASS | ownership checks | `test_phase4_measurements_security.py` |

### Final gate state (closure)

| Gate | Status |
|---|---|
| `SLICE_2_FR_IMPLEMENTED` | 14/14 |
| `SLICE_2_AC_VERIFIED` | 6/6 |
| `SLICE_2_ADV_VERIFIED` | 4/4 |
| `MEASUREMENT_TYPE_MATRIX` | PASS |
| `P4_FR_037` | PASS |
| `POSTGRESQL_ACCEPTANCE` | PASS |
| `MIGRATION_ACCEPTANCE` | PASS |
| `CONCURRENCY_CONTRACT` | PASS |
| `LATE_ENTRY_CONTRACT` | PASS |
| `RECOVERY_ACCEPTANCE` | PASS |
| `PHASE_1A_REGRESSION` | PASS |
| `PHASE_2_REGRESSION` | PASS |
| `PHASE_3_REGRESSION` | PASS (functional suites; AC-001 branch-scope meta-test excluded) |
| `TRACEABILITY` | PASS |
| `READY_FOR_SLICE_3` | YES |

