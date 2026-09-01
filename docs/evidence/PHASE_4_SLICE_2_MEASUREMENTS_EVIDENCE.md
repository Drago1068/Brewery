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
| P4-FR-026 | §12.1 | `measurements.py` temperature bounds | deferred full matrix | API_INTEGRATION | PARTIAL |
| P4-FR-027 | §12.1 | `measurements.py` pH bounds | deferred full matrix | API_INTEGRATION | PARTIAL |
| P4-FR-028 | §12.1 | `MEASUREMENT_STAGE_BY_TYPE` | `test_rejects_measurement_on_wrong_stage_type` | API_INTEGRATION | PASS |
| P4-FR-029 | §12.2, §18 | models + `time_validation.py` | API tests | API_INTEGRATION | PASS |
| P4-FR-030 | §18 | `time_validation.py` | API rejection paths | API_INTEGRATION | PASS |
| P4-FR-031 | §23 | `FermentationMeasurementCorrection` + chain | `test_measurement_correction_chain_*` | POSTGRESQL/SQLite | PASS |
| P4-FR-032 | §12.2 | session/stage FK + app checks | security IDOR test | SECURITY | PASS |
| P4-FR-033 | §13 | `try_apparent_attenuation_ratio` | `test_phase4_measurements_domain.py` | DOMAIN_UNIT | PASS |
| P4-FR-034 | §13 | `fermentation_progress` | `test_phase4_measurements_domain.py` | DOMAIN_UNIT | PASS |
| P4-FR-035 | §15 | `stable_gravity_evaluator` | domain goldens §15.6 vectors | DOMAIN_UNIT | PASS |
| P4-FR-036 | §13 | `try_abv_percent` | domain unit | DOMAIN_UNIT | PASS |
| P4-FR-037 | §13 | pitch-rate deferred (not slice-2 API) | — | DOMAIN_UNIT | DEFERRED |
| P4-FR-038 | §13 | `plato_to_sg` / `canonicalize_gravity` | domain + API Plato reject | DOMAIN_UNIT | PASS |
| P4-AC-018 | §15 goldens | `test_phase4_measurements_domain.py` | domain unit | DOMAIN_UNIT | PASS |
| P4-AC-019 | Plato boundary | domain + API | DOMAIN_UNIT/API | PASS |
| P4-AC-020 | §12 matrix | partial gravity/temp/pH | API tests | API_INTEGRATION | PARTIAL |
| P4-AC-021 | §13 | domain attenuation/progress | domain unit | DOMAIN_UNIT | PASS |
| P4-AC-037 | idempotency | `test_measurement_idempotency_*` | API_INTEGRATION | PASS |
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

## Migration

- `0005_phase4_measurements_derived_gravity` — upgrade/downgrade defined; PostgreSQL round-trip evidence pending dedicated PG CI run.
