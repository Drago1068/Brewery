# EPIC 2A E2A-0 CANONICAL ARCHITECTURE PACKAGE

**Product:** BrewingOS  
**Slice:** Epic 2A — Core Guided Brew Day  
**Increment:** E2A-0 (architecture / schema design only)  
**Date:** 2026-08-09  
**Epic 1 freeze:** `170fbdbe6d8cab37d565c7b8c073c4a4306c6fca`  
**Governing handoff:** [`EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md`](EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md)  
**Classification:** Documentation only — no Alembic migrations applied; no brew-day production domain code

---

## Locked Product Owner decisions (P1–P5)

| ID | Decision |
|----|----------|
| P1 | YELLOW/RED BrewPlan only with explicit acknowledgement (status, warnings/blockers, ack, actor, timestamp, optional note); no silent readiness conversion |
| P2 | BrewPlan requires ACTIVE or LOCKED RecipeVersion; DRAFT forbidden; no lock-on-plan |
| P3 | Confidence: HIGH / MEDIUM / LOW |
| P4 | CLOSED and ABORTED both supported; neither fabricates missing measurements |
| P5 | Inventory consume only via explicit confirmed action |

---

## 1. ADR status

| ADR | File | Status |
|-----|------|--------|
| **ADR-004** | [`ADR-004-brew-day-domain-stage-machine.md`](ADR-004-brew-day-domain-stage-machine.md) | **Accepted** — domain, stages, skip/close/handoff, OCC, atomicity, readiness events |
| **ADR-005** | [`ADR-005-measurement-integrity-provenance.md`](ADR-005-measurement-integrity-provenance.md) | **Accepted (final overwrite)** — history-first measurements |
| **ADR-006** | [`ADR-006-brew-timers-offline-idempotency.md`](ADR-006-brew-timers-offline-idempotency.md) | **Accepted (canonical)** — timers, idempotency ledger, offline minimum |

---

## 2. Core invariants

1. Epic 2 consumes immutable RecipeVersion baselines; does not rewrite Epic 1 historical truth.  
2. Timers never control process state.  
3. GET APIs are side-effect free (especially timers).  
4. Measurement observation/status history is append-only; records/statuses are projections (ADR-005).  
5. Every mutating command commits fully in one PostgreSQL transaction or rolls back entirely.  
6. Integer `BrewSession.version` is the OCC token; idempotency exact-replay is checked before stale-version rejection.  
7. `idempotency_records` is the replay authority and ships in migration `005`.  
8. `CLOSED → HANDED_OFF` only; ABORTED never hands off.  
9. Skip auto-MISS remaining REQUIRED in the same transaction; reject close while REQUIRED PENDING.  
10. `planned ≠ measured ≠ calculated ≠ estimated ≠ missing`.

---

## 3. Final schema sketch (not applied)

Additive UUID PKs; brewery ownership via `brewery_id` on plans (denormalized on sessions).

### Migration `005_brew_day_plans_sessions`

- **`brew_plans`** — brewery/recipe/version FKs (ACTIVE/LOCKED at create), recipe + calculation snapshots, readiness + ack metadata, timestamps/actor  
- **`brew_sessions`** — one session per plan in 2A; statuses `PLANNED` / `IN_PROGRESS` / `PAUSED` / `CLOSED` / `ABORTED` / `HANDED_OFF`; `current_stage_code`; **`version` INT** OCC token; abort reason  
- **`brew_stage_occurrences`** — ordered stages; `PENDING` / `ACTIVE` / `COMPLETED` / `SKIPPED`; at most one ACTIVE  
- **`brew_actions`** — checklist rows (`PENDING` / `DONE` / `SKIPPED`)  
- **`idempotency_records`** — append-only ledger (fields per ADR-006); UNIQUE `(scope_type, scope_id, client_submission_id)`

### Migration `006_brew_day_measurements`

