# EPIC 2 ARCHITECTURE & IMPLEMENTATION HANDOFF

**Product:** Brewing Intelligence & Competition OS (BrewingOS)  
**Epic:** 2 — Guided Brew Day / Brew-Day Copilot  
**First slice:** **Epic 2A — Core Guided Brew Day**  
**Audience:** Cursor / Claude production implementer + independent architecture reviewer + Human Product Owner  
**Date:** 2026-08-09  
**Prerequisite:** Epic 1 frozen at `170fbdb` on `origin/main` (verification suite green)  
**Classification:** Architecture & implementation handoff — **produce design ADRs/increments before production domain code**

---

## 1. Purpose

This handoff locks Epic 2A before production brew-day code starts, the same way Epic 1 was locked by orientation + ADRs + increments.

It defines:

- Mission boundary and non-goals  
- Relationship to Epic 1 (consume, do not rewrite historical truth)  
- Domain model  
- Stage state machine  
- Measurement model and value-kind integrity  
- Event / audit model  
- Timers (persisted; never control process state)  
- Offline / idempotency contract  
- Planned-vs-actual and reporting  
- Brew-day close + Epic 3 fermentation handoff  
- API boundaries  
- Database migration plan  
- Controlled implementation increments  
- Acceptance criteria  
- Explicit Epic 2B / Epic 3 boundaries  

**Do not** implement the full Epic 2 vision in one pass. **Do not** begin production code until Increment E2A-0 (ADRs + schema sketch) is accepted by the Product Owner or explicitly authorized to proceed under this handoff.

---

## 2. Epic 1 freeze (entry condition)

| Item | Value |
|------|-------|
| Freeze commit | `170fbdbe6d8cab37d565c7b8c073c4a4306c6fca` |
| Branch / remote | `main` / `origin/main` |
| Working tree at freeze | Clean |
| Backend pytest | 62 passed |
| Frontend vitest | 1 passed |
| TypeScript `tsc -b` | Pass |
| `docker compose config` | Pass |
| Calculation authority | ADR-003 §§A–J (canonical) |

Epic 1 remains the planning baseline. Epic 2 **must not**:

- Mutate locked/active RecipeVersion historical rows  
- Silently change ADR-003 formula behavior  
- Collapse `PLANNED` / `MEASURED` / `CALCULATED` / `ESTIMATED` / `MISSING`  

See also [`docs/EPIC_1_FREEZE.md`](EPIC_1_FREEZE.md).

---

## 3. Mission

### Epic 2 owns

**PLAN THE DAY → GUIDE THE DAY → CAPTURE REALITY → COMPARE → CLOSE → HAND OFF TO FERMENTATION**

Core proof loop (must be demonstrable end-to-end in 2A):

```text
RecipeVersion
  → BrewPlan
  → BrewSession
  → Stage
  → Action
  → Measurement
  → Validation
  → Transition
  → Audit
  → Fermentation handoff
```

### Epic 2A owns (in scope)

- BrewPlan created from an **immutable** RecipeVersion snapshot/baseline  
- BrewSession representing the actual brew  
- Explicit stage state machine  
- Initial stages listed in §6  
- MeasurementRequirements (required / recommended)  
- MeasurementRecord (raw, corrected, provenance, confidence)  
- PENDING / CAPTURED / MISSED / WAIVED handling  
- Persisted timestamp-based timers (**no Redis**)  
- Append-only BrewEvent audit history  
- Planned-vs-actual comparisons  
- Separate completeness, process-adherence, and target-performance reporting  
- Close Brew Day without fabricating missing data  
- Create Epic 3 `FermentationSession` handoff record (minimal stub/link)  
- Basic offline-resilience: idempotent submissions + client IDs  

### Explicit non-goals (not 2A)

| Deferred | Owner |
|----------|--------|
| Full offline-first sync engine / conflict UI | Epic 2B+ |
| Hardware integrations (Bluetooth hydrometer, etc.) | Later |
| Redis / distributed job queues | Out of Epic 2A |
| AI coaching that authors process state | Forbidden |
| Fermentation logging UI/domain depth | Epic 3 |
| Packaging / sensory / competition | Epics 4–5 |
| Multi-operator IAM / production frontend image | Still deferred per ADR-001/002 |
| Timer-driven auto stage advance | **Forbidden forever in Epic 2** |

---

## 4. Relationship to Epic 1 (non-negotiable)

