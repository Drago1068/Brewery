# Phase 4 Engineering and Acceptance Specification — Fermentation, Conditioning & Yeast

## 1. Document control

- Status: **REVIEW_CANDIDATE**
- Scope identifier: `PHASE_4_FERMENTATION_CONDITIONING_YEAST`
- Specification schema: `phase4-spec-v2` (remediation of independent review against `phase4-spec-v1`)
- Governing baselines:
  - Phase 0–2: accepted on `main`
  - Phase 3 tag: `v0.3.0-phase3`
  - Phase 3 baseline commit: `39c440f234149e67be6dfae948b33393857a153e`
  - Phase 3 accepted implementation: `2b82c2df2684cc599b3d84c1476513845566a517`
  - Phase 3 specification SHA-256: `6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF`
- Original reviewed specification commit: `e39a3fbd576c8cafaefad83a9686c5c152c08aec`
- Original reviewed specification SHA-256: `B5A80865CFFEAA104828E496C7EF4FCD1D45DE68422B68248D85A7F0E2058DF7`
- Expected migration: additive Alembic revision(s) from the accepted Phase 3 migration head to a verified Phase 4 head. The identifier is **not** selected by this specification. Implementation planning names the revision. Test evidence is “Phase 3 head → verified Phase 4 head”, never a hard-coded `0003→0004` identity.
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

Phase 4 consumes Phase 3; it does not rewrite Phase 3. Where this specification inherits a named Phase 3 contract, the inherited rule is normative and Phase 4 may only add the adaptations explicitly written here.

## 4. Scope

Phase 4 delivers:

1. explicit fermentation-session lifecycle from accepted pitch handoff through conditioning completion;
2. planned-versus-actual fermentation and conditioning semantics;
3. gravity, temperature, and pH tracking with deterministic curves and progress metrics;
4. yeast pitch history with optional lot linkage and minimum reuse **declaration** provenance (harvest/storage/reuse operations remain deferred);
5. post-pitch addition requirements and execution (`FERMENTATION`, `DRY_HOP` class additions deferred from Phase 3);
6. persistent long-duration timers and reminders reusing accepted Phase 3 authority patterns;
7. deterministic deviation, completion, waiver, correction, and late-entry contracts;
8. extended brew-session journal covering fermentation chronology without reordering Phase 3 events;
9. notes/media under accepted authorization and persistence rules;
10. API, security, recovery, backup/restore, performance, and accessibility acceptance for the above.

## 5. Non-scope

Phase 4 does **not** implement:

- packaging, kegging, bottling, canning, or finished-beer inventory operations;
- carbonation operations, draft/tap management, or digital menu;
- QA/QC plans, CIP/sanitation workflows, calibration/maintenance operations;
- automatic inventory reservation-to-consumption or purchasing;
- yeast harvest, storage, generation-count operations, or wash/propagation workflows;
- competition, sensory panels, Academy curriculum, branding assets;
- Brewer Knowledge Engine correlations or autonomous recommendations;
- pressure-fermentation hardware control or automated device actuation;
- email/SMS/push notification platforms;
- microservices, event brokers, transactional outbox, distributed workers, offline sync engines, new database authority, or new media subsystems;
- exact biological prediction or AI-authoritative completion/inventory/state mutation.

## 6. Phase 3 entry contract

Schema: `phase4-entry-v1`.

### 6.1 PHASE_4_ENTRY_STATE

Phase 4 begins only after an explicit owner command `StartFermentationSession`. There is no automatic start on brew completion.

Preconditions:

1. Caller is the owning user of the `BrewSession`.
2. `BrewSession.status = COMPLETED`.
3. Exactly one accepted `BrewPitchHandoff` exists for that session (`schema_version = phase3-pitch-handoff-v1`).
4. No `FermentationSession` with `status != ABORTED` exists for that `brew_session_id`.
5. The brew session is not `LEGACY_MASH_ONLY` unless a pitch handoff actually exists (the legacy kind does not waive the handoff requirement).

Authoritative Phase 3 source: the completed `BrewSession` row plus its unique `BrewPitchHandoff` row plus the current effective brew-side `ORIGINAL_GRAVITY` leaf **as of the start transaction**, identified by measurement ID. Phase 4 does not invent a second OG process point.

### 6.2 PHASE_4_ENTRY_REQUIRED_FACTS

Immutable inputs consumed from Phase 3 and pinned into `FermentationSession` / `YeastPitchReference` at start:

| Fact | Source | Availability at entry | Mutability in Phase 4 |
|---|---|---|---|
| `brew_session_id` | `BrewSession.id` | required | immutable reference |
| `recipe_version_id` | `BrewSession` snapshot | required | immutable reference |
| `pitched_at` | `BrewPitchHandoff.pitched_at` | required, non-null | immutable |
| `pitch_temperature_c` | `BrewPitchHandoff.pitch_temperature_c` | **nullable**; null is stored as `UNKNOWN` and is valid | immutable; never synthesized |
| `yeast_addition_note` | `BrewPitchHandoff.yeast_addition_note` | required | immutable |
| `pitch_actor_user_id` | `BrewPitchHandoff.actor_user_id` | required | immutable |
| `pitch_handoff_id` | `BrewPitchHandoff.id` | required | immutable reference |
| `original_gravity_consumption` | see §6.2.1 | may be `UNKNOWN` | pinned leaf; not silently refreshed |

`PITCH_CONFIRMED` is a reference-only stage instance created in the start transaction. It stores the pinned handoff facts. It is not an executable worksheet stage.

#### 6.2.1 Original-gravity consumption (`phase4-og-consumption-v1`)

Phase 3 defines `ORIGINAL_GRAVITY` as homogenized post-boil, chilled, **pre-pitch** wort (`phase3-measurement-v1`). Phase 4 **must not** relabel any `FERMENTATION_GRAVITY` as OG.

At start, in the same transaction:

1. Select the current effective brew-side `ORIGINAL_GRAVITY` leaf for the brew session, if any exists (`validation_status` accepted, not superseded).
2. Persist `og_source_measurement_id`, `og_source_correction_id` (null if the original row is the leaf), `og_canonical_sg`, `og_observed_at`, and `og_pinned_at` (server time).
3. If no accepted OG leaf exists (never recorded, or only waived with no measurement), persist `og_availability = UNKNOWN` and null value/IDs. Fermentation may start.
4. The first fermentation gravity is **never** copied into OG.

Later Phase 3 OG corrections remain permitted under the Phase 3 contract and do **not** automatically change the pinned Phase 4 consumption. An explicit owner command `ReconcileUpstreamOriginalGravity` may append a new `OriginalGravityConsumption` row that pins a later Phase 3 leaf. The original pin remains historical. Reconciliation:

- is allowed while the fermentation session is not `CLOSED` or `ABORTED`;
- requires the cited Phase 3 leaf to belong to the same owner and brew session;
- is completion-affecting if the canonical SG changes;
- never rewrites Phase 3 rows.

### 6.3 PHASE_4_ENTRY_OPTIONAL_FACTS

Optional enrichments at fermentation start (never retroactively rewriting Phase 3 handoff):

- linked `ingredient_lot_id` for pitched yeast, same owner, optional;
- manufacturer/strain/product/form metadata copied into the yeast-reference snapshot from lot metadata when a lot is linked, otherwise user-entered and labeled `USER_ENTERED`;
- fermenter equipment profile ID whose **contents** are snapshotted (§29);
- declared reuse provenance (§11);
- planned fermentation targets from `phase4-plan-v1` materialization (not optional as a snapshot row; the snapshot always exists, values may be `UNSPECIFIED`).

### 6.4 PHASE_4_ENTRY_VALIDATION

Starting fermentation fails closed with no partial writes:

| Condition | HTTP | Code |
|---|---|---|
| Unauthenticated | `401` | `UNAUTHENTICATED` |
| CSRF failure | `403` | `CSRF_REJECTED` |
| Brew session missing or not owned | `404` | established nondisclosure |
| Brew session not `COMPLETED` | `422` | `BREW_SESSION_NOT_COMPLETED` |
| Pitch handoff missing on an owned completed brew | `422` | `PITCH_HANDOFF_MISSING` |
| More than one handoff row (integrity) | `409` | `PITCH_HANDOFF_INTEGRITY` |
| Non-aborted fermentation session already exists | `409` | `FERMENTATION_SESSION_EXISTS` |
| Start after `CLOSED` (non-aborted session exists) | `409` | `FERMENTATION_SESSION_EXISTS` |
| Conflicting idempotent payload | `409` | `IDEMPOTENCY_KEY_REUSED` |
| Plan materialization failure | `422` | `PLAN_MATERIALIZATION_FAILED` with reasons |
| Recipe version inaccessible but brew session exists | start still allowed; recipe identity remains the brew snapshot reference | n/a |

Null `pitch_temperature_c` is **not** a validation failure.

### 6.5 PHASE_4_ENTRY_IDEMPOTENCY

Command: `StartFermentationSession`. Schema: `phase4-operation-v1`.

- `resource_scope` = `brew_session_id` (the scope exists before any fermentation session ID).
- `command_name` = `StartFermentationSession`.
- Replaying the same scoped operation returns the original `FermentationSession` without duplicate rows, including after that session later becomes `ABORTED`.
- A second initialization attempt with a **different** operation ID:
  - if a non-aborted session exists: `409 FERMENTATION_SESSION_EXISTS` with the existing session ID;
  - if only `ABORTED` session(s) exist: creates a new session that reuses the same accepted pitch handoff;
  - if the brew is `CLOSED` from Phase 4 (fermentation `CLOSED`): `409 FERMENTATION_SESSION_EXISTS`.

Stale clients: `expected_brew_session_revision` is required. Mismatch returns `409 STALE_REVISION` and creates nothing.

### 6.6 PHASE_4_ENTRY_FAILURE_BEHAVIOR

The start transaction is atomic and includes: session row, plan snapshot, OG pin, PITCH_CONFIRMED reference stage, ACTIVE_FERMENTATION stage instance, optional yeast reference, equipment snapshot, materialized addition requirements/reminders/timers, journal events, audit event, and operation result.

Failure creates no partial fermentation rows, timers, reminders, journal events, or reserved operation success. Validation errors are `422`; ownership/not-found are `404`; conflicts are `409`.

Correction after entry: Phase 3 brew/pitch facts remain immutable. Phase 4 may correct only Phase 4 enrichment fields listed in §23. OG changes use `ReconcileUpstreamOriginalGravity`, not measurement-type mutation.

Partial failure after commit of start is recovered by GET reconstruction; there is no compensating client-side start.

Authorization: owner only. No delegated roles.

## 7. Phase 5 handoff contract

Schema: `phase4-packaging-readiness-v1`.

### 7.1 READINESS FACTS versus PHASE 5 OPERATIONS

Phase 4 may emit versioned `PackagingReadinessHandoff` **readiness facts**. It must not execute packaging.

#### Authoritative readiness fields and provenance

| Field | Provenance | Nullability |
|---|---|---|
| `fermentation_session_id` | session PK | required |
| `brew_session_id` | pinned entry fact | required |
| `recipe_version_id` | pinned entry fact | required |
| `handoff_version` | positive integer, monotonic per session | required |
| `current` | exactly one current row per session | required |
| `status` | `READY` \| `NOT_READY` \| `READY_WITH_WAIVERS` \| `INVALIDATED` | required |
| `original_gravity_sg` | current OG consumption leaf | null iff `UNKNOWN` |
| `original_gravity_source_id` | pinned/reconciled measurement/correction ID | null iff `UNKNOWN` |
| `final_gravity_sg` | current effective last qualifying stable-gravity observation, else current last valid ferment gravity | null if none |
| `apparent_attenuation_ratio` | `packages.calculations.brewing.apparent_attenuation` via §13 adapter | null if undefined |
| `fermentation_completed_at` | `fermentation_current_completed_at` (latest successful `CompleteFermentation`); original first confirmation remains on the session as `fermentation_first_completed_at` | required for `READY`/`READY_WITH_WAIVERS`; null for `NOT_READY` |
| `conditioning_completed_at` | `conditioning_current_completed_at` of successful `CompleteConditioning`; **null** when conditioning skipped | null when skipped or not complete |
| `conditioning_skipped` | plan `CONDITIONING_NOT_REQUIRED` skip path | required boolean |
| `assessment_id` | `PackagingReadinessAssessment` PK | required |
| `evidence_summary` | IDs/versions of gravity leaves, checkpoints, waivers | required |
| `yeast_pitch_summary` | handoff ID + optional yeast-reference ID | required |
| `invalidated_at` / `invalidation_cause_id` | set when superseded or evidence-invalidated | null while current and valid |
| `journal_reconstruction_handle` | brew session ID + generation rule version | required |

Handoff status mapping is **§14.4**. `READY` means R1, R2, known OG, and no readiness-level waiver or R3-only override. `READY_WITH_WAIVERS` means R1, R2, and at least one contributing waiver or an R3-only override. After `CLOSED`, R1/R2 are evaluated from current evidence per §14.6 even when original Complete* assessment rows remain `INVALIDATED`.

Exactly one handoff row per session may have `current=true` (partial unique constraint or equivalent). Recording a new version sets the previous current row to `current=false` in the same transaction. The previous row is preserved.

`NOT_READY` is a valid recorded handoff when the owner records failed eligibility. `CloseFermentationSession` requires a current non-invalidated `READY` or `READY_WITH_WAIVERS` handoff. A later CLOSED-path `NOT_READY` version does not un-close the session.

`INVALIDATED` is appended status on a previously current handoff after completion-affecting correction/late entry/reconciliation. The row is preserved. A new current version may be recorded later.

### 7.2 PROHIBITED_PHASE_5_BEHAVIOR

Phase 4 must not create or mutate:

- `PackagingSession`, package units, kegs, cans, bottles;
- packaged-beer inventory transactions;
- tap assignments, menu publications, carbonation adjustments;
- QA/QC plans, CIP records, microbiology workflows;
- consumption/depletion events.

Requalification after invalidation is a Phase 4 assessment/handoff version. It is not a Phase 5 operation and must not create packaging rows.

## 8. Domain model

### 8.1 Authoritative aggregates and records

| Concept | Role | Aggregate? |
|---|---|---|
| `FermentationSession` | owned execution record for post-pitch lifecycle | yes (session root) |
| `FermentationPlanSnapshot` | immutable planned targets/schedules at session start | snapshot value owned by session |
| `OriginalGravityConsumption` | pinned/reconciled OG leaf | evidence record |
| `FermentationStageInstance` | ordered stage occurrences | part of session |
| `FermentationMeasurement` | append-only observation | evidence record |
| `FermentationMeasurementCorrection` | append-only supersession | evidence record |
| `FermentationTimer` | server-authoritative timer | child of session/stage |
| `FermentationReminder` | deterministic required-action projection | child of session/stage |
| `FermentationAction` | user-recorded intervention | evidence record |
| `FermentationAdditionRequirement` | materialized post-pitch obligation | plan child |
| `FermentationAdditionEvent` | planned-versus-actual addition fact | evidence record |
| `FermentationAdditionCorrection` | append-only addition supersession | evidence record |
| `FermentationDeviation` | deterministic departure record | derived/evidence |
| `FermentationCompletionAssessment` | explainable fermentation-complete decision | evidence record |
| `ConditioningAssessment` | explainable conditioning-complete decision | evidence record |
| `PackagingReadinessAssessment` | explainable readiness decision | evidence record |
| `FermentationWaiver` | explicit requirement waiver | evidence record |
| `YeastPitchReference` | Phase 4 enrichment linking handoff to lot/provenance | reference record |
| `PackagingReadinessHandoff` | versioned Phase 4 readiness fact | terminal record |
| `FermentationJournalEvent` | append-only chronology contributing to brew journal | projection/event |

No mandatory `BrewPlan`, `BrewBatch`, transactional outbox, or distributed worker is introduced.

### 8.2 Identity and ownership

- Every Phase 4 mutable resource is owned by exactly one user (same ownership model as Phase 3).
- `FermentationSession` references exactly one `brew_session_id` and inherits recipe/version identity from that session snapshot.
- Cross-session foreign keys for mutable evidence are prohibited except:
  - read-only `BrewPitchHandoff` / brew measurements for OG consumption;
  - optional yeast lot read;
  - optional `source_fermentation_session_id` / `source_yeast_reference_id` under §11 pair-agreement rules.
- Nested IDs (stage, measurement, assessment, lot, equipment, source session) are resolved only after owner scoping. Cross-owner IDs return `404`.

### 8.3 Mutability

- Plan snapshots, measurements, actions, additions, assessments, waivers, deviations, OG consumption pins, equipment snapshots, yeast-reference snapshots, and journal events are append-only with correction lineage; no silent overwrite.
- Stage/session state transitions are explicit commands with audit/journal records.
- Plan revisions after start are **prohibited**. There is no `ReviseFermentationPlan` command.
- Conditioning mode cannot be selected at fermentation-complete; it is frozen in the start snapshot.
- Terminal permissions are the matrix in §25, not this paragraph.

### 8.4 Stage occurrence cardinality

| Stage type | Instance rows per session | Status vocabulary |
|---|---|---|
| `PITCH_CONFIRMED` | exactly one, created at start | `COMPLETED` immediately (reference-only) |
| `ACTIVE_FERMENTATION` | exactly one row; **reused** after invalidation (§9.8) | `PENDING` until start commit completes as `ACTIVE`; then `ACTIVE`/`PAUSED`/`COMPLETED`/`ABORTED` |
| `CONDITIONING` | zero or one row; created only by first `StartConditioning`; **reused** after invalidation; never created on skip path | `ACTIVE`/`PAUSED`/`COMPLETED`/`ABORTED`/`INVALIDATED` |
| `HANDOFF_READY` | zero or one reference stage, created when a `READY` or `READY_WITH_WAIVERS` current handoff is recorded | not an independent executable worksheet |

A second `ACTIVE_FERMENTATION` or `CONDITIONING` **row** is denied (`409 STAGE_REPEAT_PROHIBITED`). After invalidation the existing row is reactivated (§9.8); that is not a second occurrence. Stage identity is `stage_instance_id`. Commands address that ID.

Session `status` is authoritative for lifecycle. Stage status is synchronized in the same transaction as the session command that changes it. `HANDOFF_READY` as a session status means a current non-invalidated ready handoff exists; the stage type of the same name is a reference marker only.

## 9. Lifecycle and state machines

Schema: `phase4-session-state-v1`.

### 9.1 FermentationSession states

Client-visible states after a successful start: `ACTIVE`, `PAUSED`, `FERMENTATION_COMPLETE`, `CONDITIONING`, `CONDITIONING_COMPLETE`, `COMPLETION_ASSESSED`, `HANDOFF_READY`, `CLOSED`, `ABORTED`.

`PLANNED` exists only inside the start transaction. It is not a client-editable state. A failed start never leaves a `PLANNED` row.

Uniqueness predicate (normative):

```
UNIQUE (brew_session_id) WHERE status <> 'ABORTED'
```

Interpretation:

- At most one non-aborted fermentation session per brew session, including `CLOSED`.
- `CLOSED` forbids a second start.
- `ABORTED` permits a later start that reuses the same accepted pitch handoff.
- Multiple nonterminal sessions per user are allowed only across different brew sessions. No user-wide concurrency cap (`P4-OQ-001`).

Invalid transitions return `409 INVALID_TRANSITION` without partial writes.

### 9.2 Stage vocabulary

Canonical fermentation-stage vocabulary:

1. `PITCH_CONFIRMED` (reference-only)
2. `ACTIVE_FERMENTATION`
3. `CONDITIONING`
4. `HANDOFF_READY` (reference-only marker)

`WARM_CONDITIONING`, `COLD_CONDITIONING`, `LAGERING`, `COLD_CRASH` are `conditioning_mode` attributes on the plan snapshot and, when created, on the single `CONDITIONING` stage instance. They are not independent session states. Generic/`OTHER` modes are rejected at materialization (`422`). Multiple ordered conditioning modes and runtime mode switches are **not in scope**.

### 9.3 Pause origin

`PAUSED` is a single session status. The session **must** persist `pause_origin_state` ∈ {`ACTIVE`, `CONDITIONING`} and `paused_stage_instance_id`.

Resume restores **only** that origin. A stale tab that sends resume with the wrong expected revision receives `409 STALE_REVISION`. Resume never invents a different origin.

### 9.4 Session transition table