- `measurement_definitions` (optional seed)  
- `measurement_requirements` (planned baseline + status projection)  
- `measurement_records` (projection only)  
- `measurement_observation_history` (append-only value truth)  
- `measurement_status_history` (append-only lifecycle truth)  

### Migration `007_brew_day_timers_events`

- **`brew_timers`** — authoritative `started_at`, `client_started_at`, `ends_at`, `elapsed_at`, `stopped_at`, `cancelled_at`; immutable label/target duration; status projection  
- **`brew_events`** — append-only audit stream  

### Migration `008_fermentation_handoffs`

- Stub handoff from **CLOSED** only; never from ABORTED  

---

## 4. Final API sketch

Base `/api/v1`. Mutating ops require `client_submission_id`. Session mutations require `expected_session_version` except exact idempotent replay.

| Method | Path | Notes |
|--------|------|-------|
| POST | `/recipe-versions/{id}/brew-plans` | ACTIVE/LOCKED; YELLOW/RED → `PLAN_CREATED` + `READINESS_ACKNOWLEDGED` |
| POST | `/brew-plans/{id}/sessions` | Start session |
| GET | `/brew-sessions/{id}` | Read |
| POST | `/brew-sessions/{id}/transitions` | ADVANCE / SKIP / PAUSE / RESUME / CLOSE / ABORT |
| GET | `/brew-sessions/{id}/requirements` | Measurement requirements |
| POST | `/brew-sessions/{id}/measurements` | Capture |
| POST | `/measurement-records/{id}/instrument-corrections` | History append |
| POST | `/measurement-records/{id}/revisions` | History append + reason |
| POST | `/measurement-requirements/{id}/miss` \| `/waive` | Status history |
| POST | `/brew-sessions/{id}/timers` | Start timer |
| POST | `/timers/{id}/stop` \| `/cancel` | Stop / cancel |
| POST | `/timers/{id}/observe-elapsed` | Persist elapsed once |
| GET | `/brew-sessions/{id}/timers` | Read-only; may return `computed_past_due` |
| GET | `/brew-sessions/{id}/events` | Audit |
| GET | `/brew-sessions/{id}/report` | Completeness / adherence / performance (separate) |
| POST | `/brew-sessions/{id}/fermentation-handoff` | CLOSED → HANDED_OFF only |

Idempotency: same id + fingerprint + operation → original response; mismatch → `409 IDEMPOTENCY_CONFLICT`.  
OCC: new command stale version → `409 CONCURRENCY_CONFLICT`; exact replay succeeds despite later version.

---

## 5. Event catalog

`PLAN_CREATED`, `READINESS_ACKNOWLEDGED`, `SESSION_STARTED`, `STAGE_ENTERED`, `STAGE_EXITED`, `STAGE_SKIPPED`, `ACTION_COMPLETED`, `MEASUREMENT_CAPTURED`, `MEASUREMENT_INSTRUMENT_CORRECTION`, `MEASUREMENT_USER_REVISION`, `MEASUREMENT_MISSED`, `MEASUREMENT_WAIVED`, `MEASUREMENT_INPUT_REJECTED` (operational only), `VALIDATION_WARNING`, `TIMER_STARTED`, `TIMER_STOPPED`, `TIMER_CANCELLED`, `TIMER_ELAPSED`, `SESSION_PAUSED`, `SESSION_RESUMED`, `SESSION_CLOSED`, `SESSION_ABORTED`, `FERMENTATION_HANDOFF_CREATED`, `INVENTORY_CONSUME_CONFIRMED`.

---

## 6. State transitions

**Session:** PLANNED → IN_PROGRESS; IN_PROGRESS ↔ PAUSED; IN_PROGRESS → CLOSED\* or ABORTED; CLOSED → HANDED_OFF†; ABORTED terminal (no handoff).

\* Close rejected while any REQUIRED measurement is PENDING (no auto-MISS).  
† Handoff only from CLOSED.

**Stage:** PENDING → ACTIVE → COMPLETED; PENDING|ACTIVE → SKIPPED (reason); skip auto-MISS remaining REQUIRED in same transaction; RECOMMENDED stay PENDING.