1. **Consume RecipeVersion as planning baseline.** Prefer `ACTIVE` or `LOCKED` versions. Creating a BrewPlan from a mutable `DRAFT` is forbidden (or requires explicit lock-on-plan ADR exception — default: **forbid**).  
2. **Snapshot planning inputs onto BrewPlan** at creation (batch size, efficiency, critical recipe lines, planned calculation results with `formula_id@version`). Ingredient-library edits after plan creation must not rewrite the plan.  
3. **Calculations remain ADR-003.** Brew Day may *display* planned estimates and may *compute* derived comparisons, but must not invent a second formula authority. New brew-day-only derived metrics need their own formula IDs if authoritative.  
4. **Inventory consumption** may be recorded during/after brew day, but must use the existing append-only inventory ledger semantics (Epic 1). No silent stock fabrication.  
5. **Ready-to-Brew is advisory for plan creation**, not a hard gate unless PO later requires GREEN-only (default 2A: warn on YELLOW/RED, allow with acknowledgement event).

---

## 5. Scientific integrity model

Extend Epic 1 value kinds. Never treat these as interchangeable:

| Kind | Meaning in Epic 2 |
|------|-------------------|
| `PLANNED` | BrewPlan target / RecipeVersion baseline expectation |
| `ESTIMATED` | ADR-003 (or later) predictive estimate |
| `CALCULATED` | Deterministic derivation from other known values |
| `MEASURED` | Captured via MeasurementRecord (raw and/or corrected) |
| `MISSING` | Required value not available; **never fabricated** |
| `INVALID` | Failed validation; no authoritative substitute |

Measurement lifecycle statuses (orthogonal to value kind):

| Status | Meaning |
|--------|---------|
| `PENDING` | Required/recommended, not yet captured |
| `CAPTURED` | MeasurementRecord exists |
| `MISSED` | Stage closed without capture; explicitly marked missed |
| `WAIVED` | Explicit waiver with reason + actor; still audited |

**Close Brew Day must not invent MISSING measurements.** Close may succeed with MISSED/WAIVED items if completeness reporting records them honestly.

---

## 6. Stage state machine (2A)

### Stages (ordered)

1. `PRE_BREW`  
2. `MASH_IN`  
3. `MASH`  
4. `MASH_COMPLETE`  
5. `BOIL`  
6. `CHILL_KNOCKOUT`  
7. `TRANSFER`  
8. `YEAST_PITCH`  
9. `BREW_DAY_AUDIT`  

### Session-level status

`PLANNED` → `IN_PROGRESS` → `PAUSED` → `IN_PROGRESS` → `CLOSED` → (`HANDED_OFF` **only** via explicit fermentation handoff; not a brew-day terminal peer of `CLOSED`)

`ABORTED` is a separate brew-day terminal path and **never** transitions to handoff.

### Transition rules

- Only **one active stage** at a time.  
- Advances are **explicit brewer/API actions** (`POST .../transitions`).  
- Backward transitions are disallowed by default in 2A (exception: PO-approved “reopen stage” later).  
- Skipping a stage (same transaction): stage → `SKIPPED`; remaining **REQUIRED** measurements → `MISSED` + events; **RECOMMENDED** stay `PENDING`.  
- Closing the session requires `BREW_DAY_AUDIT` path rules and **rejects** close while any REQUIRED measurement remains `PENDING` (no auto-MISS on close).  
- Optimistic concurrency: integer `BrewSession.version` required and atomically incremented on successful mutations.  
- Command atomicity: state + measurement side effects + BrewEvents in one DB transaction.

### Timer rule (critical)

**Timers never control process state.**

- A timer expiry emits a `BrewEvent` (e.g. `TIMER_ELAPSED`) and may surface a UI warning.  
- Stage remains unchanged until the brewer issues an explicit transition.  
- Timers are persisted as start/end timestamps (and optional duration targets) in Postgres — **no Redis**.  
- GET timers is read-only; persisting elapsed requires explicit observe command (ADR-006).  
- Offline retries use an idempotency ledger with request fingerprints (ADR-006).

---

## 7. Domain model (2A)

### Aggregate map

```text
BrewPlan 1—1 RecipeVersion (immutable baseline reference + snapshots)
BrewPlan 1—1 BrewSession (2A: one session per plan; multi-session later)
BrewSession 1—* BrewStageOccurrence
BrewStageOccurrence 1—* BrewAction (optional checklist items)
BrewStageOccurrence 1—* MeasurementRequirement
MeasurementRequirement 0—1 MeasurementRecord (CAPTURED)
BrewSession 1—* BrewTimer
BrewSession 1—* BrewEvent (append-only)
BrewSession 0—1 FermentationHandoff (Epic 3 stub)
```

