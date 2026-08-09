# E2A-3 IMPLEMENTATION REVIEW PACKAGE

**Increment:** E2A-3 — Brew-Day Measurement Integrity & Provenance  
**Date:** 2026-08-09  
**Governing:** ADR-005 (+ ADR-004 skip/close contracts, ADR-006 OCC/idempotency)

---

## 1. Commit SHA

_(filled at commit time)_

## 2. Working-tree status

Clean after E2A-3 commit. No E2A-4 timer code.

## 3. Files added/modified

### Added
- `backend/alembic/versions/007_brew_day_measurements.py`
- `backend/app/domain/measurement.py`
- `backend/app/services/measurements.py`
- `backend/tests/test_measurements.py`
- `backend/tests/test_migration_007.py`
- `backend/scripts/verify_e2a3_schema.py`
- `docs/EPIC_2A_E2A3_IMPLEMENTATION_REVIEW_PACKAGE.md`

### Modified
- models, enums, brew_day schemas/API
- `brew_session.py` — generate requirements on session create
- `brew_transitions.py` — skip auto-MISS + close REQUIRED gate
- migration guard tests for 005/006

## 4. Migration 007 details

- `007_brew_day_measurements`, `down_revision=006`
- Tables: definitions, requirements, records, observation_history, status_history
- Seeds 8 measurement definitions
- `app_meta` → increment 7 / schema 007
- Downgrade restores 006

## 5. MeasurementDefinition catalog / seed decisions

| Code | Stage | Level | Unit | Range |
|------|-------|-------|------|-------|
| MASH_TEMP | MASH | REQUIRED | C | NULL (not invented) |
| MASH_PH | MASH | RECOMMENDED | pH | NULL |
| PRE_BOIL_VOLUME | BOIL | REQUIRED | L | NULL |
| PRE_BOIL_GRAVITY | BOIL | RECOMMENDED | SG | NULL |
| POST_BOIL_VOLUME | BOIL | REQUIRED | L | NULL |
| OG | CHILL_KNOCKOUT | REQUIRED | SG | NULL |
| KNOCKOUT_TEMP | CHILL_KNOCKOUT | REQUIRED | C | NULL |
| YEAST_PITCH_TEMP | YEAST_PITCH | REQUIRED | C | NULL |

All expected min/max left **NULL** — no fabricated scientific authority.

## 6. MeasurementRequirement generation rules

On BrewSession create: for each active definition, attach to matching stage occurrence.  
Planned values from BrewPlan calc/recipe snapshot when present (`OG` ← ESTIMATED calc; volumes ← batch PLANNED fallback; mash temp ← mash step PLANNED). Absence remains absence. Never MEASURED from plan.

## 7. MeasurementRecord projection design

Current-only projection: raw/corrected, MEASURED kind, confidence, instrument/method/provenance, validation snapshot, latest_observation_history_id, first_captured_at, captured_by, creating client_submission_id. Display = corrected if present else raw.

## 8. Observation-history implementation

Append-only `RAW_CAPTURE` / `INSTRUMENT_CORRECTION` / `USER_REVISION`. No update/delete API.

## 9. Status-history implementation

Append-only PENDING→CAPTURED/MISSED/WAIVED. Requirement.status is projection.

## 10. Capture behavior

Atomic: validate → RAW_CAPTURE → record projection → CAPTURED status history → MEASUREMENT_CAPTURED (+ VALIDATION_WARNING) → version +1 → idempotency.

## 11. Correction behavior

INSTRUMENT_CORRECTION preserves raw; updates corrected projection; emits MEASUREMENT_INSTRUMENT_CORRECTION.

## 12. Revision behavior

USER_REVISION requires reason; prior assertion retained in history; projection raw updated; MEASUREMENT_USER_REVISION.

## 13. Miss/Waive behavior

PENDING→MISSED/WAIVED; status history + BrewEvent; no MeasurementRecord. Waive requires reason.

## 14. Validation behavior

INPUT ERROR → 422, no scientific history. UNUSUAL/DOMAIN_CONCERN accepted with immutable warning snapshot + VALIDATION_WARNING event when applicable.

## 15. Confidence enforcement

HIGH/MEDIUM/LOW only; unsupported → 422.

## 16. Skip-stage integration

SKIP_STAGE auto-MISSes REQUIRED PENDING on skipped stage in same txn; RECOMMENDED stay PENDING.

## 17. Close-gate integration

CLOSE rejects with `REQUIRED_MEASUREMENTS_PENDING` if any REQUIRED PENDING. CAPTURED/MISSED/WAIVED/RECOMMENDED PENDING do not block. No fabrication.

## 18. OCC behavior

expected_session_version; stale → 409 CONCURRENCY_CONFLICT; +1 once on success.

## 19. Idempotency behavior

Ledger-first; exact replay; fingerprint conflict → 409; no duplicate history/events/version on replay.

## 20. Atomicity verification

Capture BrewEvent failure aborts before commit/idempotency (tested).

## 21. Read APIs

- `GET .../requirements`
- `GET .../observation-history`
- `GET .../status-history`  
Side-effect free.

## 22. Tests added

`test_measurements.py`, `test_migration_007.py`; transition skip hook updated.

## 23. Full test results

```text
117 passed, 1 skipped
```

## 24. Epic 1 regression results

Golden ADR-003 + Epic 1 suite green. No formula changes.

## 25. E2A-1/E2A-2 regression results

Plan/session/idempotency and transition/BrewEvent tests green.

## 26. Docker migration/persistence verification

`006→007`, `007→006`, re-upgrade to `007 (head)` verified.

## 27. Known limitations

- No timers/reports/handoff/UI
- INPUT ERROR does not emit MEASUREMENT_INPUT_REJECTED (avoids half-committed diagnostic txn)
- Soft structural sanity checks only; definition ranges intentionally NULL
- U1 catalog is conservative starter set

## 28. Architecture deviations

None vs ADR-005 / skip-close contracts.

## 29. Explicit confirmation — no E2A-4 code

No `brew_timers` migration/service/API implemented.

---

E2A-3 COMPLETE — READY FOR ARCHITECTURE REVIEW
