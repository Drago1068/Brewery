# Phase 4 Engineering and Acceptance Specification — Fermentation, Conditioning & Yeast

## 1. Document control

- Status: **REVIEW_CANDIDATE**
- Scope identifier: `PHASE_4_FERMENTATION_CONDITIONING_YEAST`
- Governing baselines:
  - Phase 0–2: accepted on `main`
  - Phase 3 tag: `v0.3.0-phase3`
  - Phase 3 baseline commit: `39c440f234149e67be6dfae948b33393857a153e`
  - Phase 3 accepted implementation: `2b82c2df2684cc599b3d84c1476513845566a517`
  - Phase 3 specification SHA-256: `6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF`
- Expected migration: `0004_phase4_fermentation_conditioning_yeast` (identifier provisional until implementation planning verifies repository head)
- Phase 4 implementation authorization: **NOT GRANTED**
- NAS production deployment: **NOT AUTHORIZED**

This specification is the engineering contract for Phase 4. It defines implementation boundaries, required behavior, prohibited forward leakage, and evidence needed for independent acceptance. It consumes the accepted Phase 3 yeast-pitch handoff and preserves Phase 0–3 contracts.

If this specification conflicts with an accepted ADR or the master plan, implementation must stop and an ADR or specification amendment must be reviewed before code continues.

## 2. Purpose

Phase 4 makes BICOS capable of managing and evidencing the beer's fermentation and conditioning lifecycle after the accepted Phase 3 yeast-pitch handoff.

The brewer must be able to answer, from authoritative data:

- What was pitched, when, into what wort, and under what conditions?
- What fermentation plan was intended versus what actually occurred?
- What measurements were observed, when, and with what provenance?
- What corrections, deviations, waivers, and actions occurred?
- What conditioning occurred?
- Has fermentation objectively reached its defined completion state?
- Is the batch ready for Phase 5 packaging/finished-beer lifecycle?
- What evidence supports those conclusions?

## 3. Governing baselines

Phase 0 through Phase 3 are accepted and immutable inputs. Phase 4 must not silently redefine:

- `RecipeVersion`, `BrewSession`, Brew-Day stage semantics, timers, reminders, measurements, `AdditionEvent` correction semantics, media, journal, inventory ledger behavior, equipment behavior, or deterministic calculation architecture.

Phase 4 extends lineage:

`RecipeVersion → BrewSession → BrewPitchHandoff → FermentationSession → PackagingReadinessHandoff → (Phase 5)`

## 4. Scope

Phase 4 delivers:

1. explicit fermentation-session lifecycle from accepted pitch handoff through conditioning completion;
2. planned-versus-actual fermentation and conditioning semantics;
3. gravity, temperature, and pH tracking with deterministic curves and progress metrics;
4. yeast pitch history with optional lot linkage and minimum reuse provenance;
5. post-pitch addition requirements and execution (`FERMENTATION`, `DRY_HOP` class additions deferred from Phase 3);
6. persistent long-duration timers and reminders reusing accepted Phase 3 authority patterns;
7. deterministic deviation, completion, waiver, correction, and late-entry contracts;
8. extended brew-session journal covering fermentation chronology;
9. notes/media under accepted authorization and persistence rules;
10. API, security, recovery, backup/restore, performance, and accessibility acceptance for the above.

## 5. Non-scope

Phase 4 does **not** implement:

- packaging, kegging, bottling, canning, or finished-beer inventory operations;
- carbonation operations, draft/tap management, or digital menu;
- QA/QC plans, CIP/sanitation workflows, calibration/maintenance operations;
- automatic inventory reservation-to-consumption or purchasing;
- competition, sensory panels, Academy curriculum, branding assets;
- Brewer Knowledge Engine correlations or autonomous recommendations;
- pressure-fermentation hardware control or automated device actuation;
- email/SMS/push notification platforms;
- microservices, event brokers, transactional outbox, distributed workers, offline sync engines, new database authority, or new media subsystems;
- exact biological prediction or AI-authoritative completion/inventory/state mutation.

## 6. Phase 3 entry contract

### 6.1 PHASE_4_ENTRY_STATE

Phase 4 begins only after:

1. `BrewSession.status = COMPLETED`;
2. exactly one accepted `BrewPitchHandoff` exists for that session (`schema_version = phase3-pitch-handoff-v1`);
3. no existing non-aborted `FermentationSession` exists for that `brew_session_id`.

### 6.2 PHASE_4_ENTRY_REQUIRED_FACTS

Immutable inputs consumed from Phase 3:

| Fact | Source | Mutability in Phase 4 |
|---|---|---|
| `brew_session_id` | `BrewSession` | immutable reference |
| `recipe_version_id` | `BrewSession` snapshot | immutable reference |
| `pitched_at` | `BrewPitchHandoff.pitched_at` | immutable |
| `pitch_temperature_c` | `BrewPitchHandoff.pitch_temperature_c` | immutable |
| `yeast_addition_note` | `BrewPitchHandoff.yeast_addition_note` | immutable |
| `pitch_actor_user_id` | `BrewPitchHandoff.actor_user_id` | immutable |
| `original_gravity` | latest authoritative brew-side `ORIGINAL_GRAVITY` measurement if present; otherwise null until first ferment measurement | brew evidence immutable; ferment may reference only |

### 6.3 PHASE_4_ENTRY_OPTIONAL_FACTS

Optional enrichments at fermentation start (never retroactively rewriting Phase 3 handoff):

- linked `ingredient_lot_id` for pitched yeast;
- parsed yeast product/strain reference from note or lot metadata;
- equipment fermenter snapshot reference;
- planned fermentation targets from `FermentationPlan` materialization.

### 6.4 PHASE_4_ENTRY_VALIDATION

Starting fermentation fails closed with stable errors when:

- brew session not owned by caller;
- brew session not `COMPLETED`;
- pitch handoff missing;
- brew session is `LEGACY_MASH_ONLY` without pitch handoff;
- duplicate start attempted with conflicting payload (`409`);
- recipe version deleted or inaccessible to owner (still referenced immutably if session exists).

