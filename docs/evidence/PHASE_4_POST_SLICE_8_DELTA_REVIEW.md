# Phase 4 Post–Slice 8 Delta Review

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input / Slice 8 HEAD | `0deceb00f90feaab9ae105c83221b705b1404b39` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_7_DELTA_REVIEW.md` @ `14b006bc6fb14158e04a15e4c88656ce131db85f` |
| Slice 8 evidence | `docs/evidence/PHASE_4_SLICE_8_CALC_READ_MODEL_CLOSURE_EVIDENCE.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Ancestry from `v0.4.0-phase4-spec` | PASS |
| Audit type | Bounded delta review only — no application/migration/spec changes |

## Method

- Starting authority: post–Slice-5 master matrix + post–Slice-6/7 delta statuses (not rebuilt).
- Slice 8 closures applied only after objective code/test/migration checks against HEAD `0deceb0`.
- Prior evidence artifacts left immutable.

## Slice 8 closure reconciliation

| ID | SPEC | Implementation | Test | Status |
|---|---|---|---|---|
| P4-FR-036 | §13 / §28 | `try_abv_percent` → persisted `abv_percent` on `FermentationDerivedGravitySnapshot`; session GET exposure; migration `0010` | `test_ac021_abv_exposed_*`, unknown/correction/reconcile | RECONCILED |
| P4-AC-021 | §45 | Domain goldens for attenuation/progress/ABV + read-model ABV vectors including undefined | `test_ac021_domain_goldens_*` + read-model suite | RECONCILED |
| ADV | — | None assigned | — | N/A (`0/0`) |

Objective contract checks (code + tests, not machine-result alone):

| Concern | Result |
|---|---|
| Deterministic authority outside frontend/LLM (`packages.calculations`) | PASS |
| Authoritative calculation read model (`derived_gravity.abv_percent`) | PASS |
| Authoritative sources (KNOWN OG pin + effective FG leaves) | PASS |
| UNKNOWN/unresolved prerequisites → null, no fabrication | PASS |
| Correction recomputation (flush-before-recompute + correction tests) | PASS |
| OG reconcile updates ABV only after explicit reconcile | PASS |
| Provenance/version (`calculation_version`, source IDs, `evaluated_at`) | PASS |
| Persistence/reconstruction after GET | PASS |
| Concurrency/read consistency (same-txn projection after flush) | PASS |
| Security (forged/cross-owner session GET → 404) | PASS |
| Recovery (fresh GET from durable snapshot) | PASS |

Supporting fix required for FR-036 completeness: with `SessionLocal(autoflush=False)`, gravity record/correct now **flushes before** `recompute_derived_gravity`, so snapshots include the new leaf. This is infrastructure for the authorized calc read model, not a separate FR closure.

`SLICE_8_FR_RECONCILED=1/1`  
`SLICE_8_AC_RECONCILED=1/1`  
`SLICE_8_ADV_RECONCILED=0/0`

## Incidental closure analysis

| ID | PRIOR_STATUS | IMPLEMENTATION_LOCATION | TEST_LOCATION | FULL_NORMATIVE_CONTRACT_SATISFIED | RECOMMENDED_NEW_STATUS | RATIONALE |
|---|---|---|---|---|---|---|
| P4-FR-033 | IMPLEMENTED | flush-before-recompute also feeds attenuation | existing + Slice 8 goldens | YES (already) | Unchanged IMPLEMENTED | Attenuation was already closed; flush fix improves projection fidelity only |
| P4-FR-034 | IMPLEMENTED | domain progress goldens re-asserted | `test_ac021_domain_goldens_*` | YES (already) | Unchanged IMPLEMENTED | Progress remains domain-closed; not newly persisted |
| P4-FR-087 | PARTIAL | migration `0010` | `test_phase4_migration` | NO | Remain PARTIAL | Head advanced; final FR-087/AC-044 campaign still required |
| P4-FR-075 | PARTIAL | cross-owner GET 404 on calc surface | `test_calc_read_model_cross_owner_404` | NO | Remain PARTIAL | One more surface; global nested IDOR still incomplete |
| P4-FR-011 / 058 / 059… | unchanged | not in Slice 8 diff beyond calc | — | NO | Unchanged | Outside authorized set |

`INCIDENTAL_FR_CLOSURES=0`  
`INCIDENTAL_AC_CLOSURES=0`  
`INCIDENTAL_ADV_CLOSURES=0`

## Updated Phase 4 totals

