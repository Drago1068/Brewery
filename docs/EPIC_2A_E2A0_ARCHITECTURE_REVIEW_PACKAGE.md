# EPIC 2A E2A-0 ARCHITECTURE REVIEW PACKAGE

**Product:** BrewingOS  
**Epic slice:** 2A — Core Guided Brew Day  
**Increment:** E2A-0 (architecture only)  
**Date:** 2026-08-09  
**Governing spec:** [`EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md`](EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md) v1.0 (approved)  
**Epic 1 freeze:** `170fbdbe6d8cab37d565c7b8c073c4a4306c6fca` (per handoff / `EPIC_1_FREEZE.md`)  
**Classification:** Documentation & design — **no production Brew-Day domain code; no Alembic 005 applied**  
**Refinement:** Pre–E2A-1 locks for handoff semantics, skip/close rules, integer optimistic concurrency, command atomicity, and separate `READINESS_ACKNOWLEDGED` events (see ADR-004 amended).

---

## Locked Product Owner decisions (P1–P5)

| ID | Decision |
|----|----------|
| **P1** | BrewPlan from YELLOW/RED allowed **only** with explicit acknowledgement preserving status, warnings/blockers, acknowledgement, actor, timestamp, optional note. No silent readiness conversion. |
| **P2** | BrewPlan **requires** immutable `ACTIVE` or `LOCKED` RecipeVersion. DRAFT forbidden. No lock-on-plan in 2A. |
| **P3** | Confidence enum: `HIGH` \| `MEDIUM` \| `LOW` only. |
| **P4** | Support **CLOSED** and **ABORTED**. Neither fabricates missing measurements. |
| **P5** | Inventory consumption only via **explicit confirmed** action; never implied by stage/timer/close. Epic 1 ledger semantics. |

---

## 1. ADR-004

See [`ADR-004-brew-day-domain-stage-machine.md`](ADR-004-brew-day-domain-stage-machine.md).

Summary: BrewPlan/BrewSession/stage/action/event model; ordered stages; explicit transitions; pause/resume/close/abort; RecipeVersion immutability; readiness acknowledgement as a **separate** `READINESS_ACKNOWLEDGED` event; skip auto-MISS REQUIRED; reject close on REQUIRED PENDING; integer `session.version`; command atomicity; **`CLOSED`→`HANDED_OFF` only**; timers never control process state.

## 2. ADR-005

See [`ADR-005-measurement-integrity-provenance.md`](ADR-005-measurement-integrity-provenance.md).

Summary: History-first measurement ledger — append-only observation history (capture/correction/revision + validation warnings) and status history (PENDING→CAPTURED/MISSED/WAIVED); `MeasurementRecord` is a rebuildable projection only; HIGH/MEDIUM/LOW confidence; INPUT ERROR reject vs UNUSUAL/DOMAIN_CONCERN preserve.

## 3. ADR-006

See [`ADR-006-brew-timers-offline-idempotency.md`](ADR-006-brew-timers-offline-idempotency.md).

Summary: Persisted timers; TIMER_ELAPSED ≠ transition; no Redis; `client_submission_id` idempotency; server vs client timestamps; limited offline replay contract.

---

## 4. Proposed database schema (Alembic `005+` sketch — not applied)

Additive tables; all UUID PKs unless noted. `brewery_id` on plan (and denormalized on session) enforces ownership boundary.

### 4.1 `brew_plans`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `brewery_id` | UUID FK → `breweries.id` ON DELETE RESTRICT | |
| `recipe_id` | UUID FK → `recipes.id` | |
| `recipe_version_id` | UUID FK → `recipe_versions.id` RESTRICT | Must be ACTIVE/LOCKED at create |
| `status` | TEXT | `PLANNED` / `IN_USE` / `SUPERSEDED` (2A: mainly PLANNED/IN_USE) |
| `batch_size`, `batch_size_unit` | NUMERIC/TEXT | Snapshot |
| `efficiency_percent` | NUMERIC | Snapshot |
| `recipe_snapshot` | JSONB | Components/steps/targets |
| `calculation_snapshot` | JSONB | formula_id, version, values, kinds |
| `readiness_status` | TEXT NULL | At plan time |
| `readiness_details` | JSONB NULL | Warnings/blockers snapshot |
| `readiness_acknowledged` | BOOLEAN | Required true if YELLOW/RED |
| `readiness_ack_actor_id` | TEXT NULL | |
| `readiness_ack_at` | TIMESTAMPTZ NULL | Server |
| `readiness_ack_note` | TEXT NULL | |
| `created_by`, `created_at` | TEXT/TIMESTAMPTZ | |
| `client_submission_id` | TEXT NULL | Unique per brewery when present |

