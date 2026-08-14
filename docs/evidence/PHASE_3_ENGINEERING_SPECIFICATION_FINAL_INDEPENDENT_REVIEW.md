# Phase 3 Engineering Specification Final Independent Implementation-Readiness Review

## 1. Decision

`PHASE_3_FINAL_SPEC_REVIEW=FAIL`

The specification is substantially more complete and closes most prior findings, but it is not yet an implementation-decidable contract. The final independent review found two P1 defects and one implementation-affecting P2 defect:

1. the normative UUIDv5 name for a plan step collides when the first explicit Mash source expands into both `MASH_IN` and `MASH`;
2. runtime repeat/return occurrences copy only requirements marked repeatable, but no normative rule defines which measurement, addition or reminder requirements receive that designation; and
3. the terminal-session allowlist permits correction of an AdditionEvent without defining an addition-correction domain/API/persistence contract.

Under the governing gate, each issue blocks implementation. This review does not authorize Phase 3 coding.

## 2. Review identity

| Field | Verified value |
|---|---|
| Repository | `//NazarioNAS/USB_3TB/brewing-platform` (`B:\brewing-platform`) |
| Branch | `main` |
| Reviewed commit | `f35e8a42fa867b79a84bba247b4448028cda96c2` |
| Initial worktree | Clean |
| Phase 2 tag | `v0.2.0-phase2` |
| Phase 2 tag target | `c3faa93ea1502db63798b8c0dcc10c02741fabf7` |
| Authoritative specification | `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` |
| Expected specification SHA-256 | `32BE496C83C937582047864A9722474E6578CC0E39C412A849684B7B3BBB5AB6` |
| Actual specification SHA-256 | `32BE496C83C937582047864A9722474E6578CC0E39C412A849684B7B3BBB5AB6` |
| Review environment | VALID |

All mandatory environment gates passed before substantive review.

## 3. Authority and source receipt

This was a fresh, documentation-only delta review. The Development Roadmap; master plan; product requirements; project and architecture charters; system, AI, calculation and data architecture; domain model and Brew-Day workflow; API, testing, units, security and database/operations documentation; ADR-0001 through ADR-0011; Phase 1A and Phase 2 acceptance evidence; all four Phase 3 historical review/remediation artifacts; and relevant Phase 1A/2 migrations, schemas, domain models, application services and compatibility routes were inspected.

Historical FAIL artifacts remain historical FAIL artifacts. Remediation evidence was not treated as proof that the specification passes.

## 4. Findings

### P3SPEC-FINAL-001

FINDING_ID=P3SPEC-FINAL-001

SEVERITY=P1 / HIGH

TITLE=Normative plan-step UUID generation collides for the first explicit Mash expansion

SPECIFICATION_REFERENCE=Section 6.1.1 steps 3, 7 and 8; Phase 2 mapping table; plan-step uniqueness rule; P3-FR-009/090; P3-AC-074/078; P3-ADV-026/035

BASELINE_REFERENCE=Accepted Phase 2 `ProcessStepInput.step_type=MASH`; `recipe_process_steps` stable UUID/unique sequence; ADR-0003 immutable history; PostgreSQL authority and deterministic materialization requirements

OBSERVATION=The first explicit Phase 2 `MASH` source row expands into `MASH_IN` with expansion rank 0 and `MASH` with expansion rank 1. Planned same-type ordinal is one-based per canonical type, so both expansions have ordinal 1. The mandated UUIDv5 name is `phase3-plan-v1:{recipe_version_id}:{source_kind}:{stable_source_discriminator}:{planned_same_type_ordinal}`. It omits canonical stage type and expansion rank. Both expanded plan steps therefore use the same namespace and identical name and produce the same `plan_step_id`.

FAILURE_SCENARIO=For RecipeVersion `R` and Mash source UUID `S`, both `MASH_IN` and first `MASH` generate `phase3-plan-v1:R:EXPLICIT:S:1`. The required `(brew_session_id, plan_step_id, occurrence_number)` uniqueness key then collides at occurrence 1, so a normal accepted Phase 2 recipe with an explicit Mash step cannot materialize both required stages.

IMPLEMENTATION_AMBIGUITY=A team must invent an undocumented change—such as adding canonical stage type or expansion rank to the UUID name—to create the required plan. Implementing the specified UUID name cannot satisfy the specified stage mapping and uniqueness rule simultaneously.