### 6.5 PHASE_4_ENTRY_IDEMPOTENCY

`POST /api/v1/fermentation-sessions/start` requires `operation_id` and follows `phase4-operation-v1`. Replaying the same scoped operation returns the original `FermentationSession` without duplicate rows.

### 6.6 PHASE_4_ENTRY_FAILURE_BEHAVIOR

Failure creates no partial fermentation rows, timers, reminders, or journal events. Validation errors are `422`; ownership/not-found are `404`; conflicts are `409`.

## 7. Phase 5 handoff contract

### 7.1 ALLOWED_PHASE_5_HANDOFF_FACTS

Phase 4 may emit one authoritative `PackagingReadinessHandoff` (`phase4-packaging-readiness-v1`) containing:

- `fermentation_session_id`, `brew_session_id`, `recipe_version_id`;
- confirmed `original_gravity`, `final_gravity`, `apparent_attenuation`;
- `fermentation_completed_at`, `conditioning_completed_at`;
- `packaging_readiness_status` (`READY`, `NOT_READY`, `READY_WITH_WAIVERS`);
- completion assessment identity and evidence summary;
- yeast pitch summary references (handoff + optional lot);
- journal export reference or deterministic reconstruction handle.

These are **readiness facts**, not packaging operations.

### 7.2 PROHIBITED_PHASE_5_BEHAVIOR

Phase 4 must not create or mutate:

- `PackagingSession`, package units, kegs, cans, bottles;
- packaged-beer inventory transactions;
- tap assignments, menu publications, carbonation adjustments;
- QA/QC plans, CIP records, microbiology workflows;
- consumption/depletion events.

## 8. Domain model

### 8.1 Authoritative aggregates and records

| Concept | Role | Aggregate? |
|---|---|---|
| `FermentationSession` | owned execution record for post-pitch lifecycle | yes (session root) |
| `FermentationPlanSnapshot` | immutable planned targets/schedules at session start | snapshot value owned by session |
| `FermentationStageInstance` | ordered stage occurrences (`ACTIVE_FERMENTATION`, `CONDITIONING`, …) | part of session |
| `FermentationMeasurement` | append-only observation | evidence record |
| `FermentationMeasurementCorrection` | append-only supersession | evidence record |
| `FermentationTimer` | server-authoritative timer | child of session/stage |
| `FermentationReminder` | deterministic required-action projection | child of session/stage |
| `FermentationAction` | user-recorded intervention | evidence record |
| `FermentationAdditionRequirement` | materialized post-pitch obligation | plan child |
| `FermentationAdditionEvent` | planned-versus-actual addition fact | evidence record |
| `FermentationDeviation` | deterministic departure record | derived/evidence |
| `FermentationCompletionAssessment` | explainable completion decision | evidence record |
| `ConditioningAssessment` | explainable conditioning completion | evidence record |
| `FermentationWaiver` | explicit requirement waiver | evidence record |
| `YeastPitchReference` | Phase 4 enrichment linking handoff to lot/provenance | reference record |
| `PackagingReadinessHandoff` | terminal Phase 4 handoff fact | terminal record |
| `FermentationJournalEvent` | append-only chronology | projection/event |

No mandatory `BrewPlan`, `BrewBatch`, transactional outbox, or distributed worker is introduced.

### 8.2 Identity and ownership

- Every Phase 4 mutable resource is owned by exactly one user (same ownership model as Phase 3).
- `FermentationSession` references exactly one `brew_session_id` and inherits recipe/version identity from that session snapshot.
- Cross-session foreign keys for mutable evidence are prohibited except explicitly allowed reference tables (e.g., yeast lot read, brew pitch handoff read).

### 8.3 Mutability

- Plan snapshots, measurements, actions, additions, assessments, waivers, and journal events are append-only with correction lineage; no silent overwrite.
- Stage/session state transitions are explicit commands with audit/journal records.
- Terminal `CLOSED` sessions forbid new normal execution mutations except authorized correction, late entry, read, export, and media retrieval per terminal contract.

## 9. Lifecycle and state machines

### 9.1 FermentationSession states

Required lifecycle:

`PLANNED -> ACTIVE <-> PAUSED -> FERMENTATION_COMPLETE -> CONDITIONING <-> PAUSED -> CONDITIONING_COMPLETE -> COMPLETION_ASSESSED -> HANDOFF_READY -> CLOSED`

Exceptional terminal:

`PLANNED | ACTIVE | PAUSED | FERMENTATION_COMPLETE | CONDITIONING | CONDITIONING_COMPLETE -> ABORTED`

Rules:

- `PLANNED` exists only transiently during start transaction; client-visible default after successful start is `ACTIVE`.
- Only one nonterminal fermentation session per brew session.
- Multiple nonterminal fermentation sessions per user are allowed if they reference different completed brew sessions.
- Invalid transitions return `409` without partial writes.
- `HANDOFF_READY` requires successful packaging readiness handoff recording.
- `CLOSED` is terminal except for correction/export/read paths defined in section 23.

### 9.2 Stage vocabulary

Canonical fermentation-stage vocabulary:

1. `PITCH_CONFIRMED` (reference-only stage anchoring Phase 3 handoff facts)
2. `ACTIVE_FERMENTATION`
3. `CONDITIONING`
4. `HANDOFF_READY`

Optional substates such as `WARM_CONDITIONING`, `COLD_CONDITIONING`, `LAGERING`, `COLD_CRASH` may appear as `conditioning_mode` on the `CONDITIONING` stage instance when declared in the plan snapshot; they do not replace the canonical stage vocabulary.

### 9.3 State transition matrix (summary)

