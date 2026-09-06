# Phase 4 Post–Slice 9 Delta Review

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input / Slice 9 HEAD | `c8ec2791be560bedd52dd55e8dd47006373e0174` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_8_DELTA_REVIEW.md` @ `7f3333f5b1aebd4df68deb9b98d37bb38ff41841` |
| Slice 9 evidence | `docs/evidence/PHASE_4_SLICE_9_PLAN_EQUIPMENT_CLOSURE_EVIDENCE.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Ancestry from `v0.4.0-phase4-spec` | PASS |
| Audit type | Bounded delta review only — no application/migration/spec changes |

## Method

- Starting authority: post–Slice-5 master matrix + post–Slice-6/7/8 delta statuses (not rebuilt).
- Slice 9 closures applied only after objective code/test/migration checks against HEAD `c8ec279`.
- Prior evidence artifacts left immutable.

## Slice 9 closure reconciliation

| ID | SPEC | Implementation | Test | Status |
|---|---|---|---|---|
| P4-FR-011 | §10 / §6.3 / §29 | `materialize_phase4_plan` (foundation/schedule/order/templates/hash); `resolve_start_equipment` + immutable `equipment_snapshot`; migration `0011` | `test_phase4_plan_equipment.py` suite | RECONCILED |
| P4-AC-028 | §45 | `DUPLICATE_FERMENTATION_FOUNDATION` → `422 PLAN_MATERIALIZATION_FAILED`, no session row | `test_ac028_duplicate_fermentation_foundation_rejects_start` | RECONCILED |
| P4-AC-049 | §45 | Live `EquipmentProfile` edit leaves GET `equipment_snapshot` unchanged | `test_ac049_adv029_equipment_snapshot_immutable_after_live_edit` | RECONCILED |
| P4-AC-064 | §45 | Abort/restart: same `logical_plan_hash` + template IDs; distinct reminder row IDs; schedule applied | `test_ac064_abort_restart_same_template_ids_and_hash_distinct_rows` | RECONCILED |
| P4-ADV-029 | §46 | Same historical equipment immutability proof as AC-049 | `test_ac049_adv029_*` | RECONCILED |
| P4-ADV-039 | §46 | `details.schedule` participates in SHA-256 / snapshot payload | `test_adv039_schedule_included_in_plan_hash` | RECONCILED |

Objective contract checks (code + tests, not machine-result alone):

| Concern | Result |
|---|---|
| Plan materialization authoritative (`phase4-plan-v1` + stored hash) | PASS |
| Schedule / conditioning_schedule recognition | PASS |
| Ingredient total order for FERMENTATION/DRY_HOP | PASS |
| Template IDs (UUIDv5) ≠ session-owned requirement row IDs | PASS |
| Existing Phase 2 `EquipmentProfile` reused (no second aggregate) | PASS |
| Immutable equipment snapshot at start (§29) | PASS |
| Ownership / forged / missing equipment → 404 | PASS |
| Idempotency includes `equipment_profile_id` | PASS |
| Concurrency (PG FOR UPDATE + unique active-per-brew) | PASS |
| PostgreSQL migration `0011` + round-trip | PASS |
| API association/projection only (no Phase 4 equipment CRUD) | PASS |
| Journal start event carries equipment association facts | PASS |
| Recovery reread of plan + equipment from durable store | PASS |
| Phase 2 equipment regression | PASS |
| Phase 5 leakage (no packaging-equipment workflows) | PASS |

`SLICE_9_FR_RECONCILED=1/1`  
`SLICE_9_AC_RECONCILED=3/3`  
`SLICE_9_ADV_RECONCILED=2/2`

## Incidental closure analysis

