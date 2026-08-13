# Phase 3 Specification Reconciliation Report

## 1. Executive determination

Candidate B is the correct authoritative base because it is the specification selected by the current Development Roadmap, is written against the accepted `v0.2.0-phase2` tag, preserves the accepted Phase 1A route and data compatibility, and aligns its Phase 4-10 boundaries with the current repository governance package.

Candidate B is not yet ready for the separate independent engineering-specification review. Five High-severity specification gaps leave material implementation decisions unresolved around real-world stage variation, reminder lifecycle, timer revision/recovery, command/transaction integrity, and event/journal authority. The gaps are remediable by bounded text amendments; Candidate B should not be replaced.

Candidate A is not an acceptable authoritative base. It was authored from proposed external PDFs rather than the accepted repository baseline, uses an obsolete phase map, pulls inventory consumption and an offline synchronization engine into Phase 3, requires an unaccepted transactional-outbox/worker architecture, and introduces BrewPlan/BrewBatch aggregates that do not match the accepted lineage or migration baseline. Selected controls from Candidate A should be incorporated textually into Candidate B after architectural filtering.

No candidate, roadmap, architecture, code, test, or configuration file was modified by this review. Phase 3 implementation remains unauthorized.

## 2. Environment verification

| Item | Verified value | Result |
|---|---|---|
| Repository | `B:\brewing-platform` (Git resolves mapped path as `//NazarioNAS/USB_3TB/brewing-platform`) | PASS |
| Branch | `main` | PASS |
| HEAD | `c3faa93ea1502db63798b8c0dcc10c02741fabf7` | PASS |
| Phase 2 tag | `v0.2.0-phase2` | PASS |
| Phase 2 tag target | `c3faa93ea1502db63798b8c0dcc10c02741fabf7` | PASS |
| Phase 0 evidence | `docs/PHASE_0_ACCEPTANCE_GATE.md` | PASS |
| Phase 1A evidence/tag | `docs/evidence/PHASE_1A_INDEPENDENT_ARCHITECTURE_ACCEPTANCE.md`; `v0.1.0-phase1a` | PASS |
| Phase 2 evidence | `docs/evidence/PHASE_2_INDEPENDENT_ARCHITECTURE_AND_BREWING_ACCEPTANCE.md` | PASS |
| Accepted ADRs | ADR-0001 through ADR-0011 | PASS |
| Calculation specification | `docs/architecture/BREWING_CALCULATION_ENGINE.md`, ADR-0004, ADR-0008 through ADR-0010 | PASS |
| Security architecture | `docs/security/SECURITY_ARCHITECTURE.md` | PASS |
| Domain/data model | `docs/domain/DOMAIN_MODEL.md`, `docs/architecture/DATA_MODEL.md` | PASS |
| Current roadmap | `docs/DEVELOPMENT_ROADMAP.md` | FOUND; modified and uncommitted |
| Current master plan | `docs/product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md` | FOUND; untracked |
| Candidate A | External path supplied by prompt | FOUND |
| Candidate B | `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` | FOUND; untracked |

### 2.1 Working-tree status

The accepted tag and `HEAD` match, but the worktree contains a pre-existing, unstaged governance package. This review preserved it.

Modified before this review:

- `CHANGELOG.md`
- `README.md`
- `docs/DEVELOPMENT_ROADMAP.md`
- `docs/architecture/AI_ARCHITECTURE.md`
- `docs/architecture/ARCHITECTURE_CHARTER.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/product/MVP_SCOPE_FREEZE.md`
- `docs/product/PRODUCT_REQUIREMENTS.md`
- `docs/product/PROJECT_CHARTER.md`

Untracked before this review:

- `docs/product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md`
- `docs/prompts/CODEX_PHASE_3_ENGINEERING_SPECIFICATION_INDEPENDENT_REVIEW_MASTER_PROMPT.md`
- `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`

This report is the only new review artifact.

### 2.2 Governance status caveat

The current roadmap names Candidate B as the normative Phase 3 gate, and the companion master-plan/architecture edits form a coherent intended governance package. Those current files are not part of the accepted `v0.2.0-phase2` tag and are not committed. This reconciliation therefore verifies their internal authority relationship but does not represent them as already accepted history. Candidate B cannot be independently reviewed as an authoritative committed specification until the governance package and approved remediation are installed through a controlled documentation commit.

## 3. Authority determination

The applicable precedence is:

1. Accepted Phase 0-2 repository baseline and ADRs.
2. Current intended master plan and architecture amendments, pending controlled acceptance.
3. Current Development Roadmap.
4. Candidate B at the roadmap's normative path.
5. Candidate A as external reference material only.

The roadmap points to:

`docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`

Candidate B occupies that exact repository-relative target. Candidate A cannot redefine the phase map or accepted aggregates merely because it is more detailed in some areas.

## 4. Roadmap phase-boundary matrix

The rule “later means mandatory but phase-gated” is present in the current roadmap/master-plan package. Future-compatible identifiers, provenance, contracts, and extension seams are permissible in Phase 3; later-phase operational behavior is not.