Legend: INV = `409 INVALID_TRANSITION` and zero domain writes except safe conflict audit. Replay of the same operation returns the original result.

§9.4 is the **sole** session command transition authority. §9.5 is a non-normative index and must not permit a cell that lacks a row here. Every `A` in §9.5 has a row below.

| CURRENT_STATE | COMMAND/EVENT | PRECONDITIONS | NEXT_STATE | SIDE_EFFECTS | IDEMPOTENCY | INVALID_BEHAVIOR | CORRECTION_EFFECT |
|---|---|---|---|---|---|---|---|
| (none) | `StartFermentationSession` | §6 | `ACTIVE` | §6.6 children; `ACTIVE_FERMENTATION` ACTIVE; `started_at` server time | scope brew_session_id | §6.4 | n/a |
| `ACTIVE` | `PauseFermentationSession` | owner; expected revision | `PAUSED` | `pause_origin_state=ACTIVE`; pause `ACTIVE_TIME` timers `paused_by=SESSION_ACTION`; WALL_CLOCK continues | session+command | other commands per this table | note-only n/a |
| `PAUSED` (origin ACTIVE) | `ResumeFermentationSession` | expected revision; origin persisted | `ACTIVE` | resume only session-paused timers; restore ACTIVE_FERMENTATION ACTIVE | session+command | missing origin `409` | n/a |
| `PAUSED` (origin ACTIVE or CONDITIONING) | `AbortFermentationSession` | reason 10–1000 chars | `ABORTED` | §9.6; origin discarded | session+command | missing reason `422` | §25 |
| `ACTIVE` | `CompleteFermentation` | eligibility §14 or authorized override/waivers; expected revision | `FERMENTATION_COMPLETE` | persist confirmed assessment; complete fermentation-primary timers; set `fermentation_first_completed_at` if null else keep it; set `fermentation_current_completed_at` = server now; freeze availability-at-completion for this confirmation | session+command | `422 COMPLETION_INELIGIBLE` persists failed assessment, **increments revision**, state unchanged | §14.6 |
| `ACTIVE` | `AbortFermentationSession` | reason 10–1000 chars | `ABORTED` | §9.6 | session+command | missing reason `422` | §25 |
| `FERMENTATION_COMPLETE` | `StartConditioning` | plan not `CONDITIONING_NOT_REQUIRED`; expected revision | `CONDITIONING` | §9.8: create CONDITIONING row if none, else reactivate INVALIDATED row; never a second PK; materialize/recreate activation-scoped timers/reminders; set `conditioning_first_started_at` if null; set `current_activation_started_at` = server now | session+command | skip-only plan: `409 CONDITIONING_NOT_REQUIRED`; existing non-INVALIDATED CONDITIONING: `409 STAGE_REPEAT_PROHIBITED` | n/a |
| `FERMENTATION_COMPLETE` | `SkipConditioning` | snapshot `conditioning_required=false`; expected revision | `CONDITIONING_COMPLETE` | no CONDITIONING instance; `conditioning_skipped=true`; conditioning start/complete current timestamps null; persist skip assessment | session+command | if conditioning required: `409 CONDITIONING_REQUIRED` | n/a |
| `FERMENTATION_COMPLETE` | `AbortFermentationSession` | reason | `ABORTED` | §9.6 | session+command | n/a | §25 |
| `CONDITIONING` | `PauseFermentationSession` | expected revision | `PAUSED` | `pause_origin_state=CONDITIONING`; pause ACTIVE_TIME; WALL_CLOCK continues | session+command | n/a | n/a |
| `PAUSED` (origin CONDITIONING) | `ResumeFermentationSession` | expected revision | `CONDITIONING` | resume session-paused timers; CONDITIONING ACTIVE | session+command | n/a | n/a |
| `CONDITIONING` | `CompleteConditioning` | §14.3 or waivers/override | `CONDITIONING_COMPLETE` | persist conditioning assessment; set `conditioning_first_completed_at` if null; set `conditioning_current_completed_at` = server now; complete conditioning-primary timers | session+command | `422 COMPLETION_INELIGIBLE` + failed assessment + revision increment | §14.6 |
| `CONDITIONING` | `AbortFermentationSession` | reason | `ABORTED` | §9.6 | session+command | n/a | §25 |
| `CONDITIONING_COMPLETE` | `AssessPackagingReadiness` | expected revision | success READY/READY_WITH_WAIVERS → `COMPLETION_ASSESSED`; unsuccessful → remain `CONDITIONING_COMPLETE` | persist readiness assessment including unsuccessful; skip path uses R2 skipped | session+command | §14.4; override limits §14.5 | §14.6 |
| `CONDITIONING_COMPLETE` | `AbortFermentationSession` | reason | `ABORTED` | §9.6 including invalidate any assessments | session+command | n/a | §25 |
| `COMPLETION_ASSESSED` | `AssessPackagingReadiness` | expected revision | remain `COMPLETION_ASSESSED` | persist **new current** packaging assessment (success or INSUFFICIENT); previous packaging assessment INVALIDATED; no handoff change | session+command | §14.4–14.5 | §14.6 |
| `COMPLETION_ASSESSED` | `RecordPackagingReadinessHandoff` | latest packaging assessment exists; expected revision | READY or READY_WITH_WAIVERS → `HANDOFF_READY`; NOT_READY → remain `COMPLETION_ASSESSED` with current NOT_READY handoff | versioned handoff; exactly one `current=true` | session+command | missing assessment `422` | §14.6 |
| `COMPLETION_ASSESSED` | `AbortFermentationSession` | **denied** | — | — | — | `409 INVALID_TRANSITION` | n/a |
| `HANDOFF_READY` | `AssessPackagingReadiness` | expected revision | if new assessment READY or READY_WITH_WAIVERS: remain `HANDOFF_READY` (current handoff **unchanged** until RecordHandoff); if INSUFFICIENT/R1/R2 fail: `COMPLETION_ASSESSED` | persist new packaging assessment; on R1/R2 failure mark current handoff `INVALIDATED` | session+command | §14.4–14.5 | §14.6 |
| `HANDOFF_READY` | `RecordPackagingReadinessHandoff` | latest packaging assessment id; expected revision | remain `HANDOFF_READY` if READY/READY_WITH_WAIVERS; if recording NOT_READY → `COMPLETION_ASSESSED` | previous current `current=false`; new version current | session+command | `409` if assessment already bound to current handoff unless replay | §14.6 |
| `HANDOFF_READY` | `CloseFermentationSession` | current handoff READY or READY_WITH_WAIVERS and not INVALIDATED | `CLOSED` | `closed_at` server time; cancel remaining optional nonterminal timers cause `SESSION_CLOSED` | session+command | NOT_READY or INVALIDATED: `409 HANDOFF_NOT_READY` | no implicit reopen |
| `HANDOFF_READY` | `AbortFermentationSession` | **denied** | — | — | — | `409 INVALID_TRANSITION` | n/a |
| `CLOSED` | `AssessPackagingReadiness` | expected revision; §14.6 CLOSED path | remain `CLOSED` | persist packaging assessment from **current evidence** without CompleteFermentation/CompleteConditioning; unsuccessful INSUFFICIENT still persisted | session+command | ABORTED n/a | may follow evidence invalidation |
| `CLOSED` | `RecordPackagingReadinessHandoff` | latest CLOSED-path packaging assessment; expected revision | remain `CLOSED` | new current handoff version (READY, READY_WITH_WAIVERS, or NOT_READY); previous current=false | session+command | no assessment `422`; if current handoff already binds this assessment: replay or `409` | n/a |
| `CLOSED` | any other session command including Abort/Pause/Complete*/StartConditioning | — | — | — | replay only if identical prior success | `409 TERMINAL_SESSION` | §14.6 no reopen |
| `ABORTED` | `ResumeFermentationSession` | — | — | — | — | `409 INVALID_TRANSITION`; never resumable | §25 |
| `ABORTED` | `StartFermentationSession` (new operation) | uniqueness: only aborted sessions exist | new `ACTIVE` session | new identities; same pitch handoff | new operation | old start operation replays aborted session | n/a |
| any state | unlisted forward/backward edge | — | — | — | — | `409 INVALID_TRANSITION` | n/a |

`AssessPackagingReadiness` after skipped conditioning uses the skip path: fermentation confirmed complete AND `conditioning_skipped=true`.

### 9.5 Operation allowlist by state (session commands)

| Command | ACTIVE | PAUSED | FERM_COMPLETE | CONDITIONING | COND_COMPLETE | ASSESSED | HANDOFF_READY | CLOSED | ABORTED |
|---|---|---|---|---|---|---|---|---|---|
| Pause | A | D | D | A | D | D | D | D | D |
| Resume | D | A | D | D | D | D | D | D | D |
| CompleteFermentation | A | D | D | D | D | D | D | D | D |
| StartConditioning | D | D | A | D | D | D | D | D | D |
| SkipConditioning | D | D | A | D | D | D | D | D | D |
| CompleteConditioning | D | D | D | A | D | D | D | D | D |
| AssessPackagingReadiness | D | D | D | D | A | A (reassess) | A (reassess) | A (requalify only) | D |
| RecordPackagingReadinessHandoff | D | D | D | D | D | A | A (new version) | A (new version if invalidated or requalified) | D |
| Close | D | D | D | D | D | D | A | D | D |
| Abort | A | A | A | A | A | D | D | D | D |

Evidence mutations: §25.

### 9.6 Abort child effects

On `AbortFermentationSession`:

- session → `ABORTED`; every nonterminal stage → `ABORTED`; never resumable;
- every nonterminal timer → `CANCELLED` cause `SESSION_ABORTED`; retain deadlines and history;
- every unresolved reminder/addition → `CANCELLED` cause `SESSION_ABORTED`; no waiver fabricated;
- outstanding requirements remain unresolved;
- current assessments/handoffs if any → `INVALIDATED` cause `SESSION_ABORTED` (normally none exist on abort-permitted states);
- no new measurement/addition; corrections/annotations only under §25;
- one atomic audit + journal set.

Skip conditioning is **not** abort and **not** successful packaging readiness.

### 9.7 Timestamp effects of lifecycle commands

All of `started_at`, `paused_at`, `resumed_at`, `fermentation_first_completed_at`, `fermentation_current_completed_at`, `conditioning_first_started_at`, `conditioning_current_activation_started_at`, `conditioning_first_completed_at`, `conditioning_current_completed_at`, `assessed_at`, `handoff_recorded_at`, `closed_at`, `aborted_at` are **server-assigned UTC**. They are not client-supplied.

Immutable original facts: `fermentation_first_completed_at`, `conditioning_first_started_at`, `conditioning_first_completed_at`, each stage's first `completed_at` and first `started_at`. Invalidation never clears those fields.

Current facts: `*_current_*` and `current_activation_started_at` are updated on later successful complete/reactivate. Handoff provenance uses **current** completion instants. Journal shows both original and current.

### 9.8 Stage reactivation (`phase4-stage-reactivation-v1`)

Applies when §14.6 returns a session to `ACTIVE` or `CONDITIONING` without creating a second stage row.

| Field | Rule |
|---|---|
| `stage_instance_id` | Unchanged. No second PK. |
| `activation_ordinal` | Integer starting at 1; increment on each reactivation |
| `current_activation_started_at` | Server now on each activation including first start |
| Historical `started_at` / `completed_at` | First values immutable |
| Status | `INVALIDATED` or `COMPLETED` → `ACTIVE` (or `PAUSED` is not used as the reactivation landing status) |
| Timers | Cancel remaining nonterminal timers of the prior activation cause `COMPLETION_INVALIDATED`. Create **new** timer identities for the new ordinal from the plan snapshot. Do not reuse prior timer PKs. |
| Reminders | Same requirement rows. If satisfaction source was invalidated, reminder becomes `DUE` (unsatisfied). ACKNOWLEDGED remains ACKNOWLEDGED until evidence satisfies. New due_at recomputed from plan + current activation where the requirement is activation-scoped; `FROM_PITCH` additions keep original due_at. |
| Measurements | Remain attached to the same `stage_instance_id`. New observations use §18 current-activation window. |

`StartConditioning` after fermentation re-completion: if a CONDITIONING row exists with status `INVALIDATED`, reactivate it (ordinal+1). If none exists, create the first row (ordinal 1). If a row exists in `ACTIVE`, `PAUSED`, or `COMPLETED` (not invalidated): `409 STAGE_REPEAT_PROHIBITED`.

## 10. Fermentation plan versus actual

Schema: `phase4-plan-v1`. Materialized once in the start transaction. SHA-256 of the canonical snapshot is stored. Identical RecipeVersion + rule version + brew snapshot + pitched_at must produce the identical logical plan.

### 10.1 Source mapping

Inputs, in this order, all owned/readable through the brew session:

1. BrewSession execution snapshot (recipe_version_id, equipment_snapshot, calculation outputs).
2. RecipeVersion fields: `target_og`, `target_fg`, `apparent_attenuation`, `batch_size_liters`.
3. RecipeProcessStep rows with `step_type = FERMENTATION_FOUNDATION` ordered by `sequence ASC`, `id ASC`.
4. RecipeIngredient rows with `use_stage ∈ {FERMENTATION, DRY_HOP}`, ordered by `use_stage ASC`, `timing_minutes ASC NULLS FIRST`, `ingredient_id ASC`, `id ASC`. That order is the sole array order for canonical snapshot hashing. Database physical order is never authority.
5. Phase 3 exclusion provenance for those additions (they were not executed on brew day).

| Source | Mapping |
|---|---|
| Zero `FERMENTATION_FOUNDATION` steps | Sparse-valid. Targets `UNSPECIFIED`. `conditioning_required=false`. `conditioning_mode` null. Default checkpoints §10.3. |
| One `FERMENTATION_FOUNDATION` | Use `temperature_c` as fermentation target if present. `duration_minutes` as planned fermentation wall-clock duration if present (auxiliary only). `details` JSON keys listed below. |
| Two or more `FERMENTATION_FOUNDATION` | `422 PLAN_MATERIALIZATION_FAILED` reason `DUPLICATE_FERMENTATION_FOUNDATION`. |
| Conflicting `details.conditioning_mode` values | cannot occur with one row; invalid enum → `422`. |

Recognized `details` keys (unknown keys ignored, not fatal). Keys not in this table have no plan effect.

| Key | Schema | Effect |
|---|---|---|
| `conditioning_mode` | enum §17.1 or absent | mode frozen at start |
| `conditioning_temperature_c` | Decimal; optional | conditioning target |
| `conditioning_duration_minutes` | non-negative integer; optional | conditioning duration |
| `temperature_tolerance_c` | Decimal ≥ 0; optional | fermentation/conditioning tolerance source |
| `required_ph` | boolean; default false | PH checkpoint requiredness |
| `conditioning_required` | boolean; default derived | skip vs start path |
| `schedule` | array of `{effective_offset_minutes, target_temp_c}` | fermentation temperature schedule §10.2 |
| `conditioning_schedule` | array of `{effective_offset_minutes, target_temp_c}` | conditioning schedule §10.2; absent means single target or UNSPECIFIED |

Derivation of `conditioning_required`:

- if `details.conditioning_required` is boolean, use it;
- else if any of mode, conditioning temperature, or conditioning duration is present, `true`;
- else `false` (`CONDITIONING_NOT_REQUIRED`).

If `conditioning_required=false`, SkipConditioning is the only legal post-fermentation-complete path. StartConditioning is denied.

Mode is frozen at start. Selecting lagering (or any mode) at completion is denied.

### 10.2 Temperature schedule

If `details.schedule` is present it **must** be an array of objects `{effective_offset_minutes, target_temp_c}` (both required per element). Invalid shape → `422 PLAN_MATERIALIZATION_FAILED`. Canonical serialization sorts that array by `effective_offset_minutes ASC`.

- `effective_offset_minutes` is nonnegative integer minutes from **`pitched_at`** (Phase 3), clock `WALL_CLOCK`;
- duplicate offsets → `422`;
- interpolation is **piecewise constant**: a target applies from its offset inclusive until the next offset exclusive;
- after the last entry the last target remains in force while `ACTIVE_FERMENTATION` is current.

If no `schedule` key, a single target from `temperature_c` applies from `pitched_at` while fermentation is current, or `UNSPECIFIED` if temperature is null.

**Tolerance:** `details.temperature_tolerance_c` if present, else default `Decimal("1.0")` degC with provenance `PHASE4_DEFAULT_TOLERANCE_V1`. Record the chosen value and provenance in the snapshot. No unnamed tolerance.

If `details.conditioning_schedule` is present, the same array schema applies, anchored at `conditioning_first_started_at` (not later reactivations). If absent, a single conditioning target from `conditioning_temperature_c` applies, or `UNSPECIFIED`.

### 10.3 Checkpoints and requiredness

Logical requirement **template** identity uses UUIDv5 namespace `c4e21b8a-7d0e-5f33-9a14-8b6c2d91e0aa` and name `phase4-plan-v1:{recipe_version_id}:{requirement_class}:{stable_source}`. That template ID is identical across abort/restart sessions of the same recipe and is **not** a database primary key.

Session-owned requirement **row** ID is a newly generated UUID stored on `FermentationAdditionRequirement` / checkpoint rows. Uniqueness: `(fermentation_session_id, requirement_template_id)`. API paths use the session-owned row ID. Abort then restart must not collide on row ID.

| Requirement class | Required? | Waivable? |
|---|---|---|
| `FERMENTATION_GRAVITY_STABILITY` | yes (primary completion) | no as a class; individual extra gravity checkpoints may be waivable; stability itself uses §14/§15, override §24 |
| `FERMENTATION_TEMPERATURE` | yes iff planned fermentation temperature is not `UNSPECIFIED`; else optional | yes if materialized waivable |
| `FERMENTATION_PH` | yes iff `required_ph=true`; else optional | yes |
| `CONDITIONING_TEMPERATURE` | yes iff conditioning required and planned conditioning temperature present | yes |
| `CONDITIONING_DURATION` | yes iff conditioning required and planned duration present | yes |
| `PLANNED_ADDITION` | yes for each materialized FERMENTATION/DRY_HOP source | yes |
| `ATTENUATION_TARGET` | yes iff RecipeVersion `apparent_attenuation` is not null | yes |
| `ORIGINAL_GRAVITY_KNOWN` | yes for packaging `READY` only; not a fermentation-complete predicate | yes; readiness-only; never yields silent `READY` |

Missing planned values remain `UNSPECIFIED`. The API/UI must not invent them.

### 10.4 Plan versus actual

- Planned values are never overwritten by actual observations.
- Actual observations store provenance separately.
- Comparisons use `packages/calculations` with Decimal semantics and ADR-0008.
- Current observations always evaluate against the **start snapshot**, never against live RecipeVersion or live equipment profile edits.

## 11. Yeast model and provenance

Schema: `phase4-yeast-reference-v1`. Harvest, storage, wash, generation inference, and reuse **operations** are deferred (`P4-DEC-004`). Phase 4 supports declaration facts only.

### 11.1 Pitch facts

Phase 3 `BrewPitchHandoff` remains authoritative for `pitched_at`, nullable `pitch_temperature_c`, and yeast-addition note. Phase 4 may create at most one `YeastPitchReference` per fermentation session at start or by a later enrichment command while nonterminal (not CLOSED/ABORTED).

Allowed declaration fields:

- `ingredient_lot_id` (optional, same owner, not deactivated);
- snapshotted lot metadata (manufacturer/strain/product/form/generation-label as text if present on the lot at declaration time);
- quantity / pitch amount / viability inputs where supplied, labeled by provenance class;
- preparation method note;
- provenance class per field: `OBSERVED`, `USER_ENTERED`, `MANUFACTURER_PROVIDED`, `CALCULATED`, `ESTIMATED`, `UNKNOWN`;
- optional reuse declaration pair (§11.3).

Per-field provenance is stored. Changing live lot metadata after declaration does not change the snapshot.

### 11.2 Pitch history

Queryable pitch history per owner, per lot ID, and per fermentation session. Queries never mutate Phase 3 handoff rows. History returns snapshotted metadata, not live lot rows.

### 11.3 Reuse declaration pair

`source_fermentation_session_id` and `source_yeast_reference_id` are either **both null** or **both non-null**.

When both set:

1. Source session owner must equal current owner (`404` otherwise).
2. `source_yeast_reference_id` must belong to that source session (`422 SOURCE_PAIR_MISMATCH`).
3. Source session status must be `CLOSED` or `HANDOFF_READY` or `CONDITIONING_COMPLETE` or `COMPLETION_ASSESSED` (a finished or finishing fermentation). `ABORTED` sources are rejected (`422 SOURCE_SESSION_ABORTED`).
4. Source `pitched_at` must be strictly earlier than current session `pitched_at` (`422 SOURCE_TEMPORAL_INVALID`).
5. Self-reference is rejected (`422 YEAST_LINEAGE_CYCLE`).
6. Opening the source and current yeast-reference rows `SELECT ... FOR UPDATE` in ID order, the command validates the directed graph of declaration edges among the owner's references is acyclic. Concurrent A→B and B→A: one winner; loser `409 YEAST_LINEAGE_CYCLE`.

Generation numbers are not inferred. Storage dates are not operational. Declared generation text is `USER_ENTERED` or `MANUFACTURER_PROVIDED` only.

Correction of yeast reference: append-only replacement of mutable declaration fields (lot link, notes, source pair) while nonterminal; snapshots prior values. Lot identity used at pitch display remains the original snapshot unless the correction is accepted. Source-pair correction re-runs cycle validation. After CLOSED/ABORTED: annotation only, no source-pair change (§25).

## 12. Measurements

Schema: `phase4-measurement-v1`.

### 12.1 Supported measurement types

Instrument identity is optional. Method/context marked required must be present. Hard validation rejects; operational warnings do not rewrite values.

| Type | Canonical unit | Raw unit allowed | Hard validation (inclusive) | Required method/context | Required stage |
|---|---|---|---|---|---|
| `FERMENTATION_GRAVITY` | `SG` | `SG` or `Plato` | canonical `0.900 <= SG <= 1.300` | Method `HYDROMETER`/`REFRACTOMETER`/`OTHER`; raw scale/value; sample temperature when method is temperature-sensitive; conversion model ID if converted | `ACTIVE_FERMENTATION` |
| `FERMENTATION_TEMPERATURE` | `degC` | `degC` or `degF` | `-5 <= degC <= 40` | Method `THERMOMETER`/`PROBE`/`OTHER`; original value/scale | `ACTIVE_FERMENTATION` |
| `FERMENTATION_PH` | `pH` | `pH` | `2.5 <= pH <= 8.0` | Method `METER`/`STRIP`/`OTHER`; optional sample temperature | `ACTIVE_FERMENTATION` |
| `CONDITIONING_TEMPERATURE` | `degC` | `degC` or `degF` | `-5 <= degC <= 30` | Method as temperature | `CONDITIONING` |

`stage_instance_id` is **required** and must match the type’s stage. Optional was a defect; it is not permitted.

Pressure measurements are **deferred**.

Precision: persist canonical Decimal as received after conversion, without display rounding. Gravity canonical persistence uses the converted SG at calculation precision (full Decimal string in snapshots; PostgreSQL numeric scale as implemented, not less than 4 fractional digits for SG). Display may round OG/FG to 3 decimals and must not feed display values back (ADR-0008 / UNITS_AND_ROUNDING).

Source class is required: `OBSERVED` | `USER_ENTERED` | `ESTIMATED`. `UNKNOWN` is allowed only when the client explicitly sends it; it does not skip validation.

Measurement type is **immutable** after create. Corrections cannot change type. Wrong-type correction → `422 MEASUREMENT_TYPE_IMMUTABLE`.

FG below 1.000 may be stored if ≥ 0.900. Completion calculations that inherit `apparent_attenuation` domain constraints become `CALCULATION_UNDEFINED` (§13).

### 12.2 Measurement contract

Every measurement stores: `measurement_type`, raw value/unit, canonical value/unit, conversion model ID, `observed_at`, server `recorded_at`, `actor_user_id`, `source`, optional `instrument_reference`, `confidence`, `note`, per-field `provenance`, `fermentation_session_id`, required `stage_instance_id`, owner, operation ID, validation status, correction lineage.

Rules:

- Time semantics: §18.
- Corrections append new rows; never overwrite.
- Same-key idempotency replays the original measurement. Distinct operation IDs are distinct observations even at the same `observed_at`.
- Cross-session attachment is rejected by DB/API invariant (`409`/`422` as integrity).
- Temperature-to-gravity hydrometer correction is **not** a Phase 4 automatic rewrite. If a conversion model ID is supplied it must be an accepted named model; unknown model → `422`. Phase 4 does not add a new competing hydrometer table in this specification; absent model ID, raw canonical conversion is unit conversion only (Plato adapter or identity).

## 13. Deterministic calculations

All fermentation calculations remain in `packages/calculations` (or bounded domain packages), not UI or LLM. Phase 4 adapters **must not** alter accepted callers of existing functions.

| Function | Inputs | Output | Adapter / domain |
|---|---|---|---|
| `apparent_attenuation` | OG SG, FG SG | Decimal **ratio** in `[0,1]` | Call `brewing.apparent_attenuation`. Persist ratio. Display may show percent = ratio × 100 with ADR-0008 display rounding. Payload field `apparent_attenuation_ratio`. A percent field is display-only. If OG ≤ 1.000 or FG < 1.000 or FG > OG: catch `ValueError`, return `CALCULATION_UNDEFINED`, do not coerce 0.75 vs 75. |
| `fermentation_progress` | OG, current SG, target FG | Decimal ratio clipped to `[0, 1]` | `progress = (OG - current) / (OG - target_FG)` using Decimal. If denominator = 0 or OG ≤ target_FG or any input `UNKNOWN`: `CALCULATION_UNDEFINED`. If current > OG: clip to 0. If current < target_FG: clip to 1. Never negative unbounded. |
| `stable_gravity_evaluator` | ordered effective gravity leaves | `STABLE` / `NOT_STABLE` / `INSUFFICIENT_EVIDENCE` | §15 only |
| `abv_from_gravity` | OG, FG | ABV percent | Call `brewing.abv` = `(OG - FG) × 131.25`. If FG > OG: `CALCULATION_UNDEFINED`. If either `UNKNOWN`: undefined. FG < 1.000 is allowed by `abv` as specified in the accepted function (only FG > OG raises); still persist the function result. |
| `pitch_rate_estimate` | volume liters, OG, rate million/ml/°P | cells | Call `brewing.yeast_pitch_cells` only when all three inputs are present and valid. Else `NOT_COMPUTED`. Output labeled `CALCULATED`. Volume provenance: RecipeVersion `batch_size_liters` snapshot if present, else brew knockout volume current leaf if present, else missing. Do not invent volume. |
| `planned_vs_actual_temperature_delta` | planned, actual degC | signed delta | If planned `UNSPECIFIED`: `NOT_APPLICABLE`. |
| `plato_to_sg` | Plato Decimal | SG Decimal or hard reject | Adapter `phase4-plato-to-sg-v1`. **Domain:** raw Plato must lie in the closed image of accepted `specific_gravity_to_plato` over canonical SG `[0.900, 1.300]`. Compute `PLATO_MIN = specific_gravity_to_plato(Decimal("0.900"))` and `PLATO_MAX = specific_gravity_to_plato(Decimal("1.300"))` with the accepted function (independent Decimal evaluation ≈ `-28.220507` and `61.239729`; goldens must use the function, not these approximations as authority). If raw Plato `< PLATO_MIN` or `> PLATO_MAX`: `422 PLATO_OUT_OF_DOMAIN` and **no measurement row**. If inside the image, invert by Decimal binary search on SG `[0.900, 1.300]` until `|f(SG) - Plato| < Decimal("0.0000001")`. If 80 iterations complete without meeting residual: `422 PLATO_CONVERSION_FAILED`, **no row**, do not clamp to an endpoint. Round-trip golden: convert then `specific_gravity_to_plato` residual `< 1e-7`. Vector `100` Plato → `PLATO_OUT_OF_DOMAIN`. Just-inside endpoints convert; just-outside reject. |

Golden tests are required for every adapter, including undefined/missing cases. Intermediate calculation results are not rounded (UNITS_AND_ROUNDING).

## 14. Fermentation completion

Schemas: `phase4-fermentation-eligibility-v1`, `phase4-conditioning-eligibility-v1`, `phase4-readiness-eligibility-v1`.

### 14.1 Canonical completion statuses

These are **assessment outcomes**, not extra session states:

| Outcome | Meaning |
|---|---|
| `COMPLETION_ELIGIBLE` | Boolean table true; confirmation not yet accepted |
| `COMPLETION_CONFIRMED` | Owner confirmation command succeeded |
| `COMPLETION_WAIVED` | Table true only with active waivers on waivable predicates |
| `COMPLETION_OVERRIDDEN` | Owner override accepted under §24 |
| `INSUFFICIENT_EVIDENCE` | Table false; assessment row persisted; session state unchanged |
| `COMPLETION_INVALIDATED` | Previously confirmed assessment/handoff no longer current |

Elapsed duration alone never satisfies primary fermentation completion. Planned duration is `ELAPSED_TIME_AUXILIARY` and is not a primary predicate.

### 14.2 Fermentation eligibility Boolean table

Evaluate in order. Version the table in the assessment row.

| ID | Predicate | Missing / undefined | Operator / unit |
|---|---|---|---|
| F1 | `stable_gravity_evaluator = STABLE` | `INSUFFICIENT_EVIDENCE` | §15, canonical SG |
| F2 | If attenuation target specified: `apparent_attenuation_ratio >= target_ratio` | if OG/FG undefined: fail F2 unless waived | target is RecipeVersion `apparent_attenuation` already stored as ratio (`Numeric(6,5)`); compare ratios |
| F3 | Every required non-stability checkpoint satisfied or actively waived | unsatisfied required checkpoint fails | reminder/measurement identity |
| F4 | Session is `ACTIVE` | else command denied | state machine |

Primary evidence is F1. F2 is N/A (passes) when no attenuation target was snapshotted.

Confirmation is the `CompleteFermentation` command itself after F1–F4 pass, or with waivers/override. There is no silent auto-transition.

Unsuccessful assessments **persist** with outcome `INSUFFICIENT_EVIDENCE`, actor, server time, evidence set, and rule version. HTTP `422 COMPLETION_INELIGIBLE`. No session state change. This is distinct from a completion row: `CompleteFermentation` success is the only command that moves to `FERMENTATION_COMPLETE`.

### 14.3 Conditioning eligibility

| ID | Predicate | Notes |
|---|---|---|
| C0 | Session `CONDITIONING` | else invalid transition |
| C1 | If planned duration specified: `server_now - conditioning_first_started_at >= duration` | WALL_CLOCK from **first** start; pause and reactivation do not reset elapsed beer time |
| C2 | If planned temperature specified: at least one current effective `CONDITIONING_TEMPERATURE` with `|actual - target| <= tolerance` | if unspecified, N/A |
| C3 | Required conditioning checkpoints satisfied or waived |  |
| C4 | When both duration and temperature planned, C1 AND C2 |  |

Skip path: C* N/A; `SkipConditioning` records `CONDITIONING_NOT_REQUIRED`.

### 14.4 Packaging readiness eligibility

| ID | Predicate |
|---|---|
| R1 | Current fermentation assessment is `COMPLETION_CONFIRMED` or `COMPLETION_WAIVED` or `COMPLETION_OVERRIDDEN` and not invalidated |
| R2 | Conditioning skipped OR current conditioning assessment confirmed/waived/overridden and not invalidated |
| R3 | Current OG consumption known, **or** an active waiver of `ORIGINAL_GRAVITY_KNOWN`, **or** readiness override under §14.5 that is limited to R3 |

`READY` requires R1, R2, OG known, and no readiness-level waiver or R3 override.

`READY_WITH_WAIVERS` requires R1, R2, and at least one contributing waiver or an R3-only override. Missing OG without that waiver/override cannot be `READY` or `READY_WITH_WAIVERS`; the assessment is `INSUFFICIENT_EVIDENCE` / recordable as `NOT_READY`.

`ORIGINAL_GRAVITY_KNOWN` waiver:

- Actor: owner; reason 10–1000 characters; operation_id; expected revision.
- Allowed only while session is `CONDITIONING_COMPLETE`, `COMPLETION_ASSESSED`, or `HANDOFF_READY` (not `CLOSED`/`ABORTED`; not before fermentation is confirmed).
- Does not fabricate OG, does not satisfy F1/F2, does not satisfy R1/R2.
- Same requirement: one active waiver; replay same key; second active `409`.
- Effect: R3 passes via waiver; packaging status at most `READY_WITH_WAIVERS`.

### 14.5 OVERRIDE_WITH_REASON

- Actor: session owner only.
- Allowed only on `CompleteFermentation`, `CompleteConditioning`, or `AssessPackagingReadiness`.
- Requires reason 10–1000 characters and `override=true`.
- Fermentation override: at least one valid current `FERMENTATION_GRAVITY` leaf; may bypass F1–F3 only; cannot bypass F4 (must be `ACTIVE`).
- Conditioning override: may bypass C1–C3 only; cannot bypass C0.
- Readiness override: may bypass **R3 only**. If R1 or R2 is false: `409 OVERRIDE_PROHIBITED`, persist `INSUFFICIENT_EVIDENCE` packaging assessment, no READY handoff. If R1 and R2 hold and R3 fails: assessment `COMPLETION_OVERRIDDEN`, mappable handoff status `READY_WITH_WAIVERS` only.
- Must not fabricate measurements.
- Must not override ownership, CSRF, idempotency, uniqueness, pitch timestamp/note, or cross-session rules.
- Denied if session `ABORTED` (`409`). Readiness override after `CLOSED` is allowed only on `AssessPackagingReadiness` and still cannot bypass R1/R2 as evaluated from **current evidence** (§14.6 CLOSED path).
- Effect: assessment outcome `COMPLETION_OVERRIDDEN` for the bypassed predicates; they are recorded as overridden, not measured-true.

### 14.6 Invalidation, requalification, no implicit reopen

Completion-affecting events: new/corrected/late `FERMENTATION_GRAVITY` that changes §15 outcome or F2 inputs; required-checkpoint correction; attenuation-relevant OG reconciliation; waiver supersession; conditioning temperature/duration evidence that changes C1/C2.

Non-affecting: notes, media, non-required temperature/pH unless that checkpoint was in the assessment evidence set, yeast note-only edits.

**New measurement after eligibility but before confirmation:** no assessment yet; eligibility is recomputed on the next complete command.

**Correction / late entry / waiver after confirmation, session not CLOSED:**

1. Append evidence.
2. Mark current fermentation and/or conditioning and/or readiness assessments `COMPLETION_INVALIDATED` with cause ID.
3. Mark current handoff `INVALIDATED` if present (preserve row).
4. State destination (never a second stage PK):
   - if conditioning stage never started: session → `ACTIVE`; reactivate `ACTIVE_FERMENTATION` per §9.8;
   - if conditioning started or later (including `CONDITIONING_COMPLETE` / `COMPLETION_ASSESSED` / `HANDOFF_READY`) and affecting evidence is fermentation gravity/OG/F2: cancel CONDITIONING nonterminal timers cause `COMPLETION_INVALIDATED`; set CONDITIONING status `INVALIDATED`; session → `ACTIVE`; reactivate `ACTIVE_FERMENTATION` per §9.8. Later `StartConditioning` **reuses** the INVALIDATED CONDITIONING row;
   - if affecting evidence is conditioning-only: session → `CONDITIONING`; reactivate the same CONDITIONING instance per §9.8 (status ACTIVE).
5. Child reminders: §9.8.
6. Original assessment rows and `*_first_*` timestamps remain. `*_current_completed_at` is set null until the next successful complete command.

**After CLOSED:** session remains `CLOSED`. No return to `ACTIVE` or `CONDITIONING`. Current handoff becomes `INVALIDATED` / effective readiness `NOT_READY`. There is **no** `ReopenFermentationSession` and no `CompleteFermentation`/`CompleteConditioning` after CLOSED. Do **not** null `*_first_*` or `*_current_completed_at`. Those last confirmation instants remain the handoff provenance timestamps. New packaging assessments attach the current evidence-set IDs.

CLOSED requalification (makes AC-026 exact):

- `AssessPackagingReadiness` evaluates F1–F3 and C1–C3 **against current effective evidence** in the same transaction (skip path if `conditioning_skipped=true`). It does **not** require non-invalidated fermentation/conditioning assessment rows. R1 is true iff current evidence would currently satisfy fermentation confirmation predicates (or waivers/override still valid for those predicates). R2 likewise for conditioning or skip. Original Complete* assessment rows stay `INVALIDATED`.
- The new packaging assessment stores the evidence set actually used.
- `RecordPackagingReadinessHandoff` may then emit a new current version (`READY` / `READY_WITH_WAIVERS` / `NOT_READY`) while status remains `CLOSED`.
- New measurements/additions remain late-entry only (§24); they do not reopen stages.

**Note-only correction:** no invalidation.

**Concurrent confirmation:** §32.

**Evidence invalidation after conditioning started:** fermentation-affecting path above; do not rewrite Phase 3 `BrewSession`.

## 15. Stable gravity contract

Algorithm `phase4-stable-gravity-v1`. Normative. Examples are illustrative only.

### 15.1 Inputs

Effective leaves: original `FERMENTATION_GRAVITY` rows for this session whose current correction leaf is valid (not superseded, passed hard validation).

### 15.2 Ordering

Sort by `(observed_at ASC, recorded_at ASC, measurement_id ASC)`.

Same `observed_at` under different operation IDs: two observations, tie-broken by `recorded_at` then `id`.

Same operation ID + same canonical payload: not a second observation (replay).

### 15.3 Window

Let `N` be the count of effective leaves.

- If `N < 3`: `INSUFFICIENT_EVIDENCE`.
- Otherwise take the **last three** observations in the ordered list (fixed window; **no** subset search; **do not** skip a newer disqualifying reading).

### 15.4 Spacing

For consecutive pairs in the window `(a,b)` and `(b,c)`: require `observed_at` difference ≥ 24 hours exactly (`86400` seconds), inclusive. If either pair is closer: `NOT_STABLE`. Earlier triples are irrelevant.

### 15.5 Tolerance equation

Normalize each window member to canonical SG (Plato via §13 adapter). Let `spread = max(sg) - min(sg)` using Decimal, no extra rounding.

`STABLE` iff `spread <= Decimal("0.002")`.

This is the **full-window range**, not pairwise adjacent differences.

### 15.6 Boundary vectors (golden, expected outcomes)

| Vector | Expected |
|---|---|
| 2 valid observations | `INSUFFICIENT_EVIDENCE` |
| 3 equal SG at 0h, 24h, 48h | `STABLE` |
| 1.014, 1.012, 1.010 at 0h, 24h, 48h | `NOT_STABLE` (spread 0.004) |
| 1.014, 1.013, 1.012 spread exactly 0.002 | `STABLE` |
| Same with spread `0.0020001` | `NOT_STABLE` |
| 0h, 23h59m59.999999s, 48h | `NOT_STABLE` (spacing) |
| Stable 0h/24h/48h plus newest 49h reading 1.020 | `NOT_STABLE` (window is last three including 1.020) |
| Same observed_at, different operation IDs | two observations; order by recorded_at, id |
| Same operation, same payload | replay; count unchanged |
| Correction of middle reading | superseded excluded; recompute on remaining leaves |
| Late reading inside last window | included if it is among last three leaves |
| Plato near 0.002 boundary | convert then apply spread |
| Stable but FG > OG or FG < 1.000 | stability may be `STABLE`; attenuation/progress may be undefined; eligibility F2 handles attenuation |

Late entries and corrections always recompute from current leaves. Waiver does not fabricate stability. Override does not change this function’s output; it bypasses using F1 in §14.5.

## 16. Temperature management

Distinguish `TARGET` (snapshot), `MEASURED` (observation), `ESTIMATED` (explicit derived only).

Excursion deviation when a target exists and `|measured - target| > tolerance` using the snapshot target applicable at `observed_at` (§10.2).

BICOS monitors and records; it does not control hardware.

## 17. Conditioning

### 17.1 Modes

Authorized modes when declared in the plan snapshot:

- `WARM_CONDITIONING`
- `COLD_CONDITIONING`
- `LAGERING`
- `COLD_CRASH`

No runtime switch. No second mode occurrence.

### 17.2 Completion

§14.3. Skipping only when snapshot `conditioning_required=false`.

## 18. Time semantics

All persisted instants are UTC. Naive local timestamps and ambiguous DST local civil times are rejected (`422 TIMESTAMP_NOT_UTC`). Clients must send RFC 3339 with explicit offset; server stores UTC. Duration policy never interprets a local calendar without this conversion.

