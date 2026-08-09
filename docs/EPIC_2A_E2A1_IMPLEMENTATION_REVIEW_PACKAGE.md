# E2A-1 IMPLEMENTATION REVIEW PACKAGE

**Increment:** E2A-1 — BrewPlan / BrewSession foundation  
**Date:** 2026-08-09  
**Governing ADRs:** ADR-004, ADR-005, ADR-006 (Accepted / Locked)  
**BrewEvent deferment note:** [`E2A1_BREW_EVENT_DEFERMENT.md`](E2A1_BREW_EVENT_DEFERMENT.md)

---

## 1. Commit SHA

_(filled at commit time)_

## 2. Working-tree status

Clean after E2A-1 commit (docs + backend only; no E2A-2 code).

## 3. Files added/modified

### Added
- `backend/alembic/versions/005_brew_day_plans_sessions.py`
- `backend/app/domain/brew_day.py`
- `backend/app/schemas/brew_day.py`
- `backend/app/services/idempotency.py`
- `backend/app/services/brew_plan.py`
- `backend/app/services/brew_session.py`
- `backend/app/api/v1/brew_day.py`
- `backend/tests/test_brew_day_api.py`
- `backend/tests/test_brew_day_services.py`
- `backend/tests/test_migration_005.py`
- `backend/scripts/verify_e2a1_schema.py`
- `docs/E2A1_BREW_EVENT_DEFERMENT.md`
- `docs/EPIC_2A_E2A1_IMPLEMENTATION_REVIEW_PACKAGE.md` (this file)

### Modified
- `backend/app/db/models.py` — BrewPlan, BrewSession, BrewStageOccurrence, BrewAction, IdempotencyRecord
- `backend/app/domain/enums.py` — brew-day enums + audit actions
- `backend/app/api/v1/router.py` — register brew-day routes

## 4. Migration 005

`005_brew_day_plans_sessions` (`down_revision = "004"`)

Creates:
- `brew_plans`
- `brew_sessions`
- `brew_stage_occurrences`
- `brew_actions`
- `idempotency_records`

Bumps `app_meta.increment=5`, `schema_version=005`.  
Downgrade drops E2A-1 tables and restores `004` meta.

Verified live: `004 → 005` upgrade, `005 → 004` downgrade, re-upgrade to `005 (head)`.

## 5. Database constraints

| Constraint | Purpose |
|------------|---------|
| `uq_brew_sessions_brew_plan_id` | One BrewSession per BrewPlan (Epic 2A) |
| `uq_brew_stage_session_code` | Unique stage code per session |
| `uq_brew_stage_session_sequence` | Unique sequence per session |
| `uq_brew_stage_one_active_per_session` | Partial unique index: at most one `ACTIVE` stage |
| `uq_idempotency_scope_submission` | UNIQUE `(scope_type, scope_id, client_submission_id)` |
| FKs | Plan → brewery/recipe/version; session → plan; stages → session; actions → stage |

## 6. BrewPlan model

Immutable baseline from ACTIVE/LOCKED RecipeVersion:
- Identity: `id`, `brewery_id`, `recipe_id`, `recipe_version_id`, `status=CREATED`
- Snapshots: batch size/unit, efficiency, equipment ref + snapshot, recipe/component snapshot, planned calculation snapshot
- Readiness: status, summary, checks snapshot
- Acknowledgement columns (YELLOW/RED): acknowledged flag/at/by/note
- `created_by`, `created_at`

## 7. BrewSession model

- `brew_plan_id` unique; denormalized `brewery_id`
- `status` initial `PLANNED`
- `current_stage_code` null until START_SESSION (E2A-2)
- integer `version` DEFAULT 1 (OCC)
- `started_at` / `closed_at` / `abort_reason` nullable (unused in E2A-1 execution)

## 8. StageOccurrence model

Nine ordered ADR-004 stages, all `PENDING` at session create.  
Fields: session, stage_code, sequence_no, status, entered_at, exited_at, skip_reason.

