# Phase 4 Implementation Candidate 2

## 1. Candidate 2 identity and provenance

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| INPUT_COMMIT | `25b578c39967cf5fc3415dfbc64f76c3866241e0` |
| Candidate artifact | `docs/evidence/PHASE_4_IMPLEMENTATION_CANDIDATE_2.md` |
| Candidate 2 commit | *(assigned on commit of this artifact)* |
| CANDIDATE_2_TAG | **NOT_CREATED** |
| Failed Candidate 1 | `dea5e369af411f78d1230c2b4063ae2f77b9aba8` **RETIRED** |
| Independent review (C1 FAIL) | `315e3dbc755575c5e37f3fa2fe6fbec76a93dd3d` |
| Finding | CODEX-001 P2_MAJOR — closed schema / `422 UNKNOWN_FIELD` |
| Remediation | `385abaf202f04561519724ccf42687606e23750a` |
| Remediation reconciliation | `25b578c39967cf5fc3415dfbc64f76c3866241e0` |
| Assembly type | Replacement freeze for independent Codex re-review — **no** new product behavior |

`FAILED_CANDIDATE_1_REWRITTEN=NO` — historical Candidate 1 artifact left immutable.

## 2. Specification identity

| Field | Value |
|---|---|
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | **YES** |
| SPECIFICATION_CHANGED | **NO** |

## 3. CODEX-001 status (in Candidate 2 lineage)

| Gate | Value |
|---|---|
| CODEX_001 | **REMEDIATED** |
| P4_FR_077 | **PASS** / IMPLEMENTED |
| P4_AC_067 | **PASS** / VERIFIED (exact `422 UNKNOWN_FIELD`) |
| P4_AC_067_PROOF_VALID | **YES** |
| Command schemas | **22/22** closed JSON; `extra=forbid` via `Phase4ClosedCommand` |
| Handler | Phase-4 `RequestValidationError` → `UNKNOWN_FIELD` |
| Structural guard | `test_phase4_closed_command_schemas.py` |
| Permissive 200-or-422 AC-067 | **REMOVED** |

## 4. Feature-completion declaration

| Gate | Value |
|---|---|
| PHASE_4_FEATURE_IMPLEMENTATION_COMPLETE | **YES** |
| FEATURE_IMPLEMENTATION_REQUIRED_TOTAL | **0** |
| FEATURE_IMPLEMENTATION_REQUIRED_FR/AC/ADV | **0 / 0 / 0** |
| REMAINING_IMPLEMENTATION_CLUSTER_COUNT | **0** |
| REMAINING_BACKEND / FRONTEND / CROSS_CUTTING | **0 / 0 / 0** |

## 5. Requirement totals (corrected vs Candidate 1)

| Class | Candidate 1 (retired) | Candidate 2 |
|---|---|---|
| FR IMPLEMENTED | 78/89 | **79/89** |
| FR FINAL_ACCEPTANCE_ONLY | 11 | **10** |
| FR PARTIAL / NOT_IMPLEMENTED | 0 / 0 | **0 / 0** |
| AC VERIFIED | 63/68 | **63/68** |
| AC FINAL_ACCEPTANCE_ONLY | 5 | **5** |
| ADV VERIFIED | 38/42 | **38/42** |
| ADV FINAL_ACCEPTANCE_ONLY | 4 | **4** |

Arithmetic: 79+10=89; 63+5=68; 38+4=42.

Legitimate deltas from Candidate 1:
- `P4-FR-077`: FINAL_ACCEPTANCE_ONLY → **IMPLEMENTED**
- `P4-AC-067`: VERIFIED_WITH_INVALID_PROOF → **VERIFIED_WITH_VALID_PROOF**

`P4_FR_077_IN_FINAL_ACCEPTANCE_BUCKET=NO`
`TRACEABILITY_UNRELATED_CLASSIFICATION_DRIFT=NO`

## 6. Final-acceptance-only ledger

`FINAL_ACCEPTANCE_BUCKET_CONTAINS_MISSING_FEATURE_CODE=NO`

### FR (10)

`P4-FR-071,P4-FR-072,P4-FR-075,P4-FR-076,P4-FR-080,P4-FR-081,P4-FR-084,P4-FR-085,P4-FR-086,P4-FR-087`

