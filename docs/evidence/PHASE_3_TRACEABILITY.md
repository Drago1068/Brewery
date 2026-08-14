# Phase 3 traceability

Every identifier below is mapped to an implementation component and at least one executable test. Status is `IMPLEMENTED_AND_TESTED` unless noted `BLOCKED`.

Primary components:

- `brewing_api/domain/brew_day/*`
- `brewing_api/application/brew_day.py`
- `brewing_api/application/phase3/*`
- `database/migrations/versions/0003_phase3_brew_day_os.py`
- `packages/calculations/variance.py`
- `apps/web/app/brew/[id]/page.tsx`

Primary tests:

- `apps/api/tests/test_phase3_materialization.py`
- `apps/api/tests/test_phase3_api.py`
- `apps/api/tests/test_phase3_engines.py`
- `apps/api/tests/test_brew_day_api.py`
- `apps/api/tests/test_phase2_core.py`
- `apps/web/lib/brew.test.ts`
- `tests/e2e/phase1a.spec.ts`
- `tests/e2e/phase2.spec.ts`
- `tests/e2e/phase3.spec.ts`

## Functional requirements P3-FR-001 … P3-FR-097

P3-FR-001 through P3-FR-015 (session snapshot, materialization, ordering, legacy compatibility): `test_phase3_materialization.py`, `test_phase3_api.py`. IMPLEMENTED_AND_TESTED.

P3-FR-016 through P3-FR-027 (stage lifecycle, repeat/return, timers): `test_phase3_api.py`, `test_phase3_engines.py`. IMPLEMENTED_AND_TESTED.

P3-FR-028 through P3-FR-039 (reminders and measurements): `test_phase3_api.py`, `test_brew_day_api.py`, `test_phase3_engines.py`. IMPLEMENTED_AND_TESTED.

P3-FR-040 through P3-FR-049 (planned versus actual, additions, no inventory effect): `packages/calculations/variance.py`, `test_phase3_engines.py`, `test_phase3_materialization.py`. IMPLEMENTED_AND_TESTED.

P3-FR-050 through P3-FR-059 (notes, media, journal, completion audit): `test_phase3_api.py`, `test_phase3_engines.py`. IMPLEMENTED_AND_TESTED.

P3-FR-060 through P3-FR-066 (voice confirmation boundary): `voice.py`, `brew.ts`, `test_phase3_engines.py`, `brew.test.ts`, `tests/e2e/phase3.spec.ts`. IMPLEMENTED_AND_TESTED.

P3-FR-070 through P3-FR-079 (recovery, idempotency, OCC, atomic commands): `test_phase3_engines.py`, `test_phase3_api.py`. IMPLEMENTED_AND_TESTED. Worker restart is N/A.

P3-FR-080 through P3-FR-089 (security, CSRF, ownership, performance): `test_phase3_api.py`, `test_phase3_engines.py`. P3-FR-088 production-class p95 beyond dashboard GET is BLOCKED pending reference-class hardware evidence. Remaining security FRs: IMPLEMENTED_AND_TESTED.

P3-FR-090 through P3-FR-097 (plan order, compatibility, repeat/return, abort/waiver, late evidence, anti-leakage): `test_phase3_materialization.py`, `test_phase3_engines.py`, `test_phase3_api.py`. IMPLEMENTED_AND_TESTED.

## Acceptance criteria

Covered by executable tests: P3-AC-001, 002, 003, 004, 010-018, 023, 024, 030, 031 (partial MIME/header), 040, 043, 060-068, 072, 074, 076-082.

BLOCKED pending remaining validation evidence: P3-AC-020/021/022 (Postgres upgrade/round-trip), P3-AC-032/033 (secret/dependency audit in CI), P3-AC-041/042/044/045 (full browser matrix, a11y, viewport photos), P3-AC-050-054 (complete candidate-tree gate including production build and backup/restore), P3-AC-069 (full failure-injection E2E), P3-AC-070/071 (complete invariant/observability matrix), P3-AC-073 (full p95 profile).

## Adversarial scenarios P3-ADV-001 … P3-ADV-058

Exercised in API/domain tests: duplicate requests, two-user disclosure, CSRF missing token, stale revision, timer expiry after reconnect, addition without inventory mutation, waiver vs measurement, aborted-session evidence prohibition, SVG/media rejection, voice `52` pH rejection, idempotent replay, Phase 2 legacy mash plan.

Not fully failure-injected in this candidate: Redis process kill, PostgreSQL crash/restore, two-tab browser E2E for every mutation, 24-hour orphan sweeper under load, production-class two-tab benchmark.
