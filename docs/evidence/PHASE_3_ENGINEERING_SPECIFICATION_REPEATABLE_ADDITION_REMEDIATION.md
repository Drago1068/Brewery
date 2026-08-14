# Phase 3 Engineering Specification Repeatable-Addition Remediation

## 1. Remediation determination

`PHASE_3_REPEATABLE_ADDITION_REMEDIATION=COMPLETE`

This documentation-only change closes the specification defect tracked historically as `P3SPEC-FINAL-002` and identified in the fresh verification review as `P3SPEC-VERIFY-001` (`P1 / HIGH`). The amended contract now provides one authoritative and reachable mechanism for classifying planned additions during runtime repeat and controlled return without changing accepted Phase 2 data.

Phase 3 implementation remains unauthorized. This report is remediation evidence, not a new independent verification or specification baseline.

## 2. Baseline and finding receipt

| Item | Verified value |
|---|---|
| Repository | `B:\brewing-platform` (resolved root `//NazarioNAS/USB_3TB/brewing-platform`) |
| Branch | `main` |
| HEAD | `685b4c1df040616330bb28891efc0638024b4607` |
| Phase 2 tag | `v0.2.0-phase2` |
| Phase 2 tag commit | `c3faa93ea1502db63798b8c0dcc10c02741fabf7` |
| Specification SHA-256 before remediation | `017C9B2D6B5B73AF219B43568307A41CFD1B3D4A4335DB8FB3B0FD78232C66BF` |
| Expected pre-existing worktree difference | Untracked `docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_VERIFICATION_REVIEW.md` |
| Verification-review finding | `P3SPEC-VERIFY-001`, reopening `P3SPEC-FINAL-002` |
| Severity | `P1 / HIGH` |

The verification finding referenced specification sections 6.2.1 and 6.6, P3-FR-098, P3-AC-085 and P3-ADV-044. Its accepted-baseline reference was the Phase 2 `RecipeIngredient` model/schema and immutable RecipeVersion boundary. The accepted structure contains `use_stage`, `timing_minutes` and related planned-addition data but no repeatability field.

The failure scenario permitted different teams to classify the same addition from notes, stage, ingredient, or an unreachable synthetic rule. That would produce different addition obligations, reminders, timers and requirement fingerprints during repeat/return. Required enforcement was multiple-layer: database, domain, application, API and tests.

## 3. Root cause

The prior text defined generic `REGENERATE_FROM_RULE` and `DO_NOT_COPY` behavior but did not define a server-reachable fact that could select regeneration for a particular planned addition. The acceptance oracle nevertheless required an explicitly repeatable addition. The implementer therefore had to invent the source, authority, creation path and validation of that classification.

## 4. Normative design decision

The amended specification introduces `phase3-addition-repeat-policy-v1`, a Phase 3-only, versioned addition-repeat policy snapshotted into the BrewSession execution plan.

It distinguishes three concepts:

1. the immutable Phase 2 RecipeIngredient/planned addition;
2. the Phase 3 materialized addition-requirement template assigned to an exact planned `plan_step_id`; and
3. the persisted Phase 3 repeat policy that controls later runtime regeneration.

The closed policy vocabulary is:

| Value | Normative behavior |
|---|---|
| `NEVER` | One exact planned assignment only; no second planned assignment and no runtime repeat/return regeneration. |
| `PLANNED_OCCURRENCES_ONLY` | Only exact planned assignments in the immutable execution snapshot materialize; no runtime repeat/return regeneration. |
| `RUNTIME_REPEAT_ALLOWED` | Exact planned assignments materialize, and an authorized repeat/return of an owning occurrence regenerates exactly one fresh addition requirement. |

No open text, heuristic, runtime question, or LLM decision selects policy.

## 5. Safe default and Phase 2 compatibility

Every accepted Phase 2 planned addition without a valid explicit Phase 3 declaration receives:

```text
addition_repeat_policy=PLANNED_OCCURRENCES_ONLY
addition_repeat_policy_version=phase3-addition-repeat-policy-v1
assignment_provenance=PHASE2_SAFE_DEFAULT
reason_code=ABSENT_PHASE3_REPEAT_DECLARATION
```

The source RecipeIngredient UUID and resolved owner `plan_step_id` are persisted. Materialization succeeds, but runtime duplication is impossible. No Phase 2 migration, model, schema, API contract, RecipeVersion child, reservation, ledger or acceptance evidence is rewritten.

The existing declaration-free BrewSession creation contract remains valid. The server computes the plan preview/hash and safe defaults itself. That compatibility path cannot produce `RUNTIME_REPEAT_ALLOWED`.

## 6. Reachable explicit authorization and persisted authority

An authenticated, owner-scoped read-only plan-preview capability returns the deterministic preview hash, derived plan-step identities, exact source-addition assignments and defaults. A BrewSession creation request may then provide `addition_repeat_declarations` bound to that hash.

Each declaration contains the owned immutable RecipeVersion, source planned-addition UUID, an already-previewed target `plan_step_id`, closed policy value and reason. Actor and UTC time are server-derived. The declaration may classify an existing exact assignment but cannot create, move or copy one. `RUNTIME_REPEAT_ALLOWED` is reachable only through this creation-time declaration; it cannot be selected by a repeat/return command.

The server recomputes the preview. Stale hash, wrong/unassigned/cross-owner source or target, duplicate/conflicting declaration, malformed policy/reason, and untraceable provenance fail atomically before BrewSession creation.

PostgreSQL stores the materialized requirement-template identity, source planned-addition UUID, owner plan step, timing template, requiredness/waivability, policy, policy version, assignment provenance, declaration actor/reason/time when applicable and policy fingerprint. These facts participate in the logical-plan and runtime-requirement fingerprints and become immutable with the BrewSession snapshot. Browser, Redis and worker memory are nonauthoritative.

## 7. Repeat, return, continuation and identity semantics

| Operation | Addition behavior |
|---|---|
| Planned repeated stage | Receives only additions assigned to that exact planned `plan_step_id`; matching stage type never copies an addition. |
| Runtime `REPEAT` | Regenerates exactly one addition requirement per owning `RUNTIME_REPEAT_ALLOWED` template; other policies produce none. |
| Controlled `RETURN` | Applies the same persisted policy, with no return-time selection. |
| Bounded continuation | Creates no new addition requirement for any policy. |

A regenerated requirement receives a fresh identity linked to the new `stage_instance_id`, retains the original Phase 2 source and policy provenance, and receives fresh reminder/timer identities where eligible. It never reuses or inherits an earlier requirement, AdditionEvent, correction, executed/skipped state, Waiver, acknowledgement, reminder completion or satisfaction source.

The repeat/return occurrence, requirements and child records are one transaction and one stored idempotent result. Same operation ID and canonical request replays the original set. A competing operation is governed by the existing session lock, expected revision, occurrence constraint and requirement uniqueness constraint.

## 8. Inventory and phase boundary

Materializing or regenerating an addition requirement means only that the Brew-Day execution snapshot contains another authorized execution obligation. It has no inventory effect and cannot:

- consume or decrement stock;
- convert or release reservations;
- create purchasing or forecasting facts;
- choose a substitute;
- mutate a lot or RecipeVersion; or
- introduce a Phase 6 workflow.

The remediation ends within Phase 3 Brew-Day execution and retains the yeast-pitch handoff boundary. It introduces no Phase 4–10 operational behavior, distributed rules engine, worker authority, outbox, or deployment action.

## 9. Requirements and evidence added

### Functional requirements

- `P3-FR-100` — persisted closed policy, safe default, version/provenance/fingerprint and prohibition on heuristics/runtime elevation.
- `P3-FR-101` — owner-scoped preview and creation-time declaration contract, validation, snapshot freeze and Phase 2 immutability.
- `P3-FR-102` — exact planned/repeat/return/continuation behavior, fresh identity, nontransfer, idempotency and zero inventory effect.

