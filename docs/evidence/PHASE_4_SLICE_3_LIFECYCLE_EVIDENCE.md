# Phase 4 Slice 3 — Fermentation Lifecycle, Completion & Invalidation

## Identity

| Field | Value |
|---|---|
| Input commit | `815685901c3928b2fc618b4bd6c4e358e5131f7d7` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| Slice scope | Fermentation lifecycle transitions, completion assessment/confirmation, invalidation |

## Architecture

- **Migration:** `0006_phase4_lifecycle_completion` — session lifecycle timestamps, `activation_ordinal`, `fermentation_completion_assessments`, versioned handoff columns
- **Domain:** `FermentationCompletionAssessment`, extended `FermentationSession` / `FermentationStageInstance` / `PackagingReadinessHandoff`
- **Application:**
  - `lifecycle.py` — §9.4 command allowlist / invalid transition guard
  - `transitions.py` — Pause, Resume, Abort
  - `completion.py` — F1–F4 eligibility, `CompleteFermentation`, §14.6 invalidation/reactivation
  - `measurements.py` — hooks gravity correction/record invalidation after confirmation
- **API:** `POST /{id}/commands/pause|resume|abort|complete-fermentation`
- **Read model:** lifecycle timestamps, current completion assessment, stage `activation_ordinal`

## Lifecycle state table (Slice 3 implemented commands)

| CURRENT | COMMAND | NEXT | Notes |
|---|---|---|---|
| ACTIVE | PauseFermentationSession | PAUSED | `pause_origin_state=ACTIVE` |
| PAUSED (origin ACTIVE) | ResumeFermentationSession | ACTIVE | restores origin only |
| ACTIVE/PAUSED/FERM_COMPLETE/CONDITIONING/COND_COMPLETE | AbortFermentationSession | ABORTED | reason 10–1000 chars |
| ACTIVE | CompleteFermentation | FERMENTATION_COMPLETE | F1–F4 or override |
| FERMENTATION_COMPLETE+ | gravity correction (non-note) | ACTIVE | §14.6 invalidation + §9.8 reactivation |

## Transition contract evidence

| Case | Test | Result |
|---|---|---|
| Valid complete (stable gravity seed) | `test_complete_fermentation_success` | PASS |
| Invalid pause from FERMENTATION_COMPLETE | `test_invalid_transition_from_fermentation_complete` | PASS |
| Ineligible complete persists assessment | `test_complete_fermentation_ineligible_persists_assessment` | PASS |
| Pause/resume origin | `test_pause_resume_preserves_origin` | PASS |
| Abort from PAUSED | `test_abort_from_paused` | PASS |
| Idempotency replay | `test_complete_fermentation_idempotency_replay` | PASS |
| PG complete vs measurement race | `test_concurrent_complete_vs_measurement_one_winner` | PASS |

## Completion assessment evidence

- F1 consumes Slice 2 `phase4-stable-gravity-v1` via `derived_gravity.py` (no duplicate algorithm)
- Failed assessment: `INSUFFICIENT_EVIDENCE` row + journal + revision increment + `422 COMPLETION_INELIGIBLE`
- Success: `COMPLETION_CONFIRMED` or `COMPLETION_OVERRIDDEN`; sets `fermentation_first_completed_at` / `fermentation_current_completed_at`
- Override obeys §14.5 (reason length, ≥1 gravity leaf, cannot bypass F4)

## Invalidation / reassessment evidence

- Gravity correction after confirmation returns session to `ACTIVE`, reactivates `ACTIVE_FERMENTATION` (`activation_ordinal` increment), preserves first completion timestamp, marks assessment `COMPLETION_INVALIDATED`
- CLOSED path invalidates current handoff without reopening session (implementation in `invalidate_after_fermentation_affecting_evidence`)
- No informal undo command; invalidation is evidence-driven per §14.6

## Slice 3 traceability ledger

