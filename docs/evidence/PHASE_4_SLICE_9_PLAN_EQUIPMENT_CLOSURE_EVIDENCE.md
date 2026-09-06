# Phase 4 Slice 9 Evidence — Plan Equipment Closure

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `7f3333f5b1aebd4df68deb9b98d37bb38ff41841` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_8_DELTA_REVIEW.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `PLAN_EQUIPMENT_CLOSURE` |
| Ancestry from `v0.4.0-phase4-spec` | PASS |

## Exact normative extraction

| ID | SPEC_SECTION | NORMATIVE_RULE | DEPENDENCIES | CURRENT_IMPLEMENTATION (pre-slice) | MISSING | SURFACE |
|---|---|---|---|---|---|---|
| P4-FR-011 | §10 / §6.3 / §29 | Atomic `phase4-plan-v1` materialization with SHA-256; recognize `schedule`/`conditioning_schedule`; ingredient total order; template IDs ≠ session row IDs; optional fermenter equipment snapshotted at start | ENTRY | Default stage plan only; no foundation/schedule/equipment snapshot | Full §10 mapping + §29 snapshot | `plan.py`, `equipment.py`, `commands.py`, migration `0011` |
| P4-AC-028 | §45 | Duplicate `FERMENTATION_FOUNDATION` → start `422`, no session | FR-011 | Absent | Reject + no write | `test_ac028_*` |
| P4-AC-049 | §45 | Live equipment edit after start → GET snapshot JSON unchanged | FR-011 / §29 | No snapshot | Immutable JSON | `test_ac049_adv029_*` |
| P4-AC-064 | §45 | Abort then restart with `details.schedule` → same template IDs + logical hash; distinct row IDs; schedule applied | FR-011 | Partial default plan | Schedule + template identity | `test_ac064_*` |
| P4-ADV-029 | §46 | Live equipment edit → historical GET unchanged | AC-049 | Same gap | Same proof | `test_ac049_adv029_*` |
| P4-ADV-039 | §46 | `details.schedule` present → schedule in snapshot hash, not ignored | AC-064 | Hash ignored schedule | Canonical schedule in hash | `test_adv039_*` |

### Why three ACs and two ADVs attach to FR-011

FR-011 owns **plan materialization authority** (hash, schedule keys, template vs row identity) and, via §6.3/§29, **equipment snapshot authority** at start. AC-028/064/ADV-039 exercise the plan/hash/schedule side; AC-049/ADV-029 exercise historical equipment immutability. No separate equipment FR is required for this cluster.

## Existing equipment-domain reuse

- Authoritative live identity remains Phase 2 `EquipmentProfile` (`equipment_profiles`).
- Phase 4 stores only `source_equipment_profile_id` (nullable FK `ON DELETE SET NULL`) plus immutable `equipment_snapshot` JSON on `fermentation_sessions`.
- No second equipment aggregate; no Phase 4 equipment CRUD.

`EXISTING_EQUIPMENT_DOMAIN_REUSED=YES`

## Plan / session equipment association model

| Concern | Contract | Implementation |
|---|---|---|
| Association locus | Fermentation session at start | `FermentationSession.source_equipment_profile_id` + `equipment_snapshot` |
| Selection | Explicit start `equipment_profile_id`, else recipe version profile, else none | `resolve_start_equipment` |
| Snapshot contents | Calc-relevant fields + `source_equipment_profile_id` + `snapshotted_at` + `source_deleted=false` | `build_fermentation_equipment_snapshot` |
| Absence | Lawful; fermenter identity `UNSPECIFIED` | GET `fermenter_identity` |

`PLAN_EQUIPMENT_ASSOCIATION=PASS`

## Historical / snapshot behavior

Model **C**: live identity reference (nullable FK) + immutable snapshot JSON at association time. Later live profile edits do not rewrite historical JSON (AC-049 / ADV-029).

`EQUIPMENT_HISTORY_CONTRACT=PASS`

## Ownership / reference integrity

| Case | Result |
|---|---|
| Missing / forged equipment ID | `404` Equipment profile not found |
| Cross-owner brew + equipment | `404` brew nondisclosure |
| No equipment | Lawful `UNSPECIFIED` |
| Duplicate concurrent start | One `201`, one `409 FERMENTATION_SESSION_EXISTS` (PG FOR UPDATE + unique index) |

`EQUIPMENT_REFERENCE_INTEGRITY=PASS`  
`SECURITY_ACCEPTANCE=PASS`

## Revision behavior

Equipment association occurs only at start; historical sessions are not rewritten. Plan facts are versioned via immutable `FermentationPlanSnapshot`. No post-start equipment revision command in this slice.

`PLAN_EQUIPMENT_REVISION_CONTRACT=NOT_APPLICABLE`

## Idempotency

Start canonical document includes `equipment_profile_id`. Same key + same payload replays; same key + conflicting equipment ID → `409 IDEMPOTENCY_KEY_REUSED`.