| ID | WHY FAO | MISSING_FEATURE_CODE |
|---|---|---|
| P4-FR-071/072 | consolidated idempotency fingerprint campaign | NO |
| P4-FR-075 | §33 nested IDOR matrix evidence | NO |
| P4-FR-076 | CSRF campaign | NO |
| P4-FR-080/081 | backup/restore + performance harness campaigns | NO |
| P4-FR-084/085 | predecessor preserve campaigns | NO |
| P4-FR-086 | Phase 5+ leakage scan campaign | NO |
| P4-FR-087 | final migration campaign | NO |

### AC (5)

`P4-AC-038,P4-AC-039,P4-AC-040,P4-AC-041,P4-AC-044`

### ADV (4)

`P4-ADV-003,P4-ADV-014,P4-ADV-016,P4-ADV-030`

## 7. Command-schema validation manifest

File: `apps/api/brewing_api/presentation/routes/fermentation_sessions.py`
Base: `apps/api/brewing_api/presentation/phase4_schemas.py` (`Phase4ClosedCommand`, `extra=forbid`)

| SCHEMA_NAME | FILE | ENDPOINT_OR_OPERATION | EXTRA_POLICY | TEST_REFERENCE |
|---|---|---|---|---|
| `StartFermentationCommand` | `fermentation_sessions.py` | POST /brew-sessions/{id}/start | **FORBID** | test_phase4_closed_command_schemas / entry |
| `RecordMeasurementCommand` | `fermentation_sessions.py` | POST /{id}/measurements | **FORBID** | test_phase4_closed_command_schemas / measurements |
| `CorrectMeasurementCommand` | `fermentation_sessions.py` | POST /{id}/measurements/{mid}/corrections | **FORBID** | test_phase4_closed_command_schemas |
| `RevisionCommand` | `fermentation_sessions.py` | POST pause|resume|close|start-conditioning|skip|timer|reminder | **FORBID** | test_phase4_closed_command_schemas + AC-067 |
| `AbortCommand` | `fermentation_sessions.py` | POST /{id}/commands/abort | **FORBID** | test_phase4_closed_command_schemas |
| `CompleteFermentationRequest` | `fermentation_sessions.py` | POST /{id}/commands/complete-fermentation | **FORBID** | test_phase4_closed_command_schemas |
| `CompleteConditioningRequest` | `fermentation_sessions.py` | POST /{id}/commands/complete-conditioning | **FORBID** | test_phase4_closed_command_schemas |
| `RecordWaiverRequest` | `fermentation_sessions.py` | POST /{id}/waivers | **FORBID** | test_phase4_closed_command_schemas |
| `AssessPackagingReadinessRequest` | `fermentation_sessions.py` | POST assess-packaging-readiness | **FORBID** | test_phase4_closed_command_schemas |
| `RecordPackagingHandoffRequest` | `fermentation_sessions.py` | POST record-packaging-readiness-handoff | **FORBID** | test_phase4_closed_command_schemas |
| `StartAuxiliaryTimerCommand` | `fermentation_sessions.py` | POST /{id}/timers | **FORBID** | test_phase4_closed_command_schemas |
| `CancelTimerCommand` | `fermentation_sessions.py` | POST /timers/{id}/cancel | **FORBID** | test_phase4_closed_command_schemas |
| `ExtendTimerCommand` | `fermentation_sessions.py` | POST /timers/{id}/extend | **FORBID** | test_phase4_closed_command_schemas |
| `OperationOnlyCommand` | `fermentation_sessions.py` | POST /timers/{id}/acknowledge | **FORBID** | test_phase4_closed_command_schemas |
| `CreateNoteCommand` | `fermentation_sessions.py` | POST /{id}/notes | **FORBID** | test_phase4_closed_command_schemas |
| `RemoveAttachmentCommand` | `fermentation_sessions.py` | POST /{id}/attachments/{aid}/remove | **FORBID** | test_phase4_closed_command_schemas |
| `EnrichYeastReferenceCommand` | `fermentation_sessions.py` | POST /{id}/yeast-reference | **FORBID** | test_phase4_closed_command_schemas |
| `ReconcileOgCommandBody` | `fermentation_sessions.py` | POST /{id}/og-consumption | **FORBID** | test_phase4_og_reconcile + closed schemas |
| `RecordActionRequest` | `fermentation_sessions.py` | POST /{id}/actions | **FORBID** | test_phase4_closed_command_schemas |
| `ExecutePlannedAdditionRequest` | `fermentation_sessions.py` | POST /{id}/additions/{rid}/execute | **FORBID** | test_phase4_closed_command_schemas |
| `RecordUnplannedAdditionRequest` | `fermentation_sessions.py` | POST /{id}/additions/unplanned | **FORBID** | test_phase4_closed_command_schemas |
| `CorrectAdditionRequest` | `fermentation_sessions.py` | POST /{id}/addition-events/{eid}/corrections | **FORBID** | test_phase4_closed_command_schemas |

