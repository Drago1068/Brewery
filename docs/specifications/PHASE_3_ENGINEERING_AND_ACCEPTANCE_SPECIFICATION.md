# Phase 3 Engineering and Acceptance Specification - Brew-Day OS

## 1. Document control

- Status: **DRAFT REMEDIATED AFTER INDEPENDENT RE-REVIEW**
- Scope identifier: `PHASE_3_BREW_DAY_OS`
- Source baseline: annotated tag `v0.2.0-phase2`
- Source baseline commit: `c3faa93ea1502db63798b8c0dcc10c02741fabf7`
- Expected migration: `0003_phase3_brew_day_os`
- Implementation authorization: **NOT GRANTED BY THIS DOCUMENT**
- NAS production deployment: **NOT AUTHORIZED**

Independent review procedure: [Codex Phase 3 Engineering Specification Independent Review Master Prompt](../prompts/CODEX_PHASE_3_ENGINEERING_SPECIFICATION_INDEPENDENT_REVIEW_MASTER_PROMPT.md).

This specification is the engineering contract for Phase 3. It defines the implementation boundary, required behavior, prohibited forward leakage, and evidence needed for independent acceptance. It refines the [master plan](../product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md), [roadmap](../DEVELOPMENT_ROADMAP.md), and accepted [Phase 2 evidence](../evidence/PHASE_2_INDEPENDENT_ARCHITECTURE_AND_BREWING_ACCEPTANCE.md).

If this specification conflicts with a lower-level implementation convenience, this specification controls. If it conflicts with an accepted ADR or the master plan, implementation must stop and an ADR or specification amendment must be reviewed before code continues.

## 2. Authorization and stop rules

Creating or approving this document does not authorize Phase 3 implementation. Code may begin only after the user explicitly authorizes Phase 3 against an approved revision of this specification.

Phase 3 implementation must stop when all Phase 3 acceptance evidence is assembled. It must not continue into Phase 4, production deployment, or release tagging until independent architecture and brewing-domain review returns `PASS` and the next action is separately authorized.

The accepted `v0.2.0-phase2` tag is immutable. Phase 3 must be additive and must preserve the accepted Phase 1A and Phase 2 behaviors.

## 3. Outcome

Phase 3 delivers a reliable, responsive Brew-Day OS that takes an owned, immutable recipe version and its process plan through a complete, stage-aware brew session ending at the recorded yeast-pitch handoff.

The brewer must be able to:

1. review a snapshotted brew plan and required observations;
2. start, pause, resume, abort, and complete an authorized brew session;
3. move through the defined brewing stages in order;
4. run and recover multiple persistent timers, including scheduled additions;
5. receive deterministic, stage-aware reminders;
6. record validated measurements with provenance and corrections;
7. compare planned and actual values and record deviations;
8. add timestamped notes and photos;
9. safely use confirmed voice-assisted entry where supported;
10. recover the authoritative session after refresh or reconnect; and
11. finish with an immutable, chronological brew-day journal and explicit handoff facts.

Phase 3 does not manage what happens after yeast pitch.

This specification deliberately preserves the accepted Phase 1A/2 `RecipeVersion -> BrewSession` execution lineage. Phase 3 does not introduce mandatory `BrewPlan` or `BrewBatch` aggregate roots, a transactional outbox, a distributed event worker, an offline mutation/synchronization engine, or inventory reservation-to-consumption automation. Any future need for one of those architecture changes requires its own accepted ADR and phase authorization. This restriction does not prevent Phase 3 from recording stable upstream identifiers, actual addition facts, provenance, or a versioned yeast-pitch handoff fact.

## 4. Required end-to-end slice

The minimum accepted browser flow is:

`RecipeVersion -> planned BrewSession -> review checklist -> ACTIVE -> stage execution -> concurrent timers and additions -> required measurements -> deviations/corrections -> notes/photos -> YEAST_PITCH -> BREW_COMPLETE -> immutable journal`

The flow must use a real PostgreSQL-backed API and the responsive web interface. A UI-only demonstration, mocked persistence, SQLite-only evidence, or API-only path is insufficient for acceptance.

## 5. Domain boundary and vocabulary

### 5.1 Authoritative concepts

- **Brew session:** owned execution record tied to one immutable recipe version.
- **Plan snapshot:** the recipe, equipment, calculation, process-step, addition, target, tolerance, and model data needed to explain what was planned when the session was created.
- **Stage:** an ordered execution boundary with entry, active, completion, skip, and abort rules.
- **Timer:** server-authoritative elapsed-time record associated with a session, stage, or planned addition.
- **Reminder:** deterministic required-action projection derived from persisted rules and authoritative time.
- **Measurement:** append-only observation with value, unit, type, time, method, and provenance.
- **Correction:** a new observation linked to the superseded observation; never an overwrite.
- **Deviation:** deterministic comparison or explicit operational departure linked to its source.
- **Addition event:** planned-versus-actual record of an ingredient or process addition; it is not an inventory transaction.
- **Journal event:** append-only, chronological execution fact suitable for the final brew-day audit.
- **Note/media attachment:** brewer-authored context linked to the session or stage; it is not structured quality, sensory, or fermentation evidence.

### 5.2 Governing authority boundary

> AI recommends and reasons. Deterministic software calculates, validates, records, and enforces rules.

Phase 3 does not require an AI feature. All workflow transitions, timing, reminders, validation, comparisons, permissions, and persistence must be deterministic application behavior.

## 6. State machines

### 6.1 Brew-session states

Required states:

`PLANNED -> READY -> ACTIVE <-> PAUSED -> COMPLETED`

Exceptional terminal state:

`PLANNED | READY | ACTIVE | PAUSED -> ABORTED`

Rules:

- A session starts from an owned recipe version and an immutable plan snapshot.
- At most one nonterminal `ACTIVE` or `PAUSED` brew session may exist per user unless a later ADR explicitly permits concurrency.
- `READY` means preflight validation passed; it does not imply any timer started.
- Only `ACTIVE` sessions may start stages or record normal execution actions.
- Pausing and resuming are explicit, timestamped actions. Wall-clock and active-time semantics must both remain explainable.
- `COMPLETED` and `ABORTED` are terminal and cannot be reopened.
- Aborting requires a nonempty reason and retains all prior events.
- Completion requires all mandatory stages and requirements to be satisfied or explicitly waived under the waiver rules.
- Invalid or repeated commands must return a stable conflict response and must not create duplicate state or events.

#### 6.1.1 Deterministic execution-plan materialization

Creating a `PLANNED` BrewSession transactionally materializes a versioned execution-plan snapshot. The authoritative lineage remains:

`RecipeVersion process snapshot -> Phase 3 materialization rules -> BrewSession execution snapshot -> stage instances -> runtime events/deviations`

The materializer is deterministic and identified as `phase3-plan-v1`. Its complete input is the owned RecipeVersion identifier; ordered RecipeProcessStep rows; RecipeIngredient rows and their planned-use fields; equipment, calculation, target and tolerance snapshots; legacy-plan classification; and the materialization-rule version. The same normalized inputs and rule version produce the same ordered logical plan, requiredness, measurements, additions, reminders and timing semantics. The materializer never mutates RecipeVersion or its child rows.

##### Normative total-order and predecessor algorithm

`phase3-plan-v1` applies this algorithm exactly:

1. Validate that every RecipeProcessStep has a nonnegative integer `sequence`, a stable UUID, a supported `step_type`, and a structurally valid optional `details.phase3_stage`. A missing/noninteger/negative sequence, duplicate sequence within the RecipeVersion, duplicate source UUID, unsupported type/override, or malformed ordering field fails with `422` before BrewSession creation.
2. Sort explicit source steps by `(sequence ASC, source_uuid ASC)`. The UUID is a deterministic defensive tie-breaker only; duplicate sequence still fails rather than relying on the tie-breaker.
3. Map each source row to one or more canonical stages. Within one source row, `MASH_IN` has expansion rank `0` and its first `MASH` has expansion rank `1`; every other supported source row has expansion rank `0`. Additional explicit `MASH` rows produce only `MASH` and do not create another `MASH_IN`.
4. Validate the mapped explicit rows against the canonical stage ranks in section 6.3. Ignoring equal ranks for planned same-type repeats, canonical rank must never decrease as source `sequence` increases. A decrease is an irreconcilable source order and fails with `422`; the materializer never silently reorders contradictory RecipeVersion intent.
5. Insert required/default/conditional stages from the table below at their canonical stage rank. A default or derived conditional stage is omitted when an explicit mapped step already occupies that semantic stage; qualifying additions attach to the explicit step. Multiple explicit steps at the same rank retain source-sequence order. When no explicit step exists, a derived conditional stage uses the earliest qualifying source/addition UUID as its stable source discriminator.
6. Assign the final total order by `(canonical_stage_rank ASC, source_kind_rank ASC, source_sequence ASC, expansion_rank ASC, planned_same_type_ordinal ASC, stable_source_discriminator ASC)`, where `source_kind_rank` is `EXPLICIT=0`, `DERIVED_CONDITIONAL=1`, `PHASE3_DEFAULT=2`, except that a default at a rank with an explicit row is omitted. Null source sequence for derived/default rows is normalized to `2147483647`; unordered maps, database row order, insertion order and UI order are never inputs.
7. Planned same-type ordinal is contiguous and one-based in the final order for that canonical type. Each plan step except the first has the immediately preceding plan step as its execution predecessor. `BREW_COMPLETE` additionally requires every included required stage to be `COMPLETED` and every included optional stage to be `COMPLETED` or `SKIPPED`. Runtime repeat/return occurrences do not mutate this immutable predecessor graph; their runtime source-transition links are governed by section 6.2.
8. Generate each `plan_step_id` as UUIDv5 using namespace `b3ad9f4c-9e5f-5a31-9df2-25d731f5a302` and name `phase3-plan-v1:{recipe_version_id}:{source_kind}:{stable_source_discriminator}:{planned_same_type_ordinal}`, with lowercase canonical UUID/key components. A BrewSession-specific `stage_instance_id` is a newly generated UUID persisted once for each materialized plan step; repeated reads never regenerate it.
9. Serialize the normalized logical plan with lexicographically sorted object keys, arrays in final total order, canonical lowercase UUIDs, canonical Decimal strings and the `phase3-plan-v1` identifier; store its SHA-256 logical-plan hash. Identical normalized input must produce the identical ordered plan and hash.

Legacy Phase 1A RecipeVersions do not have Phase 2 process sequence data and therefore use the fixed `MASH` then `BREW_COMPLETE` order in the compatibility rules below. There is no inferred ordering from names, timestamps or existing row retrieval order.

Each materialized plan step stores:

- an immutable `plan_step_id` derived deterministically from RecipeVersion ID, materialization-rule version, source kind, stable source ID/default-stage key and planned occurrence;
- canonical stage type, requiredness, predecessor set, planned occurrence, planned duration and clock basis;
- source RecipeProcessStep ID when present, or an explicit `PHASE3_DEFAULT`/`LEGACY_PHASE1A` provenance key;
- all planned measurements, additions and reminders with their stable requirement identities;
- source equipment/calculation/process identifiers and snapshot hashes; and
- the materialization-rule version and UTC materialization time.

Every planned stage receives a distinct `stage_instance_id` scoped to the BrewSession and initially has occurrence number `1` for its `plan_step_id`. Planned repeated source steps receive separate `plan_step_id` values in source order. Runtime repeats use the same source `plan_step_id` and increment occurrence number under a session lock. The uniqueness rule is `(brew_session_id, plan_step_id, occurrence_number)`.

The execution-plan snapshot is immutable as soon as the BrewSession row is created. A failed materialization creates neither the BrewSession nor partial plan rows. Changing recipe/equipment/process data requires a new RecipeVersion and a new BrewSession; an active session never reads mutable live plan data for authority.

##### Phase 2 and legacy mapping rules

| Source condition | Materialized Phase 3 behavior |
|---|---|
| Phase 1A RecipeVersion without Phase 2 equipment/calculation snapshot | Create explicit `LEGACY_MASH_ONLY` plan containing `MASH` and `BREW_COMPLETE`; retain the accepted pH/gravity requirements and legacy completion behavior; fabricate no other stages or observations |
| Phase 2 RecipeVersion with an explicit `MASH` process step | Map the first occurrence to `MASH_IN` followed by `MASH`; additional ordered `MASH` steps create additional planned `MASH` plan steps |
| Phase 2 RecipeVersion with an explicit `BOIL` process step | Map to `BOIL` with its snapshotted duration; duplicate ordered source steps become planned repeated occurrences |
| `FERMENTATION_FOUNDATION` | Preserve source identity only for the `YEAST_PITCH` handoff facts; create no fermentation session, curve, alert or post-pitch stage |
| `PACKAGING_FOUNDATION` | Exclude from the Phase 3 execution plan and record the exclusion in materialization provenance |
| Missing sparse Phase 2 macro stages | Apply the required/default/conditional table below; defaults have `PHASE3_DEFAULT` provenance and do not alter RecipeVersion |
| Unsupported step type or invalid `details.phase3_stage` override | Fail materialization with `422`; identify the source row and unsupported value; create no BrewSession |
| Duplicate source row identity, duplicate source sequence, missing required duration/target, or irreconcilable order | Fail materialization with `422`; create no BrewSession or plan rows |

##### Existing Phase 1A BrewSession compatibility projection

Existing BrewSessions created before migration `0003_phase3_brew_day_os` are not destructively backfilled into new plan/stage history. They are read through the deterministic `legacy-phase1a-session-v1` compatibility projection over their accepted PostgreSQL rows. The projection is authoritative for compatibility presentation and route targeting but never fabricates an observation or rewrites a historical row.