| Transition | Entry conditions | Exit conditions | Invalid if |
|---|---|---|---|
| start session | Phase 3 entry contract satisfied | session `ACTIVE`, stage `ACTIVE_FERMENTATION` entered | missing handoff / duplicate |
| complete fermentation | active fermentation requirements satisfied or waived | `FERMENTATION_COMPLETE` | insufficient evidence where non-waivable |
| start conditioning | fermentation complete | `CONDITIONING` active | skipped if plan declares no conditioning |
| complete conditioning | conditioning requirements satisfied or waived | `CONDITIONING_COMPLETE` | invalid if fermentation not complete |
| assess completion | conditioning complete or waived absent | `COMPLETION_ASSESSED` with stored assessment | insufficient evidence |
| record handoff | completion assessed eligible | `HANDOFF_READY` | prohibited facts missing |
| close session | handoff recorded | `CLOSED` | n/a |

Correction behavior: append-only correction events may invalidate prior completion assessments and move session backward to `ACTIVE` or `CONDITIONING` deterministically per section 21.

## 10. Fermentation plan versus actual

At session start, materialize `phase4-plan-v1` snapshot from owned `RecipeVersion` fermentation-relevant data:

- planned yeast identity references;
- target fermentation temperature or schedule;
- planned conditioning mode/temperature/duration;
- expected final gravity / attenuation targets where present;
- post-pitch addition templates from Phase 2 `FERMENTATION` and `DRY_HOP` additions;
- required measurement checkpoints.

Rules:

- Planned values are never overwritten by actual observations.
- Actual observations store provenance separately.
- Planned-versus-actual comparisons use `packages/calculations` deterministic functions with Decimal semantics and accepted rounding policy.
- Missing planned values remain `UNSPECIFIED`; the UI and API must not invent them.

## 11. Yeast model and provenance

### 11.1 Pitch facts

Phase 3 `BrewPitchHandoff` remains authoritative for pitch timestamp, pitch temperature, and brewer-entered yeast-addition note. Phase 4 may create `YeastPitchReference` that links optional:

- `ingredient_lot_id`
- manufacturer/strain/product/form metadata (from lot or user entry)
- quantity / pitch amount / viability inputs where supplied
- preparation method note
- provenance class: `OBSERVED`, `USER_ENTERED`, `MANUFACTURER_PROVIDED`, `CALCULATED`, `ESTIMATED`, `UNKNOWN`

### 11.2 Pitch history

The platform must provide queryable pitch history per user, per lot, and per fermentation session without mutating Phase 3 handoff rows.

### 11.3 Reuse / generation lineage

Full yeast harvest, storage, and reuse operations are **deferred** to a later phase unless separately authorized.

Phase 4 minimum provenance for future reuse:

- optional `source_fermentation_session_id` and `source_yeast_reference_id` fields on `YeastPitchReference`;
- append-only note/event when reuse is claimed by the brewer;
- no automatic inventory consumption or generation inference without ADR authorization.

Circular lineage (A sourced from B sourced from A) is rejected at validation time.

## 12. Measurements

### 12.1 Supported measurement types

| Type | Unit | Value domain | Required context |
|---|---|---|---|
| `FERMENTATION_GRAVITY` | `SG` or `Plato` per entry with canonical storage | Decimal within validated bounds | fermentation stage, instrument optional |
| `FERMENTATION_TEMPERATURE` | `degC` | `-5..40` for ferment-side storage validation | location/measurement point optional |
| `FERMENTATION_PH` | `pH` | `2.5..8.0` | optional method |
| `CONDITIONING_TEMPERATURE` | `degC` | `-5..30` | conditioning stage |

Pressure measurements are **deferred** (`BASELINE_COMPATIBILITY_ISSUE` not raised; explicitly out of Phase 4 scope).

### 12.2 Measurement contract

Every measurement stores:

- `measurement_type`, `value`, `unit`, `observed_at`, `recorded_at`, `actor_user_id`, `source`, optional `instrument_reference`, `confidence`, `note`, `provenance`, `fermentation_session_id`, optional `stage_instance_id`.

Rules:

- `observed_at` is the authoritative observation time; `recorded_at` is entry time; both persisted in UTC.
- Corrections append new rows; never overwrite prior measurements.
- Duplicate idempotency replays return original measurement.
- Cross-session measurement attachment is rejected by DB/API invariant.

## 13. Deterministic calculations

All fermentation calculations remain in `packages/calculations` (or bounded domain packages), not UI or LLM.

Required deterministic functions:

| Function | Inputs | Output |
|---|---|---|
| `apparent_attenuation` | original gravity, current/final gravity | Decimal percent |
| `fermentation_progress` | original, current, target final gravity | bounded ratio |
| `stable_gravity_evaluator` | ordered gravity observations | stable/not stable/insufficient |
| `abv_from_gravity` | OG, FG | ABV per accepted formula |
| `pitch_rate_estimate` | cell count inputs when present | estimated cells/ml/°P (labeled `CALCULATED`) |
| `planned_vs_actual_temperature_delta` | planned, actual | Decimal delta |

Reuse Phase 2/3 Decimal precision and ADR-0008 rounding policy. Display rounding must not change stored authoritative values.

## 14. Fermentation completion

Completion is **not** implied by elapsed duration alone unless a plan snapshot explicitly declares a duration-only criterion **and** the specification labels it `ELAPSED_TIME_AUXILIARY` rather than primary completion evidence.

Primary completion evidence combines:

1. stable-gravity contract (section 15);
2. expected attenuation threshold if planned target exists;
3. required checkpoint measurements satisfied or waived;
4. brewer confirmation command where automatic eligibility passes;
5. explicit waiver with reason for non-waivable exceptions only where allowed.

Completion statuses:

- `AUTOMATIC_ELIGIBILITY`
- `BREWER_CONFIRMED`
- `WAIVER`
- `OVERRIDE_WITH_REASON`
- `INSUFFICIENT_EVIDENCE`
- `COMPLETION_REVOKED_BY_CORRECTION`

A completion assessment must store the evidence set used, actor, timestamps, and assessment version.

## 15. Stable gravity contract

When stable gravity is used for completion eligibility:

| Parameter | Value |
|---|---|
| minimum observations | 3 |
| minimum separation | 24 hours between consecutive qualifying observations |
| tolerance | absolute difference ≤ `0.002` SG between last three observations after unit normalization |
| unit normalization | compare in canonical SG domain |
| invalid measurements | excluded if corrected-superseded or failed validation |
| late entries | allowed; may reset stability window deterministically |
| duplicates | same idempotency scope returns original; conflicting duplicate payloads `409` |