| Class | Prior (post–Slice 7) | Delta | Post–Slice 8 |
|---|---|---|---|
| FR IMPLEMENTED | 52/89 | +1 (036 PARTIAL→IMPLEMENTED) | **53/89** |
| FR PARTIAL | 18 | −1 | **17** |
| FR NOT_IMPLEMENTED | 19 | 0 | **19** |
| AC VERIFIED | 38/68 | +1 (021 gap closed) | **39/68** |
| AC PARTIAL | 9 | 0 | **9** |
| AC NOT_VERIFIED | 21 | −1 | **20** |
| ADV VERIFIED | 27/42 | 0 | **27/42** |
| ADV PARTIAL | 5 | 0 | **5** |
| ADV NOT_VERIFIED | 10 | 0 | **10** |

Reconcile: 53+17+19=89; 39+9+20=68; 27+5+10=42.

Note: FR-036 moved from PARTIAL (not NOT_IMPLEMENTED). AC-021 was tracked as remaining/gap after Slice 7 yeast inventory despite earlier domain attenuation/progress proof; Slice 8 closes the ABV read-model gap and promotes it to VERIFIED in running totals.

## CALC_READ_MODEL cluster status

`CALC_READ_MODEL_CLUSTER=CLOSED`

| Residual concern | Status |
|---|---|
| ABV availability follows authoritative OG/FG state | CLOSED |
| Unresolved prerequisites do not fabricate output | CLOSED |
| Corrections update current projection | CLOSED |
| Provenance/version metadata sufficient for §13 snapshot | CLOSED |
| Session GET contains `abv_percent` | CLOSED |
| Persistence/reconstruction after restart/GET | CLOSED |

No residual accepted FR/AC/ADV remains inside this cluster.

## Remaining cluster inventory

`CALC_READ_MODEL_CLOSURE` is **COMPLETE** and removed from the remaining count.

Cluster structure otherwise unchanged from post–Slice 7.

| CLUSTER_NAME | FR_IDS | AC_IDS | ADV_IDS | CURRENT_STATUS | DEPENDENCIES | DEPENDENCIES_SATISFIED | BLOCKED_BY | CROSS_CUTTING | COMPLEXITY | CAN_START_NOW |
|---|---|---|---|---|---|---|---|---|---|---|
| ACTIONS_ADDITIONS | 052–057,061,070,072(part) | 031–033,048,056,068 | 031,042 | OPEN | PLAN+ACTIVE | YES | NONE | NO | LARGE | YES |
| DEVIATIONS | 058 | — | — | OPEN | measurements | YES | NONE | NO | SMALL | YES |
| WAIVERS_READINESS | 059,060 | 051,054,059 | 008,035 | OPEN | conditioning/complete (+ OG UNKNOWN available) | YES | NONE | NO | MEDIUM | YES |
| PACKAGING_READINESS_CLOSE | 013,015(part),022,044,043(part),074(part),008(part),089 | 007,011,017,025,026,047,058,061 | 012,023,033 | OPEN | WAIVERS + CONDITIONING_COMPLETE | NO | WAIVERS_READINESS | NO | LARGE | NO |
| JOURNAL_MEDIA_EXPORT | 062–065 | 046,052 | 013,019 | OPEN | journal writers | YES | NONE | NO | MEDIUM | YES |
| PLAN_EQUIPMENT_CLOSURE | 011(part) | 028,049,064 | 029,039 | OPEN | ENTRY | YES | NONE | NO | SMALL | YES |
| FRONTEND_E2E | 082 | 045,050 | — | OPEN | sufficient backend surfaces | PARTIAL | more backend preferred before UI | YES | LARGE | NO* |
| FINAL_ACCEPTANCE | 076,080,081,084–087 | 001–003,039–044 | 014,016,017,030 | OPEN | all features | NO | feature clusters | YES | LARGE | NO |

\*Frontend mechanically startable; dependency ordering still prefers core backend frontiers first.

`REMAINING_IMPLEMENTATION_CLUSTER_COUNT=8` (7 feature + final acceptance)

## Remaining yeast requirements

| Metric | Prior (post–Slice 7) | Post–Slice 8 |
|---|---|---|
| YEAST_REQUIREMENTS_TOTAL | 19 | **19** |
| YEAST_REQUIREMENTS_IMPLEMENTED | 14 | **15** (+ AC-021) |
| YEAST_REQUIREMENTS_REMAINING | 5 | **4** |