- The existing `BrewSession.id`, `BrewStage.id`, `BrewTimer.id`, Measurement IDs, Notification IDs, BrewJournalEvent IDs and AuditEvent IDs remain unchanged.
- An existing Mash row uses its existing `BrewStage.id` as `stage_instance_id`. If a legacy `PLANNED`/`ACTIVE` session has no Mash row, the projected future Mash identity is UUIDv5 with namespace `b3ad9f4c-9e5f-5a31-9df2-25d731f5a301` and name `legacy-phase1a:stage:{brew_session_id}:MASH:1`; the first compatibility `/mash/start` insert must use that exact ID.
- The legacy Mash `plan_step_id` is UUIDv5 in the same namespace with name `legacy-phase1a:plan:{recipe_version_id}:MASH:1`; occurrence number is `1`; provenance is `LEGACY_PHASE1A`; materialization rule is `legacy-phase1a-session-v1`.
- The compatibility-only `BREW_COMPLETE` plan/instance identities use names `legacy-phase1a:plan:{recipe_version_id}:BREW_COMPLETE:1` and `legacy-phase1a:stage:{brew_session_id}:BREW_COMPLETE:1`. They are deterministic projection identities, not claims that a historical BREW_COMPLETE row existed. A completed legacy session projects BREW_COMPLETE as completed at the accepted session completion time without appending a new historical event.
- Existing session status and Mash status/timestamps control the projection. `PLANNED` remains planned; an accepted started session remains active; a completed Mash/session remains completed. Existing timer, reminder, measurement, deviation and journal relationships stay attached to the existing Mash ID.
- Repeated reads, API/container/PostgreSQL restart, migration retry and `0002 -> 0003 -> 0002 -> 0003` must yield the same projection identities and logical projection hash. Migration creates only the schema/rules required to recognize the legacy projection; it does not insert replacement plan, stage, measurement, reminder or event facts for an existing session.
- Phase 1A `/start`, `/mash/start`, measurement, correction and Mash-completion adapters resolve these identities and call the same Phase 3 services. They cannot create a second Mash identity, alternate business logic, or a runtime repeat. A conflicting pre-existing shape fails closed with a compatibility diagnostic and no rewrite.

##### Required/default/conditional stage table

This table controls `phase3-plan-v1`. “Required” means the stage must complete unless this specification gives a specific legacy exception. “Optional” means it is present by default but may be skipped with a reason. “Conditional” means it is omitted unless its predicate is true; once included it is required.

| Canonical stage | Inclusion and requiredness | Phase 2 source/default | Minimum planned facts |
|---|---|---|---|
| `PRE_BREW` | Required for every nonlegacy Phase 2 plan | Default if absent | Preflight checklist and snapshot receipt |
| `WATER_PREPARATION` | Required for every nonlegacy Phase 2 plan | Explicit step/override or default | Planned liquor/target references; missing required target blocks `READY` |
| `MILLING` | Optional, present for nonlegacy Phase 2 plans with fermentable ingredients | Explicit step/override or default | Ingredient references; skip reason allowed |
| `MASH_IN` | Required when `MASH` is included | Derived from first Mash source/default | Strike/mash-in target and required temperature prompt |
| `MASH` | Required for legacy plans and nonlegacy Phase 2 plans | Explicit Mash source; otherwise default from accepted mash fields | Duration, clock basis, pH/gravity/temperature requirements |
| `LAUTER_SPARGE` | Optional, present for nonlegacy Phase 2 plans | Explicit step/override or default | Planned duration/instruction when known; skip reason allowed |
| `PRE_BOIL` | Required for nonlegacy Phase 2 plans | Default if absent | Pre-boil gravity and volume requirements |
| `BOIL` | Required for nonlegacy Phase 2 plans | Explicit Boil source; otherwise accepted `boil_duration_minutes`; missing duration fails materialization | Duration, clock basis and planned additions |
| `WHIRLPOOL_FLAMEOUT` | Conditional: include when an explicit source step/override or planned `WHIRLPOOL`/zero-minute boil addition exists | Source or derived conditional | Timing basis and planned additions |
| `CHILL` | Required for nonlegacy Phase 2 plans | Default if absent | Knockout target/context when present |
| `TRANSFER` | Required for nonlegacy Phase 2 plans | Default if absent | Receiving-vessel handoff and knockout-volume context |
| `YEAST_PITCH` | Required for nonlegacy Phase 2 plans | Default; may reference fermentation foundation without creating it | Pitch time, pitch temperature and brewer-entered yeast-addition fact |
| `BREW_COMPLETE` | Required terminal projection for every plan | Derived only | CompletionAudit and journal/export readiness |

Preflight validates the complete materialized plan, source ownership, stable ordering, required durations/targets, addition timing, measurement definitions and predecessor graph before `READY`. There is no best-effort plan improvisation: incomplete or contradictory data returns a structured blocking result identifying every failing source/default rule.

### 6.2 Stage states

Required states:

`PENDING -> ACTIVE <-> PAUSED -> COMPLETED`

Exceptional states:

`PENDING -> SKIPPED`

`PENDING | ACTIVE | PAUSED -> ABORTED` **only as an atomic child effect of BrewSession abort**

Rules:

- Stage order comes from the snapshotted execution plan, not hard-coded UI ordering alone.
- Only one primary stage may be `ACTIVE` at a time.
- A stage cannot start before its required predecessor is completed or validly skipped.
- Mandatory stages cannot be skipped. An optional stage requires a reason to skip.
- A stage cannot complete with an unsatisfied required measurement, checklist item, or addition unless an authorized waiver is appended with reason and audit event.
- Completion records actual start, end, active duration, wall-clock duration, actor, and completion result.
- Completed-stage facts are immutable except through append-only correction or annotation records.
- A recipe process step may create more than one stage instance when the process plan permits repetition or an authorized runtime repeat is required. Every instance has its own stable identity, `plan_step_id`, occurrence number, actual chronology, and reason when it was not planned.
- Extending a rest or delaying stage completion appends an extension event and updates the current projection without changing the snapshotted planned duration or prior timing facts.
- Returning to a prior stage is prohibited by default. Every authorized runtime `repeat` or `return` creates a new stage occurrence; Phase 3 has no post-completion continuation model. Extending an `ACTIVE` or `PAUSED` occurrence before completion is the only bounded continuation of that same occurrence.
- `repeat` applies when the source occurrence is the most recently completed primary stage and no later primary stage has started. `return` applies when at least one later primary stage has completed or been skipped. Both require an `ACTIVE` session, a `COMPLETED` source occurrence, no other `ACTIVE` or `PAUSED` primary stage, the expected session revision, a unique operation ID and a nonempty reason. Otherwise return/repeat is `409` with no mutation.
- The command locks the session and all occurrences for the source `plan_step_id`, assigns contiguous `occurrence_number = max(existing occurrence_number) + 1`, creates a new UUID `stage_instance_id`, retains the immutable original `plan_step_id`, and stores `runtime_occurrence_kind` (`REPEAT` or `RETURN`), reason, actor, UTC command time, source completed `stage_instance_id`, and the latest chronological stage from which control moved. The new occurrence becomes the sole authoritative current `ACTIVE` stage. All prior stages and their completion facts remain unchanged.
- A runtime occurrence receives new timer/reminder identities. It copies only requirements explicitly marked repeatable in the snapshotted plan; a single-occurrence requirement or planned addition is not copied implicitly. Any requested copy decision is part of the canonical command and event. Same operation replay returns the same new occurrence; a different operation racing for the same next occurrence conflicts under the session lock/version.
- A measurement or addition recorded after its stage completed may reference the original stage instance only through the late-evidence policy in section 6.8. It preserves `observed_at`, server `recorded_at`, actor, reason, availability-at-completion and current correction/waiver rules. Late evidence never changes the historical stage/session terminal timestamp.
- An invalid backward transition returns `409` and creates no stage, timer, reminder, journal, or audit mutation.
- Commands address `stage_instance_id`, never canonical stage name alone. Human-readable type/name is presentation metadata and cannot select an occurrence.

### 6.3 Required stage vocabulary

Phase 3 must support this canonical ordered vocabulary while allowing a recipe snapshot to omit genuinely inapplicable optional stages:

1. `PRE_BREW`
2. `WATER_PREPARATION`
3. `MILLING`
4. `MASH_IN`
5. `MASH`
6. `LAUTER_SPARGE`
7. `PRE_BOIL`
8. `BOIL`
9. `WHIRLPOOL_FLAMEOUT`
10. `CHILL`
11. `TRANSFER`
12. `YEAST_PITCH`
13. `BREW_COMPLETE`

Recording pitch temperature, pitch time, and brewer-entered yeast-addition facts belongs to Brew-Day OS. Creating a fermentation session, fermentation curve, yeast-reuse lineage, or fermentation alert does not.

### 6.4 Timer states and semantics

Required states:

`PENDING -> RUNNING <-> PAUSED -> COMPLETED`

Deadline path:

`RUNNING -> EXPIRED -> ACKNOWLEDGED | COMPLETED`

Exceptional terminal state:

`PENDING | RUNNING | PAUSED | EXPIRED -> CANCELLED`

Rules:

- Timer truth is persisted server-side using UTC timestamps and accumulated paused duration.
- Client clocks may animate the display but are never authoritative.
- Every timer declares a `WALL_CLOCK` or `ACTIVE_TIME` clock basis. Wall-clock timers continue across workflow pauses; active-time timers pause and resume with their owning stage/session.
- Pausing a session atomically pauses its active stage and all running `ACTIVE_TIME` timers. Resuming restores only timers paused by that session action; a timer that was already manually paused remains paused.
- Timers must recover with consistent state and elapsed/remaining values after refresh, reconnect, API restart, and web-container restart.
- Multiple timers may run concurrently within the same brew session.
- A timer has a type, label, source, planned duration or due time, stage link, and optional addition link.
- Timer start, pause, resume, complete, cancel, due, overdue, and acknowledge actions are idempotent or reject duplication safely.
- Completion of a stage must not silently delete, reset, or complete unrelated timers.
- Deadline passage is deterministically projected from persisted state even before a processor persists `EXPIRED`. Persisting the first expiry fact/event is idempotent. Phase 3 does not require exact background delivery while every client is disconnected.
- PostgreSQL stores timer identity, owner/session and stage links, purpose/type, clock basis, start timestamp, authoritative deadline when applicable, planned duration, accumulated pause, status, revision number, and completion/cancellation timestamps. Redis, worker memory, and the browser cannot be required to reconstruct timer truth.
- Extending a timer is an explicit command that appends a revision containing the former deadline/duration, new deadline/duration, actor, reason, operation identifier, and UTC time. It must not silently rewrite the original timer facts.
- Replacement is allowed only when the original timer can no longer represent the intended operational purpose. Replacement cancels the original with reason and creates a new timer linked by `replaces_timer_id`; it cannot reuse the old identity or erase its events.
- An expired timer discovered after reconnect/restart remains expired according to its authoritative deadline. Delayed processing records processing time separately and must not present stale remaining-time text as current.
- Timer start, extend, complete, cancel, acknowledge, and replace commands, plus idempotent expiry processing, follow the persisted idempotency and optimistic-concurrency contract in section 7.8.

### 6.5 Reminder states and semantics

Required lifecycle:

`SCHEDULED -> DUE -> COMPLETED`

Permitted non-completing/terminal paths:

- `DUE -> ACKNOWLEDGED -> COMPLETED`
- `SCHEDULED | DUE | ACKNOWLEDGED -> SKIPPED`
- `SCHEDULED | DUE | ACKNOWLEDGED -> CANCELLED`
- `DUE | ACKNOWLEDGED -> EXPIRED -> COMPLETED | SKIPPED | CANCELLED`
- `SKIPPED -> COMPLETED` only when valid late evidence supersedes the linked active waiver under section 6.8

Rules:

- Every reminder has a stable identity, owner, BrewSession, stage instance, requirement/action definition, priority, due trigger or UTC due time, status, schema/rule version, and optional measurement/addition/action link.
- `ACKNOWLEDGED` means the brewer saw or accepted the prompt; it does not satisfy a required measurement or action.
- `COMPLETED` requires the associated authoritative Measurement, AdditionEvent, or other allowed action and stores that record's identity as its satisfaction source.
- A required reminder may be skipped or cancelled only when the governing stage rule permits a waiver/cancellation; actor, reason, UTC time, and journal/audit records are mandatory. Required reminders never disappear through projection cleanup.
- Delivery is not authority. Duplicate or delayed deliveries reference the same reminder identity and cannot create another reminder or complete it twice.
- Recording the associated authoritative action and transitioning the correct reminder to `COMPLETED` occur in one transaction. Repeating the same scoped operation returns the original result. A competing action for an already completed reminder returns the authoritative result or a stable `409` without creating a second semantic completion.
- Expiration is deterministic from persisted due state/time. An expired reminder remains visible until completed, validly waived/skipped, or cancelled under an allowed rule.
- A waiver-driven `SKIPPED` reminder stores the Waiver ID as its resolution source. If eligible late evidence supersedes that waiver, the same reminder transitions once to `COMPLETED`, stores the Measurement/AdditionEvent as current satisfaction source, retains the waiver and full state history, and records cause `LATE_EVIDENCE_SUPERSEDED_WAIVER`. Duplicate waiver/evidence commands follow `phase3-operation-v1` and cannot create another reminder or resolution.

### 6.6 Addition schedule semantics

Every planned addition in the BrewSession snapshot declares `timing_basis`, nonnegative `timing_offset_seconds`, `reference_stage_instance_id` when scheduled, `clock_basis`, source provenance and a stable requirement identity. Allowed timing bases are:

- `AT_STAGE_START` — due when the referenced stage becomes `ACTIVE`;
- `FROM_STAGE_START` — due after the offset has elapsed on the declared clock basis;
- `BEFORE_PLANNED_STAGE_END` — due when planned stage duration minus offset has elapsed; runtime extension does not silently move the planned due point;
- `AT_PLANNED_STAGE_END` — due at the original planned end; and
- `UNSCHEDULED` — no timer is invented; the item is visible from stage entry and must be acknowledged, skipped or waived before its governing required stage can complete.

An authorized schedule revision may move a due point only through the timer-revision contract, preserving the original basis/offset/due projection, actor, reason and operation identity. Actual execution stores the planned basis, original/revised projected due instant, actual UTC time, signed delay/earliness, actual ingredient/lot/amount/unit and resolution status.

`phase3-plan-v1` interprets accepted Phase 2 `use_stage` and `timing_minutes` as follows; it never guesses a different meaning:

| Phase 2 source | Phase 3 reference/basis | Validation and default clock basis |
|---|---|---|
| `FIRST_WORT` | `LAUTER_SPARGE` `AT_STAGE_START` | Offset must be null or zero; `WALL_CLOCK` |
| `MASH` with null/zero timing | `MASH` `AT_STAGE_START` | `WALL_CLOCK` |
| `MASH` with positive timing | `MASH` `FROM_STAGE_START` | Offset is `timing_minutes * 60`; must not exceed planned Mash duration unless explicitly marked `UNSCHEDULED`; `WALL_CLOCK` |
| `BOIL` with positive timing | `BOIL` `BEFORE_PLANNED_STAGE_END` | Phase 2 value is boil-contact/minutes-remaining semantics; it must not exceed planned boil duration; due elapsed is `(planned_boil_minutes - timing_minutes) * 60`; `WALL_CLOCK` |
| `BOIL` with zero timing | `BOIL` `AT_PLANNED_STAGE_END` | Represents flameout; `WALL_CLOCK` |
| `WHIRLPOOL` | `WHIRLPOOL_FLAMEOUT` `FROM_STAGE_START` | Null means offset zero; otherwise offset is `timing_minutes * 60`; `WALL_CLOCK` |
| `FERMENTATION`, `DRY_HOP` or `PACKAGING` | Excluded from Phase 3 execution | Preserve source exclusion provenance only; create no post-pitch timer/reminder |
| `MISCELLANEOUS` or an unsupported stage context | `UNSCHEDULED` only when RecipeVersion explicitly marks it as a Brew-Day item and names the governing Phase 3 stage | Otherwise fail materialization with `422` and identify the source addition |

If the referenced stage is absent, duration is missing, timing is negative/out of range, or more than one stage occurrence could satisfy an unqualified reference, materialization fails with `422`. A repeated planned stage must be selected by its `plan_step_id`; runtime repeats copy the source addition only through an explicit repeat decision recorded in the new stage occurrence.

### 6.7 Normative cross-state command effects

Child effects are part of the owning command transaction. No command may delete timer/reminder history. A timer/reminder transition records its prior state, new state, cause, actor, operation ID and UTC time. `continues_after_stage` is a snapshotted Boolean allowed only for a `WALL_CLOCK` timer whose purpose explicitly crosses a stage boundary.

| Operation | Stage/session state | Timer effects | Reminder/addition effects | Required-data effects | Late entry allowed? | Journal | Audit |
|---|---|---|---|---|---|---|---|
| Stage pause | Stage `ACTIVE -> PAUSED`; session remains `ACTIVE` | Pause running stage-owned `ACTIVE_TIME` timers with `paused_by=STAGE_ACTION`; `WALL_CLOCK` timers continue | Active-time due triggers stop accumulating; wall-clock triggers may become due and remain visible | No requirement is satisfied, waived or cancelled | No new normal measurement/addition while the stage is paused; correction/annotation rules in 6.8 still apply | Stage-pause plus one event per changed timer | One command AuditEvent |
| Stage resume | Stage `PAUSED -> ACTIVE` under expected revision | Resume only timers paused by that stage-pause operation; manually paused timers remain paused | Recompute projections; preserve identity and prior acknowledgement | No requirement changes | Normal entry resumes; section 6.8 controls older evidence | Stage-resume plus changed-timer events | One command AuditEvent |
| Stage complete | `ACTIVE -> COMPLETED` after blockers resolve; session remains `ACTIVE` | Complete stage-primary timer; cancel other nonterminal stage timers with cause `STAGE_COMPLETED` unless `continues_after_stage=true` | Required items must already be completed or validly waived; cancel only optional/informational unresolved reminders with cause `STAGE_COMPLETED` | Store which evidence/active waiver satisfied each requirement at completion | Yes, only under completed-stage limits in 6.8; never changes original completion time | Stage completion and every automatic child transition | One command AuditEvent with atomic set |
| Stage cancel (optional-stage skip) | Only an optional `PENDING` stage may become `SKIPPED`; nonempty reason and owner required. No independent active-stage cancel exists | Cancel nonterminal timers owned only by that stage with cause `STAGE_SKIPPED` | Optional unresolved reminders/additions become `SKIPPED`; required items must have an eligible active waiver first | Waivers remain explicit; no measurement/addition is fabricated | Only correction/annotation rules in 6.8; no new skipped-stage execution evidence | Skip, waiver and child-transition events | One command AuditEvent plus waiver audit facts |
| Requirement waiver | Stage remains `PENDING`, `ACTIVE` or `PAUSED`; append Waiver under the policy below | Cancel only a timer dedicated solely to that requirement with cause `REQUIREMENT_WAIVED` | Target reminder/addition becomes `SKIPPED` with Waiver ID; other reminders unchanged | Requirement is `WAIVED`, never `MEASURED`/`EXECUTED` | Eligible late evidence may supersede the waiver under 6.8 | Waiver plus affected child event | One command AuditEvent |
| Session pause | Session `ACTIVE -> PAUSED`; active stage `ACTIVE -> PAUSED` atomically | Pause all running `ACTIVE_TIME` timers with `paused_by=SESSION_ACTION`; `WALL_CLOCK` timers continue | Active-time triggers stop; wall-clock reminders may become due and remain visible | No satisfaction/waiver/cancellation | No normal execution entry while paused; correction/annotation rules in 6.8 apply | Session/stage/timer facts | One command AuditEvent |
| Session resume | Session `PAUSED -> ACTIVE`; restore only the stage paused by that session action | Resume only timers automatically paused by that session action | Reproject persisted reminders; preserve manual states | No requirement changes | Normal entry resumes | Session/stage/timer facts | One command AuditEvent |
| Session abort | `PLANNED`, `READY`, `ACTIVE` or `PAUSED -> ABORTED`; every nonterminal stage -> `ABORTED`; confirmation and reason required; never resumable | Every nonterminal session timer -> `CANCELLED` with cause `SESSION_ABORTED`; retain deadlines, elapsed state and history | Every unresolved reminder/addition -> `CANCELLED` with cause `SESSION_ABORTED`; no waiver is fabricated | Outstanding requirements remain unresolved/not completed in CompletionAudit | No new measurement/addition; corrections/annotations only under aborted-session limits in 6.8 | Abort, each automatic child transition and deterministic aborted journal/CompletionAudit projection; rendering may regenerate | One atomic security AuditEvent |
| Session complete | `ACTIVE -> COMPLETED` only after mandatory stages and required items satisfy policy; never resumable | No required timer may remain nonterminal; optional nonterminal timers -> `CANCELLED` with cause `SESSION_COMPLETED` | Required reminders/additions completed or validly waived; optional unresolved items cancelled and visible | Freeze availability-at-completion and satisfaction source; waiver never counts as measurement | Bounded late evidence/corrections/annotations only under completed-session limits in 6.8 | Completion, CompletionAudit identity and child events atomically; rendering/export derived | One command AuditEvent |

There is no separate `CANCELLED` stage state or stage-cancel API. “Stage cancel” means the optional `PENDING -> SKIPPED` operation above. Stage `ABORTED` can be produced only by BrewSession abort. An `ACTIVE` or `PAUSED` stage cannot be cancelled or skipped while its session continues; the brewer must resume and complete it, or abort the BrewSession. Session abort is terminal failure/interruption evidence and never masquerades as successful completion.

##### Normative waiver policy (`phase3-waiver-v1`)

A Waiver is an append-only authorization record, not a Measurement, AdditionEvent, reminder acknowledgement, stage skip/cancel, correction or fabricated observation.

- The authenticated BrewSession owner is the only Phase 3 waiver actor; delegated roles are not introduced. The command requires an operation ID, expected session revision and a reason of 10 through 1,000 Unicode characters.
- Waivable requirements are brewer-observation measurements, planned additions that were not performed or cannot be verified, optional-stage checklist items, and informational/operational acknowledgements explicitly materialized with `waivable=true`.
- Never-waivable requirements are ownership/authentication, immutable RecipeVersion/plan identity, preflight integrity, ordering/predecessor rules, concurrency/idempotency controls, mandatory-stage completion itself, BrewSession terminal transition rules, the actual yeast-pitch timestamp and brewer-entered yeast-addition handoff fact, and any requirement materialized with `waivable=false`. A nonwaivable waiver request is `409 WAIVER_PROHIBITED` with no mutation.
- A waiver is allowed only while the session is `ACTIVE` and the associated stage is `PENDING`, `ACTIVE` or `PAUSED`, before the requirement has authoritative satisfaction evidence and before stage/session completion. It stores owner, session, stage instance, stable requirement identity, requirement kind, reason, actor, UTC time, operation ID, status and optional superseding-evidence ID.
- Initial status is `ACTIVE`. Same operation replay returns the same Waiver. A different operation for an already active waiver returns that Waiver or `409` and creates no second active waiver. A waiver cannot be edited or deleted.
- An active waiver makes only its target requirement eligible for stage completion and moves its reminder/addition resolution to waiver-driven `SKIPPED`; it never counts as a recorded measurement or executed addition.
- Eligible late evidence under section 6.8 changes the waiver projection to `SUPERSEDED_BY_EVIDENCE` by appending a supersession event/reference. The Waiver remains historical evidence; the same reminder becomes `COMPLETED` with the real evidence as current satisfaction source; current CompletionAudit/comparison uses the valid evidence and records that it was unavailable at original completion. The original completion decision and timestamp are not rewritten.

### 6.8 Late evidence and terminal-session policy

All time limits below use authoritative UTC. `recorded_at` is always server-assigned. User-supplied `observed_at` may not be more than five minutes in the future relative to server receipt and must match the declared process-point/stage chronology. Every late-evidence command requires the owner, a unique operation ID, expected session revision where the session remains nonterminal, and a reason of 10 through 1,000 Unicode characters. It stores `late_entry=true`, actor, reason, intended process point, `stage_instance_id`, `observed_at`, `recorded_at`, entry source, correction lineage where applicable, and `available_at_original_stage_completion`/`available_at_original_session_completion` Booleans.

| Late-evidence class | Allowed states and fixed boundary | Deterministic effect |
|---|---|---|
| Measurement after stage completion, session `ACTIVE` | Target stage `COMPLETED`; submit no later than 24 hours after `stage.completed_at`; `observed_at` from stage start minus five-minute skew through stage completion plus five-minute skew | Append Measurement; update current effective comparison/reminder/waiver projection; preserve original stage completion and mark evidence unavailable at completion |
| Addition after stage completion, session `ACTIVE` | Target stage `COMPLETED`; submit no later than 24 hours after `stage.completed_at`; actual execution time no later than 24 hours after stage completion and not future beyond five-minute skew | Append actual AdditionEvent/deviation; update reminder/waiver projection; preserve planned schedule and stage completion |
| Measurement/addition after session `COMPLETED` | Submit no later than 24 hours after `session.completed_at`; target stage must already exist and be `COMPLETED`; measurement observation window is that stage's start through completion plus five-minute skew; addition actual time may be no later than 24 hours after its stage completion | Append evidence only; never create a stage/timer or change terminal time; regenerate current CompletionAudit/journal projection while retaining the original completion snapshot and `available_at_original_session_completion=false` |
| New measurement/addition after session `ABORTED` | Prohibited | Return `409 TERMINAL_SESSION_EVIDENCE_PROHIBITED`; create no operation/domain/journal/audit mutation beyond the safe conflict audit policy |
| Correction of an existing measurement/addition | Nonterminal at any time; `COMPLETED` or `ABORTED` no later than 30 calendar days after terminal time | Append correction linked to existing evidence; preserve raw/original and terminal facts; current projection uses latest valid chain member and records post-terminal availability |
| Note/annotation | Nonterminal at any time; `COMPLETED` or `ABORTED` no later than seven calendar days after terminal time | Append timestamped annotation explicitly labeled post-terminal when applicable; never changes structured requirement satisfaction |
| Media attachment | Nonterminal `ACTIVE` only | No new upload after `COMPLETED` or `ABORTED`; existing attachment retrieval, unavailable-media projection and reconciliation continue under section 7.6 |
| Journal/CompletionAudit regeneration | Any state, no expiry | Read-only deterministic projection; no BrewJournalEvent or domain mutation |

After `COMPLETED` or `ABORTED`, the plan snapshot, RecipeVersion reference, original stage/session states and timestamps, timers, occurrences and preterminal events are immutable. Prohibited actions include start/resume, new normal stages or runtime occurrences, timer start/restart/extension, new waiver, attachment upload/removal that would erase evidence, plan rewrite, RecipeVersion reassignment and inventory mutation. Allowed actions are only those append-only rows in the table within their stated windows plus read/retrieval/regeneration. Expired windows return `409 LATE_ENTRY_WINDOW_CLOSED` without reserving a successful operation result or mutating domain/journal state.

## 7. Functional requirements

Each `P3-FR` requirement is mandatory unless explicitly labeled conditional.

