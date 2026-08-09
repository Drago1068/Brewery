# ADR-004 — Brew Day Domain & Stage State Machine

**Status:** Accepted (E2A-0)  
**Date:** 2026-08-09  
**Context:** Epic 2A Guided Brew Day requires an explicit process model that consumes immutable Epic 1 RecipeVersions without rewriting historical recipe or calculation truth. Product Owner authorized E2A-0 with decisions P1–P5 locked in the Epic 2 handoff.

## Decision

### A. Aggregates

| Aggregate | Role |
|-----------|------|
| **BrewPlan** | Planning artifact created from one immutable `RecipeVersion` (`ACTIVE` or `LOCKED` only). Holds snapshots of recipe/calculation baseline at plan time. |
| **BrewSession** | Actual brew-day execution of a BrewPlan. One session per plan in Epic 2A. |
| **BrewStageOccurrence** | One occurrence of a stage code within a session (ordered process step). |
| **BrewAction** | Optional checklist/procedural step within a stage occurrence. Does not replace measurements. |
| **BrewEvent** | Append-only brew-day audit stream for the session. |

Brewery ownership: every BrewPlan/BrewSession is scoped to a `brewery_id` consistent with the Recipe’s brewery.

### B. RecipeVersion relationship (immutable baseline)

1. BrewPlan **requires** `RecipeVersion.status ∈ {ACTIVE, LOCKED}`.  
2. BrewPlan creation from **DRAFT is forbidden** (P2).  
3. No automatic lock-on-plan in Epic 2A.  
4. At plan creation, snapshot: batch size/unit, efficiency, equipment reference, component lines, mash steps, planned calculation results with `formula_id` + `formula_version` + value kinds.  
5. Later ingredient-library or recipe edits **must not** mutate the BrewPlan snapshot.  
6. Epic 1 RecipeVersion rows remain historically intact.

### C. Ready-to-Brew acknowledgement (P1)

BrewPlan may be created when readiness is `GREEN`, `YELLOW`, or `RED`.

If status is `YELLOW` or `RED`, creation **requires** an explicit acknowledgement payload that preserves:

- readiness status  
- relevant warning/blocker details (copy/snapshot at acknowledgement time)  
- acknowledgement flag (`true`)  
- actor_id  
- timestamp (server)  
- optional reason/note  

Readiness is **never silently converted** to GREEN. Acknowledgement is stored on the plan and emitted as a `PLAN_CREATED` / `READINESS_ACKNOWLEDGED` audit trail.

### D. Stage ordering (2A)

Ordered stage codes:

1. `PRE_BREW`  
2. `MASH_IN`  
3. `MASH`  
4. `MASH_COMPLETE`  
5. `BOIL`  
6. `CHILL_KNOCKOUT`  
7. `TRANSFER`  
8. `YEAST_PITCH`  
9. `BREW_DAY_AUDIT`  

Exactly one stage occurrence may be `ACTIVE` at a time.

### E. Session states

| State | Meaning |
|-------|---------|
| `PLANNED` | Session row exists; not started |
| `IN_PROGRESS` | Brewing underway |
| `PAUSED` | Explicit pause; no stage advance until resume |
| `CLOSED` | Normal completion (may include MISSED/WAIVED measurements) |
| `ABORTED` | Terminal abnormal termination with reason |
| `HANDED_OFF` | Fermentation handoff stub created after close (or allowed post-close transition) |

Terminal: `CLOSED`, `ABORTED` (and `HANDED_OFF` as post-close marker). No fabrication of missing measurements on any path (P4).

### F. Stage occurrence states

| State | Meaning |
|-------|---------|
| `PENDING` | Not yet entered |
| `ACTIVE` | Current stage |
| `COMPLETED` | Exited normally via explicit transition |
| `SKIPPED` | Explicitly skipped with reason |

### G. Explicit transition commands

All process movement is via explicit API commands (never timer-driven):

| Command | Effect |
|---------|--------|
| `START_SESSION` | `PLANNED` → `IN_PROGRESS`; enter first stage `PRE_BREW` |
| `ADVANCE_STAGE` | Complete current stage; activate next in order |
| `SKIP_STAGE` | Mark current or named pending stage `SKIPPED` with reason; activate next per rules |
| `PAUSE_SESSION` | `IN_PROGRESS` → `PAUSED` |
| `RESUME_SESSION` | `PAUSED` → `IN_PROGRESS` |
| `CLOSE_SESSION` | From `BREW_DAY_AUDIT` (active/completed as defined in transition table) → `CLOSED` |
| `ABORT_SESSION` | From non-terminal → `ABORTED` with required reason |

Illegal transitions return `409`/`422` with structured reason; no partial silent apply.

### H. Skip semantics

- Skip requires `reason` + actor.  
- Skipped stages record `STAGE_SKIPPED` event.  
- Process-adherence reporting counts skips.  
- Required measurements on skipped stages become `MISSED` unless explicitly `WAIVED` before skip finalization (E2A implementation must pick one deterministic rule in service layer: **default — mark REQUIRED as MISSED on skip**).

### I. Pause / resume

- While `PAUSED`, `ADVANCE_STAGE` / `SKIP_STAGE` / `CLOSE_SESSION` are illegal.  
- `ABORT_SESSION` remains legal.  
- Running timers may continue wall-clock (elapsed still detectable) but do not advance stages.

### J. Close vs abort (P4)

**CLOSE:** Normal completion path. Honesty required: PENDING required measurements must be resolved to CAPTURED, MISSED, or WAIVED before close (or close auto-marks remaining REQUIRED PENDING as MISSED with event — **default: reject close while REQUIRED PENDING remain**, forcing explicit miss/waive). Recommended measurements may remain PENDING and are reported as incomplete recommended.

**ABORT:** Terminal abnormal end with required `reason`. Does not fabricate measurements. Remaining PENDING stay PENDING or are marked MISSED via explicit abort policy (**default: leave PENDING; report incomplete**).

### K. Inventory (P5)

Inventory consumption is **never** implied by stage start/complete, timer elapsed, or session close. Consumption requires an explicit confirmed inventory action using Epic 1 append-only ledger semantics.

### L. Concurrency expectations

- Optimistic concurrency: `BrewSession.version` (integer) or `updated_at` token required on mutating commands.  
- Conflicting concurrent transitions: first writer wins; loser gets conflict error.  
- Idempotent retries use `client_submission_id` (ADR-006), not blind re-apply.

### M. BrewEvent (append-only)

Every successful mutating command appends one or more `BrewEvent` rows:

- `occurred_at` = **server** timestamp (authoritative)  
- `client_occurred_at` = optional client wall time (provenance only)  
- `actor_id`, `event_type`, `payload` JSON  
- No UPDATE/DELETE APIs for brew events  

### N. Invariant — timers never control process state

Timer creation, stop, or `TIMER_ELAPSED` detection **must not** change `BrewSession.status` or `BrewStageOccurrence.status`. Elapsed timers emit events/warnings only (ADR-006).

## Non-goals

- Multi-session per plan  
- Backward stage reopen  
- Automatic DRAFT lock  
- Timer-driven advances  
- Epic 3 fermentation diary  

## Consequences

- E2A-1+ implements these entities and transitions behind `/api/v1` brew-day routes.  
- Illegal transitions are hard failures.  
- Epic 1 RecipeVersion/calculation history remains the planning baseline only via snapshots.