**Constraints:** CHECK readiness acknowledgement coherence; UNIQUE `(brewery_id, client_submission_id)` WHERE not null.

### 4.2 `brew_sessions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `brew_plan_id` | UUID FK → `brew_plans.id` UNIQUE | 2A: one session per plan |
| `brewery_id` | UUID FK → `breweries.id` | |
| `status` | TEXT | PLANNED/IN_PROGRESS/PAUSED/CLOSED/ABORTED/HANDED_OFF |
| `current_stage_code` | TEXT NULL | |
| `version` | INT NOT NULL DEFAULT 1 | Optimistic concurrency token (**integer only**; not `updated_at`) |
| `started_at`, `closed_at`, `aborted_at` | TIMESTAMPTZ NULL | |
| `abort_reason` | TEXT NULL | Required if ABORTED |
| `created_at`, `updated_at` | TIMESTAMPTZ | Audit timestamps only — **not** concurrency tokens |

### 4.3 `brew_stage_occurrences`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `brew_session_id` | UUID FK CASCADE | |
| `stage_code` | TEXT | Enum set from ADR-004 |
| `sequence_no` | INT | 1..9 |
| `status` | TEXT | PENDING/ACTIVE/COMPLETED/SKIPPED |
| `entered_at`, `exited_at` | TIMESTAMPTZ NULL | |
| `skip_reason` | TEXT NULL | |

**Constraints:** UNIQUE `(brew_session_id, stage_code)`; UNIQUE `(brew_session_id, sequence_no)`; partial unique one ACTIVE per session.

### 4.4 `brew_actions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `stage_occurrence_id` | UUID FK CASCADE | |
| `code`, `label` | TEXT | |
| `status` | TEXT | PENDING/DONE/SKIPPED |
| `completed_at` | TIMESTAMPTZ NULL | |
| `client_submission_id` | TEXT NULL | |

### 4.5 `measurement_definitions` (optional seed)

| Column | Type | Notes |
|--------|------|-------|
| `measurement_type` | TEXT PK | e.g. MASH_TEMP |
| `default_unit` | TEXT | |
| `typical_stage_code` | TEXT | |
| `default_requirement_level` | TEXT | REQUIRED/RECOMMENDED |
| `expected_min`, `expected_max` | NUMERIC NULL | For UNUSUAL detection |

### 4.6 `measurement_requirements`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `brew_session_id` | UUID FK | |
| `stage_occurrence_id` | UUID FK | |
| `measurement_type` | TEXT | |
| `requirement_level` | TEXT | REQUIRED/RECOMMENDED |
| `status` | TEXT | PENDING/CAPTURED/MISSED/WAIVED |
| `planned_value`, `planned_unit` | NUMERIC/TEXT NULL | |
| `planned_kind` | TEXT NULL | PLANNED/ESTIMATED |
| `current_record_id` | UUID NULL FK → measurement_records | Soft pointer |

### 4.7 `measurement_records` (projection only)

Current convenience view of the latest observation-history head. **Not** the scientific source of truth.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `requirement_id` | UUID FK | |
| `raw_value`, `raw_unit` | NUMERIC/TEXT | Projection |
| `corrected_value`, `corrected_unit` | NUMERIC/TEXT NULL | Projection |
| `confidence` | TEXT | HIGH/MEDIUM/LOW |
| `instrument`, `method`, `provenance` | TEXT NULL | Projection |
| `validation_class` | TEXT NULL | Latest OK/UNUSUAL_VALUE/DOMAIN_CONCERN |
| `validation_notes` | JSONB NULL | Latest warning snapshot only |
| `latest_observation_history_id` | UUID FK | Points at history head |
| `first_captured_at` | TIMESTAMPTZ | From original RAW_CAPTURE (stable) |
| `captured_by` | TEXT | Original capture actor |
| `client_submission_id` | TEXT NOT NULL | Creating capture idempotency key |