| ID | OWNING_CLUSTER | DEPENDENCIES | DEPENDENCIES_SATISFIED | CAN_START_NOW |
|---|---|---|---|---|
| P4-FR-070 | ACTIONS_ADDITIONS | additions/readiness ledger proof | YES (cluster deps) | YES (via ACTIONS) |
| P4-AC-054 | WAIVERS_READINESS | FR-060 non-waivable yeast note / pitched_at | YES | YES (via WAIVERS) |
| P4-ADV-008 | WAIVERS_READINESS | FR-060 waiver prohibition | YES | YES (via WAIVERS) |
| P4-FR-075 | CROSS_CUTTING / FINAL_ACCEPTANCE | global nested IDOR | PARTIAL | NO as yeast slice |

No remaining primarily yeast feature cluster. Do **not** force a yeast Slice 9.

## Frontend / Playwright gap

`PHASE_4_FRONTEND_REMAINING=YES` (unchanged; Slice 8 `FRONTEND_ACCEPTANCE=NOT_REQUIRED`).

| Set | IDs |
|---|---|
| FRONTEND_FR_IDS | P4-FR-082 |
| FRONTEND_AC_IDS | P4-AC-045, P4-AC-050 |
| FRONTEND_ADV_IDS | — |
| FRONTEND_DEPENDENCIES | Happy-path backend through conditioning (ideally packaging readiness) before canonical E2E |
| FRONTEND_CAN_START_NOW | NO |

Frontend timing: **AFTER_MORE_DOMAIN_WORK** (WAIVERS → PACKAGING), then FINAL_INTEGRATION before FINAL_ACCEPTANCE.

## AI boundary

`AI_BOUNDARY=PARTIAL` (unchanged).

| Remaining item | Classification |
|---|---|
| P4-AC-002 executable AI non-authority + packaging absence | FINAL_ACCEPTANCE_EVIDENCE_ONLY |
| P4-FR-086 / AC-002/003 Phase 5+ leakage scan | FINAL_ACCEPTANCE_EVIDENCE_ONLY |
| Slice 8 calc authority preservation | Verified `SLICE_8_AI_AUTHORITY_VIOLATION=NO`; not sufficient for global PASS |

No authorized Phase 4 AI-assistance feature remains to implement.

## Media / equipment / provenance

| ID | OWNING_CLUSTER | CURRENT_STATUS | DEPENDENCIES | IMPLEMENTATION_REQUIRED |
|---|---|---|---|---|
| P4-FR-064, P4-AC-052, P4-ADV-013 | JOURNAL_MEDIA_EXPORT | NOT_IMPLEMENTED / NOT_VERIFIED | journal writers | YES |
| P4-FR-062,065, P4-AC-046, P4-ADV-019 | JOURNAL_MEDIA_EXPORT | NOT_IMPLEMENTED / PARTIAL | journal writers | YES |
| P4-FR-011(part), P4-AC-028/049/064, P4-ADV-029/039 | PLAN_EQUIPMENT_CLOSURE | PARTIAL / gaps | ENTRY | YES |
| Yeast §11 FR-066–069 | COMPLETE (Slice 6) | IMPLEMENTED | — | NO |
| OG pin FR-004/005 | COMPLETE (Slice 7) | IMPLEMENTED | — | NO |
| Calc projection FR-036 | COMPLETE (Slice 8) | IMPLEMENTED | — | NO |

## Journal / audit

| Class | IDs |
|---|---|
| JOURNAL_FEATURE_GAPS | P4-FR-062,063(part),064,065; P4-AC-046,052; P4-ADV-013,019 → `JOURNAL_MEDIA_EXPORT` |
| JOURNAL_FINAL_ACCEPTANCE_ONLY | Full merge/export regression on final candidate; access-audit if required by final campaign |

## Security / idempotency / concurrency / recovery

| Theme | Classification |
|---|---|
| Global nested IDOR FR-075 / AC-038 | FEATURE_IMPLEMENTATION_REQUIRED (extend per new mutation surface) + FINAL_ACCEPTANCE_ONLY |
| CSRF FR-076 / AC-039 / ADV-014 | FINAL_ACCEPTANCE_ONLY |
| Concurrency Close/addition races | FEATURE_IMPLEMENTATION_REQUIRED after PACKAGING/ACTIONS; else FINAL_ACCEPTANCE_ONLY |
| Idempotency FR-071/072 | FEATURE_IMPLEMENTATION_REQUIRED for new mutation families + FINAL_ACCEPTANCE_ONLY |
| Recovery FR-078/079 | FINAL_ACCEPTANCE_ONLY re-proof |

Do not open a generic security-only feature slice.

## Performance / backup / restore / accessibility

