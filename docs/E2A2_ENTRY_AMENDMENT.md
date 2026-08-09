# E2A-2 ENTRY AMENDMENT

**Status:** Accepted architecture amendment (pre–E2A-2)  
**Date:** 2026-08-09  
**Prerequisite:** E2A-1 Accepted  
**Governing ADRs:** ADR-004, ADR-005, ADR-006 (domain behavior unchanged)  
**Classification:** Documentation only — no E2A-2 production code

## Purpose

Canonical `brew_events` must exist **before** stage-transition implementation.  
`audit_events` is **not** a temporary substitute for E2A-2 Brew-Day domain events.

This amendment revises Epic 2A migration sequencing and locks `START_SESSION` atomicity. It does not change accepted domain semantics from ADR-004/005/006.

---

## 1. Updated migration sequence

| Migration | Contents | Status |
|-----------|----------|--------|
| `005_brew_day_plans_sessions` | `brew_plans`, `brew_sessions`, `brew_stage_occurrences`, `brew_actions`, `idempotency_records` | Implemented (E2A-1) |
| `006_brew_day_events_stage_machine` | `brew_events` + append-only indexes/constraints + E2A-1 canonical event backfill | Next (E2A-2 start) |
| `007_brew_day_measurements` | measurement definitions/requirements/records + observation/status histories | Future (post–E2A-2) |
| `008_brew_day_timers` | `brew_timers` | Future |
| `009_fermentation_handoffs` | fermentation handoff stub | Future |

**Supersedes** the E2A-0 packaging that placed `brew_events` with timers in former `007_brew_day_timers_events`.

---

## 2. ADR / package references changed

| Document | Change |
|----------|--------|
| [`EPIC_2A_E2A0_ARCHITECTURE_REVIEW_PACKAGE.md`](EPIC_2A_E2A0_ARCHITECTURE_REVIEW_PACKAGE.md) | Schema sketch, migration order, increment sequence updated to 005→009; START_SESSION locked detail |
| [`ADR-004-brew-day-domain-stage-machine.md`](ADR-004-brew-day-domain-stage-machine.md) | Amendment: `brew_events` ships in `006`; START_SESSION atomic definition locked; no `audit_events` substitute for E2A-2 |
| [`ADR-006-brew-timers-offline-idempotency.md`](ADR-006-brew-timers-offline-idempotency.md) | Timers remain future `008`; consequence text updated |
| [`EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md`](EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md) | Migration list + E2A-2 scope note |
| [`E2A1_BREW_EVENT_DEFERMENT.md`](E2A1_BREW_EVENT_DEFERMENT.md) | Superseded — backfill option **B** locked via this amendment |
| [`EPIC_2A_E2A1_IMPLEMENTATION_REVIEW_PACKAGE.md`](EPIC_2A_E2A1_IMPLEMENTATION_REVIEW_PACKAGE.md) | Cross-refs updated (`006` for events) |

Domain invariants and event semantics are unchanged.

---

## 3. Migration 006 schema sketch

### `brew_events` (append-only)

| Field | Notes |
|-------|-------|
| `id` | UUID PK |
| `brewery_id` | Ownership |
| `brew_plan_id` | Nullable for purely session-scoped events when applicable; required for plan-level events |
| `brew_session_id` | Nullable for plan-level events before session exists (`PLAN_CREATED`, `READINESS_ACKNOWLEDGED`) |
| `event_type` | e.g. `PLAN_CREATED`, `SESSION_STARTED`, `STAGE_ENTERED` |
| `actor_id` | Actor |
| `occurred_at` | **Server** authoritative timestamp |
| `client_occurred_at` | Optional provenance |
| `payload` | JSONB event details |
| `correlation_key` | Stable deterministic key for backfill / duplicate protection (see §6) |

No UPDATE/DELETE application API.

Migration 006 also:
- Creates indexes/constraints in §4  
- Runs deterministic E2A-1 backfill (§5–§6)  
- Does **not** implement stage-transition service code beyond schema readiness (production transition APIs belong to authorized E2A-2 implementation after this amendment)

---

## 4. BrewEvent indexes / constraints

