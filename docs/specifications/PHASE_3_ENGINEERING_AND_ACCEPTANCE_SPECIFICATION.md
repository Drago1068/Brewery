# Phase 3 Engineering and Acceptance Specification - Brew-Day OS

## 1. Document control

- Status: **DRAFT FOR ARCHITECTURE REVIEW**
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

### 6.2 Stage states

Required states:

`PENDING -> ACTIVE <-> PAUSED -> COMPLETED`

Exceptional states:

`PENDING -> SKIPPED`

`PENDING | ACTIVE | PAUSED -> ABORTED`

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
- Returning to a prior stage is prohibited by default. It is permitted only through an explicit authorized repeat/return command that creates a new stage instance or appends a bounded continuation; it never reopens or rewrites the completed instance.
- A measurement or addition recorded after its stage completed may reference the original stage instance only through a bounded late-entry command that preserves `observed_at`, server `recorded_at`, actor, reason, and current correction/waiver rules. Late entry does not change the historical completion timestamp automatically.
- An invalid backward transition returns `409` and creates no stage, timer, reminder, journal, or audit mutation.

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

Rules:

- Every reminder has a stable identity, owner, BrewSession, stage instance, requirement/action definition, priority, due trigger or UTC due time, status, schema/rule version, and optional measurement/addition/action link.
- `ACKNOWLEDGED` means the brewer saw or accepted the prompt; it does not satisfy a required measurement or action.
- `COMPLETED` requires the associated authoritative Measurement, AdditionEvent, or other allowed action and stores that record's identity as its satisfaction source.
- A required reminder may be skipped or cancelled only when the governing stage rule permits a waiver/cancellation; actor, reason, UTC time, and journal/audit records are mandatory. Required reminders never disappear through projection cleanup.
- Delivery is not authority. Duplicate or delayed deliveries reference the same reminder identity and cannot create another reminder or complete it twice.
- Recording the associated authoritative action and transitioning the correct reminder to `COMPLETED` occur in one transaction. Repeating the same scoped operation returns the original result. A competing action for an already completed reminder returns the authoritative result or a stable `409` without creating a second semantic completion.
- Expiration is deterministic from persisted due state/time. An expired reminder remains visible until completed, validly waived/skipped, or cancelled under an allowed rule.

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

### 7.2 Stage-aware worksheet

- **P3-FR-010:** Render the current stage, completed history, upcoming stages, blockers, required actions, planned values, and actual values.
- **P3-FR-011:** Enforce transitions server-side; disabling a UI control is not enforcement.
- **P3-FR-012:** Support required/optional stage definitions and explicit, reasoned skip or waiver records.
- **P3-FR-013:** Preserve both planned order and actual execution chronology.
- **P3-FR-014:** Support session and stage pause/resume without losing timing history.
- **P3-FR-015:** Abort must require confirmation and reason, preserve history, and cancel or retain outstanding timers according to a documented deterministic rule.
- **P3-FR-016:** Support planned and authorized runtime repetition of a process step through separately identified stage instances; preserve the snapshotted plan, occurrence order, actual chronology, and repeat reason.
- **P3-FR-017:** Support a stage/rest extension without changing its planned duration. Preserve every former timing fact and the actor, reason, and operation that extended it.
- **P3-FR-018:** Support bounded late measurement/addition entry against the correct stage instance with observed and recorded times. Do not reopen a completed stage or rewrite its completion history implicitly.
- **P3-FR-019:** Reject unrestricted backward transitions. A controlled return requires explicit authorization, reason, a new occurrence/continuation record, optimistic concurrency, and journal/audit evidence.

### 7.3 Timers, additions, and reminders