If fewer than three valid observations exist, status is `INSUFFICIENT_EVIDENCE`, not complete.

## 16. Temperature management

Distinguish:

- `TARGET` (planned snapshot)
- `MEASURED` (observation)
- `ESTIMATED` (explicitly labeled derived value only)

Support planned schedule entries `{effective_at, target_temp_c}` in snapshot form.

Excursions create deterministic deviations when `|measured - target| > tolerance` and a target exists.

BICOS monitors and records; it does not control hardware.

## 17. Conditioning

Conditioning modes authorized when declared in plan snapshot or selected at fermentation-complete transition:

- `WARM_CONDITIONING`
- `COLD_CONDITIONING`
- `LAGERING`
- `COLD_CRASH`

Each mode declares planned duration and/or target temperature. Completion requires configured checkpoints satisfied or waived plus conditioning completion assessment parallel to fermentation completion rules.

Skipping conditioning is allowed only when plan snapshot declares `CONDITIONING_NOT_REQUIRED`.

## 18. Timers

Reuse Phase 3 timer semantics and persistence patterns with Phase 4 ownership:

- PostgreSQL authoritative; browser/Redis not timer authority;
- states: `PENDING -> RUNNING <-> PAUSED -> COMPLETED`, deadline path `EXPIRED -> ACKNOWLEDGED | COMPLETED`, exceptional `CANCELLED`;
- clock bases: primarily `WALL_CLOCK` for multi-day fermentation; `ACTIVE_TIME` only where explicitly declared;
- extend/replace semantics identical to Phase 3 revision/replacement contract;
- recovery after refresh/API restart/Redis loss via session GET reconstruction.

Phase 4 introduces no competing timer subsystem.

## 19. Reminders

Reuse Phase 3 reminder lifecycle:

`SCHEDULED -> DUE -> COMPLETED` with paths through `ACKNOWLEDGED`, `SKIPPED`, `CANCELLED`, `EXPIRED`.

Categories include gravity reading, temperature observation, temperature change, fermentation check, conditioning transition, conditioning completion.

Acknowledgement does not satisfy required measurement/action.

## 20. Actions and post-pitch additions

### 20.1 Fermentation actions

User-recorded actions include temperature adjustment note, dry-hop preparation, fermentation intervention, conditioning transition note, and authorized addition reference.

Each action stores actor, timestamps, type, context, planned/unplanned classification, optional note, and audit trail.

### 20.2 Post-pitch additions

In scope: materialize Phase 2 additions with `use_stage` in `{FERMENTATION, DRY_HOP}` into `FermentationAdditionRequirement` rows at session start.

Execution creates append-only `FermentationAdditionEvent` with zero inventory effect (same zero-effect contract as Phase 3 unless future ADR authorizes consumption).

Repeat/correction semantics mirror Phase 3 addition correction lineage adapted to fermentation session scope.

## 21. Deviations

Deviations may be system-derived or user-recorded.

System-derived examples:

- temperature excursion;
- missed reminder deadline;
- unexpected gravity trajectory versus plan;
- stable-gravity window broken by correction.

Each deviation stores cause evidence references and remains explainable after corrections.

## 22. Corrections

Append-only correction lineage for all Phase 4 evidence types.

| Field class | Correctable | Immutable |
|---|---|---|
| measurement value/unit/type/context/times | yes via new correction row | prior row identity |
| action/addition notes and times | yes | actor identity chain |
| waiver reason | append-only supplemental note only | original waiver fact |
| session ownership | no | brew_session link |
| pitch handoff facts | no | Phase 3 handoff immutable |

Cross-session correction is prohibited.

Correction cycles are rejected.

## 23. Late entry

Bounded late-entry windows:

| Evidence | Allowed after stage/session terminal? | Window |
|---|---|---|
| fermentation measurement | yes with flag | up to 7 days after observed_at unless session `CLOSED` and policy forbids |
| conditioning measurement | yes with flag | same |
| action note | yes | up to 7 days |
| completion-affecting measurement | yes | may revoke completion assessment |

Late entries store `late_entry=true`, `recorded_at`, and actor.

## 24. Waivers and overrides

Waiver required fields: reason, actor, timestamp, requirement identity, effect.

Non-waivable:

- ownership/authentication;
- immutable brew/pitch references;
- cross-session integrity rules;
- actual pitch timestamp and brewer-entered pitch note (Phase 3 contract);
- idempotency/concurrency controls.

Waivable with reason: selected checkpoint measurements, conditioning steps, optional planned additions.

Override requires `OVERRIDE_WITH_REASON` and may not fabricate missing measurements.

## 25. Terminal behavior

After `CLOSED`:

| Operation | Allowed |
|---|---|
| read session/measurements/journal | yes |
| export | yes |
| correction / authorized late entry | yes, deterministic reassessment |
| media retrieval | yes |
| new normal measurements/actions | no |
| new state transitions | no |

Correction may revoke prior completion/handoff and move session to earlier state deterministically with journal/audit records.

## 26. Journal

Extend brew-session journal projection with Phase 4 events without breaking Phase 3 ordering.

Required event types include:

`FERMENTATION_SESSION_STARTED`, `FERMENTATION_STAGE_ENTERED`, `FERMENTATION_MEASUREMENT_RECORDED`, `FERMENTATION_MEASUREMENT_CORRECTED`, `FERMENTATION_TIMER_*`, `FERMENTATION_REMINDER_*`, `FERMENTATION_ACTION_RECORDED`, `FERMENTATION_DEVIATION_RECORDED`, `FERMENTATION_WAIVER_RECORDED`, `FERMENTATION_COMPLETION_ASSESSED`, `CONDITIONING_COMPLETED`, `PACKAGING_READINESS_HANDOFF_RECORDED`, `FERMENTATION_SESSION_CLOSED`.

