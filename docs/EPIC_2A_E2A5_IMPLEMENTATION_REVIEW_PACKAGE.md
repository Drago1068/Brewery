# E2A-5 IMPLEMENTATION REVIEW PACKAGE

**Increment:** E2A-5 — Brew-Day Audit, Reporting & Fermentation Handoff  
**Date:** 2026-08-09  
**Governing:** ADR-004, ADR-005, ADR-006

---

## 1. Commit SHA

`PENDING_E2A5_COMMIT` (updated after commit)

## 2. Working-tree status

Clean after E2A-5 commit. No E2A-6 UI and no Epic 3 FermentationSession.

## 3. Files added/modified

### Added
- `backend/alembic/versions/009_fermentation_handoffs.py`
- `backend/app/domain/brew_day_report.py`
- `backend/app/services/brew_day_report.py`
- `backend/app/services/fermentation_handoff.py`
- `backend/tests/test_brew_day_report.py`
- `backend/tests/test_fermentation_handoff.py`
- `backend/tests/test_e2a5_backend_journey.py`
- `backend/tests/test_migration_009.py`
- `backend/scripts/verify_e2a5_schema.py`
- `backend/scripts/verify_e2a5_persist.py`
- `docs/EPIC_2A_E2A5_IMPLEMENTATION_REVIEW_PACKAGE.md`

### Modified
- `backend/app/db/models.py` — `FermentationHandoff`
- `backend/app/domain/enums.py` — `FERMENTATION_HANDOFF_CREATED`
- `backend/app/schemas/brew_day.py` — handoff request
- `backend/app/api/v1/brew_day.py` — report + handoff routes
- `backend/app/services/brew_transitions.py` — CLOSE payload documents no auto-handoff
- Migration guards 005–008 (allow 009; forbid 010)
- Close/abort hardening tests in `test_brew_transitions.py`

## 4. Migration 009 details

- Revision `009_fermentation_handoffs`, `down_revision = "008"`
- Creates `fermentation_handoffs` only
- Unique `(brew_session_id)` — at most one handoff per session
- `app_meta` → increment `9` / schema `009`
- Downgrade restores `8` / `008`
- Migrations 005–008 unmodified

## 5. FermentationHandoff schema

| Column | Role |
|--------|------|
| `id` | PK |
| `brewery_id` | Ownership |
| `brew_session_id` | Unique session link |
| `brew_plan_id` | Plan baseline |
| `recipe_version_id` | Immutable recipe baseline identity |
| `client_submission_id` | Idempotency provenance |
| `created_by` / `created_at` | Handoff provenance |
| `brew_day_closed_at` | Close timestamp |
| `payload` | Immutable JSONB boundary context |

No `FermentationSession` table.

## 6. Report/read-model architecture

`GET /api/v1/brew-sessions/{id}/report` builds a derived read model from:
- BrewSession / BrewPlan snapshots
- Measurement requirements + records + observation history
- Stage occurrences + BrewEvents
- BrewTimers (read-only list)

Zero writes: no events, projections, version, idempotency, timers, or handoff.

Independent dimensions; `overall_brew_score` is always `null`.

## 7. Completeness behavior

REQUIRED and RECOMMENDED counted separately for CAPTURED / MISSED / WAIVED / PENDING.  
MISSED/WAIVED never become fabricated measurements.

## 8. Process-adherence behavior

Exposes completed/skipped/pending/active stages, skip reasons, pause/resume counts, abort info.  
Skipped stages remain visible after successful close.

## 9. Planned-vs-actual behavior

Per requirement:
- planned value/kind/unit
- actual display value/kind/unit when CAPTURED
- delta / percent_delta only when comparison available
- missing actual → `ACTUAL_MISSING`, no delta
- incompatible units → `INCOMPATIBLE_UNITS`
- volume/temp conversion via `UNIT_CONVERSION` v1 with provenance fields

## 10. Confidence/provenance behavior

Measurement quality block includes confidence, instrument/method, validation, correction flag, raw vs corrected vs display, and observation-history flags (`has_raw_capture`, `has_instrument_correction`, `has_user_revision`).  
No numeric pseudo-score from HIGH/MEDIUM/LOW.

## 11. Timer evidence behavior

Timers listed with label/target/timestamps/status/`computed_past_due`/stage association.  
Evidence only; overruns appear in deviations without driving process state.

