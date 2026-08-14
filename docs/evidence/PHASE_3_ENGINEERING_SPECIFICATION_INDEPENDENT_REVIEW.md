# Phase 3 Engineering Specification Independent Review

## 1. Decision

`FAIL — SPECIFICATION REVISION REQUIRED`

Blocking findings: `P0=0`, `P1=5`, `P2=4`, `P3=0`.

The eleven High findings from the earlier reconciliation are closed in the committed governance package. This fresh review nevertheless found new, narrower implementation ambiguities in plan materialization, repeated-stage command identity, state/timer terminal effects, addition timing, brewing measurement context, idempotency retention/canonicalization, media/CSRF controls, and performance thresholds. Under the review mandate there is no conditional pass: implementation-affecting P2 findings also require `FAIL`.

## 2. Review identity

| Field | Value |
|---|---|
| Review time | 2026-08-13 19:40:45 -04:00 (America/New_York) |
| Repository root | `//NazarioNAS/USB_3TB/brewing-platform` (mounted as `B:\brewing-platform`) |
| Branch | `main` |
| Reviewed HEAD | `3e11d3100b38bd3a8f4c9262821f8eccfe875e16` |
| Phase 2 tag | `v0.2.0-phase2` |
| Phase 2 tag target | `c3faa93ea1502db63798b8c0dcc10c02741fabf7` |
| Accepted migration head | `0002_phase2_brewing_core` |
| Specification Git object hash | `e7c163db006ce5615fd9af55196b0f0a32bfebb3` |
| Specification SHA-256 | `9D06A24347B2EEA2B0194361D3DEA61C4FE735969548A53AC8F376906420CEAF` |
| Initial dirty-tree inventory | Clean; `git status --short`, tracked diff, and untracked inventory were empty |

## 3. Authority and scope

This was a documentation-only independent review of `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` at the exact reviewed HEAD. The accepted Phase 2 tag, governing documents, all accepted ADRs, and the actual Phase 1A/2 implementation seams were reviewed read-only.

The review did not authorize or perform Phase 3 implementation, schema/migration changes, application or test changes, dependency installation, Docker execution, deployment, tagging, pushing, or NAS mutation. The only file created by this review is this report.

## 4. Executive assessment

The specification is materially stronger after reconciliation. Its authority boundary, PostgreSQL truth model, deterministic calculation rule, reminder lifecycle, timer revisions, command atomicity, event/audit separation, completion audit, recovery matrix, and Phase 4–10 exclusions are unusually explicit. Candidate B is the only authoritative Phase 3 specification in the repository, and the roadmap points to its canonical path.

It is not yet a closed implementation contract. The accepted Phase 2 process-plan model can express only a sparse subset of the Phase 3 stage vocabulary, while the specification does not define the deterministic materialization/default/required-stage rules. The required repeated-stage model is not addressable through the required API. Abort and pause leave timer/reminder/stage effects to later documentation. Phase 2 addition timing does not define whether `timing_minutes` is elapsed, remaining, or stage-relative. Several required measurements lack the context needed to remain scientifically interpretable. Four bounded cross-cutting controls also remain undecidable.

## 5. Source review receipt

All mandatory sources were read completely before decision.

| Source | Receipt |
|---|---|
| `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` | COMPLETE |
| `docs/product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md` | COMPLETE |
| `docs/DEVELOPMENT_ROADMAP.md` | COMPLETE |
| `docs/product/PRODUCT_REQUIREMENTS.md` | COMPLETE |
| `docs/product/PROJECT_CHARTER.md` | COMPLETE |
| `docs/architecture/ARCHITECTURE_CHARTER.md` | COMPLETE |
| `docs/architecture/SYSTEM_ARCHITECTURE.md` | COMPLETE |
| `docs/architecture/AI_ARCHITECTURE.md` | COMPLETE |
| `docs/architecture/BREWING_CALCULATION_ENGINE.md` | COMPLETE |
| `docs/architecture/DATA_MODEL.md` | COMPLETE |
| `docs/domain/BREW_DAY_WORKFLOW.md` | COMPLETE |
| `docs/domain/DOMAIN_MODEL.md` | COMPLETE |
| `docs/API.md` | COMPLETE |
| `docs/TESTING.md` | COMPLETE |
| `docs/UNITS_AND_ROUNDING.md` | COMPLETE |
| `docs/security/SECURITY.md` | COMPLETE |
| `docs/security/SECURITY_ARCHITECTURE.md` | COMPLETE |
| `docs/operations/DATABASE.md` | COMPLETE |
| `docs/PHASE_2_IMPLEMENTATION_REPORT.md` | COMPLETE |
| `docs/evidence/PHASE_1A_INDEPENDENT_ARCHITECTURE_ACCEPTANCE.md` | COMPLETE |
| `docs/evidence/PHASE_2_INDEPENDENT_ARCHITECTURE_AND_BREWING_ACCEPTANCE.md` | COMPLETE |
| `docs/adr/ADR-0001-MODULAR-MONOLITH.md` | COMPLETE; Accepted |
| `docs/adr/ADR-0002-ARCHITECTURE-LAYERS.md` | COMPLETE; Accepted |
| `docs/adr/ADR-0003-IMMUTABLE-HISTORY.md` | COMPLETE; Accepted |
| `docs/adr/ADR-0004-DETERMINISTIC-CALCULATIONS.md` | COMPLETE; Accepted |
| `docs/adr/ADR-0005-LEDGER-INVENTORY.md` | COMPLETE; Accepted |
| `docs/adr/ADR-0006-PERSISTED-BREW-TIMERS.md` | COMPLETE; Accepted |
| `docs/adr/ADR-0007-PUBLIC-DIGITAL-MENU-BOUNDARY.md` | COMPLETE; Accepted |
| `docs/adr/ADR-0008-CANONICAL-UNITS-AND-ROUNDING.md` | COMPLETE; Accepted for Phase 2 |
| `docs/adr/ADR-0009-PHASE2-CALCULATION-MODELS.md` | COMPLETE; Accepted for Phase 2 |
| `docs/adr/ADR-0010-RECIPE-CALCULATION-SNAPSHOTS.md` | COMPLETE; Accepted for Phase 2 |
| `docs/adr/ADR-0011-INVENTORY-RESERVATION-SEMANTICS.md` | COMPLETE; Accepted for Phase 2 |