### Acceptance criteria

- `P3-AC-087` — legacy default, explicit reachability, preview/declaration validation, persisted provenance and Phase 2 preservation.
- `P3-AC-088` — repeat/return regeneration, fresh identity/state, idempotent replay and concurrency uniqueness.
- `P3-AC-089` — planned assignment, bounded continuation, restart/loss recovery, snapshot stability and inventory boundary.

`P3-AC-085` was tightened to name the safe and explicit policies rather than rely on “rule-repeatable” prose.

### Adversarial scenarios

- `P3-ADV-051` — legacy default plus Mash runtime repeat produces no addition.
- `P3-ADV-052` — explicit repeatable addition plus lost-response retry produces exactly one.
- `P3-ADV-053` — mixed repeatable/default additions regenerate only the permitted one.
- `P3-ADV-054` — controlled return after executed addition follows stored policy.
- `P3-ADV-055` — skipped/waived prior state does not transfer.
- `P3-ADV-056` — browser/Redis loss leaves PostgreSQL policy authoritative.
- `P3-ADV-057` — later recipe/default change cannot alter an existing snapshot.
- `P3-ADV-058` — heuristic inference is rejected as nonauthoritative.

`P3-ADV-044` was tightened to use an explicitly declared and snapshotted `RUNTIME_REPEAT_ALLOWED` source.

## 10. Historical-finding regression audit

| Finding | Status after bounded remediation | Regression assessment |
|---|---|---|
| P3SPEC-R01 | CLOSED | Full deterministic plan materialization remains intact; policy input is normalized and hashed. |
| P3SPEC-R02 | CLOSED | Stage-instance addressing and occurrence identity are unchanged. |
| P3SPEC-R03 | CLOSED | Terminal child effects remain unchanged. |
| P3SPEC-R04 | CLOSED | Typed Phase 2 addition timing remains unchanged. |
| P3SPEC-R05 | CLOSED | Measurement context remains unchanged. |
| P3SPEC-R06 | CLOSED | Idempotency is extended consistently to policy materialization/regeneration. |
| P3SPEC-R07 | CLOSED | Media controls are unchanged. |
| P3SPEC-R08 | CLOSED | CSRF contract remains applicable to creation mutations. |
| P3SPEC-R09 | CLOSED | Performance contract remains intact. |
| P3SPEC-RR-001 | CLOSED | Ordering, identity and compatibility projection remain intact. |
| P3SPEC-RR-002 | CLOSED | Repeat and return remain distinct and now have complete addition input. |
| P3SPEC-RR-003 | CLOSED | Abort and waiver behavior remains intact. |
| P3SPEC-RR-004 | CLOSED | Terminal and late-entry rules remain intact. |
| P3SPEC-FINAL-001 | CLOSED | Collision-free plan identity remains intact. |
| P3SPEC-FINAL-002 | CLOSED | The repeatable-addition branch now has a closed, persisted, reachable classifier and complete oracle. |
| P3SPEC-FINAL-003 | CLOSED | AdditionEvent correction remains separate from plan policy and Phase 2 intent. |

`PRIOR_FINDINGS_REGRESSED=0`

This is a remediation regression audit, not a substitute for a fresh independent review.

## 11. Structural and compatibility validation

| Check | Result |
|---|---|
| Functional requirements | 94 before; 97 after |
| Acceptance criteria | 60 before; 63 after |
| Adversarial scenarios | 50 before; 58 after |
| Identifier uniqueness | PASS; no duplicate FR, AC or ADV declaration |
| Dangling explicit AC-to-FR references | 0 |
| Prior FR/AC/ADV identifiers removed | 0 |
| Relative Markdown links | PASS; 4 checked, 0 broken |
| Contradictory repeatability language | 0 unresolved; generic runtime policy now maps explicitly from the closed addition policy |
| Phase 1A compatibility | PASS |
| Phase 2 compatibility | PASS |
| Phase 3 scope conformance | PASS |
| Phase 4–10 operational leakage | NO |