IMPACT=Deterministic plan creation, stable IDs, preflight, migration schema, logical plan hashes, Phase 2 compatibility and the canonical Brew-Day flow are blocked.

REQUIRED_REMEDIATION=Amend the UUIDv5 name to include an unambiguous canonical-stage/expansion discriminator, for example `{canonical_stage_type}:{expansion_rank}`, while retaining all existing stable inputs. Add a golden fixture proving distinct stable IDs for `MASH_IN` and `MASH` from one source and a PostgreSQL test proving both occurrence-1 rows coexist and repeated materialization remains identical.

ENFORCEMENT_LAYER=MULTIPLE: DOMAIN + APPLICATION + DATABASE + TEST

BLOCKS_IMPLEMENTATION=YES

CONFIDENCE=HIGH

### P3SPEC-FINAL-002

FINDING_ID=P3SPEC-FINAL-002

SEVERITY=P1 / HIGH

TITLE=Runtime repeat and return requirement-copy semantics are not defined

SPECIFICATION_REFERENCE=Sections 6.1.1 and 6.2; P3-FR-016/019/092; `phase3-operation-v1`; P3-AC-060/080; P3-ADV-017/037

BASELINE_REFERENCE=Accepted Phase 1A mandatory Mash pH/gravity workflow; ADR-0003 immutable history; server-enforced completion requirements

OBSERVATION=A runtime repeat/return receives new timer/reminder identities and copies only requirements “explicitly marked repeatable”; single-occurrence requirements and planned additions are not copied implicitly. The specification never defines a repeatability field in the plan-step contract, a rule-versioned mapping that marks each measurement/addition/reminder requirement repeatable or single-occurrence, or the allowed command choices. The statement that a requested copy decision is part of the command does not establish eligibility.

FAILURE_SCENARIO=After completing Mash and a later stage, the brewer returns to Mash. One team copies temperature and pH requirements, another copies every Mash measurement and addition, and another copies none because no requirement is normatively marked repeatable. All preserve the new occurrence identity yet enforce materially different completion, reminder, journal and CompletionAudit behavior.

IMPLEMENTATION_AMBIGUITY=Which requirements exist on a runtime occurrence, which are mandatory, and what the command may request are left to implementation policy.

IMPACT=Repeated-stage brewing evidence, reminder creation, timer/addition behavior, stage completion eligibility, waiver handling, planned-versus-actual output and recovery payloads can diverge between conforming implementations.

REQUIRED_REMEDIATION=Add a versioned repeatability table or materialization rule for every requirement class and canonical stage, including measurements, checklist items, reminders, timers and additions. Define whether the repeat/return command may select an allowed subset or must use the complete rule-derived set, persist the decision in the new occurrence, and add golden/concurrency/E2E oracles for repeated Mash and controlled return.

ENFORCEMENT_LAYER=MULTIPLE: DOMAIN + APPLICATION + API + DATABASE + TEST

BLOCKS_IMPLEMENTATION=YES

CONFIDENCE=HIGH

### P3SPEC-FINAL-003

FINDING_ID=P3SPEC-FINAL-003

SEVERITY=P2 / MEDIUM

TITLE=Terminal addition correction is authorized without a correction contract

SPECIFICATION_REFERENCE=Section 6.8 correction row; P3-FR-034/046/095/096; required API capabilities; PostgreSQL invariant inventory; P3-AC-067/082/083; P3-ADV-015/039/040

BASELINE_REFERENCE=ADR-0003 immutable history; accepted append-only correction approach; Phase 2 ledger immutability and zero Phase 3 ledger effect

OBSERVATION=Section 6.8 allows “Correction of an existing measurement/addition” for nonterminal sessions and for 30 days after `COMPLETED` or `ABORTED`. The normative correction model, route and lineage constraints cover Measurements only. No AdditionCorrection concept, API route, supersession/current-effective rule, permitted fields, chain/fork behavior, reminder/deviation interaction, or PostgreSQL invariant is defined for correction of an AdditionEvent.

FAILURE_SCENARIO=After session completion, a brewer corrects an actual hop amount or execution time. One team appends a second AdditionEvent, another creates a generic annotation, another mutates the original addition, and another rejects the command because only the measurement correction endpoint exists. Journal, timing variance, reminder satisfaction and current actual values then disagree.

IMPLEMENTATION_AMBIGUITY=The specification authorizes an operation but does not define its authoritative record, API, lineage, current-value selection or effects.

