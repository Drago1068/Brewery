# Phase 3 Engineering Specification Final Independent Re-Review

## 1. Decision

`PHASE_3_SPEC_RE_REVIEW=FAIL`

The remediated specification is materially stronger, and five of the prior nine findings are independently closed. Four prior findings are reopened because their revised text still leaves material behavior to implementation choice. The remaining ambiguities affect accepted-data migration, stage-return identity, waiver and terminal-state behavior, and late-entry validation. Under the governing review policy, the three P1 findings and one implementation-affecting P2 finding block implementation authorization.

## 2. Review identity

| Field | Verified value |
|---|---|
| Repository | `//NazarioNAS/USB_3TB/brewing-platform` (`B:\brewing-platform`) |
| Branch | `main` |
| Reviewed commit | `f7904e8b2a8eecb6cafe1da2a04c3b648902c242` |
| Initial worktree | Clean |
| Phase 2 tag | `v0.2.0-phase2` |
| Phase 2 tag target | `c3faa93ea1502db63798b8c0dcc10c02741fabf7` |
| Authoritative specification | `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` |
| Specification SHA-256 | `1CB2ED8AAFEBBA2E5F613E28CEE7A86F6086C04899F9646CF14088FC18EA9659` |

The review environment passed every mandatory precondition. The historical independent review was treated as point-in-time FAIL evidence, and the remediation closure matrix was treated only as a claim to verify.

## 3. Review scope and governing baseline

This was a fresh, read-only delta review against the accepted Phase 0-2 architecture. The roadmap, master plan, product requirements, project charter, architecture charter, system and AI architecture, calculation engine, data and domain models, Brew-Day workflow, API, testing, unit/rounding, security, database/operations documentation, ADR-0001 through ADR-0011, Phase 1A acceptance, Phase 2 acceptance, migrations, domain models, application services, and compatibility routes were inspected.

Accepted architecture was not reopened. The specification continues to preserve the modular monolith, four-layer separation, PostgreSQL authority, nonauthoritative Redis/browser state, deterministic Decimal calculations, UTC authority, immutable RecipeVersion and completed observations, append-only inventory, `RecipeVersion -> BrewSession` lineage, and the Phase 3 yeast-pitch boundary.

## 4. Prior-finding closure matrix

| Prior finding | Result | Independent basis |
|---|---|---|
| `P3SPEC-R01` | `REOPENED` | `phase3-plan-v1` defines defaults and major source mappings, but accepted existing-session backfill and conflicting source/canonical order remain undecidable. |
| `P3SPEC-R02` | `REOPENED` | Stage-instance targeting and repeat occurrence identity are closed, but `return` may create either a new occurrence or a distinct undefined “bounded continuation.” |
| `P3SPEC-R03` | `REOPENED` | The cross-state matrix closes session pause/resume/abort/complete effects, but the stage `ABORTED` transition and waiver eligibility/authority remain undefined. |
| `P3SPEC-R04` | `CLOSED` | The specification fixes timing basis, offset, reference occurrence, clock basis, Phase 2 conversion, invalid cases, revision, and planned/actual variance. |
| `P3SPEC-R05` | `REOPENED` | Process-point measurement context is closed, but required bounded back-entry and late-entry validation has no actual bound or terminal-session rule. |
| `P3SPEC-R06` | `CLOSED` | `phase3-operation-v1` defines scope, canonicalization, fingerprint, result, retention, lifetime tombstone, replay, mismatch, concurrency, and atomicity. |
| `P3SPEC-R07` | `CLOSED` | Media type, size, count, quota, metadata, serving, rate, retention, failure-isolation, and orphan controls are fixed and testable. |
| `P3SPEC-R08` | `CLOSED` | Synchronizer-token issuance, session binding, rotation, mutation coverage, origin/referrer validation, ordering, and zero-mutation failure are explicit. |
| `P3SPEC-R09` | `CLOSED` | The reference profile, dataset, sampling method, numeric p95 thresholds, raw evidence, and bounded-query requirement are measurable. |

Totals: `CLOSED=5`, `REOPENED=4`.

## 5. Findings

### P3SPEC-RR-001

FINDING_ID=P3SPEC-RR-001

SEVERITY=P1 / HIGH

TITLE=Execution-plan ordering and accepted-session backfill are not deterministic

SPECIFICATION_REFERENCE=Sections 6.1.1, 7.1 P3-FR-006/008/009, 9, P3-AC-022/074, P3-ADV-026

BASELINE_REFERENCE=`0001_phase1a.py` existing `brew_sessions`, `brew_stages`, `brew_timers`, measurements and notifications; `0002_phase2_brewing_core.py` process-step sequence; Phase 1A and Phase 2 accepted evidence

