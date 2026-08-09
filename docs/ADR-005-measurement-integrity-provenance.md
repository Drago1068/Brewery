# ADR-005 — Measurement Integrity, Provenance & Validation

**Status:** Accepted (E2A-0; strengthened for history-first design before E2A-1)  
**Date:** 2026-08-09  
**Amended:** 2026-08-09 — lock append-only observation/status history; current fields are projections only  
**Context:** Brew Day must record actual observations without collapsing Epic 1 value kinds or fabricating missing data. Product Owner locked confidence as HIGH/MEDIUM/LOW (P3). Measurement integrity is the highest-risk Epic 2A domain: captured values, corrections, transcription revisions, validation warnings, MISSED, and WAIVED must **preserve history**, not become silently mutable fields.

## Decision

### A. Catalog vs instance

| Concept | Role |
|---------|------|
| **MeasurementDefinition** (optional seed catalog) | Stable `measurement_type` metadata: display name, default unit, typical stage, requirement level template, optional expected range. |
| **MeasurementRequirement** | Per-session obligation: planned value/kind, requirement level, **current** lifecycle status (projection). |
| **MeasurementRecord** | Current projection of the captured observation for a CAPTURED requirement (convenience read model). |
| **MeasurementObservationHistory** | **Append-only source of truth** for every accepted observation, instrument correction, and user revision (including validation class/warnings at that moment). |
| **MeasurementStatusHistory** | **Append-only source of truth** for requirement lifecycle transitions (PENDING→CAPTURED/MISSED/WAIVED, and any later allowed transitions). |

**Locked implementation choice:** Epic 2A uses dedicated append-only history tables (not “overwrite the record and hope BrewEvent is enough”). BrewEvents remain the session audit stream; history tables remain the scientific measurement ledger.

### B. Non-negotiable history invariant

1. **No destructive overwrite** of prior observations, corrections, revisions, validation outcomes, miss reasons, or waive reasons.  
2. `MeasurementRecord` current columns (`raw_*`, `corrected_*`, `confidence`, `validation_*`, provenance fields) are a **materialized projection of the latest observation-history head** for UX/API convenience.  
3. Rebuilding the projection from history must always be possible.  
4. APIs may expose “current” values, but must also expose full history.  
5. DELETE of history rows is forbidden. UPDATE of history rows is forbidden.  
6. UPDATE of projection columns is allowed **only** as part of appending a new history row in the **same DB transaction** (ADR-004 command atomicity).

If a write would change a current measurement field without appending history, it is an architecture defect.

### C. Value kinds (orthogonal to lifecycle)

| Kind | Use |
|------|-----|
| `PLANNED` | BrewPlan / recipe target on the requirement |
| `ESTIMATED` | ADR-003 planned estimate snapshotted onto the plan/requirement |
| `CALCULATED` | Derived from other known values (if used on brew day) |
| `MEASURED` | Authoritative captured observation (corrected value if present on current projection, else raw) |
| `MISSING` | Not available; never fabricated |
| `INVALID` | Failed INPUT ERROR validation; not authoritative; **not stored as a MeasurementRecord** |

Lifecycle status on **MeasurementRequirement** (current projection):

| Status | Meaning |
|--------|---------|
| `PENDING` | Not yet captured, missed, or waived |
| `CAPTURED` | At least one accepted observation-history row of class `RAW_CAPTURE` exists |
| `MISSED` | Explicitly marked missed (including skip auto-MISS of REQUIRED) |
| `WAIVED` | Explicit waiver with reason + actor |

Status changes always append `MeasurementStatusHistory` **and** the corresponding `BrewEvent` in the same transaction.

### D. MeasurementObservationHistory (source of truth for values)

Each append-only row captures a complete immutable snapshot of what was asserted at that moment:

| Field | Notes |
|-------|-------|
| `id` | PK |
| `requirement_id` | FK |
| `measurement_record_id` | FK (set once record projection exists) |
| `event_class` | `RAW_CAPTURE` \| `INSTRUMENT_CORRECTION` \| `USER_REVISION` |
| `raw_value`, `raw_unit` | As asserted by this event (nullable for pure correction events that only add corrected_*) |
| `corrected_value`, `corrected_unit` | As asserted by this event (nullable) |
| `confidence` | HIGH/MEDIUM/LOW when applicable |
| `instrument`, `method`, `provenance` | Snapshot at event time |
| `validation_class` | `OK` \| `UNUSUAL_VALUE` \| `DOMAIN_CONCERN` (never INPUT ERROR — those reject) |
| `validation_notes` | Immutable JSON snapshot of warnings/context for this event |
| `reason` | Required for `USER_REVISION`; optional notes otherwise |
| `actor_id` | |
| `occurred_at` | Server authoritative |
| `client_occurred_at` | Optional provenance |
| `client_submission_id` | Idempotency |
| `payload` | Optional extra structured context |

**Projection rule after each successful append:** update `measurement_records` current fields to match this history head (and set `requirements.current_record_id`). Prior history rows remain unchanged.

### E. Two correction classes (both historical)

#### 1. Instrument / data correction

Example: temperature-corrected hydrometer reading derived from raw SG + wort temperature.

