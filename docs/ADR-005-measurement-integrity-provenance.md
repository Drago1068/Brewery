# ADR-005 — Measurement Integrity, Provenance & Validation

## Metadata

**Status:** Accepted  
**Date:** 2026-08-09  
**Amended:** 2026-08-09 — history-first measurement architecture locked for Epic 2A.  
**Context:** Brew Day must record actual observations without collapsing planned, estimated, calculated, measured, missing, or invalid values. Captures, corrections, user revisions, validation warnings, MISSED, and WAIVED states must preserve history rather than become silently mutable fields. Epic 2A uses HIGH / MEDIUM / LOW measurement confidence.

## Decision

Epic 2A uses a history-first measurement model.

Append-only measurement history is authoritative.

Current `MeasurementRecord` and `MeasurementRequirement` fields are projections for API/UI convenience and must always be rebuildable from history.

Projection updates, history rows, BrewEvents, idempotency records, and relevant session version changes must commit atomically.

Destructive overwrite of scientific or lifecycle history is forbidden.

## A. Domain Concepts

| Concept | Definition |
|---------|------------|
| **MeasurementDefinition** | Optional seed/catalog metadata for `measurement_type`, display name, default unit, typical stage, default requirement level, and optional expected range. |
| **MeasurementRequirement** | Per-session/per-stage obligation containing planned or estimated baseline, requirement level, and current lifecycle status projection. |
| **MeasurementRecord** | Current read projection for an accepted captured observation. |
| **MeasurementObservationHistory** | Append-only scientific source of truth for raw captures, instrument/data corrections, user revisions, provenance, confidence, and validation snapshots. |
| **MeasurementStatusHistory** | Append-only source of truth for requirement lifecycle transitions. |

## B. History Invariants

1. No UPDATE or DELETE of `MeasurementObservationHistory`.  
2. No UPDATE or DELETE of `MeasurementStatusHistory`.  
3. Current projections must be rebuildable from history.  
4. Projection changes require a corresponding history append.  
5. History + projection + BrewEvent + idempotency record commit atomically.  
6. Any current-value/status mutation without history is an architecture defect.

## C. Value Kinds

| Kind | Definition |
|------|------------|
| `PLANNED` | BrewPlan target. |
| `ESTIMATED` | Predictive value from ADR-003 or future approved formula. |
| `CALCULATED` | Deterministic derived value. |
| `MEASURED` | Accepted observation; corrected value may be preferred for display while raw history remains preserved. |
| `MISSING` | Unavailable; never fabricated. |
| `INVALID` | Rejected INPUT ERROR; never accepted as scientific measurement truth. |

## D. Requirement Lifecycle

| Status | Definition |
|--------|------------|
| `PENDING` | Not captured, missed, or waived. |
| `CAPTURED` | At least one accepted `RAW_CAPTURE` exists. |
| `MISSED` | Explicitly missed or auto-MISSED under ADR-004 stage-skip rules. |
| `WAIVED` | Explicitly waived with actor and required reason. |

Epic 2A permits:

- `PENDING` → `CAPTURED`  
- `PENDING` → `MISSED`  
- `PENDING` → `WAIVED`  

Reopening `MISSED` / `WAIVED` is out of scope.

`MISSED` and `WAIVED` never create fabricated `MeasurementRecord`s.

## E. MeasurementRecord Projection

| Field |
|-------|
| `raw_value` |
| `raw_unit` |
| `corrected_value` |
| `corrected_unit` |
| display_value policy |
| `confidence` |
| `instrument` |
| `method` |
| `provenance` |
| `validation_class` |
| `validation_notes` |
| `latest_observation_history_id` |
| `first_captured_at` |
| `captured_by` |
| creating `client_submission_id` |

The projection represents the latest accepted state only. It is not historical truth.

## F. MeasurementObservationHistory

| Field | Notes |
|-------|-------|
| `id` | PK |
| `requirement_id` | FK |
| `measurement_record_id` | FK |
| `event_class` | `RAW_CAPTURE` \| `INSTRUMENT_CORRECTION` \| `USER_REVISION` |
| `raw_value` / `raw_unit` | As asserted by this event |
| `corrected_value` / `corrected_unit` | As asserted by this event |
| `confidence` | HIGH / MEDIUM / LOW when applicable |
| `instrument` | Snapshot |
| `method` | Snapshot |
| `provenance` | Snapshot |
| `validation_class` | Snapshot |
| `validation_notes` | Snapshot |
| `reason` | Required for `USER_REVISION` |
| `actor_id` | Actor |
| `occurred_at` | Server authoritative |
| `client_occurred_at` | Optional |
| `client_submission_id` | Idempotency |
| `payload` | Optional |

