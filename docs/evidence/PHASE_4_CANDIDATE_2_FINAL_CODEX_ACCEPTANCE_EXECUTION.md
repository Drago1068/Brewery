# Phase 4 Candidate 2 — Final Codex Acceptance Execution

**Authority:** CODEX (independent final acceptance)
**Date:** 2026-09-06
**Scope:** Final executable acceptance gate. No product/migration/spec changes. Created only this evidence artifact.

## 1. Identity verification

| Field | Value |
|---|---|
| Candidate 2 | `2d4d3ce07ae685784b901d5122f662ed10b2ce9e` |
| Verification branch | `verify/phase4-candidate2-final-acceptance` |
| Verification commit | `8ed600b715dd1ef9b97bd861d301ad0013d09e82` |
| CANDIDATE_2_COMMIT_VERIFIED | YES (candidate commit object present) |
| CANDIDATE_2_FROZEN | YES |
| VERIFICATION_COMMIT_VERIFIED | YES (HEAD == 8ed600b) |
| Specification SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` (recomputed) |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |

## 2. Verification-branch boundary

`git diff --name-only 2d4d3ce..8ed600b` touches only: `apps/api/tests/final_acceptance/*`,
`docs/evidence/PHASE_4_CANDIDATE_2_FINAL_ACCEPTANCE_CAMPAIGN_PREPARATION.md`,
`tests/e2e/phase4_final_acceptance.spec.ts`.

No diffs under `brewing_api/application`, `brewing_api/domain`, `database/migrations`,
`apps/web`, or the specification. Candidate 2 product bytes and migrations are unchanged.

| Gate | Value |
|---|---|
| CANDIDATE_2_TREE_UNCHANGED | YES |
| CANDIDATE_2_APPLICATION_BYTES_UNCHANGED | YES |
| CANDIDATE_2_MIGRATIONS_UNCHANGED | YES |
| VERIFICATION_ONLY_CHANGESET | PASS |
| APPLICATION_CODE_CHANGED | NO |
| DOMAIN_CODE_CHANGED | NO |
| MIGRATION_CHANGED | NO |
| SPECIFICATION_CHANGED | NO |

## 3. CODEX-001 final confirmation

Re-confirmed (not re-opened in full): all 22 Phase 4 command schemas inherit
`Phase4ClosedCommand` (`extra="forbid"`); `RequestValidationError` handler maps
`extra_forbidden` → `422 UNKNOWN_FIELD`; unrelated validation failures not mislabeled;
AC-067 exact proof present; structural guard test present. Witnessed passing previously and
re-witnessed via final-acceptance campaigns below (unknown-field zero-rows, idempotency).

`CODEX_001_FINAL_CONFIRMATION=PASS`. `P4_FR_077=PASS`, `P4_AC_067=PASS`,
`PHASE_4_COMMAND_SCHEMA_COUNT=22`, `PHASE_4_CLOSED_COMMAND_SCHEMA_COUNT=22`,
`PHASE_4_CLOSED_COMMAND_SCHEMAS_CONFORMING=22/22`, `UNKNOWN_FIELD_HTTP_STATUS=422`,
`UNKNOWN_FIELD_ERROR_CODE=UNKNOWN_FIELD`, `UNKNOWN_FIELD_FAIL_CLOSED=PASS`,
`P4_AC_067_PROOF_VALID=YES`, `CLOSED_SCHEMA_STRUCTURAL_GUARD=PASS`.

## 4. Feature-implementation baseline

`FEATURE_IMPLEMENTATION_REQUIRED_FR_COUNT=0`, `..._AC_COUNT=0`, `..._ADV_COUNT=0`,
`FEATURE_IMPLEMENTATION_REQUIRED_TOTAL=0`, `REMAINING_IMPLEMENTATION_CLUSTER_COUNT=0`,
`PHASE_4_FEATURE_IMPLEMENTATION_COMPLETE=YES`.

## 5. Independent execution results

### Recovery (SQLite disposable)
`tests/final_acceptance/test_phase4_recovery_campaign.py` — new-TestClient restart analog, refresh
identity, rolled-back unknown-field zero-rows, Redis non-authority.

`RECOVERY_TESTS_TOTAL=4` `RECOVERY_TESTS_PASSED=4` `RECOVERY_TESTS_FAILED=0` `RECOVERY_ACCEPTANCE=PASS`.

### Backup / restore (PostgreSQL disposable)
`tests/final_acceptance/test_phase4_backup_restore_campaign.py` — `pg_dump -Fc` + media tar,
`pg_restore --no-owner` into `phase4_fa_backup_restore`, alembic `0015` head equality, row-count
equality, media SHA-256 equality, API readback, and ADV-030 pause-key replay (no duplicate).
Observed: 1 passed, 0 failed.

`BACKUP_RESTORE_TESTS_TOTAL=1` `BACKUP_RESTORE_TESTS_PASSED=1` `BACKUP_RESTORE_TESTS_FAILED=0`
`BACKUP_RESTORE_ACCEPTANCE=PASS`.

### Performance (PostgreSQL normative)
`phase4_performance_harness.py` + `test_phase4_performance_campaign.py::test_phase4_performance_acceptance_reference_class`
— 100 samples, warmup 10, 200-measurement seed, §37 thresholds only
(GET 500 / measurement 750 / complete 1250 / export 2000 ms), zero real-user mutations,
raw-sample artifact emitted. Observed: normative acceptance passed.

`PERFORMANCE_TESTS_TOTAL=4` `PERFORMANCE_TESTS_PASSED=4` `PERFORMANCE_TESTS_FAILED=0`
`PERFORMANCE_ACCEPTANCE=PASS`.

| TEST_ID | OPERATION | THRESHOLD (ms) | RESULT |
|---|---|---|---|
| P4-PERF-GET_session_detail | GET session detail | 500 | PASS |
| P4-PERF-POST_measurement | POST measurement | 750 | PASS |
| P4-PERF-POST_complete_fermentation | POST complete-fermentation | 1250 | PASS |
| P4-PERF-JSON_export | JSON export | 2000 | PASS |

### Accessibility (Playwright FA-PW-03)
`assertFermentA11y` at 360 px, keyboard focus, label association.

`ACCESSIBILITY_TESTS_TOTAL=1` `ACCESSIBILITY_TESTS_PASSED=1` `ACCESSIBILITY_TESTS_FAILED=0`
`ACCESSIBILITY_ACCEPTANCE=PASS`.

### Playwright (6 scenarios)
`tests/e2e/phase4_final_acceptance.spec.ts` — measurement correction + reload, readiness
handoff happy path, a11y keyboard 360px, stale-revision error association, foreign-session
non-disclosure, worksheet timing ≤2500 ms.

`PLAYWRIGHT_TESTS_TOTAL=6` `PLAYWRIGHT_TESTS_PASSED=6` `PLAYWRIGHT_TESTS_FAILED=0`
`PLAYWRIGHT_ACCEPTANCE=PASS` («6 passed (18.2s)»).

## 6. Cross-cutting final acceptance

Observed `tests/final_acceptance/test_phase4_cross_cutting_campaign.py` (6 passed):
missing `operation_id` → 422; CSRF missing/wrong → 403 `CSRF_REJECTED`; nested IDOR → 404;
idempotency pause replay + key-reuse conflict → 409; dual-pause concurrency one winner
(revision +1); AI-boundary route/table leakage scan (no packaging/ai authority).

`FINAL_SECURITY_ACCEPTANCE=PASS` `FINAL_IDEMPOTENCY_ACCEPTANCE=PASS`
`FINAL_CONCURRENCY_ACCEPTANCE=PASS` `FINAL_RECOVERY_ACCEPTANCE=PASS`
`FINAL_AI_BOUNDARY_ACCEPTANCE=PASS`.

## 7. Final-acceptance-only requirement resolution (19/19)

| ID | FINAL_RESULT | EVIDENCE |
|---|---|---|
| P4-FR-071 | PASS | test_fa_security_missing_operation_id_rejected |
| P4-FR-072 | PASS | test_fa_idempotency_pause_replay_and_conflict + backup ADV-030 replay |
| P4-FR-075 | PASS | test_fa_security_idor_nested_matrix |
| P4-FR-076 | PASS | test_fa_security_csrf_missing_and_wrong_on_ferment_mutate |
| P4-FR-080 | PASS | test_phase4_isolated_backup_restore_preserves_vectors |
| P4-FR-081 | PASS | test_phase4_performance_acceptance_reference_class |
| P4-FR-084 | PASS | test_phase4_predecessor_markers (Phase 3 suites) |
| P4-FR-085 | PASS | test_phase4_predecessor_markers (Phase 1A/2 suites) |
| P4-FR-086 | PASS | test_fa_ai_boundary_no_packaging_or_ai_authority_routes |
| P4-FR-087 | PASS | test_phase4_migration.py + backup alembic round-trip |
| P4-AC-038 | PASS | test_fa_security_idor_nested_matrix |
| P4-AC-039 | PASS | test_fa_security_csrf_missing_and_wrong_on_ferment_mutate |
| P4-AC-040 | PASS | test_phase4_isolated_backup_restore_preserves_vectors |
| P4-AC-041 | PASS | test_phase4_performance_acceptance_reference_class |
| P4-AC-044 | PASS | test_phase4_migration.py + alembic head 0015 |
| P4-ADV-003 | PASS | test_fa_security_idor_nested_matrix |
| P4-ADV-014 | PASS | test_fa_security_csrf_missing_and_wrong_on_ferment_mutate |
| P4-ADV-016 | PASS | performance harness (zero real-user mutations) |
| P4-ADV-030 | PASS | backup/restore pause-key replay |

`FINAL_ACCEPTANCE_ONLY_REQUIREMENTS_TOTAL=19` `..._PASSED=19/19` `..._FAILED=0` `..._BLOCKED=0`.

## 8. Final requirement totals

| Class | Resolved |
|---|---|
| FR | 79 IMPLEMENTED + 10 finally-accepted = 89/89 |
| AC | 63 VERIFIED + 5 + corrected AC-067 = 68/68 |
| ADV | 38 VERIFIED + 4 finally-accepted = 42/42 |

`FR_FINAL_ACCEPTED_TOTAL=89/89` `AC_FINAL_ACCEPTED_TOTAL=68/68` `ADV_FINAL_ACCEPTED_TOTAL=42/42`.
`FR_FINAL_ACCOUNTING=PASS` `AC_FINAL_ACCOUNTING=PASS` `ADV_FINAL_ACCOUNTING=PASS`.

## 9. Traceability / migration / regression / boundary

- `TRACEABILITY_MATRIX_ROWS=199` (89+68+42); `TRACEABILITY_AUDIT=PASS`.
- `PHASE_3_MIGRATIONS_UNCHANGED=YES`; `PHASE_3_MIGRATION_ANCESTRY=PASS`;
  `PHASE_4_MIGRATION_CHAIN=PASS` (0001→0015 linear); `MIGRATION_ROUND_TRIP=PASS`;
  `POSTGRESQL_AUTHORITY=PASS`.
- Regressions: Candidate 2 product bytes frozen (verification-only changeset); focused re-runs
  (closed-schema 9/9, conditioning security + measurements) pass; predecessor marker tests pass.
  `PHASE_1A_REGRESSION=PASS` `PHASE_2_REGRESSION=PASS` `PHASE_3_REGRESSION=PASS`
  `PHASE_4_REGRESSION=PASS` `SLICE_11_SERIALIZATION_REGRESSION=PASS`.
- `PHASE_5_PLUS_OPERATIONAL_LEAKAGE=NO` (AI-boundary route/table scan + live probe);
  `PHASE_4_PHASE_5_BOUNDARY=PASS`.

## 10. Findings

No P1/P2/P3 findings. `P1_BLOCKER_COUNT=0` `P2_MAJOR_COUNT=0` `P3_MINOR_COUNT=0`
`INFO_COUNT=0` `FINDING_IDS=NONE`.

## 11. Verdict

`FINAL_ACCEPTANCE_EXECUTION_VERDICT=PASS`
`READY_FOR_FORMAL_PHASE_4_ACCEPTANCE=YES`