Projection columns may change only when a new observation-history row is appended in the same transaction.

### 4.8 `measurement_observation_history` (append-only; value source of truth)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `measurement_record_id` | UUID FK | |
| `requirement_id` | UUID FK | |
| `event_class` | TEXT | `RAW_CAPTURE` / `INSTRUMENT_CORRECTION` / `USER_REVISION` |
| `raw_value`, `raw_unit` | NUMERIC/TEXT NULL | Immutable snapshot |
| `corrected_value`, `corrected_unit` | NUMERIC/TEXT NULL | Immutable snapshot |
| `confidence` | TEXT NULL | |
| `instrument`, `method`, `provenance` | TEXT NULL | Snapshot |
| `validation_class` | TEXT NULL | OK/UNUSUAL_VALUE/DOMAIN_CONCERN on this event |
| `validation_notes` | JSONB NULL | Immutable warning snapshot for this event |
| `reason` | TEXT NULL | Required for USER_REVISION |
| `actor_id` | TEXT | |
| `occurred_at` | TIMESTAMPTZ | Server |
| `client_occurred_at` | TIMESTAMPTZ NULL | |
| `client_submission_id` | TEXT NOT NULL | |
| `payload` | JSONB NULL | |

**No UPDATE/DELETE** via API or ORM helpers used by services.

### 4.8b `measurement_status_history` (append-only; lifecycle source of truth)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `requirement_id` | UUID FK | |
| `from_status` | TEXT | |
| `to_status` | TEXT | CAPTURED/MISSED/WAIVED |
| `reason` | TEXT NULL | Required for WAIVED |
| `actor_id` | TEXT | |
| `source_command` | TEXT | CAPTURE/MISS/WAIVE/SKIP_STAGE/… |
| `occurred_at` | TIMESTAMPTZ | Server |
| `client_occurred_at` | TIMESTAMPTZ NULL | |
| `client_submission_id` | TEXT NULL | |
| `payload` | JSONB NULL | |

Requirement `status` is a projection of the latest status-history head.

### 4.9 `brew_timers`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `brew_session_id` | UUID FK | |
| `stage_occurrence_id` | UUID NULL | |
| `label` | TEXT | |
| `target_duration_seconds` | INT NULL | |
| `started_at`, `ends_at`, `stopped_at` | TIMESTAMPTZ | |
| `status` | TEXT | RUNNING/ELAPSED/STOPPED/CANCELLED |
| `elapsed_event_emitted` | BOOLEAN DEFAULT FALSE | Idempotent TIMER_ELAPSED |
| `client_submission_id` | TEXT NULL | On start |

### 4.10 `brew_events` (append-only)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `brew_session_id` | UUID FK | Nullable only for plan-level events if needed; prefer session |
| `brew_plan_id` | UUID FK NULL | |
| `event_type` | TEXT | See §6 |
| `occurred_at` | TIMESTAMPTZ | Server authoritative |
| `client_occurred_at` | TIMESTAMPTZ NULL | |
| `actor_id` | TEXT | |
| `payload` | JSONB | |
| `client_submission_id` | TEXT NULL | |

**Indexes:** `(brew_session_id, occurred_at)`; UNIQUE `(brew_session_id, client_submission_id)` WHERE client_submission_id IS NOT NULL.

**Append-only protection:** DB role/app layer denies UPDATE/DELETE; optional trigger.

### 4.11 `fermentation_handoffs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `brew_session_id` | UUID FK UNIQUE | |
| `brewery_id` | UUID FK | |
| `fermentation_session_id` | UUID | Stub id created for Epic 3 |
| `og_value`, `og_unit`, `og_kind` | … | MEASURED or MISSING |
| `volume_value`, `volume_unit`, `volume_kind` | … | |
| `yeast_pitch_snapshot` | JSONB | |
| `created_at`, `created_by` | | |
| `client_submission_id` | TEXT | Unique per session |

**Note:** Does not create fermentation logging tables beyond stub id storage.

