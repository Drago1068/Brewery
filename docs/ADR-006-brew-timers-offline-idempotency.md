# ADR-006 — Brew Timers & Offline Idempotency

**Status:** Accepted (E2A-0; strengthened before E2A-1)  
**Date:** 2026-08-09  
**Amended:** 2026-08-09 — history-safe timer timeline; no GET side effects; idempotency ledger as source of truth; locked replay/fingerprint rules  
**Context:** Epic 2A needs durable timers and basic offline-safe submissions without Redis and without letting timers drive process state (ADR-004). Like measurements (ADR-005), timer elapsed handling and idempotent retries are high-risk if implemented as silent mutable flags or GET-time side effects.

## Decision

### A. Non-negotiable invariants

1. **Timers never control process state.** `TIMER_ELAPSED` must not change `BrewSession.status` or `BrewStageOccurrence.status`, and must not auto-advance, auto-complete, auto-close, auto-miss, or auto-consume inventory.  
2. **No Redis / job queue / worker dependency in Epic 2A.** Persistence is PostgreSQL only.  
3. **No GET side effects.** Read APIs may *compute* whether a timer is past `ends_at`; they must **not** persist `ELAPSED`, append `TIMER_ELAPSED`, or mutate any row.  
4. **Idempotency has an append-only ledger.** Replay safety must not depend solely on “maybe unique constraints on unrelated tables.”  
5. **Command atomicity (ADR-004)** applies to timer commands and elapsed observation: domain timeline mutation + BrewEvent(s) (+ idempotency ledger row) commit together or not at all.

### B. Timer persistence model

`BrewTimer` stores an immutable-after-start timeline with **one-way** nullable→set fields (never cleared, never rewritten):

| Field | Mutability |
|-------|------------|
| `id`, `brew_session_id` | Immutable |
| `stage_occurrence_id` / `stage_code` | Immutable after create (nullable) |
| `label` | Immutable after create |
| `target_duration_seconds` | Immutable after create (nullable) |
| `started_at` (server) | Immutable after create |
| `client_started_at` | Immutable after create (nullable) |
| `ends_at` | Immutable after create when target duration present; null if open-ended |
| `elapsed_at` | **Set at most once** (null → timestamp); never cleared |
| `stopped_at` | **Set at most once** |
| `cancelled_at` | **Set at most once** |
| `status` | **Projection** derived from timeline fields (may be stored as cache, rebuildable) |
| `start_client_submission_id` | Immutable; idempotency of start |

**Derived status projection (canonical):**

| Status | Rule |
|--------|------|
| `RUNNING` | `cancelled_at` null AND `stopped_at` null AND `elapsed_at` null AND (no `ends_at` OR server_now `< ends_at`) |
| `ELAPSED` | `elapsed_at` IS NOT NULL (authoritative once observed) OR, for **read display only**, `ends_at` present AND server_now `>= ends_at` AND not stopped/cancelled — display may show “elapsed pending observe” without persisting |
| `STOPPED` | `stopped_at` IS NOT NULL |
| `CANCELLED` | `cancelled_at` IS NOT NULL |

Precedence if multiple timestamps exist (should not happen under legal commands): `CANCELLED` > `STOPPED` > `ELAPSED` > `RUNNING`.

Illegal: rewriting `started_at`/`ends_at`, clearing `elapsed_at`, or setting elapsed after stop/cancel.

### C. Timer commands (explicit only)

| Command | Effect | Events |
|---------|--------|--------|
| `START_TIMER` | Insert timer row; status RUNNING | `TIMER_STARTED` |
| `STOP_TIMER` | Set `stopped_at` once from RUNNING or ELAPSED | `TIMER_STOPPED` |
| `CANCEL_TIMER` | Set `cancelled_at` once from RUNNING | `TIMER_CANCELLED` |
| `OBSERVE_TIMER_ELAPSED` | If eligible (`ends_at` reached, not stopped/cancelled, `elapsed_at` null): set `elapsed_at` once | `TIMER_ELAPSED` **once** |

All require `client_submission_id`. Session-scoped timer mutations that participate in session OCC require `session_version` when the session aggregate version policy applies to the endpoint (E2A-4: require `session_version` on start/stop/cancel/observe for consistency with other session mutations).

**`OBSERVE_TIMER_ELAPSED` is idempotent per timer:** second observe after `elapsed_at` is set returns the original elapsed result without a second event or version bump (via idempotency key and/or natural “already elapsed” short-circuit recorded in the ledger).

### D. TIMER_ELAPSED behavior (locked)

- Persisted only via `OBSERVE_TIMER_ELAPSED` (or equivalent explicit mutating endpoint) — **never via GET**.  
- Appends exactly one `BrewEvent` (`TIMER_ELAPSED`) for that timer’s first observation.  
- May surface UI warning after observe or based on computed-but-unobserved display.  
- **Must not** change session/stage state.  
- Duplicate observes do not duplicate events.

### E. Explicit prohibition