| ID | STATUS | OWNING_CLUSTER | CAN_START_NOW | FINAL_ACCEPTANCE_ONLY |
|---|---|---|---|---|
| P4-FR-081 / AC-041 / ADV-016 | NOT_IMPLEMENTED | FINAL_ACCEPTANCE | NO | YES |
| P4-FR-080 / AC-040 / ADV-030 | NOT_IMPLEMENTED | FINAL_ACCEPTANCE | NO | YES |
| P4-FR-082 / AC-045,050 | NOT_IMPLEMENTED | FRONTEND_E2E | NO* | NO (feature) then final E2E proof |
| Restart recovery FR-078/079 | IMPLEMENTED on closed surfaces | FINAL_ACCEPTANCE re-proof | — | YES |

## Dependency frontier (eligible now)

| CLUSTER | FR_IDS | AC_IDS | ADV_IDS | FR/AC/ADV | DEPENDENCIES | WHY_UNBLOCKED | COHERENCE | COMPLEXITY | UNCERTAINTY_REDUCTION | UNLOCKS | PHASE_5_LEAKAGE_RISK |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PLAN_EQUIPMENT_CLOSURE | 011(part) | 028,049,064 | 029,039 | 1/3/2 | ENTRY | Plan snapshot exists; calc gap no longer ahead of it | HIGH | SMALL | MEDIUM | Equipment immutability AC-049/064 | NONE |
| DEVIATIONS | 058 | — | — | 1/0/0 | measurements | Measurement foundation exists | HIGH | SMALL | MEDIUM | §22 deviation identity | NONE |
| WAIVERS_READINESS | 059,060 | 051,054,059 | 008,035 | 2/3/2 | conditioning + OG UNKNOWN | Conditioning + UNKNOWN OG closed | HIGH | MEDIUM | HIGH | Unblocks PACKAGING_READINESS_CLOSE | NONE |
| JOURNAL_MEDIA_EXPORT | 062–065 | 046,052 | 013,019 | 4/2/2 | journal writers | Append-only journal exists | MEDIUM | MEDIUM | MEDIUM | Export/media | NONE |
| ACTIONS_ADDITIONS | 052–057,… | 031–033,… | 031,042 | large | PLAN+ACTIVE | Plan+ACTIVE exist | MEDIUM | LARGE | HIGH | Proves FR-070; terminal addition | LOW (must not invent packaging ops) |

## Selected Slice 9

| Field | Value |
|---|---|
| RECOMMENDED_NEXT_SLICE | `PLAN_EQUIPMENT_CLOSURE` |
| NEXT_SLICE_FR_IDS | P4-FR-011 |
| NEXT_SLICE_AC_IDS | P4-AC-028, P4-AC-049, P4-AC-064 |
| NEXT_SLICE_ADV_IDS | P4-ADV-029, P4-ADV-039 |
| NEXT_SLICE_DEPENDENCIES | SATISFIED |
| NEXT_SLICE_SCOPE_COHERENT | YES |
| NEXT_SLICE_PHASE_5_LEAKAGE | NO |
| WHY_THIS_SLICE_NEXT | Smallest coherent unblocked frontier after CALC: closes known FR-011 PARTIAL (plan hash / schedule keys / equipment snapshot immutability) with a tight AC/ADV set, without mixing waivers, packaging, additions, or UI. Preserves established post–Slice-7 path ordering (equipment/deviations smalls before WAIVERS unlock of packaging). |
| NEXT_SLICE_COULD_COMPLETE_PHASE_4_FEATURE_IMPLEMENTATION | NO |

Parallel eligible note: `DEVIATIONS` remains a valid alternate small frontier (1 FR) but does not supersede PLAN_EQUIPMENT in the established uncertainty/path ranking.

## Remaining path to feature-complete

```
SLICE_9 = PLAN_EQUIPMENT_CLOSURE
THEN -> DEVIATIONS (parallel-eligible small; may precede or follow Slice 9)
THEN -> WAIVERS_READINESS
THEN -> PACKAGING_READINESS_CLOSE
THEN -> ACTIONS_ADDITIONS (may proceed earlier if capacity; proves FR-070)
THEN -> JOURNAL_MEDIA_EXPORT
THEN -> FRONTEND_E2E
THEN -> FINAL_ACCEPTANCE
```

`REMAINING_IMPLEMENTATION_CLUSTER_COUNT=8`

## Final-acceptance-only work

`FINAL_ACCEPTANCE_ONLY_WORK_IDENTIFIED=YES`

- Complete 89/68/42 traceability reconciliation on final candidate
- PostgreSQL acceptance (§32 full matrix)
- Migration round-trip (FR-087 / AC-044) including `0010`+
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
- Slice 9 not started.