### 7.1 Session planning and snapshots

- **P3-FR-001:** Create a brew session only from an owned immutable recipe version.
- **P3-FR-002:** Snapshot all execution-relevant recipe, equipment, calculation, target, tolerance, process-step, and planned-addition data at session creation.
- **P3-FR-003:** Later recipe, equipment, ingredient, or calculation changes must not alter the session snapshot.
- **P3-FR-004:** Preflight must identify missing required plan data before the session becomes `READY`.
- **P3-FR-005:** The UI must show the plan source, snapshot time, units, assumptions, required observations, and blocking preflight failures.
- **P3-FR-006:** Phase 1A sessions and Phase 2 recipe versions must remain readable. Migration/backfill behavior must be explicit and tested.
- **P3-FR-007:** Existing accepted Phase 1A brew-session routes remain compatible. A legacy `/start` request may perform validated `PLANNED -> READY -> ACTIVE` transitions atomically, and `/mash/start` must map to the canonical Mash stage without bypassing Phase 3 invariants.
- **P3-FR-008:** Existing Mash-only sessions use an explicit legacy plan kind and remain completable under their original accepted requirements; migration must not fabricate unobserved stages or measurements.
- **P3-FR-009:** Materialize the complete immutable execution-plan snapshot under section 6.1.1 in the same transaction as BrewSession creation. `phase3-plan-v1` mapping, defaulting, ordering, requiredness, provenance and failure behavior are normative; the same normalized source and rule version must produce the same logical plan.
- **P3-FR-090:** Apply the normative total-order/predecessor algorithm in section 6.1.1. Contradictory, duplicate, missing, malformed or unsupported order input fails atomically; database/insertion/UI order is never authority.
- **P3-FR-091:** Existing Phase 1A BrewSessions use `legacy-phase1a-session-v1` exactly. Compatibility identities, status/timestamp projection, existing relationships and route targeting remain stable across repeated reads, migration round trips and restarts without destructive historical backfill.

### 7.2 Stage-aware worksheet

- **P3-FR-010:** Render the current stage, completed history, upcoming stages, blockers, required actions, planned values, and actual values.
- **P3-FR-011:** Enforce transitions server-side; disabling a UI control is not enforcement.
- **P3-FR-012:** Support required/optional stage definitions and explicit, reasoned skip or waiver records.
- **P3-FR-013:** Preserve both planned order and actual execution chronology.
- **P3-FR-014:** Support session and stage pause/resume without losing timing history and apply the exact child-state effects in section 6.7 atomically.
- **P3-FR-015:** Abort must require confirmation and reason, preserve completed and unresolved history, and apply the exact session/stage/timer/reminder/addition effects in section 6.7 atomically.
- **P3-FR-016:** Support planned and authorized runtime repetition of a process step through separately identified stage instances; preserve the snapshotted plan, occurrence order, actual chronology, and repeat reason.
- **P3-FR-017:** Support a stage/rest extension without changing its planned duration. Preserve every former timing fact and the actor, reason, and operation that extended it.
- **P3-FR-018:** Support bounded late measurement/addition entry against the correct stage instance with observed and recorded times. Do not reopen a completed stage or rewrite its completion history implicitly.
- **P3-FR-019:** Reject unrestricted backward transitions. A controlled repeat/return always creates the exact new occurrence defined in section 6.2 with optimistic concurrency and journal/audit evidence; it never reopens or continues a completed occurrence.
- **P3-FR-092:** Distinguish repeat from return, allocate contiguous occurrence numbers under the session lock, preserve `plan_step_id`, create a new `stage_instance_id`, and reject a return while another primary stage is active/paused or the source/session state is ineligible.
- **P3-FR-093:** Implement the section 6.7 cancellation/abort model: optional pending-stage skip is the only independent stage cancellation, stage `ABORTED` is session-abort-only, and session abort is confirmed, reasoned, atomic, terminal, nonresumable and historically preserving.
- **P3-FR-094:** Implement `phase3-waiver-v1`, including explicit waivable/nonwaivable classes, owner authorization, immutable reasoned records, idempotency, reminder effects, completion meaning and deterministic late-evidence supersession.

### 7.3 Timers, additions, and reminders

- **P3-FR-020:** Support at least three concurrent persisted timers in one browser acceptance scenario.
- **P3-FR-021:** Generate hop and other addition timers from snapshotted recipe process/addition schedules using the exact timing bases, Phase 2 compatibility mapping and validation rules in section 6.6.
- **P3-FR-022:** Show due and overdue timers without relying on a continuously open browser tab.
- **P3-FR-023:** Acknowledge an addition with planned due basis/offset/instant, actual time, actor, optional actual quantity, canonical unit, signed timing variance, and note.
- **P3-FR-024:** A missed, late, early, changed, skipped, unscheduled, or extra addition must produce an explicit deviation or exception event from the snapshotted schedule semantics; it must not rewrite the plan.
- **P3-FR-025:** Required-data reminders must identify the requirement, stage, due basis, status, and satisfaction source.
- **P3-FR-026:** Reminder acknowledgement alone cannot satisfy a required measurement.
- **P3-FR-027:** In-app reminders are required. Email, SMS, push notifications, and production job infrastructure are out of scope.
- **P3-FR-028:** Reminder state must implement section 6.5, including stable identity, priority, delivery-independent authority, and reasoned skip/cancel/expiry behavior. Required reminders remain visible and auditable until resolved.
- **P3-FR-029:** Creating an authoritative measurement/addition/action and satisfying its unique reminder must be atomic and idempotent. Two tabs, retries, and duplicate delivery cannot complete the reminder or create the action twice.

### 7.4 Measurements and validation

- **P3-FR-030:** Support, at minimum, the distinct process-point definitions in the measurement table below. `POST_MASH_GRAVITY`, `PRE_BOIL_GRAVITY`, and `ORIGINAL_GRAVITY` are different observation types even when all use `SG`; knockout and pitch temperature are also distinct process points.
- **P3-FR-031:** A measurement must store definition/rule version, type, process point, stage instance, raw Decimal value/unit, canonical Decimal value/unit, observed-at UTC time, server-recorded-at UTC time, actor, entry method, required method/context fields, optional instrument reference, validation status, correction lineage and provenance.
- **P3-FR-032:** Unit, context and plausible-range validation must occur at the API boundary and domain/application layer. PostgreSQL constraints protect type/unit/status domains, required context shape and lineage where expressible; type-specific cross-field rules remain deterministic domain checks with PostgreSQL integration proof.
- **P3-FR-033:** Temperature measurements persist canonical `degC` plus original scale/value when converted. Gravity persists canonical `SG`, raw scale/value, method and any accepted conversion/correction model ID. Volume persists canonical liters, vessel/basis, sample temperature when applicable and any reference-temperature correction/model. A derived correction never replaces the raw observation.
- **P3-FR-034:** Corrections append a linked replacement and reason; no measurement update or deletion path may bypass history.
- **P3-FR-035:** Completion requirements use the latest valid measurement in a correction chain while retaining the entire chain.
- **P3-FR-036:** Measurement timestamps may be back-entered only within the exact five-minute/24-hour/terminal-state bounds in section 6.8 and must preserve both observation and recording times.
- **P3-FR-037:** A required measurement may be waived only with explicit reason, actor, timestamp, and journal/audit event. A waiver is visibly different from a measurement.
- **P3-FR-038:** `observed_at` is the brewer-supplied or device-local observation instant subject to bounded validation; `recorded_at` is assigned by the authoritative server on receipt. Store entry source/method and retain both in the journal. Client clock skew or delayed entry must not silently rewrite either instant.
- **P3-FR-039:** A repeated submission with the same operation identity returns the original Measurement and reminder result. A genuinely distinct repeat observation receives a new identity; similar value/time alone is never used for silent deduplication.
- **P3-FR-095:** Enforce every numeric/lifecycle window and state rule in section 6.8 for measurements, additions, corrections, annotations and media. Late evidence stores both availability-at-completion flags and can update only current derived projections, never original terminal facts.

#### Required measurement-definition table (`phase3-measurement-v1`)

Instrument identity is optional in Phase 3, but the method and context marked below are required. This captures interpretable evidence without implementing Phase 5 calibration schedules or validity management.

| Measurement type | Required stage/process point | Canonical unit | Required method/context | Hard validation |
|---|---|---|---|---|
| `MASH_IN_TEMPERATURE` | `MASH_IN`; immediately after mash-in equilibration | `degC` | Method (`THERMOMETER`/`PROBE`/`OTHER`), original value/scale | `-10 <= degC <= 120` |
| `MASH_REST_TEMPERATURE` | `MASH`; named rest/occurrence and elapsed offset | `degC` | Method, original value/scale, rest `stage_instance_id` | `-10 <= degC <= 120` |
| `MASH_PH` | `MASH`; named elapsed/sample point | `pH` | Method (`METER`/`STRIP`/`OTHER`), sample temperature `degC`, temperature-compensated flag; optional instrument | `0 <= pH <= 14`; operational range warnings do not rewrite value |
| `POST_MASH_GRAVITY` | End of Mash before lautering/sparging dilution | `SG` | Method (`HYDROMETER`/`REFRACTOMETER`/`OTHER`), raw scale/value, sample temperature when method is temperature-sensitive, conversion model if converted | `0.900 <= SG <= 1.300` |
| `PRE_BOIL_GRAVITY` | Kettle after runnings are combined and before boil starts | `SG` | Same gravity context; vessel=`KETTLE` | `0.900 <= SG <= 1.300` |
| `PRE_BOIL_VOLUME` | Kettle immediately before boil | `L` | Vessel=`KETTLE`, measurement method, liquid temperature, raw/canonical basis, reference temperature and model if corrected | `L > 0` and within the snapshotted equipment/plan plausibility bound |
| `ORIGINAL_GRAVITY` | Homogenized post-boil wort after chilling and before yeast pitch | `SG` | Same gravity context; `POST_BOIL_GRAVITY` may be a display alias only and cannot be a second ambiguous authority type | `0.900 <= SG <= 1.300` |
| `KNOCKOUT_VOLUME` | Wort delivered into the receiving vessel after transfer and before pitch | `L` | Receiving-vessel identity/type, method, liquid temperature, raw/canonical basis and correction model if used | `L > 0` and within the snapshotted equipment/plan plausibility bound |
| `KNOCKOUT_TEMPERATURE` | Receiving vessel at transfer completion before pitch preparation | `degC` | Method, original value/scale, receiving-vessel context | `-10 <= degC <= 120` |
| `PITCH_TEMPERATURE` | Immediately before the brewer records yeast addition/pitch handoff | `degC` | Method, original value/scale; distinct observed time even when equal to knockout temperature | `-10 <= degC <= 120` |

The equipment/plan plausibility bound for volume is snapshotted and rule-versioned before `READY`; if the accepted equipment profile lacks a physical-capacity field, `phase3-measurement-v1` uses `max(10 L, 3 * snapshotted total_liquor_liters)` as the hard upper bound and records that fallback. Values inside hard bounds but outside operational targets are preserved with warning/deviation status. Values outside hard bounds are rejected. Late entry preserves the original process point and both timestamps; it never changes a `POST_MASH_GRAVITY` into `PRE_BOIL_GRAVITY` by timing alone.

### 7.5 Planned versus actual and deviations

- **P3-FR-040:** Comparison calculations use Decimal and live in the deterministic calculation/domain layer, never React or an LLM.
- **P3-FR-041:** Persist or reproducibly derive target, actual, signed variance, tolerance, result, unit, calculation/model identity, and source observation.
- **P3-FR-042:** Persist or derive the explicit comparison tuple `planned value`, `actual value`, signed `delta`, `unit`, `tolerance`, and `status`. Distinguish `WITHIN_TOLERANCE`, `OUTSIDE_TOLERANCE`, `MISSING`, `NOT_APPLICABLE`, `NO_TARGET`, `WAIVED`, and `NOT_RECORDED` truthfully. Do not calculate or display a delta when its operands/units do not support one, and do not imply precision beyond the accepted model/input precision.
- **P3-FR-043:** Permit an operational deviation unrelated to a numeric measurement, with category, description, stage, time, and optional corrective action.
- **P3-FR-044:** Correcting an observation must not erase the original deviation history; the current effective comparison and prior superseded comparison must remain explainable.
- **P3-FR-045:** Corrective-action text is brewer-authored deterministic workflow content in Phase 3. AI diagnosis is prohibited.
- **P3-FR-046:** Addition execution records must preserve planned addition identity, planned ingredient/time/amount/unit, actual ingredient identity, actual lot when known, actual time/amount/unit, execution status, and any accepted Phase 2 substitution reference. Acknowledgement has no Phase 3 inventory-ledger effect and never mutates RecipeVersion intent.
- **P3-FR-047:** Addition schedule materialization and execution must implement section 6.6. An ambiguous or invalid Phase 2 schedule fails before `READY`; a runtime revision is append-only; and future-phase additions are excluded without creating post-pitch workflow.

### 7.6 Notes, photos, and journal

