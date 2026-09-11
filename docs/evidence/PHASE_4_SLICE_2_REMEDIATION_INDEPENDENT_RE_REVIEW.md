# Phase 4 Slice 2 — Remediation Independent Re-Review

## 1. Repository and commit receipt

| Field | Value |
|---|---|
| Root | `B:\brewing-platform` (`//NazarioNAS.local/USB_3TB/brewing-platform`) |
| Origin | `https://github.com/Drago1068/Brewery.git` |
| Branch | `phase4/slice2-review-remediation` |
| HEAD | `e962764259d292c1f5ef58292759855e1359b015` |
| Parent | `9dea54ce421d94accad400815c95cfdbecc43379` (verified exact) |
| Historic Slice 2 impl | `e2e9049d34295c32db3e310aaf76c6892335a64e` (ancestor, hash unchanged) |
| Historic Slice 2 closure | `b53119e868bcfc5be7214bcc5f4e8f0a4d467b26` (ancestor, hash unchanged) |
| Tracked worktree | CLEAN (no staged/unstaged diffs before or after review) |
| Untracked artifacts | 74 preserved, none staged, none deleted |

## 2. Six-file diff inventory (parent → remediation commit)

| File | Change |
|---|---|
| `apps/api/brewing_api/presentation/routes/fermentation_sessions.py` | F-002 `_parse_decimal_field` (422 INVALID_NUMERIC_VALUE) on record/correct measurement paths; import-sort/UTC ruff fixes |
| `apps/api/brewing_api/application/phase4/measurements.py` | F-003 session-pause deny removed; F-004 strict offset for client-supplied correction timestamps with UTC-coerced inheritance; ruff fixes |
| `apps/api/brewing_api/application/phase4/time_validation.py` | F-003 dead helper removed; ruff fixes (UTC alias, line length, unused imports) |
| `packages/calculations/fermentation.py` | F-005 authority-retention note; unused-import removal |
| `apps/api/tests/test_phase4_slice2_remediation.py` | New: 7 contract tests (F-001/F-002×2/F-003×2/F-004/F-005) |
| `docs/evidence/PHASE_4_SLICE_2_REMEDIATION_EVIDENCE.md` | New: remediation evidence record |

No Phase 5A, later-slice, deployment, dependency, Docker, or production-config
change. The committed evidence artifact was spot-checked against the diff and
test logs: file inventory, dispositions, and test/PG/migration claims match
independent observation, except it does not mention the repo-wide ruff debt
(264 pre-existing errors) — recorded as debt below, not a misrepresentation of
remediation scope.

## 3. Closure matrix (independent recheck)

| ID | Verdict | Basis |
|---|---|---|
| F-001 | CLOSED | Structural guard covers all 22 closed schemas incl. both Slice 2 models; committed correction-endpoint test plus independent live run prove 422 UNKNOWN_FIELD with zero measurement/correction/operation/journal mutation. |
| F-002 | CLOSED | Independent live runs: empty/malformed/NaN/±Infinity rejected 422 on record + correction (+sample-temp), zero mutation; valid precision/canonicalization suites still pass. |
| F-003 | CLOSED | Spec §18 (lines 823–825) governs by **stage** status with an explicit PAUSED-stage window; no session-level prohibition exists — no ADR needed. Live: pause→record 201 (late_entry false)→resume; out-of-window while paused still 422; ownership/OCC/terminal rules untouched in diff. |
| F-004 | CLOSED | Live: naive client correction timestamp → 422 TIMESTAMP_NOT_UTC, zero mutation; aware input accepted; omitted input inherits validated leaf. SQLite coercion path does not affect PostgreSQL (timestamptz returns aware; PG suites pass). |
| F-005 | NOT_REQUIRED | Independently reproduced: coefficients identical on [1.000, 1.300], bounds (−28.220507, 61.239729), round-trip < 1e-7, shared authority raises below SG 1.000 — delegation would break valid negative-Plato inputs. Documented in source + golden test. |
| F-006 | CLOSED (scoped) | Independent `ruff check` on all 5 owned Python files: PASS. Repo-wide authoritative command reports 264 errors, zero in owned files; commit touches only those files, so zero new violations by construction. |
| F-007 | NOT_APPLICABLE | CI (`.github/workflows/ci.yml`) gates are `ruff check` + `pytest` (+ `alembic upgrade head` on PG); no mypy/pyright config or documented typecheck command exists anywhere in the repo. |
| F-008 | DEFERRED | Retained: stage identity comes server-side from the validated original row; session lock + leaf-match + composite FK on measurements close the attach path. No accepted invariant mandates the extra DB key. |
| F-009 | DEFERRED | Retained: `evaluated_at` ties across separate transactions are not observed; a secondary ordering is recommended at next touch but no observable result varies today. |
| F-010 | ADR_REQUIRED_NONBLOCKING | Spec §12.1 names temperature-sensitive methods without defining them in any method vocabulary; all observable Slice 2 behaviors are enforced and tested, so current behavior is conformant. Taxonomy needs future ADR/spec clarification, non-blocking. |

## 4. PostgreSQL and migration evidence (independent reproduction)