Supplemental historical source `docs/evidence/PHASE_3_SPECIFICATION_RECONCILIATION_REVIEW.md` was reviewed for the eleven-finding closure audit. It was not treated as proof of this decision.

## 6. Baseline compatibility assessment

- The baseline tag and target match the accepted evidence. The reviewed governance commit is one documentation-only child of that tag.
- `database/migrations/versions/0001_phase1a.py` establishes the current Mash-only `BrewSession`, unique `(brew_session_id, name)` stage shape, one named timer per stage, measurements, notifications, journal events, and audit events.
- `apps/api/brewing_api/application/brew_day.py:92-102` rejects a second Mash stage, and line 208 rejects measurements outside an active stage. Phase 3 therefore needs explicit additive compatibility behavior for repeated and late stage-instance operations.
- `apps/api/brewing_api/presentation/routes/brew_sessions.py` exposes the accepted `/start`, `/mash/start`, stage-ID measurement, correction, and Mash-completion routes. Compatibility adapters can be retained, but must converge on one Phase 3 service.
- `apps/api/brewing_api/presentation/phase2_schemas.py:196-201` permits only `MASH`, `BOIL`, `FERMENTATION_FOUNDATION`, and `PACKAGING_FOUNDATION` process-step types. That source does not itself define the full Phase 3 stage plan.
- `apps/api/brewing_api/domain/recipes/models.py:79-80` stores an addition `use_stage` and undifferentiated `timing_minutes`. No accepted rule defines the operational due-time basis.
- Phase 2 recipe/equipment/calculation snapshots and immutable `RecipeVersion -> BrewSession` lineage are compatible with an additive Phase 3 session snapshot. No BrewPlan/BrewBatch replacement is necessary.
- The existing cookie is HTTP-only and `SameSite=Lax`; explicit anti-CSRF was recorded as a pre-broader-deployment limitation in Phase 1A evidence. Phase 3 remains private/local and introduces no public route, but its larger mutation surface still needs a stated acceptance disposition.
- No targeted test was necessary to establish these static compatibility facts. No Docker, migration, or test command was run.

## 7. Findings

### P3SPEC-R01 — P1 HIGH — Canonical stage-plan materialization is not deterministic

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:117-146`, `:211-218`, `:347-358`.
- **Affected IDs:** P3-FR-002, P3-FR-004, P3-FR-006, P3-FR-008, P3-FR-012, P3-FR-013; P3-AC-004, P3-AC-010, P3-AC-022.
- **Evidence/failure:** The specification says order comes from the snapshot and lists 13 canonical stages, but never identifies which are always mandatory, conditionally required, default-generated, or legitimately absent. The accepted Phase 2 API permits only four process-step types, two of which are forward-phase foundations. Two conforming implementers can materialize different Brew-Day plans from the same RecipeVersion, or one can let every stage be optional.
- **Why it matters:** Preflight, progression, completion, reminders, snapshot compatibility, and migration/backfill all depend on one reproducible plan.
- **Smallest amendment:** Add a normative stage-materialization table containing canonical stage, inclusion predicate, mandatory/conditional/optional status, Phase 2 source mapping/default, predecessor rule, required facts, and legacy Mash-only override. State that the complete materialized plan and rule version are snapshotted before `READY`.
- **Blocks authorization:** YES.

### P3SPEC-R02 — P1 HIGH — Required stage commands cannot address repeated instances

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:124-128`, `:228-231`, `:327`.
- **Affected IDs:** P3-FR-016, P3-FR-017, P3-FR-018, P3-FR-019; P3-AC-060.
- **Evidence/failure:** The domain requires distinct repeated occurrences with stable identities, yet the required stage command route uses `{stage_key}` and supplies no repeat, return, continuation, extension, or explicit late-entry command family. After two Mash occurrences, `{stage_key}=MASH` is ambiguous; an engineer must invent selection semantics or a route not in the contract.
- **Why it matters:** The exact remediation for repeated/late execution is not implementable consistently at the API boundary.
- **Smallest amendment:** Make stage-instance identity authoritative after materialization: use `/stages/{stage_id}/...`; add explicit `repeat`, `return`, `extend`, and `late-entry` capabilities with source occurrence, expected revision, reason, and operation ID. Reserve the legacy `/mash/start` adapter for the first legacy Mash occurrence.
- **Blocks authorization:** YES.

