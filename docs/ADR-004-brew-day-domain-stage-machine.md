# ADR-004 — Brew Day Domain & Stage State Machine

**Status:** Accepted (E2A-0; refined before E2A-1)  
**Date:** 2026-08-09  
**Amended:** 2026-08-09 — session handoff semantics, skip/close rules, integer optimistic concurrency, command atomicity, separate readiness event  
**Context:** Epic 2A Guided Brew Day requires an explicit process model that consumes immutable Epic 1 RecipeVersions without rewriting historical recipe or calculation truth. Product Owner authorized E2A-0 with decisions P1–P5 locked in the Epic 2 handoff.

## Decision

### A. Aggregates

| Aggregate | Role |
|-----------|------|
| **BrewPlan** | Planning artifact created from one immutable `RecipeVersion` (`ACTIVE` or `LOCKED` only). Holds snapshots of recipe/calculation baseline at plan time. |
| **BrewSession** | Actual brew-day execution of a BrewPlan. One session per plan in Epic 2A. |
| **BrewStageOccurrence** | One occurrence of a stage code within a session (ordered process step). |
| **BrewAction** | Optional checklist/procedural step within a stage occurrence. Does not replace measurements. |
| **BrewEvent** | Append-only brew-day audit stream for the session (and plan-level events where noted). |
| **FermentationHandoff** | Epic 3 bridge record created only from a **CLOSED** session. |

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

Readiness is **never silently converted** to GREEN. Acknowledgement fields are stored on the plan.

**Events (same DB transaction, distinct rows):**

1. `PLAN_CREATED` — plan creation  
2. `READINESS_ACKNOWLEDGED` — **only** when YELLOW/RED acknowledgement was required and stored  

`READINESS_ACKNOWLEDGED` must **not** be collapsed into `PLAN_CREATED`. Later audit queries must be able to find acknowledgement without parsing `PLAN_CREATED` payloads. GREEN plans emit `PLAN_CREATED` only.

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

Exactly one stage occurrence may be `ACTIVE` at a time (while session is `IN_PROGRESS`).

### E. Session states

| State | Meaning | Terminal? |
|-------|---------|-----------|
| `PLANNED` | Session row exists; not started | No |
| `IN_PROGRESS` | Brewing underway | No |
| `PAUSED` | Explicit pause; no stage advance until resume | No |
| `CLOSED` | Normal brew-day completion (may include MISSED/WAIVED measurements) | **Yes (brew-day terminal)** |
| `ABORTED` | Abnormal termination with reason | **Yes (brew-day terminal)** |
| `HANDED_OFF` | Closed session that has an Epic 3 fermentation handoff record | Post-close marker only |

**Handoff semantics (locked):**

- `HANDED_OFF` is **not** a terminal peer of `CLOSED`.  
- The only legal session-status transition into handoff is **`CLOSED` → `HANDED_OFF`**, and only when a `FermentationHandoff` row is created successfully in the same transaction.  
- Alternatively, implementations may keep status `CLOSED` and treat handoff solely as presence of `fermentation_handoffs` — if status `HANDED_OFF` is retained, it must still obey **only** `CLOSED → HANDED_OFF`.  
- **`ABORTED` must never transition to handoff** (no `ABORTED → HANDED_OFF`, no handoff create from aborted sessions).

No fabrication of missing measurements on any path (P4).

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
| `SKIP_STAGE` | Mark stage `SKIPPED` with reason; apply skip measurement policy; activate next per rules |
| `PAUSE_SESSION` | `IN_PROGRESS` → `PAUSED` |
| `RESUME_SESSION` | `PAUSED` → `IN_PROGRESS` |
| `CLOSE_SESSION` | → `CLOSED` when close rules satisfied |
| `ABORT_SESSION` | → `ABORTED` with required reason |
| `CREATE_FERMENTATION_HANDOFF` | `CLOSED` → `HANDED_OFF` (or attach handoff while remaining conceptually closed); never from `ABORTED` |

Illegal transitions return `409`/`422` with structured reason; no partial silent apply.

### H. Skip semantics (locked)

Skipping a stage in one DB transaction:

