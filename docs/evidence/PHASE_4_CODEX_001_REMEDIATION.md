# Phase 4 CODEX-001 Remediation — Closed Command Schema `UNKNOWN_FIELD`

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Failed candidate | `dea5e369af411f78d1230c2b4063ae2f77b9aba8` |
| Independent review | `315e3dbc755575c5e37f3fa2fe6fbec76a93dd3d` |
| Finding | `CODEX-001` (P2_MAJOR) |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | **YES** |
| SPECIFICATION_CHANGED | **NO** |
| FAILED_CANDIDATE_VERIFIED | **YES** |
| INDEPENDENT_REVIEW_VERIFIED | **YES** |

Historical artifacts left immutable: `PHASE_4_IMPLEMENTATION_CANDIDATE.md`, `PHASE_4_INDEPENDENT_CODEX_REVIEW.md`.

## Exact normative contract

| Field | Value |
|---|---|
| P4_FR_077_SPEC_SECTION | §44 FR-077; matrix §44→AC-020/067; domain §30 / §33 |
| P4_AC_067_SPEC_SECTION | §45 AC-067 |
| CLOSED_COMMAND_SCHEMA_DEFINITION | §30: every closed command schema rejects unknown fields; never ignored; no domain/operation-success rows |
| UNKNOWN_FIELD_HTTP_STATUS | `422` |
| UNKNOWN_FIELD_ERROR_CODE | `UNKNOWN_FIELD` |
| ERROR_ENVELOPE_CONTRACT | Canonical DomainError-shaped payload: `{"detail": <str>, "code": "UNKNOWN_FIELD"}` for extras; other validation failures retain FastAPI detail-list shape (not mislabeled) |

## Command-schema inventory

JSON mutation bodies under `/api/v1/fermentation-sessions` (multipart media upload is Form-based, not a closed JSON command schema):

| SCHEMA_NAME | CLOSED | PRIOR_EXTRA | REMEDIATION_REQUIRED |
|---|---|---|---|
| StartFermentationCommand | YES | ignore | YES |
| RecordMeasurementCommand | YES | ignore | YES |
| CorrectMeasurementCommand | YES | ignore | YES |
| RevisionCommand (+ pause/resume/close/start/skip/timer/reminder uses) | YES | ignore | YES |
| AbortCommand | YES | ignore (inherited) | YES |
| CompleteFermentationRequest | YES | ignore | YES |
| CompleteConditioningRequest | YES | ignore | YES |
| RecordWaiverRequest | YES | ignore | YES |
| AssessPackagingReadinessRequest | YES | ignore | YES |
| RecordPackagingHandoffRequest | YES | ignore | YES |
| StartAuxiliaryTimerCommand | YES | ignore | YES |
| CancelTimerCommand | YES | ignore | YES |
| ExtendTimerCommand | YES | ignore | YES |
| OperationOnlyCommand | YES | ignore | YES |
| CreateNoteCommand | YES | ignore | YES |
| RemoveAttachmentCommand | YES | ignore | YES |
| EnrichYeastReferenceCommand | YES | ignore | YES |
| ReconcileOgCommandBody | YES | forbid | NO (already) |
| RecordActionRequest | YES | forbid | NO |
| ExecutePlannedAdditionRequest | YES | forbid | NO |
| RecordUnplannedAdditionRequest | YES | forbid | NO |
| CorrectAdditionRequest | YES | forbid | NO |

| Metric | Value |
|---|---|
| PHASE_4_COMMAND_SCHEMA_COUNT | **22** (closed JSON command models) |
| PHASE_4_CLOSED_COMMAND_SCHEMA_COUNT | **22** |
| PHASE_4_CLOSED_COMMAND_SCHEMAS_REQUIRING_REPAIR | **17** |
| Media upload Form surface | Not a closed JSON schema (Phase 3 MIME/Form controls) |

`NESTED_UNKNOWN_FIELD_REQUIREMENT=NOT_REQUIRED` — no nested closed BaseModel command schemas; yeast `pitch_inputs`/`field_provenance` are documented open `dict` semantic fields, not nested command schemas.

`NESTED_UNKNOWN_FIELD_ACCEPTANCE=NOT_APPLICABLE`

## Remediation implementation

1. Added `Phase4ClosedCommand` base (`presentation/phase4_schemas.py`) with `ConfigDict(extra="forbid")`.
2. All 22 Phase 4 JSON command models inherit `Phase4ClosedCommand`.
3. Phase-4-scoped `RequestValidationError` handler in `main.py` maps `extra_forbidden` on `/api/v1/fermentation-sessions*` to `422` + `code=UNKNOWN_FIELD`. Other validation types and non-Phase-4 routes unchanged.
4. No migrations.

