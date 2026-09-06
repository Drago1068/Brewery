# Phase 4 Slice 4 — Durable Timers, Reminders & Lifecycle Child Effects

## Identity

| Field | Value |
|---|---|
| Input commit | `55bf16f1888ecd82ff0d74a417684154ad9dc012` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| Slice scope | Durable timers/reminders; close P4-FR-018 child-row effects |

## Architecture

- **Migration:** `0007_phase4_timers_reminders` — `fermentation_timers`, `fermentation_timer_revisions`, `fermentation_reminders`, `fermentation_reminder_history`
- **Application:**
  - `child_effects.py` — start materialization; pause/resume ACTIVE_TIME; abort cancel; complete primary; §9.8 reactivation (new timer PKs)
  - `timers.py` — create/pause/resume/complete/cancel/ack/extend + expiry projection
  - `reminders.py` — acknowledge (ACK≠SATISFIED); gravity measurement satisfaction
- **API:** session timer collection + `/timers/{id}/…` + `/reminders/{id}/acknowledge`
- **Read model:** GET reconstructs timers/reminders from PostgreSQL and commits expiry projection

## P4-FR-018 closure

Slice 3 historically reported P4-FR-018 as PARTIAL (journal-only). This slice implements the missing child-row effects:

| Lifecycle event | Child effect | Evidence |
|---|---|---|
| Start | Materialize WALL_CLOCK + ACTIVE_TIME timers; gravity reminder DUE | `test_start_materializes_timers_and_reminders` |
| Pause | ACTIVE_TIME → PAUSED `paused_by=SESSION_ACTION`; WALL_CLOCK continues | `test_pause_resume_child_timer_effects` |
| Resume | Resume only SESSION_ACTION pauses | same |
| Abort | Nonterminal timers/reminders → CANCELLED cause `SESSION_ABORTED` | `test_abort_cancels_nonterminal_children` |
| CompleteFermentation | STAGE_PRIMARY timers → COMPLETED | `test_complete_fermentation_completes_primary_timers` |
| Invalidation/reactivation | Cancel prior timers; new timer identities; reopen satisfied reminders | `test_invalidation_creates_new_timer_identities` |

**Result:** `P4_FR_018_CLOSURE=PASS` → effective Slice 3 FR implementation `12/12`.

## Slice 4 traceability ledger

| REQUIREMENT_ID | SPEC_REFERENCE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LAYER | STATUS |
|---|---|---|---|---|---|
| P4-FR-018 | §9.4/§9.6/§9.8 | `child_effects.py` + lifecycle wiring | `test_phase4_timers_reminders.py` | POSTGRESQL | PASS |
| P4-FR-048 | §19 | `timers.py`, models, migration 0007 | timer suite | POSTGRESQL | PASS |
| P4-FR-049 | §19/§36 | GET projection + persist | expiry + GET tests | RECOVERY | PASS |
| P4-FR-050 | §20 | `reminders.acknowledge_reminder` | `test_acknowledge_does_not_satisfy_reminder` | API_INTEGRATION | PASS |
| P4-FR-051 | §19 | `project_timers` single expiry journal | `test_timer_expiry_projection_single_event` | RECOVERY | PASS |
| P4-FR-088 | §9.8 | `invalidate_and_reactivate_children` | invalidation timer identity test | POSTGRESQL | PASS |
| P4-AC-016 | §9.6 | abort children | abort test | POSTGRESQL | PASS |
| P4-AC-029 | §36 | GET reconstruct expiry | expiry test | RECOVERY | PASS |
| P4-AC-030 | §20 | ACK≠SATISFIED | acknowledge test | API_INTEGRATION | PASS |
| P4-AC-057 | §9.6 | abort children | abort test | POSTGRESQL | PASS |
| P4-ADV-009 | §36 Redis | GET authority from PG | GET after persist | RECOVERY | PASS |
| P4-ADV-011 | §19 outage | one expiry event | expiry test | RECOVERY | PASS |

## Acknowledgement vs satisfaction

- Acknowledge: `DUE|EXPIRED → ACKNOWLEDGED`; `is_satisfied=false`; no satisfaction source
- Satisfaction: gravity measurement sets `COMPLETED` + `satisfaction_source_type=FermentationMeasurement`
- Duplicate ack: idempotent operation replay; one `BREWER_ACK` history row

## Concurrency / security

- Concurrent ack with shared `expected_revision`: one winner, one `409 STALE_REVISION`, one history row
- Cross-owner timer/reminder mutations: `404`

## Regression evidence (Docker PostgreSQL)

| Gate | Result |
|---|---|
| Slice 4 timers/reminders/security/migration | PASS |
| PHASE_4_SLICE_3_REGRESSION | PASS |
| PHASE_4_SLICE_2_REGRESSION | PASS |
| PHASE_3_REGRESSION (api/invariants/brew_day + migration harness) | PASS |
| PHASE_2_REGRESSION | PASS |
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS |

## Scope

- Conditioning lifecycle: not started
- Frontend/Playwright: NOT_REQUIRED (API + GET read-model sufficient for this slice)
- Phase 5: not authorized