Inherited from Phase 3 §6.8 unless a row says otherwise: `recorded_at` is always server-assigned; `observed_at` may not be more than five minutes in the future relative to server receipt.

Process chronology for a stage-bound measurement:

- If the stage status is `ACTIVE` or `PAUSED`: `observed_at` must be in `[current_activation_started_at - 5 minutes, server_now + 5 minutes]`. Historical `completed_at` is **not** an upper bound while the stage is active.
- If the stage status is `COMPLETED`: `observed_at` must be in `[first_started_at - 5 minutes, completed_at + 5 minutes]` and late-entry §24 applies.
- If the stage status is `INVALIDATED`: new normal measurements are denied (`409 STAGE_NOT_ACTIVE`) until §9.8 reactivation.
- Always `observed_at >= pitched_at - 5 minutes`.

| FIELD | MEANING | SOURCE | TIMEZONE | FUTURE_ALLOWED | LATE_ENTRY_ALLOWED | CORRECTABLE | ORDERING_RULE | TERMINAL_EFFECT |
|---|---|---|---|---|---|---|---|---|
| `pitched_at` | Phase 3 pitch instant | BrewPitchHandoff | UTC | n/a | no via Phase 4 | no | process epoch | immutable |
| `observed_at` | when the sample/event occurred | client, validated | UTC | ≤ 5 min skew | yes, §24 windows | yes via correction row | journal process time for measurements | does not change session terminal stamps |
| `recorded_at` | server receipt of the command | server only | UTC | n/a (server now) | n/a | no | journal record time | set once |
| `occurred_at` (journal) | event family process time | server: for measurements = observed_at; for commands = recorded_at | UTC | command = now | derived | no independently | `(occurred_at, recorded_at, id)` | regeneration only |
| `due_at` | reminder/timer due | server from plan offset + anchor | UTC | planned future ok | n/a | via inherited timer revision | plan order | freeze on terminal cancel |
| `schedule.effective_at` | planned target switch | `pitched_at + offset` or `conditioning_first_started_at + offset` | UTC | planned | n/a | no (plan immutable) | offset ASC | snapshot |
| `started_at` / first `completed_at` / `closed_at` / `aborted_at` | original lifecycle facts | server | UTC | no | no | no | session history | never rewritten |
| `current_activation_started_at` / `*_current_completed_at` | current activation / latest confirmation | server | UTC | no | no | no (updated only by defined commands) | current window | handoff uses current |
| `corrected_at` | alias of correction `recorded_at` | server | UTC | no | within correction window | n/a | chain order | append |
| `waived_at` | waiver `recorded_at` | server | UTC | no | waiver window | supplemental note only | waiver id | §25 |
| `og_pinned_at` | OG consumption pin | server | UTC | no | reconcile command | new pin row | pin version | historical pins kept |

Seven-day action-note window from original spec is **not selected**. Notes/annotations inherit Phase 3: nonterminal any time; CLOSED/ABORTED no later than **seven calendar days after terminal time**. Completion-affecting measurements inherit Phase 3 24-hour/30-day table as adapted in §24.

## 19. Timers

Reuse Phase 3 timer semantics (`ADR-0006`) with Phase 4 ownership:

- PostgreSQL authoritative; browser/Redis are not timer authority;
- states: `PENDING -> RUNNING <-> PAUSED -> COMPLETED`, deadline path `EXPIRED -> ACKNOWLEDGED | COMPLETED`, exceptional `CANCELLED`;
- clock bases: primarily `WALL_CLOCK` for multi-day fermentation; `ACTIVE_TIME` only where the snapshot explicitly declares it;
- extend/replace/cancel/complete/acknowledge identical to Phase 3 revision/replacement contract;
- API restart, browser closure, Redis loss, container restart: reconstruct from PostgreSQL on GET; remaining WALL_CLOCK time is `due_at - server_now`;
- deadline passing during outage: on next reconstruction the timer is `EXPIRED` if `server_now >= due_at` and was not completed/cancelled; a single expiry event is appended if not already recorded;
- replacement/revision/cancellation: inherited uniqueness per timer ID;
- duplicate satisfaction: same operation replay; second distinct complete conflicts `409`.

Abort/complete/skip/invalidation child effects: §9 and §14.6.

Phase 4 introduces no competing timer subsystem.

## 20. Reminders

Reuse Phase 3 reminder lifecycle:

`SCHEDULED -> DUE -> COMPLETED` with paths through `ACKNOWLEDGED`, `SKIPPED`, `CANCELLED`, `EXPIRED`.

`ACKNOWLEDGED != SATISFIED`. Acknowledgement never satisfies a required measurement or addition.

Satisfaction source is the measurement/addition/waiver identity. Correction moves the current satisfaction source to the effective leaf (Phase 3 §6.5 adaptation). Waiver versus later evidence: late eligible evidence supersedes waiver (`SUPERSEDED_BY_EVIDENCE`); original waiver retained.

Categories: gravity reading, temperature observation, temperature change, fermentation check, conditioning transition, conditioning completion, planned addition.

## 21. Actions and post-pitch additions

### 21.1 Action taxonomy (`phase4-action-v1`)

Enum (closed):

- `TEMPERATURE_ADJUSTMENT_NOTE`
- `DRY_HOP_PREPARATION`
- `FERMENTATION_INTERVENTION`
- `CONDITIONING_NOTE`
- `UNPLANNED_ADDITION_REFERENCE`
- `OTHER_NOTE`

Each stores actor, `occurred_at` (client, validated), `recorded_at` (server), type, context, `planned=false` for unplanned, optional note ≤ 4000 chars, audit trail. Actions do not satisfy gravity stability. An action may satisfy a reminder only when that reminder’s requirement class is `ACTION_ACK` (none are required by default in `phase4-plan-v1`).

### 21.2 Post-pitch addition mapping (`phase4-addition-schedule-v1`)

Phase 3 excluded `FERMENTATION` and `DRY_HOP` from brew-day timing. Phase 4 materializes them at fermentation start.

| Phase 2 `use_stage` | Stage assignment | Timing basis | Offset | Clock | Missing timing |
|---|---|---|---|---|---|
| `FERMENTATION` | `ACTIVE_FERMENTATION` | `FROM_PITCH` | `timing_minutes * 60` seconds from `pitched_at`; null/0 → `AT_FERMENTATION_START` (due when ACTIVE_FERMENTATION becomes ACTIVE, i.e. start commit) | `WALL_CLOCK` | treat as `AT_FERMENTATION_START` |
| `DRY_HOP` | `ACTIVE_FERMENTATION` | `FROM_PITCH` | `timing_minutes * 60` from `pitched_at`; null/0 → `AT_FERMENTATION_START` | `WALL_CLOCK` | treat as `AT_FERMENTATION_START` |

`timing_minutes=2880` means due at `pitched_at + 48 hours`, not session-start, not contact duration, not conditioning-start.

Negative timing → `422` at materialization. One planned occurrence per source ingredient row. `RUNTIME_REPEAT_ALLOWED` is **denied** for these Phase 4 requirements (`runtime_occurrence_policy=DO_NOT_COPY`).

Unplanned additions: allowed while session is `ACTIVE` or `CONDITIONING` (not PAUSED for new execution; correction still allowed) via `RecordUnplannedFermentationAddition` with `planned=false`. Distinct operation IDs create distinct events.

Execution creates append-only `FermentationAdditionEvent` with **zero inventory effect** (no reservation conversion, no `CONSUMPTION`).

Correction adapts `phase3-addition-correction-v1`: current-leaf only, same-owner/session/stage, nonforking, `409 ADDITION_CORRECTION_TARGET_SUPERSEDED`, correctable actual quantity/time/status/lot/note, immutable planned identity. Reminder effects match Phase 3 §6.5.

Waived planned addition: reminder `SKIPPED` with waiver source; later execution supersedes waiver.

## 22. Deviations

System-derived or user-recorded.

Identity for derived deviations: UUIDv5 namespace `d81f0c2e-4a77-5b1d-9e08-3c55a91b7f10` name `phase4-deviation-v1:{session_id}:{class}:{source_evidence_id}:{plan_hash}`.

Classes: `TEMPERATURE_EXCURSION`, `MISSED_REMINDER_DEADLINE`, `GRAVITY_TRAJECTORY`, `STABLE_GRAVITY_BROKEN`.

Unique current leaf per `(session_id, class, source_evidence_id)`. Recalculation appends a successor and marks prior `SUPERSEDED`. Historical rows remain. User-recorded deviations have random UUIDs and are not auto-superseded.

Correcting the temperature that caused an excursion: append superseding comparison; do not delete history.

## 23. Corrections

Append-only correction lineage. Only the current leaf may be corrected. Cycles and forks `409`. Stale `correction_of_id` → `409 CORRECTION_TARGET_SUPERSEDED`.

Reason 10–1000 characters. Server `recorded_at`.

| Resource | Mutable via correction | Immutable | Current-leaf rule |
|---|---|---|---|
| Measurement | value, unit (compatible), context, `observed_at`, note, method | identity, type, owner, session, stage, original ID | unique successor per leaf |
| Addition event | Phase 3-adapted actual fields | planned identity, owner, session, stage | same |
| Action | note, `occurred_at` | type, actor chain, identity | same |
| Waiver | supplemental note only | original waiver fact, requirement, effect | no replacement |
| Assessment / handoff | not rewritten; invalidation + new version | original row | current flag |
| Yeast reference | lot, source pair, notes, quantity inputs while nonterminal | owner, session, original snapshot copy | append version |
| Equipment snapshot | none | entire snapshot | n/a |
| Deviation | resolution note | derived identity | successor for derived |
| OG consumption | new pin row only | prior pins | current pin |
| Plan | none | entire snapshot | n/a |
| Pitch handoff facts | none | Phase 3 | n/a |
| Session ownership / brew link | none | — | n/a |

Cross-session correction prohibited.

## 24. Late entry

Phase 4 **explicitly inherits** Phase 3 §6.8 windows, mapped onto fermentation session terminal times. The previous unselected “7 days unless CLOSED policy forbids” rule is withdrawn for measurements.

`recorded_at` server-assigned. Future `observed_at` ≤ 5 minutes. Reason 10–1000 chars. `late_entry=true`. `expected_session_revision` required when nonterminal.

| Late-evidence class | Allowed states and fixed boundary | Deterministic effect |
|---|---|---|
| Measurement on currently `ACTIVE`/`PAUSED` stage | `observed_at` in §18 current-activation window; not classified late solely because a historical `completed_at` exists | Normal append; `late_entry=false` |
| Measurement after stage `COMPLETED`, session not CLOSED/ABORTED | Target stage `COMPLETED` (not INVALIDATED); submit ≤ 24 hours after that stage's **first** `completed_at`; `observed_at` in the COMPLETED window of §18 | Append; `late_entry=true`; original first completion unchanged |
| Addition after stage `COMPLETED`, session not CLOSED/ABORTED | ≤ 24 hours after stage first `completed_at` | Append; reminder/waiver projection |
| `RecordAction` after stage or session terminal | New actions never use the addition 24-hour window | After `CLOSED`/`ABORTED`: `409 TERMINAL_SESSION` for CREATE. Correction of an **existing** action ≤ 30 days. |
| Measurement or addition after session `CLOSED` | ≤ 24 hours after `closed_at`; target stage must exist; measurements and planned/unplanned additions allowed; **not** `RecordAction` | Append evidence only; no new stage/timer; no session reopen; may invalidate current handoff; `available_at_original_session_completion=false` |
| New measurement/addition/action after `ABORTED` | Prohibited | `409 TERMINAL_SESSION_EVIDENCE_PROHIBITED` |
| Correction of existing measurement/addition/action | Nonterminal any time; `CLOSED` or `ABORTED` ≤ 30 calendar days after terminal time | Append correction; current leaf; may invalidate completion if affecting |
| Note/annotation | Nonterminal any time; `CLOSED`/`ABORTED` ≤ 7 calendar days after terminal | Append; never satisfies requirements |
| Yeast source-pair/lot change | Nonterminal only | After CLOSED/ABORTED: DENY (`409`). Annotation note ≤7d allowed. |
| Equipment snapshot | never after start | DENY all mutation |
| Media | Nonterminal `ACTIVE` or `CONDITIONING` or `PAUSED` only | No new upload after `CLOSED`/`ABORTED` |
| Journal regeneration | Any state | Read-only |

Expired windows: `409 LATE_ENTRY_WINDOW_CLOSED`.

## 25. Terminal behavior

### 25.1 Post-terminal matrix (one row per resource class)

Cells: `ALLOW` / `DENY` / `ALLOW_WITH_CONDITIONS`. After `CLOSED` unless a column says ABORTED.

| Resource | READ | CREATE | CORRECT | LATE_ENTRY | WAIVE | REVISE | DELETE | ADD_NOTE | ADD_MEDIA | EXPORT | INVALIDATE_COMPLETION | REOPEN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Session/stage/plan | ALLOW | DENY | DENY state rewrite | DENY new stages | DENY | DENY plan | DENY | ALLOW_WITH_CONDITIONS ≤7d | DENY | ALLOW | ALLOW_WITH_CONDITIONS via evidence; session stays CLOSED | DENY |
| Fermentation measurement | ALLOW | DENY normal; LATE_ENTRY ≤24h after close | ALLOW_WITH_CONDITIONS ≤30d | ALLOW_WITH_CONDITIONS ≤24h create | DENY new waiver | DENY overwrite | DENY | via note | DENY | ALLOW | if affecting, invalidate handoff | DENY |
| Conditioning measurement | ALLOW | same | same | same | DENY | DENY | DENY | via note | DENY | ALLOW | if affecting | DENY |
| Action | ALLOW | DENY | ALLOW_WITH_CONDITIONS existing action ≤30d (note/`occurred_at` only) | DENY new action | DENY | DENY | DENY | ALLOW_WITH_CONDITIONS ≤7d session note | DENY | ALLOW | DENY | DENY |
| Addition | ALLOW | DENY normal; ALLOW_WITH_CONDITIONS planned/unplanned execute ≤24h after `closed_at` per §24 | ALLOW_WITH_CONDITIONS ≤30d | ALLOW_WITH_CONDITIONS ≤24h create | DENY | DENY | DENY | ALLOW_WITH_CONDITIONS ≤7d | DENY | ALLOW | if checkpoint satisfaction changes | DENY |
| Yeast reference | ALLOW snapshots | DENY | DENY source-pair/lot; ALLOW_WITH_CONDITIONS annotation note ≤7d | DENY | DENY | DENY | DENY | ALLOW_WITH_CONDITIONS ≤7d | DENY | ALLOW | n/a | DENY |
| Equipment snapshot | ALLOW | DENY | DENY | DENY | DENY | DENY | DENY | DENY | DENY | ALLOW | n/a | DENY |
| Timer | ALLOW | DENY | DENY new transitions | DENY | DENY | DENY | DENY history | DENY | DENY | ALLOW via session | n/a | DENY |
| Reminder | ALLOW | DENY | DENY except projection from evidence | n/a | DENY new | DENY | DENY | DENY | DENY | ALLOW | satisfaction may move | DENY |
| Waiver | ALLOW | DENY | supplemental note ≤7d | n/a | DENY new | DENY original | DENY | supplemental | DENY | ALLOW | n/a | DENY |
| Assessment / handoff | ALLOW including INVALIDATED | ALLOW_WITH_CONDITIONS new version on requalify | DENY rewrite | n/a | DENY | new version only | DENY original | DENY | DENY | ALLOW | current flag moves | DENY session reopen |
| Notes | ALLOW | ALLOW_WITH_CONDITIONS ≤7d | DENY overwrite; append | n/a | n/a | n/a | DENY silent erase | — | — | ALLOW | n/a | DENY |
| Media metadata/bytes | ALLOW retrieval | DENY upload | DENY | DENY | n/a | DENY | DENY silent erase | n/a | DENY | ALLOW; missing bytes `MEDIA_UNAVAILABLE` | n/a | DENY |
| Journal | ALLOW | DENY user-authored operational events | DENY | derived | n/a | ALLOW read-only regen | DENY | via evidence | via evidence | ALLOW | reflect invalidation | n/a |

### 25.2 ABORTED allowlist

Same as Phase 3 aborted mapping for new Phase 4 records:

- READ, EXPORT, journal regen, media **retrieval** ALLOW;
- new measurement/addition/action DENY;
- correction ALLOW_WITH_CONDITIONS ≤30d;
- notes ALLOW_WITH_CONDITIONS ≤7d;
- new waiver, media upload, resume, start children, reopen DENY;
- new start of a **different** fermentation session for the same brew ALLOW under §6.5.

## 26. Journal

Extend brew-session journal projection with Phase 4 events **without breaking Phase 3 ordering**.

Accepted Phase 3 order is `(occurred_at ASC, recorded_at ASC, id ASC)` or accepted equivalent. Phase 4 **uses that same merge key** across mixed events. Phase 4 must not assign a sequence that reorders predecessor events. A Phase 4-local monotonic `sequence` may exist for internal use but is **not** the brew-journal order key.

Closed event types (typed, versioned payloads):

`FERMENTATION_SESSION_STARTED`, `FERMENTATION_STAGE_ENTERED`, `FERMENTATION_STAGE_PAUSED`, `FERMENTATION_STAGE_RESUMED`, `FERMENTATION_STAGE_REACTIVATED`, `FERMENTATION_SESSION_ABORTED`, `FERMENTATION_MEASUREMENT_RECORDED`, `FERMENTATION_MEASUREMENT_CORRECTED`, `FERMENTATION_TIMER_STARTED`, `FERMENTATION_TIMER_PAUSED`, `FERMENTATION_TIMER_RESUMED`, `FERMENTATION_TIMER_COMPLETED`, `FERMENTATION_TIMER_EXPIRED`, `FERMENTATION_TIMER_CANCELLED`, `FERMENTATION_TIMER_REPLACED`, `FERMENTATION_REMINDER_SCHEDULED`, `FERMENTATION_REMINDER_DUE`, `FERMENTATION_REMINDER_ACKNOWLEDGED`, `FERMENTATION_REMINDER_COMPLETED`, `FERMENTATION_REMINDER_SKIPPED`, `FERMENTATION_REMINDER_CANCELLED`, `FERMENTATION_REMINDER_EXPIRED`, `FERMENTATION_ACTION_RECORDED`, `FERMENTATION_ACTION_CORRECTED`, `FERMENTATION_ADDITION_RECORDED`, `FERMENTATION_ADDITION_CORRECTED`, `FERMENTATION_DEVIATION_RECORDED`, `FERMENTATION_DEVIATION_SUPERSEDED`, `FERMENTATION_WAIVER_RECORDED`, `FERMENTATION_WAIVER_SUPERSEDED`, `FERMENTATION_COMPLETION_ASSESSED`, `FERMENTATION_COMPLETION_INVALIDATED`, `CONDITIONING_STARTED`, `CONDITIONING_SKIPPED`, `CONDITIONING_COMPLETED`, `PACKAGING_READINESS_ASSESSED`, `PACKAGING_READINESS_HANDOFF_RECORDED`, `PACKAGING_READINESS_HANDOFF_INVALIDATED`, `YEAST_REFERENCE_RECORDED`, `YEAST_REFERENCE_CORRECTED`, `OG_CONSUMPTION_PINNED`, `OG_CONSUMPTION_RECONCILED`, `FERMENTATION_SESSION_CLOSED`.

Correction/late display is dual-time: process `occurred_at` and server `recorded_at`. Regeneration is read-only and must show original and current assessments/handoffs. Missing media: `MEDIA_UNAVAILABLE` placeholder; generation succeeds.

Identical regeneration inputs produce identical order. Concurrent same-timestamp inserts tie-break on `id`.

## 27. Notes and media

Reuse Phase 3 media architecture (`MEDIA_ROOT`, authorization, MIME validation, 10 MiB, 20 attachments / 100 MiB session quota analog on the fermentation session, backup/restore). Phase 4 attachments link to fermentation session and required stage instance when stage-scoped.

No new storage subsystem. Upload uses opaque server keys; user filenames are metadata only. Path traversal, MIME/signature mismatch, decoder failure: reject `415`/`422`. Authenticated owner retrieval only. Terminal upload: §25.

Failed upload cannot roll back measurements/timers. Orphan reconciliation within 24 hours as Phase 3.