OBSERVATION=The specification says source rows are ordered by explicit sequence and stable UUID, calls the stage vocabulary canonically ordered, stores predecessor sets, and rejects an “irreconcilable order,” but never supplies the rule that reconciles source sequence with canonical macro-stage order or constructs predecessor sets. More importantly, new BrewSession materialization is specified, while the required migration/backfill for already persisted planned, active, or completed Phase 1A Mash sessions is only required to be “explicit”; the actual mapping of existing stage/timer/reminder identities and historical statuses into the immutable Phase 3 plan is absent.

FAILURE_SCENARIO=One implementation reorders an accepted Phase 2 `BOIL(sequence=0), MASH(sequence=1)` source into canonical order, another rejects it as irreconcilable, and a third honors source order. During migration, one team preserves the existing Mash stage as the Phase 3 stage instance while another creates a replacement plan/stage row and links history differently. All can cite the current text.

IMPLEMENTATION_AMBIGUITY=The canonical ordering/predecessor algorithm, invalid-order oracle, and status-by-status legacy backfill vector are not specified.

IMPACT=Logical plan hashes, stage IDs, predecessor enforcement, migration rows, API recovery, journal lineage, and Phase 1A regression behavior can differ across conforming implementations.

REQUIRED_REMEDIATION=Add a normative ordering/predecessor algorithm covering source sequence versus canonical vocabulary, repeats, defaults, and invalid order. Add a migration table for existing `PLANNED`, `ACTIVE`, and `COMPLETED` Phase 1A sessions specifying preservation/reuse of session, stage, timer, notification, measurement, and event identities; generated plan provenance; status mapping; and forbidden fabrication.

ENFORCEMENT_LAYER=MULTIPLE: DATABASE + DOMAIN + APPLICATION + MIGRATION + TEST

BLOCKS_IMPLEMENTATION=YES

CONFIDENCE=HIGH

### P3SPEC-RR-002

FINDING_ID=P3SPEC-RR-002

SEVERITY=P2 / MEDIUM

TITLE=Controlled return permits two incompatible occurrence models

SPECIFICATION_REFERENCE=Sections 6.2, 7.2 P3-FR-016/019, 8 return route, P3-AC-060, P3-ADV-017/027

BASELINE_REFERENCE=ADR-0003 immutable history; accepted Phase 1A `BrewStage` identity; Phase 3 rule that completed instances cannot reopen

OBSERVATION=A return command is allowed to create “a new stage instance or append a bounded continuation,” and the API repeats the alternative as a “new occurrence/continuation record.” Runtime repeats otherwise have a precise new `stage_instance_id`, shared `plan_step_id`, and incremented occurrence number. No continuation entity, identity, state machine, timer/reminder ownership, ordering rule, completion rule, or database invariant is defined.

FAILURE_SCENARIO=After `MASH` completes, one implementation handles return by creating occurrence 2 with new timers/reminders. Another appends a continuation to the completed occurrence and attributes later measurements and timers to the original `stage_instance_id`. Both preserve the original completion timestamp yet expose incompatible recovery state and journal lineage.

IMPLEMENTATION_AMBIGUITY=Whether return is always a new occurrence or may use a second model is left to the implementer, and the second model has no contract.

IMPACT=Command targets, uniqueness constraints, timer/reminder ownership, planned-versus-actual chronology, recovery payloads, and test oracles diverge.

REQUIRED_REMEDIATION=Select one model. Prefer requiring every return to create a new stage instance/occurrence linked to the source completed instance. If continuation remains allowed, fully specify its identity, persistence, state, ownership, ordering, completion, concurrency, and acceptance behavior.

ENFORCEMENT_LAYER=MULTIPLE: DATABASE + DOMAIN + APPLICATION + API + TEST

BLOCKS_IMPLEMENTATION=YES

CONFIDENCE=HIGH

### P3SPEC-RR-003

FINDING_ID=P3SPEC-RR-003

SEVERITY=P1 / HIGH

TITLE=Stage abort and waiver authorization/eligibility remain undefined

SPECIFICATION_REFERENCE=Sections 5.1, 6.1, 6.2, 6.5, 6.7, P3-FR-012/015/025/028/037, required API capabilities, P3-AC-012/016/018/075, P3-ADV-016/028

BASELINE_REFERENCE=ADR-0003 immutable history; accepted Phase 1A mandatory pH/gravity completion behavior; server-side authorization baseline