- **P3-FR-020:** Support at least three concurrent persisted timers in one browser acceptance scenario.
- **P3-FR-021:** Generate hop and other addition timers from snapshotted recipe process/addition schedules.
- **P3-FR-022:** Show due and overdue timers without relying on a continuously open browser tab.
- **P3-FR-023:** Acknowledge an addition with actual time, actor, optional actual quantity, canonical unit, and note.
- **P3-FR-024:** A missed, late, changed, skipped, or extra addition must produce an explicit deviation or exception event; it must not rewrite the plan.
- **P3-FR-025:** Required-data reminders must identify the requirement, stage, due basis, status, and satisfaction source.
- **P3-FR-026:** Reminder acknowledgement alone cannot satisfy a required measurement.
- **P3-FR-027:** In-app reminders are required. Email, SMS, push notifications, and production job infrastructure are out of scope.
- **P3-FR-028:** Reminder state must implement section 6.5, including stable identity, priority, delivery-independent authority, and reasoned skip/cancel/expiry behavior. Required reminders remain visible and auditable until resolved.
- **P3-FR-029:** Creating an authoritative measurement/addition/action and satisfying its unique reminder must be atomic and idempotent. Two tabs, retries, and duplicate delivery cannot complete the reminder or create the action twice.

### 7.4 Measurements and validation

- **P3-FR-030:** Support, at minimum, mash-in temperature, mash temperature, mash pH, post-mash gravity, pre-boil gravity, pre-boil volume, original/post-boil gravity, knockout volume, knockout temperature, and pitch temperature.
- **P3-FR-031:** A measurement must store type, Decimal value, canonical unit, observed-at UTC time, recorded-at UTC time, actor, entry method, optional instrument/method, stage, and provenance.
- **P3-FR-032:** Unit and plausible-range validation must occur at the API boundary and in the domain/application layer. PostgreSQL constraints must protect critical invariants where practical.
- **P3-FR-033:** Temperature measurement must make the scale explicit. Gravity must distinguish `SG` from any future Plato representation. Volumes must use canonical liters in authority-bearing storage.
- **P3-FR-034:** Corrections append a linked replacement and reason; no measurement update or deletion path may bypass history.
- **P3-FR-035:** Completion requirements use the latest valid measurement in a correction chain while retaining the entire chain.
- **P3-FR-036:** Measurement timestamps may be back-entered only within documented bounds and must preserve both observation and recording times.
- **P3-FR-037:** A required measurement may be waived only with explicit reason, actor, timestamp, and journal/audit event. A waiver is visibly different from a measurement.
- **P3-FR-038:** `observed_at` is the brewer-supplied or device-local observation instant subject to bounded validation; `recorded_at` is assigned by the authoritative server on receipt. Store entry source/method and retain both in the journal. Client clock skew or delayed entry must not silently rewrite either instant.
- **P3-FR-039:** A repeated submission with the same operation identity returns the original Measurement and reminder result. A genuinely distinct repeat observation receives a new identity; similar value/time alone is never used for silent deduplication.

### 7.5 Planned versus actual and deviations

- **P3-FR-040:** Comparison calculations use Decimal and live in the deterministic calculation/domain layer, never React or an LLM.
- **P3-FR-041:** Persist or reproducibly derive target, actual, signed variance, tolerance, result, unit, calculation/model identity, and source observation.
- **P3-FR-042:** Persist or derive the explicit comparison tuple `planned value`, `actual value`, signed `delta`, `unit`, `tolerance`, and `status`. Distinguish `WITHIN_TOLERANCE`, `OUTSIDE_TOLERANCE`, `MISSING`, `NOT_APPLICABLE`, `NO_TARGET`, `WAIVED`, and `NOT_RECORDED` truthfully. Do not calculate or display a delta when its operands/units do not support one, and do not imply precision beyond the accepted model/input precision.
- **P3-FR-043:** Permit an operational deviation unrelated to a numeric measurement, with category, description, stage, time, and optional corrective action.
- **P3-FR-044:** Correcting an observation must not erase the original deviation history; the current effective comparison and prior superseded comparison must remain explainable.
- **P3-FR-045:** Corrective-action text is brewer-authored deterministic workflow content in Phase 3. AI diagnosis is prohibited.
- **P3-FR-046:** Addition execution records must preserve planned addition identity, planned ingredient/time/amount/unit, actual ingredient identity, actual lot when known, actual time/amount/unit, execution status, and any accepted Phase 2 substitution reference. Acknowledgement has no Phase 3 inventory-ledger effect and never mutates RecipeVersion intent.

