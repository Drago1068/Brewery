# E2A-4 IMPLEMENTATION REVIEW PACKAGE

**Increment:** E2A-4 — Durable Brew-Day Timers  
**Date:** 2026-08-09  
**Governing:** ADR-006 (+ ADR-004 process-authority boundary)

---

## 1. Commit SHA

`c48fcf22c1bc4d08d84b62ca5f17a01c68fc11a2`

## 2. Working-tree status

Clean after E2A-4 commit. No E2A-5 report/handoff code.

## 3. Files added/modified

### Added
- `backend/alembic/versions/008_brew_day_timers.py`
- `backend/app/domain/timer.py`
- `backend/app/services/brew_timers.py`
- `backend/tests/test_brew_timers.py`
- `backend/tests/test_migration_008.py`
- `backend/scripts/verify_e2a4_schema.py`
- `backend/scripts/verify_e2a4_persist.py`
- `docs/EPIC_2A_E2A4_IMPLEMENTATION_REVIEW_PACKAGE.md`

### Modified
- `backend/app/db/models.py` — `BrewTimer`
- `backend/app/domain/enums.py` — `BrewTimerStatus`, `TIMER_*` event types
- `backend/app/schemas/brew_day.py` — timer request/read schemas
- `backend/app/api/v1/brew_day.py` — start/stop/cancel/observe-elapsed + GET timers
- Migration guard tests for 005/006/007 (allow 008; forbid 009)
- `backend/tests/test_brew_day_api.py` — GET timers route

## 4. Migration 008 details

- Revision `008_brew_day_timers`, `down_revision = "007"`
- Creates `brew_timers` only
- `app_meta` → increment `8` / schema `008`
- Downgrade drops `brew_timers` and restores increment `7` / schema `007`
- Migrations 005–007 unmodified
- No Redis / Celery / workers

## 5. BrewTimer schema

| Column | Role |
|--------|------|
| `id` | PK |
| `brewery_id` | Ownership |
| `brew_session_id` | Session ownership |
| `stage_occurrence_id` | Optional stage association |
| `label` | Immutable after create |
| `target_duration_seconds` | Optional; positive if set; immutable |
| `started_at` | Server-authoritative; immutable |
| `client_started_at` | Client provenance; immutable |
| `ends_at` | `started_at + duration` when duration present; immutable |
| `elapsed_at` / `stopped_at` / `cancelled_at` | Set at most once |
| `status` | Rebuildable projection |
| `start_client_submission_id` | Start provenance |
| `created_by` / `created_at` | Provenance |

Check: `target_duration_seconds IS NULL OR target_duration_seconds > 0`.

## 6. Timer authority rules

- Authoritative truth = timestamps, not `status`
- Projection precedence: `CANCELLED` > `STOPPED` > `ELAPSED` > `RUNNING`
- Configuration + `started_at` / `client_started_at` / `ends_at` never silently rewritten
- Timers never control session/stage/measurement/inventory/handoff state

## 7. Start behavior

`POST /api/v1/brew-sessions/{id}/timers`

Requires `client_submission_id`, `expected_session_version`, `label`; optional duration, stage, `client_started_at`.

On first apply: validate session/stage → create timer → server `started_at` → derive immutable `ends_at` → `TIMER_STARTED` → version +1 → idempotency → commit.

Exact replay returns original without new timer/version.

## 8. Stop behavior

`POST /api/v1/timers/{id}/stop`

Legal from `RUNNING` or `ELAPSED`. Sets `stopped_at` once, rebuilds projection, `TIMER_STOPPED`, version +1. No stage/measurement/inventory effects.

## 9. Cancel behavior

`POST /api/v1/timers/{id}/cancel`

Legal from `RUNNING` only. Sets `cancelled_at` once, `TIMER_CANCELLED`, version +1. Rejects stop→cancel and elapsed→cancel.

## 10. Observe-elapsed behavior

`POST /api/v1/timers/{id}/observe-elapsed`

Legal only when `ends_at` exists and server now ≥ `ends_at`, and not stopped/cancelled/already elapsed.

Sets `elapsed_at` once, exactly one `TIMER_ELAPSED`, version +1. Does **not** advance/skip/complete stages, miss/waive measurements, close session, consume inventory, or create handoff.

## 11. GET read-only verification