- Append `INSTRUMENT_CORRECTION` history row (preserves prior `RAW_CAPTURE` / earlier corrections).  
- Emit `MEASUREMENT_INSTRUMENT_CORRECTION` BrewEvent.  
- Refresh record projection’s `corrected_*` (and validation snapshot if re-validated).  
- Never delete or rewrite the original raw capture row.

#### 2. User revision

Example: brewer typed `1.050` then revises transcription to `1.051`.

- Append `USER_REVISION` history row with **required** `reason`.  
- Emit `MEASUREMENT_USER_REVISION` BrewEvent.  
- Refresh record projection to the revised raw/corrected values.  
- Prior raw/corrected assertions remain in history.

Both classes are independently queryable. “Current” API reads use the projection; audit/scientific review uses history.

### F. MeasurementStatusHistory (source of truth for MISSED / WAIVED / CAPTURED)

Requirement `status` is a projection. Every transition appends status history:

| Field | Notes |
|-------|-------|
| `id` | PK |
| `requirement_id` | FK |
| `from_status` | e.g. PENDING |
| `to_status` | CAPTURED / MISSED / WAIVED |
| `reason` | Required for WAIVED; optional for MISSED; null for CAPTURED |
| `actor_id` | |
| `occurred_at` | Server |
| `client_occurred_at` | Optional |
| `client_submission_id` | When applicable |
| `source_command` | e.g. `CAPTURE`, `MISS`, `WAIVE`, `SKIP_STAGE` |
| `payload` | Optional (e.g. skip stage code) |

Rules:

- **Miss:** `PENDING → MISSED`; status history + `MEASUREMENT_MISSED`; **no** fabricated MeasurementRecord / observation values.  
- **Waive:** `PENDING → WAIVED`; reason required; status history + `MEASUREMENT_WAIVED`; **no** fabricated values.  
- **Capture:** `PENDING → CAPTURED`; status history + observation `RAW_CAPTURE` + `MEASUREMENT_CAPTURED`.  
- **Skip auto-MISS (ADR-004):** for each remaining REQUIRED PENDING on the skipped stage, append status history `PENDING → MISSED` with `source_command=SKIP_STAGE` in the same transaction as the skip.  
- Re-opening MISSED/WAIVED back to PENDING is **out of scope for 2A** (forbidden unless a future ADR allows it with history).

BrewEvent alone is not sufficient scientific ledger for miss/waive; status history is required so audits do not depend on parsing session event payloads.

### G. Validation classifications

Validation runs on capture and on revision/correction (when values change). Classifications:

| Class | Meaning | System behavior |
|-------|---------|-----------------|
| **INPUT ERROR** | Cannot parse, wrong type, impossible unit, or structurally invalid | **Reject**; no observation history row; no record projection create/update; requirement stays PENDING |
| **UNUSUAL VALUE** | Structurally valid, outside expected/typical range | **Accept**; persist value; store `validation_class` + notes **on the history row**; emit warning BrewEvent; refresh projection |
| **DOMAIN CONCERN** | Valid observation that may indicate a process issue | **Accept**; persist; store class/notes on history row; emit warning; refresh projection |

An unusual value must **not** be automatically rejected or silently changed.

**Warning persistence:** validation warnings live immutably on the observation-history row that produced them. They must not exist only as an overwritten `measurement_records.validation_notes` field. The record projection may copy the latest warning snapshot for convenience.

Expected ranges come from MeasurementDefinition and/or BrewPlan planned targets ± tolerance (E2A-3 seed).

### H. MeasurementRecord projection fields

Convenience current view (always rebuildable):

- `raw_value`, `raw_unit`  
- `corrected_value`, `corrected_unit` (nullable)  
- display policy: corrected if present else raw; kind `MEASURED`  
- `confidence` HIGH/MEDIUM/LOW  
- `instrument`, `method`, `provenance`  
- `validation_class`, `validation_notes` (latest)  
- `captured_at` / `captured_by` from the original `RAW_CAPTURE` head (do not shift “first captured” identity when revising)  
- `latest_observation_history_id`  
- `client_submission_id` of the creating capture (stable)

Confidence means evidence/measurement quality context, not preference for the number.

### I. Planned vs measured reporting

- Planned/estimated values live on requirements / plan snapshots (immutable after plan create except via explicit future ADR).  
- Measured values come only from CAPTURED observation history / projection.  
- Target-performance deltas compute only when both planned and measured exist.  
- MISSING/MISSED/WAIVED never receive invented measured values.

### J. Inventory independence

Capturing a measurement never consumes inventory (P5 / ADR-004).

## Non-goals

- Lab LIMS integration  
- Automatic instrument Bluetooth ingestion (may appear later as provenance source)  
- Numeric 0–1 confidence scores in 2A  
- Editing history rows  
- Silent in-place mutation of current measurement fields without history append  

## Consequences

- E2A-3 must implement observation history + status history before or with capture/miss/waive APIs.  
- Schema sketch must include `measurement_observation_history` and `measurement_status_history` as append-only.  
- Reviews fail any design where MISSED/WAIVED/corrections/warnings are only mutable columns on a single row.