### 7.6 Notes, photos, and journal

- **P3-FR-050:** Add, read, and append-correct timestamped session/stage notes without overwriting completed history.
- **P3-FR-051:** Upload authenticated image attachments with allowlisted MIME types, bounded size/count, generated storage identifiers, checksum, original filename metadata, actor, and UTC timestamp.
- **P3-FR-052:** Reject executable, mismatched, oversized, and unauthorized files. User-controlled filenames must not become storage paths.
- **P3-FR-053:** Store attachment metadata in PostgreSQL and bytes behind the existing file/object-storage abstraction or a bounded local-development implementation; database paths must not expose server filesystem layout.
- **P3-FR-054:** Attachment deletion before session completion must be an audited soft removal. Completed-session attachment evidence cannot be silently deleted.
- **P3-FR-055:** The journal must automatically include session/stage transitions, timer lifecycle, reminders, measurements/corrections/waivers, deviations, addition acknowledgements, notes/media metadata, and completion/abort.
- **P3-FR-056:** Journal chronology must be stable, paginatable, ownership-scoped, and based on authoritative UTC event timestamps plus deterministic tie-breaking.
- **P3-FR-057:** Export a human-readable brew-day summary and a machine-readable JSON representation without introducing a general reporting platform.
- **P3-FR-058:** A failed, timed-out, or retried media operation cannot mutate or block session/stage/timer/reminder/measurement authority. Upload uses a stable operation identity; ambiguous retry is idempotent; orphan bytes/metadata are detected and reconciled. Journal/export renders an explicit unavailable-media reference when bytes cannot be read.
- **P3-FR-059:** Completion must produce a deterministic, rule-versioned Brew-Day CompletionAudit projection containing required recorded/waived/missing counts, unresolved reminders/deviations/additions, timer states, lineage and journal integrity, and outstanding issues. A waiver or `NOT_RECORDED` result never counts as a measured value or inflates measurement completeness.

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
- **P3-FR-076:** Every retryable mutation uses a client operation identifier persisted under an actor + use case + aggregate scope. Same identifier and equivalent normalized payload returns the prior result; same identifier with a different semantic payload returns `409` and creates no mutation. Retention must exceed the documented retry/recovery window.
- **P3-FR-077:** Order-sensitive commands include the expected aggregate/timer revision. Exactly one concurrent transition/revision may succeed; stale commands return current version/recovery data without a second semantic action.
- **P3-FR-078:** Each command atomically commits its authoritative state change, associated timer/reminder/action record, BrewJournalEvent, and required AuditEvent. A failure before commit rolls back all of them. Notification delivery and journal rendering/export are derived effects and cannot roll back an already committed Brew-Day command.
- **P3-FR-079:** Recovery must be correct after browser close/reopen, device sleep, network loss or unknown response, API restart, PostgreSQL restart/rollback, Redis loss, delayed/duplicate delivery, and reconnect after a deadline. A worker-restart test is required only if Phase 3 actually introduces/uses a worker; otherwise evidence must show the scenario is not applicable and no authority depends on one.

### 7.9 Security, ownership, and audit

- **P3-FR-080:** Every identifier lookup and mutation is ownership-scoped server-side.
- **P3-FR-081:** A second authenticated user cannot infer, read, modify, upload to, or transition another user's session or attachment.
- **P3-FR-082:** Audit records must cover state changes, waivers, corrections, attachment removal, and other security-relevant commands.
- **P3-FR-083:** Logs must include correlation/request identifiers and safe entity identifiers without secrets, raw audio, or unnecessary measurement/note contents.
- **P3-FR-084:** No route added by Phase 3 may be public.
- **P3-FR-085:** BrewJournalEvents are typed, append-oriented operational facts with schema version, session/stage identity, occurred and server-recorded UTC times, actor/source, operation identity, correlation/causation identifiers, and validated payload. They are not security/governance AuditEvents.
- **P3-FR-086:** The human-readable journal and exports are deterministic projections of BrewJournalEvents and linked authoritative records. They are never independently writable. Rendering/generation failure does not roll back Brew-Day state; regeneration is idempotent and creates no operational event.
- **P3-FR-087:** Phase 3 metrics and correlated logs must expose timer processing/display lag, recovery outcome, command conflict/deduplication, reminder satisfaction, journal generation failure, and media reconciliation without logging secrets or unrestricted measurement/note contents. Acceptance must reconstruct one simulated Brew-Day failure from this evidence.
- **P3-FR-088:** Before implementation, the work package must propose Product Owner-approved p95 targets for routine Brew-Day commands, active-session recovery, and dashboard rendering, plus the test hardware and representative event/timer/measurement volume. Acceptance records actual values and cannot replace missing thresholds with “appears responsive.”

