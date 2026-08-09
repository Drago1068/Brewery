# ADR-005 — Measurement Integrity, Provenance & Validation

## Metadata

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** Brew Day must record actual observations without collapsing Epic 1 value kinds or fabricating missing data. Measurement integrity is the highest-risk Epic 2A domain: captures, corrections, revisions, validation warnings, MISSED, and WAIVED must preserve history rather than become silently mutable fields. Product Owner locked confidence as HIGH / MEDIUM / LOW (P3).  
**Amendment:** Canonical rebuild for final E2A-0 review — architecture unchanged; iterative-edit duplication removed. INPUT ERROR may emit operational `MEASUREMENT_INPUT_REJECTED` BrewEvent (not a scientific observation).

## Decision

Epic 2A uses a **history-first** measurement model. Append-only history tables are the scientific and lifecycle sources of truth. `MeasurementRequirement.status` and `MeasurementRecord` current columns are **rebuildable projections** for API/UX convenience. Projection fields may change only when the corresponding history row is appended, and history + projection + related `BrewEvent` rows commit in one database transaction (ADR-004 command atomicity). Destructive overwrite of observation or status history is forbidden.

---

### A. Domain concepts

| Concept | Role |
|---------|------|
| **MeasurementDefinition** | Optional seed catalog: stable `measurement_type` metadata (display name, default unit, typical stage, default requirement level, optional expected range). |
| **MeasurementRequirement** | Per-session obligation for a measurement type on a stage occurrence: planned/estimated baseline, requirement level, and **current** lifecycle status (projection). |
| **MeasurementRecord** | **Current projection** of the captured observation for a CAPTURED requirement (read model only). |
| **MeasurementObservationHistory** | **Append-only source of truth** for scientific values: raw capture, instrument corrections, user revisions, and validation snapshots at each event. |
| **MeasurementStatusHistory** | **Append-only source of truth** for requirement lifecycle transitions (e.g. PENDING → CAPTURED / MISSED / WAIVED). |

History tables are authoritative. Current requirement/record fields are projections and must remain rebuildable from history.

---

### B. History invariant

1. No UPDATE or DELETE of `MeasurementObservationHistory` or `MeasurementStatusHistory` rows.  
2. Current projections (`MeasurementRecord` fields and `MeasurementRequirement.status`) are rebuildable from history.  
3. Projection changes occur only together with the corresponding history append.  
4. History append + projection refresh + related `BrewEvent`(s) (+ idempotency ledger per ADR-006) commit **atomically** in one DB transaction.  
5. A write that changes a current measurement or status field without appending history is an architecture defect.

---

### C. Value kinds and lifecycle

**Value kinds** (orthogonal to requirement lifecycle status):

| Kind | Meaning |
|------|---------|
| `PLANNED` | BrewPlan / recipe target on the requirement |
| `ESTIMATED` | ADR-003 estimate snapshotted onto the plan/requirement |
| `CALCULATED` | Deterministic derivation from other known values (if used on brew day) |
| `MEASURED` | Authoritative captured observation (prefer corrected projection if present, else raw) |
| `MISSING` | Not available; never fabricated |
| `INVALID` | Failed INPUT ERROR validation; not authoritative; not stored as a MeasurementRecord |

**Requirement lifecycle statuses** (current projection of status history):

| Status | Meaning |
|--------|---------|
| `PENDING` | Not yet captured, missed, or waived |
| `CAPTURED` | At least one accepted `RAW_CAPTURE` observation-history row exists |
| `MISSED` | Explicitly marked missed (including ADR-004 skip auto-MISS of REQUIRED) |
| `WAIVED` | Explicit waiver with reason and actor |

---

### D. MeasurementRecord projection

Current read-model fields (always rebuildable from observation-history head / original capture):