| Phase | Exact current functional boundary | Phase 3 consequence |
|---|---|---|
| Phase 3 - Brew-Day OS | Complete stage-aware worksheet; multiple persistent timers; hop/addition schedules; required-data reminders; mash, post-mash, pre-boil, OG, knockout, volume and temperature measurements; validation; planned-versus-actual deviations; confirmed voice boundary; event log; photos/notes; automatic journal; refresh recovery | Must be fully specified and accepted now |
| Phase 4 - Fermentation, Conditioning & Yeast | Gravity/temperature/pH tracking, curves, alerts, yeast lots/pitch history, milestones/additions, conditioning, readiness, troubleshooting | Phase 3 may record pitch facts and stable handoff identifiers only |
| Phase 5 - Quality, Packaging & Finished Beer | QA/QC, sanitation/CIP, calibration/maintenance, oxygen/stability, packaging sessions, carbonation, kegs/cans/bottles, draft/taps, cleaning, consumption | Phase 3 may retain general notes/photos and instrument/method provenance only |
| Phase 6 - Inventory Intelligence, Purchasing & Operations | Reorder/lead-time/demand/purchasing/freshness/waste, substitution intelligence, production calendars, deadlines, maintenance/calibration scheduling, capacity planning | Phase 3 may display snapshotted planned additions and record execution; it must not automate consumption/reservation conversion or purchasing |
| Phase 7 - Master Brewer Academy | Curriculum, assessment, science/math, BJCP/style, sensory/fault/triangle training, practical exercises, contextual instruction | Phase 3 may display static instructions already in the recipe/process snapshot; no learning engine |
| Phase 8 - Advanced Recipe Experiments & Sensory | Sensory-target formulation, advanced formulation/water/cost, A/B and split-batch experiments, structured sensory/panels/scoresheets, recipe iteration | Phase 3 deviations/notes cannot become sensory or experiment records |
| Phase 9 - Competition, Branding & Digital Menu | AI judge, judge disagreement, competition selection/calendar/entries/history/awards, naming, identity, logos/labels/tap badges, QR menu, live availability | No Phase 3 operational surface |
| Phase 10 - Brewer Knowledge Engine | Personal profile, historical analysis, correlations, experiment synthesis, evidence-ranked recommendations, intelligent substitutions, future-batch guidance | Phase 3 preserves trustworthy evidence and provenance only; no analysis/recommendation engine |

## 5. Candidate hash comparison

| Candidate | Path | Bytes | SHA-256 |
|---|---|---:|---|
| A | `C:\Users\Drago\Documents\ChatGPT\BREW PLATFORM\specifications\PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` | 49,191 | `8EFB9C1BAE34C8A28F8A67AB1D30D91E149AE065225AB5B4295CF330028E6322` |
| B | `B:\brewing-platform\docs\specifications\PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` | 33,966 | `B705F49527424E311FAC2C6FDE0DB9FF15B08E1F5D9C761FFEC34F6B506B169E` |

The documents are materially different, not line-ending variants.

## 6. Section-by-section structural comparison