| Constraint / index | Purpose |
|--------------------|---------|
| PK on `id` | Identity |
| Index `(brew_session_id, occurred_at)` | Session timeline reads |
| Index `(brew_plan_id, occurred_at)` | Plan-level event reads |
| Index `(brewery_id, occurred_at)` | Brewery audit slices |
| Index `(event_type, occurred_at)` | Type filters |
| **UNIQUE `(correlation_key)`** where `correlation_key IS NOT NULL` | Duplicate-safe backfill and retry guard |
| Optional CHECK | `brew_plan_id IS NOT NULL OR brew_session_id IS NOT NULL` |

Append-only: application must not expose update/delete.

---

## 5. E2A-1 backfill algorithm

When migration `006` introduces `brew_events`, for **each** existing `brew_plans` row:

1. **Evidence sources (prefer authoritative originals):**
   - BrewPlan durable columns: readiness status/summary/checks, acknowledgement flag/at/by/note, `created_by`, `created_at`
   - Matching append-only `audit_events` with `action ∈ {PLAN_CREATED, READINESS_ACKNOWLEDGED}` and `entity_type='BrewPlan'` / `entity_id=brew_plan.id`

2. **Emit `PLAN_CREATED`:**
   - `correlation_key = 'backfill:PLAN_CREATED:' || brew_plan.id`
   - `actor_id` = audit `actor_id` if present, else `brew_plans.created_by`
   - `occurred_at` = audit `occurred_at` if present, else `brew_plans.created_at`  
     (**never** migration execution time when an original timestamp exists)
   - `payload` includes plan id, recipe_version_id, readiness_status at create

3. **If acknowledgement occurred** (`brew_plans.readiness_acknowledged = true` **or** a matching `READINESS_ACKNOWLEDGED` audit row exists):
   - Emit `READINESS_ACKNOWLEDGED`
   - `correlation_key = 'backfill:READINESS_ACKNOWLEDGED:' || brew_plan.id`
   - Prefer audit actor/timestamp; else `readiness_acknowledged_by` / `readiness_acknowledged_at`
   - Payload includes readiness status, checks snapshot, acknowledgement note

4. Inserts use `ON CONFLICT (correlation_key) DO NOTHING` (or equivalent) so retry is duplicate-safe.

5. Do **not** delete or rewrite E2A-1 `audit_events` rows.

After migration 006, **new** Brew-Day domain mutations write canonical `brew_events` **directly** in the same transaction as the domain mutation (not via `audit_events` as the brew-day stream).

---

## 6. Backfill duplicate protection

| Guard | Rule |
|-------|------|
| Deterministic `correlation_key` | One key per `(event_type, brew_plan_id)` for E2A-1 backfill events |
| UNIQUE on `correlation_key` | Migration re-run cannot insert duplicates |
| Idempotent SQL | `INSERT … ON CONFLICT DO NOTHING` |
| Evidence-only timestamps | No “now()” fallback when plan/audit timestamp exists |

---

## 7. START_SESSION transition definition (LOCKED)

`START_SESSION` atomically performs **in one PostgreSQL transaction**:

| Effect | Value |
|--------|-------|
| BrewSession.status | `PLANNED` → `IN_PROGRESS` |
| PRE_BREW BrewStageOccurrence.status | `PENDING` → `ACTIVE` |
| BrewSession.current_stage_code | `PRE_BREW` |
| BrewSession.started_at | set (server) |
| PRE_BREW.entered_at | set (server) |
| BrewEvents appended | `SESSION_STARTED`, `STAGE_ENTERED` |
| BrewSession.version | increment **exactly once** |
| Idempotency | persist ledger result in the same transaction |

Requires `client_submission_id` and `expected_session_version` per ADR-006/004.  
If any write fails → **roll back the entire command**.

Illegal unless session is `PLANNED` (and PRE_BREW is `PENDING`). Exact replay returns the recorded response without a second version bump.

---

## 8. Measurement seed (U1) — deferred

U1 measurement seed catalog remains **unresolved** and is **not** a blocker for E2A-2.  
Resolve before measurement implementation (migration `007` / E2A-3).  
**Do not** implement measurement infrastructure in E2A-2.

---

## 9. Confirmation — no E2A-2 production code

This amendment updates documentation and ADR cross-references only.

- No Alembic `006` migration file created  
- No stage-transition / BrewEvent production service code started  
- No measurement, timer, or handoff implementation started  

---

E2A-2 ENTRY AMENDMENT COMPLETE — READY FOR AUTHORIZATION