### 4.12 Idempotency / indexes (summary)

- UNIQUE `(brew_session_id, client_submission_id)` on events, measurements, transitions log as applicable  
- UNIQUE one ACTIVE stage per session (partial index)  
- FK RESTRICT from plans to recipe_versions to preserve baseline  

---

## 5. Proposed API contracts

Base: `/api/v1`. All mutating brew-day ops below that can be offline-retried require `client_submission_id` unless marked optional. Optimistic `session.version` required on session mutations.

### 5.1 Create BrewPlan

`POST /recipe-versions/{recipe_version_id}/brew-plans`

Request:

```json
{
  "client_submission_id": "uuid",
  "readiness_acknowledgement": {
    "status": "YELLOW",
    "details": {"warnings": [], "blockers": []},
    "acknowledged": true,
    "note": "optional"
  }
}
```

Rules: version ACTIVE/LOCKED; if YELLOW/RED, acknowledgement required and stored; snapshot recipe + calculations.

Response: `201` plan resource.

### 5.2 Start session

`POST /brew-plans/{id}/sessions` + `{ "client_submission_id": "..." }`  
→ session PLANNED→IN_PROGRESS, PRE_BREW ACTIVE.

### 5.3 Transition commands

`POST /brew-sessions/{id}/transitions`

```json
{
  "client_submission_id": "uuid",
  "session_version": 3,
  "command": "ADVANCE_STAGE | SKIP_STAGE | PAUSE_SESSION | RESUME_SESSION | CLOSE_SESSION | ABORT_SESSION",
  "reason": "required for SKIP/ABORT",
  "client_occurred_at": "optional ISO-8601"
}
```

- `session_version` is the expected integer `BrewSession.version` (required). On success it increments atomically.  
- Entire command (state + measurement side effects + BrewEvents) commits in **one transaction**; event-append failure rolls back domain changes.  
- Response includes updated session, stage occurrences, and new `session_version`.

**Skip:** remaining REQUIRED requirements on the skipped stage → `MISSED` + `MEASUREMENT_MISSED` events in the same transaction; RECOMMENDED stay `PENDING`.

**Close:** rejected while any REQUIRED requirement is still `PENDING` (no auto-MISS on close).

**Abort:** never eligible for fermentation handoff.

### 5.4 Measurement capture

`POST /brew-sessions/{id}/measurements`

```json
{
  "client_submission_id": "uuid",
  "requirement_id": "uuid",
  "raw_value": 65.2,
  "raw_unit": "C",
  "confidence": "HIGH",
  "instrument": "optional",
  "method": "optional",
  "provenance": "optional",
  "client_captured_at": "optional"
}
```

- INPUT ERROR → `422`, no row  
- UNUSUAL/DOMAIN_CONCERN → `201` with `warnings[]`  
- Idempotent replay → `200` original  

### 5.5 Instrument correction

`POST /measurement-records/{id}/instrument-corrections`  
Body: corrected value/unit, method, client_submission_id, reason/note.

### 5.6 User revision

`POST /measurement-records/{id}/revisions`  
Body: new raw (and optional corrected), reason (**required**), confidence, client_submission_id.

### 5.7 Miss / waive

`POST /measurement-requirements/{id}/miss`  
`POST /measurement-requirements/{id}/waive`  
Both require `client_submission_id`; waive requires `reason`.

### 5.8 Timers

`POST /brew-sessions/{id}/timers` — start (`client_submission_id`, label, target_duration_seconds?)  
`POST /timers/{id}/stop` | `/cancel` — `client_submission_id`  
`GET /brew-sessions/{id}/timers` — computes elapsed; may emit TIMER_ELAPSED once

### 5.9 Report

`GET /brew-sessions/{id}/report` → `{ completeness, process_adherence, target_performance }` (separate objects).

### 5.10 Close / abort

Via transitions (`CLOSE_SESSION` / `ABORT_SESSION`).

- Close rejected while REQUIRED `PENDING` remain — brewer must explicitly miss/waive/capture.  
- Abort is terminal; no handoff.

### 5.11 Fermentation handoff

`POST /brew-sessions/{id}/fermentation-handoff`