| Section / capability | Candidate A | Candidate B | Roadmap phase owner | Architecture requirement | Recommended Phase 3 disposition |
|---|---|---|---|---|---|
| Document authority/baseline | References external proposed PDFs and says accepted baseline is not verified | Names exact accepted tag/commit and accepted evidence | Governance | Tagged baselines immutable; lower documents conform | KEEP_FROM_B |
| Phase outcome | Full Brew Day plus separate BrewPlan/BrewBatch concepts and offline operation | Full RecipeVersion-to-journal/yeast-pitch slice using accepted BrewSession seam | Phase 3 | Preserve Phase 1A/2 lineage | KEEP_FROM_B |
| BrewPlan aggregate/revisions | Requires new BrewPlan and BrewPlanRevision aggregates | Uses immutable plan snapshot owned by BrewSession | Phase 3 planning seam | Accepted model is RecipeVersion -> BrewSession; material aggregate change requires ADR | KEEP_FROM_B |
| BrewBatch aggregate | Creates separate BrewBatch at start | Preserves accepted BrewSession-centered execution and snapshot | Cross-phase lineage | Accepted domain/data model does not currently define BrewBatch | KEEP_FROM_B |
| Preflight/readiness | Detailed persisted ReadinessAssessment | `PLANNED -> READY` with preflight requirements and legacy route mapping | Phase 3 | Server enforcement and accepted route compatibility | KEEP_FROM_B |
| Session lifecycle | Created/active/interrupted/completing/completed/aborted | Planned/ready/active/paused/completed/aborted | Phase 3 | Recoverable, immutable terminal history | KEEP_FROM_B |
| Stage lifecycle | Supports repeat, extension, return, manual override and abort conceptually | Ordered single-primary stage with pause/skip/waiver/abort; repetition/extension/late capture unresolved | Phase 3 | Real stage-aware workflow without history corruption | MERGE |
| Canonical stages | Similar high-level stages with BrewPlan template | Explicit current canonical vocabulary ending at yeast pitch and Brew complete | Phase 3 | Current roadmap/Phase 4 boundary | KEEP_FROM_B |
| Timers | Durable deadlines, deadline revisions, delay/modify/cancel, restart/Redis/clock tests | Strong wall-clock versus active-time model, pause ownership, persisted UTC; extension/replacement/revision and some failure tests absent | Phase 3 | ADR-0006 persisted timers; Redis non-authoritative | MERGE |
| Reminders | MeasurementDefinition/request model but no complete reminder lifecycle | Required reminder semantics but no explicit lifecycle/ownership/atomic satisfaction model | Phase 3 | Master plan requires reminders/escalation | CONFLICT_REQUIRES_ARCHITECT_DECISION |
| Measurements | Detailed provenance, correction chains, multi-time capture, not-recorded outcome | Strong Decimal/unit/provenance/correction/waiver model compatible with baseline; server-received/source detail weaker | Phase 3 | ADR-0003, ADR-0008, accepted measurement schema | MERGE |
| Planned versus actual | Deterministic comparison and completion audit | Strong model identity, signed variance, tolerance, unit, truthful result states | Phase 3 | Deterministic calculation boundary | KEEP_FROM_B |
| Deviations | General deviation aggregate/status | Numeric and operational deviations; preserves corrected history; no AI diagnosis | Phase 3 | Append/version history | KEEP_FROM_B |
| Addition schedules | Strong planned/actual separation; also mandates inventory consumption/reconciliation | Planned timers and actual acknowledgement without inventory mutation; actual lot/substitution trace is weak | Phase 3 execution; automated consumption Phase 6 | Preserve intent/actual without premature ledger automation | MERGE |
| Inventory interaction | Requires reservation-to-consumption posting during Phase 3 | Explicitly prohibits automatic consumption/reservation conversion | Phase 6 | Phase 2 evidence says reservation consumption deferred | KEEP_FROM_B |
| Events | Typed/versioned envelope, operation/correlation/source fields, append-only rules | Journal-event vocabulary and stable chronology, but event envelope and audit distinction are underdefined | Phase 3 | Existing baseline separates `brew_journal_events` and `audit_events` | MERGE |
| Automatic journal | Completion audit plus event/history output | Strong automatic journal and JSON/HTML export | Phase 3 | Journal derived from authoritative execution facts | KEEP_FROM_B, CLARIFY authority |
| Completion audit/data completeness | Explicit rule-versioned completion audit and completeness accounting | Completion gates and journal, but no deterministic Brew-Day audit/completeness result | Phase 3 | Master plan explicitly requires Brew-Day audit | KEEP_FROM_A |
| Notes/photos | Notes, attachment references, security; limited failure detail | Strong upload security, metadata/bytes boundary, soft removal, journal inclusion | Phase 3 | File/object storage is platform concern | KEEP_FROM_B, ADD failure isolation |
| Voice entry | Controlled proposal/confirmation/validation sequence | Explicit untrusted draft -> preview -> confirm -> same API validation; no ambient audio | Phase 3 | Current AI architecture requires confirmation | KEEP_FROM_B |
| Refresh/reconnect recovery | Implements offline bundle and offline mutation queue | Server-authoritative GET recovery; explicitly no offline claim/sync engine | Phase 3 refresh/reconnect; offline-first unassigned | System architecture requires refresh/reconnect, not offline-first | KEEP_FROM_B |
| Command idempotency/concurrency | Precise key scope, replay mismatch and atomic-operation rules | Requires idempotency or equivalent and optimistic concurrency but leaves key/transaction semantics open | Phase 3 | PostgreSQL authority; repeated commands must be safe | KEEP_FROM_A after adapting to accepted model |
| API | Broad use-case API plus batch/sync endpoints | Versioned routes tied to accepted BrewSession API and Phase 1A adapters | Phase 3 | Versioned APIs and backward compatibility | KEEP_FROM_B |
| Database/migrations | Extensive generic invariants; assumes new aggregates/outbox | Exact additive `0003`, backfill/round-trip and Phase 1A/2 preservation | Phase 3 | Migrations mandatory; accepted rows preserved | KEEP_FROM_B plus selected invariants from A |
| Transactional outbox/worker | Mandatory for Phase 3 | Not required; current internal events remain transaction-local | Architecture decision, not roadmap capability | No accepted outbox ADR | REMOVE_FROM_PHASE_3 |
| Redis/background delivery | Recovery worker and at-least-once notification design | Redis/browser non-authoritative; in-app reminders only; exact background delivery not required | Phase 3 | ADR-0006, existing Redis support boundary | KEEP_FROM_B; test Redis loss |
| Security | Broad security/offline rules | Strong ownership, file security, voice, non-public routes, audit/logging | Cross-cutting | Accepted security architecture | KEEP_FROM_B |
| Observability | Specific reconstruction and operational metrics | Correlation-safe logging and runtime checks; Phase 3 metrics/reconstruction acceptance weak | Cross-cutting | Master plan mandates observability | KEEP_FROM_A, adapt without outbox assumptions |
| Backup/restore | Active-session and full recovery scenarios | Completed representative session including attachments, correction, timers and journal | Cross-cutting | Accepted restore evidence model | KEEP_FROM_B, add interrupted-session restore scenario if required |
| Performance/capacity | Requires documented thresholds/hardware/data set | No measurable interaction/recovery performance gate | Cross-cutting | Responsive mobile operation | KEEP_FROM_A as bounded acceptance threshold |
| Test/evidence | Extensive failure/concurrency/scenario matrix | Strong layered acceptance matrix and exact repository commands/evidence | Phase 3 | Deterministic acceptance | KEEP_FROM_B plus missing failure injections from A |
| Phase 4-10 boundary | Uses obsolete phase assignments and calls Phase 10 undefined | Matches current roadmap exactly | Governance | Later is mandatory but phase-gated | KEEP_FROM_B |

## 7. Required Phase 3 scope coverage