`GET /api/v1/brew-sessions/{id}/timers`

- No `elapsed_at` write
- No status DB mutation
- No BrewEvent / idempotency / version change
- May return `computed_past_due=true` when past due and no terminal timestamps
- Tests assert commit/add not called on list

## 12. Stage/session interaction

- Optional stage must belong to the same session
- Stage advance/skip does not auto-stop/cancel/elapsed timers
- Running timers continue across `PAUSE` (wall-clock; `ends_at` not recalculated)
- Explicit legality: timer mutations rejected after session `CLOSED` / `ABORTED` / `HANDED_OFF` (`TIMER_SESSION_TERMINAL`)
- No implicit rewrite of historical timer timestamps on abort/close

## 13. OCC behavior

ADR-006 order: idempotency lookup → exact replay → fingerprint conflict → `expected_session_version` → mutate → version +1 once → BrewEvent + idempotency in same transaction.

## 14. Idempotency behavior

Required for start/stop/cancel/observe-elapsed. Exact replay never duplicates timer, timestamps, events, version increments, or ledger rows.

## 15. Atomicity verification

Failure-injection tests:
- BrewEvent failure on start → no commit; version unchanged
- Idempotency write failure on observe-elapsed → no commit

## 16. Restart durability

- No in-memory countdown dependency
- State derives from persisted timestamps after restart
- Docker: upgrade 007→008, downgrade 008→007, re-upgrade 007→008
- Postgres restart: `schema_version=008`, `increment=8`, `brew_timers` intact

## 17. Error/validation behavior

| Condition | Code |
|-----------|------|
| Blank label | 422 `TIMER_INVALID_LABEL` |
| ≤0 duration | 422 `TIMER_INVALID_DURATION` |
| Missing stage | 422 `TIMER_STAGE_NOT_FOUND` |
| Foreign stage | 409 `TIMER_STAGE_SESSION_MISMATCH` |
| Stale OCC | 409 `CONCURRENCY_CONFLICT` |
| Idempotency mismatch | 409 `IDEMPOTENCY_CONFLICT` |
| Observe before end | 409 `TIMER_NOT_PAST_DUE` |
| No target end | 409 `TIMER_NO_TARGET_END` |
| Illegal terminal mutations | 409 `TIMER_ALREADY_*` / `TIMER_*_ILLEGAL` |
| Session terminal | 409 `TIMER_SESSION_TERMINAL` |

## 18. Tests added

- `tests/test_brew_timers.py` — domain, start, GET, observe, stop, cancel, terminal, OCC, idempotency, atomicity, pause wall-clock
- `tests/test_migration_008.py`
- Updated 005/006/007 migration guards
- API GET timers route test

## 19. Full test results

```
143 passed, 1 skipped
```

## 20. Epic 1 regression results

```
tests/test_calculations_golden.py — 11 passed
```

No Epic 1 formula changes.

## 21. E2A-1/2/3 regression results

```
E2A-1/2/3 + E2A-4 timer/migration tests — 81 passed, 1 skipped
```

No measurement history semantics changed. No state-machine transition became timer-driven.

## 22. Docker migration/persistence verification

| Step | Result |
|------|--------|
| Rebuild backend image | OK |
| `alembic upgrade head` (007→008) | OK |
| `verify_e2a4_schema.py` | schema 008, increment 8, `brew_timers` present |
| `alembic downgrade 007` | OK (timers removed; meta 007) |
| Re-upgrade to 008 | OK |
| Postgres restart | schema/timers/meta survived |

## 23. Known limitations

- No live brew-session seed in docker DB for row-level restart insert in this environment; durability proven via timestamp authority + schema survival after Postgres restart
- Frontend countdown UX is out of scope (E2A-6)
- Offline replay hardening remains E2A-6
- No background observe-elapsed worker (by design)

## 24. Architecture deviations, if any

None. ADR-006 followed for timestamp authority, GET read-only, explicit observe-elapsed, OCC/idempotency order, and timer non-authority over process state.

## 25. Explicit confirmation no E2A-5 code was implemented

Confirmed: no brew-day report/audit service, no fermentation handoff table/API, no E2A-6 UI, no Redis/background jobs, no Epic 2B/3 work.

---

E2A-4 COMPLETE — READY FOR ARCHITECTURE REVIEW