`IDEMPOTENCY_CONTRACT=PASS`

## Concurrency

PostgreSQL: `SELECT … FOR UPDATE` on brew session before create; unique partial index `uq_fermentation_one_active_per_brew`; IntegrityError mapped to `409`.

`CONCURRENCY_CONTRACT=PASS` — `test_concurrent_start_one_session_with_equipment`

## PostgreSQL / migration

| Item | Result |
|---|---|
| Migration | `0011_phase4_plan_equipment` (new only) |
| Columns | `source_equipment_profile_id` FK SET NULL; `equipment_snapshot` JSON |
| Phase 1–3 migrations | Unchanged |
| Round-trip | `test_phase4_migration` PASS on disposable DB |

`POSTGRESQL_ACCEPTANCE=PASS`  
`MIGRATION_ACCEPTANCE=PASS`  
`PHASE_3_MIGRATIONS_UNCHANGED=YES`  
`PHASE_3_MIGRATION_ANCESTRY=PASS`

## API

- Start accepts optional `equipment_profile_id`.
- GET session exposes `equipment_snapshot`, `source_equipment_profile_id`, `fermenter_identity`, enriched `plan_snapshot.payload` (schedule, templates, conditioning).
- No Phase 4 equipment CRUD.

`API_ACCEPTANCE=PASS`

## Journal / audit

`FERMENTATION_SESSION_STARTED` event_data includes `logical_plan_hash`, `source_equipment_profile_id`, `equipment_snapshotted`.

`JOURNAL_ACCEPTANCE=PASS`

## Recovery

Fresh TestClient / login re-reads plan hash, schedule, and equipment snapshot from PostgreSQL/SQLite persistence.

`RECOVERY_ACCEPTANCE=PASS`

## AC / ADV proof traces

| ID | Governing | Implementation | Test ID | Evidence |
|---|---|---|---|---|
| P4-AC-028 | P4-FR-011 §10.1 | `materialize_phase4_plan` duplicate reject | `test_ac028_duplicate_fermentation_foundation_rejects_start` | this section |
| P4-AC-049 | P4-FR-011 §29 | immutable `equipment_snapshot` | `test_ac049_adv029_equipment_snapshot_immutable_after_live_edit` | this section |
| P4-AC-064 | P4-FR-011 §10.2–10.3 | schedule + UUIDv5 templates + distinct reminder PKs | `test_ac064_abort_restart_same_template_ids_and_hash_distinct_rows` | this section |
| P4-ADV-029 | AC-049 | same test | `test_ac049_adv029_*` | this section |
| P4-ADV-039 | AC-064 / FR-011 | schedule in `logical_plan_hash` | `test_adv039_schedule_included_in_plan_hash` | this section |

`P4_AC_028=PASS` `P4_AC_049=PASS` `P4_AC_064=PASS`  
`P4_ADV_029=PASS` `P4_ADV_039=PASS`

## Frontend / AI / Phase 5

| Gate | Result |
|---|---|
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| PLAYWRIGHT_ACCEPTANCE | NOT_REQUIRED |
| SLICE_9_AI_AUTHORITY_VIOLATION | NO |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |

## Regressions

| Suite | Result |
|---|---|
| Slice 9 plan/equipment (SQLite) | PASS (9 passed, 1 skipped concurrency) |
| Slice 9 concurrency + migration (PostgreSQL) | PASS |
| Phase 4 prior slices (entry/lifecycle/measurements/conditioning/timers/yeast/og/calc/pitch) | PASS |
| Phase 2 equipment domain | PASS |
| Phase 1A / Phase 3 materialization samples | PASS (executed with Phase 2) |

## Traceability

| ID | Spec | Implementation | Test | Evidence |
|---|---|---|---|---|
| P4-FR-011 | §10, §6.3, §29 | `plan.py`, `equipment.py`, `commands.py`, `0011` | `test_phase4_plan_equipment.py` | this artifact |
| P4-AC-028 | §45 | `PlanMaterializationError` DUPLICATE | `test_ac028_*` | this artifact |
| P4-AC-049 | §45 | session equipment_snapshot | `test_ac049_adv029_*` | this artifact |
| P4-AC-064 | §45 | templates + hash + schedule | `test_ac064_*` | this artifact |
| P4-ADV-029 | §46 | same as AC-049 | `test_ac049_adv029_*` | this artifact |
| P4-ADV-039 | §46 | schedule in hash | `test_adv039_*` | this artifact |

`SLICE_9_FR_IMPLEMENTED=1/1`  
`SLICE_9_AC_VERIFIED=3/3`  
`SLICE_9_ADV_VERIFIED=2/2`  
`TRACEABILITY=PASS`

## Self-review

Falsified: forged equipment, cross-owner, missing equipment, duplicate concurrent start, live edit after snapshot, abort/restart template collision, schedule omitted from hash, response-loss idempotency, restart reread. No specification contradiction encountered.

`IMPLEMENTATION_SELF_REVIEW=PASS`