## 12. Warning/deviation behavior

Evidence-only list: skipped stages, missed/waived measurements, validation warnings, timer overrun/elapsed, readiness acknowledgement (YELLOW/RED not reinterpreted as GREEN), abort.

## 13. Close hardening

CLOSE_SESSION:
- requires `IN_PROGRESS` (not PAUSED)
- blocks on REQUIRED PENDING (`REQUIRED_MEASUREMENTS_PENDING`)
- allows CAPTURED/MISSED/WAIVED; RECOMMENDED PENDING OK
- no fabrication
- `SESSION_CLOSED` with `fermentation_handoff_created: false`
- no automatic handoff

## 14. Abort hardening

ABORT_SESSION requires non-blank reason (`ABORT_REASON_REQUIRED`).  
Preserves unresolved measurements; no handoff; no inventory consume; history retained.  
Report classifies as `ABORTED_INCOMPLETE`.

## 15. Handoff eligibility

Only `CLOSED`. Rejects:
- `ABORTED` → `SESSION_ABORTED_NO_HANDOFF`
- `IN_PROGRESS` / `PAUSED` / `PLANNED` → `SESSION_NOT_CLOSED_FOR_HANDOFF`
- existing handoff / `HANDED_OFF` → `FERMENTATION_HANDOFF_ALREADY_EXISTS`

## 16. Handoff payload and missing-data behavior

Payload separates planned vs actual for OG, knockout temp, yeast pitch temp, transferred volume.  
Example honesty:
- Planned OG ESTIMATED vs Actual OG MEASURED
- MISSED → status MISSED / value null (never recipe estimate as actual)
- Boundary statement: Epic 2 facts vs Epic 3 responsibilities; `claims_fermentation_readiness: false`

## 17. CLOSED→HANDED_OFF behavior

Atomic: handoff row + status transition + `FERMENTATION_HANDOFF_CREATED` + version +1 + idempotency.

## 18. OCC behavior

ADR-006 order: idempotency → replay → conflict → OCC → mutate → version +1 once.

## 19. Idempotency behavior

Exact replay returns original success even after `HANDED_OFF`.  
Different second attempt rejected.

## 20. Atomicity verification

Event-failure injection on handoff: no commit / partial persist.

## 21. Full backend journey test

`tests/test_e2a5_backend_journey.py`:
start → timer observe-elapsed (process unchanged) → close (no auto handoff) → report → explicit handoff → HANDED_OFF with OG honesty.

## 22. Restart/persistence verification

| Verified | Result |
|----------|--------|
| upgrade 008→009 | OK |
| downgrade 009→008 | OK (meta 008; handoffs removed) |
| re-upgrade →009 | OK |
| Postgres restart | schema 009, increment 9, tables present |
| Row-level timer/handoff insert | **Not verified** — docker DB had no brewery/session seed |

Honest limitation: schema/meta durability proven; live row-level journey persistence still needs a seeded BrewSession environment.

## 23. Tests added

- report domain/service tests
- handoff eligibility/honesty/OCC/idempotency/atomicity
- close/abort hardening
- canonical E2A-5 journey
- migration 009 guards

## 24. Full test results

```
167 passed, 1 skipped
```

## 25. Epic 1 regression results

Golden calculations included in full suite — unchanged.  
`tests/test_calculations_golden.py` passes within full run.

## 26. E2A-1/2/3/4 regression results

Full suite includes prior brew-day, measurement, timer, and transition tests — all green.  
Timers still never drive process; GET timers/report remain read-only; histories append-only.

## 27. Docker migration verification

See §22. Backend image rebuilt; alembic head = 009.

## 28. Known limitations

- No seeded brewery/session in local docker Postgres → row-level restart insert skipped
- BrewAction checklist depth still lightweight
- No live HTTP E2E against running API stack in this package
- Epic 3 fermentation domain intentionally absent

## 29. Architecture deviations, if any

None material. Handoff uses dedicated POST (not a transition-command enum value) while preserving CLOSED→HANDED_OFF semantics and ADR event naming.

## 30. Explicit confirmation no E2A-6 or Epic 3 code was implemented

Confirmed: no guided Brew-Day UI, no FermentationSession, no fermentation measurements/targets/terminal gravity, no packaging/sensory, no brew-quality score, no background timer workers.

---

E2A-5 COMPLETE — READY FOR ARCHITECTURE REVIEW
