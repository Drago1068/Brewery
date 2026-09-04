# Phase 4 Slice 6 Evidence — Yeast Provenance & Pitch History

## Identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `be560717c6c0174a9af8a08dcd9c8ad896862365` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `YEAST_PROVENANCE_AND_PITCH_HISTORY` |

## Requirement extraction (normative)

| ID | SPEC_SECTION | NORMATIVE_RULE | DEPENDENCIES | IMPLEMENTATION | TEST |
|---|---|---|---|---|---|
| P4-FR-066 | §11.1/§28 | Optional same-owner yeast `IngredientLot` linkage with an immutable metadata snapshot captured at declaration; live lot edits never rewrite the snapshot. | IngredientLot / Ingredient (Phase 2) | `yeast.py::enrich_yeast_reference`, `_build_lot_snapshot` | `test_phase4_yeast.py::test_lot_linkage_immutable_snapshot` |
| P4-FR-067 | §11.3 | Source-pair agreement (both null or both non-null), same-owner source session (`404`), reference-belongs-to-source (`422 SOURCE_PAIR_MISMATCH`), aborted/finishing source status (`422 SOURCE_SESSION_ABORTED` / `SOURCE_SESSION_NOT_FINISHED`), strict temporal order (`422 SOURCE_TEMPORAL_INVALID`). | FermentationSession status, pitched_at | `yeast.py::_validate_source_pair` | `test_phase4_yeast.py` + `test_phase4_yeast_closure.py::test_foreign_session_source_returns_404` |
| P4-FR-068 | §11.2/§30 | Queryable pitch history by session/lot/owner returning snapshotted (not live) metadata. | fermentation_yeast_pitch_references + lot_snapshot | `yeast.py::pitch_history`, route `GET /pitch-history` | `test_phase4_yeast.py::test_pitch_history_filters_by_session_and_lot` |
| P4-FR-069 | §11.3/§32 R12 | Reject circular lineage under transactional locking; self-reference `422`, graph cycle `409 YEAST_LINEAGE_CYCLE`; ordered `SELECT ... FOR UPDATE`. | source_yeast_reference_id lineage | `yeast.py::_lineage_reaches`, `_lock_references_in_id_order` | `test_phase4_yeast.py::test_self_reference_rejected_422`, `test_phase4_yeast_closure.py::test_lineage_cycle_rejected_under_lock` |

| AC | EXPECTED | RESULT |
|---|---|---|
| P4-AC-034 | mismatched pair / aborted source / cycle race → `422`/`409` per §11 | PASS (`SOURCE_PAIR_MISMATCH`, `SOURCE_SESSION_ABORTED`, `YEAST_LINEAGE_CYCLE`) |
| P4-AC-035 | live lot metadata change → GET history snapshot unchanged | PASS |

| ADV | EXPECTED | RESULT |
|---|---|---|
| P4-ADV-018 | circular and concurrent opposite yeast edges → reject (`422`/`409`) | PASS (self-ref 422, 3-node cycle 409 under ordered locks) |
| P4-ADV-027 | yeast lot of user B cited by user A → `404` | PASS |

## Implementation architecture

- `domain/fermentation/models.py`: extended `FermentationYeastPitchReference` with
  `ingredient_lot_id`, `lot_snapshot` (JSON), `preparation_method_note`, `pitch_inputs` (JSON),
  `field_provenance` (JSON), `source_fermentation_session_id`, `source_yeast_reference_id`,
  `declaration_note`, `revision`, `actor_user_id`, `enriched_at`; added
  `FermentationYeastReferenceHistory` (append-only history with prior/new snapshots).
- `application/phase4/yeast.py`: `enrich_yeast_reference` command (idempotent, OCC,
  source-pair validation, cycle rejection, append-only history, journal/audit) and
  `pitch_history` query + `serialize_yeast_reference`.
- `presentation/routes/fermentation_sessions.py`: `GET /pitch-history`, `POST /{id}/yeast-reference`.
- `database/migrations/versions/0008_phase4_yeast_provenance.py`: additive columns + history table.

## Provenance model

Per-field provenance and snapshotted lot metadata are persisted. `lot_snapshot` captures
`lot_code`, `manufacturer`, `product`, `form`, `strain`, `generation_label`, full `attributes`,
and `unit` at declaration time. Live changes to `Ingredient`/`IngredientLot` do not rewrite the
snapshot (AC-035 verified).

## Pitch-history model

`GET /pitch-history?session_id=&lot_id=` returns owner-scoped serialized references, ordered by
creation, reconstructable from PostgreSQL. History rows are append-only; prior values are
snapshotted in `FermentationYeastReferenceHistory.prior_snapshot`.

## Cross-session traceability

Each reference carries an optional reuse pair (`source_fermentation_session_id`,
`source_yeast_reference_id`) forming an explicit lineage chain; a reviewer can reconstruct which
source fed which session and detect supersession via history rows.

## Correction / revision behavior

`PITCH_HISTORY_CORRECTION_CONTRACT=PASS`. Enrich and correction share one command; each mutation
appends a history row (prior + new snapshot) and increments the reference `revision`. No silent
overwrite.

## PostgreSQL constraints

`ingredient_lot_id` FK (`SET NULL`), `source_fermentation_session_id` FK (`SET NULL`),
`source_yeast_reference_id` self-FK (`SET NULL`), history FKs (`CASCADE`); indexes on all FK
columns. Referential integrity verified via migration round-trip.

## Contracts

| Contract | Result |
|---|---|
| YEAST_PROVENANCE_DOMAIN | PASS |
| PITCH_HISTORY_DOMAIN | PASS |
| PITCH_HISTORY_IMMUTABILITY | PASS |
| PITCH_HISTORY_CORRECTION_CONTRACT | PASS |
| CROSS_SESSION_TRACEABILITY | PASS |
| PROVENANCE_REFERENTIAL_INTEGRITY | PASS |
| IDEMPOTENCY_CONTRACT | PASS (replay + key-reuse conflict) |
| CONCURRENCY_CONTRACT | PASS (one winner under session OCC + ordered reference locks) |
| POSTGRESQL_ACCEPTANCE | PASS |
| MIGRATION_ACCEPTANCE | PASS (0008 round-trip on disposable DB) |
| API_ACCEPTANCE | PASS |
| SECURITY_ACCEPTANCE | PASS (cross-owner lot/session → 404) |
| JOURNAL_ACCEPTANCE | PASS (YEAST_REFERENCE_RECORDED / CORRECTED) |
| RECOVERY_ACCEPTANCE | PASS (fresh client re-read) |
| SLICE_6_AI_AUTHORITY_VIOLATION | NO |
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |

## Test commands

- SQLite: `pytest tests/test_phase4_yeast.py` (11 passed)
- PostgreSQL: `TEST_USE_POSTGRES=1 pytest tests/test_phase4_yeast_closure.py tests/test_phase4_migration.py -m integration` (11 passed, incl. migration round-trip)
- Regressions: `test_phase4_entry.py`, `test_phase4_lifecycle.py` re-run green.

## Traceability

| FR | IMPLEMENTED | VERIFIED |
|---|---|---|
| P4-FR-066 | YES | YES |
| P4-FR-067 | YES | YES |
| P4-FR-068 | YES | YES |
| P4-FR-069 | YES | YES |

`SLICE_6_FR_IMPLEMENTED=4/4`, `SLICE_6_AC_VERIFIED=2/2`, `SLICE_6_ADV_VERIFIED=2/2`.