```json
{
  "client_submission_id": "uuid",
  "session_version": 12
}
```

- Allowed **only** from `CLOSED` (legal transition `CLOSED` → `HANDED_OFF` if status used; never from `ABORTED`).  
- Creates `fermentation_handoffs` stub + `FERMENTATION_HANDOFF_CREATED` in the same transaction as the status update / version increment.  
- `HANDED_OFF` is not a brew-day terminal peer of `CLOSED`; it is a post-close handoff marker only.

### 5.12 Operations requiring `client_submission_id`

Capture, instrument correction, user revision, miss, waive, all transition commands, timer start/stop/cancel, fermentation handoff, explicit inventory consume (future 2A endpoint). Plan create: required if client retries.

---

## 6. Event catalog

| Event type | Emitted when |
|------------|--------------|
| `PLAN_CREATED` | BrewPlan created |
| `READINESS_ACKNOWLEDGED` | YELLOW/RED ack stored (**separate event row** from `PLAN_CREATED`, same transaction) |
| `SESSION_STARTED` | Start session |
| `STAGE_ENTERED` / `STAGE_EXITED` | Stage boundaries |
| `STAGE_SKIPPED` | Skip |
| `ACTION_COMPLETED` / `ACTION_SKIPPED` | Checklist |
| `MEASUREMENT_CAPTURED` | Capture accepted |
| `MEASUREMENT_INSTRUMENT_CORRECTION` | Instrument correction |
| `MEASUREMENT_USER_REVISION` | User revision |
| `MEASUREMENT_MISSED` / `MEASUREMENT_WAIVED` | Miss/waive |
| `VALIDATION_WARNING` | UNUSUAL or DOMAIN_CONCERN |
| `TIMER_STARTED` / `TIMER_STOPPED` / `TIMER_CANCELLED` / `TIMER_ELAPSED` | Timer lifecycle |
| `SESSION_PAUSED` / `SESSION_RESUMED` | Pause/resume |
| `SESSION_CLOSED` / `SESSION_ABORTED` | Terminal |
| `FERMENTATION_HANDOFF_CREATED` | Handoff stub |
| `INVENTORY_CONSUME_CONFIRMED` | Explicit consume only |

---

## 7. State-transition tables

### 7.1 Session

| From \ Command | START | PAUSE | RESUME | CLOSE | ABORT | HANDOFF |
|----------------|-------|-------|--------|-------|-------|---------|
| PLANNED | IN_PROGRESS | — | — | — | ABORTED | — |
| IN_PROGRESS | — | PAUSED | — | CLOSED* | ABORTED | — |
| PAUSED | — | — | IN_PROGRESS | — | ABORTED | — |
| CLOSED | — | — | — | — | — | HANDED_OFF† |
| ABORTED | — | — | — | — | — | — |
| HANDED_OFF | — | — | — | — | — | — |

\* CLOSE only when stage rules satisfied (in/after `BREW_DAY_AUDIT`) **and** no REQUIRED measurement is still `PENDING` (explicit miss/waive/capture required; **no auto-MISS on close**).  
† Handoff **only** from `CLOSED`. `ABORTED` never hands off. `HANDED_OFF` is a post-close marker, not a brew-day terminal peer of `CLOSED`.

### 7.2 Stage (happy path)

`PENDING → ACTIVE → COMPLETED` via ADVANCE.  
`PENDING|ACTIVE → SKIPPED` via SKIP (+ reason): in the **same transaction**, remaining REQUIRED requirements → `MISSED` + events; RECOMMENDED stay `PENDING`.  
Only one ACTIVE.

### 7.3 Measurement requirement

`PENDING → CAPTURED` (capture)  
`PENDING → MISSED` (explicit miss **or** skip of owning stage)  
`PENDING → WAIVED` (waive)  
CAPTURED may receive corrections/revisions without leaving CAPTURED.  
Close does **not** transition PENDING → MISSED.

---

## 8. Measurement lifecycle