### P3SPEC-R03 — P1 HIGH — Pause, abort, and terminal side effects are delegated instead of specified

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:96-100`, `:107-128`, `:168-180`, `:227`.
- **Affected IDs:** P3-FR-014, P3-FR-015, P3-FR-022, P3-FR-025, P3-FR-028; P3-AC-012, P3-AC-018, P3-AC-042.
- **Evidence/failure:** Session pause defines its timer cascade, but stage pause does not. Abort says outstanding timers are cancelled or retained according to a later “documented deterministic rule”; reminder and active-stage terminal effects are not chosen here. Two implementations can leave an aborted session with running timers, cancel every wall-clock timer, or preserve due reminders and still claim textual compliance.
- **Why it matters:** Terminal truth, recovery, notifications, journal chronology, and completion/abort evidence can diverge.
- **Smallest amendment:** Add one session/stage/timer/reminder/addition transition-effect matrix. For each session pause/resume/abort/complete and stage pause/abort/complete command, define atomic child-state effects, exemptions by clock basis, retained evidence, and forbidden post-terminal mutations.
- **Blocks authorization:** YES.

### P3SPEC-R04 — P1 HIGH — Planned addition timing has no authoritative basis or formula

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:172-180`, `:235-244`, `:267`, `:463`, `:512`.
- **Affected IDs:** P3-FR-021, P3-FR-022, P3-FR-023, P3-FR-024, P3-FR-046; P3-AC-014, P3-AC-067.
- **Evidence/failure:** Phase 2 stores `use_stage` plus `timing_minutes`; for boil hops that value is also used as utilization/contact time. The Phase 3 specification never says whether an addition is due N minutes after stage start, N minutes before stage end, at flameout, or after whirlpool start, nor which clock basis governs pauses. A “60 minute” boil hop can therefore be scheduled at boil start or 60 minutes after it.
- **Why it matters:** A wrong timer changes the actual brew, not merely presentation.
- **Smallest amendment:** Define and snapshot an `AdditionScheduleBasis` vocabulary (for example `FROM_STAGE_START`, `BEFORE_STAGE_END`, `AT_STAGE_END`, `ABSOLUTE_STAGE_OFFSET`) and a deterministic conversion from each accepted Phase 2 `use_stage/timing_minutes` combination to due trigger, stage instance, and clock basis. Reject ambiguous schedules at preflight.
- **Blocks authorization:** YES.

### P3SPEC-R05 — P1 HIGH — Required brewing measurements can remain scientifically ambiguous

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:248-257`, `:459-466`.
- **Affected IDs:** P3-FR-030, P3-FR-031, P3-FR-032, P3-FR-033, P3-FR-036, P3-FR-038; P3-AC-015, P3-AC-065.
- **Evidence/failure:** Instrument/method is optional for every type. Mash pH has no sample/measurement temperature context; gravity has no hydrometer/refractometer or temperature-correction context; volume has no vessel basis or measured-versus-temperature-corrected basis; “post-mash” and “pre-boil” gravity are not distinguished operationally. Numerically valid records can therefore be incomparable or misleading while passing range/unit tests.
- **Why it matters:** Planned-versus-actual evidence and later trustworthy analysis depend on interpretable observations, without requiring Phase 5 calibration management.
- **Smallest amendment:** Add a measurement-definition table per required type with canonical name, stage/trigger, required context fields, allowed method/source, plausible range, target/tolerance source, and correction rule. Require sample/measurement temperature where it changes interpretation; require vessel/reference-temperature basis for volume; distinguish raw observed from deterministically corrected values and model identity.
- **Blocks authorization:** YES.

### P3SPEC-R06 — P2 MEDIUM — Idempotency canonicalization and retention remain open

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:296-303`, `:341-343`, `:508`.
- **Affected IDs:** P3-FR-072, P3-FR-076, P3-FR-077; P3-AC-017, P3-AC-063.
- **Evidence/failure:** The key scope and replay/conflict behavior are now strong, but “equivalent normalized payload” and “documented retry/recovery window” have no normative canonicalization or minimum duration. Decimal formatting, omitted defaults, timestamps, and key reuse after pruning can receive incompatible treatment.
- **Why it matters:** Retry safety can change with serializer or cleanup choices.
- **Smallest amendment:** Require command-schema-versioned canonical JSON/hash rules, store the canonical request hash and result, and set a minimum retention period (or retain through terminal session plus a fixed interval) that cannot expire while an operation can still be retried.
- **Blocks authorization:** YES.

### P3SPEC-R07 — P2 MEDIUM — Media and mutation resource/security limits are not independently decidable

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:271-279`, `:307-315`, `:479-482`.
- **Affected IDs:** P3-FR-050, P3-FR-051, P3-FR-052, P3-FR-053, P3-FR-054, P3-FR-080, P3-FR-081, P3-FR-083; P3-AC-030, P3-AC-031.
- **Evidence/failure:** “Bounded size/count” has no numbers or pre-implementation approval rule. Retention, response headers/content disposition, image-serving policy, and request/rate/size controls for notes, events, timers, and retries are absent. An implementation can accept very large images or unbounded event creation and still claim compliance.
- **Why it matters:** The new surface can exhaust storage/CPU or turn stored content into an unsafe browser response.
- **Smallest amendment:** Define approved numeric upload/count/text/request limits, storage quota/error behavior, retention/soft-removal policy, `X-Content-Type-Options: nosniff`, safe `Content-Disposition`, authorization on every byte response, and bounded per-user mutation throttles with deterministic `413/429` behavior.
- **Blocks authorization:** YES.

### P3SPEC-R08 — P2 MEDIUM — CSRF protection has no Phase 3 acceptance disposition

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:305-315`, `:341`, `:477-482`.
- **Affected IDs:** P3-FR-080, P3-FR-081, P3-FR-084; P3-AC-030.
- **Evidence/failure:** The accepted API authenticates with a cookie and SameSite=Lax. The specification adds many state-changing endpoints but has no Origin/Referer, token, or explicit same-site threat decision and no cross-origin adversarial test. SameSite helps but is not a complete statement of the accepted trust boundary.
- **Why it matters:** Security behavior should not be silently chosen by individual route implementations.
- **Smallest amendment:** State the Phase 3 CSRF control (synchronizer/double-submit token or strict Origin/Referer enforcement in addition to SameSite) and require a test proving a cross-origin state-changing request cannot mutate authority. Keep production/TLS deployment as a separate gate.
- **Blocks authorization:** YES.