Journal ordering is `(occurred_at ASC, sequence ASC)` with stable tie-breaker.

## 27. Notes and media

Reuse Phase 3 media architecture (`MEDIA_ROOT`, authorization, MIME validation, backup/restore).

Phase 4 attachments link to fermentation session and optional stage instance.

No new storage subsystem.

## 28. Inventory integration

Phase 4 may:

- reference yeast `IngredientLot` on pitch enrichment;
- display lot metadata;
- record explicit user-confirmed pitch quantity notes.

Phase 4 must not:

- post automatic `CONSUMPTION` ledger entries;
- convert reservations automatically;
- mutate stock without future ADR + phase authorization.

If manual consumption is later authorized, it requires separate ADR and is not part of this specification's default contract.

## 29. Equipment integration

Fermentation sessions may snapshot fermenter/equipment profile references at start.

Historical sessions must not change when equipment profiles are edited later.

## 30. API contract (normative summary)

Base path: `/api/v1/fermentation-sessions`

| Capability | Method | Idempotent | Notes |
|---|---|---|---|
| Start session from brew session | POST `/start` | yes | requires completed brew + pitch handoff |
| Get session detail | GET `/{id}` | n/a | reconstruct timers/reminders |
| List sessions | GET `/` | n/a | owner scoped |
| Record measurement | POST `/{id}/measurements` | yes | |
| Correct measurement | POST `/{id}/measurements/{mid}/corrections` | yes | |
| Record action | POST `/{id}/actions` | yes | |
| Transition stage/state | POST `/{id}/commands/...` | yes | pause/resume/complete fermentation/conditioning |
| Record waiver | POST `/{id}/waivers` | yes | |
| Assess completion | POST `/{id}/completion-assessments` | yes | |
| Record packaging readiness handoff | POST `/{id}/packaging-readiness-handoff` | yes | terminal Phase 4 fact |
| Export | GET `/{id}/export` | n/a | JSON + human-readable |
| Media upload/list/get | POST/GET media routes | yes | reuse accepted patterns |

All mutations require CSRF, ownership checks, `operation_id`, and optimistic revision where applicable.

Errors: `404` cross-owner, `409` conflict/stale revision/terminal violation, `422` validation.

## 31. Idempotency

`phase4-operation-v1` mirrors `phase3-operation-v1`:

- scoped by `(user_id, operation_id, command_name, resource_scope)`;
- duplicate same payload replays original result;
- conflicting payload returns `409` without partial mutation;
- tombstone/retention rules equivalent to Phase 3 acceptance.

## 32. Concurrency

Authoritative PostgreSQL transactions enforce:

- one winner for concurrent completion assessments;
- no duplicate stage transitions;
- measurement/reminder races resolved server-side;
- stale revision conflicts return `409`.

Representative tests require real PostgreSQL locks for completion and state transition races.

## 33. Security and authorization

Preserve Phase 3 CSRF synchronizer token + Origin/Referer checks.

Server-side ownership enforcement for every fermentation resource.

IDOR matrix covers session, stage, measurement, action, media, journal, export, handoff.

Media path safety, MIME allowlist, decoder bounds, and error non-leakage reuse Phase 3 contracts.

## 34. Privacy

Phase 4 introduces no new personal data classes beyond existing user identity and brewer notes/photos.

Notes/media retention follows platform policy; no new profiling.

## 35. Backup and restore

Acceptance requires representative fermentation session survives platform backup/restore into isolated environment with:

- session/stages/timers/reminders/measurements/actions/deviations/waivers/assessments/handoff;
- journal events;
- media metadata **and bytes**.

## 36. Recovery

Acceptance requires recovery proofs for:

- browser refresh during active fermentation;
- API restart with session/timers/reminders intact;
- Redis loss with PostgreSQL authority preserved;
- overdue timer/reminder after outage;
- reconnect after partial failure.

## 37. Performance

Reference-class fermentation session for harness (isolated, non-authoritative):

- 1 session, 90 days simulated history cap in test harness;
- 200 measurements, 50 reminders, 20 timers, 100 journal events, 10 attachments;
- thresholds: representative GET p95 ≤ 500 ms and mutation p95 ≤ 750 ms at n=100 in disposable PostgreSQL/API environment.

No production-route performance mutation endpoint.

## 38. Accessibility

Keyboard operability for record measurement, acknowledge reminder, record action, review state/history, add note/media, complete/waive.

Semantic timers/reminders/status changes (`role="timer"`, labels, errors associated).

If charts are implemented, provide tabular equivalent data path.

## 39. Responsive UX

Minimum usable workflows at ~360 px width for measurement entry, reminder acknowledgement, current state review, and note capture near fermentation equipment.

## 40. Trends and visualization

Charts are derived views over authoritative measurements.

Missing data renders as missing, not zero.

Corrections update derived series to current effective values while preserving historical points per accepted correction policy.

## 41. AI boundary

AI may summarize/explain; it may not authoritatively create measurements, state transitions, completion, inventory mutations, corrections, or waivers.

## 42. Safety boundary

Fail-closed validation for impossible timestamps, out-of-range values, and dangerous mis-entry patterns.

BICOS is not a substitute for physical pressure/temperature safety systems.

## 43. Failure modes

See adversarial scenarios section; includes duplicate measurement/action, IDOR, late/corrected gravity, completion with insufficient evidence, stale client, API restart, Redis loss, backup/restore, malformed media, CSRF, XSS, SQLi, performance contamination, post-terminal mutation, and out-of-order evidence.

## 44. Functional requirements

### Session and handoff

- **P4-FR-001:** Phase 4 shall start a fermentation session only from a completed brew session with exactly one Phase 3 pitch handoff.
- **P4-FR-002:** Phase 4 shall immutable-reference Phase 3 pitch timestamp, pitch temperature, and yeast-addition note in session detail.
- **P4-FR-003:** Phase 4 shall reject fermentation start when pitch handoff is missing (`422`/`404` as appropriate).
- **P4-FR-004:** Phase 4 shall enforce at most one non-aborted fermentation session per brew session.
- **P4-FR-005:** Phase 4 shall allow multiple concurrent fermentation sessions for one user when they reference different brew sessions.
- **P4-FR-006:** Phase 4 shall materialize `phase4-plan-v1` snapshot transactionally at session start.
- **P4-FR-007:** Phase 4 shall never mutate RecipeVersion or BrewSession Phase 3 evidence during fermentation operations.
- **P4-FR-008:** Phase 4 shall record packaging readiness handoff facts without creating packaging sessions.