- **P3-FR-050:** Add, read, and append-correct timestamped session/stage notes of at most 4,000 Unicode characters without overwriting completed history.
- **P3-FR-051:** Upload authenticated image attachments under the normative media-control table below with allowlisted MIME/signature, fixed size/count/quota, generated storage identifiers, checksum, bounded original filename metadata, actor, and UTC timestamp.
- **P3-FR-052:** Reject executable, mismatched, oversized, and unauthorized files. User-controlled filenames must not become storage paths.
- **P3-FR-053:** Store attachment metadata in PostgreSQL and bytes behind the existing file/object-storage abstraction or a bounded local-development implementation; database paths must not expose server filesystem layout.
- **P3-FR-054:** Attachment deletion before session completion must be an audited soft removal. Completed-session attachment evidence cannot be silently deleted.
- **P3-FR-055:** The journal must automatically include session/stage transitions, timer lifecycle, reminders, measurements/corrections/waivers, deviations, addition acknowledgements, notes/media metadata, and completion/abort.
- **P3-FR-056:** Journal chronology must be stable, paginatable, ownership-scoped, and based on authoritative UTC event timestamps plus deterministic tie-breaking.
- **P3-FR-057:** Export a human-readable brew-day summary and a machine-readable JSON representation without introducing a general reporting platform.
- **P3-FR-058:** A failed, timed-out, or retried media operation cannot mutate or block session/stage/timer/reminder/measurement authority. Upload uses a stable operation identity; ambiguous retry is idempotent; orphan bytes/metadata are detected and reconciled. Journal/export renders an explicit unavailable-media reference when bytes cannot be read.
- **P3-FR-059:** Completion must produce a deterministic, rule-versioned Brew-Day CompletionAudit projection containing required recorded/waived/missing counts, unresolved reminders/deviations/additions, timer states, lineage and journal integrity, and outstanding issues. A waiver or `NOT_RECORDED` result never counts as a measured value or inflates measurement completeness.

#### Normative private/local media and resource controls

| Control | Phase 3 requirement |
|---|---|
| Allowed image types | JPEG (`image/jpeg`), PNG (`image/png`) and WebP (`image/webp`) only; declared MIME, magic signature and successful bounded decoder probe must agree |
| Per-file limit | 10 MiB of received bytes; reject before metadata finalization with `413` |
| Per-session limit | 20 nonremoved attachments and 100 MiB total retained bytes; deterministic `409 ATTACHMENT_QUOTA_EXCEEDED` without affecting core Brew-Day state |
| Metadata bounds | Original filename is metadata only, normalized for display and limited to 255 Unicode characters; caption/description is limited to 1,000 characters; neither becomes a path or response header value |
| Storage identity | Server-generated UUID/opaque key; storage path is constructed only from trusted server components; SHA-256 checksum and byte length are stored in PostgreSQL |
| Retrieval | Authenticated owner-scoped API lookup on every request; `X-Content-Type-Options: nosniff`, exact validated MIME and safe generated `Content-Disposition` filename; no filesystem path disclosure |
| Executable/active content | SVG, HTML, XML, scripts, archives, polyglots, MIME/signature mismatch and failed decode are rejected with `415`/`422` and no authoritative attachment row |
| Upload transaction | Stable operation ID reserves intent; bytes are written to a temporary generated key, checksum/decoder validated, final key promoted, then metadata finalized idempotently. Core session commands never share this transaction |
| Failed/ambiguous upload | Retry follows `phase3-operation-v1`; no duplicate bytes/metadata; failure cannot roll back or block measurements, timers, reminders, optional stage completion or BrewSession state |
| Orphan handling | Temporary/unreferenced bytes are nonauthoritative and reconciled within 24 hours; reconciliation is owner-safe, metrics/logged and never deletes bytes referenced by live metadata |
| Removal/retention | Pre-completion removal is audited soft removal. Completed-session metadata/bytes follow BrewSession evidence retention and cannot be silently deleted; backup/isolated restore must cover both |
| Unavailable bytes | Journal/export retains metadata/checksum and renders explicit `MEDIA_UNAVAILABLE`; generation remains successful and does not invent content |

Human-command abuse bounds for the private single-user Phase 3 runtime are 120 non-upload mutations per authenticated user per rolling minute and 10 upload attempts per minute, with a bounded burst of 20. Exceeding a bound returns `429` with `Retry-After` and no domain mutation. Timer display polling uses `GET`, not mutation. These controls are application/API protections; they do not make Redis authoritative and do not authorize public exposure.

### 7.7 Voice-assisted entry boundary

- **P3-FR-060:** Voice entry is conditional on browser capability and permission; the full workflow must remain usable manually.
- **P3-FR-061:** A transcript or parsed candidate is untrusted draft input and must not create a measurement, note, timer action, addition, or transition.
- **P3-FR-062:** The UI must show the parsed field, value, unit, and target action for explicit brewer confirmation.
- **P3-FR-063:** Confirmed voice candidates pass through the identical API authorization, unit, range, state, and duplicate validation as manual entry.
- **P3-FR-064:** Persist `VOICE_CONFIRMED` only as entry-method provenance after successful confirmation. Do not persist ambient audio by default.
- **P3-FR-065:** No always-listening mode, cloud speech service, speaker identity, voice biometric, autonomous command execution, or AI conversational assistant is permitted.
- **P3-FR-066:** The normative sequence is voice input -> transcription -> parsed proposal -> explicit user confirmation -> ordinary domain/API validation -> authoritative commit. A transcript such as “five point two” parsed as `52` must remain uncommitted and fail range validation unless the brewer corrects and confirms the proposed value.

### 7.8 Recovery and concurrency

- **P3-FR-070:** `GET` recovery must return the complete current session projection needed to resume safely without reconstructing authority from browser storage.
- **P3-FR-071:** Refresh, navigation away/back, logout/login, API restart, and web restart must preserve authoritative progress.
- **P3-FR-072:** Mutating commands must use the persisted client-operation/idempotency contract in P3-FR-076 for double-clicks, retries, unknown HTTP responses, reconnect, and multi-tab submission.
- **P3-FR-073:** Stale concurrent commands must not advance a session twice or create duplicate measurements/additions/events. Use a persisted version or equivalent optimistic concurrency control.
- **P3-FR-074:** The UI must surface a conflict and refresh authoritative state rather than silently overwrite newer work.
- **P3-FR-075:** Redis and browser local storage may improve delivery or presentation but cannot own session, timer, reminder, or journal truth.
- **P3-FR-076:** Every retryable mutation uses the PostgreSQL-backed idempotency contract below under an actor + use case + aggregate scope. Same identifier and canonical request fingerprint returns the prior result; same identifier with a different fingerprint returns `409` and creates no mutation.
- **P3-FR-077:** Order-sensitive commands include the expected aggregate/timer revision. Exactly one concurrent transition/revision may succeed; stale commands return current version/recovery data without a second semantic action.
- **P3-FR-078:** Each command atomically commits its authoritative state change, associated timer/reminder/action record, BrewJournalEvent, and required AuditEvent. A failure before commit rolls back all of them. Notification delivery and journal rendering/export are derived effects and cannot roll back an already committed Brew-Day command.
- **P3-FR-079:** Recovery must be correct after browser close/reopen, device sleep, network loss or unknown response, API restart, PostgreSQL restart/rollback, Redis loss, delayed/duplicate delivery, and reconnect after a deadline. A worker-restart test is required only if Phase 3 actually introduces/uses a worker; otherwise evidence must show the scenario is not applicable and no authority depends on one.

#### PostgreSQL-backed idempotency contract (`phase3-operation-v1`)

- Clients send a unique operation identifier as a UUIDv4 or ULID-compatible ASCII value of at most 64 characters. The server never derives it from mutable UI text.
- Scope is the immutable tuple `(actor_user_id, use_case, aggregate_type, aggregate_id, operation_id)`. A key is never shared across owners, sessions, command families or aggregate identities.
- After authentication and schema validation, the server constructs a canonical command document containing command-schema version, path aggregate identity and every semantic field with server-defined defaults applied. Object keys sort lexicographically; arrays retain order unless the command schema explicitly defines set semantics; UUIDs are lowercase canonical text; UTC instants use RFC 3339 `Z` form at microsecond precision; Decimal values use canonical non-exponent decimal strings with insignificant trailing zeros removed; and omitted versus explicit null are equivalent only where the versioned schema declares the same default. Transport-only headers, JSON whitespace and object-key order are excluded.
- The server stores SHA-256 of the canonical UTF-8 document, command-schema version, scope, creation/terminal times, HTTP/result status, resulting resource identity/version and enough immutable response data to replay or reconstruct the authoritative result.
- Full result data remains while the BrewSession is nonterminal and for at least 90 days after `COMPLETED`/`ABORTED`. An immutable tombstone containing scope, fingerprint and result resource reference remains for the life of the BrewSession evidence. Cleanup cannot make an old key eligible for a new mutation.
- Same scope/key/fingerprint returns the original authoritative result and marks the response as replayed. Same scope/key with a different fingerprint returns `409 IDEMPOTENCY_KEY_REUSED` and creates no domain, journal or audit mutation other than the safe conflict audit policy.
- After full-result retention expires, same fingerprint reconstructs the result from authoritative records or returns `410 IDEMPOTENT_RESULT_ARCHIVED` with the stable resource reference; it never executes again. A different fingerprint still returns `409` from the tombstone.
- A different key with a semantically duplicate single-occurrence action is governed by domain uniqueness and expected revision: it returns the existing authoritative result where the command defines that behavior or stable `409`; repeatable observations require an explicit repeat-capable requirement and otherwise conflict.
- Commit and operation-result persistence are one PostgreSQL transaction. If the commit succeeds but the HTTP response is lost, retry returns the stored result. If the transaction rolls back, no operation success/tombstone or partial domain/event row remains.

This contract applies at minimum to measurement creation/correction, action-linked reminder completion, timer creation/revision/cancellation, stage repeat/return/extension/completion, addition execution/skip, deviation creation, media metadata finalization, and BrewSession abort/completion. It uses no distributed lock, event broker, outbox or Redis authority.

### 7.9 Security, ownership, and audit

- **P3-FR-080:** Every identifier lookup and mutation is ownership-scoped server-side.
- **P3-FR-081:** A second authenticated user cannot infer, read, modify, upload to, or transition another user's session or attachment.
- **P3-FR-082:** Audit records must cover state changes, waivers, corrections, attachment removal, and other security-relevant commands.
- **P3-FR-083:** Logs must include correlation/request identifiers and safe entity identifiers without secrets, raw audio, or unnecessary measurement/note contents.
- **P3-FR-084:** No route added by Phase 3 may be public.
- **P3-FR-085:** BrewJournalEvents are typed, append-oriented operational facts with schema version, session/stage identity, occurred and server-recorded UTC times, actor/source, operation identity, correlation/causation identifiers, and validated payload. They are not security/governance AuditEvents.
- **P3-FR-086:** The human-readable journal and exports are deterministic projections of BrewJournalEvents and linked authoritative records. They are never independently writable. Rendering/generation failure does not roll back Brew-Day state; regeneration is idempotent and creates no operational event.
- **P3-FR-087:** Phase 3 metrics and correlated logs must expose timer processing/display lag, recovery outcome, command conflict/deduplication, reminder satisfaction, journal generation failure, and media reconciliation without logging secrets or unrestricted measurement/note contents. Acceptance must reconstruct one simulated Brew-Day failure from this evidence.
- **P3-FR-088:** Phase 3 must meet the normative private-runtime performance profile and p95 thresholds below on the recorded reference class. Acceptance records raw samples and actual percentiles; “appears responsive” is not evidence.
- **P3-FR-089:** Phase 3 state-changing browser requests implement the synchronizer-token and same-origin CSRF contract below. `SameSite=Lax` and private binding remain defense in depth, not the sole mutation defense.
- **P3-FR-096:** Enforce the post-`COMPLETED` and post-`ABORTED` allowlist in section 6.8 server-side. Every nonallowlisted mutation and every expired late-entry window fails without normal domain/journal mutation; journal/CompletionAudit regeneration remains read-only and idempotent.

#### Phase 3 CSRF disposition

Phase 3 selects an architecture-consistent synchronizer-token control. After login, the server generates at least 256 bits of randomness, stores only a secret-salted digest bound to the authenticated server session, and returns the token through an authenticated same-origin bootstrap response. The browser sends it in `X-CSRF-Token` for every `POST`, `PUT`, `PATCH` and `DELETE`, including legacy compatibility mutations and logout. Tokens rotate on login/session rotation, are never accepted in a URL, never logged, and expire with the auth session.

For browser requests the API also requires an exact configured same-origin `Origin`; when a user agent legitimately omits `Origin`, an exact same-origin `Referer` is required. Missing/mismatched origin or token returns `403` before command/idempotency persistence and creates no domain mutation. Login applies the same origin check to prevent login CSRF. Non-browser administrative clients are not introduced by Phase 3; any future alternative authentication/CSRF profile requires separate security review.

Phase 3 remains bound to the accepted private/local development trust boundary. No public route, tunnel, DNS, remote exposure or NAS production deployment is authorized. TLS, secure cookies, rotated production secrets, external-access controls and deployment-specific CSRF review remain separate NAS deployment gates even after this Phase 3 control passes.

#### Normative private-runtime performance profile

The reference class is a production-build disposable environment with PostgreSQL, API and web containers on SSD-backed storage, at least 4 logical x86-64 CPU cores and 8 GiB available RAM, and a private LAN/browser round-trip baseline no greater than 10 ms. The evidence records exact CPU, RAM, storage, OS/container runtime, browser and measured baseline latency. This is local acceptance evidence, not NAS production evidence.

The representative active BrewSession contains 13 canonical plan steps plus three repeated stage occurrences, 10 simultaneous timers, 20 reminders, 100 measurements/corrections, 100 planned/actual additions, 50 notes, metadata for 20 attachments, and 750 BrewJournalEvents. Attachment bytes are not eagerly loaded by the dashboard. Two authenticated browser tabs exercise the same session.

After 10 warm-up iterations, collect at least 100 successful samples per API operation and 30 browser navigation/recovery samples. Measure server duration and end-to-end browser duration separately using a production build. No measured operation may return an unexpected error or produce a duplicate/partial authoritative row.

