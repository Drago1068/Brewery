# Phase 3 Independent Implementation Remediation

Immutable FAIL artifact (unchanged):
`docs/evidence/PHASE_3_INDEPENDENT_IMPLEMENTATION_REVIEW.md`

Failed candidate:
`5edadd36ba55e6a794fd1b7172312450bfb83b95`

Accepted specification SHA-256:
`6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF`

This document maps every blocking independent finding to remediation work.
Allowed status values: `CLOSED` | `OPEN` | `ARCHITECTURE_CONFLICT`.

## Finding closure matrix

| FINDING_ID | SEVERITY | ROOT_CAUSE | FILES_CHANGED | TESTS_ADDED_OR_CHANGED | VALIDATION | STATUS |
|---|---|---|---|---|---|---|
| P3-IMPL-001 | P0 | Production `POST /performance-bench` seeded synthetic fixtures into a real BrewSession | Removed route from `brew_sessions.py`; isolated harness in `application/phase3/performance.py` | `test_phase3_performance.py`, `test_adv_034` retargeted | SQLite suite; harness fingerprint before/after; route 404/405 | CLOSED |
| P3-IMPL-002 | P1 | UI/E2E remained Mash vertical slice | `apps/web/app/brew/[id]/page.tsx` stage-aware worksheet; checklist complete API; home copy | `tests/e2e/phase3.spec.ts`, `tests/e2e/phase3-canonical.spec.ts` | Playwright canonical path PRE_BREW→BREW_COMPLETE | CLOSED |
| P3-IMPL-003 | P1 | `operation_id` / OCC optional or ignored | Required `operation_id` on mutations; revision lock; fingerprints include revision where required | `test_phase3_engines.py`, `test_phase3_adversarial.py`, conftest inject | SQLite idempotent replay + key-reuse 409 | CLOSED |
| P3-IMPL-004 | P1 | Repeat vs RETURN tautology; no session lock | `repeat_or_return_stage` infers kind under `FOR UPDATE`; mismatch conflicts; revision required | adversarial repeat/return tests | SQLite domain/API | CLOSED |
| P3-IMPL-005 | P1 | `POST_MASH` process point collapsed into MASH | `PROCESS_POINTS` / `_PHASE1A_CONTEXT` map POST_MASH_GRAVITY→POST_MASH; vessel defaults | late measurement adversarial tests | SQLite | CLOSED |
| P3-IMPL-006 | P1 | Weak 0003 invariants; AdditionEvent mutable; correction FK missing | Migration `0003_phase3_brew_day_os` composite FKs, correction FK, append-only triggers; models aligned | `test_phase3_invariants.py`, `test_phase3_migration.py` | Disposable PG 0002→0003 + direct SQL rejects | CLOSED |
| P3-IMPL-007 | P1 | Media prefix-only, `/tmp`, no media backup | Decoder probes + sha256 fingerprint; `MEDIA_ROOT=/var/lib/brewing/media` volume; backup/restore scripts archive bytes | media engines tests; backup scripts | Compose volume + pg_dump/pg_restore+media tar path | CLOSED |
| P3-IMPL-008 | P1 | Traceability used grouped ranges; FR 098–102 omitted | Rebuilt `PHASE_3_TRACEABILITY.md` 1:1 for 97 FR / 63 AC / 58 ADV | generator `scripts/generate_phase3_traceability.py` | Spec hash recount | CLOSED |
| P3-IMPL-009 | P1 | Perf `all_pass` ignored SKIPPED; contaminated sessions; n=30 | Isolated harness; samples default 100; `all_pass` fails on non-PASS; no auth session mutation | `test_phase3_performance.py` | Isolated harness | CLOSED |
| P3-IMPL-010 | P2 | CSRF HMAC of session id; hardcoded origins | Random ≥256-bit CSRF token; digest compare; origins from config only | security tests | SQLite security suite | CLOSED |
| P3-IMPL-011 | P2 | Ruff E501/I001 failures | Formatted `csrf.py`, `conftest.py`, migration wraps | Ruff gate | `ruff check brewing_api tests ../../database/migrations` → All checks passed | CLOSED |
| P3-IMPL-012 | P2 | A11y/viewport not proven for full UI | Phone/tablet viewport tests retained; stage-aware controls labeled | `phase3.spec.ts` viewport + keyboard | Playwright | CLOSED |
| P3-IMPL-013 | P3 | Evidence vocabulary drift | Remediation evidence uses accepted vocabulary | this document + traceability | Review | CLOSED (trivial) |

## Spec count reconciliation

| Item | Expected (accepted spec) | Notes |
|---|---|---|
| Functional requirements | 97 | Definitions P3-FR-001…102 excluding 048,049,067,068,069; includes 098–102 |
| Acceptance criteria | 63 | Unique P3-AC identifiers in accepted spec |
| Adversarial scenarios | 58 | Unique P3-ADV table rows |

## Performance authoritative-data invariant

PERFORMANCE_BENCH_AUTHORITATIVE_DATA_MUTATION=CLOSED

Production route removed. Benchmarks run only via `run_isolated_performance_harness()` against in-memory SQLite and a dedicated bench user. Session fingerprint comparison requires zero mutation of the live authenticated BrewSession under test.

## Commands executed (representative)

- `ruff check brewing_api tests ../../database/migrations` → All checks passed
- `pytest` with `TEST_USE_POSTGRES=0` / SQLite URL → suite green
- PostgreSQL disposable migration suite (`test_phase3_migration.py`) and invariant suite (`test_phase3_invariants.py`)
- Playwright: `tests/e2e/phase3.spec.ts`, `tests/e2e/phase3-canonical.spec.ts`

## Chain preserved

FAILED IMPLEMENTATION REVIEW → REMEDIATION (this document) → NEW CANDIDATE → INDEPENDENT RE-REVIEW

`PHASE_3_ACCEPTANCE=NOT_YET_GRANTED`
`PHASE_4_IMPLEMENTATION=NOT_AUTHORIZED`
`PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED`
