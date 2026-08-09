# ADR-005 — Measurement Integrity, Provenance & Validation

**Status:** Accepted (E2A-0)  
**Date:** 2026-08-09  
**Context:** Brew Day must record actual observations without collapsing Epic 1 value kinds or fabricating missing data. Product Owner locked confidence as HIGH/MEDIUM/LOW (P3).

## Decision

### A. Catalog vs instance

| Concept | Role |
|---------|------|
| **MeasurementDefinition** (optional seed catalog) | Stable `measurement_type` metadata: display name, default unit, typical stage, requirement level template, optional expected range. |
| **MeasurementRequirement** | Per-session (or per-stage-occurrence) obligation: planned value/kind, requirement level, lifecycle status. |
| **MeasurementRecord** | Captured observation for a requirement (CAPTURED). |
| **MeasurementObservationEvent** | Append-only history of raw capture, instrument corrections, and user revisions (never destructive overwrite of history). |

Epic 2A may implement ObservationEvent as a dedicated table or as versioned rows linked to `measurement_records`; destructive in-place overwrite of the original observation is **forbidden**.

### B. Value kinds (orthogonal to lifecycle)

| Kind | Use |
|------|-----|
| `PLANNED` | BrewPlan / recipe target on the requirement |
| `ESTIMATED` | ADR-003 planned estimate snapshotted onto the plan/requirement |
| `CALCULATED` | Derived from other known values (if used on brew day) |
| `MEASURED` | Authoritative captured observation (corrected value if present, else raw) |
| `MISSING` | Not available; never fabricated |
| `INVALID` | Failed INPUT ERROR validation; not authoritative |

Lifecycle status on **MeasurementRequirement**:

| Status | Meaning |
|--------|---------|
| `PENDING` | Not yet captured |
| `CAPTURED` | At least one accepted MeasurementRecord exists |
| `MISSED` | Explicitly marked missed (stage skip/close policy) |
| `WAIVED` | Explicit waiver with reason + actor |

### C. MeasurementRecord fields

- `raw_value`, `raw_unit` (required on capture)  
- `corrected_value`, `corrected_unit` (nullable) — instrument/data correction result  
- `display_value` policy: prefer corrected if present, else raw; kind `MEASURED`  
- `provenance` text / structured note  
- `instrument` (optional)  
- `method` (optional)  
- `confidence`: **`HIGH` | `MEDIUM` | `LOW`** only (P3)  
- `captured_at` (server), optional `client_captured_at`  
- `captured_by` actor_id  
- `client_submission_id` (idempotency; ADR-006)  

Confidence means **evidence/measurement quality context**, not preference for the number.

### D. Non-destructive history — two correction classes

Destructive overwrite of the original observation is forbidden. All changes append history.

#### 1. Instrument / data correction

Example: temperature-corrected hydrometer reading derived from raw SG + wort temperature.

- Stored as correction linked to the same logical measurement  
- Preserves raw observation  
- Audited as `MEASUREMENT_INSTRUMENT_CORRECTION`  
- May update the record’s current `corrected_value` pointer **without deleting** prior correction rows  

#### 2. User revision

Example: brewer typed `1.050` then revises transcription to `1.051`.

- Prior raw/corrected values remain in history  
- New revision row with reason  
- Audited as `MEASUREMENT_USER_REVISION`  
- Current record pointers move forward; history retained  

Both classes remain independently queryable for audit.

### E. Miss / waive

- **Miss:** requires actor; optional note; status → `MISSED`; event `MEASUREMENT_MISSED`. No fabricated value.  
- **Waive:** requires actor + reason; status → `WAIVED`; event `MEASUREMENT_WAIVED`. No fabricated value.  

### F. Validation classifications

Validation runs on capture (and on revision). Classifications:

| Class | Meaning | System behavior |
|-------|---------|-----------------|
| **INPUT ERROR** | Cannot parse, wrong type, impossible unit, or structurally invalid for the measurement type | **Reject** capture; no MeasurementRecord; requirement stays PENDING |
| **UNUSUAL VALUE** | Parses and is structurally valid, but outside expected/typical range | **Accept and preserve**; attach warning; event notes unusual |
| **DOMAIN CONCERN** | Valid observation that may indicate a process problem (e.g., mash temp far from rest) | **Accept and preserve**; attach warning/context for UI/report |

An unusual value must **not** be automatically rejected or silently changed.

Expected ranges come from MeasurementDefinition and/or BrewPlan planned targets ± tolerance configured in 2A seed data.

### G. Planned vs measured reporting

- Planned/estimated values live on requirements / plan snapshots.  
- Measured values come only from CAPTURED records.  
- Target-performance deltas compute only when both planned and measured exist.  
- MISSING/MISSED/WAIVED never receive invented measured values.

### H. Inventory independence

Capturing a measurement never consumes inventory (P5 / ADR-004).

## Non-goals

- Lab LIMS integration  
- Automatic instrument Bluetooth ingestion (may appear later as provenance source)  
- Numeric 0–1 confidence scores in 2A  

## Consequences

- E2A-3 implements requirements seeding, capture/miss/waive, validation classes, and revision/correction history.  
- Reports and close paths must honor non-fabrication.
