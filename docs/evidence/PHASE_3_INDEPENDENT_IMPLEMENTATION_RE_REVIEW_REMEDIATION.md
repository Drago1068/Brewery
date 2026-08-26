# Phase 3 Independent Implementation Re-Review Remediation

Immutable FAIL artifact (unchanged; do not modify):
`docs/evidence/PHASE_3_INDEPENDENT_IMPLEMENTATION_RE_REVIEW.md`

Failed implementation candidate:
`5edadd36ba55e6a794fd1b7172312450bfb83b95`

Failed re-review candidate:
`d0c8f8366d54760e8f4f652af3995321acf9f35c`

Current remediation candidate commit:
the git commit on `codex/phase3-brew-day-os` that contains this file (see `git rev-parse HEAD` after that commit)

Accepted specification SHA-256:
`6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF`

This document maps every re-review finding to remediation work. Allowed status values: `CLOSED` | `IN_PROGRESS` | `OPEN` | `ARCHITECTURE_CONFLICT`. Status is `CLOSED` only when the named validation for that finding was executed on this candidate.

## Finding closure matrix

| FINDING_ID | SEVERITY | ROOT_CAUSE | FILES_CHANGED | TESTS_ADDED_OR_CHANGED | VALIDATION | STATUS |
|---|---|---|---|---|---|---|
| P3-IMPL-RR-001 | P1 | Full browser suite red; canonical flow skipped repeat/return/media and accepted ACTIVE terminal | `apps/web/app/brew/[id]/page.tsx`; `tests/e2e/helpers.ts`; `tests/e2e/phase3-canonical.spec.ts`; `tests/e2e/phase3.spec.ts` | Playwright canonical/pause/voice/viewport/a11y | `docker compose -p bicos_phase3_remed --profile test run --rm e2e`: 8 passed, 0 failed, 1 skipped (opt-in browser sampler). Canonical flow asserted PRE_BREW through BREW_COMPLETE, mash extras, media, repeat | CLOSED |
| P3-IMPL-RR-002 | P1 | Critical mutations accepted missing operation/revision; tests rewrote the wire contract | `apps/api/brewing_api/presentation/routes/brew_sessions.py`; `apps/api/tests/conftest.py`; `apps/api/brewing_api/application/phase3/commands.py` | `test_phase3_adversarial.py`; `test_phase3_engines.py`; `test_phase3_concurrency.py` | Production mutations require `operation_id` and `expected_revision`; conftest no longer injects them; PostgreSQL suite 121 passed, 0 failed | CLOSED |
| P3-IMPL-RR-003 | P1 | Repeat/return lacked concurrent PostgreSQL and browser proof | `apps/api/brewing_api/application/phase3/commands.py` | `test_phase3_concurrency.py`; canonical E2E Repeat Mash | Parallel PostgreSQL clients (`test_concurrent_repeat_*`, `test_concurrent_controlled_return_*`, `test_concurrent_http_repeat_*`) plus unconditional browser repeat in canonical flow | CLOSED |
| P3-IMPL-RR-004 | P1 | Measurement context defaulted; append-only trigger blocked legitimate finalization | `apps/api/brewing_api/application/brew_day.py`; `apps/api/brewing_api/domain/measurements/models.py` | `test_brew_day_api.py`; measurement adversarial tests | Observed type-specific context required; PostgreSQL measurement create/correct in the 121-pass suite | CLOSED |
| P3-IMPL-RR-005 | P1 | Incomplete same-session/lineage invariants | `database/migrations/versions/0003_phase3_brew_day_os.py` | `test_phase3_invariants.py`; `test_phase3_migration.py` | Direct SQL rejects cross-session timer/attachment/requirement/correction; addition events append-only; correction FK; Alembic 0002↔0003 round-trip on disposable PostgreSQL | CLOSED |
| P3-IMPL-RR-006 | P1 | Media decoder/atomicity incomplete; backup test did not restore representative state | `apps/api/brewing_api/application/phase3/media.py`; `infrastructure/docker/api.Dockerfile`; backup helpers | `test_phase3_backup_restore.py`; `test_truncated_png_is_rejected_by_decoder` | Bounded Pillow decoder; isolated `pg_dump`/`pg_restore` preserves attachment metadata and media bytes; Dockerfile copies backup scripts | CLOSED |
| P3-IMPL-RR-007 | P1 | Traceability used invented suite labels, globs, and wrong mappings | `scripts/generate_phase3_traceability.py`; `docs/evidence/PHASE_3_TRACEABILITY.md` | Generator fails if a referenced pytest/Playwright name is missing | Rebuilt 97/63/58 matrices with exact TEST_FILE/TEST_NAME; PASS only where named executables ran; P3-FR-090 is `_finalize_order` | CLOSED |
| P3-IMPL-RR-008 | P1 | Performance harness outside normative reference class/dataset/browser sampling | `apps/api/brewing_api/application/phase3/performance.py` | `test_phase3_performance.py`; `tests/e2e/phase3-performance.spec.ts` | PostgreSQL harness n=100 (`test_phase3_performance_acceptance_reference_class`) plus two-tab Playwright sampler `PHASE3_PERF_BROWSER=1` (1 passed). Production `/performance-bench` remains absent | CLOSED |
| P3-IMPL-RR-009 | P2 | Accessibility not proven for full stage-aware product | `apps/web/app/brew/[id]/page.tsx`; `tests/e2e/helpers.ts` `assertBrewDayA11y` | `tests/e2e/phase3.spec.ts` viewport/keyboard; canonical flow | Phone/tablet viewports, keyboard focus, error association, voice dialog, media controls, and terminal brew-day a11y assertions executed in the green Playwright suite | CLOSED |