| Mandatory capability | Candidate B coverage | Result |
|---|---|---|
| Stage-aware Brew-Day worksheet | Sections 6.2, 6.3, 7.2, 10 | PARTIAL - repeat/extension/late entry ambiguity |
| Multiple persistent timers | Sections 6.4, 7.3, acceptance P3-AC-013 | PASS with recovery amendment required |
| Hop/addition schedules | P3-FR-021 through 024 | PARTIAL - actual lot/authorized substitution trace missing |
| Required-data reminders | P3-FR-025 through 027 | PARTIAL - lifecycle and satisfaction transaction undefined |
| Mash measurements | P3-FR-030 | PASS |
| Post-mash measurements | P3-FR-030 | PASS |
| Pre-boil measurements | P3-FR-030 | PASS |
| OG | P3-FR-030 | PASS |
| Knockout | P3-FR-030 | PASS |
| Volumes | P3-FR-030, 033 | PASS |
| Temperatures | P3-FR-030, 033 | PASS |
| Measurement validation | P3-FR-031 through 037 | PASS with provenance clarification |
| Planned versus actual | P3-FR-040 through 045 | PASS |
| Deviations | P3-FR-043 through 045 | PASS |
| Voice confirmation | P3-FR-060 through 065 | PASS |
| Event log | P3-FR-055 through 057 | PARTIAL - envelope/authority distinction missing |
| Photos/notes | P3-FR-050 through 054 | PASS with failure-isolation amendment required |
| Automatic journal | P3-FR-055 through 057 | PASS with derived-authority clarification |
| Browser refresh recovery | P3-FR-070 through 075 | PASS with broader failure-injection amendment required |

### 7.1 Phase 1A compatibility

Candidate B explicitly preserves the accepted vertical slice:

`Create Recipe -> Start Brew Session -> Mash Timer -> pH Reminder -> Record pH -> Mash Gravity Reminder -> Record Gravity -> Complete Mash -> Planned-versus-Actual -> Journal`

P3-FR-006 through 008 require legacy data and routes to remain readable/completable, and P3-AC-004 plus the required Playwright regression preserves Phase 1A and Phase 2. This is materially stronger and safer than Candidate A's generic dependency statement.

## 8. Future-phase leakage review

### 8.1 Candidate B

No operational Phase 4-10 leakage was found. The permitted seams are narrow and aligned:

- pitch facts without FermentationSession;
- notes/photos and instrument metadata without QA/packaging workflows;
- planned/actual addition acknowledgement without inventory mutation;
- static snapshot instructions without Academy state;
- deviations without sensory/experiment semantics;
- no Phase 9 surface; and
- trustworthy provenance without Knowledge Engine analysis.

### 8.2 Candidate A

Two operational scope-leakage items were found:

1. **Phase 6 inventory consumption leakage.** Candidate A requires reservation-to-consumption posting, actual inventory reconciliation, partial consumption, and completion blocking on inventory reconciliation. The accepted Phase 2 evidence explicitly defers reservation consumption, and the current roadmap assigns operational inventory intelligence/automation to Phase 6. Phase 3 may capture actual addition/lot facts, but it may not implement automatic inventory mutation.
2. **Unapproved offline synchronization platform.** Candidate A requires an offline bundle, durable client operation queue, offline timer/stage/measurement mutations, authorization-paused synchronization and conflict UI. The accepted architecture requires server-authoritative refresh/reconnect recovery; the current Candidate B explicitly prohibits claiming offline support or building an offline-first synchronization engine. This is material platform scope beyond Phase 3.

Candidate A's Phase 4-10 table also mislabels the roadmap: it assigns quality/CAPA/cleaning/calibration to Phase 4, Sensory/Competition to Phase 6, branding/menu to Phase 7, Academy to Phase 8, Knowledge Engine to Phase 9, and calls Phase 10 undefined. Although those rows mostly prohibit rather than implement the capabilities, importing them would corrupt governance.

## 9. Legitimate Phase 3 requirements missing or materially weaker in Candidate B

Eleven Candidate A controls belong legitimately to Phase 3 or to mandatory cross-cutting architecture and should be incorporated selectively.

### RL-001 - Repeated stages, stage extensions and late/out-of-order capture

**REQUIREMENT:** Preserve planned order while supporting repeated stage instances, extensions, controlled return, and late recording against the correct stage without reopening or rewriting it.
**SOURCE_SECTION:** Candidate A sections 8.3 and 18.
**WHY_PHASE_3_REQUIRES_IT:** Real mashes may add/repeat rests; cooling and additions can interrupt planned chronology; the reconciliation prompt explicitly requires repeated stages, extensions, and out-of-order measurements.
**CANDIDATE_B_GAP:** Candidate B enforces one ordered instance per canonical stage and does not state how repetition or late observation entry works.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add a stage-instance identity and `plan_step_id`; allow authorized repeat/extension/late-entry commands that append actual chronology and reason without changing the plan or terminal stage facts.

### RL-002 - Exact idempotency contract

**REQUIREMENT:** Every retryable mutation has a persisted, actor/use-case/aggregate-scoped operation ID; same ID and same semantic payload returns the prior result, while same ID with different payload returns conflict.
**SOURCE_SECTION:** Candidate A section 9.1.
**WHY_PHASE_3_REQUIRES_IT:** Double clicks, timeouts, reconnect and multi-tab commands otherwise create duplicate measurements, timer actions and events.
**CANDIDATE_B_GAP:** “Idempotency keys or equivalent” leaves storage, scope, mismatch and retention undecided.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Replace the open alternative with the exact persisted semantics above and require a unique PostgreSQL constraint plus retention exceeding the accepted retry/recovery window.

### RL-003 - Atomic command boundaries

**REQUIREMENT:** State transition, authoritative record, reminder/timer effect, journal event and audit event caused by one command commit or roll back together.
**SOURCE_SECTION:** Candidate A section 9.2.
**WHY_PHASE_3_REQUIRES_IT:** Partial Mash completion, measurement-without-reminder-close, or timer-without-event corrupts the journal and recovery projection.
**CANDIDATE_B_GAP:** Acceptance rejects partial writes but the specification does not define the atomic record set per command.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add a normative transaction table for session/stage transitions, timer actions, measurements/corrections, reminders, additions, media metadata, abort and completion.

### RL-004 - Typed event envelope and audit distinction

