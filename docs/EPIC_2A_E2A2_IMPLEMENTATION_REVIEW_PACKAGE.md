# E2A-2 IMPLEMENTATION REVIEW PACKAGE

**Increment:** E2A-2 — BrewEvents + stage/session transitions  
**Date:** 2026-08-09  
**Governing:** ADR-004/005/006 + [`E2A2_ENTRY_AMENDMENT.md`](E2A2_ENTRY_AMENDMENT.md)

---

## 1. Commit SHA

`c0bc05680cbc4fb69028c0578674be714a1d2a84`

## 2. Working-tree status

Clean after E2A-2 commit (backend + docs). No E2A-3 code.

## 3. Files added/modified

### Added
- `backend/alembic/versions/006_brew_day_events_stage_machine.py`
- `backend/app/services/brew_events.py`
- `backend/app/services/brew_transitions.py`
- `backend/tests/test_brew_transitions.py`
- `backend/tests/test_migration_006.py`
- `backend/scripts/verify_e2a2_schema.py`
- `docs/EPIC_2A_E2A2_IMPLEMENTATION_REVIEW_PACKAGE.md` (this file)

### Modified
- `backend/app/db/models.py` — `BrewEvent`
- `backend/app/domain/enums.py` — transition/event enums
- `backend/app/schemas/brew_day.py` — transition + event schemas
- `backend/app/api/v1/brew_day.py` — transitions + events GET
- `backend/app/services/brew_plan.py` — live `brew_events` writes
- `backend/tests/test_brew_day_services.py`, `test_migration_005.py`
- `docs/EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md` — next-actions cleanup

## 4. Migration 006 details

- Revision `006`, `down_revision = "005"`
- Creates `brew_events`
- Deterministic E2A-1 backfill of `PLAN_CREATED` / `READINESS_ACKNOWLEDGED`
- Bumps `app_meta` to increment `6` / schema `006`
- Downgrade drops `brew_events` and restores `005` meta

## 5. BrewEvent schema / indexes / constraints

| Item | Detail |
|------|--------|
| Columns | id, brewery_id, brew_plan_id, brew_session_id, event_type, actor_id, occurred_at, client_occurred_at, payload, client_submission_id, correlation_key |
| CHECK | plan or session present |
| Indexes | session/plan/brewery/type + occurred_at |
| UNIQUE partial | `correlation_key` WHERE NOT NULL |
| API | append-only; no UPDATE/DELETE endpoints |

## 6. Backfill implementation and evidence

For each `brew_plans` row:

1. Insert `PLAN_CREATED` with `correlation_key = backfill:PLAN_CREATED:{plan_id}`
2. Prefer audit actor/timestamp; else plan `created_by` / `created_at`
3. If `readiness_acknowledged` or READINESS audit exists → insert `READINESS_ACKNOWLEDGED`
4. Prefer audit evidence; else plan ack columns
5. `ON CONFLICT (correlation_key) … DO NOTHING`
6. Historical `audit_events` left intact

## 7. Transition command matrix

| Command | From | Effect |
|---------|------|--------|
| START_SESSION | PLANNED | → IN_PROGRESS; PRE_BREW ACTIVE; SESSION_STARTED + STAGE_ENTERED |
| ADVANCE_STAGE | IN_PROGRESS | complete ACTIVE; activate next PENDING; STAGE_EXITED + STAGE_ENTERED |
| SKIP_STAGE | IN_PROGRESS | ACTIVE → SKIPPED (reason); E2A-3 measurement hook no-op; STAGE_SKIPPED (+ STAGE_ENTERED) |
| PAUSE_SESSION | IN_PROGRESS | → PAUSED; SESSION_PAUSED |
| RESUME_SESSION | PAUSED | → IN_PROGRESS; SESSION_RESUMED |
| ABORT_SESSION | PLANNED/IN_PROGRESS/PAUSED | → ABORTED (reason); SESSION_ABORTED; terminal |
| CLOSE_SESSION | IN_PROGRESS | → CLOSED; SESSION_CLOSED (measurement gate deferred to E2A-3) |

API: `POST /api/v1/brew-sessions/{id}/transitions`  
Events: `GET /api/v1/brew-sessions/{id}/events`

## 8. State-machine invariants

- Exactly one ACTIVE stage (partial unique index from 005 + service checks)
- Forward-only stage movement; no reopen
- Explicit skips only with reason
- No timer-driven transitions
- ABORTED terminal
- While PAUSED: ADVANCE/SKIP/CLOSE illegal; ABORT legal

## 9. OCC behavior

`expected_session_version` required. Mismatch → `409 CONCURRENCY_CONFLICT`. Version increments exactly once per successful new command; not on exact replay.

## 10. Idempotency behavior

Lookup first. Exact replay returns snapshot. Fingerprint/op conflict → `409 IDEMPOTENCY_CONFLICT`. Ledger row in same transaction.

## 11. Atomicity behavior

Domain + BrewEvents + version + idempotency in one transaction. BrewEvent failure aborts before commit (covered by test).

## 12. Illegal-transition results

Structured `409`/`422` with codes such as `ILLEGAL_TRANSITION`, `SESSION_PAUSED`, `SESSION_TERMINAL`, `CONCURRENCY_CONFLICT`, `IDEMPOTENCY_CONFLICT`, `SKIP_REASON_REQUIRED`, `ABORT_REASON_REQUIRED`, `ACTIVE_STAGE_INVARIANT`, `STAGE_ORDER_VIOLATION`.

## 13. Tests added

- `test_brew_transitions.py` — happy paths, pause/resume/abort/close, illegal, OCC, idempotency, atomicity, E2A-3 skip hook
- `test_migration_006.py` — schema/backfill SQL guards

## 14. Full test results

```text
102 passed, 1 skipped
```

## 15. Epic 1 regression results

Golden ADR-003 calculations and prior Epic 1 suite remain green. No formula changes.

## 16. E2A-1 regression results

BrewPlan/BrewSession/idempotency tests remain green. Plan create now also emits live `brew_events`.

## 17. Docker migration/persistence verification

- `005 → 006` upgrade OK  
- `006 → 005` downgrade OK  
- re-upgrade to `006 (head)` OK  
- Postgres restart preserves schema `006`, `brew_events` table, correlation unique index  

## 18. Known limitations

- No measurement tables/side effects (E2A-3); skip hook is intentional no-op
- CLOSE does not yet enforce REQUIRED measurement PENDING gate (E2A-3)
- No timers/reports/handoff/UI
- U1 seed catalog still deferred

## 19. Architecture deviations

None vs locked ADRs / entry amendment.

## 20. Explicit confirmation — no E2A-3 code

No measurement migrations, models, seed catalog, or measurement APIs were implemented.

---

E2A-2 COMPLETE — READY FOR ARCHITECTURE REVIEW