IMPACT=Terminal history, addition variance, reminder resolution, journal regeneration and Phase 2 identity references can become incompatible or non-auditable.

REQUIRED_REMEDIATION=Either remove AdditionEvent correction from the terminal allowlist and state that only annotations are permitted, or define an append-only AdditionCorrection contract: endpoint, correctable fields, identity/lineage, no-fork rule, current-effective projection, reminder/waiver/deviation/journal effects, ownership/idempotency, database invariants and boundary-value acceptance evidence.

ENFORCEMENT_LAYER=MULTIPLE: DOMAIN + APPLICATION + API + DATABASE + TEST

BLOCKS_IMPLEMENTATION=YES

CONFIDENCE=HIGH

## 5. Prior-finding status

| Prior finding | Status | Independent disposition |
|---|---|---|
| `P3SPEC-R01` | REOPENED | FINAL-001: plan materialization cannot produce distinct IDs for the required first Mash expansion. |
| `P3SPEC-R02` | REOPENED | FINAL-002: repeated/returned stage requirement content remains undecidable. |
| `P3SPEC-R03` | CLOSED | Stage cancellation, waiver and session-abort effects are now explicitly distinguished and atomic. |
| `P3SPEC-R04` | CLOSED | Addition timing basis, reference, offset, clock and Phase 2 conversion are deterministic. |
| `P3SPEC-R05` | CLOSED | Measurement process points, contexts, raw/canonical values, methods and terminal availability remain interpretable. |
| `P3SPEC-R06` | CLOSED | Idempotency canonicalization, results, retention, tombstones, replay and conflicts are explicit. |
| `P3SPEC-R07` | CLOSED | Media limits, ownership, safe serving, failure isolation and orphan handling are fixed. |
| `P3SPEC-R08` | CLOSED | Synchronizer-token and exact-origin CSRF behavior is explicit and testable. |
| `P3SPEC-R09` | CLOSED | Numeric private-runtime workload, method and p95 thresholds are present. |
| `P3SPEC-RR-001` | REOPENED | FINAL-001 is a contradiction inside the remediated deterministic-ID algorithm. |
| `P3SPEC-RR-002` | REOPENED | FINAL-002 leaves runtime-occurrence requirements to implementation policy. |
| `P3SPEC-RR-003` | CLOSED | Abort/cancel/waiver actor, eligibility, effects, idempotency and evidence supersession are explicit. |
| `P3SPEC-RR-004` | REOPENED | FINAL-003 leaves one authorized post-terminal correction class without a contract. |

Totals: `PRIOR_FINDINGS_CLOSED=8`, `PRIOR_FINDINGS_REOPENED=5`.

## 6. Structural validation

Independent extraction produced:

```text
FUNCTIONAL_REQUIREMENTS=91
ACCEPTANCE_CRITERIA=57
ADVERSARIAL_SCENARIOS=40
IDENTIFIER_UNIQUENESS=PASS
DANGLING_FR_REFERENCES=0
DANGLING_AC_REFERENCES=0
DANGLING_ADV_REFERENCES=0
BROKEN_RELATIVE_LINKS=0
```

No previous functional, acceptance or adversarial identifier was removed. Structural integrity passes, but it cannot override the three substantive findings.

## 7. Domain and architecture assessment

| Review area | Result | Determination |
|---|---|---|
| Stage-plan materialization | FAIL | Ordering and failure behavior are explicit, but the mandated UUID name collides for first explicit Mash expansion. |
| Legacy session compatibility | PASS | Fixed UUIDv5 projection identities, existing row preservation, restart/migration idempotency and route convergence are explicit. |
| Repeated-stage commands | FAIL | Instance targeting and occurrence allocation pass; runtime requirement population is undefined. |
| Controlled return | FAIL | New occurrence identity/state is explicit; the returned occurrence's required content is not. |
| Terminal-effect matrix | PASS | Stage completion/cancel, waiver, pause/resume, abort and completion have explicit child effects. |
| Abort policy | PASS | Source states, confirmation/reason, child effects, terminal state, audit/journal and nonresumption are fixed. |
| Waiver policy | PASS | Eligible/prohibited classes, actor, reason, state, reminder and late-evidence supersession are explicit. |
| Timer model | PASS | PostgreSQL truth, clock basis, revisions, replacement, expiry, concurrency and recovery are explicit. |
| Reminder model | PASS | Acknowledgement, satisfaction, waiver, expiry, duplication, abort and late-evidence behavior are deterministic. |
| Addition timing | PASS | Legacy timing meanings and all due/variance formulas are typed and fail closed. |
| Measurement context | PASS | Process points and scientific context remain distinct, including post-mash versus pre-boil gravity. |
| Late-entry/terminal behavior | FAIL | Measurement/new-addition/note/media windows pass; the authorized addition-correction branch lacks semantics. |
| Idempotency contract | PASS | Operation scope, canonical request, retained result, replay, mismatch and lost-response behavior are fixed. |
| Planned versus actual | PASS | Decimal/domain authority, units, tolerance/status and immutable corrections are explicit. |
| Event/audit/journal authority | PASS | Operational facts, AuditEvents and derived journal remain distinct; regeneration is read-only and isolated. |
| Media controls | PASS | Fixed types, sizes, quotas, safe names/headers, ownership and orphan/retry behavior are explicit. |
| CSRF | PASS | Issuance, session binding, rotation, exact origin/referrer, coverage and rejection ordering are testable. |
| Refresh/restart recovery | PASS | PostgreSQL reconstructs authoritative identities/deadlines/state after browser/API/Redis loss. |
| Performance | PASS | Dataset, concurrency, sampling, hardware evidence and numeric p95 limits are measurable without cloud scale. |