**REQUIREMENT:** Journal events carry stable type/schema version, session/stage IDs, occurred/recorded timestamps, actor/source, operation ID, correlation/causation IDs and validated payload; domain journal and security audit remain separate records.
**SOURCE_SECTION:** Candidate A section 7.6.
**WHY_PHASE_3_REQUIRES_IT:** The accepted baseline already separates `brew_journal_events` and `audit_events`; safe ordering, retry deduplication and later provenance need a stable envelope.
**CANDIDATE_B_GAP:** Candidate B defines chronology and content but not the envelope or explicit non-equivalence to audit.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add the envelope and state that the automatic journal is a projection/export of authoritative BrewJournalEvents and linked records, never a second writable history.

### RL-005 - Timer deadline revision, extension and replacement

**REQUIREMENT:** Delay/extend/replace preserves original deadline/duration, revision history, actor, reason and relationship to the replacement timer.
**SOURCE_SECTION:** Candidate A sections 7.7, 8.4 and 11.
**WHY_PHASE_3_REQUIRES_IT:** Real boil/addition timers are extended or replaced; mutating the original erases planned-versus-actual evidence.
**CANDIDATE_B_GAP:** Candidate B supports pause/resume/cancel/acknowledge but does not define extension/replacement.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add `extend` and `replace` commands using append-only TimerRevision/TimerEvent history and prohibit in-place erasure of the former deadline.

### RL-006 - Multi-time measurement provenance

**REQUIREMENT:** Preserve observed-at, recorded-at/server-received-at, actor, origin/entry method and correction reason; do not rewrite observed time on delayed entry.
**SOURCE_SECTION:** Candidate A section 7.9.
**WHY_PHASE_3_REQUIRES_IT:** Back-entered or retried observations otherwise become indistinguishable from contemporaneous capture.
**CANDIDATE_B_GAP:** Candidate B has observed-at and recorded-at but does not clearly define trusted server receipt/source semantics.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Define server-assigned `recorded_at`, bounded user-observed `observed_at`, entry source and clock-skew validation; require both in journal output.

### RL-007 - Deterministic Brew-Day completion audit

**REQUIREMENT:** Completion produces a rule-versioned derived audit of required recorded/waived/missing items, open deviations, timer states, addition status, lineage, journal integrity and unresolved issues.
**SOURCE_SECTION:** Candidate A section 7.11.
**WHY_PHASE_3_REQUIRES_IT:** The master plan requires a Brew-Day audit, not only an event export.
**CANDIDATE_B_GAP:** Candidate B has completion rules and journal, but no explicit completeness/audit result.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add a read-only/derived CompletionAudit contract and acceptance case; waivers reduce truthful completeness and never masquerade as measurements.

### RL-008 - Failure and restore matrix

**REQUIREMENT:** Deterministic behavior for browser close/reopen, sleep, network loss/ambiguous response, API/worker/Redis/PostgreSQL restart, delayed/duplicate delivery, client skew/DST, abort and active-session restore.
**SOURCE_SECTION:** Candidate A sections 18 and 21.
**WHY_PHASE_3_REQUIRES_IT:** Timer and command correctness is a core differentiator and failure behavior must be independently testable.
**CANDIDATE_B_GAP:** Candidate B tests refresh and service restart but omits several required injections.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add acceptance cases for each failure while retaining Candidate B's server-authoritative, non-offline boundary.

### RL-009 - Phase 3 observability and reconstruction

**REQUIREMENT:** Metrics and correlated logs make timer lag, recovery, conflicts, duplicate suppression, reminder satisfaction and journal generation reconstructable without logging private note/measurement contents.
**SOURCE_SECTION:** Candidate A section 16.
**WHY_PHASE_3_REQUIRES_IT:** Observability is mandatory cross-cutting master-plan scope and Brew-Day failures must be diagnosable.
**CANDIDATE_B_GAP:** Candidate B requires safe IDs/logging but no Phase 3 metric/reconstruction acceptance.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add bounded metrics and one reconstruction acceptance scenario; omit Candidate A's outbox-specific metrics unless an ADR later accepts an outbox.

### RL-010 - Explicit database invariant inventory

**REQUIREMENT:** PostgreSQL enforces ownership FKs, valid enum/check domains, one active/paused session per owner, stage instance/order uniqueness, timer/reminder ownership, correction lineage, command-operation uniqueness and terminal-history protection where feasible.
**SOURCE_SECTION:** Candidate A sections 6 and 19.
**WHY_PHASE_3_REQUIRES_IT:** The accepted architecture uses PostgreSQL aggressively and the review prompt forbids frontend-only invariants.
**CANDIDATE_B_GAP:** Candidate B asks generally for “constraints/indexes needed” without enumerating which critical rules must reach the database.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add a normative invariant-to-enforcement table and corresponding PostgreSQL acceptance tests.

### RL-011 - Actual addition ingredient/lot trace

**REQUIREMENT:** Addition acknowledgement preserves planned addition ID, actual ingredient identity, actual lot when known, actual quantity/unit/time, and accepted Phase 2 substitution reference without mutating inventory.
**SOURCE_SECTION:** Candidate A sections 7.2, 10 and 18, filtered to remove consumption automation.
**WHY_PHASE_3_REQUIRES_IT:** Brew-Day actuals must remain distinct from recipe intent, and Phase 2 already owns ingredient/lot/substitution identity.
**CANDIDATE_B_GAP:** P3-FR-023 records time/actor/quantity/unit/note but does not explicitly preserve actual ingredient, lot or substitution identity.
**RECOMMENDED_TEXTUAL_REMEDIATION:** Add those reference fields and state explicitly that acknowledgement has zero inventory-ledger effect in Phase 3.

