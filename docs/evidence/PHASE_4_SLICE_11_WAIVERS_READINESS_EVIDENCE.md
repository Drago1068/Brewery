# Phase 4 Slice 11 Evidence — Waivers Readiness

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `5a643bf911a837b2dcf8d3da06011f41417241a3` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_10_DELTA_REVIEW.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `WAIVERS_READINESS` |
| Ancestry from `v0.4.0-phase4-spec` | PASS |

## Exact normative extraction

| ID | SPEC_SECTION | NORMATIVE_RULE | DEPENDENCIES | MISSING (pre-slice) | SURFACES |
|---|---|---|---|---|---|
| P4-FR-059 | §10.3 / §14.4 / §23 | Waivers with reason/actor/timestamp/effect for §10.3 waivable catalog only, including readiness-only `ORIGINAL_GRAVITY_KNOWN` | conditioning complete; plan templates | No `FermentationWaiver` | `waivers.py`, `0013`, session GET |
| P4-FR-060 | §10.3 / §14.5 | Reject non-waivable requests with `409 WAIVER_PROHIBITED` | FR-059 | No catalog enforcement | `waivers.py` |
| P4-AC-051 | §45 / §20 | Waiver vs later gravity: ACK≠SATISFIED; evidence supersedes waiver; one satisfaction source | FR-050,059 | No supersession | `test_ac051_*` |
| P4-AC-054 | §45 | Waive pitched_at / yeast note / ownership / idempotency → `409`, no row | FR-060 | Absent | `test_ac054_adv008_*` |
| P4-AC-059 | §45 / §14.4–14.5 | R1+R2, OG UNKNOWN: (a) assess not READY; (b) waive OG then handoff `READY_WITH_WAIVERS`; (c) override with R1 false → `409 OVERRIDE_PROHIBITED` | FR-059,042,089 | No readiness assess/handoff | `test_ac059_adv035_*` |
| P4-ADV-008 | §46 | Waive pitched_at or yeast note → `409 WAIVER_PROHIBITED` | FR-060 / AC-054 | Absent | same as AC-054 |
| P4-ADV-035 | §46 | UNKNOWN OG, R1/R2 true: READY without waiver denied; override with R1 false → `409` | FR-059 / AC-059 | Absent | same as AC-059 |

### Waiver ↔ readiness relationship

One decision boundary: §10.3 catalog waivers (checkpoint + readiness-only `ORIGINAL_GRAVITY_KNOWN`) feed §14.4 R3. Waivers never fabricate OG, never satisfy F1/F2/R1/R2, and never silently yield `READY`. Active OG waiver yields at most `READY_WITH_WAIVERS`.

## Waiver domain model

| Concern | Implementation |
|---|---|
| Aggregate | `FermentationWaiver` append-only |
| Catalog | `WAIVABLE_REQUIREMENT_CLASSES` + plan `waivable` flag |
| Never waivable | pitched_at, yeast note, ownership, idempotency, CSRF, `FERMENTATION_GRAVITY_STABILITY`, … |
| Active uniqueness | Partial unique `(session, requirement_template_id)` where `ACTIVE` |
| Chronology | `occurred_at` / `recorded_at` server dual-time |
| Effect | `CHECKPOINT_WAIVED` or `READINESS_R3_WAIVED` |
| Supersession | `SUPERSEDED_BY_EVIDENCE` when later measurement completes waived reminder |
| Correction | Supplemental note field only (§23); no replacement of original fact |

`WAIVER_DOMAIN_MODEL=PASS`  
`WAIVER_PROVENANCE=PASS`  
`WAIVER_HISTORY_CONTRACT=PASS`  
`WAIVER_REVISION_CONTRACT=PASS`

## Readiness model

| Predicate | Source |
|---|---|
| R1 | Current non-invalidated fermentation assessment confirmed/waived/overridden |
| R2 | `conditioning_skipped` OR current conditioning assessment OK |
| R3 | OG pin `KNOWN` OR active `ORIGINAL_GRAVITY_KNOWN` waiver OR R3-only override |
| `READY` | R1∧R2∧ known OG ∧ no readiness waiver/override |
| `READY_WITH_WAIVERS` | R1∧R2∧ (OG waiver or R3 override) |
| Not READY | Missing R1/R2/R3 → `INSUFFICIENT_EVIDENCE` |

Authority is PostgreSQL session/assessment/OG/waiver rows only (no Redis/LLM).

`READINESS_MODEL=PASS`  
`READINESS_AUTHORITY=PASS`  
`WAIVER_READINESS_INTERACTION=PASS`  
`DETERMINISTIC_READINESS=PASS`

## Lifecycle / late entry

- Checkpoint waivers: nonterminal statuses through `HANDOFF_READY`; denied `CLOSED`/`ABORTED`.
- `ORIGINAL_GRAVITY_KNOWN`: only `CONDITIONING_COMPLETE` / `COMPLETION_ASSESSED` / `HANDOFF_READY`.
- Assess/handoff reuse §9.5 allowlist; Close remains out of slice.
- Late-entry: not a separate waiver window beyond inherited measurement late-entry for evidence supersession.

`WAIVER_LIFECYCLE_CONTRACT=PASS`  
`WAIVER_LATE_ENTRY_CONTRACT=PASS`

## Idempotency / concurrency / security

| Gate | Result |
|---|---|
| Same operation_id replay | Single waiver row |
| Concurrent OG waiver (PG) | One ACTIVE leaf |
| Cross-owner | `404` |
| Non-waivable keys | `409 WAIVER_PROHIBITED`, zero rows |
| Stale revision | `409 STALE_REVISION` via OCC |