| Operation | Required threshold |
|---|---|
| Active-session/dashboard API projection | p95 server duration `<= 750 ms` |
| Initial Brew-Day dashboard usable state | p95 navigation-to-authoritative-controls `<= 2,500 ms` |
| Refresh/reconnect recovery | p95 navigation-to-authoritative-reconciled-state `<= 2,000 ms` |
| Reconstruct and project 10 timers | p95 server duration `<= 500 ms`; all identities/deadlines exact |
| Measurement submission plus reminder satisfaction | p95 end-to-end `<= 1,000 ms` |
| Reminder acknowledgement/skip | p95 end-to-end `<= 750 ms` |
| Stage transition, including atomic child effects | p95 end-to-end `<= 1,250 ms` |
| JSON journal regeneration for 750 events | p95 server duration `<= 2,000 ms` |
| Human-readable HTML journal regeneration | p95 server duration `<= 3,000 ms` |

The implementation must use bounded indexed queries and pagination/projection appropriate to the active view; it may not require a full unbounded history scan. Missing a threshold is an acceptance failure and does not authorize Redis authority, a distributed cache, microservice split or new infrastructure. Optimization remains inside the accepted modular monolith unless a separately accepted ADR is necessary.

## 8. Required API capability

Exact request/response schemas may be refined during implementation, but the following versioned capabilities and semantics are required. Any route deviation must be documented in the implementation report.

The existing Phase 1A route contracts remain supported. Compatibility adapters must call the same Phase 3 application services and produce the same authoritative transitions and events; they may not maintain a second workflow implementation.

- `POST /api/v1/brew-sessions` - create `PLANNED` session and immutable snapshot.
- `POST /api/v1/brew-sessions/{id}/ready` - validate preflight and enter `READY`.
- `POST /api/v1/brew-sessions/{id}/start|pause|resume|abort|complete`.
- `GET /api/v1/brew-sessions/active` and `GET /api/v1/brew-sessions/{id}`.
- `POST /api/v1/brew-sessions/{id}/stages/{stage_instance_id}/start|pause|resume|skip|complete|extend`; the stable instance ID is mandatory and stage name/type cannot select an occurrence.
- `POST /api/v1/brew-sessions/{id}/stages/{stage_instance_id}/repeat|return` always creates the next runtime occurrence for the same `plan_step_id` under section 6.2. It never appends to or reopens the source. Both require expected session revision, operation ID and nonempty reason.
- `POST /api/v1/brew-sessions/{id}/timers` and timer `start|pause|resume|extend|replace|complete|cancel|acknowledge` commands.
- Authenticated reminder query and `acknowledge|skip|cancel` commands; completion is performed only by the linked authoritative action or allowed waiver, not a generic completion route.
- `POST /api/v1/brew-sessions/stages/{stage_instance_id}/measurements`; a completed-stage or terminal-session target additionally requires explicit late-entry flag/reason and is accepted only under section 6.8 and P3-FR-018/095/096.
- `POST /api/v1/brew-sessions/measurements/{id}/corrections`.
- `POST /api/v1/brew-sessions/stages/{stage_instance_id}/waivers`; no stage-name selector is permitted and `phase3-waiver-v1` controls eligibility.
- `POST /api/v1/brew-sessions/{id}/additions/{addition_id}/acknowledge|skip`.
- `POST /api/v1/brew-sessions/{id}/deviations`.
- `POST /api/v1/brew-sessions/{id}/notes`.
- `POST /api/v1/brew-sessions/{id}/attachments` and authenticated retrieval/removal routes.
- `GET /api/v1/brew-sessions/{id}/journal`.
- `GET /api/v1/brew-sessions/{id}/completion-audit`.
- `GET /api/v1/brew-sessions/{id}/export?format=json|html`.

Mutation responses must identify the resulting resource/state and concurrency version. Validation failures use `422`, authentication failures `401`, cross-owner or hidden-resource access the established non-disclosure response, invalid transitions/conflicts `409`, and unsupported media `415` where applicable.

There is no independent stage-abort/cancel route. The stage `skip` route accepts only optional `PENDING` stages. Session `/abort` is the sole producer of stage `ABORTED`. Terminal-session mutation middleware/application policy rejects every command outside the section 6.8 allowlist before ordinary domain orchestration.

Every mutation accepts the scoped operation identifier required by P3-FR-076. APIs must return enough stable identity and state to distinguish an original success replay from a new mutation. Event delivery, media transfer, journal rendering, or a dropped response cannot cause the client to invent success.

Every browser mutation also enforces P3-FR-089 before idempotency or domain processing. A CSRF rejection returns `403` and cannot reserve an operation key or create a domain/journal/audit mutation.

The accepted Phase 1A `/api/v1/brew-sessions/{id}/mash/start` adapter selects only the first not-started `MASH` instance in a `LEGACY_MASH_ONLY` plan or the single unambiguous first planned Mash occurrence in a nonlegacy plan. It calls the same instance-targeted Phase 3 service. If no eligible occurrence exists or more than one candidate is ambiguous, it returns `409` with current stage identities and creates nothing. It never creates an unplanned repeat implicitly.

## 9. Persistence and migration contract

Phase 3 must use a single additive Alembic revision named `0003_phase3_brew_day_os` unless an accepted implementation ADR justifies a bounded series with one Phase 3 head.

The migration must:

- upgrade from `0002_phase2_brewing_core` without editing either accepted migration;
- preserve all Phase 1A and Phase 2 rows and constraints;
- provide explicit defaults/backfill/nullability for existing Mash-only sessions;
- preserve existing Mash-only session/stage/timer/reminder/measurement/event IDs and implement the read-only `legacy-phase1a-session-v1` compatibility projection without replacement historical rows;
- add database constraints/indexes needed for state, order, ownership joins, correction lineage, timer integrity, and stable journal retrieval;
- retain or strengthen completed-measurement and used-recipe-version immutability;
- avoid creating Phase 4–10 tables or speculative columns;
- downgrade only Phase 3 objects and return cleanly to `0002_phase2_brewing_core`; and
- re-upgrade with the representative Phase 1A/2 preservation vector unchanged.

No authoritative session state, timer state, reminder state, or attachment metadata may exist only in Redis, memory, filesystem naming, or browser storage.

### 9.1 Required PostgreSQL invariant inventory

The Phase 3 migration and integration tests must enforce the following wherever PostgreSQL can express the rule safely. Application/domain checks supplement these constraints; frontend state is never sufficient enforcement.

| Invariant | Required enforcement |
|---|---|
| Every Phase 3 row belongs through foreign keys to the correct owner/session/stage hierarchy | Foreign keys plus ownership-scoped application queries; no orphan or cross-session link |
| Session, stage, timer, reminder and addition statuses use valid values and compatible required timestamps | Check constraints plus domain transitions |
| At most one `ACTIVE` or `PAUSED` BrewSession per owner under the current architecture | Partial unique index or transactionally locked equivalent documented and PostgreSQL-tested |
| BrewSession creation and complete `phase3-plan-v1` snapshot materialization are all-or-nothing; plan rows cannot be changed after creation | One transaction, non-null rule/source fields, deterministic logical-plan hash, and append-protection trigger/permissions |
| `phase3-plan-v1` total order and predecessor graph are reproducible; accepted legacy projection IDs never drift | Persist normalized order keys/hash for new plans; fixed UUIDv5 namespace/name fixtures and no-replacement migration tests for legacy sessions |
| One stage occurrence identity/order within a session; repeated occurrences remain distinct | Unique `(brew_session_id, plan_step_id, occurrence_number)` or accepted equivalent |
| Runtime repeat/return occurrence numbers are contiguous and exactly one concurrent next occurrence succeeds | Session/plan-step transaction lock plus unique occurrence constraint, expected revision and idempotency record |
| A stage command cannot target a stage instance from another session/owner or select by ambiguous type/name | Session-scoped foreign keys plus ownership query/transaction lock; instance-targeted API only |
| Timer revision/replace links remain in the same session and cannot self-reference | Foreign keys/checks plus domain validation |
| Addition timing basis, offset, reference stage, clock basis and revision are valid and internally compatible | Check constraints for enum/nonnegative shape plus domain validation against the snapshotted plan |
| Reminder satisfaction source belongs to the same session/stage and one requirement is not completed twice | Unique requirement identity plus transaction/domain validation |
| At most one active Waiver exists per stable requirement; nonwaivable kinds cannot be accepted; supersession retains both Waiver and evidence | Unique active-waiver scope, immutable Waiver rows, constrained status/source shape plus domain eligibility policy |
| Measurement type/process point/context shape is valid; correction references the same type/session lineage and cannot self-reference or fork ambiguously | Enum/check constraints and same-session foreign keys where expressible plus versioned domain validation and unique lineage |
| Late evidence retains terminal availability/provenance and cannot alter original session/stage terminal facts | Non-null late-entry metadata/checks, immutable terminal columns and domain/application time-window enforcement with PostgreSQL integration proof |
| Scoped operation identity is unique and payload mismatch cannot overwrite the stored result or tombstone | Unique actor/use-case/aggregate/operation key plus immutable fingerprint/result/tombstone record |
| Attachment metadata is owner/session scoped and cannot reference a temporary/unvalidated storage identity | Foreign keys, finalized-status/checksum/size constraints and ownership-scoped application finalization |
| Completed/aborted session and completed stage observations/history cannot be updated or deleted through normal paths | Retain/strengthen PostgreSQL trigger protection plus append-only corrections/annotations |
| Stable journal order is deterministic | Indexed `(brew_session_id, occurred_at, recorded_at, id)` or accepted equivalent |

State-transition legality that cannot be expressed reliably as a static check remains a domain/application responsibility inside the same transaction and requires PostgreSQL integration tests for competing commands.

## 10. User-interface contract

The responsive Brew-Day interface must provide:

- a large, glanceable current-stage and timer presentation suitable for wet-hands operation;
- visible session state, sync/recovery state, current stage, upcoming actions, and blockers;
- concurrent timer cards with distinct labels, due/overdue status, and accessible controls;
- planned-versus-actual cards with explicit units and truthful missing/waived states;
- measurement forms with manual fallback and confirmation for voice candidates;
- addition acknowledgement, deviation, note, and photo workflows;
- a chronological event log and completed-session summary;
- a deterministic CompletionAudit showing recorded, waived, missing, unresolved, and unavailable items without treating waivers as measurements;
- destructive-action confirmation for abort, skip, waiver, cancellation, and attachment removal;
- keyboard operation, visible focus, semantic labels, error association, non-color-only status, and `aria-live` use that does not announce every timer tick; and
- usable layouts at approximately 360 px phone width, tablet width, and desktop width.

The UI must not claim offline support. If disconnected, it must display the loss of synchronization, prevent false success, preserve safe unsubmitted form text where practical, and reconcile against server state after reconnect.

## 11. Explicit Phase 4–10 anti-leakage boundary

The following table is normative. “Permitted seam” means only the smallest data needed to finish Brew-Day OS; it does not authorize the later domain.

| Later phase | Prohibited in Phase 3 | Permitted Phase 3 seam |
|---|---|---|
| Phase 4 - Fermentation, Conditioning, Yeast | Fermentation sessions, curves, alerts, conditioning, attenuation tracking, yeast inventory/reuse lineage, troubleshooting engine | Record pitch time, temperature, and brewer-entered pitch note/addition as brew-day facts |
| Phase 5 - Quality, Packaging, Finished Beer | QA/QC plans, CIP/sanitation domain, calibration/maintenance workflows, microbiology, oxygen/stability, packaging sessions, carbonation operations, kegs/cans/bottles, draft/taps | General brew-stage notes/photos and instrument/method metadata only |
| Phase 6 - Inventory Intelligence, Purchasing, Operations | Automatic inventory consumption, reservation conversion, purchasing, reorder automation, forecasts, freshness scoring, substitution simulation, calendars, capacity planning | Display snapshotted planned ingredient additions and acknowledge actual additions without inventory mutation |
| Phase 7 - Master Brewer Academy | Curriculum, assessments, mastery, BJCP lessons, sensory training, contextual tutoring | Static operational instructions already owned by the recipe/process snapshot |
| Phase 8 - Experiments and Sensory | Sensory-target formulation, A/B or split-batch management, panels, scoresheets, advanced optimization | Operational deviations and notes without sensory/experiment semantics |
| Phase 9 - Competition, Branding, Menu | AI judge, competition records, names/logos/labels/tap badges, menus, QR availability | None |
| Phase 10 - Brewer Knowledge Engine | Personal brewing profile, correlations, historical recommendations, predictive scoring, AI optimization | Preserve trustworthy Phase 3 evidence for later authorized analysis |

Additional prohibited leakage:

- no LLM, AI coach, generated corrective action, or autonomous recommendation;
- no IoT sensor ingestion, hardware control, MQTT, PLC, smart-device integration, or automatic actuation;
- no public APIs or public UI;
- no production/NAS deployment, tunnel, DNS, remote-access, or secrets rollout;
- no native mobile app or offline-first synchronization engine;
- no email/SMS/push notification platform;
- no broad refactor of accepted Phase 2 code solely for style;
- no microservice split, new database authority, event broker, or distributed workflow engine;
- no speculative schema for later phases; and
- no release tag before independent acceptance.

The following rejected designs are normative closure of the two known reconciliation leakage risks and related Candidate A architecture conflicts:

- **Phase 6 deferral:** Phase 3 does not consume reservations, post inventory-ledger consumption, reconcile stock, automate purchasing, or block BrewSession completion on inventory mutation. It may preserve planned and actual ingredient/lot/substitution references with zero ledger effect. Inventory consumption and reservation conversion remain Phase 6 operational scope.
- **No offline synchronization engine:** Phase 3 provides server-authoritative refresh/reconnect recovery and truthful unsynchronized UI state. It does not queue authoritative offline mutations, resolve generalized offline conflicts, or establish a client operation-log platform. Broader offline-first behavior requires a later roadmap/ADR decision.
- **No aggregate replacement:** The accepted `RecipeVersion -> BrewSession` lineage and immutable session snapshot remain authoritative for Phase 3; no mandatory BrewPlan/BrewBatch replacement is introduced.
- **No outbox mandate:** BrewJournalEvent and AuditEvent creation is atomic with the owning command in PostgreSQL, but Phase 3 does not require a transactional outbox, event broker, or distributed worker. A future durable external side effect must justify those mechanisms through an accepted ADR.