| ID | PRIOR_STATUS | IMPLEMENTATION_LOCATION | TEST_LOCATION | FULL_NORMATIVE_CONTRACT_SATISFIED | RECOMMENDED_NEW_STATUS | RATIONALE |
|---|---|---|---|---|---|---|
| P4-FR-087 | PARTIAL | migration head → `0011` | `test_phase4_migration` | NO | Remain PARTIAL | Head advanced; final FR-087/AC-044 campaign still required |
| P4-FR-075 | PARTIAL | start equipment 404 + prior surfaces | integrity tests | NO | Remain PARTIAL | Another owned surface; global nested IDOR still incomplete |
| P4-FR-071/072 | PARTIAL/IMPL on start | start document includes equipment key | idempotency test | NO (already for start family) | Unchanged | Extends existing start idempotency; not new mutation family closure |
| P4-AC-004 | VERIFIED (ENTRY) | richer plan hash at start | existing entry + Slice 9 | YES (already) | Unchanged VERIFIED | Plan hash enrichment fulfills FR-011; AC-004 already credited under ENTRY |
| P4-FR-058 / 059… | unchanged | not in Slice 9 feature set | — | NO | Unchanged | Outside authorized set |

Supporting infra (template ID formula correction in `child_effects`, brew-session `FOR UPDATE` on start) is required for FR-011 completeness, not a separate FR closure.

`INCIDENTAL_FR_CLOSURES=0`  
`INCIDENTAL_AC_CLOSURES=0`  
`INCIDENTAL_ADV_CLOSURES=0`

## Updated Phase 4 totals

| Class | Prior (post–Slice 8) | Delta | Post–Slice 9 |
|---|---|---|---|
| FR IMPLEMENTED | 53/89 | +1 (011 PARTIAL→IMPLEMENTED) | **54/89** |
| FR PARTIAL | 17 | −1 | **16** |
| FR NOT_IMPLEMENTED | 19 | 0 | **19** |
| AC VERIFIED | 39/68 | +3 (028,049,064) | **42/68** |
| AC PARTIAL | 9 | 0 | **9** |
| AC NOT_VERIFIED | 20 | −3 | **17** |
| ADV VERIFIED | 27/42 | +2 (029,039) | **29/42** |
| ADV PARTIAL | 5 | 0 | **5** |
| ADV NOT_VERIFIED | 10 | −2 | **8** |

Reconcile: 54+16+19=89; 42+9+17=68; 29+5+8=42.

## PLAN_EQUIPMENT cluster status

`PLAN_EQUIPMENT_CLUSTER=CLOSED`

| Residual concern | Status |
|---|---|
| Authoritative plan materialization + SHA-256 | CLOSED |
| Schedule / conditioning_schedule keys | CLOSED |
| Template vs session row identity | CLOSED |
| Equipment live identity + immutable snapshot | CLOSED |
| Historical rewrite after live edit | CLOSED |
| Ownership / reference integrity | CLOSED |
| Journal association facts | CLOSED |
| Recovery of association | CLOSED |

No residual accepted FR/AC/ADV remains inside this cluster. Related readiness/waiver/addition work belongs elsewhere.

## Remaining cluster inventory

`PLAN_EQUIPMENT_CLOSURE` is **COMPLETE** and removed from the remaining count.

Cluster structure otherwise unchanged from post–Slice 8.

| CLUSTER_NAME | FR_IDS | AC_IDS | ADV_IDS | CURRENT_STATUS | DEPENDENCIES | DEPENDENCIES_SATISFIED | BLOCKED_BY | CROSS_CUTTING | COMPLEXITY | CAN_START_NOW |
|---|---|---|---|---|---|---|---|---|---|---|
| ACTIONS_ADDITIONS | 052–057,061,070,072(part) | 031–033,048,056,068 | 031,042 | OPEN | PLAN+ACTIVE | YES | NONE | NO | LARGE | YES |
| DEVIATIONS | 058 | — | — | OPEN | measurements | YES | NONE | NO | SMALL | YES |
| WAIVERS_READINESS | 059,060 | 051,054,059 | 008,035 | OPEN | conditioning/complete (+ OG UNKNOWN available) | YES | NONE | NO | MEDIUM | YES |
| PACKAGING_READINESS_CLOSE | 013,015(part),022,044,043(part),074(part),008(part),089 | 007,011,017,025,026,047,058,061 | 012,023,033 | OPEN | WAIVERS + CONDITIONING_COMPLETE | NO | WAIVERS_READINESS | NO | LARGE | NO |
| JOURNAL_MEDIA_EXPORT | 062–065 | 046,052 | 013,019 | OPEN | journal writers | YES | NONE | NO | MEDIUM | YES |
| FRONTEND_E2E | 082 | 045,050 | — | OPEN | sufficient backend surfaces | PARTIAL | more backend preferred before UI | YES | LARGE | NO* |
| FINAL_ACCEPTANCE | 076,080,081,084–087 | 001–003,039–044 | 014,016,017,030 | OPEN | all features | NO | feature clusters | YES | LARGE | NO |