OBSERVATION=The stage state machine permits `PENDING | ACTIVE | PAUSED -> ABORTED`, and the domain vocabulary says stages have abort rules, but there is no stage-abort command or normative individual-stage abort row. The matrix defines only session-driven stage abort. Separately, required measurements, reminders, additions, and optional-stage requirements may be waived/skipped only when an authorized or governing rule permits it, but no requirement/stage waiver-eligibility table or authorizing role/policy exists. The single-user ownership model does not by itself decide whether every required item is waivable.

FAILURE_SCENARIO=One team exposes an individual stage-abort operation; another allows `ABORTED` only as a session-abort child effect. One allows the owner to waive any missing pH, gravity, addition, or checklist requirement; another forbids waiver of selected scientific or terminal handoff facts. Both can satisfy the present prose and produce different completion outcomes.

IMPLEMENTATION_AMBIGUITY=The legal producer of stage `ABORTED`, its child effects, waiver eligibility per requirement, authorizing actor, allowed source states, and the effect of waiver on completion are not fully decided.

IMPACT=Stage/session completion, safety prompts, required brewing evidence, reminder terminal states, CompletionAudit counts, API surface, and historical regression can differ materially.

REQUIRED_REMEDIATION=State whether stage `ABORTED` is exclusively session-driven; if not, define its command and complete atomic effects. Add a normative waiver-policy table for each required requirement class/stage stating waivable or nonwaivable, authorized actor, allowed states, reason requirements, timer/reminder/addition transitions, and completion-audit result.

ENFORCEMENT_LAYER=MULTIPLE: DOMAIN + APPLICATION + API + DATABASE + TEST

BLOCKS_IMPLEMENTATION=YES

CONFIDENCE=HIGH

### P3SPEC-RR-004

FINDING_ID=P3SPEC-RR-004

SEVERITY=P1 / HIGH

TITLE=Late-entry time bounds and post-terminal mutation policy are absent

SPECIFICATION_REFERENCE=Sections 6.2, 7.2 P3-FR-018, 7.4 P3-FR-036/038, 8 measurement route, P3-AC-018/060/065, P3-ADV-018

BASELINE_REFERENCE=ADR-0003 immutable history; accepted completed-measurement immutability trigger; UTC and provenance baseline

OBSERVATION=The specification repeatedly requires “bounded” late measurement/addition entry and says timestamp back-entry is allowed only within documented bounds, but supplies no maximum age, future-clock tolerance, relationship to stage start/end, or explicit rule for `COMPLETED` and `ABORTED` BrewSessions. P3-AC-018 says terminal sessions reject further “normal execution mutations,” which does not decide whether a late-entry command is an allowed exceptional append. Corrections after completion are expected, but creation of a new late observation is semantically different.

FAILURE_SCENARIO=A brewer attempts to add a previously omitted pre-boil gravity after the stage and session are completed. One implementation accepts it indefinitely because both timestamps and a reason are stored; another allows 24 hours; another rejects all new observations after session completion. Current-effective comparisons and CompletionAudit then disagree.

IMPLEMENTATION_AMBIGUITY=The accepted time window, clock-skew tolerance, stage/session terminal-state matrix, authorization, and effect on current projections are unspecified.

IMPACT=Historical integrity, completion evidence, planned-versus-actual results, correction semantics, API validation, and adversarial tests cannot share one deterministic oracle.

REQUIRED_REMEDIATION=Define numeric past/future bounds and the reference timestamps for ordinary back-entry and completed-stage late entry. Define the allowed BrewSession/stage states, whether terminal sessions permit exceptional append, required authorization/reason, and deterministic effects on current measurement selection, deviations, journal, and CompletionAudit without rewriting completion facts.

ENFORCEMENT_LAYER=MULTIPLE: DOMAIN + APPLICATION + API + DATABASE + TEST

BLOCKS_IMPLEMENTATION=YES

CONFIDENCE=HIGH

## 6. Domain and architecture determinations