1. Mark the stage occurrence `SKIPPED` (reason + actor required).  
2. Emit `STAGE_SKIPPED`.  
3. For every remaining **REQUIRED** `MeasurementRequirement` on that stage still `PENDING`: set status `MISSED`, emit `MEASUREMENT_MISSED` per requirement.  
4. For **RECOMMENDED** requirements still `PENDING`: leave `PENDING` **or** mark with a deterministic skipped-recommended policy — **locked for 2A: leave RECOMMENDED as `PENDING`** (reported under completeness as unresolved recommended). Do not invent measured values.  
5. Activate the next stage per ordering rules (unless skip ends the path — not applicable in linear 2A).

Waived requirements already `WAIVED` are untouched. Captured requirements are untouched.

### I. Pause / resume

- While `PAUSED`, `ADVANCE_STAGE` / `SKIP_STAGE` / `CLOSE_SESSION` are illegal.  
- `ABORT_SESSION` remains legal.  
- Running timers may continue wall-clock (elapsed still detectable) but do not advance stages.

### J. Close vs abort (P4) — locked rules

**CLOSE:**

- Reject `CLOSE_SESSION` while any **REQUIRED** measurement requirement on the session remains `PENDING`.  
- **Do not** auto-mark REQUIRED items `MISSED` on close.  
- The brewer must explicitly capture, miss, or waive each REQUIRED item before close.  
- RECOMMENDED may remain `PENDING`; completeness report lists them as incomplete recommended.  
- On success: session → `CLOSED`; emit `SESSION_CLOSED`.

**ABORT:**

- Terminal abnormal end with required `reason`.  
- Does not fabricate measurements.  
- Remaining `PENDING` requirements stay `PENDING` (report incomplete).  
- Emit `SESSION_ABORTED`.  
- No fermentation handoff from aborted sessions.

### K. Inventory (P5)

Inventory consumption is **never** implied by stage start/complete, timer elapsed, or session close. Consumption requires an explicit confirmed inventory action using Epic 1 append-only ledger semantics.

### L. Optimistic concurrency (locked)

- `BrewSession.version` is a dedicated **integer** column (not `updated_at`).  
- Mutating session commands provide `expected_session_version`.  
- **Idempotency lookup (ADR-006) occurs before rejecting an exact replay as stale.**  
- On first successful application: compare expected vs current; execute transaction; increment version **exactly once**.  
- Stale version on a **new** command → `409 CONCURRENCY_CONFLICT`.  
- Exact idempotent replay returns the recorded result even if the session version has since advanced (no second increment).

### M. Command atomicity (locked)

Every mutating Epic 2A command commits its complete effect in **ONE** PostgreSQL transaction. Where applicable this includes:

1. Domain state changes (session, stages, timers, …)  
2. Projection changes  
3. History rows (measurement observation/status history, …)  
4. All required `BrewEvent` rows  
5. `idempotency_records` row (ADR-006)  
6. `BrewSession.version` update  
7. Associated measurement status changes (e.g. skip → MISSED)

If any required write fails → **ROLL BACK THE ENTIRE COMMAND**. No partial-success states.

Example — `ADVANCE_STAGE` atomically: validate `expected_session_version`; verify legality; mark current stage COMPLETED; activate next stage; update `current_stage`; increment version; append `STAGE_EXITED` and `STAGE_ENTERED`; persist idempotency result. Failure of BrewEvent or idempotency persistence rolls back the stage transition.

Plan creation with YELLOW/RED ack: `PLAN_CREATED` and `READINESS_ACKNOWLEDGED` are distinct event rows in the same transaction.

### N. BrewEvent (append-only)

- `occurred_at` = **server** timestamp (authoritative)  
- `client_occurred_at` = optional client wall time (provenance only)  
- `actor_id`, `event_type`, `payload` JSON  
- No UPDATE/DELETE APIs for brew events  

### O. Invariant — timers never control process state

Timer creation, stop, or `TIMER_ELAPSED` detection **must not** change `BrewSession.status` or `BrewStageOccurrence.status`. Elapsed timers emit events/warnings only (ADR-006).

## Non-goals

- Multi-session per plan  
- Backward stage reopen  
- Automatic DRAFT lock  
- Timer-driven advances  
- Epic 3 fermentation diary  
- Handoff from `ABORTED` sessions  

## Consequences

- E2A-1+ implements these entities and transitions behind `/api/v1` brew-day routes.  
- Illegal transitions are hard failures.  
- Skip/close/handoff/concurrency/atomicity rules above are **locked** for E2A-1 implementation.  
- Epic 1 RecipeVersion/calculation history remains the planning baseline only via snapshots.