## 10. Candidate B defect review

### PH3-REC-B-001

**SEVERITY:** HIGH
**TITLE:** Stage model cannot deterministically represent repeated/extended stages and late observations
**AFFECTED SECTION:** 6.2, 6.3, 7.2, 8
**OBSERVATION:** The specification defines one ordered canonical stage instance and one primary active stage. It does not define repeat instances, controlled return, extension, or late measurement entry against a completed stage.
**IMPACT:** Implementers must either reject valid brewing behavior or mutate/reopen history inconsistently.
**REMEDIATION:** Apply RL-001 and add E2E cases for repeated mash rest, extended stage, late addition and late measurement.
**BLOCKS REVIEW READINESS:** YES

### PH3-REC-B-002

**SEVERITY:** HIGH
**TITLE:** Reminder lifecycle, ownership and idempotent satisfaction are undefined
**AFFECTED SECTION:** 5.1, 7.3, 8, 9, 13
**OBSERVATION:** P3-FR-025 requires a status but no lifecycle is normative. It is unclear whether acknowledgement differs from completion, how expiration/cancellation works, or how one MeasurementRecord atomically satisfies the correct reminder once across tabs/retries.
**IMPACT:** Duplicate/incorrect reminder completion and stage-gate corruption.
**REMEDIATION:** Define `SCHEDULED -> DUE -> ACKNOWLEDGED|COMPLETED|SKIPPED|EXPIRED|CANCELLED` (or explicitly equivalent states), ownership/reference rules, unique active requirement identity, and atomic measurement-to-reminder satisfaction.
**BLOCKS REVIEW READINESS:** YES

### PH3-REC-B-003

**SEVERITY:** HIGH
**TITLE:** Timer modification and required failure recovery are incomplete
**AFFECTED SECTION:** 6.4, 7.3, 7.8, acceptance P3-AC-013/024
**OBSERVATION:** Persisted wall/active-time semantics are strong, but extension/replacement history is absent and acceptance does not explicitly exercise browser close/reopen, sleep, network interruption, worker restart if used, Redis loss, delayed/duplicate delivery, expired discovery, client skew/DST or PostgreSQL interruption.
**IMPACT:** A conforming implementation could still erase timer intent or fail under required operational conditions.
**REMEDIATION:** Apply RL-005 and RL-008 without adding offline mutation authority.
**BLOCKS REVIEW READINESS:** YES

### PH3-REC-B-004

**SEVERITY:** HIGH
**TITLE:** Command idempotency, transaction boundaries and database enforcement remain material implementation decisions
**AFFECTED SECTION:** 7.8, 8, 9, 12, acceptance P3-AC-011/017/023
**OBSERVATION:** “Idempotency keys or equivalent” and general no-partial-write tests do not define replay semantics, mismatched payload behavior, key retention, atomic record sets or required PostgreSQL constraints.
**IMPACT:** Double submissions and ambiguous timeouts can create duplicate measurements/events or partial state despite nominal compliance.
**REMEDIATION:** Apply RL-002, RL-003 and RL-010.
**BLOCKS REVIEW READINESS:** YES

### PH3-REC-B-005

**SEVERITY:** HIGH
**TITLE:** Brew event, automatic journal and security audit authority are not sharply separated
**AFFECTED SECTION:** 5.1, 7.6, 7.9, 8
**OBSERVATION:** The specification calls journal events execution facts and also requires a final immutable journal, but lacks a typed/versioned envelope and does not explicitly preserve the accepted separation between `brew_journal_events` and `audit_events`.
**IMPACT:** Event ordering, deduplication, audit purpose and journal derivation may diverge between implementations.
**REMEDIATION:** Apply RL-004 and require one journal-projection reconstruction test.
**BLOCKS REVIEW READINESS:** YES

### PH3-REC-B-006

**SEVERITY:** MEDIUM
**TITLE:** Actual addition identity and lot lineage are incomplete
**AFFECTED SECTION:** P3-FR-021 through 024
**OBSERVATION:** Actual time/actor/quantity/unit/note are required, but actual ingredient, lot and accepted substitution reference are not.
**IMPACT:** The system can show that “an addition” occurred without preserving exactly what was added.
**REMEDIATION:** Apply RL-011 while retaining zero Phase 3 inventory mutation.
**BLOCKS REVIEW READINESS:** NO independently; disposition required

### PH3-REC-B-007

**SEVERITY:** MEDIUM
**TITLE:** Media failure isolation and orphan lifecycle lack requirements and tests
**AFFECTED SECTION:** P3-FR-051 through 057, P3-AC-031/041/053
**OBSERVATION:** Security and successful persistence are covered, but failed upload, retry after ambiguous response, orphan bytes/metadata, unavailable media during journal/export and storage outage isolation are not.
**IMPACT:** A non-critical photo can block or corrupt core Brew-Day workflow or leak orphaned media.
**REMEDIATION:** State that media failure cannot mutate/block core session state; define idempotent upload identity, orphan cleanup/reconciliation and journal placeholder behavior; add failure tests.
**BLOCKS REVIEW READINESS:** NO independently; disposition required

### PH3-REC-B-008

**SEVERITY:** MEDIUM
**TITLE:** Brew-Day completion audit and data-completeness result are missing
**AFFECTED SECTION:** 3, 7.6, 13, 16
**OBSERVATION:** Completion gates and journal exist, but the master-plan Brew-Day audit is not a defined reproducible artifact/projection.
**IMPACT:** Missing, waived and completed requirements can be summarized inconsistently.
**REMEDIATION:** Apply RL-007.
**BLOCKS REVIEW READINESS:** NO independently; disposition required

