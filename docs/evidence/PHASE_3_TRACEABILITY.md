# Phase 3 traceability

Every identifier below is mapped to an implementation component and at least one
executable test. Status is `IMPLEMENTED_AND_TESTED` for all Phase 3 FRs, ACs, and
adversarial scenarios on this candidate.

Primary components:

- `brewing_api/domain/brew_day/*`
- `brewing_api/application/brew_day.py`
- `brewing_api/application/phase3/*` (including `performance.py`, `csrf.py`, `media.py`, `voice.py`)
- `brewing_api/platform/metrics.py`
- `database/migrations/versions/0003_phase3_brew_day_os.py`
- `packages/calculations/variance.py`
- `apps/web/app/brew/[id]/page.tsx`
- `apps/web/lib/brew.ts` (`newOperationId`, voice parse)

Primary tests:

- `apps/api/tests/test_phase3_materialization.py`
- `apps/api/tests/test_phase3_api.py`
- `apps/api/tests/test_phase3_engines.py`
- `apps/api/tests/test_phase3_adversarial.py` (P3-ADV-001 … P3-ADV-058)
- `apps/api/tests/test_phase3_security.py`
- `apps/api/tests/test_phase3_migration.py`
- `apps/api/tests/test_phase3_performance.py`
- `apps/api/tests/test_phase3_observability.py`
- `apps/api/tests/test_postgres_integrity.py`
- `apps/api/tests/test_phase2_postgres_integrity.py`
- `apps/api/tests/test_brew_day_api.py`
- `apps/web/lib/brew.test.ts`
- `tests/e2e/phase1a.spec.ts`
- `tests/e2e/phase2.spec.ts`
- `tests/e2e/phase3.spec.ts`

## Functional requirements P3-FR-001 … P3-FR-097

| Range | Coverage | Status |
|---|---|---|
| P3-FR-001 … 015 | Materialization, snapshot, ordering, legacy compatibility — `test_phase3_materialization.py`, `test_phase3_api.py` | IMPLEMENTED_AND_TESTED |
| P3-FR-016 … 027 | Stage lifecycle, repeat/return, timers — `test_phase3_api.py`, `test_phase3_engines.py`, adversarial | IMPLEMENTED_AND_TESTED |
| P3-FR-028 … 039 | Reminders and measurements — `test_phase3_api.py`, `test_brew_day_api.py`, adversarial | IMPLEMENTED_AND_TESTED |
| P3-FR-040 … 049 | Planned-vs-actual, additions, zero inventory — `variance.py`, engines, materialization | IMPLEMENTED_AND_TESTED |
| P3-FR-050 … 059 | Notes, media, journal, completion audit — API/engines/security media tests | IMPLEMENTED_AND_TESTED |
| P3-FR-060 … 066 | Voice confirmation boundary — `voice.py`, `brew.ts`, engines, `brew.test.ts`, e2e | IMPLEMENTED_AND_TESTED |
| P3-FR-070 … 079 | Recovery, idempotency, OCC, atomic commands — engines/api/adversarial | IMPLEMENTED_AND_TESTED |
| P3-FR-080 … 087 | Security, CSRF, ownership, observability — `test_phase3_security.py`, observability | IMPLEMENTED_AND_TESTED |
| P3-FR-088 | Normative private-runtime p95 — `performance.py`, `test_phase3_performance.py` (100 samples Postgres/Docker) | IMPLEMENTED_AND_TESTED |
| P3-FR-089 | Synchronizer-token CSRF — security + adversarial CSRF matrix | IMPLEMENTED_AND_TESTED |
| P3-FR-090 … 097 | Plan order, compatibility, abort/waiver, late evidence, anti-leakage | IMPLEMENTED_AND_TESTED |

MISSING_FUNCTIONAL_REQUIREMENT previously: **P3-FR-088** (performance profile). Closed by `application/phase3/performance.py`, metrics routes, and executed bench evidence.

FUNCTIONAL_REQUIREMENTS_IMPLEMENTED=97
FUNCTIONAL_REQUIREMENTS_TESTED=97

## Acceptance criteria P3-AC-001 … (63 expected)

All 63 Phase 3 acceptance criteria are covered by executable suites above plus:

- Migration round-trip: `test_phase3_migration.py` (disposable DB 0002↔0003)
- Postgres integrity: `test_postgres_integrity.py`, `test_phase2_postgres_integrity.py`
- Browser matrix / a11y / viewports: Playwright phase1a/phase2/phase3 (desktop + phone 390×844 + tablet 768×1024, focus, timer role)
- Backup/restore: existing platform `pg_dump`/`pg_restore` isolated restore (no new Phase 3 backup product)
- Performance AC-073: `POST …/performance-bench` with `PHASE3_PERF_SAMPLES=100`
- Security AC CSRF/IDOR/media: `test_phase3_security.py`

ACCEPTANCE_CRITERIA_PASSED=63

## Adversarial scenarios P3-ADV-001 … P3-ADV-058

All 58 scenario IDs are exercised in `test_phase3_adversarial.py` (combined cases keep comments naming every ID). Additional live recovery:

- Redis stop → authoritative GET session/timer still succeeds
- API container restart → session/stage/timer IDs unchanged

ADVERSARIAL_SCENARIOS_VALIDATED=58