## 8. Required API capability

Exact request/response schemas may be refined during implementation, but the following versioned capabilities and semantics are required. Any route deviation must be documented in the implementation report.

The existing Phase 1A route contracts remain supported. Compatibility adapters must call the same Phase 3 application services and produce the same authoritative transitions and events; they may not maintain a second workflow implementation.

- `POST /api/v1/brew-sessions` - create `PLANNED` session and immutable snapshot.
- `POST /api/v1/brew-sessions/{id}/ready` - validate preflight and enter `READY`.
- `POST /api/v1/brew-sessions/{id}/start|pause|resume|abort|complete`.
- `GET /api/v1/brew-sessions/active` and `GET /api/v1/brew-sessions/{id}`.
- `POST /api/v1/brew-sessions/{id}/stages/{stage_key}/start|pause|resume|skip|complete`.
- `POST /api/v1/brew-sessions/{id}/timers` and timer `start|pause|resume|extend|replace|complete|cancel|acknowledge` commands.
- Authenticated reminder query and `acknowledge|skip|cancel` commands; completion is performed only by the linked authoritative action or allowed waiver, not a generic completion route.
- `POST /api/v1/brew-sessions/stages/{stage_id}/measurements`.
- `POST /api/v1/brew-sessions/measurements/{id}/corrections`.
- `POST /api/v1/brew-sessions/stages/{stage_id}/waivers`.
- `POST /api/v1/brew-sessions/{id}/additions/{addition_id}/acknowledge|skip`.
- `POST /api/v1/brew-sessions/{id}/deviations`.
- `POST /api/v1/brew-sessions/{id}/notes`.
- `POST /api/v1/brew-sessions/{id}/attachments` and authenticated retrieval/removal routes.
- `GET /api/v1/brew-sessions/{id}/journal`.
- `GET /api/v1/brew-sessions/{id}/completion-audit`.
- `GET /api/v1/brew-sessions/{id}/export?format=json|html`.

Mutation responses must identify the resulting resource/state and concurrency version. Validation failures use `422`, authentication failures `401`, cross-owner or hidden-resource access the established non-disclosure response, invalid transitions/conflicts `409`, and unsupported media `415` where applicable.

Every mutation accepts the scoped operation identifier required by P3-FR-076. APIs must return enough stable identity and state to distinguish an original success replay from a new mutation. Event delivery, media transfer, journal rendering, or a dropped response cannot cause the client to invent success.

## 9. Persistence and migration contract

Phase 3 must use a single additive Alembic revision named `0003_phase3_brew_day_os` unless an accepted implementation ADR justifies a bounded series with one Phase 3 head.

The migration must:

- upgrade from `0002_phase2_brewing_core` without editing either accepted migration;
- preserve all Phase 1A and Phase 2 rows and constraints;
- provide explicit defaults/backfill/nullability for existing Mash-only sessions;
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
| One stage occurrence identity/order within a session; repeated occurrences remain distinct | Unique `(brew_session_id, plan_step_id, occurrence_number)` or accepted equivalent |
| Timer revision/replace links remain in the same session and cannot self-reference | Foreign keys/checks plus domain validation |
| Reminder satisfaction source belongs to the same session/stage and one requirement is not completed twice | Unique requirement identity plus transaction/domain validation |
| Measurement correction references the same type/session lineage and cannot self-reference or fork ambiguously | Foreign key/check/unique lineage plus domain validation |
| Scoped operation identity is unique and payload mismatch cannot overwrite the stored result | Unique actor/use-case/aggregate/operation key plus immutable result record |
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