**Measurement requirement:** PENDING → CAPTURED | MISSED | WAIVED; no reopen in 2A.

---

## 7. Offline contract (Epic 2A minimum)

Client: generate `client_submission_id` before queue → store locally → UNSYNCED → retry on reconnect.  
Server: ledger check → exact replay or validate OCC/legality → atomic commit → authoritative resource/version.  
Client: SYNCED or SYNC FAILED / REJECTED.  
No CRDT, no multi-writer merge, no silent loss, no duplicate side effects.

---

## 8. Final migration order

1. `005_brew_day_plans_sessions` — plans, sessions, stages, actions, **idempotency_records**  
2. `006_brew_day_measurements` — definitions, requirements, records, observation_history, status_history  
3. `007_brew_day_timers_events` — timers, brew_events  
4. `008_fermentation_handoffs` — handoff stub  

Apply starting **E2A-1** only.

---

## 9. Final test plan

| Area | Tests |
|------|-------|
| Recipe / plan | DRAFT rejected; ACTIVE/LOCKED ok; snapshots stable; YELLOW/RED ack; GREEN without ack; distinct readiness event |
| Transitions | Legal ADVANCE; illegal while PAUSED/CLOSED; skip + REQUIRED→MISSED; pause/resume |
| Close / abort | Reject close with REQUIRED PENDING; close after miss/waive/capture; abort reason; no handoff from abort |
| Measurements | Capture; miss; waive; correction/revision history; unusual preserved; INPUT ERROR rejected |
| Timers | Survives restart; GET side-effect free; `computed_past_due`; observe-elapsed once; concurrent observe → one event; never advances stage |
| Idempotency / OCC | Exact replay; no double version bump; body/op conflict 409; stale version 409; replay despite later version |
| Atomicity | BrewEvent failure rolls back; idempotency-record failure rolls back |
| Offline | Delayed retry duplicate-safe |
| Reports | Planned-vs-actual; completeness; adherence; performance separate |
| Handoff | CLOSED only |
| Epic 1 | Golden calculations unchanged |

---

## 10. Increments E2A-1 … E2A-6

| Inc | Scope |
|-----|--------|
| E2A-1 | Migration 005 + plan/session APIs + idempotency ledger |
| E2A-2 | Stage transitions + brew_events |
| E2A-3 | Migration 006 + measurement capture/history/miss/waive |
| E2A-4 | Migration 007 timers + observe-elapsed; read-only GET |
| E2A-5 | Reports; close/abort hardening; migration 008 handoff |
| E2A-6 | Offline replay hardening/tests; journey test; guided UI shell |

---

## 11. Remaining unresolved decisions

| ID | Topic | Notes |
|----|-------|-------|
| U1 | Exact REQUIRED/RECOMMENDED measurement set per stage | Seed in E2A-3 |
| U5 | Plan-level event `brew_plan_id` / null session conventions | Prefer always store plan_id; session_id when present |
| U7 | Explicit inventory consume endpoint path/shape | Required by P5; design in E2A-1/5 API pass |

---

## 12. Confirmations

- No Epic 3 fermentation functionality implemented (handoff stub designed only).  
- No production Brew-Day domain code implemented in E2A-0.  
- No Alembic `005+` migrations applied.

---

# E2A-0 CANONICAL ARCHITECTURE PACKAGE COMPLETE

| Item | Status |
|------|--------|
| ADR-004 | Accepted |
| ADR-005 | Accepted (final overwrite) |
| ADR-006 | Accepted (canonical presentation) |
| Final schema sketch | §3 |
| Final API sketch | §4 |
| Final migration order | `005` → `006` → `007` → `008` (idempotency in `005`) |
| Final test plan | §9 |
| Remaining unresolved | U1, U5, U7 |

**E2A-0 READY FOR FINAL ARCHITECTURE ACCEPTANCE**
