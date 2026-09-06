# Phase 4 Slice 8 Evidence — Calculation Read-Model Closure

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `14b006bc6fb14158e04a15e4c88656ce131db85f` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_7_DELTA_REVIEW.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `CALC_READ_MODEL_CLOSURE` |
| Ancestry from `v0.4.0-phase4-spec` | PASS |

## Exact normative extraction

| ID | SPEC_SECTION | NORMATIVE_RULE | DEPENDENCIES | PRIOR GAP | SURFACE |
|---|---|---|---|---|---|
| P4-FR-036 | §13 / §28 | Compute ABV with accepted `(OG-FG)×131.25` when defined via `brewing.abv` / `abv_from_gravity` adapter; FG>OG → `CALCULATION_UNDEFINED`; UNKNOWN inputs → undefined; persist function result when defined. | OG consumption (KNOWN), effective FG leaf, `packages.calculations` | Domain `try_abv_percent` existed; not persisted/exposed on Phase 4 derived read model | `derived_gravity.py`, snapshot `abv_percent`, session GET |
| P4-AC-021 | §45 | PRECONDITION: OG/FG pairs including undefined. ACTION: attenuation/progress/ABV. EXPECTED: ratio, clips, `CALCULATION_UNDEFINED`. EVIDENCE: goldens. RELATED_FR: 033,034,036,037 | FR-033/034/036/037 adapters | Domain goldens partial; ABV missing from API read model | `test_phase4_calc_read_model.py` |

## Prior gap

Post–Slice-7 delta classified `CALC_READ_MODEL_CLOSURE` OPEN: FR-036 PARTIAL because ABV lived only in `packages/calculations` (+ domain unit test) and was not written into `fermentation_derived_gravity_snapshots` or session `derived_gravity` payload.

Additionally, with `SessionLocal(autoflush=False)`, gravity record/correct recomputed derived snapshots **before** flushing the new measurement/correction, so snapshots could be empty (`source_measurement_ids=[]`). Slice 8 flushes before recompute so the read model sees authoritative lineage.

## Read-model architecture

- **Persisted projection:** append-only `FermentationDerivedGravitySnapshot` rows (existing Slice 2 pattern).
- **Recompute trigger:** measurement record/correct (gravity) and OG reconcile.
- **Query surface:** existing `GET /api/v1/fermentation-sessions/{id}` → `derived_gravity.abv_percent`.
- No new mutation API; no React/LLM calculation.

## Deterministic calculation authority

| Adapter | Authority |
|---|---|
| ABV | `calculations.fermentation.try_abv_percent` → `brewing.abv` |
| Attenuation | existing `try_apparent_attenuation_ratio` |
| Progress | domain goldens only (FR-034 already closed; not newly persisted) |

`DETERMINISTIC_CALCULATION_AUTHORITY=PASS`

## Authoritative source mapping

| Input | Source |
|---|---|
| OG | current `FermentationOgConsumption` with `og_availability=KNOWN` |
| FG | `final_gravity_from_leaves` over effective `FERMENTATION_GRAVITY` leaves |
| Provenance | `source_measurement_ids`, `window_measurement_ids`, `calculation_version`, `evaluated_at` |

## Unknown / indeterminate behavior

| Case | Result |
|---|---|
| OG UNKNOWN | `abv_percent=null`, `apparent_attenuation_ratio=null` (no fabricated value) |
| Missing FG leaves | null ABV |
| FG > OG | adapter `CALCULATION_UNDEFINED` → null persisted |
| FG < 1.000 (still ≤ OG) | ABV persisted per accepted `abv` |

`FABRICATED_CALC_RESULT=NO`

## Correction / OG reconcile integration

- Gravity correction → flush → recompute → ABV updates to corrected FG.
- Phase 3 OG correction alone does not change Phase 4 ABV until `ReconcileUpstreamOriginalGravity`.
- After reconcile, ABV uses reconciled OG.

## Provenance / version

Existing snapshot fields retained: `calculation_version` (`phase4-stable-gravity-v1`), `source_measurement_ids`, `evaluated_at`, `schema_version`. No parallel version system invented.

`CALC_PROVENANCE=PASS`

## API / security / journal / recovery

| Gate | Result |
|---|---|
| API | Existing session GET; `API_ACCEPTANCE=NOT_REQUIRED` for new routes; payload extended |
| Forged session | `404` |
| Cross-owner GET | `404` |
| Journal | Pure read creates no events; `JOURNAL_ACCEPTANCE=NOT_REQUIRED` |
| Recovery | Fresh GET reconstructs `abv_percent` from PostgreSQL/SQLite snapshot |

## PostgreSQL / migration

- Forward migration `0010_phase4_calc_read_model_abv` adds nullable `abv_percent`.
- Revises `0009`; Phase 1–3 and Phase 4 `0004`–`0009` unmodified.
- Round-trip + head check: PASS.

## Idempotency / concurrency

- No new mutation command → `IDEMPOTENCY_CONTRACT=NOT_APPLICABLE`.
- Read consistency: derived snapshot written in same transaction as measurement/correction/reconcile after flush; GET returns committed projection.
- `CONCURRENCY_CONTRACT=PASS` (transactional projection; no invented race harness beyond correction/reconcile sequencing).

## P4-AC-021 proof

| Vector | Evidence |
|---|---|
| Attenuation ratio / undefined | domain goldens in `test_ac021_domain_goldens_*` |
| Progress clips / undefined | same |
| ABV defined `(1.050-1.010)×131.25=5.25` | domain + session read model |
| ABV undefined (UNKNOWN OG / FG>OG / missing) | domain + `test_abv_undefined_when_og_unknown` |
| Read-model exposure | `test_ac021_abv_exposed_on_session_read_model` |

## Regressions

| Suite | Result |
|---|---|
| PHASE_1A | PASS |
| PHASE_2 | PASS |
| PHASE_3 | PASS |
| PHASE_4_SLICE_2–7 | PASS |
| Slice 8 SQLite | PASS |
| Slice 8 PostgreSQL + migration | PASS |
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS (`0003`→…→`0010`) |

## Boundaries

| Gate | Result |
|---|---|
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| PLAYWRIGHT_ACCEPTANCE | NOT_REQUIRED |
| SLICE_8_AI_AUTHORITY_VIOLATION | NO |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |
| SLICE_8_ADV_VERIFIED | 0/0 |

## Traceability

| ID | Implementation | Test | Evidence |
|---|---|---|---|
| P4-FR-036 | `try_abv_percent` → snapshot `abv_percent` → read model | `test_ac021_abv_exposed_*`, correction/reconcile/unknown | this artifact |
| P4-AC-021 | domain adapters + session derived payload | `test_ac021_domain_goldens_*` + read-model tests | this artifact |

`SLICE_8_FR_IMPLEMENTED=1/1`  
`SLICE_8_AC_VERIFIED=1/1`  
`SLICE_8_ADV_VERIFIED=0/0`  
`TRACEABILITY=PASS`