### Core entities (logical)

#### BrewPlan

- `id`, `brewery_id`, `recipe_id`, `recipe_version_id`  
- `status`  
- Snapshots: batch size/unit, efficiency, recipe component snapshot JSON/normalized rows, planned calculation bundle (`formula_id`, `formula_version`, values, kinds)  
- `created_at`, `created_by` (`default_actor_id` for now)  
- `readiness_acknowledgement` (optional JSON: readiness status at plan time)

#### BrewSession

- `id`, `brew_plan_id`  
- `status`  
- `current_stage`  
- `started_at`, `closed_at`  
- `client_meta` (optional)

#### BrewStageOccurrence

- `id`, `brew_session_id`, `stage_code`  
- `status` (`PENDING` / `ACTIVE` / `COMPLETED` / `SKIPPED`)  
- `entered_at`, `exited_at`  
- Planned vs actual notes as needed

#### BrewAction (lightweight in 2A)

- Checklist / procedural step within a stage  
- `status`: `PENDING` / `DONE` / `SKIPPED`  
- Does not replace measurements

#### MeasurementRequirement

- `id`, `stage_occurrence_id` (or stage_code + session)  
- `measurement_type` (e.g. `MASH_TEMP`, `MASH_PH`, `PRE_BOIL_VOLUME`, `PRE_BOIL_GRAVITY`, `POST_BOIL_VOLUME`, `ORIGINAL_GRAVITY`, `KNOCKOUT_TEMP`, `YEAST_PITCH_TEMP`, …)  
- `requirement_level`: `REQUIRED` | `RECOMMENDED`  
- `planned_value` / `planned_unit` / `planned_kind` (`PLANNED` / `ESTIMATED`)  
- `status`: `PENDING` | `CAPTURED` | `MISSED` | `WAIVED`  
- Validation bounds (optional min/max)

#### MeasurementRecord

- `id`, `requirement_id`  
- `raw_value`, `raw_unit`  
- `corrected_value`, `corrected_unit` (nullable if none)  
- `value_kind`: always `MEASURED` for captured authority  
- `provenance` (instrument, method, note)  
- `confidence` (`HIGH` / `MEDIUM` / `LOW` or numeric 0–1 — pick enum in ADR)  
- `captured_at`, `captured_by`  
- `client_submission_id` (idempotency)

#### BrewTimer

- `id`, `brew_session_id`, `stage_code` (optional)  
- `label`  
- `target_duration_seconds` (optional)  
- `started_at`, `ends_at` (computed or stored), `stopped_at`  
- `status`: `RUNNING` / `ELAPSED` / `STOPPED` / `CANCELLED`  
- Elapsed detection is query-time and/or periodic API poll — **not** a process transition trigger

#### BrewEvent (append-only)

- `id`, `brew_session_id`  
- `event_type`  
- `occurred_at`  
- `actor_id`  
- `payload` JSON  
- `client_submission_id` (nullable, unique when present)  
- Never updated/deleted

#### FermentationHandoff

- Minimal Epic 3 bridge: `brew_session_id`, `fermentation_session_id` (created stub), wort volume/OG snapshots as measured/missing, yeast pitch info, `created_at`  
- Does **not** implement fermentation logging

---

## 8. Event model (minimum types)

| Event type | When |
|------------|------|
| `PLAN_CREATED` | BrewPlan created |
| `READINESS_ACKNOWLEDGED` | YELLOW/RED acknowledgement (separate event from `PLAN_CREATED`) |
| `SESSION_STARTED` | BrewSession starts |
| `STAGE_ENTERED` | Transition into stage |
| `STAGE_EXITED` | Transition out |
| `STAGE_SKIPPED` | Explicit skip |
| `ACTION_COMPLETED` | Checklist action done |
| `MEASUREMENT_CAPTURED` | MeasurementRecord written |
| `MEASUREMENT_MISSED` | Marked missed |
| `MEASUREMENT_WAIVED` | Waiver with reason |
| `TIMER_STARTED` / `TIMER_STOPPED` / `TIMER_ELAPSED` | Timer lifecycle |
| `VALIDATION_FAILED` / `VALIDATION_PASSED` | Measurement validation |
| `SESSION_PAUSED` / `SESSION_RESUMED` | Pause |
| `SESSION_CLOSED` | Close without fabrication |
| `SESSION_ABORTED` | Abort path |
| `FERMENTATION_HANDOFF_CREATED` | Epic 3 stub created |
| `IDEMPOTENT_REPLAY` | Duplicate client submission ignored (optional audit) |