- `raw_value`, `raw_unit`  
- `corrected_value`, `corrected_unit` (nullable)  
- Display policy: corrected if present, else raw; value kind `MEASURED`  
- `confidence` (`HIGH` / `MEDIUM` / `LOW`)  
- `instrument`, `method`, `provenance`  
- `validation_class`, `validation_notes` (latest snapshot only)  
- `latest_observation_history_id`  
- `first_captured_at`, `captured_by` from the original `RAW_CAPTURE` (stable identity of first capture)  
- Creating-capture `client_submission_id`  

---

### E. MeasurementObservationHistory

Immutable append-only scientific value history. Each row is a complete snapshot of what was asserted at that moment.

| Field | Notes |
|-------|-------|
| `id` | PK |
| `requirement_id` | FK |
| `measurement_record_id` | FK once projection exists |
| `event_class` | `RAW_CAPTURE` \| `INSTRUMENT_CORRECTION` \| `USER_REVISION` |
| `raw_value`, `raw_unit` | As asserted by this event (nullable when event only adds correction) |
| `corrected_value`, `corrected_unit` | As asserted by this event (nullable) |
| `confidence` | HIGH/MEDIUM/LOW when applicable |
| `instrument`, `method`, `provenance` | Snapshot at event time |
| `validation_class` | `OK` \| `UNUSUAL_VALUE` \| `DOMAIN_CONCERN` |
| `validation_notes` | Immutable warning/context snapshot for this event |
| `reason` | Required for `USER_REVISION` |
| `actor_id` | |
| `occurred_at` | Server authoritative |
| `client_occurred_at` | Optional provenance |
| `client_submission_id` | Idempotency (ADR-006) |
| `payload` | Optional structured context |

**Event classes:**

| Class | Meaning |
|-------|---------|
| `RAW_CAPTURE` | First accepted observation for the requirement |
| `INSTRUMENT_CORRECTION` | Derived/corrected value added without destroying prior raw assertion |
| `USER_REVISION` | Correction of a prior assertion/transcription; requires reason |

---

### F. Correction semantics

**Instrument / data correction**  
Preserves the original physical observation while adding a derived or corrected value (example: temperature-corrected hydrometer reading). Appends `INSTRUMENT_CORRECTION`, emits `MEASUREMENT_INSTRUMENT_CORRECTION`, refreshes the record projection. Prior history rows remain unchanged.

**User revision**  
Corrects a prior assertion or transcription (example: typed `1.050`, later revised to `1.051`). Appends `USER_REVISION` with **required** reason, emits `MEASUREMENT_USER_REVISION`, refreshes the projection. Prior assertions remain in history.

Neither class may destroy prior history.

---

### G. MeasurementStatusHistory

Append-only lifecycle transition ledger. `MeasurementRequirement.status` is a projection of the latest status-history head.

| Field | Notes |
|-------|-------|
| `id` | PK |
| `requirement_id` | FK |
| `from_status` | Prior status |
| `to_status` | New status |
| `reason` | Required for `WAIVED`; optional for `MISSED` |
| `actor_id` | |
| `source_command` | e.g. `CAPTURE`, `MISS`, `WAIVE`, `SKIP_STAGE` |
| `occurred_at` | Server |
| `client_occurred_at` | Optional |
| `client_submission_id` | When applicable |
| `payload` | Optional (e.g. skipped stage code) |

**Locked transitions (Epic 2A):**

| From | To | How |
|------|----|-----|
| `PENDING` | `CAPTURED` | Accepted capture (`RAW_CAPTURE` + status history + events) |
| `PENDING` | `MISSED` | Explicit miss, or ADR-004 skip of owning stage for remaining **REQUIRED** requirements (same transaction) |
| `PENDING` | `WAIVED` | Explicit waive with reason |

Reopening `MISSED` or `WAIVED` is **out of scope for Epic 2A**.  
MISSED/WAIVED never fabricate measured values.  
BrewEvent counterparts (`MEASUREMENT_CAPTURED` / `MISSED` / `WAIVED`) are required in the same transaction; status history remains the scientific lifecycle ledger so audits need not parse session event payloads alone.

---

### H. Validation