### P3SPEC-R09 — P2 MEDIUM — Performance acceptance is deferred beyond the reviewed contract

- **Reference:** `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md:315`, `:517-518`.
- **Affected IDs:** P3-FR-088; P3-AC-073.
- **Evidence/failure:** The work package is told to propose Product Owner-approved p95 targets “before implementation,” so this reviewed specification contains no pass threshold. Code can begin only after a material acceptance decision outside the contract.
- **Why it matters:** The specification is not yet independently accept/reject capable for a stated mandatory requirement.
- **Smallest amendment:** Put the approved command, recovery, and render p95 thresholds, dataset size, concurrency, and reference hardware class directly in the specification (or a versioned normative appendix approved before implementation authorization).
- **Blocks authorization:** YES.

## 8. Historical eleven-High remediation closure matrix

This matrix answers the reconciliation closure question. `VERIFIED_CLOSED` means the original High defect is no longer present; it does not imply that this fresh review passed.

| Finding | Closure | Exact committed evidence |
|---|---|---|
| PH3-REC-B-001 | VERIFIED_CLOSED | Stage occurrences, extension, return, and late entry at specification lines 124-128; P3-FR-016 through 019; P3-AC-060; P3-ADV-017/018 |
| PH3-REC-B-002 | VERIFIED_CLOSED | Normative reminder lifecycle at lines 182-203; P3-FR-028/029; P3-AC-061; P3-ADV-005/006 |
| PH3-REC-B-003 | VERIFIED_CLOSED | Timer revisions/replacement/recovery at lines 150-180; P3-FR-079; P3-AC-062/069; P3-ADV-007 through 013 |
| PH3-REC-B-004 | VERIFIED_CLOSED | Persisted operation identity, atomic command sets, optimistic concurrency, and PostgreSQL invariant inventory at lines 296-303 and 362-379; P3-AC-063/070 |
| PH3-REC-B-005 | VERIFIED_CLOSED | Typed BrewJournalEvent and separate AuditEvent authority at lines 312-314; P3-AC-064 |
| PH3-REC-A-001 | VERIFIED_CLOSED | Candidate B binds to accepted tag/commit at lines 7-8, 15, and 25; the roadmap selects only its canonical path |
| PH3-REC-A-002 | VERIFIED_CLOSED | Correct Phase 4–10 ownership matrix at lines 399-411 aligns with the roadmap |
| PH3-REC-A-003 | VERIFIED_CLOSED | P3-FR-046 has zero inventory-ledger effect; explicit Phase 6 deferral at line 428 |
| PH3-REC-A-004 | VERIFIED_CLOSED | No offline claim at line 397 and explicit no-offline-engine rule at lines 419 and 429 |
| PH3-REC-A-005 | VERIFIED_CLOSED | No outbox/worker mandate at lines 47 and 431; worker test is conditional in P3-FR-079 |
| PH3-REC-A-006 | VERIFIED_CLOSED | Accepted `RecipeVersion -> BrewSession` lineage preserved at lines 47 and 430 |

Machine-readable closure result:

```json
{
  "baseline_commit": "3e11d3100b38bd3a8f4c9262821f8eccfe875e16",
  "specification_sha256": "9D06A24347B2EEA2B0194361D3DEA61C4FE735969548A53AC8F376906420CEAF",
  "candidate_b_authoritative": true,
  "roadmap_canonical_path_confirmed": true,
  "original_high_findings_total": 11,
  "original_high_findings_verified_closed": 11,
  "original_high_findings": {
    "PH3-REC-B-001": "VERIFIED_CLOSED",
    "PH3-REC-B-002": "VERIFIED_CLOSED",
    "PH3-REC-B-003": "VERIFIED_CLOSED",
    "PH3-REC-B-004": "VERIFIED_CLOSED",
    "PH3-REC-B-005": "VERIFIED_CLOSED",
    "PH3-REC-A-001": "VERIFIED_CLOSED",
    "PH3-REC-A-002": "VERIFIED_CLOSED",
    "PH3-REC-A-003": "VERIFIED_CLOSED",
    "PH3-REC-A-004": "VERIFIED_CLOSED",
    "PH3-REC-A-005": "VERIFIED_CLOSED",
    "PH3-REC-A-006": "VERIFIED_CLOSED"
  },
  "fresh_independent_review_decision": "FAIL_SPECIFICATION_REVISION_REQUIRED",
  "fresh_blocking_findings": {"P0": 0, "P1": 5, "P2": 4, "P3": 0},
  "phase_3_implementation_authorized": false,
  "nas_production_deployment_authorized": false
}
```

## 9. Functional-requirement traceability appendix