\*Frontend mechanically startable; dependency ordering still prefers core backend frontiers first.

`REMAINING_IMPLEMENTATION_CLUSTER_COUNT=7` (6 feature + final acceptance)

## Remaining yeast requirements

| Metric | Prior (post–Slice 8) | Post–Slice 9 |
|---|---|---|
| YEAST_REQUIREMENTS_TOTAL | 19 | **19** |
| YEAST_REQUIREMENTS_IMPLEMENTED | 15 | **15** (unchanged) |
| YEAST_REQUIREMENTS_REMAINING | 4 | **4** |

| ID | OWNING_CLUSTER | CURRENT_STATUS | DEPENDENCIES | DEPENDENCIES_SATISFIED | CAN_START_NOW |
|---|---|---|---|---|---|
| P4-FR-070 | ACTIONS_ADDITIONS | NOT_IMPLEMENTED (ledger absence proof with additions) | additions/readiness | YES (cluster deps) | YES (via ACTIONS) |
| P4-AC-054 | WAIVERS_READINESS | NOT_VERIFIED | FR-060 non-waivable yeast note / pitched_at | YES | YES (via WAIVERS) |
| P4-ADV-008 | WAIVERS_READINESS | NOT_VERIFIED | FR-060 waiver prohibition | YES | YES (via WAIVERS) |
| P4-FR-075 | CROSS_CUTTING / FINAL_ACCEPTANCE | PARTIAL | global nested IDOR | PARTIAL | NO as yeast slice |

No remaining primarily yeast feature cluster. Do **not** force a yeast Slice 10.

## Frontend / Playwright gap

`PHASE_4_FRONTEND_REMAINING=YES` (unchanged; Slice 9 `FRONTEND_ACCEPTANCE=NOT_REQUIRED`).

| Set | IDs |
|---|---|
| FRONTEND_FR_IDS | P4-FR-082 |
| FRONTEND_AC_IDS | P4-AC-045, P4-AC-050 |
| FRONTEND_ADV_IDS | — |
| FRONTEND_DEPENDENCIES | Happy-path backend through conditioning (ideally packaging readiness) before canonical E2E |
| FRONTEND_CAN_START_NOW | NO |

Frontend timing: **AFTER_MORE_DOMAIN_WORK** (WAIVERS → PACKAGING), then FINAL_INTEGRATION before FINAL_ACCEPTANCE.

Domain prerequisites for a thin conditioning happy-path UI are partially present, but packaging readiness and waivers remain open; do not start FRONTEND_E2E as Slice 10.

## AI boundary

`AI_BOUNDARY=PARTIAL` (unchanged).

| Remaining item | Classification |
|---|---|
| P4-AC-002 executable AI non-authority + packaging absence | FINAL_ACCEPTANCE_EVIDENCE_ONLY |
| P4-FR-086 / AC-002/003 Phase 5+ leakage scan | FINAL_ACCEPTANCE_EVIDENCE_ONLY |
| Slice 9 plan/equipment authority preservation | Verified `SLICE_9_AI_AUTHORITY_VIOLATION=NO`; not sufficient for global PASS |

No authorized Phase 4 AI-assistance feature remains to implement.

## Media / evidence / provenance

| ID | OWNING_CLUSTER | CURRENT_STATUS | IMPLEMENTATION_REQUIRED | DEPENDENCIES | CAN_START_NOW |
|---|---|---|---|---|---|
| P4-FR-064, P4-AC-052, P4-ADV-013 | JOURNAL_MEDIA_EXPORT | NOT_IMPLEMENTED / NOT_VERIFIED | YES | journal writers | YES (via JOURNAL) |
| P4-FR-062,065, P4-AC-046, P4-ADV-019 | JOURNAL_MEDIA_EXPORT | NOT_IMPLEMENTED / PARTIAL | YES | journal writers | YES (via JOURNAL) |
| Equipment §29 / plan §10 | PLAN_EQUIPMENT | CLOSED (Slice 9) | NO | — | — |
| Yeast §11 FR-066–069 | COMPLETE (Slice 6) | IMPLEMENTED | NO | — | — |
| OG pin FR-004/005 | COMPLETE (Slice 7) | IMPLEMENTED | NO | — | — |
| Calc projection FR-036 | COMPLETE (Slice 8) | IMPLEMENTED | NO | — | — |