```text
Definition (seed)
  → Requirement (PENDING + planned/estimated)
  → Capture:
        append observation_history RAW_CAPTURE (with validation snapshot)
        append status_history PENDING→CAPTURED
        upsert record projection
        BrewEvents
      → Instrument correction:
        append observation_history INSTRUMENT_CORRECTION
        refresh projection only
      → User revision:
        append observation_history USER_REVISION (reason required)
        refresh projection only
  → OR Miss:
        append status_history PENDING→MISSED (no value fabrication)
  → OR Waive:
        append status_history PENDING→WAIVED (reason required)
  → OR Skip stage:
        append status_history PENDING→MISSED for remaining REQUIRED
```

History tables are authoritative; record/requirement status fields are projections.

---

## 9. Validation model

| Class | Persist? | HTTP |
|-------|----------|------|
| INPUT ERROR | No | 422 |
| UNUSUAL VALUE | Yes + warning | 201 |
| DOMAIN CONCERN | Yes + warning | 201 |
| OK | Yes | 201 |

---

## 10. Idempotency model

- Key: `client_submission_id` scoped to session (or brewery/plan pre-session).  
- Same key + same logical op → original result (**no second `version` increment**).  
- Same key + different body → 409.  
- Server timestamps authoritative.  
- Session mutations also require matching integer `session_version` on first apply.

## 10a. Command atomicity

Domain mutation + measurement status side effects + all BrewEvents for the command commit in **one** DB transaction. Failed event append rolls back domain changes.

---

## 11. Offline contract (2A)

- Queue locally → replay with client_submission_id.  
- Server legality still enforced.  
- Server wins conflicts; client marks REJECTED.  
- No multi-writer merge / CRDT.  
- Sync status foundation is client-side + ack via normal responses.

---

## 12. Test plan (deterministic)

| Area | Tests |
|------|-------|
| RecipeVersion immutability | Plan from DRAFT rejected; ACTIVE/LOCKED accepted; snapshot insulated from later recipe edits |
| Plan snapshots | calculation_snapshot retains formula_id@version |
| Readiness ack | GREEN without ack OK; YELLOW/RED without ack rejected; with ack stores details |
| Legal transitions | Ordered ADVANCE through all stages |
| Illegal transitions | ADVANCE while PAUSED; CLOSE before audit; ADVANCE from CLOSED |
| Skip | Reason required; event; adherence impact |
| Pause/resume | Round-trip; blocked commands while paused |
| Close | Reject with REQUIRED PENDING (no auto-MISS); success after explicit miss/waive/capture |
| Abort | Reason required; terminal; no fabricated measurements; **no handoff** |
| Skip | REQUIRED → MISSED in same transaction; RECOMMENDED remain PENDING; events emitted |
| Capture | Happy path; idempotent replay |
| Instrument correction history | Prior rows immutable; projection refreshed; BrewEvent emitted |
| User revision history | Prior values retained; reason required; history append |
| Miss / waive history | `measurement_status_history` append; no fabricated values |
| Unusual value | Persisted on observation-history row + warning; not overwrite-only notes |
| Invalid input | 422; still PENDING |
| Timer persistence | Restart process/read still shows RUNNING/ELAPSED |
| Timer expiry | ELAPSED event; stage unchanged |
| Duplicate submission | Same id returns same resource; no double version bump |
| Command atomicity | Forced event-write failure rolls back domain mutation |
| Optimistic concurrency | Stale `session_version` → 409; success increments integer version |
| Offline delayed capture | Capture after delay still valid if stage allows |
| Append-only events | No update API; count monotonic |
| Readiness events | YELLOW/RED plan create yields both `PLAN_CREATED` and `READINESS_ACKNOWLEDGED` |
| Planned-vs-actual | Delta only when both present |
| Completeness / adherence / performance | Separate report sections |
| Fermentation handoff | Only from CLOSED → HANDED_OFF; aborted rejected; no fermentation logs |
| Epic 1 regression | Full golden calculation suite unchanged |

---

## 13. Migration sequence proposal

| Migration | Content |
|-----------|---------|
| `005_brew_day_plans_sessions` | brew_plans, brew_sessions, brew_stage_occurrences, brew_actions |
| `006_brew_day_measurements` | definitions, requirements, records (projection), observation_history, status_history |
| `007_brew_day_timers_events` | brew_timers, brew_events |
| `008_fermentation_handoffs` | fermentation_handoffs stub |