`ALL_PHASE_4_CLOSED_COMMAND_SCHEMAS_FORBID_UNKNOWN_FIELDS=YES`  
`MIGRATION_CHANGE_REQUIRED=NO`  
`UNKNOWN_FIELD_ERROR_NORMALIZATION=PASS`  
`VALIDATION_ERROR_CLASSIFICATION=PASS`

## Tests

| Gate | Location | Result |
|---|---|---|
| Exact AC-067 | `test_phase4_conditioning_security.py::test_mass_assignment_and_forged_fields_rejected` | Requires `422` + `UNKNOWN_FIELD`; permissive 200/422 branch **removed** |
| Fail-closed + side effects | `test_phase4_closed_command_schemas.py` | No revision/journal/operation success on reject |
| Structural guard | same | All 22 models `extra=forbid`; inventory equality |
| Compatibility | valid pause succeeds | PASS |
| Classification | missing/type/enum ≠ UNKNOWN_FIELD | PASS |
| Idempotency safety | rejected key not stored; reuse succeeds | PASS |
| OG reconcile code assert | `test_phase4_og_reconcile.py` | asserts `UNKNOWN_FIELD` |

`P4_AC_067_EXACT_TEST=PASS`  
`P4_AC_067_PERMISSIVE_ASSERTION_REMOVED=YES`  
`TEST_WOULD_FAIL_ON_FAILED_CANDIDATE=YES` (failed candidate ignored extras → 200)  
`CLOSED_SCHEMA_STRUCTURAL_GUARD=PASS`  
`CLOSED_SCHEMA_COVERAGE=PASS`  
`UNKNOWN_FIELD_FAIL_CLOSED=PASS`  
`VALID_COMMAND_COMPATIBILITY=PASS`  
`UNKNOWN_FIELD_SECURITY_BOUNDARY=PASS`  
`UNKNOWN_FIELD_IDEMPOTENCY_SAFETY=PASS`  
`UNKNOWN_FIELD_CONCURRENCY_SAFETY=PASS` (fails before OCC/domain lock)

## Regressions

| Gate | Result | Evidence |
|---|---|---|
| Focused CODEX-001 suite | PASS (10/10) | rebuilt API image |
| PHASE_1A / 2 / 3 / 4 SQLite (`pytest tests -k "phase4 or phase3 or phase2 or phase1"`) | PASS (exit 0) | `.pytest-p4-codex001-reg.txt` |
| SLICE_11_SERIALIZATION_REGRESSION | PASS (included in Phase 4 suite) | `test_slice11_serialization_regression_idempotent_close_payload` |

`PHASE_1A_REGRESSION=PASS`  
`PHASE_2_REGRESSION=PASS`  
`PHASE_3_REGRESSION=PASS`  
`PHASE_4_REGRESSION=PASS`  
`SLICE_11_SERIALIZATION_REGRESSION=PASS`

## Requirement accounting correction

Failed candidate incorrectly classified `P4-FR-077` as `FINAL_ACCEPTANCE_ONLY` and marked `P4-AC-067` VERIFIED without `UNKNOWN_FIELD`.

After remediation:

| ID | Classification |
|---|---|
| P4-FR-077 | **IMPLEMENTED** |
| P4-AC-067 | **VERIFIED** |

| Metric | Value |
|---|---|
| FEATURE_IMPLEMENTATION_REQUIRED_TOTAL | **0** |
| REMAINING_IMPLEMENTATION_CLUSTER_COUNT | **0** |
| PHASE_4_FEATURE_IMPLEMENTATION_COMPLETE | **YES** |

Do not rewrite the failed candidate artifact. Replacement candidate assembly is a separate gate.

## Phase 5 boundary

No packaging execution, inventory consumption, or Phase 5 operational surfaces added.

`PHASE_5_PLUS_OPERATIONAL_LEAKAGE=NO`  
`PHASE_4_PHASE_5_BOUNDARY=PASS`

## Self-review

Falsified: silent ignore of extras; permissive AC-067; mislabeling missing/type as UNKNOWN_FIELD; domain mutation on reject; journal/op success on reject; Phase 3 route envelope change; migration introduction; Phase 5 leakage.

`REMEDIATION_SELF_REVIEW=PASS`

## Stop

Remediation commit is **not** automatically a replacement Phase 4 candidate. Next: remediation delta reconciliation (separate authorization). No Codex re-invocation, merge, tag, deploy, or Phase 5 from this task.