### Lifecycle

- **P4-FR-009:** Phase 4 shall implement the fermentation session state machine in section 9.1 as authoritative server state.
- **P4-FR-010:** Phase 4 shall reject invalid state transitions with `409` and no partial writes.
- **P4-FR-011:** Phase 4 shall support explicit pause/resume of an active fermentation session.
- **P4-FR-012:** Phase 4 shall separate fermentation completion from conditioning start.
- **P4-FR-013:** Phase 4 shall support conditioning completion distinct from fermentation completion.
- **P4-FR-014:** Phase 4 shall support abort with reason and preserved history.
- **P4-FR-015:** Phase 4 shall close session only after packaging readiness handoff is recorded.

### Measurements

- **P4-FR-016:** Phase 4 shall support `FERMENTATION_GRAVITY` measurements with validated units/value domain.
- **P4-FR-017:** Phase 4 shall support `FERMENTATION_TEMPERATURE` measurements.
- **P4-FR-018:** Phase 4 shall support `FERMENTATION_PH` measurements.
- **P4-FR-019:** Phase 4 shall support `CONDITIONING_TEMPERATURE` measurements.
- **P4-FR-020:** Phase 4 shall persist `observed_at` and `recorded_at` separately in UTC.
- **P4-FR-021:** Phase 4 shall append measurement corrections without overwriting prior rows.
- **P4-FR-022:** Phase 4 shall reject cross-session measurement linkage.

### Calculations

- **P4-FR-023:** Phase 4 shall compute apparent attenuation deterministically from authoritative gravities.
- **P4-FR-024:** Phase 4 shall compute fermentation progress without UI/LLM authority.
- **P4-FR-025:** Phase 4 shall evaluate stable gravity using section 15 contract.
- **P4-FR-026:** Phase 4 shall compute ABV using accepted deterministic formula when OG/FG exist.
- **P4-FR-027:** Phase 4 shall label calculated pitch-rate outputs as `CALCULATED`, not observed.

### Completion and conditioning

- **P4-FR-028:** Phase 4 shall not mark fermentation complete from elapsed time alone unless plan declares auxiliary elapsed criterion and primary evidence still passes.
- **P4-FR-029:** Phase 4 shall store explainable completion assessments with evidence references.
- **P4-FR-030:** Phase 4 shall support brewer confirmation after automatic eligibility.
- **P4-FR-031:** Phase 4 shall support completion revocation when corrections invalidate prior evidence.
- **P4-FR-032:** Phase 4 shall support declared conditioning modes in section 17.
- **P4-FR-033:** Phase 4 shall allow explicit skip of conditioning only when plan declares `CONDITIONING_NOT_REQUIRED`.

### Timers and reminders

- **P4-FR-034:** Phase 4 shall persist timers in PostgreSQL with Phase 3-equivalent lifecycle semantics.
- **P4-FR-035:** Phase 4 shall recover timers/reminders after refresh and API restart from authoritative GET reconstruction.
- **P4-FR-036:** Phase 4 shall treat reminder acknowledgement as distinct from requirement satisfaction.
- **P4-FR-037:** Phase 4 shall support overdue reminders/timers deterministically after reconnect.

### Additions and actions

- **P4-FR-038:** Phase 4 shall materialize post-pitch addition requirements from Phase 2 `FERMENTATION`/`DRY_HOP` additions.
- **P4-FR-039:** Phase 4 shall record fermentation addition events append-only with correction lineage.
- **P4-FR-040:** Phase 4 shall record user fermentation actions with actor/timestamp/type/context.
- **P4-FR-041:** Phase 4 shall keep fermentation addition execution at zero inventory effect by default.

### Deviations, waivers, late entry

- **P4-FR-042:** Phase 4 shall record deterministic deviations with evidence pointers.
- **P4-FR-043:** Phase 4 shall support explicit waivers with reason/actor/timestamp/effect.
- **P4-FR-044:** Phase 4 shall reject waivers for non-waivable requirements (`409 WAIVER_PROHIBITED`).
- **P4-FR-045:** Phase 4 shall support bounded late entry per section 23.

### Journal, media, export

- **P4-FR-046:** Phase 4 shall append fermentation journal events to the brew-session chronology.
- **P4-FR-047:** Phase 4 shall support note/media attachments under accepted Phase 3 media security architecture.
- **P4-FR-048:** Phase 4 shall export JSON and human-readable session summaries including plan/actual/completion evidence.

### Yeast and inventory

- **P4-FR-049:** Phase 4 shall allow optional yeast lot linkage on pitch reference enrichment.
- **P4-FR-050:** Phase 4 shall provide pitch history queries by session, lot, and user.
- **P4-FR-051:** Phase 4 shall reject circular yeast reuse lineage declarations.
- **P4-FR-052:** Phase 4 shall not post automatic inventory consumption transactions.

### API, idempotency, concurrency, security

- **P4-FR-053:** Phase 4 shall require `operation_id` on all Phase 4 mutation commands.
- **P4-FR-054:** Phase 4 shall implement `phase4-operation-v1` replay/conflict semantics.
- **P4-FR-055:** Phase 4 shall enforce optimistic revision conflicts as `409`.
- **P4-FR-056:** Phase 4 shall enforce owner-only access to fermentation resources (`404` cross-owner).
- **P4-FR-057:** Phase 4 shall preserve CSRF protections on mutating routes.
- **P4-FR-058:** Phase 4 shall validate input units/value domains server-side.

### Recovery, backup, performance, accessibility