## 28. Inventory integration

Phase 4 may reference yeast `IngredientLot`, display snapshotted metadata, and record quantity notes.

Phase 4 must not post automatic `CONSUMPTION`, convert reservations, or mutate stock. Manual consumption is deferred (`P4-DEC-003` / `P4-OQ-002`).

## 29. Equipment integration

At start, persist `fermentation_equipment_snapshot` JSON containing:

- `source_equipment_profile_id` if supplied or copied from RecipeVersion snapshot;
- copied calculation-relevant fields from the live profile **at start time** (capacity, losses, vessel name/type, identifiers present on the accepted equipment snapshot schema);
- `snapshotted_at` server time;
- `source_deleted` false at start.

If the live profile is later edited or deleted, historical sessions keep the JSON. FK to live profile may become null; snapshot remains. Source deletion does not rewrite history.

No equipment snapshot → lawful; fermenter identity `UNSPECIFIED`.

## 30. API contract (normative summary)

Base path: `/api/v1/fermentation-sessions`. Exact URL spelling may vary if semantics, auth, and IDs are complete; capabilities below are required. All mutations: CSRF, owner, `operation_id`, `phase4-operation-v1`. Nonterminal commands require `expected_revision` except start (uses brew session revision).

Common errors: `401`, `403` CSRF, `404` nondisclosure, `409` conflict/stale/terminal/idempotency, `410` archived idempotent result, `413`/`415` media, `422` validation.

Every mutation capability:

| Command | METHOD | RESOURCE | AUTH | REQUEST (semantic) | RESPONSE | IDEMPOTENCY scope | VALIDATION | CONFLICT | TERMINAL | ERROR |
|---|---|---|---|---|---|---|---|---|---|---|
| StartFermentationSession | POST | `/start` | owner brew | brew_session_id, operation_id, expected_brew_revision, optional yeast/equipment/reuse | session detail | user+Start+brew_session_id+op | §6 | 409 exists/stale/key | n/a | §6.4 |
| GetSession | GET | `/{id}` | owner | — | reconstruct timers/reminders/current leaves | n/a | — | — | allowed | 404 |
| ListSessions | GET | `/` | owner | — | owner list | n/a | — | — | allowed | — |
| Pause/Resume/Abort/Close | POST | `/{id}/commands/{name}` | owner | operation_id, expected_revision, reason when required | new state | user+cmd+session_id+op | §9 | 409 | close/abort terminal rules | 409 invalid |
| CompleteFermentation | POST | `/{id}/commands/complete-fermentation` | owner | operation_id, revision, optional override/waivers | assessment+state | session | §14 | 409 race | deny CLOSED | 422 ineligible |
| StartConditioning / SkipConditioning / CompleteConditioning | POST | commands | owner | as above | state | session | §9/§17 | 409 | deny CLOSED | 422 |
| AssessPackagingReadiness | POST | `/{id}/completion-assessments` | owner | operation_id, revision, optional override | assessment including unsuccessful | session | §14.4 | 409 | CLOSED requalify only | 422 |
| RecordPackagingReadinessHandoff | POST | `/{id}/packaging-readiness-handoff` | owner | assessment_id, operation_id, revision | handoff version | session | §7 | 409 | new version if invalidated | 422 |
| ReconcileUpstreamOriginalGravity | POST | `/{id}/og-consumption` | owner | phase3 leaf ids | new pin | session | §6.2.1 | 409 | deny CLOSED/ABORTED | 422 |
| RecordMeasurement | POST | `/{id}/measurements` | owner | type, raw, observed_at, method, stage_instance_id, late flag | measurement | user+RecordMeasurement+session+op | §12/§18 | 409 key | §24 | 422 domain |
| CorrectMeasurement | POST | `/{id}/measurements/{mid}/corrections` | owner | correction_of_id, fields, reason | correction | user+CorrectMeasurement+mid+op | §23 | 409 superseded | §24 | 422 |
| RecordAction | POST | `/{id}/actions` | owner | type enum, occurred_at | action | session | §21.1 | 409 | DENY after CLOSED/ABORTED | 422 |
| RecordPlannedAdditionExecution | POST | `/{id}/additions/{req_id}/execute` | owner | actual fields | event | requirement+op | §21.2 | 409 | §24 late ≤24h CLOSED | 422 |
| RecordUnplannedAddition | POST | `/{id}/additions/unplanned` | owner | actual fields | event | session+op | ACTIVE/CONDITIONING or CLOSED late §24 | 409 | CLOSED ≤24h; ABORTED deny | 422 |
| Yeast enrich/correct | POST | `/{id}/yeast-reference` | owner | pair/lot/fields | reference | session+op | §11 | 409 cycle | CLOSED: annotation only; source-pair DENY | 422 pair |
| CorrectAddition | POST | `/{id}/addition-events/{id}/corrections` | owner | phase3-adapted | correction | original event+op | §21.2 | 409 superseded | §24 | 422 |
| Timer commands | POST | `/{id}/timers...` | owner | inherited Phase 3 set | timer | timer+op | inherited | 409 | deny new after terminal | inherited |
| Reminder acknowledge/skip | POST | `/{id}/reminders/{id}/...` | owner | inherited; skip may require waiver | reminder | reminder+op | ACK ≠ SATISFIED | 409 | §25 | inherited |
| RecordWaiver | POST | `/{id}/waivers` | owner | requirement_id, reason | waiver | requirement+op | §24 catalog | 409 duplicate active | deny CLOSED/ABORTED | 409 WAIVER_PROHIBITED |
| Notes | POST | `/{id}/notes` | owner | text ≤4000 | note | session+op | length | 409 | §24 | 422 |
| Media upload/list/get/remove | POST/GET | media routes | owner | Phase 3 controls | metadata | upload op | MIME/size | 409 quota | no upload terminal | 413/415 |
| Export | GET | `/{id}/export?format=json\|html` | owner | — | original+current history | n/a | — | — | allowed | MEDIA_UNAVAILABLE |
| Pitch history | GET | `/pitch-history` | owner | filters session/lot | snapshots | n/a | — | — | allowed | 404 |

Every closed command schema **rejects unknown fields** with `422 UNKNOWN_FIELD` and creates no domain/operation-success rows. Unknown fields are never ignored. Owner, session, stage, status, and server timestamps cannot be client-set except documented semantic fields.

## 31. Idempotency

`phase4-operation-v1` binds `phase3-operation-v1` canonicalization, fingerprint, 90-day full-result retention after fermentation terminal (`CLOSED` or `ABORTED`), lifetime tombstone, rollback, and lost-response replay. Terminal mapping for retention: fermentation session `CLOSED`/`ABORTED`.

Canonicalization uses UTF-8, schema version, semantic defaults, sorted keys, ordered arrays unless sets, canonical UUID/UTC microsecond/Decimal, and SHA-256. Omitted vs null are equivalent only where the command schema says so. Canonicalization includes **only the client semantic command** plus those defaults. It does **not** include server-derived evidence fingerprints or computed eligibility. The server **looks up** `(scope, operation_id)` **before** rereading completion evidence. Same key + same client canonical payload always replays the stored result even if evidence changed after a lost response.

`expected_revision` is a request precondition. A retry after `409 STALE_REVISION` **must use a new operation_id**. Evidence fingerprints belong on the assessment/result provenance document only.

| MUTATION | KEY_REQUIRED | KEY_SCOPE | CANONICALIZATION | RETENTION | SAME_KEY_SAME_PAYLOAD | SAME_KEY_DIFFERENT_PAYLOAD | RETRY_AFTER_PARTIAL_FAILURE | TERMINAL_BEHAVIOR |
|---|---|---|---|---|---|---|---|---|
| Start | yes | brew_session_id | §6 optional yeast/equipment defaults | inherited | replay original session | 409 | rollback no partial start | replay even if later ABORTED |
| Measurement | yes | session_id | raw+canonical+time+stage+type | inherited | replay | 409 | inherited | §24 |
| Action | yes | session_id | type+occurred_at+note defaults | inherited | replay | 409 | inherited | §25 |
| Planned addition execute | yes | requirement_id | actual fields | inherited | replay | 409 | inherited | §24 |
| Unplanned addition | yes | session_id | actual fields | inherited | replay | 409 | inherited | deny after terminal |
| State pause/resume/abort/close/complete/skip/start-conditioning | yes | session_id | command name + reason defaults | inherited | replay | 409 | atomic children | abort/close terminal |
| Timer create/extend/replace/cancel/complete/ack | yes | timer or session | inherited | inherited | replay | 409 | inherited | deny new |
| Reminder ack/skip | yes | reminder_id | inherited | inherited | replay | 409 | inherited | §25 |
| Waiver | yes | requirement_id | reason | inherited | replay | 409 | inherited | deny new |
| Override (on complete commands) | yes | session + command | reason+override flag | inherited | replay | 409 | inherited | deny CLOSED |
| Correction | yes | original evidence id | correction_of_id+fields | inherited | replay | 409 | inherited | 30d window |
| Assessment | yes | session_id | client command name + override flag + reason defaults only | inherited | replay original assessment/HTTP even if evidence later changed | 409 | lookup before evidence reread; fail persists assessment+journal and **increments revision** | CLOSED requalify |
| Handoff | yes | session_id | assessment_id | inherited | replay | 409 | atomic current flag | new version rules |
| Yeast enrich | yes | session_id | pair+lot | inherited | replay | 409 | cycle-safe | annotation only |
| Deviation user | yes | session_id | class+text | inherited | replay | 409 | inherited | notes only |
| Notes/media | yes | session_id | inherited media | inherited | replay; no dup bytes | 409 | orphan isolation | §25 |
| Plan/mode revision | — | — | — | — | — | — | — | **command does not exist** |
| OG reconcile | yes | session_id | phase3 leaf ids | inherited | replay | 409 | inherited | deny CLOSED/ABORTED |

## 32. Concurrency

Authoritative boundary: one PostgreSQL transaction per command. Lock: `SELECT ... FOR UPDATE` on `FermentationSession` (or brew session row for start) **before** reading evidence used in completion. Evidence inserts for that session take the same session lock. Frontend control is not enforcement.

Revision: integer `revision` on `FermentationSession`. Every command that persists domain, assessment, journal, or operation-success rows **increments** revision, including `422 COMPLETION_INELIGIBLE` (failed assessment is a persisted mutation). `409 STALE_REVISION` and `409 INVALID_TRANSITION` that write no domain rows do **not** increment revision and do **not** store a successful operation result (safe conflict audit only). Stale `expected_revision` → `409 STALE_REVISION`. Start uses brew session revision.

When two nonterminal mutations share the **same initial** `expected_revision`, exactly one wins the session lock and commits. The loser **always** returns `409 STALE_REVISION` and writes no domain rows. The loser does not observe the winner’s new evidence in that request. Observing it requires a **new command** with a **new operation_id** and the fresh revision from GET.

| RACE_ID | OPERATION_A | OPERATION_B | AUTHORITATIVE_TRANSACTION_BOUNDARY | WINNER/CONFLICT_RULE | EXPECTED_RESPONSE | FINAL_PERSISTED_STATE | JOURNAL_EFFECT |
|---|---|---|---|---|---|---|---|
| R1 | two Start different keys | same brew | brew row lock | one session; loser 409 EXISTS | 201 vs 409 | one non-aborted session | one start event |
| R2 | Start same key | retry | operation table lookup first | replay | 200 replay | original | no second event |
| R3 | CompleteFermentation | RecordMeasurement gravity | session lock + OCC | same initial revision: one winner; loser 409 STALE | 2xx/422 vs 409 | only winner’s rows; revision +1 once | only winner |
| R4 | CompleteFermentation | CorrectMeasurement | session lock + OCC | same as R3 | same | no READY from the stale request | only winner |
| R5 | CompleteFermentation | RecordWaiver | session lock + OCC | same as R3 | same | at most one of the two requests commits | only winner |
| R6 | two CompleteFermentation | concurrent | session lock + OCC | one winner; loser 409 STALE or already-complete INVALID_TRANSITION | one FERMENTATION_COMPLETE | one success assessment | one success assess event |
| R7 | two corrections same leaf | concurrent | leaf unique successor + session lock | one winner; loser 409 SUPERSEDED or STALE | one successor | unique leaf | one correction event |
| R8 | Waiver vs satisfaction evidence | concurrent | session lock + OCC | same initial revision: one winner; loser 409 STALE. After retry, Phase 3 supersession applies | 409 loser | one committed mutation from the pair | only winner |
| R9 | two handoff records | concurrent | unique current=true + OCC | one current; loser 409 STALE or conflict | one 2xx | one new current handoff | one version from winner |
| R10 | Pause vs Complete | concurrent | session lock + OCC | one winner; loser 409 STALE | 409 loser | one state | one transition |
| R11 | Resume stale tab | concurrent resume | revision | one resume; loser 409 STALE | 409 STALE | origin restored once | one resume |
| R12 | Yeast A→B vs B→A | concurrent | ordered row locks | one cycle loser 409 | 409 | acyclic | one enrich |
| R13 | Complete vs new measurement after read without lock | forbidden implementation | must lock session first **and** match expected_revision | specification forbids lock-free read | tests with PostgreSQL interleaving | no stale READY | — |

Atomic write vector for successful CompleteFermentation: session state, stage status, assessment row, timer/reminder child effects, journal events, audit, operation result, revision increment. Failed eligibility: assessment row + operation result + journal assess event + revision increment + **no** session-state change, same transaction.

## 33. Security and authorization

Preserve Phase 3 CSRF synchronizer token + Origin/Referer (`403`, no operation reservation).

Server-side ownership for every fermentation resource including nested yeast source IDs, lot IDs, equipment IDs, assessment IDs, and OG source measurement IDs. Cross-owner always `404`, never `403` disclosure.

IDOR matrix (executable): session, stage, measurement, correction, action, addition, timer, reminder, waiver, assessment, handoff, yeast reference, source session, lot, equipment profile, note, media bytes, journal, export, OG pin.

Mass assignment: closed command schemas; unknown fields `422 UNKNOWN_FIELD`; owner, session, stage, revision, timestamps, status cannot be client-set except documented semantic fields.

Media: Phase 3 path-safe keys, MIME/signature/decode, 10 MiB, quota, nosniff, no path disclosure.

Logs: correlation IDs; no request bodies, secrets, or unrestricted note/measurement contents. New correction/provenance errors use stable codes without leaking other owners’ IDs.

Idempotency abuse: mismatched fingerprint `409` without executing. Keys not shared across owners.

XSS: notes and human-readable export are encoded; no raw HTML from user fields. JSON export is data.

SQL: parameterized queries; hostile IDs rejected as `404`/`422`, never 500 with driver text.

## 34. Privacy

Phase 4 introduces no new personal data classes beyond existing user identity and brewer notes/photos. No new profiling.

## 35. Backup and restore

Acceptance requires **isolated** restore of a representative fixture (one nonterminal ACTIVE and one CLOSED session) proving preservation of:

- session state machine, revisions, pause origin;
- plan snapshot hash and bytes;
- OG pins and yeast references (including source pair);
- measurements and full correction chains;
- timers (IDs, due_at, states);
- reminders (IDs, satisfaction sources);
- actions/additions/correction chains;
- deviations current and historical;
- waivers;
- assessments and **all** handoff versions plus current flag;
- operation results and tombstones (replay after restore must not re-execute);
- journal events;
- media metadata **and** bytes (SHA-256 match);
- equipment snapshot JSON.

Metadata-only restore is insufficient when media exists. Compare pre/post vectors; derived projections may regenerate but operational IDs must match.

## 36. Recovery

Proof is from persisted PostgreSQL state, not browser memory.

Required nontrivial fixture F-REC-1 (ACTIVE): session with pause_origin unset, 5 gravity leaves spanning 48h, 2 running WALL_CLOCK timers, 1 PAUSED ACTIVE_TIME timer, 3 reminders (one ACKNOWLEDGED unsatisfied, one DUE, one COMPLETED), 1 planned addition executed, 1 waiver, 1 temperature excursion deviation, yeast reference, 2 media attachments, in-flight operation tombstone none.

Faults:

- browser refresh: GET returns same IDs/deadlines/effective leaves;
- API process restart: same;
- Redis stopped: GET identical authority; timer remaining time may change with wall clock as designed; compare IDs and due_at, not literal remaining-ms bytes;
- container restart: same as API restart;
- deadline during outage: after restart, expired timer has exactly one expiry event;
- partial failure: rolled-back command leaves zero rows; retried operation either replays or executes once.

F-REC-2 (CLOSED): completed path with invalidated then replaced handoff version 2 current; restore preserves both versions.

## 37. Performance

### Reference class

Same as Phase 3 private-runtime class: production-build disposable PostgreSQL + API + web on SSD, ≥4 logical x86-64 cores, ≥8 GiB RAM, LAN RTT ≤ 10 ms. Record exact hardware/OS/container/browser. Not NAS production.

### Dataset

Isolated harness only. **Must not** seed or mutate authoritative user records.

Construction: generate disposable owner + completed brew + pitch handoff + fermentation session with 200 measurements (valid spacing mix), 50 reminders, 20 timers, 100 journal events, 10 attachment metadata rows (bytes present, not eagerly loaded on GET detail), plan snapshot, yeast reference. Explain construction in the evidence log (seed script identity, not production data).

Warmup: 10 iterations excluded from samples.

Sample size: ≥100 successful samples per named API operation; ≥30 browser navigation/recovery samples.

Statistic: p95 of successful samples. Errors: zero unexpected 5xx; expected 4xx not mixed into success p95.

Clock: server duration from API middleware; browser from navigation start to authoritative controls. Production build.

| OPERATION | THRESHOLD | PASS_FAIL |
|---|---|---|
| GET session detail (authoritative projection) | p95 ≤ 500 ms | fail if p95 > 500 ms or wrong IDs |
| POST measurement (authoritative) | p95 ≤ 750 ms | fail if exceeded or duplicate rows |
| POST complete-fermentation (eligible fixture) | p95 ≤ 1250 ms | fail if exceeded |
| JSON export regeneration | p95 ≤ 2000 ms | fail if exceeded |
| Browser worksheet usable state | p95 ≤ 2500 ms | fail if exceeded |
| Refresh recovery to reconciled state | p95 ≤ 2000 ms | fail if exceeded |

PASS_FAIL_RULE: all rows pass on the recorded class with raw samples retained. Missing methodology is failure.

## 38. Accessibility

Keyboard operability for record measurement, acknowledge reminder, record action, review state/history, add note/media, complete/waive.

Semantic timers/reminders/status (`role="timer"` where applicable, labels, errors associated).

If charts exist, tabular equivalent is required.

PASS remains the specification baseline; runtime a11y is implementation evidence.

## 39. Responsive UX

Minimum usable workflows at 360 px width for measurement entry, reminder acknowledgement, current state review, and note capture.

## 40. Trends and visualization

Charts are derived views. Missing data renders as missing, not zero. Current series uses effective leaves; originals remain in history.

## 41. AI boundary

AI may summarize/explain; it may not authoritatively create measurements, state transitions, completion, inventory mutations, corrections, or waivers.

## 42. Safety boundary

BICOS is not a substitute for physical pressure, temperature, or vessel safety systems. It does not actuate hardware.

Software-system safety (testable):

| Class | BICOS validates (reject `422`) | BICOS warns (persist + deviation) | BICOS rejects | External responsibility |
|---|---|---|---|---|
| Time | future >5 min; naive/DST-ambiguous; before pitch−5 min | n/a | those timestamps | brewer process timing |
| Gravity domain | outside 0.900–1.300 SG; raw Plato outside `PLATO_MIN`/`PLATO_MAX` or nonconvergent inverse | FG > OG or FG < 1.000 while in SG bounds: allow store, `CALCULATION_UNDEFINED` / eligibility fail | `422 PLATO_OUT_OF_DOMAIN` / `PLATO_CONVERSION_FAILED`; SG hard bounds | hydrometer use |
| Temperature | outside type bounds | excursion vs plan | hard bounds | fermentation control hardware |
| pH | outside 2.5–8.0 | n/a | hard bounds | process sanitation |
| Pressure | n/a deferred | n/a | pressure execution APIs | physical PRV |
| Biology | n/a | n/a | certainty claims | lab/process |

Impossible timestamps and out-of-range values fail closed. Dangerous mis-entry inside bounds may warn but is not biological advice.

## 43. Failure modes