| Review area | Result | Basis |
|---|---|---|
| Stage-plan materialization | FAIL | Core source/default mapping exists, but ordering/predecessor and accepted-session backfill are incomplete. |
| Repeated-stage commands | FAIL | Instance targeting and repeat identity pass; controlled return still permits two models. |
| Terminal-effect matrix | FAIL | Session-driven effects pass; stage abort and waiver policy do not. |
| Timer model | PASS | Durable identity, UTC/deadline authority, pause basis, revision/replacement history, expiry, concurrency, recovery, and Redis loss are specified. |
| Reminder model | FAIL | Lifecycle, identity, acknowledgement and atomic satisfaction pass; waiver/cancellation eligibility is not decidable. |
| Addition timing | PASS | Phase 2 meanings, due formulas, invalidity, revisions, and actual variance are explicit. |
| Measurement context | FAIL | Versioned process-point context passes; late-entry time/state validation does not. |
| Idempotency contract | PASS | Scope, canonical request, persistence, replay, conflict, retention, tombstone, concurrency, and lost response are deterministic. |
| Planned versus actual | PASS | Decimal, units, target/actual/tolerance/status, missing states, correction history, and no RecipeVersion mutation are explicit. |
| Event/journal authority | PASS | Operational facts, AuditEvents, and derived human journal are distinct; regeneration and failure isolation are explicit. |
| Media controls | PASS | Fixed private/local controls and failure isolation are testable without Phase 5 expansion. |
| CSRF control | PASS | Synchronizer token plus exact same-origin checks cover the browser mutation surface without authorizing public deployment. |
| Performance contract | PASS | Workload, environment evidence, samples, percentiles, and numeric thresholds are defined without distributed infrastructure. |
| Refresh recovery | PASS | PostgreSQL reconstructs the same identities, deadlines, measurements, reminders, and events after refresh/restart/loss. |

## 7. Compatibility and phase-boundary review

- **Phase 1A compatibility: FAIL at specification level.** Compatibility adapters converge on Phase 3 services, and legacy Mash requirements are preserved, but existing-session migration/backfill is not deterministic.
- **Phase 2 compatibility: FAIL at specification level.** RecipeVersion/equipment/calculation and ledger/reservation authority remain unchanged, but source-order reconciliation can produce incompatible Phase 3 plans.
- **Phase 3 scope conformance: PASS.** The design remains a Brew-Day OS ending at yeast-pitch handoff.
- **Phase 4-10 operational leakage: NO.** Fermentation, quality/packaging, advanced inventory, Academy, sensory/experiments, competition/branding/menu, and Knowledge Engine operations are explicitly excluded.
- No mandatory BrewPlan/BrewBatch aggregate, outbox, distributed worker, offline mutation engine, or inventory reservation-to-consumption conversion is introduced.

## 8. Security and database enforcement review

Authentication, owner-scoped authorization, CSRF, immutable history, media isolation, journal/audit separation, and PostgreSQL authority are not weakened. The specification correctly assigns foreign keys, checks, uniqueness, append protection, transactionality, domain transitions, optimistic concurrency, and negative PostgreSQL integration evidence across multiple layers. No critical rule is intentionally left solely to UI behavior.

The open findings require multiple-layer enforcement: migration/database constraints and backfill for RR-001; occurrence identity for RR-002; domain/application authorization and state rules for RR-003; and API/domain/database validation for RR-004.

## 9. Acceptance and identifier review

Independent extraction found:

```text
FUNCTIONAL_REQUIREMENTS=84
ACCEPTANCE_CRITERIA=51
ADVERSARIAL_SCENARIOS=34
IDENTIFIER_UNIQUENESS=PASS
DANGLING_IDENTIFIER_REFERENCES=0
```

The identifier system is structurally sound, but IDs do not cure the four missing oracles. P3-AC-074 cannot prove a unique legacy backfill/order outcome; P3-AC-060 cannot choose the return model; P3-AC-012/016/075 cannot prove unspecified waiver/stage-abort rules; and P3-AC-018/060/065 cannot prove an unspecified late-entry time/state boundary.

## 10. Mandatory adversarial review