Apply only starting **E2A-1** (not in E2A-0).

---

## 14. Files/modules expected for E2A-1 … E2A-6

| Increment | Expected modules |
|-----------|------------------|
| E2A-1 | `alembic/versions/005_*`; `db/models` brew plan/session; `domain/brew_day_rules.py`; `services/brew_plan.py`, `brew_session.py`; `api/v1/brew_plans.py`; tests |
| E2A-2 | Stage transition service; brew_events writer; transition API; illegal-path tests |
| E2A-3 | Measurement services; validation; history; miss/waive APIs; seed definitions |
| E2A-4 | Timer service; elapsed observer; UI warning hooks |
| E2A-5 | Report service; close/abort hardening; fermentation_handoff service/API |
| E2A-6 | Idempotency middleware/helpers; offline contract tests; journey test; guided UI shell (`BrewDayPanel` or similar) |

Frontend remains Vite-dev interim (ADR-001/002).

---

## 15. Architecture decisions still unresolved

| ID | Topic | Notes |
|----|-------|-------|
| U1 | Exact REQUIRED measurement set per stage | Seed in E2A-3; not locked in E2A-0 |
| U5 | Whether plan-level events always include `brew_plan_id` with null session | Prefer both plan_id and session_id when session exists |
| U7 | Explicit inventory consume endpoint shape on session | Required by P5; path TBD in E2A-1/5 |

### Locked in pre–E2A-1 refinement (formerly open)

| ID | Topic | Locked rule |
|----|-------|-------------|
| U2 | Close vs auto-MISS | **Reject close** while REQUIRED `PENDING`; never auto-MISS on close |
| U3 | Skip → REQUIRED | **Auto-MISS** remaining REQUIRED in same transaction + events |
| U4 | Abort PENDING | **Leave PENDING**; report incomplete; no handoff |
| U6 | Observation/status history | **Dedicated append-only tables** required; record fields are projections only |

---

## 16. Risks

| Risk | Mitigation |
|------|------------|
| Timer misuse auto-advances stages | ADR-004/006 invariant + tests |
| Mutable measurement fields without history | ADR-005 history-first invariant + projection-only records |
| Fabrication on close | Reject close with REQUIRED PENDING; explicit miss/waive |
| Partial commit without audit | Command atomicity: event failure rolls back domain mutation |
| Stale client overwrites | Integer `session_version` compare-and-increment |
| Handoff from aborted brew | Forbidden; only `CLOSED` → `HANDED_OFF` |
| Snapshot drift from live recipe | Immutable version + JSON snapshots |
| Offline out-of-order transitions | Hard fail + client reconcile |
| Scope creep into Epic 3 | Handoff stub only |
| Dual audit streams | brew_events authoritative for brew day |

---

## 17. Epic 1 regression impact

- **Expected:** None if E2A remains additive.  
- **Gate:** Epic 1 golden calculation tests + existing API tests must stay green before any E2A increment merge.  
- **Forbidden:** Formula identity changes, RecipeVersion mutability relaxation, inventory silent consumes.

---

## 18. Confirmation — no Epic 3 functionality implemented

**Confirmed.** Only a future `fermentation_handoffs` stub is designed. No fermentation logging, charts, or diary APIs/tables beyond the handoff row sketch.

## 19. Confirmation — no production Brew-Day domain code implemented

**Confirmed.** E2A-0 delivers ADRs + this review package only. No Alembic `005` migration applied; no brew-day services/API modules added in this increment.

---

## Document index

| Doc | Path |
|-----|------|
| ADR-004 | `docs/ADR-004-brew-day-domain-stage-machine.md` |
| ADR-005 | `docs/ADR-005-measurement-integrity-provenance.md` |
| ADR-006 | `docs/ADR-006-brew-timers-offline-idempotency.md` |
| This package | `docs/EPIC_2A_E2A0_ARCHITECTURE_REVIEW_PACKAGE.md` |
| Handoff | `docs/EPIC_2_ARCHITECTURE_IMPLEMENTATION_HANDOFF.md` |
| Epic 1 freeze | `docs/EPIC_1_FREEZE.md` |

**E2A-0 COMPLETE — READY FOR ARCHITECTURE REVIEW**
