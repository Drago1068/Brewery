# EPIC 2A E2A-0 CANONICAL ARCHITECTURE PACKAGE

## 1. Metadata / Classification

| Field | Value |
|-------|-------|
| Product | BrewingOS |
| Slice | Epic 2A — Core Guided Brew Day |
| Increment | E2A-0 (architecture / schema design only) |
| Date | 2026-08-09 |
| Epic 1 freeze | `170fbdbe6d8cab37d565c7b8c073c4a4306c6fca` |
| Governing handoff | [`EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md`](EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md) |
| Classification | Documentation only — no Alembic migrations applied; no brew-day production domain code |

### Locked Product Owner decisions (P1–P5)

| ID | Decision |
|----|----------|
| P1 | YELLOW/RED BrewPlan only with explicit acknowledgement; no silent readiness conversion |
| P2 | BrewPlan requires ACTIVE or LOCKED RecipeVersion; DRAFT forbidden; no lock-on-plan |
| P3 | Confidence HIGH / MEDIUM / LOW |
| P4 | CLOSED and ABORTED both supported; neither fabricates missing measurements |
| P5 | Inventory consume only via explicit confirmed action |

---

## 2. Accepted ADRs

| ADR | File | Status |
|-----|------|--------|
| ADR-004 | [`ADR-004-brew-day-domain-stage-machine.md`](ADR-004-brew-day-domain-stage-machine.md) | Accepted |
| ADR-005 | [`ADR-005-measurement-integrity-provenance.md`](ADR-005-measurement-integrity-provenance.md) | Accepted |
| ADR-006 | [`ADR-006-brew-timers-offline-idempotency.md`](ADR-006-brew-timers-offline-idempotency.md) | Accepted |

Architecture decisions in these ADRs are locked. This package does not redesign them.

---

## 3. Core Invariants

1. Epic 1 freeze remains authoritative.  
2. Epic 2 consumes immutable RecipeVersion baselines.  
3. BrewPlan accepts ACTIVE or LOCKED RecipeVersion only; DRAFT cannot create a BrewPlan.  
4. YELLOW/RED readiness requires explicit acknowledgement.  
5. `PLAN_CREATED` and `READINESS_ACKNOWLEDGED` are separate events.  
6. BrewSession uses integer `version` OCC.  
7. Exact idempotent replay is checked before stale-version rejection.  
8. `idempotency_records` ships in migration `005`.  
9. Every mutating command is atomic (one PostgreSQL transaction or full rollback).  
10. Measurement observation/status histories are append-only; `MeasurementRecord` and requirement status are projections.  
11. Timers never control process state.  
12. Timer GET is read-only; elapsed persistence requires explicit observe-elapsed.  
13. Skip auto-MISSes remaining REQUIRED measurements in the same transaction.  
14. Close rejects while REQUIRED measurements remain PENDING.  
15. ABORTED never creates fermentation handoff; CLOSED may explicitly transition to HANDED_OFF.  
16. Planned, estimated, calculated, measured, missing, and invalid remain distinct.  
17. No Redis in Epic 2A.  
18. No CRDT in Epic 2A.

---

## 4. Final Schema Sketch

Additive UUID PKs. Brewery ownership via `brewery_id` on plans (denormalized on sessions).

**Migration sequencing amendment (pre–E2A-2):** canonical `brew_events` ships in `006` before stage transitions. See [`E2A2_ENTRY_AMENDMENT.md`](E2A2_ENTRY_AMENDMENT.md). Domain behavior unchanged.

### 005_brew_day_plans_sessions

| Table | Purpose |
|-------|---------|
| `brew_plans` | Plan from immutable RecipeVersion; recipe + calculation snapshots; readiness + acknowledgement metadata |
| `brew_sessions` | One session per plan in 2A; integer `version` OCC; status including CLOSED / ABORTED / HANDED_OFF |
| `brew_stage_occurrences` | Ordered stage instances; at most one ACTIVE |
| `brew_actions` | Optional checklist steps on a stage |
| `idempotency_records` | Append-only replay ledger; UNIQUE `(scope_type, scope_id, client_submission_id)` |

**Status:** Implemented in E2A-1.

### 006_brew_day_events_stage_machine

| Table | Purpose |
|-------|---------|
| `brew_events` | Append-only brew-day domain event stream (plan- and session-scoped); required before stage transitions |

Includes indexes/constraints for append-only history and deterministic E2A-1 backfill of `PLAN_CREATED` / `READINESS_ACKNOWLEDGED`.  
`audit_events` is **not** a substitute for this stream in E2A-2+.