## Journal / audit

| Class | IDs |
|---|---|
| FEATURE_IMPLEMENTATION_REQUIRED | P4-FR-062,063(part),064,065; P4-AC-046,052; P4-ADV-013,019 → `JOURNAL_MEDIA_EXPORT` |
| FINAL_ACCEPTANCE_ONLY | Full merge/export regression on final candidate; access-audit if required by final campaign |

Start journal enrichment in Slice 9 is infrastructure for FR-011, not closure of JOURNAL_MEDIA_EXPORT.

## Security / ownership / idempotency / concurrency

| Theme | Classification |
|---|---|
| Global nested IDOR FR-075 / AC-038 | FEATURE_IMPLEMENTATION_REQUIRED (extend per new mutation surface) + FINAL_ACCEPTANCE_ONLY |
| CSRF FR-076 / AC-039 / ADV-014 | FINAL_ACCEPTANCE_ONLY |
| Concurrency Close/addition races | FEATURE_IMPLEMENTATION_REQUIRED after PACKAGING/ACTIONS; else FINAL_ACCEPTANCE_ONLY |
| Idempotency FR-071/072 | FEATURE_IMPLEMENTATION_REQUIRED for new mutation families + FINAL_ACCEPTANCE_ONLY |
| Start equipment concurrency (Slice 9) | Closed for start association; not a substitute for Close/addition races |

Do not open a generic security-only feature slice.

## Recovery / backup / restore

| ID | STATUS | OWNING_CLUSTER | IMPLEMENTATION_REQUIRED | FINAL_ACCEPTANCE_ONLY | CAN_START_NOW |
|---|---|---|---|---|---|
| P4-FR-078/079 | IMPLEMENTED on closed surfaces (incl. Slice 9 plan/equipment reread) | FINAL_ACCEPTANCE re-proof | NO (new feature) | YES | — |
| P4-FR-080 / AC-040 / ADV-030 | NOT_IMPLEMENTED | FINAL_ACCEPTANCE | NO (campaign) | YES | NO |

## Performance / accessibility

| ID | OWNING_CLUSTER | CURRENT_STATUS | IMPLEMENTATION_REQUIRED | FINAL_ACCEPTANCE_ONLY | DEPENDENCIES | CAN_START_NOW |
|---|---|---|---|---|---|---|
| P4-FR-081 / AC-041 / ADV-016 | FINAL_ACCEPTANCE | NOT_IMPLEMENTED | NO (harness campaign) | YES | feature surfaces | NO |
| P4-FR-082 / AC-045,050 | FRONTEND_E2E | NOT_IMPLEMENTED | YES (feature UI + a11y) | then final E2E proof | more domain preferred | NO as Slice 10 |

## Convergence assessment

`PHASE_4_CONVERGENCE_STATE=DOMAIN_HEAVY`

| Metric | Value |
|---|---|
| REMAINING_BACKEND_CLUSTER_COUNT | **5** (ACTIONS, DEVIATIONS, WAIVERS, PACKAGING, JOURNAL) |
| REMAINING_FRONTEND_OR_INTEGRATION_CLUSTER_COUNT | **1** (FRONTEND_E2E) |
| Evidence | Five independent domain/backend clusters remain before UI; packaging still blocked by waivers |

## Dependency frontier (eligible now)