All transitions and measurement outcomes must leave an audit trail in `BrewEvent` and/or existing `audit_events` (prefer BrewEvent for brew-day domain; link actor via ADR-002 default actor).

---

## 9. Planned-vs-actual & reporting (separate axes)

Do **not** collapse into one score.

### A. Completeness

- Fraction of REQUIRED measurements CAPTURED vs PENDING/MISSED/WAIVED  
- Recommended tracked separately  

### B. Process adherence

- Stages completed in order  
- Skips / waivers / pauses counted  
- Timer warnings acknowledged or ignored (informational)

### C. Target performance

- Measured vs planned/estimated for captured measurements only  
- Never invent deltas for MISSING  

Planned values come from BrewPlan snapshots / ADR-003 outputs stored at plan time.

---

## 10. Offline / idempotency contract (2A basic)

1. Mutating brew-day endpoints accept optional `client_submission_id` (UUID).  
2. Unique constraint per session (or global) on `client_submission_id` for measurement captures, transitions, and events.  
3. Replays return the original result (`200`/`201` with same resource), not a duplicate side effect.  
4. Clients may queue captures offline and flush later; server remains source of truth.  
5. No full CRDT/sync protocol in 2A.  
6. Clock skew: prefer server `occurred_at` with optional client `captured_at` stored as provenance field.

---

## 11. API boundaries (sketch)