`COMMAND_SCHEMA_VALIDATION_MANIFEST=PASS`
`COMMAND_SCHEMA_VALIDATION_COUNT=22/22`
`PHASE_4_CLOSED_COMMAND_SCHEMAS_CONFORMING=22/22`

## 8. Migration manifest

| REVISION | DOWN_REVISION | FILE | CHECKSUM_SHA256 |
|---|---|---|---|
| `0001_phase1a` | None | `database/migrations/versions/0001_phase1a.py` | `3bcffcdf9f3d668dc491eaf07e3291de2f0c7c425941a0856dceccb378985ae8` |
| `0002_phase2_brewing_core` | "0001_phase1a" | `database/migrations/versions/0002_phase2_brewing_core.py` | `57a189fac554fe42aca9eae3772ae5d239cc32ece6be8cf29a8a99c74af0e826` |
| `0003_phase3_brew_day_os` | "0002_phase2_brewing_core" | `database/migrations/versions/0003_phase3_brew_day_os.py` | `8f2ec77cd68f9eab097919232df9e320b50dbeb987e47c7d6027958389dc97ff` |
| `0004_phase4_fermentation_conditioning_yeast` | "0003_phase3_brew_day_os" | `database/migrations/versions/0004_phase4_fermentation_conditioning_yeast.py` | `98f08af926ae37c4789a8f5472441bf265c1deb34a247208abcbfe7e26403cb7` |
| `0005_phase4_measurements_derived_gravity` | "0004_phase4_fermentation_conditioning_yeast" | `database/migrations/versions/0005_phase4_measurements_derived_gravity.py` | `9d82eb9670bfc2b2e252e14493006fa38d24d2b0f46bc0f2c9af6672c1ea6233` |
| `0006_phase4_lifecycle_completion` | "0005_phase4_measurements_derived_gravity" | `database/migrations/versions/0006_phase4_lifecycle_completion.py` | `b6e70e8bb1b4e96c6e5503d51bdcd5d63d914d869181711f90a54e8fb8606abb` |
| `0007_phase4_timers_reminders` | "0006_phase4_lifecycle_completion" | `database/migrations/versions/0007_phase4_timers_reminders.py` | `d07e1635885574d5915adea0a27dd306ae18a2c0e17827a47f97ed358d6d0f1e` |
| `0008_phase4_yeast_provenance` | "0007_phase4_timers_reminders" | `database/migrations/versions/0008_phase4_yeast_provenance.py` | `acdc5ef6cc47d1764436067e109ce54d14262874cda4755afec67db6be554107` |
| `0009_phase4_og_unknown_reconcile` | "0008_phase4_yeast_provenance" | `database/migrations/versions/0009_phase4_og_unknown_reconcile.py` | `bad6423bb28281fd04899b7a5578f0db25a0f5464b79adc2ccc91c52b710f09e` |
| `0010_phase4_calc_read_model_abv` | "0009_phase4_og_unknown_reconcile" | `database/migrations/versions/0010_phase4_calc_read_model_abv.py` | `1593016b790011f9da1c9dfbd66ec1cfb36a8eb4e6890bdc4ee2990d056b0c52` |
| `0011_phase4_plan_equipment` | "0010_phase4_calc_read_model_abv" | `database/migrations/versions/0011_phase4_plan_equipment.py` | `a82ec637cb1ef2a1445b67522d1c7e2500db9fd20e8e3a25d982e5c1245e5466` |
| `0012_phase4_deviations` | "0011_phase4_plan_equipment" | `database/migrations/versions/0012_phase4_deviations.py` | `1db980c66c3c3738aeae2e63bf48d44c0e6e3ff7c41099a39dd7dde4b81f64c0` |
| `0013_phase4_waivers` | "0012_phase4_deviations" | `database/migrations/versions/0013_phase4_waivers.py` | `c7784a5f5454ac0bd21f58d19abffc11b87829881ece6e6c9c18f1282636ae3d` |
| `0014_phase4_actions_additions` | "0013_phase4_waivers" | `database/migrations/versions/0014_phase4_actions_additions.py` | `7e9711da7c63ad626f4a0297063d24f2b37544b14c5eb1a879057134d85c654c` |
| `0015_phase4_journal_media_export` | "0014_phase4_actions_additions" | `database/migrations/versions/0015_phase4_journal_media_export.py` | `c8109f7959b86128c300c0506e608ebe91fc75e4e4d13df5da3d27c5bb4793db` |