Validation runs on capture and on revision/correction when values change.

| Class | Meaning | Behavior |
|-------|---------|----------|
| **INPUT ERROR** | Cannot parse, wrong type, impossible unit, or structurally invalid | **Reject.** No `MeasurementRecord`. No `MeasurementObservationHistory` row. Requirement stays `PENDING`. |
| **UNUSUAL VALUE** | Structurally valid but outside expected/typical range | **Accept and preserve.** Warning stored on the observation-history row. Emit warning BrewEvent. Refresh projection. |
| **DOMAIN CONCERN** | Valid observation that may indicate a process issue | **Accept and preserve.** Contextual warning stored on the history row. Emit warning BrewEvent. Refresh projection. |

An unusual value must not be automatically rejected or silently changed.

**Rejected INPUT ERROR attempts** MAY emit an operational BrewEvent:

`MEASUREMENT_INPUT_REJECTED`

That event is audit/diagnostic metadata only. It **MUST NOT** be treated as a scientific observation and **MUST NOT** create a `MeasurementObservationHistory` row or a `MeasurementRecord`.

Expected ranges come from `MeasurementDefinition` and/or BrewPlan planned targets ± tolerance (seeded in E2A-3).

---

### I. Planned vs actual

- **Planned / estimated** baselines live on the requirement / BrewPlan snapshot (`PLANNED` / `ESTIMATED`).  
- **Actual** values come only from CAPTURED observation history / the record projection (`MEASURED`).  
- Never substitute planned/estimated for measured, or invent measured values for `MISSING` / `MISSED` / `WAIVED`.  
- Target-performance deltas compute only when both a planned/estimated baseline and a measured observation exist.

---

### J. Confidence

`HIGH` / `MEDIUM` / `LOW` express **evidence / measurement quality context** (instrument trust, method care, conditions). They do not mean preference for the number, correctness of the brew, or process success.

---

### K. Provenance

Each accepted observation or lifecycle decision records, as applicable:

- instrument  
- method  
- actor (`actor_id`)  
- server `occurred_at` / first-capture timestamp (authoritative)  
- optional client timestamp (`client_occurred_at` / `client_captured_at`)  
- correction provenance (event class, prior history linkage via record/history ids)  
- reason (required for user revision and waive)  
- validation snapshot (`validation_class`, `validation_notes` on the history row)  
- `client_submission_id`  

---

### L. Atomicity and idempotency

- **ADR-004:** mutating commands commit domain state + side effects + BrewEvents in one transaction; integer `BrewSession.version` for session OCC where applicable.  
- **ADR-006:** `client_submission_id` + idempotency ledger with request fingerprint; successful replay returns the original result without duplicating history rows or version bumps.  
- Measurement capture/correction/revision/miss/waive require `client_submission_id`.

---

### M. Reporting implications

History-first storage must support, without rewriting historical observations:

- planned-vs-actual comparisons  
- completeness (REQUIRED/RECOMMENDED vs CAPTURED/MISSED/WAIVED/PENDING)  
- process adherence (including skip-driven MISSED)  
- target performance (measured vs planned/estimated when both exist)  
- later Epic 5 evidence analysis using immutable observation and status history  

Current projections may optimize reads; reports that need provenance must query history.

---

## Non-goals

- Destructive measurement editing or history UPDATE/DELETE  
- Automatic process diagnosis or AI-authored measurements  
- Numeric 0–1 confidence scoring in 2A  
- Fabricated values for MISSED / WAIVED / MISSING  
- Reopening terminal measurement states (`MISSED` / `WAIVED`) in Epic 2A  
- Epic 3 fermentation measurement behavior  
- Inventory consumption implied by measurement capture (P5 / ADR-004)

## Consequences

- E2A-3 implements definitions, requirements, record projections, observation history, status history, validation, and miss/waive/capture/revision APIs under this ADR.  
- Designs that treat `MeasurementRecord` or requirement status as silently mutable sources of truth without history appends fail architecture review.
