# Phase 4 Independent Codex Implementation Review

**Reviewer:** CODEX (independent verification gate)
**Date:** 2026-09-05
**Mandate:** Independent review only — no feature/migration/spec repairs, no merge, no tag, no deploy, no NAS production access.

## 1. Candidate identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Candidate commit | `dea5e369af411f78d1230c2b4063ae2f77b9aba8` |
| HEAD resolution | `dea5e369af411f78d1230c2b4063ae2f77b9aba8` (candidate == HEAD) |
| Candidate artifact | `docs/evidence/PHASE_4_IMPLEMENTATION_CANDIDATE.md` (committed) |
| Candidate tag | NOT_CREATED |

`CANDIDATE_COMMIT_VERIFIED=YES`

## 2. Specification verification

| Check | Result |
|---|---|
| Spec SHA-256 (recomputed) | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| Expected SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Candidate descends from `v0.4.0-phase4-spec` (`bc063d1…`) | PASS |

## 3. Requirement accounting

| Class | Candidate claim | Independent | Reconciliation |
|---|---|---|---|
| FR IMPLEMENTED | 78 | 78 | 78 + 11 = 89 |
| FR FINAL_ACCEPTANCE_ONLY | 11 | 11 (one mis-classified — see finding) | — |
| AC VERIFIED | 63 | 63 | 63 + 5 = 68 |
| AC FINAL_ACCEPTANCE_ONLY | 5 | 5 | — |
| ADV VERIFIED | 38 | 38 | 38 + 4 = 42 |
| ADV FINAL_ACCEPTANCE_ONLY | 4 | 4 | — |

Arithmetic (`78+11=89`, `63+5=68`, `38+4=42`) is internally consistent. Classification of
`P4-FR-077` as FINAL_ACCEPTANCE_ONLY is **incorrect** (see finding CODEX-001).

## 4. Migration review

Migration chain is linear and valid: `0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007 →
0008 → 0009 → 0010 → 0011 → 0012 → 0013 → 0014 → 0015`. No duplicate revision IDs, all
down-revisions valid, Phase 3 migrations `0001`–`0003` untouched.

| Check | Result |
|---|---|
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS |
| PHASE_4_MIGRATION_CHAIN | PASS |
| Migration file SHA-256 vs manifest (0001–0015) | ALL MATCH (no rewrite) |

## 5. Traceability ledger

`TRACEABILITY_MATRIX_ROWS=199` verified: 89 FR + 68 AC + 42 ADV = 199. All 89 FR-001–089,
68 AC-001–068, 42 ADV-001–042 mapped. No fabricated/stale IDs found in sampled checks.

## 6. Slice provenance

Slices S1–S15 + delta docs N1/N14c/N15 reachable on branch; feature commits (17bf72a … dea5e36)
form linear ancestry from `v0.4.0-phase4-spec`. Implementation modules (`actions`, `additions`,
`deviations`, `waivers`, `readiness`, `equipment`, `export`, `journal`, `media`, `notes`,
`yeast`, `plan`, `og_consumption`, …) and per-slice test files all exist. No material feature
implementation observed only in uncommitted files (working tree tracked-clean).

## 7. Cross-cutting foundations (verified present)

| FR (FAO) | Foundation | RESULT |
|---|---|---|
| FR-071 operation_id on mutations | required in all mutation request schemas | present |
| FR-072 phase4-operation-v1 | `operations.py` fingerprint/tombstone/retention | present |
| FR-075 owner-only 404 | session getters + per-family nested-source getters | present |
| FR-076 CSRF | `Phase3SecurityMiddleware` added globally (`main.py:52`) | present |
| FR-080/081/084/085/086/087 | backup/perf/regression/leakage/migration campaigns | acceptance-only |

## 8. FINDINGS

### CODEX-001 — Closed command schemas / `422 UNKNOWN_FIELD` not implemented

- **SEVERITY:** P2_MAJOR
- **REQUIREMENT_IDS:** P4-FR-077, P4-AC-067 (spec §30 lines 1081; §33 lines 1163)
- **FILE:** `apps/api/brewing_api/presentation/routes/fermentation_sessions.py` (lines 54–167)
- **DESCRIPTION:** The accepted specification requires every closed command schema to reject
  unknown fields with `422 UNKNOWN_FIELD` and to never ignore unknown fields. Only 5 of the
  ~19 Phase 4 command request schemas set `model_config = ConfigDict(extra="forbid")`
  (`ReconcileOgCommandBody`, `RecordActionRequest`, `ExecutePlannedAdditionRequest`,
  `RecordUnplannedAdditionRequest`, `CorrectAdditionRequest`). The remaining schemas
  (`StartFermentationCommand`, `RecordMeasurementCommand`, `CorrectMeasurementCommand`,
  `RevisionCommand` and its subclasses, `OperationOnlyCommand`, `CreateNoteCommand`,
  `RemoveAttachmentCommand`, `EnrichYeastReferenceCommand`) do **not** forbid extras, so Pydantic
  v2 silently ignores unknown fields. The string `UNKNOWN_FIELD` does not appear anywhere in
  `apps/` or `packages/`; no `RequestValidationError` handler emits it.
- **EXPECTED:** Extra/unknown JSON field on any Phase 4 mutation → `422` with `code=UNKNOWN_FIELD`, no domain/operation-success rows.
- **ACTUAL:** Extra/unknown field silently ignored; request returns `200`/`201`; field not persisted.
- **REPRODUCTION:** POST to any measurement/lifecycle/conditioning/timer/note/yeast endpoint
  with an extra field (e.g. `"status": "..."`). The existing test
  `test_phase4_conditioning_security.py::test_mass_assignment_and_forged_fields_rejected`
  demonstrates the weakness: it accepts **either** `200` (extra ignored) **or** `422`.
- **RECOMMENDED_REMEDIATION_SCOPE:** Add `extra="forbid"` (or a shared closed base) to all
  Phase 4 command schemas and map validation to `422 UNKNOWN_FIELD`; strengthen AC-067 to
  require the exact `422`/`UNKNOWN_FIELD` outcome.

This finding makes the candidate's central claim
`FINAL_ACCEPTANCE_BUCKET_CONTAINS_MISSING_FEATURE_CODE=NO` **false** for P4-FR-077, and shows
P4-AC-067 is marked VERIFIED without the required behavior (`422 UNKNOWN_FIELD`) actually
being produced.

- **FEATURE_IMPLEMENTATION_REQUIRED_TOTAL:** 1 (P4-FR-077)

## 9. Final verdict

| Metric | Value |
|---|---|
| P1_BLOCKER_COUNT | 0 |
| P2_MAJOR_COUNT | 1 |
| P3_MINOR_COUNT | 0 |
| INFO_COUNT | 0 |
| INDEPENDENT_REVIEW_VERDICT | **FAIL** |
| READY_FOR_FORMAL_PHASE_4_ACCEPTANCE | NO |