The complete amended specification and immutable verification review were reread after editing. The verification review remains unchanged at SHA-256 `B443944EA45240F53B86FB317AE8653731B03450C8273512407BDA4E70E295DC`.

## 12. Changed-file and hash receipt

Files changed by this bounded remediation:

- `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`
- `docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_REPEATABLE_ADDITION_REMEDIATION.md`

Pre-existing and intentionally unchanged historical evidence:

- `docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_VERIFICATION_REVIEW.md`

Final amended specification SHA-256:

`6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF`

No application code, migration, test, dependency, Docker, runtime configuration, historical review evidence or Phase 2 artifact was modified. Nothing was staged or committed.

## 13. Final machine-readable result

```text
PHASE_3_REPEATABLE_ADDITION_REMEDIATION=COMPLETE

TARGET_FINDING=P3SPEC-FINAL-002
TARGET_FINDING_SEVERITY=P1
TARGET_FINDING_STATUS=CLOSED

AUTHORITATIVE_REPEATABILITY_MECHANISM=PASS
PERSISTED_REPEAT_POLICY=PASS
SAFE_DEFAULT_DEFINED=PASS
POLICY_VERSIONING=PASS
POLICY_PROVENANCE=PASS

LEGACY_PHASE2_ADDITION_BEHAVIOR=PASS
PLANNED_REPEAT_BEHAVIOR=PASS
RUNTIME_REPEAT_BEHAVIOR=PASS
CONTROLLED_RETURN_BEHAVIOR=PASS
BOUNDED_CONTINUATION_BEHAVIOR=PASS

NEW_REQUIREMENT_IDENTITY=PASS
REPEAT_IDEMPOTENCY=PASS
PRIOR_STATE_NONTRANSFER=PASS
INVENTORY_BOUNDARY=PASS

HISTORICAL_FINDINGS_TOTAL=16
HISTORICAL_FINDINGS_CLOSED=16
HISTORICAL_FINDINGS_REOPENED=0
PRIOR_FINDINGS_REGRESSED=0

PHASE_1A_COMPATIBILITY=PASS
PHASE_2_COMPATIBILITY=PASS
PHASE_3_SCOPE_CONFORMANCE=PASS
PHASE_4_10_OPERATIONAL_LEAKAGE=NO

FUNCTIONAL_REQUIREMENTS_BEFORE=94
FUNCTIONAL_REQUIREMENTS_AFTER=97

ACCEPTANCE_CRITERIA_BEFORE=60
ACCEPTANCE_CRITERIA_AFTER=63

ADVERSARIAL_SCENARIOS_BEFORE=50
ADVERSARIAL_SCENARIOS_AFTER=58

IDENTIFIER_UNIQUENESS=PASS
DANGLING_REFERENCES=0
PRIOR_REQUIREMENTS_REMOVED=0

SPEC_SHA256_BEFORE=017C9B2D6B5B73AF219B43568307A41CFD1B3D4A4335DB8FB3B0FD78232C66BF
SPEC_SHA256_AFTER=6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF

APPLICATION_CODE_CHANGED=NO
MIGRATIONS_CHANGED=NO
TEST_CODE_CHANGED=NO
DEPENDENCIES_CHANGED=NO
DOCKER_CHANGED=NO
RUNTIME_CONFIG_CHANGED=NO

DOCUMENTATION_FILES_CHANGED=docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md;docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_REPEATABLE_ADDITION_REMEDIATION.md

READY_FOR_CHIEF_ARCHITECT_REVIEW=YES
READY_FOR_NEW_SPEC_BASELINE=NO
READY_FOR_INDEPENDENT_VERIFICATION=NO

PHASE_3_IMPLEMENTATION=NOT_AUTHORIZED
```