## 8. Database and enforcement review

The specification correctly requires multiple-layer enforcement for ownership, state values/timestamps, active-session uniqueness, immutable plan snapshots, occurrence uniqueness, stage targeting, timer lineage, addition timing, reminder satisfaction, Waiver uniqueness, measurement correction lineage, late-evidence provenance, operation idempotency, media finalization, terminal immutability and journal ordering. No critical invariant is deliberately assigned to React/UI alone.

FINAL-001 reveals that the stated domain identity algorithm conflicts with its required database uniqueness rule. FINAL-002 lacks the domain/application materialization rule needed before database/API enforcement can be designed. FINAL-003 lacks the addition-correction record and invariants required for append-only terminal evidence.

## 9. Compatibility and phase boundary

- **Phase 1A compatibility:** PASS at specification level. The fixed legacy projection retains accepted identities/history and routes converge on Phase 3 services.
- **Phase 2 compatibility:** FAIL overall because an ordinary explicit Phase 2 Mash process step triggers FINAL-001. Phase 2 aggregate ownership itself remains unchanged.
- **Phase 3 scope:** PASS. The workflow ends at the yeast-pitch handoff.
- **Phase 4-10 operational leakage:** NO.
- No mandatory BrewPlan/BrewBatch aggregate, outbox, distributed worker, generalized offline synchronization engine or reservation-to-consumption conversion is introduced.

## 10. Adversarial review

| # | Scenario | Classification |
|---:|---|---|
| 1 | Sparse legacy recipe process plan | AMBIGUOUS when an accepted explicit Mash source exercises FINAL-001 |
| 2 | Duplicate source order | DEFINED / TESTABLE / SAFE (`422`, zero rows) |
| 3 | Repeated materialization | AMBIGUOUS because the mandated first-Mash IDs collide before repeatability can be proven |
| 4 | Legacy Phase 1A session compatibility | DEFINED / TESTABLE / SAFE |
| 5 | Two same-type stages | AMBIGUOUS for Mash plans whose first source also expands to colliding `MASH_IN`/`MASH` IDs |
| 6 | Controlled return to completed Mash | AMBIGUOUS because copied requirements are not normatively classified |
| 7 | Duplicate return command | DEFINED / TESTABLE / SAFE for identity/replay; returned content remains affected by FINAL-002 |
| 8 | Stage completion with unresolved required evidence | DEFINED / TESTABLE / SAFE |
| 9 | Waiver of eligible required measurement | DEFINED / TESTABLE / SAFE |
| 10 | Attempted waiver of non-waivable requirement | DEFINED / TESTABLE / SAFE |
| 11 | Late valid measurement after waiver | DEFINED / TESTABLE / SAFE |
| 12 | Session abort with active stage | DEFINED / TESTABLE / SAFE |
| 13 | Session abort with active timers | DEFINED / TESTABLE / SAFE |
| 14 | Session abort with unresolved reminder | DEFINED / TESTABLE / SAFE |
| 15 | Late measurement after stage completion | DEFINED / TESTABLE / SAFE |
| 16 | Late evidence after session completion | AMBIGUOUS for correction of an AdditionEvent under FINAL-003 |
| 17 | Late evidence after abort | AMBIGUOUS for correction of an AdditionEvent under FINAL-003 |
| 18 | Three active timers then browser refresh | DEFINED / TESTABLE / SAFE |
| 19 | Redis loss | DEFINED / TESTABLE / SAFE |
| 20 | API restart | DEFINED / TESTABLE / SAFE |
| 21 | Timer expiry while disconnected | DEFINED / TESTABLE / SAFE |
| 22 | Duplicate reminder delivery | DEFINED / TESTABLE / SAFE |
| 23 | Two tabs satisfy same reminder | DEFINED / TESTABLE / SAFE |
| 24 | Duplicate measurement submission | DEFINED / TESTABLE / SAFE |
| 25 | Measurement correction | DEFINED / TESTABLE / SAFE |
| 26 | Addition occurs late | DEFINED / TESTABLE / SAFE |
| 27 | API response lost after commit | DEFINED / TESTABLE / SAFE |
| 28 | Voice input 5.2 parsed as 52 | DEFINED / TESTABLE / SAFE |
| 29 | Media upload failure | DEFINED / TESTABLE / SAFE |
| 30 | Missing/invalid CSRF token | DEFINED / TESTABLE / SAFE |
| 31 | Journal generation failure | DEFINED / TESTABLE / SAFE |
| 32 | Journal regeneration | DEFINED / TESTABLE / SAFE |
| 33 | RecipeVersion mutation attempt | DEFINED / TESTABLE / SAFE |
| 34 | Phase 1A route execution | DEFINED / TESTABLE / SAFE |
| 35 | Phase 2 reservation remains unchanged | DEFINED / TESTABLE / SAFE |
| 36 | Private-runtime performance benchmark | DEFINED / TESTABLE / SAFE |