## 12. Architecture constraints

- Preserve the modular monolith and four-layer architecture.
- Keep brewing calculations and comparisons in `packages/calculations` or a clearly bounded deterministic domain package.
- Keep workflow orchestration out of HTTP route handlers and React components.
- PostgreSQL remains authoritative; migrations own schema evolution.
- Use Decimal for authority-bearing physical calculations and comparisons.
- Persist UTC; localize only for display.
- Reuse the existing authentication, ownership, audit, logging, health, and configuration foundations.
- Decompose the Phase 2 orchestration facade only where Phase 3 dependency direction or testability requires it; document any such refactor and prove behavior preservation.
- A new dependency requires an explicit need, license review, vulnerability review, and lockfile update.
- A new architectural decision requires an ADR before implementation relies on it.

## 13. Acceptance matrix

Independent acceptance must record `PASS`, `FAIL`, or `NOT RUN` with evidence for every gate. `NOT RUN` cannot produce overall `PASS`.

### A. Scope and architecture

- **P3-AC-001:** Diff from `v0.2.0-phase2` contains only Phase 3, bounded compatibility work, tests, migrations, and documentation.
- **P3-AC-002:** Architecture review confirms deterministic workflow/calculation authority and no prohibited AI or forward-domain implementation.
- **P3-AC-003:** Phase 4–10 leakage scan maps every new table, route, service, dependency, and page to an authorized Phase 3 requirement.
- **P3-AC-004:** Phase 1A and Phase 2 accepted browser flows still pass unchanged or with documented selector-only maintenance.

### B. Domain and API

- **P3-AC-010:** Full canonical stage flow materialized by `phase3-plan-v1` completes with server-enforced ordering and requirements.
- **P3-AC-011:** Invalid transitions, duplicate commands, missing requirements, and stale versions fail without partial writes.
- **P3-AC-012:** Session/stage pause, resume, abort, skip, waiver, and completion apply every child effect in section 6.7 atomically.
- **P3-AC-013:** Three concurrent timers survive refresh and service restart with explainable elapsed time.
- **P3-AC-014:** Planned additions use section 6.6 timing semantics to create timers/reminders; acknowledge/early/late/skip/unscheduled paths preserve basis, due projection, variance, plan and actual history.
- **P3-AC-015:** All required measurement types validate definition version, process point, context, range/unit and produce truthful distinguishable comparison states.
- **P3-AC-016:** Correction chains and waivers are append-only and used correctly by completion rules.
- **P3-AC-017:** Retry and concurrency tests prove no duplicate transition, measurement, addition, or journal event.
- **P3-AC-018:** Complete and aborted sessions reject further normal execution mutations.

### C. Persistence and integrity

- **P3-AC-020:** Fresh PostgreSQL upgrade reaches the exact Phase 3 head.
- **P3-AC-021:** `0002 -> 0003 -> 0002 -> 0003` round trip succeeds.
- **P3-AC-022:** Representative Phase 1A and Phase 2 counts and relationships are unchanged across the round trip.
- **P3-AC-023:** PostgreSQL integration tests prove critical immutability, correction, state, timer, and ownership invariants.
- **P3-AC-024:** API/web restart recovery proves no authoritative reliance on process memory, Redis, or browser storage.

### D. Security and media

- **P3-AC-030:** Cross-user tests cover session, stage, timer, measurement, journal, note, and attachment identifiers.
- **P3-AC-031:** File tests cover each fixed type/size/count/quota/metadata bound, invalid MIME/signature/decoder, executable/active/polyglot, traversal/header filename, unauthorized retrieval, safe response headers, throttling, retention and completed-evidence removal.
- **P3-AC-032:** Secret/artifact scan finds no credentials, dumps, uploaded test media, databases, logs, traces, or build artifacts in Git.
- **P3-AC-033:** Dependency audits report zero known high or critical vulnerabilities; any lower finding requires documented disposition.

### E. Frontend and browser

- **P3-AC-040:** Component tests cover stage controls, concurrent timers, planned/actual states, validation, conflicts, and voice confirmation.
- **P3-AC-041:** Browser E2E completes the full PostgreSQL-backed flow, including refresh recovery, at least three timers, late addition, required measurements, correction, waiver, note, photo, completion, and journal/export.
- **P3-AC-042:** A second E2E scenario proves pause/restart/resume and abort behavior.
- **P3-AC-043:** Voice-capable mocked-browser test proves draft -> parse -> preview -> explicit confirm -> validated persistence; unsupported-browser test proves manual fallback.
- **P3-AC-044:** Automated accessibility checks plus keyboard/manual review find no blocking issue in Brew-Day pages.
- **P3-AC-045:** Phone, tablet, and desktop viewport evidence shows no inaccessible control, clipped authoritative value, or unusable timer.

### F. Runtime and operations

- **P3-AC-050:** Ruff, backend tests, PostgreSQL tests, frontend tests, lint, TypeScript, production build, and complete Playwright suite pass from the exact candidate tree.
- **P3-AC-051:** Dependency audits and Compose configuration validation pass.
- **P3-AC-052:** Disposable runtime health and authenticated smoke checks pass for login, session creation, recovery, journal, and attachment retrieval.
- **P3-AC-053:** Backup and isolated restore preserve one representative completed Phase 3 session, including correction lineage, timers, journal, and attachment metadata/bytes.
- **P3-AC-054:** The disposable environment is stopped without deleting owner data; no NAS production action occurs.

### G. Reconciliation-remediation traceability

| Requirement ID | Requirement | Enforcement layer | Test type | Pass criteria | Evidence expected |
|---|---|---|---|---|---|
| P3-AC-060 | P3-FR-016 through 019: repeated/extended/late stage execution | Database + domain + application + API | PostgreSQL integration + contract + E2E | Planned and runtime repeats have distinct instance IDs/occurrences; every command targets the intended instance; extension/late entry preserves old facts; wrong occurrence and invalid duplicate/backward transition are atomic `409`; legacy Mash adapter reaches the same service | Rows/events, API identities and browser timeline for two same-type stages, repeat, extension, late measurement, legacy route and rejected wrong occurrence |
| P3-AC-061 | P3-FR-028/029: reminder lifecycle and idempotent satisfaction | Database + domain + application | Concurrency integration + E2E | All required states are demonstrated; acknowledgement does not satisfy; one measurement completes one reminder once across two tabs/retry/duplicate delivery | Reminder state history, operation result and row counts |
| P3-AC-062 | Timer extension/replacement and revision history | Database + domain + application | Unit + PostgreSQL integration + E2E | Original duration/deadline survives extend/replace; current timer reconstructs from PostgreSQL; competing revisions yield one success | Timer/revision rows, events and browser recovery evidence |
| P3-AC-063 | P3-FR-076 through 078: operation identity, optimistic concurrency and atomic command sets | Database + application | Contract + failure-injection + concurrency integration | Canonical equivalents share one SHA-256 fingerprint/result; array/Decimal/UUID/time/default rules match `phase3-operation-v1`; key mismatch is `409`; timeout retry replays; archived result returns reconstructed result/`410` without execution; different-key semantic duplicate obeys domain uniqueness; injected failure leaves zero partial rows/events | Canonical fixtures, operation/tombstone rows, transaction vectors and replay/conflict responses |
| P3-AC-064 | P3-FR-085/086: event, audit and journal authority | Database + domain + application | Contract + integration + regeneration test | Typed event and separate audit are created once; journal/export regeneration is byte/semantically stable and creates no operational event; renderer failure does not roll back command | Event/audit IDs, schema versions, journal hashes/counts and failure evidence |
| P3-AC-065 | P3-FR-030 through 039: measurement identity/context/provenance | Database + domain + API | Golden + contract + PostgreSQL integration | Every `phase3-measurement-v1` type retains process point, stage instance, raw/canonical value/unit, required method/temperature/vessel/correction context and both times; post-mash/pre-boil/OG and knockout/pitch remain distinguishable after completion; duplicate replays; correction retains original | Golden payloads and completed-session correction/provenance chains for every required type |
| P3-AC-066 | P3-FR-059: CompletionAudit | Domain + application | Golden/unit + API + E2E | Rule-versioned counts/status reproduce from authoritative data; waiver/missing does not count measured; unresolved blockers shown truthfully | Golden audit JSON and human-readable completed/aborted summaries |
| P3-AC-067 | P3-FR-046: actual addition identity without Phase 6 mutation | Database + domain + application | Contract + PostgreSQL integration + E2E | Planned and actual identities/times/amounts/lots/substitution ref remain separate; inventory transaction/reservation counts do not change | Addition record/event plus before/after Phase 2 ledger vector |
| P3-AC-068 | P3-FR-050 through 058: media/resource controls and failure isolation | API + application + infrastructure | Security + quota + failure-injection integration + E2E | Exact type/size/count/quota/rate bounds enforce deterministic errors; retrieval headers/ownership pass; failed/ambiguous/retried upload does not change core state or duplicate bytes; orphan reconciliation meets 24-hour boundary; unavailable bytes render placeholder | Response/header receipt, quota/rate cases, state vectors, storage/metadata counts and journal output |
| P3-AC-069 | P3-FR-079: authoritative failure recovery | Database + application + infrastructure | Restart/failure-injection E2E | Same session/stage/deadlines/reminders/measurements/actions return with no duplicate event after close/sleep/network/API/PostgreSQL/Redis cases; worker case is tested or proven N/A | Pre/post identity/state vectors, timer deadlines and event counts |
| P3-AC-070 | Required PostgreSQL invariant inventory | Database + domain | PostgreSQL integrity + migration test | Every section 9.1 rule has named enforcement and negative/concurrent proof; no critical invariant relies only on frontend | Invariant-to-constraint/test matrix and database failure output |
| P3-AC-071 | P3-FR-087: observability/reconstruction | Application + infrastructure | Integration + operational reconstruction | One injected timer/reminder/command failure is reconstructed by correlation and safe metrics/logs; sensitive payload scan is clean | Timeline, metric samples, correlation IDs and redaction scan |
| P3-AC-072 | P3-FR-066: voice transcription safety | Frontend + API + domain | Component + E2E | Parsed `52` from “five point two” remains draft, is visibly confirmed/corrected, and cannot pass pH validation as 52 | Mock transcript/preview plus rejected API and corrected committed value |
| P3-AC-073 | P3-FR-088: responsive-operation performance | Application + frontend + infrastructure | Bounded production-build benchmark | Every numeric p95 in the normative profile passes on the recorded reference class/dataset with zero unexpected errors or duplicate/partial writes; active dashboard uses bounded indexed queries and no full-history scan | Hardware/environment/data manifest, query evidence, raw samples and calculated percentiles |
| P3-AC-074 | P3-FR-002/004/006/008/009/012/013: deterministic stage-plan materialization | Database + domain + application | Golden + contract + PostgreSQL integration | Same normalized Phase 2 source/rule produces identical logical plan; sparse/default/legacy/duplicate/unsupported/invalid cases match section 6.1.1; failure creates zero session/plan rows | Golden plan hashes/rows, structured `422` cases and Phase 1A/2 preservation vector |
| P3-AC-075 | P3-FR-014/015/022/025/028: state-effect matrix | Database + domain + application | State-table unit + PostgreSQL failure/concurrency + E2E | Every row in section 6.7 produces exactly the stated stage/session/timer/reminder/addition transitions and events atomically; unrelated history is unchanged | Before/after state vectors, journal/audit IDs and injected rollback evidence |
| P3-AC-076 | P3-FR-021 through 024/046/047: addition schedule semantics | Domain + application + API | Golden + contract + E2E | Every Phase 2 use-stage/timing case maps to the exact basis/offset/reference/clock rule; invalid/ambiguous schedule blocks materialization; early/late variance and revision history are exact; forward-phase additions create no workflow | Golden due calculations, preflight errors, timer/addition rows and zero post-pitch surface |
| P3-AC-077 | P3-FR-080/081/084/089: CSRF and private boundary | Security middleware + API | Adversarial integration + browser | Valid token/origin succeeds; missing/wrong token, cross-origin request and login CSRF fail `403` before idempotency/domain mutation; token rotates/expires; routes remain private and no deployment/public surface appears | Request matrix, zero-mutation row vectors, binding/config scan and browser receipt |
| P3-AC-078 | P3-FR-009/090: total plan order/predecessors | Domain + application + database | Golden + property/contract + PostgreSQL integration | Permuting database/insertion/UI retrieval does not change plan; same valid source yields identical order/hash; duplicate/missing/malformed/unsupported/decreasing canonical order is exact `422` with zero rows; same-type repeats/default insertion match section 6.1.1 | Ordered normalized fixtures, hashes, predecessor rows and failure row counts |
| P3-AC-079 | P3-FR-006/007/008/091: accepted-session compatibility | Migration + application + API | Migration round-trip + restart + contract + Phase 1A E2E | Existing planned/active/completed Mash sessions retain every accepted ID/status/time/relationship; UUIDv5 projected identities remain byte-identical across reads/restarts/round trips; old routes create no duplicate Mash or alternate events | Pre/post row vectors, UUID fixtures, repeated responses and complete Phase 1A flow |
| P3-AC-080 | P3-FR-016/019/092: controlled repeat/return | Database + domain + application + API | State-table + concurrency + contract + E2E | Completed-stage repeat/return creates one new UUID instance with same plan step and contiguous next occurrence; prior stage remains immutable; active-stage, invalid-source, duplicate-key and racing commands produce the specified replay/`409` behavior | Occurrence/link/event rows, before/after terminal facts and browser chronology |
| P3-AC-081 | P3-FR-012/015/028/037/093/094: abort/cancel/waiver | Database + domain + application + API | State-table + PostgreSQL rollback/concurrency + E2E | Optional pending skip is the only stage cancel; session abort alone creates stage ABORTED and exact child effects; each waivable class succeeds once, each nonwaivable class fails `409`, duplicate waiver is idempotent, and late evidence supersedes without erasure | Full effect vectors, waiver/reminder history, CompletionAudit and atomic row/event counts |
| P3-AC-082 | P3-FR-018/036/038/095: late evidence | Database + domain + API | Boundary-value clock + contract + PostgreSQL integration + E2E | At, before and after every 5-minute/24-hour/7-day/30-day boundary produce exact acceptance/conflict; observed/recorded times and availability flags persist; completed and aborted policies differ exactly; original terminal facts never change | Fixed-clock fixtures, row/timestamp vectors, reminder/waiver transitions, journal and comparisons |
| P3-AC-083 | P3-FR-059/086/096: terminal-session allowlist | Database + domain + application + API | Mutation-matrix + failure-injection + E2E | Every allowed post-terminal append/regeneration works only in its window; every prohibited start/resume/stage/timer/waiver/media/plan/reference mutation is `409` with zero ordinary domain/journal change; completed/aborted journal and CompletionAudit remain reproducible | Endpoint/state matrix, zero-mutation vectors, projection hashes and immutable terminal timestamps |