- **P4-FR-059:** Phase 4 shall survive API restart without losing authoritative fermentation state.
- **P4-FR-060:** Phase 4 shall treat Redis as non-authoritative for fermentation state.
- **P4-FR-061:** Phase 4 representative state shall survive backup/restore including media bytes.
- **P4-FR-062:** Phase 4 shall provide isolated performance harness without authoritative mutation of user sessions.
- **P4-FR-063:** Phase 4 UI shall support keyboard and mobile workflows defined in sections 38–39.

### Regression and scope

- **P4-FR-064:** Phase 4 shall preserve accepted Phase 3 brew-day behavior and evidence unchanged.
- **P4-FR-065:** Phase 4 shall preserve accepted Phase 2 and Phase 1A regression surfaces.
- **P4-FR-066:** Phase 4 shall include explicit Phase 5+ leakage prevention matrix enforcement in acceptance scans.
- **P4-FR-067:** Phase 4 migrations shall be additive against Phase 3 head and preserve legacy data.

## 45. Acceptance criteria

### Scope and architecture

- **P4-AC-001:** Diff from `v0.3.0-phase3` contains only Phase 4 specification/implementation artifacts, bounded compatibility work, tests, migrations, and documentation.
- **P4-AC-002:** Architecture review confirms deterministic authority and no prohibited AI or Phase 5+ operational leakage.
- **P4-AC-003:** Phase 5–10 leakage scan maps every new table/route/page to authorized Phase 4 requirement or handoff fact.

### Entry and handoff

- **P4-AC-010:** Starting from accepted pitch handoff creates exactly one fermentation session and plan snapshot.
- **P4-AC-011:** Missing pitch handoff prevents fermentation start with stable error and no partial rows.
- **P4-AC-012:** Packaging readiness handoff records only readiness facts; no packaging session rows created.

### Lifecycle

- **P4-AC-020:** Invalid fermentation state transitions fail without partial writes.
- **P4-AC-021:** Pause/resume preserves timer/reminder authority semantics.
- **P4-AC-022:** Completion assessment stores evidence set and actor auditably.
- **P4-AC-023:** Correction can revoke prior completion and re-open session deterministically.

### Measurements and calculations

- **P4-AC-030:** Gravity/temperature/pH measurements validate units/domains and separate observed/recorded times.
- **P4-AC-031:** Stable-gravity evaluator matches section 15 thresholds in golden tests.
- **P4-AC-032:** Attenuation/progress/ABV functions match calculation-engine golden cases.

### Timers, reminders, additions

- **P4-AC-040:** Fermentation timers recover after refresh/API restart.
- **P4-AC-041:** Acknowledged reminder does not satisfy required measurement.
- **P4-AC-042:** Post-pitch addition materialization includes `FERMENTATION`/`DRY_HOP` sources excluded from Phase 3.

### Security, recovery, backup, performance

- **P4-AC-050:** CSRF/IDOR/media security matrix passes representative PostgreSQL tests.
- **P4-AC-051:** Backup/restore preserves fermentation metadata and media bytes.
- **P4-AC-052:** Redis-loss recovery returns authoritative fermentation session state from PostgreSQL.
- **P4-AC-053:** Isolated performance harness meets declared thresholds at n=100.

### Regression

- **P4-AC-060:** Phase 3 canonical E2E and PostgreSQL suite remain green (144/144 baseline unless superseded by explicit recount evidence).
- **P4-AC-061:** Phase 2 core and calculation regressions remain green.
- **P4-AC-062:** Phase 1A browser regression remains green.

### UX/a11y/browser

- **P4-AC-070:** Canonical Phase 4 browser flow completes active fermentation → conditioning → readiness handoff.
- **P4-AC-071:** Phone viewport supports measurement entry and reminder acknowledgement.
- **P4-AC-072:** Keyboard focus and error association assertions pass for fermentation worksheet.

## 46. Adversarial scenarios

- **P4-ADV-001:** Duplicate measurement submit with same `operation_id` replays original; conflicting payload `409`.
- **P4-ADV-002:** Duplicate completion assessment concurrent submit yields one winner, no double handoff.
- **P4-ADV-003:** Cross-owner fermentation session GET returns `404`.
- **P4-ADV-004:** Cross-session measurement insert rejected by DB/API invariant.
- **P4-ADV-005:** Late gravity entry revokes stable-gravity eligibility deterministically.
- **P4-ADV-006:** Corrected gravity changes completion assessment outcome with audit trail.
- **P4-ADV-007:** Completion attempt with insufficient evidence returns `409`/`422` without completion row.
- **P4-ADV-008:** Waiver prohibited on pitch timestamp/note returns `409 WAIVER_PROHIBITED`.
- **P4-ADV-009:** Redis stop does not change authoritative fermentation session GET results.
- **P4-ADV-010:** API restart preserves session stage/timer IDs.
- **P4-ADV-011:** Browser refresh reconstructs overdue reminder/timer accurately.
- **P4-ADV-012:** Post-terminal normal mutation rejected (`409`).
- **P4-ADV-013:** Malformed media rejected by decoder/MIME allowlist.
- **P4-ADV-014:** CSRF missing/wrong token rejected on mutation.
- **P4-ADV-015:** SQL injection-like session identifiers rejected safely.
- **P4-ADV-016:** Performance harness does not mutate authoritative user fermentation sessions.
- **P4-ADV-017:** Attempt to create packaging session from Phase 4 route/table fails closed (leakage test).
- **P4-ADV-018:** Circular yeast reuse lineage rejected.
- **P4-ADV-019:** Out-of-order observed_at corrections preserve deterministic ordering in journal/export.
- **P4-ADV-020:** Phase 3 pitch handoff mutation attempt has no Phase 4 API path.

(Representative set; implementation traceability must map all FR/AC as needed.)

## 47. Testing strategy