- **P3-AC-010:** Full canonical stage flow completes with server-enforced ordering and requirements.
- **P3-AC-011:** Invalid transitions, duplicate commands, missing requirements, and stale versions fail without partial writes.
- **P3-AC-012:** Session/stage pause, resume, abort, skip, waiver, and completion rules match this specification.
- **P3-AC-013:** Three concurrent timers survive refresh and service restart with explainable elapsed time.
- **P3-AC-014:** Planned additions create timers/reminders; acknowledge/late/skip paths preserve plan and actual history.
- **P3-AC-015:** All required measurement types validate range/unit and produce truthful comparison states.
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
- **P3-AC-031:** File tests cover allowed image, invalid MIME/signature, executable, traversal filename, oversize, unauthorized retrieval, and completed-evidence removal.
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
| P3-AC-060 | P3-FR-016 through 019: repeated/extended/late stage execution | Database + domain + application | PostgreSQL integration + E2E | Planned order remains immutable; repeated stage has distinct occurrence; extension/late entry preserves old facts; invalid backward transition is atomic `409` | Rows/events and browser timeline for repeated mash rest, extension, late measurement and rejected backward transition |
| P3-AC-061 | P3-FR-028/029: reminder lifecycle and idempotent satisfaction | Database + domain + application | Concurrency integration + E2E | All required states are demonstrated; acknowledgement does not satisfy; one measurement completes one reminder once across two tabs/retry/duplicate delivery | Reminder state history, operation result and row counts |
| P3-AC-062 | Timer extension/replacement and revision history | Database + domain + application | Unit + PostgreSQL integration + E2E | Original duration/deadline survives extend/replace; current timer reconstructs from PostgreSQL; competing revisions yield one success | Timer/revision rows, events and browser recovery evidence |
| P3-AC-063 | P3-FR-076 through 078: operation identity, optimistic concurrency and atomic command sets | Database + application | Failure-injection + concurrency integration | Same key/same payload returns original result; mismatched payload is `409`; timeout retry creates no duplicate; injected failure leaves zero partial authoritative rows/events | Transaction row-count vectors and normalized response evidence |
| P3-AC-064 | P3-FR-085/086: event, audit and journal authority | Database + domain + application | Contract + integration + regeneration test | Typed event and separate audit are created once; journal/export regeneration is byte/semantically stable and creates no operational event; renderer failure does not roll back command | Event/audit IDs, schema versions, journal hashes/counts and failure evidence |
| P3-AC-065 | P3-FR-038/039: multi-time measurement provenance | Database + domain + API | Contract + PostgreSQL integration | Server assigns recorded time; bounded observed time/source persist; duplicate operation replays; distinct observation stays distinct; correction retains original | API payloads and complete correction/provenance chain |
| P3-AC-066 | P3-FR-059: CompletionAudit | Domain + application | Golden/unit + API + E2E | Rule-versioned counts/status reproduce from authoritative data; waiver/missing does not count measured; unresolved blockers shown truthfully | Golden audit JSON and human-readable completed/aborted summaries |
| P3-AC-067 | P3-FR-046: actual addition identity without Phase 6 mutation | Database + domain + application | Contract + PostgreSQL integration + E2E | Planned and actual identities/times/amounts/lots/substitution ref remain separate; inventory transaction/reservation counts do not change | Addition record/event plus before/after Phase 2 ledger vector |
| P3-AC-068 | P3-FR-058: media failure isolation | Application + infrastructure | Failure-injection integration + E2E | Failed/ambiguous/retried upload does not change core state, duplicate bytes, or block progression; orphan reconciliation works; unavailable bytes render placeholder | Session/timer/measurement vectors, storage/metadata counts and journal output |
| P3-AC-069 | P3-FR-079: authoritative failure recovery | Database + application + infrastructure | Restart/failure-injection E2E | Same session/stage/deadlines/reminders/measurements/actions return with no duplicate event after close/sleep/network/API/PostgreSQL/Redis cases; worker case is tested or proven N/A | Pre/post identity/state vectors, timer deadlines and event counts |
| P3-AC-070 | Required PostgreSQL invariant inventory | Database + domain | PostgreSQL integrity + migration test | Every section 9.1 rule has named enforcement and negative/concurrent proof; no critical invariant relies only on frontend | Invariant-to-constraint/test matrix and database failure output |
| P3-AC-071 | P3-FR-087: observability/reconstruction | Application + infrastructure | Integration + operational reconstruction | One injected timer/reminder/command failure is reconstructed by correlation and safe metrics/logs; sensitive payload scan is clean | Timeline, metric samples, correlation IDs and redaction scan |
| P3-AC-072 | P3-FR-066: voice transcription safety | Frontend + API + domain | Component + E2E | Parsed `52` from “five point two” remains draft, is visibly confirmed/corrected, and cannot pass pH validation as 52 | Mock transcript/preview plus rejected API and corrected committed value |
| P3-AC-073 | P3-FR-088: responsive-operation performance | Application + frontend + infrastructure | Bounded performance test | Approved p95 command/recovery/render targets pass on the recorded hardware and representative dataset; no full-history scan is required for active dashboard | Threshold approval, environment/data manifest and raw percentile results |

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
| P3-ADV-018 | Measurement is entered late against a completed stage | Bounded late-entry rule preserves observed/recorded times without reopening/re-timing the stage |
| P3-ADV-019 | Photo upload fails or response is ambiguous during boil | Core state is unchanged and operable; retry is idempotent; orphan reconciliation and journal unavailable placeholder work |
| P3-ADV-020 | Voice parser proposes pH `52` from “five point two” | No authoritative commit before confirmation; API rejects 52; corrected confirmed 5.2 follows normal validation |
| P3-ADV-021 | RecipeVersion mutation is attempted during an active session | Existing PostgreSQL immutability rejects mutation; session snapshot and journal remain unchanged |
| P3-ADV-022 | Interrupted BrewSession is reopened the next day | Same server-authoritative session and history load; timers show truthful elapsed/expired state; no generalized offline commands are replayed |
| P3-ADV-023 | Journal renderer/export fails then is retried | Brew-Day command remains committed; regeneration is idempotent and adds no BrewJournalEvent |
| P3-ADV-024 | CompletionAudit includes measured, waived, missing and not-applicable requirements | Counts/status are deterministic; only measured observations contribute to measurement completeness |
| P3-ADV-025 | Phase 1A and Phase 2 regression | Both accepted E2E flows and PostgreSQL invariants pass; Phase 3 adds no Phase 6 inventory mutation or Phase 4-10 table/surface |

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