### H. Mandatory adversarial scenarios

| ID | Scenario | Deterministic pass oracle |
|---|---|---|
| P3-ADV-001 | Two tabs submit the same measurement/operation | One Measurement, one reminder satisfaction, one operational event; both clients receive the original result or one stable conflict |
| P3-ADV-002 | Two tabs submit distinct measurements for a single-occurrence requirement | Exactly one succeeds unless the definition permits repeated observations; loser receives current authoritative state; no silent merge |
| P3-ADV-003 | Same operation key is reused with a different payload | `409`; no state/event/audit mutation beyond the safe conflict audit policy |
| P3-ADV-004 | API commits then response is lost | Retry with the same operation identity returns the committed result and creates no duplicate |
| P3-ADV-005 | Reminder is delivered twice and acknowledged in two tabs | One reminder identity; acknowledgement is idempotent and does not complete the requirement |
| P3-ADV-006 | Measurement is recorded while two clients try to complete its reminder | Measurement and reminder complete atomically once; no standalone generic completion succeeds |
| P3-ADV-007 | Three timers run during browser refresh, close/reopen and device sleep | Same identities/deadlines reconstruct from PostgreSQL; elapsed/expired projection is correct; no duplicate timers/events |
| P3-ADV-008 | Timer is extended then replaced concurrently | One expected revision succeeds; original/revision/replacement lineage remains complete; stale command conflicts |
| P3-ADV-009 | Redis disappears during boil | Session, timers, reminders, journal and measurements remain authoritative and recoverable; only explicitly non-authoritative delivery may degrade visibly |
| P3-ADV-010 | API restarts and reconnect occurs after a deadline | Timer is shown expired using the original deadline; no stale remaining-time claim or duplicate expiry fact |
| P3-ADV-011 | PostgreSQL restarts during a command | Command is wholly committed or rolled back; retry is safe and no partial rows exist |
| P3-ADV-012 | Worker restarts | If a worker is used, no authority or semantic delivery is lost/duplicated; otherwise architecture evidence marks the scenario N/A |
| P3-ADV-013 | Client clock is skewed or a DST boundary occurs | UTC authoritative deadline/result is unchanged; display/localization remains correct; skewed observed time is validated and preserved truthfully |
| P3-ADV-014 | Brewer corrects an erroneous measurement | Original remains immutable; linked correction becomes current effective value; comparison and audit/journal remain explainable |
| P3-ADV-015 | Hop addition occurs five minutes late using an authorized substitute lot | Plan remains unchanged; actual identity/lot/time/amount and substitution reference persist; deviation appears; Phase 2 ledger is unchanged |
| P3-ADV-016 | Stage completion is attempted with missing required data | Server rejects or follows an explicitly authorized waiver path; no fabricated measurement or partial completion |
| P3-ADV-017 | Mash rest is extended and then repeated | Planned rest remains; extension history and distinct repeat occurrence preserve actual chronology |
| P3-ADV-018 | Measurement is entered late against a completed stage | Section 6.8 state/time boundary is enforced; observed/recorded times and availability flags persist without reopening/re-timing the stage |
| P3-ADV-019 | Photo upload fails or response is ambiguous during boil | Core state is unchanged and operable; retry is idempotent; orphan reconciliation and journal unavailable placeholder work |
| P3-ADV-020 | Voice parser proposes pH `52` from “five point two” | No authoritative commit before confirmation; API rejects 52; corrected confirmed 5.2 follows normal validation |
| P3-ADV-021 | RecipeVersion mutation is attempted during an active session | Existing PostgreSQL immutability rejects mutation; session snapshot and journal remain unchanged |
| P3-ADV-022 | Interrupted BrewSession is reopened the next day | Same server-authoritative session and history load; timers show truthful elapsed/expired state; no generalized offline commands are replayed |
| P3-ADV-023 | Journal renderer/export fails then is retried | Brew-Day command remains committed; regeneration is idempotent and adds no BrewJournalEvent |
| P3-ADV-024 | CompletionAudit includes measured, waived, missing and not-applicable requirements | Counts/status are deterministic; only measured observations contribute to measurement completeness |
| P3-ADV-025 | Phase 1A and Phase 2 regression | Both accepted E2E flows and PostgreSQL invariants pass; Phase 3 adds no Phase 6 inventory mutation or Phase 4-10 table/surface |
| P3-ADV-026 | The same sparse Phase 2 RecipeVersion is materialized twice under `phase3-plan-v1`; then one invalid/unsupported source is tried | Valid logical plan hashes/ordering/defaults match exactly; invalid source returns structured `422` and creates zero BrewSession/plan rows |
| P3-ADV-027 | Two Mash instances exist; commands target the second, the wrong occurrence, and the legacy `/mash/start` adapter | Instance-targeted command changes only the intended row; wrong/duplicate target is atomic `409`; legacy adapter selects only the unambiguous first occurrence and uses the same service |
| P3-ADV-028 | Session is paused/resumed and then aborted while active-time/wall-clock timers and required/optional reminders are open | Every child transition exactly matches section 6.7; unresolved required items remain truthful evidence; unrelated/completed history is unchanged; all rows/events commit atomically |
| P3-ADV-029 | Legacy Phase 2 Mash, first-wort, 60-minute boil, flameout, whirlpool and invalid miscellaneous additions are materialized | Exact basis/offset/reference/clock projections match section 6.6; invalid context blocks plan; five-minute late execution stores signed variance without ledger effect |
| P3-ADV-030 | Completed session records post-mash gravity, pre-boil gravity, OG, volumes, pH and knockout/pitch temperatures with a correction | Types/process points and required method/temperature/vessel/raw/canonical context remain distinguishable; correction never overwrites raw evidence |
| P3-ADV-031 | Canonically equivalent JSON is retried after lost response, key is reused with changed Decimal/time payload, and full result retention is expired | Equivalent request replays once; changed fingerprint is `409`; archived same request reconstructs/returns `410` without execution; tombstone prevents key reuse |
| P3-ADV-032 | Oversize, quota-exceeding, MIME/polyglot, traversal/header filename, cross-owner and throttled media requests occur during active boil | Exact `413/415/409/429` or nondisclosure result; safe headers on valid retrieval; no core-state mutation; retry/orphan handling remains idempotent |
| P3-ADV-033 | Browser sends missing/wrong/expired CSRF token, cross-origin state mutation, login CSRF, then valid same-origin token | Invalid requests are `403` before operation/domain writes; valid request succeeds once; token rotates/expires; no public/deployment surface appears |
| P3-ADV-034 | Representative two-tab BrewSession is benchmarked on the recorded reference class | Every P3-FR-088 p95 threshold passes with raw samples, zero unexpected errors/duplicates/partials and bounded indexed active-view queries |
| P3-ADV-035 | Valid plan sources are fetched in different database/insertion orders; duplicate, missing, malformed and canonically decreasing sequences are attempted | Valid ordered plan/hash/predecessors are identical; every invalid vector is exact `422` and creates zero session/plan rows |
| P3-ADV-036 | Planned, active and completed Phase 1A Mash sessions are read repeatedly across API/PostgreSQL restart and migration round trip, then old routes are called | Existing and projected identities/statuses/times/relationships remain identical; no replacement/duplicate Mash, measurement, reminder or event appears; old routes use the Phase 3 service |
| P3-ADV-037 | A completed Mash is returned to after a later stage, an immediate rest repeat is requested, two returns race, and return is attempted while another stage is active | Each valid command creates exactly one new contiguous occurrence with same plan step and immutable source; replay/race/invalid active-stage cases return the prescribed result/`409` |
| P3-ADV-038 | Optional stage cancel, active-stage cancel, session abort with active children, waivable/nonwaivable requests, duplicate waiver and later valid evidence are attempted | Only optional pending skip succeeds as stage cancel; abort applies the full matrix; prohibited waiver/cancel fails; one waiver remains historical and is superseded deterministically by evidence |
| P3-ADV-039 | Measurement/addition/note/correction requests occur immediately before, at and after each late-entry boundary for active, completed and aborted sessions | Fixed-clock results match section 6.8 exactly; provenance/availability flags persist; aborted new evidence is rejected; original terminal facts never change |
| P3-ADV-040 | Every normal mutation is attempted after `COMPLETED` and `ABORTED`, followed by journal/CompletionAudit regeneration | Only the explicit append-only allowlist within its window succeeds; all other commands are `409` without ordinary mutation; regeneration is stable and adds no event |

## 14. Required test layers

Implementation must add and execute:

- pure unit/golden tests for timing, pause math, due/overdue projection, unit/range rules, stage transitions, comparisons, and completion policies;
- application/service tests for idempotency, concurrency, ownership, corrections, waivers, journal emission, and transactional rollback;
- API contract tests for every command family and failure status;
- PostgreSQL tests for migration head, constraints, indexes, immutability, and round-trip preservation;
- attachment security/storage tests;
- frontend component tests;
- complete Playwright regression for Phase 1A, Phase 2, and Phase 3;
- backup/restore verification; and
- live disposable-runtime smoke checks.

The test plan must execute every P3-AC-060 through P3-AC-083 traceability row and every applicable P3-ADV-001 through P3-ADV-040 scenario. Failure-injection must occur at the authoritative boundary named by the scenario; merely mocking a successful response or restarting an unrelated container is insufficient. Any scenario marked not applicable requires architecture evidence and independent-review disposition.

SQLite may support fast tests but cannot substitute for PostgreSQL integrity evidence.

## 15. Required documentation and evidence artifacts

The implementation candidate is incomplete without:

- updated `README.md`, `docs/API.md`, `docs/TESTING.md`, `docs/domain/BREW_DAY_WORKFLOW.md`, architecture/data-model documentation, and operations/backup instructions;
- ADRs for any new material architecture decision;
- `docs/PHASE_3_IMPLEMENTATION_REPORT.md` containing scope mapping, migration summary, commands, actual results, limitations, and exact candidate SHA;
- `docs/evidence/PHASE_3_INDEPENDENT_ARCHITECTURE_AND_BREWING_ACCEPTANCE.md` completed by independent review;
- an explicit inventory proving no Phase 4–10 leakage; and
- a remediation traceability appendix mapping P3-FR-009, 014 through 019, 021 through 024, 030 through 039, 046/047, 050 through 059, 066, and 072 through 096 to enforcement, tests, actual results, and evidence locations;
- a clean-worktree and artifact/secret scan receipt.

Evidence must distinguish repository/static checks, automated tests, disposable local runtime checks, restore evidence, and any unavailable external/deployment evidence. Local Compose success is not NAS-production evidence.

## 16. Definition of done

Phase 3 is eligible for acceptance only when:

1. every `P3-FR` requirement is implemented or this specification is formally amended;
2. every `P3-AC` gate is `PASS` with reproducible evidence;
3. no Phase 4–10 or deployment leakage is present;
4. Phase 1A and Phase 2 regressions pass;
5. migration downgrade/upgrade and isolated restore pass;
6. documentation and evidence identify the exact candidate commit;
7. independent architecture and brewing-domain review returns `PASS`; and
8. the work stops before Phase 4 and NAS production deployment.

Only after closure may an annotated `v0.3.0-phase3` tag be proposed. Tagging, pushing, deployment, and Phase 4 each require their own authorization.

## 17. Pre-implementation approval checklist

Before Cursor/Claude writes code, review must explicitly confirm:

- [ ] This specification revision is accepted.
- [ ] Phase 3 implementation is explicitly authorized.
- [ ] The implementation starts from the accepted Phase 2 tag plus reviewed planning documents.
- [ ] Existing uncommitted owner changes are inventoried and preserved.
- [ ] No Phase 4–10 capability is interpreted as implied Phase 3 scope.
- [ ] No NAS production deployment is authorized.
- [ ] The implementer agrees to stop after assembling the Phase 3 review candidate and evidence.

Until those boxes are affirmatively resolved, the correct state is:

`PHASE_3_SPECIFICATION_READY_FOR_REVIEW`

`PHASE_3_IMPLEMENTATION_NOT_AUTHORIZED`