All under `/api/v1`, brewery-scoped as needed.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/recipe-versions/{id}/brew-plans` | Create plan from immutable version |
| `GET` | `/brew-plans/{id}` | Plan + snapshots |
| `POST` | `/brew-plans/{id}/sessions` | Start BrewSession |
| `GET` | `/brew-sessions/{id}` | Session + current stage + summary |
| `POST` | `/brew-sessions/{id}/transitions` | Explicit stage advance/skip |
| `GET` | `/brew-sessions/{id}/requirements` | Measurement requirements/status |
| `POST` | `/brew-sessions/{id}/measurements` | Capture (idempotent) |
| `POST` | `/measurements/{id}/miss` \| `/waive` | Miss/waive |
| `POST` | `/brew-sessions/{id}/timers` | Start timer |
| `POST` | `/timers/{id}/stop` | Stop timer |
| `GET` | `/brew-sessions/{id}/timers` | Timer state (elapsed computed) |
| `GET` | `/brew-sessions/{id}/events` | Append-only history |
| `GET` | `/brew-sessions/{id}/report` | Completeness / adherence / performance |
| `POST` | `/brew-sessions/{id}/close` | Close without fabrication |
| `POST` | `/brew-sessions/{id}/fermentation-handoff` | Create Epic 3 stub |

Validation failures return structured errors; never substitute fabricated measurements.

---

## 12. Database / migrations

- Continue Alembic additive migrations from Epic 1 (`005+`).  
- Prefer new tables for brew-day aggregates; do not widen RecipeVersion mutability.  
- Append-only: `brew_events` has no update/delete API.  
- **Sequencing (pre–E2A-2 amendment):**  
  - `005` plans/sessions/actions/idempotency (done)  
  - `006` `brew_events` + E2A-1 backfill (before stage transitions)  
  - `007` measurements  
  - `008` timers  
  - `009` fermentation handoffs  
- Indexes: `(brew_session_id, occurred_at)`, unique backfill `correlation_key`, unique idempotency scope tuple.  
- NAS persistence rules unchanged (ADR-002 paths; DB not on USB git volume).  
- Detail: [`E2A2_ENTRY_AMENDMENT.md`](E2A2_ENTRY_AMENDMENT.md).

---

## 13. Implementation increments (Epic 2A)

| Increment | Scope | Exit criteria |
|-----------|-------|---------------|
| **E2A-0** | ADRs: brew-day domain, stage machine, measurement integrity, timers-do-not-control-state, offline idempotency; schema sketch; freeze checklist | PO accepts handoff/ADRs |
| **E2A-1** | Migration 005 + BrewPlan from RecipeVersion + snapshots + session create (PLANNED) | Plan/session API green; cannot plan from DRAFT |
| **E2A-2** | Migration 006 (`brew_events` + E2A-1 backfill) + stage state machine/transitions including locked START_SESSION | Illegal transitions rejected; events append-only on `brew_events` |
| **E2A-3** | Migration 007 MeasurementRequirements seed per stage + MeasurementRecord capture/miss/waive + validation | Statuses correct; no fabrication |
| **E2A-4** | Migration 008 persisted timers + elapsed events; UI warnings only | Expiry does not auto-transition |
| **E2A-5** | Planned-vs-actual + three report axes; close session; migration 009 fermentation handoff stub | Close honest with MISSED/WAIVED; handoff row created |
| **E2A-6** | Idempotent client_submission_id; basic offline contract tests; journey test RecipeVersion→…→handoff; UI shell for guided day | Journey green; no Redis |

**Stop after each increment** for review unless PO authorizes continuous 2A execution against this handoff.

---

## 14. Acceptance criteria (Epic 2A done when)

1. BrewPlan created only from immutable RecipeVersion with calculation/provenance snapshots.  
2. BrewSession runs the §6 stage sequence via explicit transitions only.  
3. Measurements support PENDING/CAPTURED/MISSED/WAIVED with raw/corrected/provenance/confidence.  
4. Missing data is never fabricated on close.  
5. Timers persist in Postgres; expiry ≠ stage advance.  
6. BrewEvent history is append-only and covers transitions/measurements/close/handoff.  
7. Reports separate completeness, process adherence, and target performance.  
8. Fermentation handoff stub exists for Epic 3.  
9. Idempotent submissions demonstrated by tests.  
10. Epic 1 golden calculation tests still pass unchanged.  
11. No Redis introduced.  
12. Deployment posture remains Epic 1 interim (Vite-dev / no-login) unless a separate hardening epic lands.

---

## 15. Epic 3 boundary

Epic 2A **creates** `FermentationSession` handoff linkage and passes measured/missing OG, volume, yeast pitch facts.

Epic 3 **owns**: fermentation logging, gravity/temp over time, dry hops during fermentation, crash/condition planning, etc.

Epic 2 must not grow a fermentation diary “just a little.”

---

## 16. Security / actor model

Unchanged from Epic 1 interim: `default_actor_id` + ADR-001 network isolation. Record actor on all brew-day writes. Do not treat this as production IAM.

---

## 17. Recommended immediate next actions

1. Architecture review of E2A-0 package (`docs/EPIC_2A_E2A0_ARCHITECTURE_REVIEW_PACKAGE.md`).  
2. On approval, begin **E2A-1** only (plans/sessions schema + API) — not a full Epic 2 dump.  

**Forbidden:** Undifferentiated “build all of Epic 2.”

---

## 18. Product Owner decisions (locked E2A-0)

| ID | Decision | Status |
|----|----------|--------|
| P1 | BrewPlan from YELLOW/RED only with explicit acknowledgement (status, warnings/blockers, ack, actor, timestamp, optional note); no silent readiness conversion | **Locked** |
| P2 | BrewPlan requires ACTIVE or LOCKED RecipeVersion; DRAFT forbidden; no lock-on-plan in 2A | **Locked** |
| P3 | Confidence: HIGH / MEDIUM / LOW only | **Locked** |
| P4 | Support CLOSED and ABORTED; neither fabricates missing measurements | **Locked** |
| P5 | Inventory consumption only via explicit confirmed action; never implied by stage/timer/close | **Locked** |

---

## Document control

| Version | Date | Notes |
|---------|------|-------|
| 1.0 | 2026-08-09 | Initial Epic 2A handoff after Epic 1 freeze |
| 1.1 | 2026-08-09 | P1–P5 locked; E2A-0 ADRs + review package authorized |
| 1.2 | 2026-08-09 | Pre–E2A-1 refinements: handoff semantics, skip/close locks, integer OCC, command atomicity, separate readiness event |
| 1.3 | 2026-08-09 | ADR-005/006 history-first strengthening (measurements + timers/idempotency) |
| 1.4 | 2026-08-09 | Pre–E2A-2: migration sequencing amendment — `brew_events` in 006 before transitions; START_SESSION locked; U1 deferred |

**E2A-1 ACCEPTED — PRE–E2A-2 ENTRY AMENDMENT REQUIRED BEFORE E2A-2 AUTHORIZATION**