### PH3-REC-B-009

**SEVERITY:** MEDIUM
**TITLE:** Recovery test matrix does not cover all authoritative failure modes
**AFFECTED SECTION:** 7.8, P3-AC-013/024/041/042/053
**OBSERVATION:** Refresh and service restart are covered, but not every required close/sleep/network/ambiguous-response/Redis/PostgreSQL/clock case.
**IMPACT:** Recovery claims may pass while important real failure paths remain untested.
**REMEDIATION:** Apply RL-008 and identify whether any worker exists; if none, mark worker-restart scenario not applicable with architecture evidence rather than simulating one.
**BLOCKS REVIEW READINESS:** NO independently; disposition required

### PH3-REC-B-010

**SEVERITY:** MEDIUM
**TITLE:** Phase 3 observability lacks measurable reconstruction criteria
**AFFECTED SECTION:** P3-FR-083, acceptance section F
**OBSERVATION:** Safe correlation logging exists, but timer lag, reminder satisfaction, command conflict/deduplication and recovery behavior have no metric/reconstruction gate.
**IMPACT:** Brew-Day failures may be hard to diagnose after the fact.
**REMEDIATION:** Apply RL-009.
**BLOCKS REVIEW READINESS:** NO independently; disposition required

### PH3-REC-B-011

**SEVERITY:** LOW
**TITLE:** Responsive-operation performance is not measurable
**AFFECTED SECTION:** 10, 13.E/F
**OBSERVATION:** Viewports and builds are tested, but no documented response/recovery/bundle-size threshold, dataset or hardware context is required.
**IMPACT:** “Usable” can be asserted without a repeatable performance baseline.
**REMEDIATION:** Require the work package to propose and obtain approval for bounded p95 command/dashboard/recovery targets and record environment/data volume.
**BLOCKS REVIEW READINESS:** NO

### PH3-REC-B-012

**SEVERITY:** ADVISORY
**TITLE:** Preserve Candidate B's strong compatibility and anti-leakage structure
**OBSERVATION:** Exact baseline commit, legacy route adapter rule, additive migration/round-trip, Phase 1A/2 E2E regression, voice confirmation, media security and current Phase 4-10 map are particularly strong.
**RECOMMENDATION:** Amend in place; do not replace with Candidate A or broaden scope.

## 11. Candidate A defect review

### PH3-REC-A-001

**SEVERITY:** HIGH
**TITLE:** Candidate A asserts the wrong baseline context
**OBSERVATION:** It says source PDFs are proposed, repository baseline is unverified and Phase 0-2 exits are not verified, while the authoritative repository has accepted tags/evidence.
**IMPACT:** It cannot govern migration, compatibility or acceptance against the real codebase.
**DISPOSITION:** Do not use as base.

### PH3-REC-A-002

**SEVERITY:** HIGH
**TITLE:** Candidate A's Phase 4-10 ownership map contradicts the current roadmap
**OBSERVATION:** It misassigns Quality, Inventory Intelligence, Academy, Sensory/Experiments, Competition/Branding/Menu and Knowledge Engine and calls Phase 10 undefined.
**IMPACT:** Importing its boundary table would corrupt accepted sequencing.
**DISPOSITION:** Retain Candidate B's table; extract only phase-neutral controls.

### PH3-REC-A-003

**SEVERITY:** HIGH
**TITLE:** Candidate A prematurely implements inventory consumption/reconciliation
**OBSERVATION:** It requires reservation-to-consumption posting and completion blocking on inventory reconciliation.
**IMPACT:** Conflicts with Phase 2 accepted deferral and Phase 6 ownership.
**DISPOSITION:** Remove from Phase 3; preserve actual addition/lot facts only.

### PH3-REC-A-004

**SEVERITY:** HIGH
**TITLE:** Candidate A introduces an unauthorized offline synchronization engine
**OBSERVATION:** It requires offline mutation queueing, conflict resolution and authorization-paused synchronization.
**IMPACT:** Material new platform architecture, security and testing scope beyond refresh/reconnect recovery.
**DISPOSITION:** Do not import; retain Candidate B's truthful server-authoritative reconnect boundary.

### PH3-REC-A-005

**SEVERITY:** HIGH
**TITLE:** Candidate A mandates an unaccepted transactional outbox/background worker architecture
**OBSERVATION:** No accepted ADR requires an outbox for current in-process Brew-Day events.
**IMPACT:** Introduces infrastructure and delivery semantics outside the accepted modular-monolith baseline.
**DISPOSITION:** Architectural hook only if a future concrete durable side effect justifies an ADR; not Phase 3 default.

### PH3-REC-A-006

**SEVERITY:** HIGH
**TITLE:** Candidate A replaces accepted execution lineage with unapproved BrewPlan/BrewBatch aggregates
**OBSERVATION:** The accepted domain model and Phase 1A/2 implementation use RecipeVersion -> BrewSession. Candidate A mandates new aggregate roots without an ADR or backfill/adapter design.
**IMPACT:** Material schema/domain rewrite and Phase 1A regression risk.
**DISPOSITION:** Keep Candidate B's BrewSession snapshot model unless an independent ADR later proves a new aggregate is necessary.

### PH3-REC-A-007

**SEVERITY:** ADVISORY
**TITLE:** Candidate A contains useful phase-neutral engineering controls
**OBSERVATION:** Its idempotency semantics, transaction list, event envelope, timer revision history, completion audit, failure matrix, invariant matrix and observability requirements materially strengthen Candidate B when adapted to the accepted model.
**DISPOSITION:** Extract only the eleven requirements in section 9; do not merge documents wholesale.