| Gate | Value |
|---|---|
| MIGRATION_CHANGE_REQUIRED | NO (CODEX-001 was API-only) |
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS |
| PHASE_4_MIGRATION_CHAIN | PASS (`0004`→`0015`) |
| MIGRATION_MANIFEST | **PASS** |

## 9. PostgreSQL / API / domain / security manifests

Authority unchanged from Candidate 1 except request-boundary UNKNOWN_FIELD enforcement:

| Manifest | Status |
|---|---|
| PostgreSQL integrity (FK/OCC/ownership/journal/media/yeast/additions) | PASS (assemblage) |
| API surface `/fermentation-sessions` | PASS (assemblage; closed schemas enforced) |
| Domain authority (AI_AUTHORITY_ALLOWED=NO for all Phase 4 facts) | PASS |
| Security / ownership | PASS assemblage; FINAL security campaign PENDING |
| Idempotency / concurrency | PASS assemblage; FINAL campaigns PENDING |
| Recovery | PASS assemblage; FINAL PENDING |
| Backup/restore | FEATURE complete; FINAL_ACCEPTANCE PENDING |
| Frontend / a11y / Playwright | Feature complete; FINAL a11y/Playwright PENDING |
| Performance | Feature complete; FINAL PENDING |
| AI boundary | Feature remaining NO; FINAL PENDING |
| Phase 4/5 boundary | PASS; leakage NO |

## 10. Regression manifest

| Gate | Value | Evidence |
|---|---|---|
| PHASE_1A / 2 / 3 / 4 | PASS | `.pytest-p4-codex001-reg.txt` (exit 0 post-remediation) |
| SLICE_11_SERIALIZATION | PASS | Phase 4 suite includes `test_slice11_serialization_regression_*` |
| CODEX-001 focused | PASS | closed-schema + AC-067 tests |

`REGRESSION_MANIFEST=PASS`

## 11. Pending final acceptance gates

| Gate | Pending |
|---|---|
| FINAL_SECURITY_ACCEPTANCE_PENDING | YES |
| FINAL_IDEMPOTENCY_ACCEPTANCE_PENDING | YES |
| FINAL_CONCURRENCY_ACCEPTANCE_PENDING | YES |
| FINAL_RECOVERY_ACCEPTANCE_PENDING | YES |
| FINAL_BACKUP_RESTORE_ACCEPTANCE_PENDING | YES |
| FINAL_PERFORMANCE_ACCEPTANCE_PENDING | YES |
| FINAL_ACCESSIBILITY_ACCEPTANCE_PENDING | YES |
| FINAL_PLAYWRIGHT_ACCEPTANCE_PENDING | YES |
| FINAL_AI_BOUNDARY_ACCEPTANCE_PENDING | YES |

## 12. Traceability matrix (199 rows)

### 12.1 Functional requirements (89)

| ID | TYPE | SPEC_SECTION | FINAL_STATUS | OWNING_SLICE_OR_GATE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LOCATION | FINAL_ACCEPTANCE_REQUIRED |
|---|---|---|---|---|---|---|---|---|
| P4-FR-001 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-002 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-003 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-004 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-005 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-006 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-007 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-008 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-009 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-010 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-011 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-012 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-013 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-014 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-015 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-016 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-017 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-018 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-019 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-020 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-021 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-022 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-023 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-024 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-025 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-026 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-027 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-028 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-029 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-030 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-031 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-032 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-033 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-034 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-035 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-036 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-037 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-038 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-039 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-040 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-041 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-042 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-043 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-044 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-045 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-046 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-047 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-048 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-049 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-050 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-051 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-052 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-053 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-054 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-055 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-056 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-057 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-058 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-059 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-060 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-061 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-062 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-063 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-064 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-065 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-066 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-067 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-068 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-069 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-070 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-071 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-072 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-073 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-074 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-075 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-076 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-077 | FR | §44 | IMPLEMENTED | CODEX_001_REMEDIATION | Phase4ClosedCommand + handler UNKNOWN_FIELD | test_phase4_closed_command_schemas; AC-067 conditioning_security | PHASE_4_CODEX_001_REMEDIATION.md | NO |
| P4-FR-078 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-079 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-080 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-081 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-082 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-083 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-084 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-085 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-086 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-087 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations present; campaign residual | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-FR-088 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |
| P4-FR-089 | FR | §44 | IMPLEMENTED | MULTI_SLICE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | slice evidence + Candidate 2 | NO |