| # | Scenario | Determination |
|---:|---|---|
| 1 | Sparse legacy Phase 2 process plan | AMBIGUOUS - defaults exist, but conflicting source/canonical order and persisted legacy backfill do not have one oracle |
| 2 | Two same-type stage instances | DEFINED / TESTABLE / SAFE |
| 3 | Runtime stage repeat | DEFINED / TESTABLE / SAFE |
| 4 | Invalid backward transition | DEFINED / TESTABLE / SAFE; controlled return remains ambiguous under RR-002 |
| 5 | Three active timers then refresh | DEFINED / TESTABLE / SAFE |
| 6 | Redis loss | DEFINED / TESTABLE / SAFE |
| 7 | API restart | DEFINED / TESTABLE / SAFE |
| 8 | Timer extension | DEFINED / TESTABLE / SAFE |
| 9 | Timer expiry while disconnected | DEFINED / TESTABLE / SAFE |
| 10 | Duplicate reminder delivery | DEFINED / TESTABLE / SAFE |
| 11 | Reminder acknowledged but unsatisfied | DEFINED / TESTABLE / SAFE |
| 12 | Two tabs complete same reminder | DEFINED / TESTABLE / SAFE |
| 13 | Duplicate measurement submission | DEFINED / TESTABLE / SAFE |
| 14 | Correction of erroneous measurement | DEFINED / TESTABLE / SAFE |
| 15 | Distinct repeat observation | DEFINED / TESTABLE / SAFE |
| 16 | Addition occurs late | DEFINED / TESTABLE / SAFE |
| 17 | API timeout after successful commit | DEFINED / TESTABLE / SAFE |
| 18 | Abort with active timers/reminders | DEFINED / TESTABLE / SAFE for session abort |
| 19 | Required measurement missing at completion | AMBIGUOUS - rejection versus waiver depends on an undefined waiver-eligibility policy |
| 20 | Voice parses 5.2 as 52 | DEFINED / TESTABLE / SAFE |
| 21 | Media upload failure | DEFINED / TESTABLE / SAFE |
| 22 | CSRF token absent/invalid | DEFINED / TESTABLE / SAFE |
| 23 | Journal generation failure | DEFINED / TESTABLE / SAFE |
| 24 | Journal regeneration | DEFINED / TESTABLE / SAFE |
| 25 | Phase 1A compatibility route | DEFINED / TESTABLE / SAFE for new commands; persisted-session backfill remains ambiguous under RR-001 |
| 26 | RecipeVersion mutation during session | DEFINED / TESTABLE / SAFE |
| 27 | Phase 2 reservation state untouched | DEFINED / TESTABLE / SAFE |
| 28 | Performance threshold under realistic Brew-Day load | DEFINED / TESTABLE / SAFE |

Additional mandatory scenarios P3-ADV-018 and the terminal-session variant of late entry are ambiguous under RR-004. Any implementation-affecting `AMBIGUOUS` result is a finding under the review mandate.

## 11. Nonblocking observations

- Candidate B remains the only authoritative Phase 3 specification, and the roadmap points to its canonical path.
- Numbering gaps in functional and acceptance IDs are editorial reservations; all defined identifiers are unique.
- The performance reference class is deliberately local rather than NAS-production evidence. That separation is correct because deployment remains unauthorized.
- Exact request/response field layout may be refined during implementation only after the four material behavioral choices above are closed.

## 12. Authorization boundary

This report does not remediate the specification and does not authorize implementation. No application code, migration, test, dependency, Docker/runtime configuration, ADR, tag, push, deployment, staging operation, or commit was performed.

```text
PHASE_3_SPEC_RE_REVIEW=FAIL
REVIEW_ENVIRONMENT_VALID=YES
REVIEWED_COMMIT=f7904e8b2a8eecb6cafe1da2a04c3b648902c242
SPEC_HASH_VERIFIED=YES

PRIOR_FINDINGS_EXPECTED=9
PRIOR_FINDINGS_CLOSED=5
PRIOR_FINDINGS_REOPENED=4

P0_FINDINGS=0
P1_FINDINGS=3
P2_FINDINGS=1
P3_FINDINGS=0
ADVISORY_FINDINGS=0

FUNCTIONAL_REQUIREMENTS=84
ACCEPTANCE_CRITERIA=51
ADVERSARIAL_SCENARIOS=34
IDENTIFIER_UNIQUENESS=PASS

STAGE_PLAN_MATERIALIZATION=FAIL
REPEATED_STAGE_COMMANDS=FAIL
TERMINAL_EFFECT_MATRIX=FAIL
TIMER_MODEL=PASS
REMINDER_MODEL=FAIL
ADDITION_TIMING=PASS
MEASUREMENT_CONTEXT=FAIL
IDEMPOTENCY_CONTRACT=PASS
PLANNED_VS_ACTUAL=PASS
EVENT_JOURNAL_AUTHORITY=PASS
MEDIA_CONTROLS=PASS
CSRF_CONTROL=PASS
PERFORMANCE_CONTRACT=PASS
REFRESH_RECOVERY=PASS

PHASE_1A_COMPATIBILITY=FAIL
PHASE_2_COMPATIBILITY=FAIL
PHASE_3_SCOPE_CONFORMANCE=PASS
PHASE_4_10_OPERATIONAL_LEAKAGE=NO

IMPLEMENTATION_CONTRACT_DECIDABLE=NO
PHASE_3_IMPLEMENTATION_RECOMMENDED=NO

APPLICATION_CODE_CHANGED=NO
MIGRATIONS_CHANGED=NO
TEST_CODE_CHANGED=NO
COMMIT_CREATED=NO
PHASE_3_IMPLEMENTATION=NOT_AUTHORIZED
```