## 12. Recommended authoritative base

Candidate B is selected as the authoritative base.

Reasons:

- It is the exact path selected by the current roadmap.
- It names the accepted tag and commit.
- It preserves existing Phase 1A data, routes and E2E behavior.
- It aligns with ADR-0001 through ADR-0011.
- It uses the accepted BrewSession/plan-snapshot seam rather than inventing replacement aggregates.
- It respects the accepted Phase 2 inventory-consumption deferral.
- It matches the current Phase 4-10 boundaries.
- It provides an additive migration, PostgreSQL evidence, UI/security/media controls and a deterministic acceptance matrix.
- Its defects are bounded omissions, not a fundamentally unsuitable architecture.

## 13. Required remediation plan for Candidate B

Do not apply these changes in this reconciliation pass.

| # | Classification | Required change before independent review |
|---:|---|---|
| 1 | ALIGN_WITH_ARCHITECTURE | Keep the accepted BrewSession-centered lineage and plan snapshot; explicitly reject Candidate A's mandatory BrewPlan/BrewBatch aggregates absent a future ADR |
| 2 | ADD / ADD_INVARIANT | Define repeated stage instances, extensions, controlled return and late measurement/addition entry while preserving plan and actual chronology |
| 3 | ADD / ADD_INVARIANT | Add normative reminder states, ownership, unique requirement identity and atomic measurement satisfaction |
| 4 | CLARIFY / ADD_INVARIANT | Add timer extension/replacement/deadline-revision history and deterministic abort/stage-completion effects |
| 5 | ADD_INVARIANT | Define persisted idempotency operation scope, replay result, payload mismatch conflict, retention and PostgreSQL uniqueness |
| 6 | ALIGN_WITH_ARCHITECTURE | Add exact transaction boundaries joining domain mutation, timer/reminder effect, journal and audit while not mandating an outbox |
| 7 | ADD / CLARIFY | Define typed/versioned BrewJournalEvent envelope and explicitly distinguish journal/domain history from security audit; journal/export is derived |
| 8 | ADD | Add actual addition ingredient, lot and authorized substitution references with zero Phase 3 inventory mutation |
| 9 | ADD | Add server-received/source semantics to measurement provenance and bounded late-entry/clock-skew rules |
| 10 | ADD | Add deterministic Brew-Day CompletionAudit/data-completeness projection |
| 11 | ADD_ACCEPTANCE_TEST | Add close/reopen, sleep, network/ambiguous response, Redis loss, API/worker-if-present/PostgreSQL restart, duplicate delivery, reconnect expiry and DST/skew tests |
| 12 | ADD_ACCEPTANCE_TEST | Add media upload failure/retry/orphan/unavailable-byte isolation tests |
| 13 | ADD_ACCEPTANCE_TEST | Add reminder double-completion/two-tabs and timer extend/replace concurrency cases |
| 14 | ADD / ADD_ACCEPTANCE_TEST | Add Phase 3 observability metrics and one post-incident reconstruction test, without logging sensitive payloads |
| 15 | CLARIFY | Require proposed and approved measurable performance thresholds with hardware/data context |
| 16 | ALIGN_WITH_ROADMAP | Preserve Candidate B's Phase 4-10 table and explicit no-offline/no-consumption/no-AI/no-public/no-deployment boundary unchanged except for clarifying permitted seams |
| 17 | DOCUMENTATION | After Product Owner/Architect approval, commit the entire coherent governance package intentionally; do not present untracked documents as accepted authority |

## 14. Governance recommendation for Candidate A

`SUPERSEDED`

Candidate A should remain outside the authoritative repository and be treated only as a hash-identified reconciliation source until the approved Candidate B amendments are committed. After the Product Owner confirms that the eleven legitimate controls have been dispositioned, Candidate A may be archived or deleted through a separate approval. It should never be installed wholesale or represented as an accepted specification.

## 15. Final readiness determination

Reconciliation succeeds in choosing the authoritative base, but specification remediation is required. Candidate B should be amended through an architect-owned change, reviewed against this report, and committed with the governing roadmap/master-plan package. Only then should a clean independent Phase 3 engineering-specification review run.

The result is not authorization to implement Phase 3.

RECONCILIATION_REVIEW=REMEDIATION_REQUIRED
REPOSITORY_VALID=YES
PHASE_2_BASELINE_VERIFIED=YES
ROADMAP_AUTHORITY_VERIFIED=YES
CANDIDATE_A_FOUND=YES
CANDIDATE_B_FOUND=YES
CANDIDATE_A_SHA256=8EFB9C1BAE34C8A28F8A67AB1D30D91E149AE065225AB5B4295CF330028E6322
CANDIDATE_B_SHA256=B705F49527424E311FAC2C6FDE0DB9FF15B08E1F5D9C761FFEC34F6B506B169E
AUTHORITATIVE_BASE=CANDIDATE_B
PHASE_3_REQUIREMENTS_MISSING_FROM_BASE=11
FUTURE_PHASE_LEAKAGE_ITEMS=2
CRITICAL_FINDINGS=0
HIGH_FINDINGS=11
MEDIUM_FINDINGS=5
LOW_FINDINGS=1
ADVISORY_FINDINGS=2
SPEC_REMEDIATION_REQUIRED=YES
PHASE_3_SPEC_READY_FOR_INDEPENDENT_REVIEW=NO
PHASE_3_IMPLEMENTATION=NOT_AUTHORIZED