- Environment: disposable `postgres:17.6-alpine` (matches CI), container
  `p4s2-rereview-pg`, fresh volume, CI-identical credentials, removed after use.
- `alembic upgrade head`: exit 0, 0001→0015.
- PG suites: closure+migration+remediation 23 passed; measurements
  api/security/matrix/pitch/entry/closed/domain + Phase 3 concurrency 57
  passed; zero failures (concurrency one-winner, lineage, ownership exercised).
- Round trip: downgrade to `0005_phase4_measurements_derived_gravity` then
  `upgrade head`, both exit 0; single `alembic_version` row (`0015`); all 3
  measurement tables and all 5 Slice 2 constraints
  (`uq_fermentation_measurement_session`,
  `fk_fermentation_measurement_stage_session`,
  `uq_fermentation_measurement_correction_leaf`,
  `uq_fermentation_correction_session`, `uq_phase4_operation_scope`) verified
  present; post-round-trip closure suite 6 passed.

## 5. Targeted and regression results (independent runs)

- Targeted SQLite: remediation 7 pass; closed-schemas + measurements-api 14
  pass (incl. correction-chain regression).
- Slice 2 SQLite: domain/security/pitch/entry 19 pass; matrix/lifecycle/
  conditioning 41 pass.
- PG: as §4 (86 + 6 test executions, all pass).
- `test_phase3_evidence_closure`: 20 pass, 1 fail (`ac_032` hygiene artifact —
  qualifier 2 below).

## 6. Ruff: scoped vs repository-wide

- Touched files: PASS (independent run).
- Authoritative `ruff check . ../../database/migrations`: 264 pre-existing
  errors (F811/E501/I001/F401/UP017/E402/F841/B009); zero in remediation files;
  remediation commit provably introduces zero new violations (only the 6 clean
  files changed).

## 7. Qualifier classification (re-checked at remediation HEAD)

1. Stale Alembic-head assertion: `evidence_closure::ac_001` now PASSES (fixed
   by later history). The twin assertion in `test_postgres_integrity.py:45-48`
   (`== "0003_phase3_brew_day_os"`) necessarily fails on any post-Phase-3
   head — **stale test expectation**, pre-existing, untouched by remediation,
   does not block Slice 2, needs separate policy disposition (not silent edit).
2. `apps/api/.test-brewing.db` artifact: reproduces now — **test-isolation
   defect** (suite creates the file its own meta-test flags), pre-existing,
   does not block Slice 2.
3. Phase 3 naive/aware failure: does **not** reproduce at this HEAD
   (`fr_095` passed) — pre-existing defect resolved by later history,
   unaffected by remediation.

## 8. Unresolved debt (not blocking)

- Repo-wide ruff debt (264 errors, none remediation-owned).
- Stale `test_postgres_integrity` head assertion (separate policy decision).
- Deferred advisories F-008/F-009; F-010 taxonomy ADR (non-blocking).
- No authoritative Python typecheck gate (project-level gap, not Slice 2).

## 9. New findings

None. No P0/P1/P2 introduced; no P3 beyond the already-reported style residual,
which this remediation reduced in its owned files.

## 10. Verdict

PASS: F-001–F-004 closed and independently exercised; F-005 justified
NOT_REQUIRED with reproduced proofs; no new Ruff/regression failures;
F-007 genuinely NOT_APPLICABLE; PostgreSQL and migration independently
reproduced green; no P0/P1, no open P2; F-010 non-blocking; no forward leakage.

## Machine-readable result

PHASE_4_SLICE_2_REMEDIATION_REVIEW=PASS
REPOSITORY_VALID=YES
BRANCH=phase4/slice2-review-remediation
HEAD=e962764259d292c1f5ef58292759855e1359b015
PARENT_VERIFIED=YES
COMMIT_SCOPE_VALID=YES
EXPECTED_FILES_CHANGED=6
ACTUAL_FILES_CHANGED=6
TRACKED_WORKTREE_CLEAN=YES
ORIGINAL_UNTRACKED_ARTIFACTS_PRESERVED=YES
F_001=CLOSED
F_002=CLOSED
F_003=CLOSED
F_004=CLOSED
F_005=NOT_REQUIRED
F_006=CLOSED
F_007=NOT_APPLICABLE
F_008=DEFERRED
F_009=DEFERRED
F_010=ADR_REQUIRED_NONBLOCKING
POSTGRESQL_TESTS=PASS
MIGRATION_VERIFICATION=PASS
TARGETED_TESTS=PASS
SLICE_2_REGRESSION_TESTS=PASS
REPOSITORY_WIDE_REGRESSION_TESTS=QUALIFIED
TOUCHED_FILES_RUFF=PASS
REPOSITORY_WIDE_RUFF=FAIL
AUTHORITATIVE_TYPECHECK=NOT_APPLICABLE
P0_FINDINGS=0
P1_FINDINGS=0
P2_FINDINGS=0
P3_FINDINGS=0
ADVISORY_FINDINGS=3
REVIEW_ARTIFACT_CREATED=YES
REVIEW_ARTIFACT_STAGED=NO
COMMIT_CREATED=NO
MERGE_PERFORMED=NO
TAG_CREATED=NO
PUSH_PERFORMED=NO
DEPLOYMENT_PERFORMED=NO