`event_class` exactly:

- `RAW_CAPTURE`  
- `INSTRUMENT_CORRECTION`  
- `USER_REVISION`  

History rows are immutable.

## G. Correction Semantics

### Instrument / Data Correction

Preserves original physical observation.

Example: temperature correction applied to a hydrometer reading.

Append `INSTRUMENT_CORRECTION`.  
Emit `MEASUREMENT_INSTRUMENT_CORRECTION`.  
Refresh current projection.  
Never rewrite `RAW_CAPTURE`.

### User Revision

Corrects a prior assertion or transcription.

Example: `1.050` entered accidentally and corrected to `1.051`.

Requires reason.  
Append `USER_REVISION`.  
Emit `MEASUREMENT_USER_REVISION`.  
Refresh projection.  
Preserve all prior assertions.

## H. MeasurementStatusHistory

| Field | Notes |
|-------|-------|
| `id` | PK |
| `requirement_id` | FK |
| `from_status` | Prior status |
| `to_status` | New status |
| `reason` | Required for waive |
| `actor_id` | Actor |
| `source_command` | Command that caused the transition |
| `occurred_at` | Server |
| `client_occurred_at` | Optional |
| `client_submission_id` | When applicable |
| `payload` | Optional |

Every lifecycle transition writes:

- `MeasurementStatusHistory`  
- corresponding BrewEvent  
- projection update  

in one transaction.

Skip-stage REQUIRED auto-MISS follows ADR-004.

## I. Validation

| Class | Meaning | Behavior |
|-------|---------|----------|
| **INPUT ERROR** | Cannot parse, invalid unit/type, or structurally impossible input. | Reject request. Do not create `MeasurementRecord`. Do not create `MeasurementObservationHistory`. Requirement remains `PENDING`. May emit operational `MEASUREMENT_INPUT_REJECTED` BrewEvent. |
| **UNUSUAL VALUE** | Valid measurement outside expected/typical range. | Accept and preserve. Store warning on immutable observation history. Emit warning event/context. |
| **DOMAIN CONCERN** | Valid observation that may indicate a brewing-process concern. | Accept and preserve. Store contextual warning. Do not diagnose automatically. |

Never silently change unusual values.

## J. Confidence

Allowed values only:

- `HIGH`  
- `MEDIUM`  
- `LOW`  

Confidence represents evidence/measurement-quality context.

It does not mean:

- whether the brewer likes the value;  
- whether the value matches the target;  
- certainty of diagnosis.

## K. Provenance

Preserve as applicable:

- instrument  
- method  
- actor  
- server timestamp  
- optional client timestamp  
- correction method  
- revision reason  
- validation snapshot  
- `client_submission_id`  

Server timestamp remains authoritative for persistence/audit ordering.

## L. Planned vs Actual

Planned and estimated values come from BrewPlan snapshots.

Measured values come only from accepted measurement history.

Never replace missing measured data with planned or estimated values.

Reporting must not calculate planned-vs-actual deltas for missing measurements.

## M. Atomicity and Idempotency

Cross-reference ADR-004 and ADR-006.

Every accepted measurement mutation must commit all required:

- history rows  
- projection updates  
- BrewEvents  
- status transitions  
- idempotency records  
- applicable `BrewSession.version` increment  

in one PostgreSQL transaction.

Failure rolls back the complete command.

Exact idempotent replay must not duplicate history, events, or version increments.

## N. Reporting and Future Use

The architecture must support:

- data completeness  
- planned vs actual  
- target-performance reporting  
- scientific audit  
- Epic 5 evidence/hypothesis analysis  

without rewriting prior observations.

## Non-Goals

Epic 2A does not implement:

- destructive measurement editing  
- automatic process diagnosis  
- numeric 0–1 confidence  
- fake values for MISSED or WAIVED  
- reopening MISSED or WAIVED  
- fermentation measurement workflows owned by Epic 3  

## Consequences

Measurement history becomes trustworthy evidence across Brew Day, fermentation, sensory evaluation, and future recipe-learning workflows.

BrewEvent remains the session audit stream.

`MeasurementObservationHistory` and `MeasurementStatusHistory` remain the specialized scientific/lifecycle ledgers.