### 007_brew_day_measurements

| Table | Purpose |
|-------|---------|
| `measurement_definitions` | Optional seed/catalog metadata |
| `measurement_requirements` | Planned/estimated baseline + current status projection |
| `measurement_records` | Current observation projection only |
| `measurement_observation_history` | Append-only scientific value history |
| `measurement_status_history` | Append-only lifecycle history |

### 008_brew_day_timers

| Table | Purpose |
|-------|---------|
| `brew_timers` | Timestamp-authoritative timers; status is projection; immutable label/target after create |

### 009_fermentation_handoffs

| Table | Purpose |
|-------|---------|
| `fermentation_handoffs` | Epic 3 stub from CLOSED sessions only |

---

## 5. Final API Sketch

Base: `/api/v1`. Mutating operations require `client_submission_id`. Session mutations require `expected_session_version` except exact idempotent replay.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/recipe-versions/{id}/brew-plans` | BrewPlan creation |
| POST | `/brew-plans/{id}/sessions` | BrewSession creation/start |
| GET | `/brew-sessions/{id}` | BrewSession read |
| POST | `/brew-sessions/{id}/transitions` | Stage/session transitions |
| GET | `/brew-sessions/{id}/requirements` | Measurement requirements |
| POST | `/brew-sessions/{id}/measurements` | Measurement capture |
| POST | `/measurement-records/{id}/instrument-corrections` | Instrument corrections |
| POST | `/measurement-records/{id}/revisions` | User revisions |
| POST | `/measurement-requirements/{id}/miss` | Miss |
| POST | `/measurement-requirements/{id}/waive` | Waive |
| POST | `/brew-sessions/{id}/timers` | Timer start |
| POST | `/timers/{id}/stop` | Timer stop |
| POST | `/timers/{id}/cancel` | Timer cancel |
| POST | `/timers/{id}/observe-elapsed` | Persist elapsed once |
| GET | `/brew-sessions/{id}/timers` | Read-only timer GET (`computed_past_due` allowed) |
| GET | `/brew-sessions/{id}/events` | Events |
| GET | `/brew-sessions/{id}/report` | Completeness / adherence / performance (separate axes) |
| POST | `/brew-sessions/{id}/fermentation-handoff` | Fermentation handoff (CLOSED → HANDED_OFF only) |

Exact replay (same id + fingerprint + operation): original response; no duplicate side effects.  
Same id, different body/operation: `409 IDEMPOTENCY_CONFLICT`.  
New command with stale version: `409 CONCURRENCY_CONFLICT`.

---

## 6. Event Catalog

| Event |
|-------|
| `PLAN_CREATED` |
| `READINESS_ACKNOWLEDGED` |
| `SESSION_STARTED` |
| `STAGE_ENTERED` |
| `STAGE_EXITED` |
| `STAGE_SKIPPED` |
| `ACTION_COMPLETED` |
| `MEASUREMENT_CAPTURED` |
| `MEASUREMENT_INSTRUMENT_CORRECTION` |
| `MEASUREMENT_USER_REVISION` |
| `MEASUREMENT_MISSED` |
| `MEASUREMENT_WAIVED` |
| `MEASUREMENT_INPUT_REJECTED` |
| `VALIDATION_WARNING` |
| `TIMER_STARTED` |
| `TIMER_STOPPED` |
| `TIMER_CANCELLED` |
| `TIMER_ELAPSED` |
| `SESSION_PAUSED` |
| `SESSION_RESUMED` |
| `SESSION_CLOSED` |
| `SESSION_ABORTED` |
| `FERMENTATION_HANDOFF_CREATED` |
| `INVENTORY_CONSUME_CONFIRMED` |

`MEASUREMENT_INPUT_REJECTED` is operational/diagnostic only (ADR-005); it is not scientific observation history.

---

## 7. State Transitions

### Session

- `PLANNED` → `IN_PROGRESS` via locked `START_SESSION` (see below)  
- `IN_PROGRESS` ↔ `PAUSED`  
- `IN_PROGRESS` → `CLOSED`  
- `IN_PROGRESS` → `ABORTED`  
- `CLOSED` → `HANDED_OFF`  

`ABORTED` is terminal. Close is rejected while any REQUIRED measurement remains `PENDING`.

#### START_SESSION (locked)

Atomic one-transaction command:

- Session: `PLANNED` → `IN_PROGRESS`; set `started_at`; `current_stage_code = PRE_BREW`  
- PRE_BREW stage: `PENDING` → `ACTIVE`; set `entered_at`  
- Append `SESSION_STARTED` and `STAGE_ENTERED` to `brew_events`  
- Increment `BrewSession.version` exactly once  
- Persist idempotency result in the same transaction  

Any write failure rolls back the entire command.

### Stage

- `PENDING` → `ACTIVE` → `COMPLETED`  
- `PENDING` / `ACTIVE` → `SKIPPED` (explicit)  

Skip auto-MISSes remaining REQUIRED measurements in the same transaction.

### Measurement Requirement

- `PENDING` → `CAPTURED`  
- `PENDING` → `MISSED`  
- `PENDING` → `WAIVED`  

No reopen in Epic 2A.

---

## 8. Offline Contract

Client: generate `client_submission_id` before queueing; store action locally; show UNSYNCED; retry after reconnect.

Server: check idempotency ledger; return existing response for exact replay; validate concurrency/legality for new commands; commit atomically; return authoritative resource/version.

Client then: SYNCED or SYNC FAILED / REJECTED.

No CRDT. No automatic multi-writer merge. No silent loss. No duplicate side effects. Server state wins.

---

## 9. Final Test Plan

| Category | Coverage |
|----------|----------|
| Recipe / BrewPlan | DRAFT rejected; ACTIVE/LOCKED accepted; snapshots stable; YELLOW/RED acknowledgement; GREEN without ack; separate `PLAN_CREATED` and `READINESS_ACKNOWLEDGED` |
| Session / transitions | Legal ADVANCE path; illegal while PAUSED/CLOSED; skip with REQUIRED→MISSED; pause/resume |
| Close / abort / handoff | Close rejected with REQUIRED PENDING; close after miss/waive/capture; abort with reason; no handoff from ABORTED; handoff from CLOSED only |
| Measurements / history | Capture; miss; waive; instrument correction history; user revision history |
| Validation | INPUT ERROR rejected without observation history; UNUSUAL/DOMAIN_CONCERN preserved with warnings |
| Timers | Survives restart; GET side-effect free; `computed_past_due`; observe-elapsed once; concurrent observe → one event; elapsed/stop/cancel never advance stage |
| Idempotency / OCC | Exact replay; no double version bump; body/op conflict 409; stale version 409; replay despite later version |
| Atomicity | Forced BrewEvent failure rolls back; forced idempotency-record failure rolls back |
| Offline replay | Delayed retry duplicate-safe |
| Epic 1 regression | Golden calculations and existing API suite unchanged |
| End-to-end Brew Day journey | RecipeVersion → BrewPlan → BrewSession → stages → measurements → close → handoff |

---

## 10. Migration Order

1. `005_brew_day_plans_sessions` (E2A-1 — done)  
2. `006_brew_day_events_stage_machine` (E2A-2 — `brew_events` + backfill before transitions)  
3. `007_brew_day_measurements`  
4. `008_brew_day_timers`  
5. `009_fermentation_handoffs`  

Amended pre–E2A-2: [`E2A2_ENTRY_AMENDMENT.md`](E2A2_ENTRY_AMENDMENT.md).

---

## 11. Increment Delivery Sequence

| Increment | Scope |
|-----------|--------|
| E2A-1 | Migration 005 + BrewPlan/BrewSession APIs + idempotency ledger |
| E2A-2 | Migration 006 (`brew_events` + E2A-1 backfill) + stage transitions including locked START_SESSION |
| E2A-3 | Migration 007 + measurement capture/history/miss/waive |
| E2A-4 | Migration 008 timers + observe-elapsed; read-only GET |
| E2A-5 | Reports; close/abort hardening; migration 009 handoff |
| E2A-6 | Offline replay hardening/tests; journey test; guided UI shell |

U1 measurement seed catalog is deferred until before measurement implementation (not an E2A-2 blocker).

---

## 12. E2A-0 Acceptance Statement

E2A-0 delivers accepted ADR-004, ADR-005, and ADR-006 plus this canonical architecture package.

No brew-day production domain code was implemented.  
No Alembic `005+` migrations were created or applied.  
Epic 3 fermentation functionality was not implemented (handoff stub designed only).

Unresolved seed/API-shape items only: exact per-stage measurement catalog (U1); plan-event id conventions (U5); inventory consume endpoint shape (U7).

**E2A-0 READY FOR FINAL ACCEPTANCE — REQUEST AUTHORIZATION FOR E2A-1**