## Spec count reconciliation

| Item | Expected (accepted spec) | Current matrix |
|---|---|---|
| Functional requirements | 97 | 97 rows (PASS=86, NOT_PROVEN=11) |
| Acceptance criteria | 63 | 63 rows (PASS=40, NOT_PROVEN=23) |
| Adversarial scenarios | 58 | 58 rows (PASS=46, NOT_PROVEN=12) |
| Highest FR | P3-FR-102 | P3-FR-102 |
| Missing FR numbers | 048,049,067,068,069 | 048,049,067,068,069 |

`PASS` is named-executable evidence from this candidate (PostgreSQL pytest and/or Playwright). It is not independent Codex acceptance. Independently accepted complete counts remain 0.

NOT_PROVEN identifiers are listed in `PHASE_3_TRACEABILITY.md`. They are items whose mapped test still does not prove the full requirement (process gates, incomplete type/boundary matrices, review invariants), not skipped green tests.

## Validation evidence (this candidate)

Compose project: `bicos_phase3_remed` (api `127.0.0.1:18300`, web `127.0.0.1:18301`). Spec file was not modified.

| Gate | Command | Result |
|---|---|---|
| Spec hash | SHA-256 of `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` | MATCH `6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF` |
| PostgreSQL pytest | `docker compose -p bicos_phase3_remed exec -e TEST_USE_POSTGRES=1 -T api pytest -q --tb=line` | 121 passed, 0 failed, 0 skipped, exit 0 |
| Playwright (required command) | `docker compose -p bicos_phase3_remed --profile test run --rm e2e` | 8 passed, 0 failed, 1 skipped, exit 0. First attempt failed 401 after pytest truncated `users`; API restart restored bootstrap `brewer`; retry green |
| Playwright two-tab sampler | same e2e image with `-e PHASE3_PERF_BROWSER=1` `npx playwright test phase3-performance.spec.ts` | 1 passed |
| Ruff | `docker compose -p bicos_phase3_remed exec -T api ruff check brewing_api tests` | All checks passed |
| API restart recovery | Restart `bicos_phase3_remed-api-1`; login + GET `/api/v1/brew-sessions/active` | Same ACTIVE session `08286eea-…` survived |
| Redis-loss recovery | Stop Redis; login + GET active session | Session still returned from PostgreSQL; `/health/ready` 503 while Redis down (readiness, not authority) |
| Traceability generator | `python scripts/generate_phase3_traceability.py` | 97/63/58 rows; missing names fail generation |

Pytest collect-only on the API image (same 121 functions executed): auth 3, brew_day 5, calculations 3, phase2 11, postgres integrity 3, phase3 adversarial 38, api 5, backup 1, concurrency 4, engines 14, invariants 8, materialization 8, migration 4, observability 2, performance 3, security 10.

## Chain preserved

FAILED IMPLEMENTATION REVIEW (`5edadd36…`) → first remediation → FAILED RE-REVIEW (`d0c8f83…`, immutable FAIL) → CURRENT REMEDIATION (this commit) → new independent re-review (not yet requested)

`PHASE_3_ACCEPTANCE=NOT_YET_GRANTED`
`PHASE_4_IMPLEMENTATION=NOT_AUTHORIZED`
`PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED`