| ID | Review | Authority | Acceptance mapping | Note |
|---|---|---|---|---|
| P3-FR-001 | PASS | Application + DB | P3-AC-010, P3-AC-030, P3-AC-041 | Owned immutable source is decidable |
| P3-FR-002 | AMEND | Application + DB | P3-AC-010, P3-AC-022, P3-AC-041 | R01: materialization contents/rules incomplete |
| P3-FR-003 | PASS | DB + application | P3-AC-004, P3-AC-022 | Snapshot immutability is testable |
| P3-FR-004 | AMEND | Domain + application | P3-AC-010, P3-AC-011, P3-AC-041 | R01: required plan data depends on missing table |
| P3-FR-005 | PASS | API + frontend | P3-AC-040, P3-AC-041, P3-AC-045 | Presentation evidence defined |
| P3-FR-006 | AMEND | Migration + application | P3-AC-004, P3-AC-021, P3-AC-022 | R01: nonlegacy Phase 2 materialization undefined |
| P3-FR-007 | PASS | Application adapter | P3-AC-004, P3-AC-011, P3-AC-041 | One-service compatibility rule is explicit |
| P3-FR-008 | AMEND | Migration + domain | P3-AC-004, P3-AC-022 | R01: legacy exception exists; full rule table absent |
| P3-FR-010 | PASS | API + frontend | P3-AC-010, P3-AC-040, P3-AC-041 | Testable projection |
| P3-FR-011 | PASS | Domain + application | P3-AC-010, P3-AC-011, P3-AC-023 | Server authority explicit |
| P3-FR-012 | AMEND | Domain + application | P3-AC-010, P3-AC-012 | R01: stage classifications missing |
| P3-FR-013 | AMEND | DB + domain | P3-AC-010, P3-AC-060 | R01: source plan derivation missing |
| P3-FR-014 | AMEND | Domain + application | P3-AC-012, P3-AC-042 | R03: stage-pause child effects missing |
| P3-FR-015 | AMEND | Domain + application | P3-AC-012, P3-AC-018, P3-AC-042 | R03: cancel-or-retain choice delegated |
| P3-FR-016 | AMEND | DB + application | P3-AC-060 | R02: no addressable repeat command |
| P3-FR-017 | AMEND | DB + application | P3-AC-060 | R02: no stage extension capability in API list |
| P3-FR-018 | AMEND | Application + API | P3-AC-060 | R02: bounded late-entry command unspecified |
| P3-FR-019 | AMEND | Domain + API | P3-AC-060 | R02: return command unspecified |
| P3-FR-020 | PASS | DB + application | P3-AC-013, P3-AC-041 | Concrete concurrency count |
| P3-FR-021 | AMEND | Domain + application | P3-AC-014, P3-AC-041 | R04: schedule basis/formula missing |
| P3-FR-022 | AMEND | DB + application | P3-AC-013, P3-AC-014, P3-AC-069 | R03/R04 affect overdue semantics |
| P3-FR-023 | AMEND | Application | P3-AC-014, P3-AC-067 | R04: actual timing lacks planned basis |
| P3-FR-024 | AMEND | Domain + application | P3-AC-014, P3-AC-067 | R04: late determination is ambiguous |
| P3-FR-025 | AMEND | Domain + application | P3-AC-061 | R03: abort/terminal effect missing |
| P3-FR-026 | PASS | Domain + application | P3-AC-061 | Explicit and adversarially tested |
| P3-FR-027 | PASS | Application boundary | P3-AC-002, P3-AC-003 | Clear no-external-notification boundary |
| P3-FR-028 | AMEND | DB + domain | P3-AC-061 | Lifecycle strong; R03 terminal cascade missing |
| P3-FR-029 | PASS | DB + application | P3-AC-061, P3-AC-063 | Atomic satisfaction defined |
| P3-FR-030 | AMEND | Domain | P3-AC-015, P3-AC-065 | R05: definitions/context incomplete |
| P3-FR-031 | AMEND | DB + domain | P3-AC-015, P3-AC-065 | R05: context optional/underspecified |
| P3-FR-032 | AMEND | API + domain + DB | P3-AC-015, P3-AC-023 | R05: type-specific rules missing |
| P3-FR-033 | AMEND | Domain + DB | P3-AC-015, P3-AC-023 | R05: volume/gravity bases incomplete |
| P3-FR-034 | PASS | DB + application | P3-AC-016, P3-AC-023 | Append-only correction explicit |
| P3-FR-035 | PASS | Domain | P3-AC-016 | Effective-value rule explicit |
| P3-FR-036 | AMEND | Domain + API | P3-AC-065 | R05/R06: bounds remain unspecified |
| P3-FR-037 | PASS | Domain + application | P3-AC-012, P3-AC-016 | Waiver remains distinct |
| P3-FR-038 | AMEND | API + DB | P3-AC-065 | R05: observation context incomplete |
| P3-FR-039 | PASS | DB + application | P3-AC-063, P3-AC-065 | Distinct observation semantics explicit |
| P3-FR-040 | PASS | Calculation/domain | P3-AC-002, P3-AC-015 | Deterministic Decimal boundary explicit |
| P3-FR-041 | PASS | Calculation/domain + DB | P3-AC-015 | Reproducible tuple defined |
| P3-FR-042 | PASS | Domain + frontend | P3-AC-015, P3-AC-040 | Truth states explicit |
| P3-FR-043 | PASS | Domain + application | P3-AC-014, P3-AC-041 | Non-numeric deviation bounded |
| P3-FR-044 | PASS | Domain + DB | P3-AC-016 | Superseded history retained |
| P3-FR-045 | PASS | Application boundary | P3-AC-002, P3-AC-003 | AI diagnosis prohibited |
| P3-FR-046 | AMEND | DB + application | P3-AC-067 | Original reconciliation closed; R04 timing basis remains |
| P3-FR-050 | AMEND | Application + DB | P3-AC-041 | R07: text/resource bounds absent |
| P3-FR-051 | AMEND | API + storage + DB | P3-AC-031, P3-AC-053 | R07: numeric limits absent |
| P3-FR-052 | AMEND | API + storage | P3-AC-031 | R07: response policy/limits incomplete |
| P3-FR-053 | AMEND | Infrastructure + DB | P3-AC-031, P3-AC-053 | R07: storage/serving contract incomplete |
| P3-FR-054 | AMEND | DB + application | P3-AC-031, P3-AC-053 | R07: retention period/disposition absent |
| P3-FR-055 | PASS | Application + DB | P3-AC-041, P3-AC-064 | Journal contents explicit |
| P3-FR-056 | PASS | DB + application | P3-AC-023, P3-AC-064 | Stable ordering specified |
| P3-FR-057 | PASS | Application | P3-AC-041, P3-AC-064 | Bounded exports defined |
| P3-FR-058 | PASS | Application + storage | P3-AC-068 | Failure isolation strongly tested |
| P3-FR-059 | PASS | Domain + application | P3-AC-066 | Deterministic audit defined |
| P3-FR-060 | PASS | Frontend | P3-AC-043, P3-AC-072 | Conditional manual fallback explicit |
| P3-FR-061 | PASS | Frontend + API | P3-AC-043, P3-AC-072 | Draft cannot mutate |
| P3-FR-062 | PASS | Frontend | P3-AC-040, P3-AC-043 | Confirmation presentation testable |
| P3-FR-063 | PASS | API + domain | P3-AC-043, P3-AC-072 | Same validation path explicit |
| P3-FR-064 | PASS | DB + application | P3-AC-043 | Provenance/privacy boundary explicit |
| P3-FR-065 | PASS | Architecture boundary | P3-AC-002, P3-AC-003 | Forward leakage prohibited |
| P3-FR-066 | PASS | Frontend + API + domain | P3-AC-072 | Exact adversarial oracle supplied |
| P3-FR-070 | PASS | API + application | P3-AC-024, P3-AC-041, P3-AC-052 | Complete recovery projection required |
| P3-FR-071 | PASS | DB + application | P3-AC-024, P3-AC-042, P3-AC-069 | Authorities and restart cases explicit |
| P3-FR-072 | AMEND | DB + application | P3-AC-017, P3-AC-063 | R06 residual canonicalization/retention |
| P3-FR-073 | PASS | DB + application | P3-AC-017, P3-AC-063 | Optimistic concurrency explicit |
| P3-FR-074 | PASS | API + frontend | P3-AC-040, P3-AC-041 | Conflict recovery behavior explicit |
| P3-FR-075 | PASS | Architecture | P3-AC-024, P3-AC-069 | PostgreSQL authority explicit |
| P3-FR-076 | AMEND | DB + application | P3-AC-063 | R06: normalization/window missing |
| P3-FR-077 | AMEND | DB + application | P3-AC-063 | R06: command canonical version linkage needed |
| P3-FR-078 | PASS | Application + DB | P3-AC-011, P3-AC-063, P3-AC-064 | Atomic set explicit |
| P3-FR-079 | PASS | DB + infrastructure | P3-AC-069 | Failure matrix and N/A rule explicit |
| P3-FR-080 | AMEND | API + application | P3-AC-030 | R07/R08 security controls incomplete |
| P3-FR-081 | AMEND | API + application | P3-AC-030, P3-AC-031 | R07/R08 affect nested/media surface |
| P3-FR-082 | PASS | Application + DB | P3-AC-023, P3-AC-030, P3-AC-064 | Audit scope explicit |
| P3-FR-083 | AMEND | Application + infrastructure | P3-AC-071 | R07: abuse/resource evidence incomplete |
| P3-FR-084 | AMEND | Presentation + security | P3-AC-002, P3-AC-003, P3-AC-030 | R08: no CSRF disposition |
| P3-FR-085 | PASS | DB + domain | P3-AC-064 | Typed envelope and separation explicit |
| P3-FR-086 | PASS | Application | P3-AC-064 | Projection/nonrollback rule explicit |
| P3-FR-087 | PASS | Application + infrastructure | P3-AC-071 | Reconstruction evidence explicit |
| P3-FR-088 | AMEND | Application + frontend | P3-AC-073 | R09: thresholds not in reviewed contract |