### 12.2 Acceptance criteria (68)

| ID | TYPE | SPEC_SECTION | FINAL_STATUS | OWNING_SLICE_OR_GATE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LOCATION | FINAL_ACCEPTANCE_REQUIRED |
|---|---|---|---|---|---|---|---|---|
| P4-AC-001 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-002 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-003 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-004 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-005 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-006 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-007 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-008 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-009 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-010 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-011 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-012 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-013 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-014 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-015 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-016 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-017 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-018 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-019 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-020 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-021 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-022 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-023 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-024 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-025 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-026 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-027 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-028 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-029 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-030 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-031 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-032 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-033 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-034 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-035 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-036 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-037 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-038 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-AC-039 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-AC-040 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-AC-041 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-AC-042 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-043 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-044 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-AC-045 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-046 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-047 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-048 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-049 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-050 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-051 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-052 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-053 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-054 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-055 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-056 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-057 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-058 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-059 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-060 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-061 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-062 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-063 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-064 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-065 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-066 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |
| P4-AC-067 | AC | §45 | VERIFIED | CODEX_001_REMEDIATION | governing FR | test_mass_assignment_and_forged_fields_rejected (exact 422 UNKNOWN_FIELD) | PHASE_4_CODEX_001_REMEDIATION.md | NO |
| P4-AC-068 | AC | §45 | VERIFIED | MULTI_SLICE | governing FR | phase4 AC tests | slice evidence + Candidate 2 | NO |

### 12.3 Adversarial requirements (42)

| ID | TYPE | SPEC_SECTION | FINAL_STATUS | OWNING_SLICE_OR_GATE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LOCATION | FINAL_ACCEPTANCE_REQUIRED |
|---|---|---|---|---|---|---|---|---|
| P4-ADV-001 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-002 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-003 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-ADV-004 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-005 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-006 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-007 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-008 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-009 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-010 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-011 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-012 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-013 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-014 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-ADV-015 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-016 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-ADV-017 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-018 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-019 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-020 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-021 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-022 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-023 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-024 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-025 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-026 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-027 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-028 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-029 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-030 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE | YES |
| P4-ADV-031 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-032 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-033 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-034 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-035 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-036 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-037 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-038 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-039 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-040 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-041 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |
| P4-ADV-042 | ADV | §46 | VERIFIED | MULTI_SLICE | governing FR | phase4 ADV tests | slice evidence + Candidate 2 | NO |

`TRACEABILITY_MATRIX_ROWS=199`
`TRACEABILITY_MATRIX=PASS`

## 13. Candidate 2 self-check

| Falsification attempt | Result |
|---|---|
| Stale FR totals 78/11 | ABSENT — Candidate 2 uses 79/10 |
| FR-077 still FAO | ABSENT — IMPLEMENTED |
| Permissive AC-067 200-or-422 | ABSENT — exact 422 UNKNOWN_FIELD |
| Missing UNKNOWN_FIELD string | PRESENT in main.py handler |
| Closed schema without forbid | NONE — 22/22 via Phase4ClosedCommand |
| Candidate 1 presented as current | NO — C1 RETIRED; this is Candidate 2 |
| Migration drift from CODEX-001 | NO |
| Unrelated classification drift | NO (2 legitimate deltas only) |
| Traceability rows | 89+68+42=199 |
| Phase 5 leakage | NO |

`CANDIDATE_2_SELF_CHECK=PASS`

## 14. Independent reviewer mandate

Independently verify Candidate 2 (do not trust this freeze). Confirm CODEX-001 closure, 79/10 FR accounting, valid AC-067 proof, 199-row ledger, migrations, Phase 4/5 boundary, and that Candidate 1 remains retired. Outcomes: PASS | FAIL | BLOCKED. No implementation changes unless separately authorized.

## 15. Freeze stop

Candidate 2 is frozen at the commit that adds this artifact. Substantive later change requires Candidate 3. Formal acceptance and Codex re-review are not performed by this assembly gate.