`IDEMPOTENCY_CONTRACT=PASS`  
`CONCURRENCY_CONTRACT=PASS`  
`OWNERSHIP_ISOLATION=PASS`  
`SECURITY_ACCEPTANCE=PASS`

## PostgreSQL / migration

| Item | Result |
|---|---|
| Migration | `0013_phase4_waivers` (revises `0012`) |
| Columns | `fermentation_waivers` + `fermentation_reminders.waivable` |
| Phase 1–3 migrations | Unchanged |
| Round-trip | `test_phase4_migration` PASS |

`POSTGRESQL_ACCEPTANCE=PASS`  
`MIGRATION_ACCEPTANCE=PASS`  
`PHASE_3_MIGRATIONS_UNCHANGED=YES`  
`PHASE_3_MIGRATION_ANCESTRY=PASS`

## API / read model / journal

- `POST /fermentation-sessions/{id}/waivers`
- `POST .../commands/assess-packaging-readiness`
- `POST .../commands/record-packaging-readiness-handoff`
- Session GET: `waivers`, `packaging_readiness_assessment`, `packaging_readiness_handoff`
- Journal: `FERMENTATION_WAIVER_RECORDED`, `FERMENTATION_WAIVER_SUPERSEDED`, `PACKAGING_READINESS_ASSESSED`, `PACKAGING_READINESS_HANDOFF_RECORDED`

`API_ACCEPTANCE=PASS`  
`WAIVER_READINESS_READ_MODEL=PASS`  
`JOURNAL_ACCEPTANCE=PASS`

## AC / ADV proofs

| ID | Test | Result |
|---|---|---|
| P4-AC-051 | `test_ac051_waiver_vs_later_gravity_supersession` | PASS |
| P4-AC-054 | `test_ac054_adv008_non_waivable_prohibited` | PASS |
| P4-AC-059 | `test_ac059_adv035_og_unknown_readiness_waiver_and_override` | PASS |
| P4-ADV-008 | same as AC-054 | PASS |
| P4-ADV-035 | same as AC-059 | PASS |

### ADV-008 record

- SPEC_FAULT_CONDITION: waive pitched_at / yeast note  
- SETUP: started fermentation session  
- ACTION: `POST .../waivers` with prohibited class  
- EXPECTED: `409 WAIVER_PROHIBITED`, no row  
- ACTUAL: matches  
- TEST_ID: `test_ac054_adv008_non_waivable_prohibited`

### ADV-035 record

- SPEC_FAULT_CONDITION: UNKNOWN OG readiness without waiver; override with R1 false  
- SETUP: conditioning complete + forced UNKNOWN OG; later invalidate fermentation assessment  
- ACTION: assess; waive+handoff; override assess  
- EXPECTED: not READY; then READY_WITH_WAIVERS; then `409 OVERRIDE_PROHIBITED`  
- ACTUAL: matches  
- TEST_ID: `test_ac059_adv035_og_unknown_readiness_waiver_and_override`

## Recovery

Fresh TestClient re-reads waivers + handoff from durable store.

`RECOVERY_ACCEPTANCE=PASS`

## Frontend / AI / Phase 5

| Gate | Result |
|---|---|
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| PLAYWRIGHT_ACCEPTANCE | NOT_REQUIRED |
| SLICE_11_AI_AUTHORITY_VIOLATION | NO |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO (Phase 4 packaging readiness assess/handoff only; no Close/finished-product/Phase 5 inventory) |

## Regressions

| Suite | Result |
|---|---|
| Slice 11 SQLite | PASS (7 passed, 1 skipped concurrency) |
| Slice 11 + migration PostgreSQL | PASS (`.pytest-p4s11-pg.txt`) |
| Phase 1A / 2 / 3 + Phase 4 slices 2–10 + Slice 11 | PASS (`.pytest-p4s11-reg.txt`, exit 0) |
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS |

## Traceability

| ID | Spec | Implementation | Persistence/API | Test | Evidence |
|---|---|---|---|---|---|
| P4-FR-059 | §10.3 §14.4 §23 | `waivers.py`, `readiness.py` | `0013`, GET waivers/handoff | `test_phase4_waivers_readiness.py` | this artifact |
| P4-FR-060 | §10.3 | NEVER_WAIVABLE + catalog | API 409 | `test_ac054_adv008_*`, `test_fr060_*` | this artifact |
| P4-AC-051 | §45 §20 | supersede_waiver_by_evidence | reminders + waivers | `test_ac051_*` | this artifact |
| P4-AC-054 | §45 | WAIVER_PROHIBITED | API | `test_ac054_adv008_*` | this artifact |
| P4-AC-059 | §45 §14.4–14.5 | assess + handoff + OG waiver | assessments/handoffs | `test_ac059_adv035_*` | this artifact |
| P4-ADV-008 | §46 | same as AC-054 | API | `test_ac054_adv008_*` | this artifact |
| P4-ADV-035 | §46 | same as AC-059 | API | `test_ac059_adv035_*` | this artifact |

`SLICE_11_FR_IMPLEMENTED=2/2`  
`SLICE_11_AC_VERIFIED=3/3`  
`SLICE_11_ADV_VERIFIED=2/2`  
`TRACEABILITY=PASS`

## Self-review

Falsified: non-waivable keys, stability class, duplicate active OG waiver, concurrent OG waiver, cross-owner 404, ACK≠SATISFIED, evidence supersession, UNKNOWN OG assess, READY_WITH_WAIVERS handoff, OVERRIDE_PROHIBITED with R1 false, idempotent replay, restart reread. No specification contradiction.

`IMPLEMENTATION_SELF_REVIEW=PASS`