Covered by §47 adversarial scenarios, including missing/null OG, null pitch temperature, upstream OG correction, CLOSED/ABORTED restart, pause origin, skip conditioning, stable-gravity vectors, DST/future/window boundaries, terminal matrix, yeast pair/cycle, addition epoch, evidence-vs-completion races, mixed journal ties, restore, performance isolation.

## 44. Functional requirements

Each `P4-FR` is mandatory, atomic, implementation-independent, and testable.

### Session and handoff

- **P4-FR-001:** Start a fermentation session only from an owned `COMPLETED` brew session with exactly one Phase 3 pitch handoff, via `StartFermentationSession`.
- **P4-FR-002:** Immutable-reference `pitched_at`, yeast-addition note, and nullable `pitch_temperature_c` without synthesizing temperature.
- **P4-FR-003:** Pin OG consumption from the current pre-pitch `ORIGINAL_GRAVITY` leaf at start; never treat `FERMENTATION_GRAVITY` as OG.
- **P4-FR-004:** When OG is absent, store `og_availability=UNKNOWN` and still allow start.
- **P4-FR-005:** Provide `ReconcileUpstreamOriginalGravity` to pin a later Phase 3 OG leaf without rewriting Phase 3 or the original pin.
- **P4-FR-006:** Reject start when the pitch handoff is missing on an owned completed brew with `422 PITCH_HANDOFF_MISSING` and zero fermentation rows.
- **P4-FR-007:** Return `404` nondisclosure when the brew session is missing or not owned.
- **P4-FR-008:** Enforce at most one non-aborted fermentation session per brew session, including after `CLOSED`.
- **P4-FR-009:** Allow a new start after `ABORTED` that reuses the same accepted pitch handoff and new identities.
- **P4-FR-010:** Allow multiple concurrent fermentation sessions for one user only when they reference different brew sessions.
- **P4-FR-011:** Materialize `phase4-plan-v1` atomically in the start transaction with stored SHA-256, recognized `schedule`/`conditioning_schedule` keys, ingredient total order, template IDs distinct from session-owned requirement row IDs.
- **P4-FR-012:** Never mutate `RecipeVersion`, `BrewSession`, Phase 3 measurements, pitch handoff, timers, or inventory during Phase 4 operations.
- **P4-FR-013:** Record packaging readiness facts without creating packaging sessions or ledger consumption.
- **P4-FR-014:** Scope start idempotency to `brew_session_id` before a fermentation session ID exists.

### Lifecycle

- **P4-FR-015:** Implement §9.4 as the sole session command transition contract; §9.5 is an index of those rows only.
- **P4-FR-016:** Reject invalid transitions with `409 INVALID_TRANSITION` and no partial writes.
- **P4-FR-017:** Persist `pause_origin_state` and resume only to that origin.
- **P4-FR-018:** Apply Phase 3-equivalent timer/reminder child effects on pause, resume, abort, skip, complete, invalidation, and §9.8 reactivation (new timer identities; reminders not silently satisfied).
- **P4-FR-019:** Separate fermentation completion from conditioning start.
- **P4-FR-020:** Keep conditioning completion distinct from fermentation completion.
- **P4-FR-021:** Abort with reason 10–1000 characters, preserved history, and §9.6 child effects.
- **P4-FR-022:** Close only when a current `READY` or `READY_WITH_WAIVERS` handoff exists and is not `INVALIDATED`.
- **P4-FR-023:** On `SkipConditioning`, move `FERMENTATION_COMPLETE` → `CONDITIONING_COMPLETE` with `conditioning_skipped=true` and null conditioning timestamps, creating no CONDITIONING instance.
- **P4-FR-024:** Deny a second `ACTIVE_FERMENTATION` or `CONDITIONING` row (`409 STAGE_REPEAT_PROHIBITED`); invalidation reuses the existing row per §9.8.

### Measurements and time

- **P4-FR-025:** Enforce `FERMENTATION_GRAVITY` schema, bounds, method/context, and required stage in §12.1.
- **P4-FR-026:** Enforce `FERMENTATION_TEMPERATURE` schema and `-5..40` degC inclusive.
- **P4-FR-027:** Enforce `FERMENTATION_PH` schema and `2.5..8.0` inclusive.
- **P4-FR-028:** Enforce `CONDITIONING_TEMPERATURE` with required CONDITIONING `stage_instance_id` and `-5..30` degC.
- **P4-FR-029:** Persist `observed_at` and server `recorded_at` separately in UTC per §18.
- **P4-FR-030:** Reject naive, missing-offset, and >5-minute-future timestamps with `422`.
- **P4-FR-031:** Append measurement corrections without overwrite, unique current leaf, immutable type.
- **P4-FR-032:** Reject cross-session measurement linkage.

### Calculations

- **P4-FR-033:** Compute apparent attenuation via the accepted function as a ratio; expose percent only as display.
- **P4-FR-034:** Compute fermentation progress with the zero-denominator and clipping rules in §13.
- **P4-FR-035:** Evaluate stable gravity exclusively with `phase4-stable-gravity-v1`.
- **P4-FR-036:** Compute ABV with accepted `(OG-FG)×131.25` when defined.
- **P4-FR-037:** Label pitch-rate outputs `CALCULATED` and omit them when volume/OG/rate inputs are missing.
- **P4-FR-038:** Convert Plato to SG only through `phase4-plato-to-sg-v1`, rejecting out-of-image inputs (`PLATO_OUT_OF_DOMAIN`) and nonconvergence (`PLATO_CONVERSION_FAILED`) without persisting a row.

### Completion and conditioning

- **P4-FR-039:** Do not mark fermentation complete from elapsed time alone.
- **P4-FR-040:** Evaluate fermentation eligibility with §14.2 and persist unsuccessful assessments without state change.
- **P4-FR-041:** Move to `FERMENTATION_COMPLETE` only on successful `CompleteFermentation`.
- **P4-FR-042:** Apply override limits in §14.5.
- **P4-FR-043:** Invalidate and destinate state per §14.6 with no implicit reopen after `CLOSED` and with stage-row reuse rather than a second occurrence.
- **P4-FR-044:** Version packaging handoffs with exactly one current row and preserve invalidated rows.
- **P4-FR-045:** Evaluate conditioning with §14.3.
- **P4-FR-046:** Freeze conditioning mode in the start snapshot; deny mode selection at completion.
- **P4-FR-047:** Allow skip of conditioning only when the snapshot declares `conditioning_required=false`.

### Timers and reminders

- **P4-FR-048:** Persist timers in PostgreSQL with Phase 3-equivalent lifecycle.
- **P4-FR-049:** Recover timers/reminders after refresh, API restart, Redis loss, and container restart from PostgreSQL.
- **P4-FR-050:** Treat reminder acknowledgement as distinct from requirement satisfaction.
- **P4-FR-051:** Emit at most one expiry event when a deadline passes during outage.

### Additions and actions

- **P4-FR-052:** Materialize `FERMENTATION`/`DRY_HOP` additions with §21.2 timing (`FROM_PITCH`, minutes from `pitched_at`).
- **P4-FR-053:** Allow exactly one planned occurrence per source and deny runtime repeat of those requirements.
- **P4-FR-054:** Allow unplanned additions only while `ACTIVE` or `CONDITIONING`.
- **P4-FR-055:** Record addition corrections with Phase 3 leaf semantics adapted to the fermentation session.
- **P4-FR-056:** Record actions using the closed §21.1 enum.
- **P4-FR-057:** Keep addition execution at zero inventory-ledger effect.

### Deviations, waivers, late entry

- **P4-FR-058:** Record derived deviations with §22 identity and supersession.
- **P4-FR-059:** Support waivers with reason/actor/timestamp/effect for the §10.3 waivable catalog only, including readiness-only `ORIGINAL_GRAVITY_KNOWN`.
- **P4-FR-060:** Reject non-waivable waiver requests with `409 WAIVER_PROHIBITED`.
- **P4-FR-061:** Enforce late-entry windows in §24.

### Journal, media, export

- **P4-FR-062:** Merge Phase 4 journal events with Phase 3 using `(occurred_at, recorded_at, id)` without reordering predecessor events.
- **P4-FR-063:** Emit the closed event vocabulary in §26.
- **P4-FR-064:** Support notes/media under Phase 3 media security architecture.
- **P4-FR-065:** Export JSON and human-readable summaries including original and current assessments/handoffs.

### Yeast and inventory

- **P4-FR-066:** Allow optional same-owner yeast lot linkage with an immutable metadata snapshot.
- **P4-FR-067:** Enforce yeast source-pair agreement, ownership, temporal, and aborted-source rules.
- **P4-FR-068:** Provide pitch history by session, lot, and user from snapshots.
- **P4-FR-069:** Reject circular lineage under transactional locking.
- **P4-FR-070:** Must not post automatic inventory consumption.

### API, idempotency, concurrency, security

- **P4-FR-071:** Require `operation_id` on all Phase 4 mutation commands.
- **P4-FR-072:** Implement `phase4-operation-v1` including tombstones, rollback, client-only canonical fingerprints, and lookup-before-evidence-reread.
- **P4-FR-073:** Enforce optimistic revision conflicts as `409 STALE_REVISION`.
- **P4-FR-074:** Serialize completion against evidence mutations under the session lock and OCC rule in §32 (same initial revision: one winner; loser `409 STALE_REVISION`).
- **P4-FR-075:** Enforce owner-only access (`404` cross-owner) including nested source IDs.
- **P4-FR-076:** Preserve CSRF protections on every new mutating route.
- **P4-FR-077:** Validate units/domains server-side with closed command schemas; unknown fields return `422 UNKNOWN_FIELD`.

### Recovery, backup, performance, accessibility, safety

- **P4-FR-078:** Survive API restart without losing authoritative fermentation state.
- **P4-FR-079:** Treat Redis as non-authoritative.
- **P4-FR-080:** Survive isolated backup/restore of fixture vectors in §35 including media bytes and operation keys.
- **P4-FR-081:** Provide the isolated performance harness in §37 without mutating authoritative user sessions.
- **P4-FR-082:** Support keyboard and 360 px workflows in §38–39.
- **P4-FR-083:** Fail closed on impossible timestamps and hard measurement bounds per §42.

### Regression and scope

- **P4-FR-084:** Preserve accepted Phase 3 brew-day behavior and evidence unchanged.
- **P4-FR-085:** Preserve accepted Phase 2 core/calculation/inventory and Phase 1A browser regression surfaces.
- **P4-FR-086:** Enforce the Phase 5+ leakage matrix in §51.
- **P4-FR-087:** Apply additive migrations from accepted Phase 3 head to verified Phase 4 head, preserving legacy data, constraints, and predecessor round-trip policy.
- **P4-FR-088:** Reactivate an invalidated stage by reusing `stage_instance_id`, incrementing `activation_ordinal`, setting `current_activation_started_at`, and creating new timer identities per §9.8.
- **P4-FR-089:** After `CLOSED`, evaluate packaging readiness from current evidence without `CompleteFermentation`/`CompleteConditioning` and without leaving `CLOSED`.

## 45. Acceptance criteria

Format: PRECONDITION / ACTION / EXPECTED / EVIDENCE / RELATED_FR.

- **P4-AC-001:** PRECONDITION: git diff from `v0.3.0-phase3`. ACTION: inventory paths. EXPECTED: only Phase 4 spec/implementation/tests/migrations/docs; no silent accepted-contract edits. EVIDENCE: diff list. RELATED_FR: 012,084. DOMAIN of proof: scoped review + git.
- **P4-AC-002:** PRECONDITION: candidate tree. ACTION: architecture inspection plus executable assertions that AI cannot mutate and packaging tables/routes are absent. EXPECTED: no prohibited AI authority or Phase 5 operations. EVIDENCE: route/table scan + negative API tests. RELATED_FR: 013,086.
- **P4-AC-003:** PRECONDITION: implementation. ACTION: map every new table/route/page to a P4-FR or handoff fact. EXPECTED: zero unmapped operational surfaces. EVIDENCE: mapping file in implementation report plus scan. RELATED_FR: 086.
- **P4-AC-004:** PRECONDITION: owned completed brew with handoff and OG leaf. ACTION: start. EXPECTED: one session, plan hash, OG pin IDs, null pitch temp accepted if null. EVIDENCE: PostgreSQL rows. RELATED_FR: 001–004,011,014.
- **P4-AC-005:** PRECONDITION: owned completed brew, no handoff. ACTION: start. EXPECTED: `422 PITCH_HANDOFF_MISSING`, zero fermentation/operation-success rows. EVIDENCE: API+DB. RELATED_FR: 006.
- **P4-AC-006:** PRECONDITION: foreign brew ID. ACTION: start or GET. EXPECTED: `404`. EVIDENCE: API. RELATED_FR: 007,075.
- **P4-AC-007:** PRECONDITION: existing CLOSED session. ACTION: second start different key. EXPECTED: `409 FERMENTATION_SESSION_EXISTS`. EVIDENCE: API+DB. RELATED_FR: 008.
- **P4-AC-008:** PRECONDITION: ABORTED session. ACTION: new start different key. EXPECTED: new ACTIVE session, same pitch handoff ID. EVIDENCE: DB. RELATED_FR: 009.
- **P4-AC-009:** PRECONDITION: two completed brews. ACTION: two starts. EXPECTED: two ACTIVE sessions. EVIDENCE: DB. RELATED_FR: 010.
- **P4-AC-010:** PRECONDITION: Phase 3 OG corrected after pin. ACTION: read session; then reconcile. EXPECTED: original pin unchanged until reconcile; new pin current; Phase 3 row unchanged. EVIDENCE: IDs. RELATED_FR: 003,005,012.
- **P4-AC-011:** PRECONDITION: ready path. ACTION: record handoff and scan packaging tables. EXPECTED: readiness row only; zero packaging/ledger consumption. EVIDENCE: DB counts. RELATED_FR: 013,086.
- **P4-AC-012:** PRECONDITION: each invalid edge in §9.4. ACTION: command. EXPECTED: 409, no writes. EVIDENCE: matrix test. RELATED_FR: 015,016.
- **P4-AC-013:** PRECONDITION: CONDITIONING then pause. ACTION: resume. EXPECTED: CONDITIONING, not ACTIVE. EVIDENCE: state+pause_origin. RELATED_FR: 017,018.
- **P4-AC-014:** PRECONDITION: `conditioning_required=false` and FERMENTATION_COMPLETE. ACTION: skip. EXPECTED: CONDITIONING_COMPLETE, skipped flag, null timestamps, no CONDITIONING instance. EVIDENCE: DB. RELATED_FR: 023,047.
- **P4-AC-015:** PRECONDITION: `conditioning_required=true`. ACTION: skip. EXPECTED: 409. EVIDENCE: API. RELATED_FR: 047.
- **P4-AC-016:** PRECONDITION: abort from ACTIVE with running timers. ACTION: abort. EXPECTED: §9.6 effects, history retained. EVIDENCE: timer/reminder states. RELATED_FR: 021,018.
- **P4-AC-017:** PRECONDITION: NOT_READY current handoff. ACTION: close. EXPECTED: 409 HANDOFF_NOT_READY. EVIDENCE: API. RELATED_FR: 022.
- **P4-AC-018:** PRECONDITION: §15 golden vectors. ACTION: evaluator. EXPECTED: exact table outcomes. EVIDENCE: domain unit goldens. RELATED_FR: 035.
- **P4-AC-019:** PRECONDITION: Plato near spread boundary. ACTION: convert+evaluate. EXPECTED: adapter + STABLE/NOT_STABLE per Decimal spread. EVIDENCE: goldens. RELATED_FR: 038,035.
- **P4-AC-020:** PRECONDITION: measurement fixtures. ACTION: submit bounds/method/stage/time cases. EXPECTED: §12 accept/reject. EVIDENCE: API+DB. RELATED_FR: 025–032,083.
- **P4-AC-021:** PRECONDITION: OG/FG pairs including undefined. ACTION: attenuation/progress/ABV. EXPECTED: ratio, clips, CALCULATION_UNDEFINED. EVIDENCE: goldens. RELATED_FR: 033,034,036,037.
- **P4-AC-022:** PRECONDITION: F1–F4 fail. ACTION: CompleteFermentation. EXPECTED: 422, persisted INSUFFICIENT assessment, state ACTIVE. EVIDENCE: DB. RELATED_FR: 040,041.
- **P4-AC-023:** PRECONDITION: eligible ACTIVE. ACTION: complete. EXPECTED: FERMENTATION_COMPLETE, confirmed assessment. EVIDENCE: DB. RELATED_FR: 041,019.
- **P4-AC-024:** PRECONDITION: confirmed then gravity correction. ACTION: correct. EXPECTED: §14.6 destination; original assessment preserved INVALIDATED. EVIDENCE: state vector. RELATED_FR: 043.
- **P4-AC-025:** PRECONDITION: CLOSED with READY handoff. ACTION: completion-affecting correction. EXPECTED: session stays CLOSED; handoff INVALIDATED; no ACTIVE. EVIDENCE: DB. RELATED_FR: 043,044.
- **P4-AC-026:** PRECONDITION: CLOSED with current READY handoff; FG correction within 24h invalidates current handoff; original Complete* rows INVALIDATED. ACTION: AssessPackagingReadiness then RecordPackagingReadinessHandoff. EXPECTED: session remains CLOSED; no CompleteFermentation/CompleteConditioning; R1/R2 from current evidence; handoff version 2 current; version 1 preserved `current=false`; zero packaging-operation rows. EVIDENCE: DB. RELATED_FR: 044,013,089.
- **P4-AC-027:** PRECONDITION: sparse recipe. ACTION: start then complete fermentation. EXPECTED: deterministic plan; unspecified targets; skip-only conditioning. EVIDENCE: snapshot JSON+hash. RELATED_FR: 011,046,047.
- **P4-AC-028:** PRECONDITION: duplicate FERMENTATION_FOUNDATION. ACTION: start. EXPECTED: 422, no session. EVIDENCE: API. RELATED_FR: 011.
- **P4-AC-029:** PRECONDITION: timers on F-REC-1. ACTION: refresh, API restart, Redis stop, deadline outage. EXPECTED: §36. EVIDENCE: IDs/due_at/expiry count. RELATED_FR: 048–051,078,079.
- **P4-AC-030:** PRECONDITION: required gravity reminder. ACTION: acknowledge. EXPECTED: still unsatisfied. EVIDENCE: reminder+requirement. RELATED_FR: 050.
- **P4-AC-031:** PRECONDITION: DRY_HOP timing_minutes=2880. ACTION: start. EXPECTED: due_at = pitched_at+48h, stage ACTIVE_FERMENTATION. EVIDENCE: requirement row. RELATED_FR: 052.
- **P4-AC-032:** PRECONDITION: planned addition. ACTION: runtime repeat command. EXPECTED: 409. EVIDENCE: API. RELATED_FR: 053.
- **P4-AC-033:** PRECONDITION: addition execute/retry. ACTION: ledger query. EXPECTED: zero consumption/reservation conversion. EVIDENCE: ledger counts. RELATED_FR: 057,070.
- **P4-AC-034:** PRECONDITION: mismatched yeast source pair / aborted source / cycle race. ACTION: enrich. EXPECTED: 422/409 per §11. EVIDENCE: API+locks test. RELATED_FR: 066,067,069.
- **P4-AC-035:** PRECONDITION: live lot metadata change after start. ACTION: GET history. EXPECTED: snapshot unchanged. EVIDENCE: JSON. RELATED_FR: 066,068.
- **P4-AC-036:** PRECONDITION: each §32 race. ACTION: PostgreSQL interleaving. EXPECTED: stated winner/state/journal. EVIDENCE: concurrent tests. RELATED_FR: 073,074.
- **P4-AC-037:** PRECONDITION: every mutation family. ACTION: missing operation_id; same key different payload; tombstone after retention simulation. EXPECTED: reject/409/410 per §31. EVIDENCE: API. RELATED_FR: 071,072.
- **P4-AC-038:** PRECONDITION: two owners. ACTION: nested IDOR matrix §33. EXPECTED: 404 no mutation. EVIDENCE: security tests. RELATED_FR: 075.
- **P4-AC-039:** PRECONDITION: browser mutation. ACTION: missing CSRF / bad Origin. EXPECTED: 403, no rows. EVIDENCE: API. RELATED_FR: 076.
- **P4-AC-040:** PRECONDITION: F-REC-1/2 backup. ACTION: isolated restore. EXPECTED: §35 equality including bytes and tombstones. EVIDENCE: hashes/IDs. RELATED_FR: 080.
- **P4-AC-041:** PRECONDITION: harness dataset. ACTION: §37 operations. EXPECTED: thresholds; zero authoritative user mutation. EVIDENCE: raw samples+manifest. RELATED_FR: 081.
- **P4-AC-042:** PRECONDITION: accepted Phase 3 suites. ACTION: run canonical E2E + PostgreSQL suite. EXPECTED: green vs immutable baseline identities, not a raw 144 claim alone. EVIDENCE: named tests. RELATED_FR: 084.
- **P4-AC-043:** PRECONDITION: Phase 2/1A suites. ACTION: run core/calculation/inventory and phase1a.spec.ts / phase2.spec.ts. EXPECTED: green. EVIDENCE: named tests. RELATED_FR: 085.
- **P4-AC-044:** PRECONDITION: fresh DB and upgraded Phase 3 DB. ACTION: migrate to Phase 4 head and round-trip per repository policy. EXPECTED: additive; predecessor rows/constraints/IDs preserved. EVIDENCE: migration tests. RELATED_FR: 087.
- **P4-AC-045:** PRECONDITION: worksheet. ACTION: keyboard and 360px measurement/reminder/state/note flows. EXPECTED: operable; errors associated. EVIDENCE: Playwright + a11y inspection listed. RELATED_FR: 082.
- **P4-AC-046:** PRECONDITION: mixed Phase 3 journal + backdated Phase 4 correction same occurred_at. ACTION: export twice. EXPECTED: stable `(occurred_at, recorded_at, id)` order; Phase 3 relative order preserved. EVIDENCE: export hash. RELATED_FR: 062,065.
- **P4-AC-047:** PRECONDITION: CLOSED. ACTION: each DENY cell in §25. EXPECTED: 409, no mutation. EVIDENCE: matrix. RELATED_FR: 043 plus terminal FRs 061,064.
- **P4-AC-048:** PRECONDITION: ABORTED. ACTION: new measurement. EXPECTED: 409 TERMINAL_SESSION_EVIDENCE_PROHIBITED. EVIDENCE: API. RELATED_FR: 061.
- **P4-AC-049:** PRECONDITION: equipment profile edit after start. ACTION: GET session. EXPECTED: snapshot JSON unchanged. EVIDENCE: JSON. RELATED_FR: 011.
- **P4-AC-050:** PRECONDITION: canonical happy path. ACTION: Playwright ACTIVE→complete fermentation→conditioning→assess→handoff. EXPECTED: states and IDs per §9/§14. EVIDENCE: E2E. RELATED_FR: 015,019,020,041.
- **P4-AC-051:** PRECONDITION: waiver vs later gravity. ACTION: race and supersession. EXPECTED: ACK≠SATISFIED; evidence supersedes waiver; one satisfaction source. EVIDENCE: PG. RELATED_FR: 050,059.
- **P4-AC-052:** PRECONDITION: malformed media. ACTION: upload. EXPECTED: Phase 3 MIME/decoder rejection, no authoritative row. EVIDENCE: security test. RELATED_FR: 064.
- **P4-AC-053:** PRECONDITION: duration elapsed, temperature missed, conditioning required both. ACTION: CompleteConditioning. EXPECTED: 422 + failed assessment. EVIDENCE: DB. RELATED_FR: 045,040.
- **P4-AC-054:** PRECONDITION: any nonterminal fermentation session. ACTION: waive `pitched_at`, yeast-addition note, ownership, or idempotency. EXPECTED: `409 WAIVER_PROHIBITED`, no waiver row. EVIDENCE: API+DB. RELATED_FR: 060.
- **P4-AC-055:** PRECONDITION: planned fermentation duration elapsed, fewer than three valid gravities. ACTION: CompleteFermentation. EXPECTED: `422 COMPLETION_INELIGIBLE`, state remains `ACTIVE`. EVIDENCE: DB. RELATED_FR: 039.
- **P4-AC-056:** PRECONDITION: ACTIVE session. ACTION: RecordAction with a type not in §21.1. EXPECTED: `422`, no action row. EVIDENCE: API. RELATED_FR: 056.
- **P4-AC-057:** PRECONDITION: PAUSED from CONDITIONING; separately CONDITIONING_COMPLETE. ACTION: Abort. EXPECTED: `ABORTED` and §9.6 children; zero remaining nonterminal timers. EVIDENCE: state vector. RELATED_FR: 015,021.
- **P4-AC-058:** PRECONDITION: HANDOFF_READY then completion-affecting gravity making F1 fail. ACTION: AssessPackagingReadiness. EXPECTED: session `COMPLETION_ASSESSED`; current handoff `INVALIDATED`. EVIDENCE: DB. RELATED_FR: 015,044.
- **P4-AC-059:** PRECONDITION: R1 and R2 true, OG UNKNOWN. ACTION: (a) assess without waiver; (b) waive `ORIGINAL_GRAVITY_KNOWN` then record handoff; (c) override while R1 false. EXPECTED: (a) not READY; (b) `READY_WITH_WAIVERS`; (c) `409 OVERRIDE_PROHIBITED`. EVIDENCE: API+DB. RELATED_FR: 059,042,089.
- **P4-AC-060:** PRECONDITION: CONDITIONING started then fermentation-affecting correction. ACTION: CompleteFermentation again then StartConditioning. EXPECTED: same `stage_instance_id`; `activation_ordinal=2`; no second CONDITIONING PK. EVIDENCE: DB. RELATED_FR: 024,088.
- **P4-AC-061:** PRECONDITION: CLOSED READY then FG correction within 24h. ACTION: AssessPackagingReadiness then RecordPackagingReadinessHandoff. EXPECTED: session stays CLOSED; new current handoff version; no CompleteFermentation. EVIDENCE: IDs/status. RELATED_FR: 089,044,026-related 043.
- **P4-AC-062:** PRECONDITION: FERMENTATION_GRAVITY raw Plato 100; just-outside PLATO_MAX; just-inside PLATO_MAX. ACTION: submit. EXPECTED: first two `422 PLATO_OUT_OF_DOMAIN` zero rows; inside converts with residual < 1e-7. EVIDENCE: goldens. RELATED_FR: 038.
- **P4-AC-063:** PRECONDITION: conditioning completed 10 days ago; session still nonterminal; correction invalidates; session CONDITIONING. ACTION: Record CONDITIONING_TEMPERATURE now. EXPECTED: accepted; `late_entry=false`; not rejected by historical `completed_at`. EVIDENCE: API+timestamps. RELATED_FR: 029,088.
- **P4-AC-064:** PRECONDITION: abort then restart same brew/recipe with `details.schedule`. ACTION: compare plan hashes and requirement IDs. EXPECTED: same template IDs and logical hash; distinct row IDs; schedule applied. EVIDENCE: snapshot JSON. RELATED_FR: 011.
- **P4-AC-065:** PRECONDITION: two clients, `expected_revision=10`. ACTION: CompleteFermentation and RecordMeasurement concurrently. EXPECTED: one commit; loser `409 STALE_REVISION`; loser writes zero domain rows. EVIDENCE: PG interleaving. RELATED_FR: 073,074.
- **P4-AC-066:** PRECONDITION: CompleteFermentation commits; HTTP lost; new gravity commits; client retries same operation_id and body. EXPECTED: replay original assessment/HTTP, not `IDEMPOTENCY_KEY_REUSED`. EVIDENCE: operation table. RELATED_FR: 072.
- **P4-AC-067:** PRECONDITION: any mutation. ACTION: extra undocumented JSON field (including owner/status). EXPECTED: `422 UNKNOWN_FIELD`, no rows. EVIDENCE: API. RELATED_FR: 077.
- **P4-AC-068:** PRECONDITION: CLOSED at T. ACTION: RecordAction at T+12h and T+25h; addition execute at T+12h and T+25h; yeast source-pair change; yeast annotation at T+2d. EXPECTED: both actions 409; addition 12h allowed 25h 409; source-pair 409; annotation allowed. EVIDENCE: API. RELATED_FR: 061.