## 10. Acceptance-criterion traceability appendix

| ID | Review | Requirement/control mapping | Evidence layer | Note |
|---|---|---|---|---|
| P3-AC-001 | PASS | Scope boundary, all Phase 3 FRs | Git diff review | Exact baseline comparison required |
| P3-AC-002 | PASS | Deterministic/AI boundary | Architecture review | Decidable |
| P3-AC-003 | PASS | Phase 4–10 boundary | Static inventory | Complete mapping required |
| P3-AC-004 | AMEND | P3-FR-006/007/008 | Playwright regression | R01 affects migrated Phase 2 plan behavior |
| P3-AC-010 | AMEND | P3-FR-002/004/010-013 | API + E2E | R01/R03 prevent one canonical oracle |
| P3-AC-011 | PASS | P3-FR-011/078 | Integration + failure injection | Atomic negative oracle explicit |
| P3-AC-012 | AMEND | P3-FR-012/014/015/037 | Integration + E2E | R03 terminal/pause effects incomplete |
| P3-AC-013 | PASS | P3-FR-020/022 | Integration + E2E | Concrete timer count/restart |
| P3-AC-014 | AMEND | P3-FR-021-024/043/046 | Integration + E2E | R04 lacks schedule formula |
| P3-AC-015 | AMEND | P3-FR-030-033/040-042 | Unit + API + E2E | R05 lacks scientific context oracle |
| P3-AC-016 | PASS | P3-FR-034-037/044 | DB + integration | Append-only chains/waivers |
| P3-AC-017 | AMEND | P3-FR-039/072/073/076/077 | Concurrency integration | R06 canonicalization/retention gap |
| P3-AC-018 | AMEND | P3-FR-015 and terminal rules | API + DB | R03 child terminal effects incomplete |
| P3-AC-020 | PASS | Migration contract | PostgreSQL migration | Exact head required |
| P3-AC-021 | PASS | Migration contract | PostgreSQL round trip | Exact sequence required |
| P3-AC-022 | AMEND | P3-FR-002/006/008 | PostgreSQL preservation | R01 plan backfill/materialization gap |
| P3-AC-023 | PASS | DB invariant inventory | PostgreSQL negative/concurrent tests | Named inventory is strong |
| P3-AC-024 | PASS | P3-FR-070/071/075 | Restart integration | Authority boundaries explicit |
| P3-AC-030 | AMEND | P3-FR-080-084 | Adversarial API/security | R08 lacks CSRF case; R07 abuse limits |
| P3-AC-031 | AMEND | P3-FR-051-054/058 | File/storage security | R07 numeric/serving/retention oracle missing |
| P3-AC-032 | PASS | Artifact hygiene | Repository scan | Concrete categories |
| P3-AC-033 | PASS | Dependency policy | Audit reports | Decidable disposition gate |
| P3-AC-040 | PASS | UI controls/conflicts/voice | Component tests | Suitable layer |
| P3-AC-041 | AMEND | Full Phase 3 slice | PostgreSQL Playwright | R01/R02/R04/R05 prevent one oracle |
| P3-AC-042 | AMEND | P3-FR-014/015/071 | Restart E2E | R03 abort/pause cascade missing |
| P3-AC-043 | PASS | P3-FR-060-066 | Mock capability + E2E | Manual fallback included |
| P3-AC-044 | PASS | Accessibility contract | Automation + manual keyboard | Both layers required |
| P3-AC-045 | PASS | Responsive contract | Three viewport evidence | Concrete widths/classes |
| P3-AC-050 | PASS | Full quality gate | Native suites/build/E2E | Exact candidate required |
| P3-AC-051 | PASS | Dependency/configuration | Audits + Compose config | No deployment inference |
| P3-AC-052 | PASS | Runtime recovery | Disposable authenticated smoke | Real persistence required |
| P3-AC-053 | AMEND | Backup/restore + media | Isolated restore | R07 retention/storage details affect oracle |
| P3-AC-054 | PASS | Stop/cleanup boundary | Runtime receipt | Owner data and NAS protected |
| P3-AC-060 | AMEND | P3-FR-016-019 | PostgreSQL + E2E | R02 API cannot address occurrences |
| P3-AC-061 | AMEND | P3-FR-025-029 | Concurrency + E2E | Reminder lifecycle strong; R03 abort cascade absent |
| P3-AC-062 | PASS | Timer revision model | Unit + PostgreSQL + E2E | Original facts/competition explicit |
| P3-AC-063 | AMEND | P3-FR-076-078 | Failure + concurrency | R06 normalization/retention gap |
| P3-AC-064 | PASS | P3-FR-055-057/078/085/086 | Contract + integration + regeneration | Authority separation explicit |
| P3-AC-065 | AMEND | P3-FR-030-039 | Contract + PostgreSQL | R05 observation context incomplete |
| P3-AC-066 | PASS | P3-FR-059 | Golden + API + E2E | Deterministic counts/status |
| P3-AC-067 | AMEND | P3-FR-023/024/046 | Contract + PostgreSQL + E2E | R04 timing basis missing; zero ledger effect clear |
| P3-AC-068 | PASS | P3-FR-058 | Failure integration + E2E | Isolation/orphan behavior explicit |
| P3-AC-069 | PASS | P3-FR-070-079 | Restart/failure E2E | Broad authoritative matrix |
| P3-AC-070 | PASS | Section 9.1 invariants | PostgreSQL migration/integrity | Named enforcement required |
| P3-AC-071 | PASS | P3-FR-083/087 | Operational reconstruction | Redaction plus correlation evidence |
| P3-AC-072 | PASS | P3-FR-060-066 | Component + E2E | Exact pH adversarial oracle |
| P3-AC-073 | AMEND | P3-FR-088 | Bounded performance | R09 thresholds not yet approved/in contract |

