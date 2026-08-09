# ADR-006 — Brew Timers & Offline Idempotency

## Metadata

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Epic 2A requires durable brew-day timers and offline-safe mutating APIs without Redis and without letting timers drive process state (ADR-004).  
**Amendment:** 2026-08-09 — canonical timer, idempotency, OCC, and offline contract locked for E2A-0; `idempotency_records` ships in migration `005`.

## Decision

Timers are timestamp-authoritative; `status` is a rebuildable projection.  
GET timer APIs are side-effect free.  
Elapsed persistence is an explicit observe command only.  
Idempotent retries are governed by an append-only `idempotency_records` ledger with request fingerprints.  
Every mutating command commits atomically with ADR-004 optimistic concurrency.  
Timers never control process state.

## A. Timer Authority

Authoritative timer fields (one-way after set; never cleared or rewritten in Epic 2A):

| Field | Role |
|-------|------|
| `started_at` | Server start time (immutable after create) |
| `client_started_at` | Optional client provenance (immutable after create) |
| `ends_at` | `started_at + target_duration_seconds` when target present (immutable after create) |
| `elapsed_at` | Set at most once by observe-elapsed |
| `stopped_at` | Set at most once by stop |
| `cancelled_at` | Set at most once by cancel |

`status` is a rebuildable projection/cache derived from those timestamps.

Timer configuration (`label`, `target_duration_seconds`, stage linkage) is immutable after creation in Epic 2A.

No Redis in Epic 2A.

## B. GET Is Read-Only

`GET /brew-sessions/{id}/timers` must never persist:

- `elapsed_at`  
- `TIMER_ELAPSED`  
- status mutation  
- BrewEvent  
- `BrewSession.version` change  

It may return `computed_past_due=true` when `ends_at` is present, server now ≥ `ends_at`, and `elapsed_at` / `stopped_at` / `cancelled_at` are still null.

## C. Explicit Elapsed Observation

Persist elapsed state only via:

`POST /timers/{id}/observe-elapsed`

This command:

- requires `client_submission_id`  
- requires `expected_session_version` where session OCC applies  
- sets `elapsed_at` at most once  
- emits `TIMER_ELAPSED` at most once  
- never advances, completes, or skips a stage  
- never closes a session or creates a fermentation handoff  
- may update `BrewSession.version` only as normal OCC bookkeeping on first successful apply  

Concurrent or repeated observe-elapsed resolves to one authoritative `elapsed_at` and one `TIMER_ELAPSED` event.

## D. Timer Commands

| Command | Effect |
|---------|--------|
| Start | Insert timer; RUNNING projection |
| Stop | Set `stopped_at` once from RUNNING or ELAPSED |
| Cancel | Set `cancelled_at` once from RUNNING |
| Observe elapsed | Set `elapsed_at` once when past due and not stopped/cancelled |

All require `client_submission_id` and `expected_session_version` (session-scoped).

## E. Timer Invariant

Timers NEVER control process state.

No timer expiry, stop, cancel, or elapsed observation may automatically:

- advance stage  
- complete stage  
- skip stage  
- close session  
- create fermentation handoff  
- miss/waive measurements  
- consume inventory  

Stage and session changes occur only via explicit ADR-004 transition commands.

## F. Idempotency Ledger

Append-only table `idempotency_records`:

| Field |
|-------|
| `id` |
| `scope_type` |
| `scope_id` |
| `client_submission_id` |
| `operation_type` |
| `request_fingerprint` |
| `resource_type` |
| `resource_id` |
| `http_status` |
| `response_snapshot` |
| `session_version_before` |
| `session_version_after` |
| `actor_id` |
| `occurred_at` |

UNIQUE `(scope_type, scope_id, client_submission_id)`.

No UPDATE/DELETE API.

**Same ID + same fingerprint + same operation_type:** return original recorded response. Do not repeat domain mutation, BrewEvent, measurement/history rows, inventory transaction, or `BrewSession.version` increment.

**Same ID + different fingerprint or operation_type:** return `409 IDEMPOTENCY_CONFLICT`. Do not modify domain state.

**Migration placement:** `idempotency_records` belongs in `005_brew_day_plans_sessions` with the first mutating brew-day APIs. Do not defer the ledger to E2A-6 (E2A-6 hardens and tests offline replay only).

## G. Operations Requiring `client_submission_id`

Required: BrewPlan create; session start; all transitions; measurement capture/correction/revision/miss/waive; timer start/stop/cancel/observe-elapsed; fermentation handoff; explicit inventory consume (when added).

GETs never require it and never persist.

## H. Optimistic Concurrency Interaction

Mutating session commands provide `expected_session_version`.

Locked order:

1. Lookup idempotency ledger for `(scope, client_submission_id)`.  
2. If exact replay (same fingerprint/operation) → return recorded response even if session version has advanced.  
3. Else if fingerprint/operation conflict → `409 IDEMPOTENCY_CONFLICT`.  
4. Else compare `expected_session_version` to current; mismatch → `409 CONCURRENCY_CONFLICT`.  
5. Else execute atomic command (including version increment exactly once).

## I. Command Atomicity

Every mutating Epic 2A command commits its complete effect in one PostgreSQL transaction, including as applicable:

- domain state changes  
- projection changes  
- history rows  
- BrewEvents  
- idempotency record  
- `BrewSession.version` update  
- associated measurement status changes  

If any required write fails, roll back the entire command. No partial-success states.

## J. Offline Contract (Epic 2A Minimum)

**Client:** generate `client_submission_id` before queueing; store action locally; show UNSYNCED; retry after reconnect.

**Server:** check idempotency ledger; return existing response for exact replay; validate concurrency/legality for new commands; commit atomically; return authoritative resource/version.

**Client then:** SYNCED or SYNC FAILED / REJECTED.

No CRDT. No automatic multi-writer merge. No silent loss. No duplicate side effects. Server state wins.

## K. Time Authority

Server timestamps (`occurred_at`, `started_at`, `elapsed_at`, and related fields) are authoritative for ordering. Client timestamps are provenance only.

## Non-Goals

- Redis / workers for timers  
- GET side effects  
- Timer-driven process transitions  
- Updating or deleting idempotency ledger rows  
- Full offline CRDT merge  

## Consequences

E2A-1 creates `idempotency_records` in migration `005`.

E2A-4 implements timers with observe-elapsed POST and read-only GET.

E2A-6 hardens offline replay tests against this contract.

Designs that persist elapsed on GET or advance stages on timer events fail architecture review.