The test plan must execute every P3-AC-060 through P3-AC-073 traceability row and every applicable P3-ADV-001 through P3-ADV-025 scenario. Failure-injection must occur at the authoritative boundary named by the scenario; merely mocking a successful response or restarting an unrelated container is insufficient. Any scenario marked not applicable requires architecture evidence and independent-review disposition.

SQLite may support fast tests but cannot substitute for PostgreSQL integrity evidence.

## 15. Required documentation and evidence artifacts

The implementation candidate is incomplete without:

- updated `README.md`, `docs/API.md`, `docs/TESTING.md`, `docs/domain/BREW_DAY_WORKFLOW.md`, architecture/data-model documentation, and operations/backup instructions;
- ADRs for any new material architecture decision;
- `docs/PHASE_3_IMPLEMENTATION_REPORT.md` containing scope mapping, migration summary, commands, actual results, limitations, and exact candidate SHA;
- `docs/evidence/PHASE_3_INDEPENDENT_ARCHITECTURE_AND_BREWING_ACCEPTANCE.md` completed by independent review;
- an explicit inventory proving no Phase 4–10 leakage; and
- a remediation traceability appendix mapping P3-FR-016 through 019, 028/029, 038/039, 046, 058/059, 066, and 076 through 088 to enforcement, tests, actual results, and evidence locations;
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