## 46. Adversarial scenarios

- **P4-ADV-001:** PRECONDITION: recorded measurement. ACTION: same operation_id same payload; then same key different payload. EXPECTED: replay; then 409. EVIDENCE: IDs. RELATED_FR: 071,072. RELATED_AC: 037.
- **P4-ADV-002:** PRECONDITION: eligible session. ACTION: two concurrent CompleteFermentation. EXPECTED: one winner. EVIDENCE: PG interleaving. RELATED_FR: 074. RELATED_AC: 036.
- **P4-ADV-003:** PRECONDITION: owner A session. ACTION: owner B GET/mutate nested IDs. EXPECTED: 404. EVIDENCE: matrix. RELATED_FR: 075. RELATED_AC: 038.
- **P4-ADV-004:** PRECONDITION: session A. ACTION: attach measurement to session B via API and direct SQL. EXPECTED: both rejected. EVIDENCE: API+constraint. RELATED_FR: 032. RELATED_AC: 020.
- **P4-ADV-005:** PRECONDITION: three stable readings then newer 1.020. ACTION: evaluate / complete. EXPECTED: NOT_STABLE; complete 422. EVIDENCE: goldens. RELATED_FR: 035,040. RELATED_AC: 018,022.
- **P4-ADV-006:** PRECONDITION: confirmed complete. ACTION: invalidating vs note-only correction. EXPECTED: invalidate vs no-invalidate per §14.6. EVIDENCE: state. RELATED_FR: 043. RELATED_AC: 024.
- **P4-ADV-007:** PRECONDITION: two gravities only. ACTION: complete. EXPECTED: 422, persisted INSUFFICIENT assessment, not FERMENTATION_COMPLETE. EVIDENCE: DB. RELATED_FR: 040. RELATED_AC: 022.
- **P4-ADV-008:** PRECONDITION: any state. ACTION: waive pitched_at or yeast note. EXPECTED: 409 WAIVER_PROHIBITED. EVIDENCE: API. RELATED_FR: 060. RELATED_AC: 054.
- **P4-ADV-009:** PRECONDITION: F-REC-1. ACTION: stop Redis. EXPECTED: GET authority unchanged; compare IDs/due_at. EVIDENCE: GET. RELATED_FR: 079. RELATED_AC: 029.
- **P4-ADV-010:** PRECONDITION: F-REC-1. ACTION: API restart. EXPECTED: same IDs. EVIDENCE: GET. RELATED_FR: 078. RELATED_AC: 029.
- **P4-ADV-011:** PRECONDITION: deadline during outage. ACTION: refresh. EXPECTED: one expiry event. EVIDENCE: journal count. RELATED_FR: 051. RELATED_AC: 029.
- **P4-ADV-012:** PRECONDITION: CLOSED and ABORTED. ACTION: full §25 DENY set. EXPECTED: 409. EVIDENCE: matrix. RELATED_FR: 016. RELATED_AC: 047,048.
- **P4-ADV-013:** PRECONDITION: upload. ACTION: polyglot/MIME mismatch. EXPECTED: 415/422. EVIDENCE: security. RELATED_FR: 064. RELATED_AC: 052.
- **P4-ADV-014:** PRECONDITION: mutation. ACTION: wrong CSRF. EXPECTED: 403. EVIDENCE: API. RELATED_FR: 076. RELATED_AC: 039.
- **P4-ADV-015:** PRECONDITION: GET. ACTION: hostile session ID. EXPECTED: 404/422, no 500 leak. EVIDENCE: logs+status. RELATED_FR: 075. RELATED_AC: 038.
- **P4-ADV-016:** PRECONDITION: perf harness. ACTION: run §37. EXPECTED: no authoritative user writes. EVIDENCE: user-table diff. RELATED_FR: 081. RELATED_AC: 041.
- **P4-ADV-017:** PRECONDITION: Phase 4 API. ACTION: create packaging session. EXPECTED: fail closed. EVIDENCE: 404/405/422. RELATED_FR: 013,086. RELATED_AC: 011.
- **P4-ADV-018:** PRECONDITION: two sessions. ACTION: circular and concurrent opposite yeast edges. EXPECTED: reject. EVIDENCE: 422/409. RELATED_FR: 069. RELATED_AC: 034.
- **P4-ADV-019:** PRECONDITION: mixed journal. ACTION: backdated correction same occurred_at as Phase 3 event. EXPECTED: stable merge key. EVIDENCE: export. RELATED_FR: 062. RELATED_AC: 046.
- **P4-ADV-020:** PRECONDITION: Phase 4 client. ACTION: mutate pitch handoff. EXPECTED: no Phase 4 path; Phase 3 rules unchanged. EVIDENCE: route scan. RELATED_FR: 012. RELATED_AC: 010.
- **P4-ADV-021:** PRECONDITION: waived OG brew, first ferment gravity 3 days later. ACTION: start then read OG. EXPECTED: OG UNKNOWN, ferment gravity not OG. EVIDENCE: pin row. RELATED_FR: 003,004. RELATED_AC: 004,010.
- **P4-ADV-022:** PRECONDITION: valid handoff null pitch_temperature_c. ACTION: start. EXPECTED: success, temperature UNKNOWN. EVIDENCE: DB. RELATED_FR: 002. RELATED_AC: 004.
- **P4-ADV-023:** PRECONDITION: CLOSED session. ACTION: start different key. EXPECTED: 409 EXISTS. EVIDENCE: API. RELATED_FR: 008. RELATED_AC: 007.
- **P4-ADV-024:** PRECONDITION: PAUSED from ACTIVE, stale complete. ACTION: complete. EXPECTED: 409. EVIDENCE: API. RELATED_FR: 016. RELATED_AC: 012.
- **P4-ADV-025:** PRECONDITION: 1.014/1.012/1.010 spaced 24h. ACTION: stable eval. EXPECTED: NOT_STABLE. EVIDENCE: unit. RELATED_FR: 035. RELATED_AC: 018.
- **P4-ADV-026:** PRECONDITION: future observed_at >5 min or naive TZ. ACTION: measure. EXPECTED: 422. EVIDENCE: API. RELATED_FR: 030. RELATED_AC: 020.
- **P4-ADV-027:** PRECONDITION: yeast lot of user B cited by user A. ACTION: enrich. EXPECTED: 404. EVIDENCE: API. RELATED_FR: 067,075. RELATED_AC: 034,038.
- **P4-ADV-028:** PRECONDITION: completion read then gravity insert. ACTION: interleave without waiting. EXPECTED: lock-before-read; no stale READY. EVIDENCE: R3/R13. RELATED_FR: 074. RELATED_AC: 036.
- **P4-ADV-029:** PRECONDITION: live equipment edit. ACTION: historical GET. EXPECTED: unchanged snapshot. EVIDENCE: JSON. RELATED_FR: 011. RELATED_AC: 049.
- **P4-ADV-030:** PRECONDITION: restore. ACTION: replay old start key. EXPECTED: replay, no second session. EVIDENCE: operation table. RELATED_FR: 072,080. RELATED_AC: 040.
- **P4-ADV-031:** PRECONDITION: unplanned addition while PAUSED. ACTION: create. EXPECTED: 409/422 no execution. EVIDENCE: API. RELATED_FR: 054. RELATED_AC: 012.
- **P4-ADV-032:** PRECONDITION: override with zero gravities. ACTION: complete override. EXPECTED: 422. EVIDENCE: API. RELATED_FR: 042. RELATED_AC: 022.
- **P4-ADV-033:** PRECONDITION: HANDOFF_READY. ACTION: abort. EXPECTED: 409 INVALID_TRANSITION. EVIDENCE: API. RELATED_FR: 016. RELATED_AC: 012.
- **P4-ADV-034:** PRECONDITION: PAUSED origin CONDITIONING. ACTION: abort. EXPECTED: ABORTED, §9.6. EVIDENCE: DB. RELATED_FR: 021. RELATED_AC: 057.
- **P4-ADV-035:** PRECONDITION: UNKNOWN OG, R1/R2 true. ACTION: record READY without waiver; then override with R1 false. EXPECTED: not READY; `409 OVERRIDE_PROHIBITED`. EVIDENCE: API. RELATED_FR: 059. RELATED_AC: 059.
- **P4-ADV-036:** PRECONDITION: INVALIDATED CONDITIONING row. ACTION: StartConditioning creating a new UUID. EXPECTED: reuse existing ID or 409 if a non-invalidated row exists; never two PKs. EVIDENCE: DB. RELATED_FR: 088. RELATED_AC: 060.
- **P4-ADV-037:** PRECONDITION: ACTIVE. ACTION: 100 Plato gravity. EXPECTED: `422 PLATO_OUT_OF_DOMAIN`, no leaf. EVIDENCE: API. RELATED_FR: 038. RELATED_AC: 062.
- **P4-ADV-038:** PRECONDITION: day-10 reactivation. ACTION: new temperature. EXPECTED: accepted in current-activation window. EVIDENCE: API. RELATED_FR: 088. RELATED_AC: 063.
- **P4-ADV-039:** PRECONDITION: `details.schedule` present. ACTION: start. EXPECTED: schedule in snapshot hash, not ignored. EVIDENCE: hash. RELATED_FR: 011. RELATED_AC: 064.
- **P4-ADV-040:** PRECONDITION: shared expected_revision. ACTION: complete vs measure. EXPECTED: one STALE loser. EVIDENCE: PG. RELATED_FR: 074. RELATED_AC: 065.
- **P4-ADV-041:** PRECONDITION: lost assessment response then new gravity. ACTION: retry same key/body. EXPECTED: replay. EVIDENCE: operation row. RELATED_FR: 072. RELATED_AC: 066.
- **P4-ADV-042:** PRECONDITION: CLOSED. ACTION: RecordAction at 12h. EXPECTED: 409, not addition window. EVIDENCE: API. RELATED_FR: 016. RELATED_AC: 068.

## 47. Testing strategy

| Layer | Applies to |
|---|---|
| DOMAIN_UNIT | calculations, stable gravity, plan materialization, eligibility tables, state guards |
| POSTGRESQL | invariants, locks, unique leaves, cycles, append-only |
| API_INTEGRATION | endpoints, validation, idempotency, terminal matrix |
| SECURITY | CSRF, IDOR nested, media, mass assignment, error leakage |
| MIGRATION | Phase 3 head → Phase 4 head; fresh/upgrade/round-trip |
| RECOVERY | F-REC-1/2 faults |
| BACKUP_RESTORE | §35 vectors |
| PERFORMANCE | §37 isolated harness |
| FRONTEND_UNIT | view-model only |
| PLAYWRIGHT | canonical flow + regressions |
| ACCESSIBILITY_INSPECTION | listed controls/viewports |

No requirement may be accepted from documentation alone.

## 48. Migration acceptance

Phase 4 migration must:

1. apply additively from the accepted Phase 3 migration head;
2. preserve all Phase 1A/2/3 data, IDs, and constraints;
3. enforce new constraints/indexes/triggers for append-only, uniqueness, and ownership joins;
4. support fresh install and upgrade;
5. support downgrade/round-trip to the same standard as Phase 3 (downgrade removes only new Phase 4 objects).

The test-layer name is “accepted Phase 3 head → verified Phase 4 head”, not a provisional `0003→0004` label.

## 49. Regression requirements

Phase 4 acceptance requires green baseline evidence for Phase 3 (canonical PRE_BREW→BREW_COMPLETE browser test and PostgreSQL suite including invariants, migration, addition correction, waiver, reminders, media/security, recovery and backup), Phase 2 (core/calculations/inventory plus phase2.spec.ts), and Phase 1A (phase1a.spec.ts), in addition to Phase 4 gates. Existing test counts are recountable, not permission to drop named tests.

Phase 4 must preserve RecipeVersion→BrewSession, stages, timers/reminders, measurements, additions, corrections/waivers, notes/media, journal, and pitch handoff.

## 50. Phase 5+ leakage matrix

