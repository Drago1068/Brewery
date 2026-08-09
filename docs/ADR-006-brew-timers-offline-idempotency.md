# ADR-006 — Brew Timers & Offline Idempotency

**Status:** Accepted (E2A-0)  
**Date:** 2026-08-09  
**Context:** Epic 2A needs durable timers and basic offline-safe submissions without Redis and without letting timers drive process state (ADR-004 invariant).

## Decision

### A. Timers — persistence model

`BrewTimer` rows store:

- `brew_session_id`  
- optional `stage_code` / `stage_occurrence_id`  
- `label`  
- optional `target_duration_seconds`  
- `started_at` (server)  
- optional `client_started_at`  
- `ends_at` = `started_at + target_duration_seconds` when target present  
- `stopped_at` nullable  
- `status`: `RUNNING` | `ELAPSED` | `STOPPED` | `CANCELLED`  

**No Redis** in Epic 2A. Elapsed detection is:

- computed on read (`now() >= ends_at` and still RUNNING → treat as ELAPSED), and/or  
- updated when an API poll/heartbeat observes elapsed and appends `TIMER_ELAPSED` once (idempotent per timer).

### B. Timer lifecycle

| Command | From → To |
|---------|-----------|
| Start | → `RUNNING` |
| Stop | `RUNNING`/`ELAPSED` → `STOPPED` |
| Cancel | `RUNNING` → `CANCELLED` |
| Observe elapsed | `RUNNING` → `ELAPSED` + event (once) |

### C. TIMER_ELAPSED behavior

- Appends `BrewEvent` type `TIMER_ELAPSED`.  
- May surface UI warning.  
- **Must not** change session or stage state.  
- **Must not** auto-advance, auto-complete, or auto-close.

### D. Explicit prohibition

> Timers never control process state. Stage and session transitions occur only via explicit brewer/API transition commands (ADR-004).

### E. Idempotency — `client_submission_id`

Mutating brew-day operations that may be retried from an offline queue **require** `client_submission_id` (UUID string) unless noted optional below.

#### Requires `client_submission_id`

- Measurement capture  
- Measurement instrument correction  
- Measurement user revision  
- Measurement miss  
- Measurement waive  
- Stage transition commands (`ADVANCE`, `SKIP`, start/pause/resume/close/abort)  
- Timer start / stop / cancel  
- Explicit inventory consume actions tied to the session (when added)  
- Fermentation handoff creation  

#### Optional but recommended

- BrewPlan create (usually online once)  
- Report GETs (no)

### F. Idempotency scope

Unique constraint:

```text
UNIQUE (brew_session_id, client_submission_id)
```

For plan-level ops before session exists:

```text
UNIQUE (brew_plan_id, client_submission_id)  -- or brewery-scoped
```

Duplicate submission with same id + same operation semantics:

- Return the **original** success response (same resource ids)  
- Do **not** apply side effects twice  
- Optionally append `IDEMPOTENT_REPLAY` event once per detection (or omit to reduce noise; default: **omit event**, return original)

Different payload with same `client_submission_id`:

- Reject with conflict (`409`) — id is consumed by first payload.

### G. Time fields

| Field | Authority |
|-------|-----------|
| `occurred_at` / `captured_at` / `started_at` (server) | Authoritative ordering |
| `client_occurred_at` / `client_captured_at` / `client_started_at` | Provenance only; may be skewed |

### H. Offline queued submissions (2A limited contract)

1. Client may queue measurement captures and transitions while offline.  
2. On reconnect, replay in client sequence order when possible; server still accepts any order that is domain-legal.  
3. Illegal out-of-order transition → error; client must reconcile (no silent rewrite of history).  
4. Successful replay uses idempotency keys.  
5. `sync_status` foundation on client (local only in 2A): `PENDING_UPLOAD` | `ACKED` | `REJECTED`. Server may expose last-ack via GET session.  
6. **No full CRDT / multi-writer merge** in 2A.  
7. Conflict behavior: server state wins; rejected ops remain in client queue as `REJECTED` with error body.

### I. Duplicate protection beyond idempotency

- Append-only events never update.  
- Measurement history rows append.  
- Concurrent double-submit without client id: prevented by session version token where required; without token, last writer risks conflict on stage uniqueness — E2A-1 will require version token on transitions.

## Non-goals

- Redis / Celery / background workers for timers  
- Guaranteed push notifications on elapsed  
- Multi-device simultaneous offline merge  

## Consequences

- E2A-4 implements timers; E2A-6 hardens idempotency tests.  
- Architecture review must fail any design that advances stages on timer elapsed.