| REQUIREMENT_ID | SPEC_REFERENCE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LAYER | STATUS |
|---|---|---|---|---|---|
| P4-FR-015 | §9.4 | `lifecycle.py`, `transitions.py`, `completion.py` | `test_phase4_lifecycle.py` | API_INTEGRATION | PASS |
| P4-FR-016 | §9.4 | `lifecycle.py` | `test_invalid_transition_*` | API_INTEGRATION | PASS |
| P4-FR-017 | §9.3 | `transitions.py` | `test_pause_resume_preserves_origin` | POSTGRESQL | PASS |
| P4-FR-018 | §9.6/§9.8 | journal events only | — | JOURNAL | PARTIAL (timers FR-048+) |
| P4-FR-019 | §9.4 | `completion.py` | `test_complete_fermentation_success` | API_INTEGRATION | PASS |
| P4-FR-020 | §14 | assessment kind separation | domain/API | API_INTEGRATION | PASS |
| P4-FR-021 | §9.6 | `transitions.py` | `test_abort_*` | API_INTEGRATION | PASS |
| P4-FR-039 | §14.2 | `completion.py` | `test_complete_fermentation_ineligible_*` | API_INTEGRATION | PASS |
| P4-FR-040 | §14.2 | `completion.py` | `test_complete_fermentation_ineligible_*` | POSTGRESQL | PASS |
| P4-FR-041 | §14.2 | `completion.py` | `test_complete_fermentation_success` | API_INTEGRATION | PASS |
| P4-FR-042 | §14.5 | `completion.py` | `test_complete_override_*` | API_INTEGRATION | PASS |
| P4-FR-043 | §14.6 | `completion.py`, `measurements.py` | `test_gravity_correction_invalidates_completion` | POSTGRESQL | PASS |
| P4-AC-012 | §9.4 matrix | API | `test_invalid_transition_*` | API_INTEGRATION | PASS |
| P4-AC-022 | §14.2 | API | ineligible test | POSTGRESQL | PASS |
| P4-AC-023 | §14.2 | API | success test | POSTGRESQL | PASS |
| P4-AC-024 | §14.6 | API | invalidation test | POSTGRESQL | PASS |
| P4-AC-055 | §14.2 | API | ineligible test | POSTGRESQL | PASS |
| P4-AC-065 | §32 R3 | PG | closure concurrency test | POSTGRESQL | PASS |
| P4-AC-066 | §31 | API | idempotency replay test | POSTGRESQL | PASS |
| P4-ADV-002 | §32 | PG | closure concurrency test | POSTGRESQL | PASS |
| P4-ADV-006 | §14.6 | API | invalidation test | POSTGRESQL | PASS |

## Regression evidence (Docker PostgreSQL, TEST_USE_POSTGRES=1)

| Gate | Suite | Result |
|---|---|---|
| PHASE_4_SLICE_3 | lifecycle + security + closure + migration | 42 passed (combined run) |
| PHASE_4_SLICE_2_REGRESSION | slice2 closure + measurements | PASS |
| PHASE_3_REGRESSION | migration regression + phase3 api/invariants + brew_day_api | PASS |
| PHASE_2_REGRESSION | calculations + core | PASS |
| PHASE_3_MIGRATIONS_UNCHANGED | `phase3_migration_regression.py` | PASS |
| MIGRATION_ACCEPTANCE | `0006` upgrade + round-trip | PASS |

## Scope control

- Conditioning lifecycle commands (`StartConditioning`, `CompleteConditioning`, `SkipConditioning`) not implemented (Slice 4+)
- Packaging readiness/handoff/close not implemented (later slice)
- Timer/reminder persistence (P4-FR-048+) deferred; journal records lifecycle decisions
- Frontend / Playwright: NOT_REQUIRED for Slice 3 API-first increment

## Self-review notes

- Invalid transition, duplicate operation replay, stale revision race, post-confirmation gravity correction invalidation, and cross-owner denial exercised
- Stable-gravity completion path tested via seeded leaves + API complete; live 24h-spaced entry remains Slice 2 time-window constraint
- P4-FR-018 timer child rows deferred until timer slice; journal/audit captures lifecycle decisions