| Capability | Phase | PHASE_4_STATUS | Rationale |
|---|---|---|---|
| Fermentation session management | 4 | ALLOWED_OPERATIONAL | core Phase 4 |
| Conditioning tracking | 4 | ALLOWED_OPERATIONAL | core Phase 4 |
| Yeast pitch history / declaration | 4 | ALLOWED_OPERATIONAL | core Phase 4 |
| Packaging readiness handoff facts | 4 | ALLOWED_HANDOFF_FACT | terminal seam to Phase 5 |
| Packaging sessions | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| Keg/can/bottle inventory | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| Carbonation operations | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| QA/QC plans | 5 | PROHIBITED_OPERATIONAL_BEHAVIOR | Phase 5 scope |
| Automatic inventory consumption | 6 | PROHIBITED_OPERATIONAL_BEHAVIOR | ADR required |
| Yeast harvest/storage/reuse operations | later | PROHIBITED_OPERATIONAL_BEHAVIOR | P4-DEC-004 |
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
| P4-DEC-001 | Fermentation session start trigger | explicit start after completed brew + pitch handoff | preserves brew-day terminal boundary | none | NO |
| P4-DEC-002 | Timer subsystem | reuse Phase 3 timer architecture | avoid competing authority | pattern reuse | NO |
| P4-DEC-003 | Inventory consumption on pitch | none in Phase 4 | Phase 6/ADR gate | none | YES if later enabled; candidate ADR, not blocking |
| P4-DEC-004 | Yeast harvest/reuse ops | deferred; declaration fields only | roadmap sequencing | additive fields | YES before ops; candidate ADR, not blocking |
| P4-DEC-005 | Pressure fermentation | deferred | not in authoritative PRD | none | NO |
| P4-DEC-006 | Completion primary evidence | stable gravity full-window + checkpoints + confirm | deterministic | none | NO |
| P4-DEC-007 | Phase 5 seam | versioned packaging readiness facts only | smallest forward seam | none | NO |
| P4-DEC-008 | Journal strategy | extend brew journal with Phase 3 merge key | preserve chronology | additive events | NO |
| P4-DEC-009 | OG after entry | pin at start; explicit reconcile | ADR-0003/0010; preserve pre-pitch meaning | Phase 4 only | NO |
| P4-DEC-010 | Plan revisions | prohibited after start | ADR-0010 snapshot discipline | none | NO |
| P4-DEC-011 | Late-entry windows | inherit Phase 3 §6.8 mapped to fermentation terminal times | do not invent a second time policy | none | NO |
| P4-DEC-012 | Reopen after CLOSED | denied; requalify handoff versions only | no implicit reopen | none | NO |

## 53. Open questions

Declared register plus independent-review implicit questions. All blocking items are resolved from accepted architecture.

| QUESTION_ID | QUESTION | BLOCKS_SPEC_ACCEPTANCE | DISPOSITION |
|---|---|---|---|
| P4-OQ-001 | User-wide concurrent fermentation cap? | NO | none; per-brew uniqueness only |
| P4-OQ-002 | Manual yeast consumption in Phase 4? | NO | deferred; ADR required before enablement |
| P4-OQ-003 | Conditioning mode names | NO | enum in §17.1 |
| RQ-01 | Missing/corrected OG and null pitch temperature | resolved | §6.2 / P4-DEC-009 |
| RQ-02 | Lifecycle, pause origin, skip, uniqueness | resolved | §9 |
| RQ-03 | Completion/waiver/override predicates | resolved | §14 |
| RQ-04 | Revoke/requalify/handoff current | resolved | §14.6 §7 |
| RQ-05 | Stable gravity window | resolved | §15 |
| RQ-06 | Measurement/calculation domains | resolved | §12–13 |
| RQ-07 | Time and late/terminal windows | resolved | §18 §24 P4-DEC-011 |
| RQ-08 | Plan/schedule/deviation/equipment | resolved | §10 §22 §29 P4-DEC-010 |
| RQ-09 | Post-pitch addition timing/repeat | resolved | §21 |
| RQ-10 | Yeast source relation | resolved | §11 |
| RQ-11 | Concurrent evidence/assessment | resolved | §32 |

RQ-01 through RQ-11 remain the original implicit review questions. The second bounded remediation closed the residual implementation-critical gaps that the independent re-review still found in RQ-02, RQ-03, RQ-04, RQ-06, RQ-07, RQ-08, and RQ-11. No new product decision was invented. `P4-OQ-001` through `P4-OQ-003` remain non-blocking.

`OPEN_BLOCKING_QUESTIONS=0`

## 54. Traceability contract

The following mapping is normative. Every FR, AC, and ADV appears at least once. EXPECTED_TEST_LAYER is the primary evidence layer; additional layers may supplement.

| FR_ID | AC_ID(S) | ADV_ID(S) | EXPECTED_TEST_LAYER | REQUIRED_EVIDENCE |
|---|---|---|---|---|
| P4-FR-001 | 004 | 022 | API_INTEGRATION | start transaction rows |
| P4-FR-002 | 004 | 022 | API_INTEGRATION | null temperature fixture |
| P4-FR-003 | 004,010 | 021,020 | POSTGRESQL | OG pin IDs; ferment ≠ OG |
| P4-FR-004 | 004 | 021 | API_INTEGRATION | UNKNOWN OG start |
| P4-FR-005 | 010 | 020 | API_INTEGRATION | pin versions |
| P4-FR-006 | 005 | — | API_INTEGRATION | 422 zero rows |
| P4-FR-007 | 006 | 003 | SECURITY | 404 |
| P4-FR-008 | 007 | 023 | POSTGRESQL | unique partial index |
| P4-FR-009 | 008 | — | API_INTEGRATION | new session after abort |
| P4-FR-010 | 009 | — | API_INTEGRATION | two brews |
| P4-FR-011 | 004,027,028,049,064 | 029,039 | DOMAIN_UNIT | hash goldens + schedule keys + template vs row IDs |
| P4-FR-012 | 001,010 | 020 | POSTGRESQL | Phase 3 row hashes |
| P4-FR-013 | 011 | 017 | API_INTEGRATION | zero packaging rows |
| P4-FR-014 | 004 | 001 | API_INTEGRATION | start replay before list |
| P4-FR-015 | 012,050,057,058 | 024,033 | DOMAIN_UNIT | full table including every §9.5 A cell |
| P4-FR-016 | 012,068 | 012,024,033,042 | API_INTEGRATION | 409 no writes |
| P4-FR-017 | 013 | 024 | POSTGRESQL | pause_origin |
| P4-FR-018 | 013,016,029,057 | 011,034 | POSTGRESQL | child states including abort/reactivation |
| P4-FR-019 | 023,050 | — | API_INTEGRATION | no auto conditioning |
| P4-FR-020 | 050,053 | — | API_INTEGRATION | distinct assessments |
| P4-FR-021 | 016,057 | 012,034 | API_INTEGRATION | abort vector including PAUSED and COND_COMPLETE |
| P4-FR-022 | 017 | 012 | API_INTEGRATION | close guard |
| P4-FR-023 | 014 | — | API_INTEGRATION | skip destination |
| P4-FR-024 | 012,060 | 036 | API_INTEGRATION | repeat deny; reuse after invalidation |
| P4-FR-025 | 020 | 004,025 | DOMAIN_UNIT | gravity matrix |
| P4-FR-026 | 020 | 026 | API_INTEGRATION | temp bounds |
| P4-FR-027 | 020 | — | API_INTEGRATION | pH bounds |
| P4-FR-028 | 020 | — | API_INTEGRATION | stage required |
| P4-FR-029 | 020,063 | 019,038 | API_INTEGRATION | dual timestamps; current-activation window |
| P4-FR-030 | 020 | 026 | API_INTEGRATION | 422 time |
| P4-FR-031 | 020,024 | 006 | POSTGRESQL | leaf uniqueness |
| P4-FR-032 | 020 | 004 | POSTGRESQL | FK/API |
| P4-FR-033 | 021 | — | DOMAIN_UNIT | ratio goldens |
| P4-FR-034 | 021 | — | DOMAIN_UNIT | clip/undefined |
| P4-FR-035 | 018,019 | 005,025 | DOMAIN_UNIT | §15 vectors |
| P4-FR-036 | 021 | — | DOMAIN_UNIT | ABV formula |
| P4-FR-037 | 021 | — | DOMAIN_UNIT | missing inputs |
| P4-FR-038 | 019,062 | 037 | DOMAIN_UNIT | inversion goldens including 100 Plato and endpoints |
| P4-FR-039 | 055,022 | 007 | API_INTEGRATION | duration-only fail |
| P4-FR-040 | 022,053 | 007,032 | POSTGRESQL | failed assessment row |
| P4-FR-041 | 023 | 002 | API_INTEGRATION | success transition |
| P4-FR-042 | 022,059 | 032,035 | API_INTEGRATION | override limits including R3-only |
| P4-FR-043 | 024,025,047,061 | 006 | POSTGRESQL | destination+CLOSED |
| P4-FR-044 | 026,061 | 017 | POSTGRESQL | versions/current |
| P4-FR-045 | 053 | — | API_INTEGRATION | C1/C2 |
| P4-FR-046 | 027 | — | API_INTEGRATION | deny mode at complete |
| P4-FR-047 | 014,015 | — | API_INTEGRATION | skip guards |
| P4-FR-048 | 029 | 010 | POSTGRESQL | timer rows |
| P4-FR-049 | 029 | 009,010 | RECOVERY | F-REC-1 |
| P4-FR-050 | 030,051 | — | API_INTEGRATION | ACK≠SATISFIED |
| P4-FR-051 | 029 | 011 | RECOVERY | one expiry |
| P4-FR-052 | 031 | — | DOMAIN_UNIT | 2880 mapping |
| P4-FR-053 | 032 | — | API_INTEGRATION | 409 repeat |
| P4-FR-054 | 012 | 031 | API_INTEGRATION | paused deny |
| P4-FR-055 | 024 | 006 | POSTGRESQL | addition leaf |
| P4-FR-056 | 056 | — | API_INTEGRATION | enum 422 |
| P4-FR-057 | 033 | — | POSTGRESQL | ledger zero |
| P4-FR-058 | 020 | 006 | POSTGRESQL | deviation successor |
| P4-FR-059 | 051,059 | 008,035 | API_INTEGRATION | waiver catalog including ORIGINAL_GRAVITY_KNOWN |
| P4-FR-060 | 054 | 008 | API_INTEGRATION | WAIVER_PROHIBITED |
| P4-FR-061 | 047,048,068 | 012,042 | API_INTEGRATION | windows; Action vs Addition vs yeast vs equipment |
| P4-FR-062 | 046 | 019 | API_INTEGRATION | export order |
| P4-FR-063 | 046 | 019 | API_INTEGRATION | event types present |
| P4-FR-064 | 047,052 | 013 | SECURITY | media+notes terminal |
| P4-FR-065 | 046 | 019 | API_INTEGRATION | json/html |
| P4-FR-066 | 034,035 | 027 | API_INTEGRATION | snapshot |
| P4-FR-067 | 034 | 018,027 | API_INTEGRATION | pair rules |
| P4-FR-068 | 035 | — | API_INTEGRATION | query filters |
| P4-FR-069 | 034 | 018 | POSTGRESQL | cycle race |
| P4-FR-070 | 033 | 017 | POSTGRESQL | no consumption |
| P4-FR-071 | 037 | 001 | API_INTEGRATION | missing key |
| P4-FR-072 | 037,066 | 001,030,041 | API_INTEGRATION | fingerprint/tombstone; lookup before evidence reread |
| P4-FR-073 | 036,065 | 002,024,040 | POSTGRESQL | stale 409 |
| P4-FR-074 | 036,065 | 002,028,040 | POSTGRESQL | R3–R8,R13 OCC loser always STALE |
| P4-FR-075 | 006,038 | 003,015,027 | SECURITY | IDOR |
| P4-FR-076 | 039 | 014 | SECURITY | CSRF |
| P4-FR-077 | 020,067 | 026 | API_INTEGRATION | closed schema; 422 UNKNOWN_FIELD |
| P4-FR-078 | 029 | 010 | RECOVERY | restart |
| P4-FR-079 | 029 | 009 | RECOVERY | Redis |
| P4-FR-080 | 040 | 030 | BACKUP_RESTORE | vectors |
| P4-FR-081 | 041 | 016 | PERFORMANCE | harness |
| P4-FR-082 | 045,050 | — | PLAYWRIGHT | keyboard/360 |
| P4-FR-083 | 020 | 026 | API_INTEGRATION | fail-closed |
| P4-FR-084 | 001,042 | 020 | PLAYWRIGHT | Phase 3 named suites |
| P4-FR-085 | 043 | — | PLAYWRIGHT | 1A/2 named suites |
| P4-FR-086 | 002,003,011 | 017 | API_INTEGRATION | leakage scan |
| P4-FR-087 | 044 | — | MIGRATION | head-to-head |
| P4-FR-088 | 060,063 | 036,038 | POSTGRESQL | reuse PK; current-activation window; new timer IDs |
| P4-FR-089 | 026,059,061 | 035 | POSTGRESQL | CLOSED requalify from current evidence |

AC rows 001–068 and ADV rows 001–042 are each cited above. P4-AC-001 additionally maps FR-084.

Bidirectional check: no AC or ADV may be introduced without a row in this table.

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

Phase 4 consumption of Phase 3 is reconciled: OG meaning remains pre-pitch; journal merge preserves Phase 3 relative order; additions/timers/reminders/waivers/corrections adapt named Phase 3 contracts; pitch temperature nullability is accepted; no Phase 3 file is modified by this specification.

`PHASE_3_BASELINE_COMPATIBILITY=PASS` as a Phase 4 consumption verdict. Predecessor sources remain untouched.

## 57. Specification self-review checklist

- [x] Phase 3 entry contract decidable including OG pin, null temperature, uniqueness, atomicity, retry
- [x] Phase 5 readiness versus operations distinguished; handoff versioned
- [x] Exhaustive session transition table matching the allowlist, including abort from PAUSED/CONDITIONING_COMPLETE and reassessment from ASSESSED/HANDOFF_READY/CLOSED
- [x] Completion eligibility/confirmation/invalidation/CLOSED requalify without implicit reopen
- [x] Stage reuse after invalidation; current-activation time window; new timer identities
- [x] Stable gravity total algorithm plus goldens
- [x] Plato inverse domain, nonconvergence, and fail-closed 422 codes
- [x] Time table as sole source including current vs first timestamps
- [x] Correction/late-entry/terminal matrix with Action, Addition, Yeast, and Equipment split
- [x] Idempotency (client-canonical fingerprints; lookup before evidence reread) and OCC concurrency
- [x] Yeast pair/cycle/snapshot
- [x] Addition FROM_PITCH mapping
- [x] Traceability table with zero orphans
- [x] Security nested IDOR, CSRF, and unknown-field 422 on new commands
- [x] Recovery/backup/performance measurable
- [x] Safety software versus hardware
- [x] No blocking open questions
- [x] Passing predecessor contracts not destabilized

`SPECIFICATION_SELF_REVIEW=PASS` as an author checklist, not independent acceptance.

## 58. Independent review remediation traceability

Historical finding IDs from `docs/evidence/PHASE_4_INDEPENDENT_ARCHITECTURE_AND_SPECIFICATION_REVIEW.md` are preserved. Re-review IDs from `docs/evidence/PHASE_4_INDEPENDENT_SPECIFICATION_RE_REVIEW.md` are appended. Prior FAIL history is not erased. First-remediation STATUS values that the re-review reopened remain visible in `FIRST_REMEDIATION_STATUS` / `RE_REVIEW_STATUS`.

| FINDING_ID | ORIGINAL_SEVERITY | FIRST_REMEDIATION_STATUS | RE_REVIEW_STATUS | SECOND_REMEDIATION_REFERENCE | RELATED_FR | RELATED_AC | RELATED_ADV | FINAL_STATUS |
|---|---|---|---|---|---|---|---|---|
| P4-SPEC-001 | P1 | CLOSED | CLOSED | unchanged; §§6–7 | 002–007 | 004–006,010 | 021,022,020 | CLOSED |
| P4-SPEC-002 | P1 | CLOSED | REOPENED | §9.4 sole authority; abort PAUSED/COND_COMPLETE; reassess ASSESSED/HANDOFF_READY/CLOSED | 015–024,088,089 | 012,016,050,057,058 | 024,033,034 | CLOSED |
| P4-SPEC-003 | P1 | CLOSED | REOPENED | §10.3 `ORIGINAL_GRAVITY_KNOWN`; §14.4–14.5 R3-only override | 042,059,089 | 022,051,059 | 008,032,035 | CLOSED |
| P4-SPEC-004 | P1 | CLOSED | REOPENED | §9.8 reuse; §14.6 CLOSED current-evidence path; current vs first timestamps | 024,043,044,088,089 | 024–026,060,061 | 006,036 | CLOSED |
| P4-SPEC-005 | P1 | CLOSED | CLOSED | unchanged; §15 | 035 | 018,019 | 005,025 | CLOSED |
| P4-SPEC-006 | P1 | CLOSED | REOPENED | §13 Plato image domain; `PLATO_OUT_OF_DOMAIN` / `PLATO_CONVERSION_FAILED` | 038,083 | 019,062 | 026,037 | CLOSED |
| P4-SPEC-007 | P1 | CLOSED | REOPENED | §18 current-activation window; historical `completed_at` not an active upper bound | 029,030,061,088 | 020,047,063 | 026,038 | CLOSED |
| P4-SPEC-008 | P1 | CLOSED | REOPENED | §10.1 recognized `schedule`/`conditioning_schedule`; ingredient order; template vs row ID | 011 | 027,028,049,064 | 029,039 | CLOSED |
| P4-SPEC-009 | P1 | CLOSED | CLOSED | unchanged; §21 | 052–057 | 031–033,056 | 031 | CLOSED |
| P4-SPEC-010 | P1 | CLOSED | CLOSED | unchanged; §11 | 066–070 | 034,035 | 018,027 | CLOSED |
| P4-SPEC-011 | P1 | CLOSED | REOPENED | §32 OCC: same initial revision → one winner, loser `409 STALE_REVISION`; fail increments revision | 073,074 | 036,065 | 002,028,040 | CLOSED |
| P4-SPEC-012 | P2 | CLOSED | REOPENED | §31 client-canonical fingerprint; lookup before evidence reread; `422 UNKNOWN_FIELD` | 014,071,072,077 | 004,037,066,067 | 001,041 | CLOSED |
| P4-SPEC-013 | P2 | CLOSED | CLOSED | unchanged; §26 | 062,063,065 | 046 | 019 | CLOSED |
| P4-SPEC-014 | P2 | CLOSED | CLOSED | unchanged; §§35–37 | 078–081 | 029,040,041 | 009–011,016,030 | CLOSED |
| P4-SPEC-015 | P2 | CLOSED | CLOSED | §54/§58 ranges 001–089 / 001–068 / 001–042 | 001–089 | 001–068 | 001–042 | CLOSED |
| P4-SPEC-016 | P2 | CLOSED | REOPENED | §24–§25 split Action, Addition, Yeast, Equipment; API alignment | 016,061,064 | 047,048,068 | 012,042 | CLOSED |
| P4-SPEC-017 | P3 | CLOSED | CLOSED | unchanged; §§1,47–48 | 087 | 044 | — | CLOSED |
| P4-RR-001 | P1 | n/a | REOPENED | same as P4-SPEC-002 second pass | 015,021,089 | 057,058 | 034 | CLOSED |
| P4-RR-002 | P1 | n/a | REOPENED | same as P4-SPEC-003 second pass | 059,042,089 | 059 | 035 | CLOSED |
| P4-RR-003 | P1 | n/a | REOPENED | same as P4-SPEC-004 second pass | 024,088,089 | 060,061,026 | 036 | CLOSED |
| P4-RR-004 | P1 | n/a | REOPENED | same as P4-SPEC-006 second pass | 038 | 062 | 037 | CLOSED |
| P4-RR-005 | P1 | n/a | REOPENED | same as P4-SPEC-007 second pass | 029,088 | 063 | 038 | CLOSED |
| P4-RR-006 | P1 | n/a | REOPENED | same as P4-SPEC-008 second pass | 011 | 064 | 039 | CLOSED |
| P4-RR-007 | P1 | n/a | REOPENED | same as P4-SPEC-011 second pass | 073,074 | 065 | 040 | CLOSED |
| P4-RR-008 | P2 | n/a | REOPENED | same as P4-SPEC-012 second pass | 072,077 | 066,067 | 041 | CLOSED |
| P4-RR-009 | P2 | n/a | REOPENED | same as P4-SPEC-016 second pass | 016,061 | 068 | 042 | CLOSED |
| P4-RR-010 | P3 | n/a | NEW | §58 RELATED_AC now the full AC range | 001–089 | 001–068 | 001–042 | CLOSED |

`P0_OPEN=0` `P1_OPEN=0` `BLOCKING_P2_OPEN=0` `P3_OPEN=0`
