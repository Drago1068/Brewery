# Phase 4 Implementation Candidate

## 1. Candidate identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input / assembly baseline HEAD | `58711550a8bccf89f2dc5af4cf36b763d141fc76` |
| Final delta review | `docs/evidence/PHASE_4_POST_SLICE_15_FINAL_DELTA_REVIEW.md` |
| Candidate artifact | `docs/evidence/PHASE_4_IMPLEMENTATION_CANDIDATE.md` |
| Candidate commit | *(assigned on commit of this artifact)* |
| Candidate tag | **NOT_CREATED** |
| Assembly type | Architecture-controlled freeze for independent Codex review — **no** new product behavior |

## 2. Specification identity

| Field | Value |
|---|---|
| Spec baseline tag | `v0.4.0-phase4-spec` |
| Spec commit | `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | **YES** |
| SPECIFICATION_CHANGED | **NO** |
| Ancestry from `v0.4.0-phase4-spec` | **PASS** |
| CANDIDATE_BASELINE | **PASS** |

## 3. Feature-completion declaration

| Gate | Value |
|---|---|
| PHASE_4_FEATURE_IMPLEMENTATION_COMPLETE | **YES** |
| FEATURE_IMPLEMENTATION_REQUIRED_FR_COUNT | **0** |
| FEATURE_IMPLEMENTATION_REQUIRED_AC_COUNT | **0** |
| FEATURE_IMPLEMENTATION_REQUIRED_ADV_COUNT | **0** |
| FEATURE_IMPLEMENTATION_REQUIRED_TOTAL | **0** |
| REMAINING_BACKEND_CLUSTER_COUNT | **0** |
| REMAINING_FRONTEND_OR_INTEGRATION_CLUSTER_COUNT | **0** |
| REMAINING_CROSS_CUTTING_CLUSTER_COUNT | **0** |
| REMAINING_IMPLEMENTATION_CLUSTER_COUNT | **0** |
| IMPLEMENTATION_CANDIDATE_PREREQUISITES_COMPLETE | **YES** |
| IMPLEMENTATION_CANDIDATE_BLOCKERS | **NONE** |
| JOURNAL_MEDIA_EXPORT_CLUSTER | **CLOSED** |
| PHASE_4_CONVERGENCE_STATE | FEATURE_COMPLETE_PENDING_CANDIDATE |

## 4. Requirement totals

| Class | Count |
|---|---|
| FR IMPLEMENTED | **78/89** |
| FR FINAL_ACCEPTANCE_ONLY | **11** |
| FR PARTIAL | **0** |
| FR NOT_IMPLEMENTED | **0** |
| AC VERIFIED | **63/68** |
| AC FINAL_ACCEPTANCE_ONLY | **5** |
| AC PARTIAL | **0** |
| AC NOT_VERIFIED | **0** |
| ADV VERIFIED | **38/42** |
| ADV FINAL_ACCEPTANCE_ONLY | **4** |
| ADV PARTIAL | **0** |
| ADV NOT_VERIFIED | **0** |

Arithmetic: 78+11=89; 63+5=68; 38+4=42.

## 5. Final-acceptance-only requirements

`FINAL_ACCEPTANCE_BUCKET_CONTAINS_MISSING_FEATURE_CODE=NO`

| ID | WHY_FINAL_ACCEPTANCE_ONLY | REQUIRED_ACCEPTANCE_PROOF | DEPENDENCIES | CURRENT_IMPLEMENTATION_FOUNDATION | MISSING_FEATURE_CODE |
|---|---|---|---|---|---|
| P4-AC-038 | evidence AC for §33 nested IDOR matrix | security test matrix | FR-075 | ownership tests per surface | NO |
| P4-AC-039 | CSRF evidence AC | CSRF suite | FR-076 | mutating route CSRF | NO |
| P4-AC-040 | backup/restore evidence AC | §35 vectors | FR-080 | durable state | NO |
| P4-AC-041 | performance evidence AC | §37 harness | FR-081 | spec thresholds | NO |
| P4-AC-044 | migration campaign AC | upgrade/downgrade campaign | FR-087 | 0015 chain | NO |
| P4-ADV-003 | cross-owner IDOR adversarial matrix | ADV suite with FR-075 | ownership gates | security tests | NO |
| P4-ADV-014 | CSRF adversarial | CSRF ADV suite | FR-076 | middleware | NO |
| P4-ADV-016 | performance adversarial | §37 ADV | FR-081 | harness | NO |
| P4-ADV-030 | backup/restore adversarial | §35 ADV | FR-080 | durable state | NO |
| P4-FR-071 | operation_id required on mutations; foundations exist across families | consolidated missing-key + fingerprint campaign | all mutation surfaces | operations.py + per-family tests | NO |
| P4-FR-072 | phase4-operation-v1 implemented; residual = global fingerprint/tombstone campaign | same-key conflict + loss-retry matrix across families | all mutation surfaces | operations.py | NO |
| P4-FR-075 | owner-only 404 gates via get_fermentation_session; residual = §33 nested IDOR matrix | full nested IDOR matrix AC-038/ADV-003 | complete surface inventory | session-scoped getters | NO |
| P4-FR-076 | CSRF middleware present on mutating routes | CSRF campaign AC-039/ADV-014 | all mutating routes | framework CSRF + route suite | NO |
| P4-FR-077 | closed Pydantic schemas; UNKNOWN_FIELD paths exist | consolidated schema campaign | command schemas | route request models | NO |
| P4-FR-080 | backup/restore is acceptance campaign over existing durable state | §35 fixture vectors incl. media/ops | features closed | PostgreSQL + MEDIA_ROOT | NO |
| P4-FR-081 | performance harness is acceptance execution | §37 harness thresholds | features closed | spec §37 | NO |
| P4-FR-084 | Phase 3 preserve; residual consolidated regression | named Phase 3 suites on candidate | features closed | Phase 3 tests | NO |
| P4-FR-085 | Phase 1A/2 preserve; residual consolidated regression | named 1A/2 suites on candidate | features closed | predecessor tests | NO |
| P4-FR-086 | leakage absence enforced in domain; residual executable scan | §51 leakage matrix + AC-002/003 | features closed | packaging absence tests | NO |
| P4-FR-087 | additive chain 0004→0015 exists; residual final migration campaign | head-to-head + round-trip campaign | 0015 head | test_phase4_migration.py | NO |

## 6. Implementation slice inventory

| SLICE_ID | NAME | INPUT_COMMIT | OUTPUT_COMMIT | FR_IDS | AC_IDS | ADV_IDS | EVIDENCE_ARTIFACT | REGRESSION_STATUS | PHASE_5_LEAKAGE_STATUS |
|---|---|---|---|---|---|---|---|---|---|
| S1 | ENTRY_FOUNDATION | v0.4.0-phase4-spec | 17bf72aab801169507657ae4e0b54d637a5a830d | 001–014 (core) | 004–009 | 022 | commit + test_phase4_entry.py | PASS | NO |
| S2 | MEASUREMENTS_DERIVED_GRAVITY | 17bf72a | b53119e / e2e9049 | 025–038,083 | 018–020 | 004–006,025–026 | PHASE_4_SLICE_2_MEASUREMENTS_EVIDENCE.md | PASS | NO |
| S3 | LIFECYCLE_COMPLETION | b53119e | 55bf16f | 015–017,021,024,039–042 | 012+ | 012,024,033+ | PHASE_4_SLICE_3_LIFECYCLE_EVIDENCE.md | PASS | NO |
| S4 | TIMERS_REMINDERS | 55bf16f | fdf2091 | 018,048–051 | 029–030 | 009–011 | PHASE_4_SLICE_4_TIMERS_REMINDERS_EVIDENCE.md | PASS | NO |
| S5 | CONDITIONING | fdf2091 | b464f97 / f878609 | 019–020,023,045–047 | 014–017+ | — | PHASE_4_SLICE_5_CONDITIONING_EVIDENCE.md | PASS | NO |
| S6 | YEAST_PROVENANCE | be56071 | e9b2403 | 066–069 | 034–035 | 018,027 | PHASE_4_SLICE_6_YEAST_PROVENANCE_PITCH_HISTORY_EVIDENCE.md | PASS | NO |
| S7 | OG_UNKNOWN_RECONCILE | 34cfcf0 | c134c4b | 004–005 | 010 | 020–021 | PHASE_4_SLICE_7_ENTRY_OG_UNKNOWN_RECONCILE_EVIDENCE.md | PASS | NO |
| S8 | CALC_READ_MODEL | 14b006b | 0deceb0 | 036 | 021 | — | PHASE_4_SLICE_8_CALC_READ_MODEL_CLOSURE_EVIDENCE.md | PASS | NO |
| S9 | PLAN_EQUIPMENT | 7f3333f | c8ec279 | 011 | 027–028,049 | 029,039 | PHASE_4_SLICE_9_PLAN_EQUIPMENT_CLOSURE_EVIDENCE.md | PASS | NO |
| S10 | DEVIATIONS | 3f9eb74 | 157edc5 | 058 | — | — | PHASE_4_SLICE_10_DEVIATIONS_EVIDENCE.md | PASS | NO |
| S11 | WAIVERS_READINESS | 5a643bf | 5955fc4 | 059–060 | 051,054,059 | 008,035 | PHASE_4_SLICE_11_WAIVERS_READINESS_EVIDENCE.md | PASS | NO |
| S12 | PACKAGING_READINESS_CLOSE | baac382 | 9e40a08 | 013,022,043–044,088–089 | 011,026,059–061+ | 017,035 | PHASE_4_SLICE_12_PACKAGING_READINESS_CLOSE_EVIDENCE.md | PASS | NO |
| S13 | FRONTEND_E2E | a6777d4 | cc8916c | 082 | 045,050 | — | PHASE_4_SLICE_13_FRONTEND_E2E_EVIDENCE.md | PASS | NO |
| S14 | ACTIONS_ADDITIONS | 616631f | 5489f22 | 052–057,061,070 | 031–033,048,056,068 | 031,042 | PHASE_4_SLICE_14_ACTIONS_ADDITIONS_EVIDENCE.md | PASS | NO |
| S15 | JOURNAL_MEDIA_EXPORT | 11b9712 | aaae10d | 062–065 | 046,052 | 013,019 | PHASE_4_SLICE_15_JOURNAL_MEDIA_EXPORT_EVIDENCE.md | PASS | NO |
| N1 | POST_SLICE_5_DELTA | b464f97 | be56071 | planning | — | — | PHASE_4_POST_SLICE_5_REQUIREMENTS_DELTA.md | N/A | NO |
| N14c | POST_SLICE_14_CORRECTION | 6725afb | 11b9712 | FR-075/AC-038 FAO | — | — | PHASE_4_POST_SLICE_14_DELTA_REVIEW.md (correction) | N/A | NO |
| N15 | POST_SLICE_15_FINAL_DELTA | aaae10d | 5871155 | feature-complete | — | — | PHASE_4_POST_SLICE_15_FINAL_DELTA_REVIEW.md | N/A | NO |

`SLICE_INVENTORY=PASS`

## 7. Commit provenance

Linear ancestry from `v0.4.0-phase4-spec` (`bc063d1…`) through Slice 1–15 feature commits and delta/normalization docs to `5871155`. Spec file hash unchanged. Phase 3 migrations `0001`–`0003` not rewritten. Expected implementation and evidence commits reachable on branch.

`CANDIDATE_COMMIT_PROVENANCE=PASS`

## 8. Migration manifest

| REVISION | DOWN_REVISION | PURPOSE | INTRODUCED_BY_SLICE | FILE | CHECKSUM_SHA256 |
|---|---|---|---|---|---|
| `0001_phase1a` | None | Phase 1A foundation | PREDECESSOR | `database/migrations/versions/0001_phase1a.py` | `3bcffcdf9f3d668dc491eaf07e3291de2f0c7c425941a0856dceccb378985ae8` |
| `0002_phase2_brewing_core` | "0001_phase1a" | Phase 2 core | PREDECESSOR | `database/migrations/versions/0002_phase2_brewing_core.py` | `57a189fac554fe42aca9eae3772ae5d239cc32ece6be8cf29a8a99c74af0e826` |
| `0003_phase3_brew_day_os` | "0002_phase2_brewing_core" | Phase 3 brew-day | PREDECESSOR | `database/migrations/versions/0003_phase3_brew_day_os.py` | `8f2ec77cd68f9eab097919232df9e320b50dbeb987e47c7d6027958389dc97ff` |
| `0004_phase4_fermentation_conditioning_yeast` | "0003_phase3_brew_day_os" | Phase 4 entry/session foundation | S1 | `database/migrations/versions/0004_phase4_fermentation_conditioning_yeast.py` | `98f08af926ae37c4789a8f5472441bf265c1deb34a247208abcbfe7e26403cb7` |
| `0005_phase4_measurements_derived_gravity` | "0004_phase4_fermentation_conditioning_yeast" | Measurements / derived gravity | S2 | `database/migrations/versions/0005_phase4_measurements_derived_gravity.py` | `9d82eb9670bfc2b2e252e14493006fa38d24d2b0f46bc0f2c9af6672c1ea6233` |
| `0006_phase4_lifecycle_completion` | "0005_phase4_measurements_derived_gravity" | Lifecycle / completion | S3 | `database/migrations/versions/0006_phase4_lifecycle_completion.py` | `b6e70e8bb1b4e96c6e5503d51bdcd5d63d914d869181711f90a54e8fb8606abb` |
| `0007_phase4_timers_reminders` | "0006_phase4_lifecycle_completion" | Timers / reminders | S4 | `database/migrations/versions/0007_phase4_timers_reminders.py` | `d07e1635885574d5915adea0a27dd306ae18a2c0e17827a47f97ed358d6d0f1e` |
| `0008_phase4_yeast_provenance` | "0007_phase4_timers_reminders" | Yeast provenance | S6 | `database/migrations/versions/0008_phase4_yeast_provenance.py` | `acdc5ef6cc47d1764436067e109ce54d14262874cda4755afec67db6be554107` |
| `0009_phase4_og_unknown_reconcile` | "0008_phase4_yeast_provenance" | OG UNKNOWN / reconcile | S7 | `database/migrations/versions/0009_phase4_og_unknown_reconcile.py` | `bad6423bb28281fd04899b7a5578f0db25a0f5464b79adc2ccc91c52b710f09e` |
| `0010_phase4_calc_read_model_abv` | "0009_phase4_og_unknown_reconcile" | Calc read model / ABV | S8 | `database/migrations/versions/0010_phase4_calc_read_model_abv.py` | `1593016b790011f9da1c9dfbd66ec1cfb36a8eb4e6890bdc4ee2990d056b0c52` |
| `0011_phase4_plan_equipment` | "0010_phase4_calc_read_model_abv" | Plan / equipment | S9 | `database/migrations/versions/0011_phase4_plan_equipment.py` | `a82ec637cb1ef2a1445b67522d1c7e2500db9fd20e8e3a25d982e5c1245e5466` |
| `0012_phase4_deviations` | "0011_phase4_plan_equipment" | Deviations | S10 | `database/migrations/versions/0012_phase4_deviations.py` | `1db980c66c3c3738aeae2e63bf48d44c0e6e3ff7c41099a39dd7dde4b81f64c0` |
| `0013_phase4_waivers` | "0012_phase4_deviations" | Waivers / readiness | S11 | `database/migrations/versions/0013_phase4_waivers.py` | `c7784a5f5454ac0bd21f58d19abffc11b87829881ece6e6c9c18f1282636ae3d` |
| `0014_phase4_actions_additions` | "0013_phase4_waivers" | Actions / additions | S14 | `database/migrations/versions/0014_phase4_actions_additions.py` | `7e9711da7c63ad626f4a0297063d24f2b37544b14c5eb1a879057134d85c654c` |
| `0015_phase4_journal_media_export` | "0014_phase4_actions_additions" | Notes / media / journal export support | S15 | `database/migrations/versions/0015_phase4_journal_media_export.py` | `c8109f7959b86128c300c0506e608ebe91fc75e4e4d13df5da3d27c5bb4793db` |

| Gate | Value |
|---|---|
| PHASE_3_MIGRATIONS_UNCHANGED | **YES** |
| PHASE_3_MIGRATION_ANCESTRY | **PASS** |
| PHASE_4_MIGRATION_CHAIN | **PASS** (`0004`→`0015`) |
| MIGRATION_MANIFEST | **PASS** |

## 9. PostgreSQL integrity manifest

| Concern | Evidence loci |
|---|---|
| Foreign keys / uniqueness | migrations 0004–0015; models in `domain/fermentation/models.py` |
| Ownership isolation | `get_fermentation_session`; security tests per slice |
| Occurrence identity / correction chains | measurement/addition/handoff correction tables + leaf uniqueness |
| Idempotency keys | `phase4-operation-v1` / operations persistence |
| Concurrency / revision | session `revision` OCC; PG interleave tests (e.g. AC-068) |
| Journal / media / export | `0015` + journal merge + MEDIA_ROOT |
| Yeast provenance | `0008` + yeast tests |
| Readiness / handoff | packaging readiness tables; Slice 11–12 |
| Actions / additions | `0014` + Slice 14 tests |

`POSTGRESQL_INTEGRITY_MANIFEST=PASS` — final PG acceptance pending formal campaign.

## 10. API manifest

Prefix: `/fermentation-sessions` (auth via `CurrentUser`). Ownership via session getters unless noted.

| METHOD | PATH | PURPOSE | AUTH | OWNERSHIP | IDEMPOTENCY | OCC | PRIMARY_IDS | TEST_LOCATION |
|---|---|---|---|---|---|---|---|---|
| GET | / | List owned sessions | Y | Y | N | N | FR-007,075 | test_phase4_entry / frontend_list |
| POST | / | StartFermentationSession | Y | Y | Y | brew rev | FR-001–014 | test_phase4_entry |
| GET | /pitch-history | Pitch history | Y | Y | N | N | FR-068 | test_phase4_yeast |
| POST | /{id}/yeast-reference | Enrich yeast ref | Y | Y | Y | Y | FR-066–067 | test_phase4_yeast |
| POST | /{id}/og-consumption | Reconcile OG | Y | Y | Y | Y | FR-005 | test_phase4_og_reconcile |
| GET | /{id} | Session detail read model | Y | Y | N | N | FR-075 | multiple |
| POST | /{id}/measurements | Record measurement | Y | Y | Y | Y | FR-025–032 | test_phase4_measurements_* |
| POST | /{id}/measurements/{mid}/corrections | Correct measurement | Y | Y | Y | Y | FR-031 | test_phase4_measurements_* |
| POST | /{id}/actions | Record action | Y | Y | Y | Y | FR-056 | test_phase4_actions_additions |
| POST | /{id}/planned-additions/execute | Execute planned addition | Y | Y | Y | Y | FR-052–053 | test_phase4_actions_additions |
| POST | /{id}/unplanned-additions | Record unplanned addition | Y | Y | Y | Y | FR-054,061 | test_phase4_actions_additions |
| POST | /{id}/additions/{aid}/corrections | Correct addition | Y | Y | Y | Y | FR-055 | test_phase4_actions_additions |
| POST | /{id}/commands/pause|resume|abort|close | Lifecycle commands | Y | Y | Y | Y | FR-015–022 | test_phase4_lifecycle* |
| POST | /{id}/commands/complete-fermentation | Complete fermentation | Y | Y | Y | Y | FR-039–042 | test_phase4_lifecycle* |
| POST | /{id}/commands/start|skip|complete-conditioning | Conditioning cmds | Y | Y | Y | Y | FR-019–020,023,045–047 | test_phase4_conditioning* |
| POST | /{id}/waivers | Record waiver | Y | Y | Y | Y | FR-059–060 | test_phase4_waivers_readiness |
| POST | /{id}/commands/assess-packaging-readiness | Assess readiness | Y | Y | Y | Y | FR-013,089 | test_phase4_packaging_close |
| POST | /{id}/commands/record-packaging-readiness-handoff | Record handoff | Y | Y | Y | Y | FR-044 | test_phase4_packaging_close |
| POST | /{id}/… timers/reminders … | Timer/reminder ops | Y | Y | Y | Y | FR-048–051 | test_phase4_timers_* |
| POST | /{id}/notes | Add note | Y | Y | Y | opt | FR-064 | test_phase4_journal_media_export |
| POST | /{id}/attachments | Upload media | Y | Y | Y | opt | FR-064 | test_phase4_journal_media_export |
| GET | /{id}/attachments[/{aid}] | List/get attachment | Y | Y | N | N | FR-064 | test_phase4_journal_media_export |
| POST | /{id}/attachments/{aid}/remove | Soft-remove media | Y | Y | Y | opt | FR-064 | test_phase4_journal_media_export |
| GET | /{id}/journal | Merged journal | Y | Y | N | N | FR-062–063 | test_phase4_journal_media_export |
| GET | /{id}/export | JSON/HTML export | Y | Y | N | N | FR-065 | test_phase4_journal_media_export |

`API_MANIFEST=PASS`

## 11. Domain authority manifest

| CONCEPT | AUTHORITATIVE_DOMAIN | PERSISTENCE_AUTHORITY | READ_MODEL | CORRECTION_MODEL | AI_AUTHORITY_ALLOWED |
|---|---|---|---|---|---|
| Fermentation lifecycle | phase4 lifecycle/commands | PostgreSQL session/stage | session detail | invalidation/reactivation §9.8 | NO |
| Conditioning lifecycle | phase4 conditioning | PostgreSQL | session detail | assessment invalidation | NO |
| Measurements | phase4 measurements | PostgreSQL | detail + derived | append-only corrections | NO |
| Derived gravity / calc | calculations + derived_gravity | PostgreSQL snapshots | read_models | recompute from leaves | NO |
| Deviations | phase4 deviations | PostgreSQL | detail | supersession | NO |
| Waivers | phase4 waivers | PostgreSQL | detail | catalog-bounded | NO |
| Readiness / handoff | phase4 packaging readiness | PostgreSQL | detail + export histories | versioned invalidate | NO |
| Equipment references | phase4 plan snapshot | PostgreSQL plan | detail | immutable snapshot | NO |
| Yeast provenance/history | phase4 yeast | PostgreSQL | pitch-history | immutable snapshots | NO |
| Actions / additions | phase4 actions/additions | PostgreSQL | detail + journal | addition corrections | NO |
| Journal | phase4 journal merge | PostgreSQL Phase3+4 events | journal API | append-only | NO |
| Media / evidence | phase4 media + MEDIA_ROOT | PostgreSQL + files | attachments API | soft-remove preserves history | NO |
| Export | phase4 export | regenerated from DB | export API | N/A (read) | NO |
| Phase 4 handoff | readiness handoff facts only | PostgreSQL | export/detail | invalidate/version | NO |

`DOMAIN_AUTHORITY_MANIFEST=PASS`

## 12. Security manifest

| Concern | Evidence |
|---|---|
| Authentication | `CurrentUser` dependency on all routes |
| Authorization / ownership | session-scoped getters → cross-owner 404 |
| Forged IDs / cross-session | measurement/security + per-slice IDOR tests |
| Mass assignment | closed Pydantic schemas; UNKNOWN_FIELD |
| Actor attribution | audit + journal actor fields |
| Correction authorization | owner + stage rules |
| Export / media authorization | Slice 15 ownership + MIME gates |

`SECURITY_MANIFEST=PASS`
`FINAL_SECURITY_ACCEPTANCE_PENDING=YES`

## 13. Idempotency manifest

| OPERATION | MECHANISM | PERSISTENCE | SAME_KEY_SAME | CONFLICT | LOSS_RETRY | EVIDENCE |
|---|---|---|---|---|---|---|
| Start / lifecycle / measurements / yeast / readiness / actions / additions / notes / media | `phase4-operation-v1` + `operation_id` | operations table | per-family tests | fingerprint conflict tests | replay-before-reread | slice suites + FAO FR-071/072 campaign |

`IDEMPOTENCY_MANIFEST=PASS`
`FINAL_IDEMPOTENCY_ACCEPTANCE_PENDING=YES`

## 14. Concurrency manifest

| RACE | CONTROL | PG MECHANISM | TEST | EVIDENCE |
|---|---|---|---|---|
| Lifecycle vs evidence | session revision OCC | row lock + revision | lifecycle/conditioning PG | slice 3/5/12/14 |
| Close vs late addition | OCC STALE loser | session lock | `test_ac068_close_vs_late_addition_interleave` | Slice 14 |
| Yeast cycle | transactional locking | PG | yeast cycle race | Slice 6 |
| Journal/media/export | read-only export; OCC on mutations | session revision where supplied | Slice 15 | S15 evidence |

`CONCURRENCY_MANIFEST=PASS`
`FINAL_CONCURRENCY_ACCEPTANCE_PENDING=YES`

## 15. Recovery manifest

| Concern | Evidence |
|---|---|
| API restart / Redis non-authority | timers recover from PostgreSQL (FR-049/078/079) |
| Lost response / retry | operation lookup-before-reread |
| Deterministic reconstruction | journal merge + export rebuild from DB |
| Durable timers/reminders | Slice 4 recovery tests |
| Note/media reread | `test_recovery_reread_note_media` |

`RECOVERY_MANIFEST=PASS`
`FINAL_RECOVERY_ACCEPTANCE_PENDING=YES`

## 16. Backup / restore manifest

| Field | Value |
|---|---|
| FEATURE_BEHAVIOR_COMPLETE | YES (durable PostgreSQL + MEDIA_ROOT + operations) |
| FINAL_ACCEPTANCE_EXECUTION_PENDING | YES (§35 vectors FR-080/AC-040/ADV-030) |
| NAS production access | **NO** |

`BACKUP_RESTORE_MANIFEST=PASS`
`FINAL_BACKUP_RESTORE_ACCEPTANCE_PENDING=YES`

## 17. Frontend / accessibility / Playwright manifests

| Gate | Value |
|---|---|
| PHASE_4_FEATURE_FRONTEND_REMAINING | NO |
| FEATURE_ACCESSIBILITY_REMAINING | NO |
| FEATURE_PLAYWRIGHT_REMAINING | NO |
| Surfaces | `/ferment/[id]` worksheet; list integration |
| API→UI | `apps/web/lib/fermentation.ts` |
| A11y | Slice 13 `assertFermentA11y`; AC-045 |
| Playwright | `tests/e2e/phase4.spec.ts` |
| Vitest | `apps/web/lib/fermentation.test.ts` |

`FRONTEND_MANIFEST=PASS` / `ACCESSIBILITY_MANIFEST=PASS` / `PLAYWRIGHT_MANIFEST=PASS`
Final consolidated a11y/Playwright acceptance pending.

## 18. Performance manifest

| Item | Value |
|---|---|
| Requirements | P4-FR-081 / P4-AC-041 / P4-ADV-016 (§37) |
| Thresholds | as defined in accepted specification only |
| Feature remaining | NO |
| Final acceptance | PENDING |

`PERFORMANCE_MANIFEST=PASS`
`FINAL_PERFORMANCE_ACCEPTANCE_PENDING=YES`

## 19. AI boundary manifest

| Concern | Status |
|---|---|
| Deterministic domain authority | YES — application + PostgreSQL |
| Frontend non-authority | YES — UI calls APIs; no local authority |
| Redis non-authority | YES — FR-079 |
| LLM authoritative for Phase 4 facts | **NO** |
| AI_BOUNDARY | PARTIAL (feature remaining NO; final scan YES) |

`AI_BOUNDARY_MANIFEST=PASS`
`FINAL_AI_BOUNDARY_ACCEPTANCE_PENDING=YES`

## 20. Phase 4 / Phase 5 boundary manifest

Phase 4 stops at packaging-readiness assessment/handoff facts. No packaging session execution, finished-product inventory, package disposition, consumption, or release lifecycle. Actions/additions force `inventory_effect=false`. Export includes handoff histories only.

`PHASE_5_PLUS_OPERATIONAL_LEAKAGE=NO`
`PHASE_4_PHASE_5_BOUNDARY_MANIFEST=PASS`

## 21. Regression manifest

| TEST_GROUP | COMMAND (representative) | LAST_RESULT | EVIDENCE_LOCATION |
|---|---|---|---|
| PHASE_1A / 2 / 3 | pytest predecessor suites in slice regression logs | PASS (last S15 reg) | `.pytest-p4s15-reg.txt` (untracked log) + slice evidence |
| PHASE_4 S2–S15 | pytest `test_phase4_*` | PASS | per-slice evidence + `.pytest-p4s15*.txt` |
| PostgreSQL | pytest PG markers | PASS | `.pytest-p4s15-pg.txt` |
| Migration | `test_phase4_migration` | PASS | S15 evidence |
| Playwright Phase 4 | `tests/e2e/phase4.spec.ts` | PASS (S13) | PHASE_4_SLICE_13_* |

Full final-acceptance suite not re-executed in this assembly gate.

`REGRESSION_MANIFEST=PASS`

## 22. Requirement ledger + traceability matrix (199 rows)

### 22.1 Functional requirements (89)

| ID | TYPE | SPEC_SECTION | FINAL_STATUS | OWNING_SLICE_OR_GATE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LOCATION | FINAL_ACCEPTANCE_REQUIRED |
|---|---|---|---|---|---|---|---|---|
| P4-FR-001 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-002 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-003 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-004 | FR | §44 | IMPLEMENTED | SLICE_7_OG_RECONCILE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_7_*_EVIDENCE.md | NO |
| P4-FR-005 | FR | §44 | IMPLEMENTED | SLICE_7_OG_RECONCILE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_7_*_EVIDENCE.md | NO |
| P4-FR-006 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-007 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-008 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-009 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-010 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-011 | FR | §44 | IMPLEMENTED | SLICE_9_PLAN_EQUIPMENT | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_9_*_EVIDENCE.md | NO |
| P4-FR-012 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-013 | FR | §44 | IMPLEMENTED | SLICE_12_PACKAGING_CLOSE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_12_*_EVIDENCE.md | NO |
| P4-FR-014 | FR | §44 | IMPLEMENTED | SLICE_1_ENTRY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_1_*_EVIDENCE.md | NO |
| P4-FR-015 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-016 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-017 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-018 | FR | §44 | IMPLEMENTED | SLICE_4_TIMERS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_4_*_EVIDENCE.md | NO |
| P4-FR-019 | FR | §44 | IMPLEMENTED | SLICE_5_CONDITIONING | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_5_*_EVIDENCE.md | NO |
| P4-FR-020 | FR | §44 | IMPLEMENTED | SLICE_5_CONDITIONING | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_5_*_EVIDENCE.md | NO |
| P4-FR-021 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-022 | FR | §44 | IMPLEMENTED | SLICE_12_PACKAGING_CLOSE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_12_*_EVIDENCE.md | NO |
| P4-FR-023 | FR | §44 | IMPLEMENTED | SLICE_5_CONDITIONING | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_5_*_EVIDENCE.md | NO |
| P4-FR-024 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-025 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-026 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-027 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-028 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-029 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-030 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-031 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-032 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-033 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-034 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-035 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-036 | FR | §44 | IMPLEMENTED | SLICE_8_CALC_READ_MODEL | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_8_*_EVIDENCE.md | NO |
| P4-FR-037 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-038 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-039 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-040 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-041 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-042 | FR | §44 | IMPLEMENTED | SLICE_3_LIFECYCLE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_3_*_EVIDENCE.md | NO |
| P4-FR-043 | FR | §44 | IMPLEMENTED | SLICE_12_PACKAGING_CLOSE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_12_*_EVIDENCE.md | NO |
| P4-FR-044 | FR | §44 | IMPLEMENTED | SLICE_12_PACKAGING_CLOSE | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_12_*_EVIDENCE.md | NO |
| P4-FR-045 | FR | §44 | IMPLEMENTED | SLICE_5_CONDITIONING | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_5_*_EVIDENCE.md | NO |
| P4-FR-046 | FR | §44 | IMPLEMENTED | SLICE_5_CONDITIONING | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_5_*_EVIDENCE.md | NO |
| P4-FR-047 | FR | §44 | IMPLEMENTED | SLICE_5_CONDITIONING | application/phase4/lifecycle.py, commands.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_5_*_EVIDENCE.md | NO |
| P4-FR-048 | FR | §44 | IMPLEMENTED | SLICE_4_TIMERS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_4_*_EVIDENCE.md | NO |
| P4-FR-049 | FR | §44 | IMPLEMENTED | SLICE_4_TIMERS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_4_*_EVIDENCE.md | NO |
| P4-FR-050 | FR | §44 | IMPLEMENTED | SLICE_4_TIMERS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_4_*_EVIDENCE.md | NO |
| P4-FR-051 | FR | §44 | IMPLEMENTED | SLICE_4_TIMERS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_4_*_EVIDENCE.md | NO |
| P4-FR-052 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-053 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-054 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-055 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-056 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-057 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-058 | FR | §44 | IMPLEMENTED | SLICE_10_DEVIATIONS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_10_*_EVIDENCE.md | NO |
| P4-FR-059 | FR | §44 | IMPLEMENTED | SLICE_11_WAIVERS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_11_*_EVIDENCE.md | NO |
| P4-FR-060 | FR | §44 | IMPLEMENTED | SLICE_11_WAIVERS | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_11_*_EVIDENCE.md | NO |
| P4-FR-061 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-062 | FR | §44 | IMPLEMENTED | SLICE_15_JOURNAL_MEDIA_EXPORT | application/phase4/journal.py, notes.py, media.py, export.py | test_phase4_journal_media_export.py | docs/evidence/PHASE_4_SLICE_15_*_EVIDENCE.md | NO |
| P4-FR-063 | FR | §44 | IMPLEMENTED | SLICE_15_JOURNAL_MEDIA_EXPORT | application/phase4/journal.py, notes.py, media.py, export.py | test_phase4_journal_media_export.py | docs/evidence/PHASE_4_SLICE_15_*_EVIDENCE.md | NO |
| P4-FR-064 | FR | §44 | IMPLEMENTED | SLICE_15_JOURNAL_MEDIA_EXPORT | application/phase4/journal.py, notes.py, media.py, export.py | test_phase4_journal_media_export.py | docs/evidence/PHASE_4_SLICE_15_*_EVIDENCE.md | NO |
| P4-FR-065 | FR | §44 | IMPLEMENTED | SLICE_15_JOURNAL_MEDIA_EXPORT | application/phase4/journal.py, notes.py, media.py, export.py | test_phase4_journal_media_export.py | docs/evidence/PHASE_4_SLICE_15_*_EVIDENCE.md | NO |
| P4-FR-066 | FR | §44 | IMPLEMENTED | SLICE_6_YEAST | application/phase4/yeast.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_6_*_EVIDENCE.md | NO |
| P4-FR-067 | FR | §44 | IMPLEMENTED | SLICE_6_YEAST | application/phase4/yeast.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_6_*_EVIDENCE.md | NO |
| P4-FR-068 | FR | §44 | IMPLEMENTED | SLICE_6_YEAST | application/phase4/yeast.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_6_*_EVIDENCE.md | NO |
| P4-FR-069 | FR | §44 | IMPLEMENTED | SLICE_6_YEAST | application/phase4/yeast.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_6_*_EVIDENCE.md | NO |
| P4-FR-070 | FR | §44 | IMPLEMENTED | SLICE_14_ACTIONS_ADDITIONS | application/phase4/actions.py, additions.py, plan.py | test_phase4_actions_additions.py | docs/evidence/PHASE_4_SLICE_14_*_EVIDENCE.md | NO |
| P4-FR-071 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-072 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-073 | FR | §44 | IMPLEMENTED | CROSS_CUTTING_OCC | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | this candidate + prior slice/delta evidence | NO |
| P4-FR-074 | FR | §44 | IMPLEMENTED | CROSS_CUTTING_OCC | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | this candidate + prior slice/delta evidence | NO |
| P4-FR-075 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-076 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-077 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-078 | FR | §44 | IMPLEMENTED | CROSS_CUTTING_RECOVERY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | this candidate + prior slice/delta evidence | NO |
| P4-FR-079 | FR | §44 | IMPLEMENTED | CROSS_CUTTING_RECOVERY | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | this candidate + prior slice/delta evidence | NO |
| P4-FR-080 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-081 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-082 | FR | §44 | IMPLEMENTED | SLICE_13_FRONTEND_E2E | apps/web/app/ferment/[id]/page.tsx, lib/fermentation.ts | tests/e2e/phase4.spec.ts; apps/web/lib/fermentation.test.ts | docs/evidence/PHASE_4_SLICE_13_*_EVIDENCE.md | NO |
| P4-FR-083 | FR | §44 | IMPLEMENTED | SLICE_2_MEASUREMENTS | application/phase4/measurements.py, derived_gravity.py | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_2_*_EVIDENCE.md | NO |
| P4-FR-084 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-085 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-086 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-087 | FR | §44 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | foundations per FAO table; no new feature code | FINAL_ACCEPTANCE campaign | FINAL_ACCEPTANCE (pending formal campaign) | YES |
| P4-FR-088 | FR | §44 | IMPLEMENTED | SLICE_12_PACKAGING_CLOSE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_12_*_EVIDENCE.md | NO |
| P4-FR-089 | FR | §44 | IMPLEMENTED | SLICE_12_PACKAGING_CLOSE | apps/api/brewing_api/application/phase4/ | apps/api/tests/test_phase4_*.py | docs/evidence/PHASE_4_SLICE_12_*_EVIDENCE.md | NO |

### 22.2 Acceptance criteria (68)

| ID | TYPE | SPEC_SECTION | FINAL_STATUS | OWNING_SLICE_OR_GATE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LOCATION | FINAL_ACCEPTANCE_REQUIRED |
|---|---|---|---|---|---|---|---|---|
| P4-AC-001 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-002 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-003 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-004 | AC | §45 | VERIFIED | SLICE_1_ENTRY | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-005 | AC | §45 | VERIFIED | SLICE_1_ENTRY | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-006 | AC | §45 | VERIFIED | SLICE_1_ENTRY | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-007 | AC | §45 | VERIFIED | SLICE_1_ENTRY | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-008 | AC | §45 | VERIFIED | SLICE_1_ENTRY | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-009 | AC | §45 | VERIFIED | SLICE_1_ENTRY | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-010 | AC | §45 | VERIFIED | SLICE_7_OG_RECONCILE | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-011 | AC | §45 | VERIFIED | SLICE_12_PACKAGING_CLOSE | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-012 | AC | §45 | VERIFIED | SLICE_3_LIFECYCLE | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-013 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-014 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-015 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-016 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-017 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-018 | AC | §45 | VERIFIED | SLICE_2_MEASUREMENTS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-019 | AC | §45 | VERIFIED | SLICE_2_MEASUREMENTS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-020 | AC | §45 | VERIFIED | SLICE_2_MEASUREMENTS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-021 | AC | §45 | VERIFIED | SLICE_8_CALC_READ_MODEL | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-022 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-023 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-024 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-025 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-026 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-027 | AC | §45 | VERIFIED | SLICE_9_PLAN_EQUIPMENT | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-028 | AC | §45 | VERIFIED | SLICE_9_PLAN_EQUIPMENT | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-029 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-030 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-031 | AC | §45 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-032 | AC | §45 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-033 | AC | §45 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-034 | AC | §45 | VERIFIED | SLICE_6_YEAST | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-035 | AC | §45 | VERIFIED | SLICE_6_YEAST | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-036 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-037 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-038 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 AC tests / Playwright | FINAL_ACCEPTANCE | YES |
| P4-AC-039 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 AC tests / Playwright | FINAL_ACCEPTANCE | YES |
| P4-AC-040 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 AC tests / Playwright | FINAL_ACCEPTANCE | YES |
| P4-AC-041 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 AC tests / Playwright | FINAL_ACCEPTANCE | YES |
| P4-AC-042 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-043 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-044 | AC | §45 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 AC tests / Playwright | FINAL_ACCEPTANCE | YES |
| P4-AC-045 | AC | §45 | VERIFIED | SLICE_13_FRONTEND_E2E | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-046 | AC | §45 | VERIFIED | SLICE_15_JOURNAL_MEDIA_EXPORT | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-047 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-048 | AC | §45 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-049 | AC | §45 | VERIFIED | SLICE_9_PLAN_EQUIPMENT | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-050 | AC | §45 | VERIFIED | SLICE_13_FRONTEND_E2E | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-051 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-052 | AC | §45 | VERIFIED | SLICE_15_JOURNAL_MEDIA_EXPORT | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-053 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-054 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-055 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-056 | AC | §45 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-057 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-058 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-059 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-060 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-061 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-062 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-063 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-064 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-065 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-066 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-067 | AC | §45 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |
| P4-AC-068 | AC | §45 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 AC tests / Playwright | slice evidence + candidate | NO |

### 22.3 Adversarial requirements (42)

| ID | TYPE | SPEC_SECTION | FINAL_STATUS | OWNING_SLICE_OR_GATE | IMPLEMENTATION_LOCATION | TEST_LOCATION | EVIDENCE_LOCATION | FINAL_ACCEPTANCE_REQUIRED |
|---|---|---|---|---|---|---|---|---|
| P4-ADV-001 | ADV | §46 | VERIFIED | CROSS_CUTTING_IDEMPOTENCY | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-002 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-003 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 ADV tests | FINAL_ACCEPTANCE | YES |
| P4-ADV-004 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-005 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-006 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-007 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-008 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-009 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-010 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-011 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-012 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-013 | ADV | §46 | VERIFIED | SLICE_15_JOURNAL_MEDIA_EXPORT | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-014 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 ADV tests | FINAL_ACCEPTANCE | YES |
| P4-ADV-015 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-016 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 ADV tests | FINAL_ACCEPTANCE | YES |
| P4-ADV-017 | ADV | §46 | VERIFIED | SLICE_12_PACKAGING_CLOSE | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-018 | ADV | §46 | VERIFIED | SLICE_6_YEAST | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-019 | ADV | §46 | VERIFIED | SLICE_15_JOURNAL_MEDIA_EXPORT | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-020 | ADV | §46 | VERIFIED | SLICE_7_OG_RECONCILE | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-021 | ADV | §46 | VERIFIED | SLICE_7_OG_RECONCILE | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-022 | ADV | §46 | VERIFIED | SLICE_1_ENTRY | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-023 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-024 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-025 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-026 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-027 | ADV | §46 | VERIFIED | SLICE_6_YEAST | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-028 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-029 | ADV | §46 | VERIFIED | SLICE_9_PLAN_EQUIPMENT | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-030 | ADV | §46 | FINAL_ACCEPTANCE_ONLY | FINAL_ACCEPTANCE | governing FR implementation | phase4 ADV tests | FINAL_ACCEPTANCE | YES |
| P4-ADV-031 | ADV | §46 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-032 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-033 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-034 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-035 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-036 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-037 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-038 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-039 | ADV | §46 | VERIFIED | SLICE_9_PLAN_EQUIPMENT | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-040 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-041 | ADV | §46 | VERIFIED | SEE_MATRIX | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |
| P4-ADV-042 | ADV | §46 | VERIFIED | SLICE_14_ACTIONS_ADDITIONS | governing FR implementation | phase4 ADV tests | slice evidence + candidate | NO |

`TRACEABILITY_MATRIX_ROWS=199` (89+68+42)
`REQUIREMENT_LEDGER=PASS`
`TRACEABILITY_MATRIX=PASS`

## 23. Candidate self-check

| Check | Result |
|---|---|
| Missing requirement mappings | NONE (199 rows) |
| Orphaned migrations | NONE (linear 0001→0015) |
| Unreachable slice commits | NONE (reachable on branch) |
| Spec drift | NO |
| Migration rewrite of Phase 3 | NO |
| Feature gap in FAO bucket | NO |
| Phase 5 leakage | NO |
| Feature implementation required residual | 0 |

`CANDIDATE_SELF_CHECK=PASS`

## 24. Remaining final-acceptance-only work

Execute formal Phase 4 acceptance campaigns for the FAO set in §5, plus consolidated: full 89/68/42 matrix proof; AI non-authority scan; PostgreSQL/migration round-trip; security/ownership/idempotency/concurrency; recovery; backup/restore; performance; accessibility; Playwright; Phase 1A/2/3/4 regressions; Phase 5 leakage review; consolidated implementation evidence.

## 25. Independent reviewer mandate (Codex)

The independent reviewer must **independently verify, not trust** this candidate:

1. Candidate provenance from `v0.4.0-phase4-spec` to candidate SHA
2. Specification immutability (SHA-256)
3. Requirement accounting (78/11 FR; 63/5 AC; 38/4 ADV)
4. Feature completion (zero implementation-required residuals)
5. Final-acceptance-only classification integrity (`MISSING_FEATURE_CODE=NO`)
6. Migration integrity (Phase 3 unchanged; Phase 4 chain)
7. PostgreSQL integrity
8. Security / ownership / idempotency / concurrency
9. Recovery / backup-restore
10. Frontend / accessibility / Playwright
11. Performance
12. AI non-authority
13. Phase 4/5 boundary
14. Regressions
15. Traceability (199 rows)

Allowed outcomes: **PASS** | **FAIL** | **BLOCKED**.

No implementation modifications by the reviewer unless separately authorized.
Do not merge, tag, deploy, access NAS, or begin Phase 5 from this review alone.

## 26. Assembly stop

This artifact freezes the implementation candidate for handoff. Formal acceptance and Codex review are **not** performed by this assembly gate.