| Layer | Applies to |
|---|---|
| DOMAIN UNIT TEST | calculations, stable gravity, plan materialization, state machine guards |
| DATABASE/POSTGRESQL TEST | invariants, cross-session FKs, append-only protections |
| API INTEGRATION TEST | endpoints, validation, idempotency, terminal rules |
| SECURITY TEST | CSRF, IDOR, media matrix |
| MIGRATION TEST | 0003→0004 round-trip and legacy survival |
| RECOVERY TEST | API restart, Redis loss, refresh reconstruction |
| BACKUP/RESTORE TEST | metadata + media bytes |
| PERFORMANCE TEST | isolated harness only |
| FRONTEND UNIT TEST | formatting/helpers/view-model derivations only |
| PLAYWRIGHT E2E | canonical Phase 4 flow + regressions |
| MANUAL/A11Y INSPECTION | only where automation insufficient, must be explicitly listed |

No requirement may be accepted from documentation alone.

## 48. Migration acceptance

Phase 4 migration must:

1. apply additively from Phase 3 head;
2. preserve all Phase 1A/2/3 data;
3. enforce new constraints/indexes/triggers for append-only and cross-session rules;
4. support fresh install and upgrade path;
5. support downgrade/round-trip if repository policy requires (same standard as Phase 3).

## 49. Regression requirements

Phase 4 acceptance requires green baseline evidence for Phase 3 (brew-day), Phase 2 (core/calculations/inventory), and Phase 1A vertical slice, in addition to Phase 4 gates.

## 50. Phase 5+ leakage matrix

| Capability | Phase | PHASE_4_STATUS | Rationale |
|---|---|---|---|
| Fermentation session management | 4 | ALLOWED_OPERATIONAL | core Phase 4 |
| Conditioning tracking | 4 | ALLOWED_OPERATIONAL | core Phase 4 |
| Yeast pitch history | 4 | ALLOWED_OPERATIONAL | core Phase 4 |
| Packaging readiness handoff facts | 4 | ALLOWED_HANDOFF_FACT | terminal seam to Phase 5 |
| Packaging sessions | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| Keg/can/bottle inventory | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| Carbonation operations | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| QA/QC plans | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| Automatic inventory consumption | 6 | PROHIBITED_OPERATIONAL_BEHAVIOR | ADR required |
| Purchasing/reorder automation | 6 | DEFERRED | later phase |
| Academy operations | 7 | PROHIBITED_OPERATIONAL_BEHAVIOR | later phase |
| Sensory/competition ops | 8–9 | PROHIBITED_OPERATIONAL_BEHAVIOR | later phase |
| Branding/digital menu | 9 | PROHIBITED_OPERATIONAL_BEHAVIOR | later phase |
| Knowledge Engine mutations | 10 | PROHIBITED_OPERATIONAL_BEHAVIOR | later phase |

## 51. Architectural non-goals

See section 5 and Phase 3 non-goals inheritance. No microservice split, broker, outbox, offline sync engine, new DB authority, or replacement BrewBatch aggregate.

## 52. Decision register

| DECISION_ID | QUESTION | SELECTED | RATIONALE | BASELINE_IMPACT | ADR_REQUIRED |
|---|---|---|---|---|---|
| P4-DEC-001 | Fermentation session start trigger | explicit start command after completed brew + pitch handoff | preserves brew-day terminal boundary | none | NO |
| P4-DEC-002 | Timer subsystem | reuse Phase 3 timer architecture with Phase 4 ownership | avoid competing authority | pattern reuse | NO |
| P4-DEC-003 | Inventory consumption on pitch | none in Phase 4 default | Phase 6/ADR gate | none | YES if later enabled |
| P4-DEC-004 | Yeast harvest/reuse ops | deferred; provenance fields only | roadmap sequencing | minimal additive fields | YES before ops |
| P4-DEC-005 | Pressure fermentation | deferred | not in authoritative PRD | none | NO |
| P4-DEC-006 | Completion primary evidence | stable gravity + checkpoints + brewer confirm | deterministic, explainable | none | NO |
| P4-DEC-007 | Phase 5 seam | packaging readiness handoff facts only | smallest forward seam | none | NO |
| P4-DEC-008 | Journal strategy | extend brew journal projection | preserve chronology | additive events | NO |

## 53. Open questions

| QUESTION_ID | QUESTION | BLOCKS_SPEC_ACCEPTANCE | DISPOSITION |
|---|---|---|---|
| P4-OQ-001 | Should multiple concurrent active fermentations per user be capped? | NO | default allow one session per brew session; no global cap |
| P4-OQ-002 | Manual yeast consumption command in Phase 4? | NO | deferred; ADR required |
| P4-OQ-003 | Exact conditioning mode enum from product marketing names | NO | canonical modes listed in section 17 |

`OPEN_BLOCKING_QUESTIONS=0`

## 54. Traceability contract

Future implementation evidence must map each `P4-FR-*` to:

- implementation file + symbol;
- exact executable test name (pytest or Playwright title);
- related `P4-AC-*` and `P4-ADV-*` rows;

Generation must fail if referenced tests are missing (same discipline as Phase 3).

## 55. Implementation authorization gate

```
PHASE_4_SPECIFICATION_STATUS=REVIEW_CANDIDATE
PHASE_4_IMPLEMENTATION_AUTHORIZATION=NOT_GRANTED
PHASE_4_IMPLEMENTATION_STARTED=NO
PHASE_5_IMPLEMENTATION=NOT_AUTHORIZED
PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED
NAS_ACCESS=NOT_AUTHORIZED
```

Implementation may begin only after independent specification review PASS, blocking findings closed, formal acceptance, and explicit implementation authorization.

## 56. Baseline compatibility issues

`BASELINE_COMPATIBILITY_ISSUES=0`

No accepted Phase 0–3 contract modification is required by this specification.

## 57. Specification self-review checklist

- [x] Phase 3 entry contract is decidable
- [x] Phase 5 handoff boundary explicit
- [x] Lifecycle/state machines defined
- [x] Correction/late-entry/terminal semantics defined
- [x] Idempotency/concurrency defined
- [x] Security/recovery/backup/performance/a11y contracts defined
- [x] Regression and leakage matrix defined
- [x] No blocking open questions remain

`SPECIFICATION_SELF_REVIEW=PASS`