## 11. Phase 4–10 anti-leakage matrix

| Later phase | Prohibited surface | Permitted seam | Result | Evidence |
|---|---|---|---|---|
| Phase 4 | Fermentation/conditioning sessions, curves, alerts, yeast inventory/reuse, troubleshooting | Pitch time, temperature, note/addition fact | PASS | Specification lines 405 and 148; no implementation authorized |
| Phase 5 | QA/QC, CIP, calibration/maintenance workflows, packaging, finished beer/draft | Note/photo plus instrument/method metadata | PASS | Line 406; R05 adds context only, not calibration management |
| Phase 6 | Consumption, reservation conversion, purchasing, forecast, substitutions, calendars/capacity | Planned/actual addition identity with zero ledger mutation | PASS | Lines 407 and 428; P3-FR-046; P3-AC-067 |
| Phase 7 | Academy, assessment, tutoring | Static recipe/process instruction | PASS | Line 408; no AI/tutoring dependency |
| Phase 8 | Experiments, sensory, optimization | Operational deviation/note without sensory semantics | PASS | Line 409 |
| Phase 9 | Competition, AI judge, branding, labels, menus, public availability | None | PASS | Lines 410 and 417 |
| Phase 10 | Profiles, correlations, recommendations, Knowledge Engine | Preserve trustworthy evidence | PASS | Line 411; no analytics/recommendation surface |

