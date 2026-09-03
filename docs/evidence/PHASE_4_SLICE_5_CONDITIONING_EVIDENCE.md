# Phase 4 Slice 5 — Conditioning Lifecycle & Fermentation Handoff

## Identity

| Field | Value |
|---|---|
| Input commit | `fdf209100f4bc6fe778dd37c6ba94b5359878535` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice scope | Conditioning lifecycle; fermentation→conditioning handoff |

## Architecture

- **Application:** `conditioning.py` — `StartConditioning`, `SkipConditioning`, `CompleteConditioning`, §14.3 eligibility, conditioning-only §14.6 invalidation
- **Child effects:** conditioning timers/reminders on start; primary timer complete; cancel on predecessor invalidation
- **Plan:** sparse-valid snapshot defaults `conditioning_required=false`; optional mode/duration/temperature fields
- **Start materialization:** only `PITCH_CONFIRMED` + `ACTIVE_FERMENTATION` stage rows (§8.4); CONDITIONING created solely by `StartConditioning`
- **API:** `commands/start-conditioning`, `skip-conditioning`, `complete-conditioning`
- **Read model:** conditioning timestamps, mode, skipped flag, current conditioning assessment
- **Migration:** none required (reuses Slice 3 assessment/stage columns + Slice 4 timers/reminders)

## Handoff contract

| Element | Behavior |
|---|---|
| Source state | Session must be `FERMENTATION_COMPLETE` |
| Completion evidence | Current fermentation assessment confirmed/waived/overridden (`STALE_HANDOFF` otherwise) |
| Versioning | Session `expected_revision` OCC; stale → `409 STALE_REVISION` |
| Activation | Creates CONDITIONING stage ordinal 1 or reactivates `INVALIDATED` (ordinal+1, same PK) |
| Skip | Only when `conditioning_required=false`; no stage row; `conditioning_skipped=true` |
| Duplicate activation | Same `operation_id` replays; competing start → one winner |

## Conditioning state machine

| CURRENT | COMMAND | NEXT | Notes |
|---|---|---|---|
| FERMENTATION_COMPLETE | StartConditioning | CONDITIONING | plan requires conditioning |
| FERMENTATION_COMPLETE | SkipConditioning | CONDITIONING_COMPLETE | plan does not require |
| CONDITIONING | CompleteConditioning | CONDITIONING_COMPLETE | §14.3 or override |
| CONDITIONING | Pause / Resume | PAUSED → CONDITIONING | origin preserved |
| CONDITIONING+ | fermentation-affecting correction | ACTIVE | CONDITIONING → INVALIDATED; reuse later |

Invalid transitions fail closed (`409 INVALID_TRANSITION`).

## Completion (§14.3)

| Predicate | Rule |
|---|---|
| C0 | Session `CONDITIONING` |
| C1 | Duration from `conditioning_first_started_at` (not reset on pause/reactivation) |
| C2 | Effective CONDITIONING_TEMPERATURE within tolerance when planned |
| C3 | Checkpoints (none materialized → N/A pass) |
| C4 | When both duration+temp planned: C1∧C2 |
| Confirmation | Command itself (no separate confirm step) → `CONDITIONING_COMPLETION_CONFIRMATION=NOT_APPLICABLE` |
| Failure | `422 COMPLETION_INELIGIBLE` + persisted assessment + revision bump |
| Override | May bypass C1–C3; cannot bypass C0 |

## Invalidation / reactivation

| Path | Behavior |
|---|---|
| Fermentation-affecting after handoff | CONDITIONING `INVALIDATED`; cancel conditioning children; session `ACTIVE`; reactivate ACTIVE_FERMENTATION; later StartConditioning reuses PK |
| Conditioning-only after complete | Session → `CONDITIONING`; reactivate same stage ordinal+1; preserve history |
| History | Prior assessments retained `COMPLETION_INVALIDATED`; `*_first_*` preserved |

## Slice 5 traceability ledger