> Timers never control process state. Stage and session transitions occur only via explicit brewer/API transition commands (ADR-004).

Architecture review **fails** any design where timer expiry triggers ADVANCE/SKIP/CLOSE/ABORT/MISS/inventory consume, or where GET persists elapsed state.

### F. Idempotency ledger (source of truth for retries)

Introduce `idempotency_records` (name flexible) as the **append-only** replay authority:

| Field | Notes |
|-------|-------|
| `id` | PK |
| `scope_type` | `BREWERY` \| `BREW_PLAN` \| `BREW_SESSION` |
| `scope_id` | UUID of brewery/plan/session |
| `client_submission_id` | UUID string |
| `operation_type` | Stable op name (e.g. `MEASUREMENT_CAPTURE`, `ADVANCE_STAGE`, `OBSERVE_TIMER_ELAPSED`) |
| `request_fingerprint` | Hash of canonicalized request body (excluding auth noise) |
| `resource_type` / `resource_id` | Primary created/affected resource |
| `http_status` | Original success status |
| `response_snapshot` | JSON of idempotent response body **or** enough ids to reconstruct |
| `session_version_before` / `session_version_after` | Nullable; set for session-versioned ops |
| `occurred_at` | Server |
| `actor_id` | |

**Constraint:** `UNIQUE (scope_type, scope_id, client_submission_id)`.

**Replay rules (locked):**

1. First success: write ledger row in the **same transaction** as domain mutation + BrewEvents.  
2. Same `client_submission_id` + same fingerprint + same operation_type → return original success (**no** second domain write, **no** second BrewEvent, **no** second `session.version` increment).  
3. Same `client_submission_id` + **different** fingerprint or operation_type → `409` conflict; id is consumed.  
4. Failed requests (4xx/5xx before commit) do **not** consume the idempotency key unless a ledger row was committed (prefer not to store failures in 2A).  
5. Ledger rows are never updated/deleted (except forbidden). Response snapshot is immutable.

BrewEvent unique indexes alone are insufficient; the ledger is required so retries can return the original response shape even when no new event is written.

### G. Operations requiring `client_submission_id` (locked)

**Required:**

- BrewPlan create  
- Session start  
- All transition commands (advance/skip/pause/resume/close/abort)  
- Measurement capture, instrument correction, user revision, miss, waive  
- Timer start / stop / cancel / observe-elapsed  
- Fermentation handoff create  
- Explicit inventory consume (when added)

**Not required:**

- GET/report endpoints (and they must remain side-effect free)

### H. Scope selection

| Operation class | Idempotency scope |
|-----------------|-------------------|
| Plan create | `BREWERY` or `BREW_PLAN` after id allocation — prefer brewery + client id until plan id exists; store final plan id in ledger |
| Session ops / measurements / timers / handoff | `BREW_SESSION` |

### I. Time fields

| Field | Authority |
|-------|-----------|
| Server `occurred_at` / `captured_at` / `started_at` / `elapsed_at` / `stopped_at` | Authoritative ordering |
| Client `client_*` timestamps | Provenance only; may be skewed; never used to authorize transitions alone |

### J. Offline queued submissions (2A limited contract)

1. Client may queue mutating commands while offline with pre-generated `client_submission_id`s.  
2. On reconnect, replay preferring client sequence; server accepts any order that is **domain-legal**.  
3. Illegal out-of-order command → error body; client marks `REJECTED`; **no silent history rewrite**.  
4. Successful replay uses the idempotency ledger.  
5. Client local sync status: `PENDING_UPLOAD` \| `ACKED` \| `REJECTED`.  
6. Server foundation: ledger ack is the server sync authority; GET session may expose `version` + recent events for reconcile.  
7. **No CRDT / multi-writer merge** in 2A.  
8. **Server state wins.** Rejected ops stay rejected; client must create a new command with a **new** `client_submission_id` if it wants a different action.  
9. Stale `session_version` on first apply → `409`; client re-reads session and may retry with same idempotency key only if fingerprint still matches an already-applied ledger entry; otherwise new key + updated version.

### K. Relationship to ADR-004 / ADR-005

- Session OCC integer version + command atomicity: ADR-004.  
- Measurement history append-only: ADR-005.  
- This ADR covers timer timeline one-way fields, elapsed observe semantics, and the idempotency ledger shared by brew-day mutations (including measurement retries).

## Non-goals

- Redis / Celery / background workers for timers  
- Guaranteed push/websocket notifications on elapsed  
- Multi-device simultaneous offline merge  
- GET endpoints that persist elapsed state  
- Updating or deleting idempotency ledger rows  

## Consequences

- E2A-4 implements timers with observe-elapsed POST and read-only GET.  
- E2A-1/E2A-6 introduce and harden `idempotency_records` (may land as soon as first mutating brew-day APIs exist).  
- Architecture review fails: timer-driven transitions, GET side effects for elapsed, mutable timer timeline rewrites, or idempotency without a ledger/fingerprint.