| CLUSTER | FR_IDS | AC_IDS | ADV_IDS | FR/AC/ADV | DEPENDENCIES | WHY_UNBLOCKED | COHERENCE | COMPLEXITY | UNCERTAINTY_REDUCTION | DOWNSTREAM_UNLOCK | UNLOCKS | PHASE_5_LEAKAGE_RISK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEVIATIONS | 058 | — | — | 1/0/0 | measurements | Measurement foundation exists; PLAN_EQUIPMENT no longer competing small | HIGH | SMALL | MEDIUM | MEDIUM | §22 deviation identity | NONE |
| WAIVERS_READINESS | 059,060 | 051,054,059 | 008,035 | 2/3/2 | conditioning + OG UNKNOWN | Conditioning + UNKNOWN OG closed | HIGH | MEDIUM | HIGH | HIGH | Unblocks PACKAGING_READINESS_CLOSE | NONE |
| JOURNAL_MEDIA_EXPORT | 062–065 | 046,052 | 013,019 | 4/2/2 | journal writers | Append-only journal exists | MEDIUM | MEDIUM | MEDIUM | MEDIUM | Export/media | NONE |
| ACTIONS_ADDITIONS | 052–057,… | 031–033,… | 031,042 | large | PLAN+ACTIVE | Plan+ACTIVE exist; plan completeness improved by Slice 9 | MEDIUM | LARGE | HIGH | HIGH | Proves FR-070; terminal addition | LOW (must not invent packaging ops) |

## Selected Slice 10

| Field | Value |
|---|---|
| RECOMMENDED_NEXT_SLICE | `DEVIATIONS` |
| NEXT_SLICE_FR_IDS | P4-FR-058 |
| NEXT_SLICE_AC_IDS | — (none exclusively owned; mapping table cites AC-020/ADV-006 as related evidence surfaces elsewhere — do **not** pull measurement/completion ACs into this slice) |
| NEXT_SLICE_ADV_IDS | — |
| NEXT_SLICE_DEPENDENCIES | SATISFIED |
| NEXT_SLICE_SCOPE_COHERENT | YES |
| NEXT_SLICE_PHASE_5_LEAKAGE | NO |
| WHY_THIS_SLICE_NEXT | Smallest coherent unblocked frontier after PLAN_EQUIPMENT: single FR (§22 derived deviations with identity/supersession). Preserves established post–Slice-8 path (deviations small before WAIVERS unlock of packaging). Does not mix waivers, packaging, additions, journal/media, or UI. |
| NEXT_SLICE_COULD_COMPLETE_PHASE_4_FEATURE_IMPLEMENTATION | NO |

Parallel eligible note: `WAIVERS_READINESS` remains the highest-unlock alternate and may be chosen instead if architecture prefers packaging critical path over the smallest frontier; it does not supersede DEVIATIONS under the documented selection order (smallest reasonable frontier before unlock preference).

## Remaining path to feature-complete

```
SLICE_10 = DEVIATIONS
THEN FRONTIER ->
  - WAIVERS_READINESS
  - ACTIONS_ADDITIONS (capacity-parallel; proves FR-070)
  - JOURNAL_MEDIA_EXPORT
THEN ->
  PACKAGING_READINESS_CLOSE (after WAIVERS)
THEN ->
  FRONTEND_E2E
THEN ->
  FINAL_ACCEPTANCE (implementation candidate + independent review)
```

`REMAINING_IMPLEMENTATION_CLUSTER_COUNT=7`  
`NEXT_SLICE_COULD_COMPLETE_PHASE_4_FEATURE_IMPLEMENTATION=NO`

## Final-acceptance-only work

`FINAL_ACCEPTANCE_ONLY_WORK_IDENTIFIED=YES`

- Complete 89/68/42 traceability reconciliation on final candidate
- PostgreSQL acceptance (§32 full matrix)
- Migration round-trip (FR-087 / AC-044) including `0011`+
- Concurrency suite (Close/addition races once features exist)
- Security suite (CSRF FR-076 / AC-039 / ADV-014; global IDOR FR-075)
- Recovery re-proof
- Performance harness §37 (FR-081)
- Accessibility + Playwright Phase 4 + Phase 1A/2/3 regressions (FR-082/084/085)
- Backup/restore §35 (FR-080)
- Full Phase 4 integration + Phase 5 leakage review (FR-086 / AC-002/003)
- Consolidated implementation evidence

## Declarations

- `PHASE_4_IMPLEMENTATION_CANDIDATE=NOT_YET_ASSIGNED`
- `PHASE_4_IMPLEMENTATION_ACCEPTANCE=NOT_YET_GRANTED`
- `PHASE_5_IMPLEMENTATION=NOT_AUTHORIZED`
- Spec / prior evidence artifacts not modified by this review.
- Slice 10 not started.