Any material `AMBIGUOUS` classification requires a finding under the mandate; each ambiguous classification above maps to FINAL-001, FINAL-002 or FINAL-003.

## 11. Authorization boundary

This report does not remediate the specification and does not authorize implementation. No application code, migration, test, dependency, Docker/runtime configuration, historical evidence, ADR, tag, push or deployment was changed. Only this final review artifact was created, and it remains untracked.

## 12. Final machine-readable result

```text
PHASE_3_FINAL_SPEC_REVIEW=FAIL
REVIEW_ENVIRONMENT_VALID=YES
REVIEWED_COMMIT=f35e8a42fa867b79a84bba247b4448028cda96c2
SPEC_SHA256_EXPECTED=32BE496C83C937582047864A9722474E6578CC0E39C412A849684B7B3BBB5AB6
SPEC_HASH_VERIFIED=YES

PRIOR_FINDINGS_TOTAL=13
PRIOR_FINDINGS_CLOSED=8
PRIOR_FINDINGS_REOPENED=5

P0_FINDINGS=0
P1_FINDINGS=2
P2_FINDINGS=1
IMPLEMENTATION_AFFECTING_P2_FINDINGS=1
P3_FINDINGS=0
ADVISORY_FINDINGS=0

FUNCTIONAL_REQUIREMENTS=91
ACCEPTANCE_CRITERIA=57
ADVERSARIAL_SCENARIOS=40
IDENTIFIER_UNIQUENESS=PASS

STAGE_PLAN_MATERIALIZATION=FAIL
LEGACY_SESSION_COMPATIBILITY=PASS
REPEATED_STAGE_COMMANDS=FAIL
CONTROLLED_RETURN_SEMANTICS=FAIL
TERMINAL_EFFECT_MATRIX=PASS
ABORT_POLICY=PASS
WAIVER_POLICY=PASS
TIMER_MODEL=PASS
REMINDER_MODEL=PASS
ADDITION_TIMING=PASS
MEASUREMENT_CONTEXT=PASS
LATE_ENTRY_TERMINAL_BEHAVIOR=FAIL
IDEMPOTENCY_CONTRACT=PASS
PLANNED_VS_ACTUAL=PASS
EVENT_JOURNAL_AUTHORITY=PASS
MEDIA_CONTROLS=PASS
CSRF_CONTROL=PASS
REFRESH_RECOVERY=PASS
PERFORMANCE_CONTRACT=PASS

PHASE_1A_COMPATIBILITY=PASS
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

## 13. Stop boundary

`PHASE_3_IMPLEMENTATION_NOT_AUTHORIZED`

`NO_REMEDIATION_NO_COMMIT_NO_TAG_NO_PUSH_NO_DEPLOYMENT`