| REQUIREMENT_ID | SPEC_REFERENCE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LOCATION | STATUS |
|---|---|---|---|---|---|
| P4-FR-015 | §9.4 | `lifecycle.py` + conditioning commands | conditioning suite | this file | PASS |
| P4-FR-016 | §9.4 | fail-closed transitions | `test_invalid_transition_while_conditioning` | API | PASS |
| P4-FR-018 | §9.6/§9.8 | `child_effects` conditioning | handoff timers test | POSTGRESQL | PASS |
| P4-FR-019 | §9.4 | StartConditioning separate from CompleteFermentation | handoff test | API | PASS |
| P4-FR-020 | §14.3 | distinct conditioning assessment kind | complete tests | API | PASS |
| P4-FR-023 | §9.4 | SkipConditioning | `test_skip_conditioning_when_not_required` | DB | PASS |
| P4-FR-024 | §8.4/§9.8 | reuse CONDITIONING PK | AC-060 test | DB | PASS |
| P4-FR-045 | §14.3 | `evaluate_conditioning_eligibility` | AC-053 + success | DB | PASS |
| P4-FR-046 | §8.3 | mode from snapshot at start | handoff test | API | PASS |
| P4-FR-047 | §9.4 | skip only when not required | AC-014/015 | API | PASS |
| P4-FR-071/072 | §31 | operation_id + replay | duplicate start / retry | API | PASS |
| P4-FR-073/074 | §32 | OCC + session lock | concurrent start | PG | PASS |
| P4-FR-075 | §33 | owner-only | security cross-session | API | PASS |
| P4-FR-078/079 | §36 | durable GET | recovery test | RECOVERY | PASS |
| P4-FR-088 | §9.8 | reactivation reuse | AC-060 | DB | PASS |
| P4-AC-013 | pause origin | transitions + pause test | conditioning suite | PASS |
| P4-AC-014 | skip path | skip test | DB | PASS |
| P4-AC-015 | skip denied | skip denied test | API | PASS |
| P4-AC-053 | C2 fail | ineligible temperature test | DB | PASS |
| P4-AC-060 | reuse PK | post-handoff invalidation test | DB | PASS |
| P4-ADV-036 | never two PKs | same | DB | PASS |

Counts: **FR 15/15**, **AC 5/5**, **ADV 1/1** governing this slice.

## Gate results

| Gate | Result |
|---|---|
| FERMENTATION_CONDITIONING_HANDOFF | PASS |
| HANDOFF_VERSIONING | PASS |
| STALE_HANDOFF_REJECTION | PASS |
| CONDITIONING_STATE_MACHINE | PASS |
| CONDITIONING_ACTIVATION | PASS |
| CONDITIONING_TRANSITION_CONTRACT | PASS |
| CONDITIONING_COMPLETION_ASSESSMENT | PASS |
| CONDITIONING_COMPLETION_CONFIRMATION | NOT_APPLICABLE |
| CONDITIONING_INVALIDATION | PASS |
| CONDITIONING_REACTIVATION | PASS |
| CONDITIONING_MEASUREMENT_INTEGRATION | PASS |
| CONDITIONING_TIMER_INTEGRATION | PASS |
| CONDITIONING_REMINDER_INTEGRATION | PASS |
| POST_HANDOFF_PREDECESSOR_INVALIDATION | PASS |
| IDEMPOTENCY_CONTRACT | PASS |
| CONCURRENCY_CONTRACT | PASS |
| POSTGRESQL_ACCEPTANCE | PASS |
| MIGRATION_ACCEPTANCE | NOT_REQUIRED |
| API_ACCEPTANCE | PASS |
| SECURITY_ACCEPTANCE | PASS |
| JOURNAL_ACCEPTANCE | PASS |
| RECOVERY_ACCEPTANCE | PASS |
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| ACCESSIBILITY_ACCEPTANCE | NOT_REQUIRED |
| PLAYWRIGHT_ACCEPTANCE | NOT_REQUIRED |
| PHASE_1A_REGRESSION | PASS (`test_auth_and_recipe_api`) |
| PHASE_2_REGRESSION | PASS |
| PHASE_3_REGRESSION | PASS |
| PHASE_4_SLICE_2_REGRESSION | PASS |
| PHASE_4_SLICE_3_REGRESSION | PASS |
| PHASE_4_SLICE_4_REGRESSION | PASS |
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |

## Phase 5 boundary

No packaging execution, finished-product records, packaging inventory, keg/bottle/can workflows, or Phase 5 state machines. Conditioning completion only records Phase 4 facts (`CONDITIONING_COMPLETE` + assessment).

## Self-review

Falsified and repaired: PENDING CONDITIONING rows at start (violated §8.4); skip blocked by premature stage; temperature unit; correction observed_at before pitch; AC-060 re-complete eligibility after correction noise.

No accepted-spec contradiction found.