Additional exclusions—AI/LLM authority, IoT/hardware, public endpoints, native mobile/offline sync, external notification platform, distributed workflow, speculative schema, NAS deployment, and release tagging—are explicit at specification lines 413-431 and pass this boundary review.

## 12. Architecture and data-integrity assessment

The modular monolith, four-layer dependency direction, PostgreSQL authority, Decimal calculations, UTC storage, additive migration, immutable lineage, typed journal events, separate audit events, deterministic export, and nonauthoritative Redis/browser boundary all pass. The required PostgreSQL invariant table is strong and materially closes the earlier database-enforcement gap.

R01-R04 prevent the domain/API/migration contract from being fully decidable. No new ADR is inherently required for the proposed amendments; they are bounded specification decisions inside the accepted architecture. A new infrastructure subsystem is neither required nor authorized.

## 13. Brewing-domain assessment

The canonical macro-stage vocabulary, yeast-pitch handoff boundary, planned-versus-actual truth states, zero inventory effect, append-only correction model, and avoidance of AI diagnosis are sound. R04 is operationally critical because addition timing can alter the brew. R05 is scientifically material because pH, gravity, and volume observations need enough measurement context to remain comparable without importing Phase 5 calibration workflows.

## 14. Security, media, and voice threat assessment

Ownership-scoped nested identifiers, hidden-resource responses, server-side mutation authority, voice draft/confirm/validate flow, no ambient-audio retention, file signature/MIME checks, generated storage IDs, soft removal, log redaction, and cross-user tests are strong. R07 requires numeric resource and safe serving/retention decisions. R08 requires one explicit CSRF control and adversarial test for the expanded cookie-authenticated mutation surface. These amendments do not authorize public exposure or deployment.

## 15. Test and evidence sufficiency assessment

The required layers correctly distinguish unit/golden, application, API, PostgreSQL, storage, frontend, complete Playwright, backup/restore, and disposable runtime evidence. SQLite is explicitly insufficient for PostgreSQL authority; restore must be isolated; accessibility needs automated and manual evidence; and `NOT RUN` cannot pass.

The acceptance matrix is traceable, but affected gates cannot have a single deterministic oracle until R01-R09 are amended. No test suite was run for this pre-implementation documentation review because static source and code inspection was sufficient and the prompt expressly prohibits broad runtime execution merely to review the specification.

## 16. Required amendments

Apply only the minimal text changes stated in P3SPEC-R01 through P3SPEC-R09. Do not implement code while resolving them. In particular:

1. add the stage-materialization/requiredness table;
2. make repeated stage instances addressable and add the missing bounded stage command capabilities;
3. add the cross-state transition-effect matrix;
4. define addition schedule bases and conversion formulas;
5. add per-measurement semantic/context definitions;
6. fix idempotency canonicalization and minimum retention;
7. set resource, media-serving, and retention limits;
8. state and test the Phase 3 CSRF control; and
9. approve and place performance thresholds in a normative revision or appendix.

## 17. Non-blocking observations

- Numbering gaps in `P3-FR-*` and `P3-AC-*` are reserved-space/editorial choices; all present identifiers are unique.
- Candidate B is the sole tracked file under `docs/specifications` matching the Phase 3 specification name. The reconciliation report and review prompt are evidence/instructions, not competing specifications.
- The roadmap’s relative link resolves to `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`.
- The historical reconciliation report correctly remains a point-in-time pre-remediation artifact and should not be rewritten to claim a later decision.

## 18. Validation receipt

Read-only initial checks recorded:

```text
git status --short                                      -> clean
git branch --show-current                               -> main
git rev-parse HEAD                                      -> 3e11d3100b38bd3a8f4c9262821f8eccfe875e16
git rev-list -n 1 v0.2.0-phase2                         -> c3faa93ea1502db63798b8c0dcc10c02741fabf7
git hash-object docs/specifications/...                 -> e7c163db006ce5615fd9af55196b0f0a32bfebb3
mandatory sources                                      -> 21 named documents + 11 accepted ADRs read completely
specification identifiers                              -> 81 unique P3-FR IDs; 47 unique P3-AC IDs
```

Final artifact validation results:

```text
tracked git diff --check                               -> PASS (no tracked diff)
untracked report trailing-whitespace check            -> PASS (0 defects)
relative Markdown link validation                     -> PASS (0 links; no unresolved target)
functional traceability appendix                      -> PASS (81 rows, 81 unique, exact specification set)
acceptance traceability appendix                      -> PASS (47 rows, 47 unique, exact specification set)
Phase 4–10 anti-leakage matrix                        -> PASS (7 required rows)
machine-readable historical closure JSON              -> PASS (11 total, 11 VERIFIED_CLOSED)
staged files                                           -> 0
untracked files                                        -> exactly this review report
final git status --short                               -> ?? docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_INDEPENDENT_REVIEW.md
```

## 19. Final authorization boundary

```text
PHASE_3_IMPLEMENTATION_NOT_AUTHORIZED_BY_THIS_REVIEW
NAS_PRODUCTION_DEPLOYMENT_NOT_AUTHORIZED
```