## 9. BrewAction foundation

Lightweight checklist table (`code`, `label`, `status`, `sort_order`, …).  
No procedural templates seeded in E2A-1.

## 10. IdempotencyRecord model

Append-only ADR-006 ledger with all required fields. No UPDATE/DELETE API.

## 11. BrewPlan API

`POST /api/v1/recipe-versions/{id}/brew-plans`

- Requires `client_submission_id`
- Rejects DRAFT; allows ACTIVE/LOCKED; no lock-on-plan
- Evaluates Ready-to-Brew; GREEN without ack; YELLOW/RED require explicit acknowledgement
- Never converts readiness to GREEN
- Atomic with idempotency record + durable ack audit (see §14 / deferment note)

## 12. BrewSession API

`POST /api/v1/brew-plans/{id}/sessions` — one session, nine PENDING stages, status PLANNED, idempotent  
`GET /api/v1/brew-sessions/{id}` — side-effect free; returns session, plan id, version, current stage, stage summary

## 13. Snapshot behavior

Plan stores deep JSON copies of recipe/components, equipment, and calculation results including `formula_id`, `formula_version`, and `value_kind`. Later library/recipe edits cannot rewrite the plan baseline.

## 14. Readiness acknowledgement behavior

YELLOW/RED require `readiness_acknowledgement.acknowledged=true`.  
Stored status remains YELLOW/RED.  
Distinct durable facts:
1. Immutable BrewPlan acknowledgement columns  
2. Separate `audit_events` rows: `PLAN_CREATED` and `READINESS_ACKNOWLEDGED`  

Canonical `brew_events` deferred to migration 007 — see [`E2A1_BREW_EVENT_DEFERMENT.md`](E2A1_BREW_EVENT_DEFERMENT.md).

## 15. Idempotency behavior

Lookup by `(scope_type, scope_id, client_submission_id)` before domain work.  
Exact fingerprint/operation → original response.  
Different fingerprint/operation → `409 IDEMPOTENCY_CONFLICT`.  
Ledger row commits in the same transaction as the domain resource.

## 16. Tests added

- `test_brew_day_api.py` — domain snapshot/API smoke
- `test_brew_day_services.py` — DRAFT reject, YELLOW/RED ack, GREEN, status preservation, idempotent replay/conflict
- `test_migration_005.py` — migration structure / order guards

## 17. Full test results

```text
85 passed, 1 skipped
```

(Skipped: optional live DB pytest marker when `DATABASE_URL` unset; docker verification covers live migration.)

## 18. Epic 1 regression results

All pre-existing Epic 1 tests remain green, including ADR-003 golden calculation tests. No formula changes.

## 19. Docker/persistence verification

- Postgres volume: `./data/postgres` (Compose default; NAS-backed via `BREWINGOS_POSTGRES_DATA` when configured)
- `alembic upgrade head` → `005 (head)`
- `alembic downgrade 004` → `004`; re-upgrade → `005`
- Postgres container restart preserves schema `005` and all five E2A-1 tables + active-stage partial index

## 20. Known limitations

- No stage transitions, measurements, timers, reports, handoff, or offline UI (E2A-2+)
- `brew_events` not yet persisted (migration 007)
- PRE_BREW not activated at session create (PLANNED; start is E2A-2)
- No Redis / CRDT (by design)

## 21. Architecture deviations

None against ADR decisions. Migration-order packaging of BrewEvents reconciled via durable plan columns + append-only `audit_events` (documented, not throwaway).

## 22. Decisions required before E2A-2

1. BrewEvent backfill strategy for E2A-1 plans (options A/B/C in `E2A1_BREW_EVENT_DEFERMENT.md`)
2. Confirm START_SESSION activates PRE_BREW and moves session `PLANNED → IN_PROGRESS`
3. U1 measurement seed catalog (still unresolved from E2A-0)

---

**E2A-1 COMPLETE — READY FOR ARCHITECTURE REVIEW**
