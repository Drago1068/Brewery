# Phase 4 Specification Second Remediation

Remediation date: 2026-08-31 (America/New_York)
Work type: specification only. No Phase 4 application code, tests, migrations, ADRs, tags, merges, NAS access, or implementation authorization.

## Identity

| Item | Value |
|---|---|
| Repository | `//NazarioNAS/USB_3TB/brewing-platform` |
| Branch | `spec/phase4-fermentation-conditioning-yeast` |
| Original specification commit | `e39a3fbd576c8cafaefad83a9686c5c152c08aec` |
| First remediation commit (reviewed) | `5db86bf8f8a3bc4390e45b676b5d156555e42abc` |
| First remediated specification SHA-256 | `9F5CE8DC46D5F9ADEAAF067A98A7CD259705C99FA1A6099A912CDB680CAD10D4` |
| SECOND_REMEDIATED_PHASE_4_SPEC_SHA256 | `50AC93DF69965A15FB084207B631316DCEC3D93D85E8DD35CA01AA2119CBC823` |
| Phase 3 baseline tag | `v0.3.0-phase3` |
| Phase 3 baseline commit | `39c440f234149e67be6dfae948b33393857a153e` |
| Fresh re-review artifact | `docs/evidence/PHASE_4_INDEPENDENT_SPECIFICATION_RE_REVIEW.md` (immutable; not modified) |
| Re-review artifact SHA-256 | `104236E2EB0422734724EC155E3F297739D568AD48290E031E97F808F18454E0` |
| Re-review SHA verified against expected | YES |
| First remediation evidence | `docs/evidence/PHASE_4_SPECIFICATION_REMEDIATION.md` (not modified) |
| Original review artifact | `docs/evidence/PHASE_4_INDEPENDENT_ARCHITECTURE_AND_SPECIFICATION_REVIEW.md` (not modified) |

`REVIEWED_REMEDIATION_COMMIT=5db86bf8f8a3bc4390e45b676b5d156555e42abc`

## Codex re-review verdict (authoritative source: re-review artifact)

```
PHASE_4_INDEPENDENT_SPECIFICATION_RE_REVIEW=FAIL
PRIOR_P1_OPEN=7
PRIOR_BLOCKING_P2_OPEN=2
NEW_P3_FINDINGS=1
ORPHAN_FR_COUNT=0
ORPHAN_AC_COUNT=0
ORPHAN_ADV_COUNT=0
PHASE_3_BASELINE_COMPATIBILITY=PASS
PHASE_5_PLUS_LEAKAGE_CONTROL=PASS
OPEN_BLOCKING_QUESTIONS=7
ADR_CANDIDATES_ACTUAL=2
ADR_BLOCKERS=0
SPECIFICATION_ACCEPTANCE_RECOMMENDED=NO
```

The seven open blocking questions in the re-review are the residual gaps inside existing RQ-02, RQ-03, RQ-04, RQ-06, RQ-07, RQ-08, and RQ-11. They are not new product decisions.

## Reopened finding inventory

| FINDING_ID | ORIGIN | SEVERITY | BLOCKING_STATUS | PRIOR_FINDING_ID | SPEC_REFERENCE | ROOT_CAUSE | REQUIRED_REMEDIATION | AFFECTED_SECTIONS | AFFECTED_FR | AFFECTED_AC | AFFECTED_ADV | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P4-RR-001 | REOPENED | P1 | YES | P4-SPEC-002 | §9.4 vs §9.5 | Allowlist A cells missing from the sole transition table; reassessment destinations undefined | Add every A-cell row; define ASSESSED/HANDOFF_READY/CLOSED assess/handoff effects | 9.4, 9.5 | 015,021,089 | 057,058 | 034 | CLOSED |
| P4-RR-002 | REOPENED | P1 | YES | P4-SPEC-003 | §10.3; §14.4–14.5 | Missing-OG READY_WITH_WAIVERS path not in waiver catalog; override vs R1–R3 undefined | Named `ORIGINAL_GRAVITY_KNOWN`; override R3-only | 10.3, 14.4, 14.5 | 042,059,089 | 059 | 035 | CLOSED |
| P4-RR-003 | REOPENED | P1 | YES | P4-SPEC-004 | §7.1; §9.4; §14.6 | Invalidation vs stage cardinality; CLOSED requalify needs R1/R2 without Complete*; timestamps | Reuse stage PK; current vs first timestamps; CLOSED current-evidence path | 7.1, 8.4, 9.7, 9.8, 14.6 | 024,043,044,088,089 | 026,060,061 | 036 | CLOSED |
| P4-RR-004 | REOPENED | P1 | YES | P4-SPEC-006 | §13; FR-038 | Plato inverse out-of-image and nonconvergence undefined | Domain = accepted SG-to-Plato image; 422 codes; no clamp | 13, 42 | 038 | 062 | 037 | CLOSED |
| P4-RR-005 | REOPENED | P1 | YES | P4-SPEC-007 | §14.6; §18; §24 | Reactivation keeps old `completed_at`; §18 still bounded by it | Current-activation window while ACTIVE/PAUSED | 9.8, 18, 24 | 029,088 | 063 | 038 | CLOSED |
| P4-RR-006 | REOPENED | P1 | YES | P4-SPEC-008 | §10.1–10.3 | `details.schedule` unrecognized; no ingredient order; UUIDv5 omits session | Recognize schedule keys; ingredient total order; template vs row ID | 10.1, 10.2, 10.3 | 011 | 064 | 039 | CLOSED |
| P4-RR-007 | REOPENED | P1 | YES | P4-SPEC-011 | §30; §32 | Race rows said both ops commit despite mandatory `expected_revision` | Same initial revision: one winner; loser 409 STALE; fail increments revision | 32, 31 | 073,074 | 065 | 040 | CLOSED |
| P4-RR-008 | REOPENED | P2 | YES | P4-SPEC-012 | §30–31 | Assessment fingerprint included server evidence; unknown fields ignore-or-422 | Client-canonical only; lookup before evidence reread; always `422 UNKNOWN_FIELD` | 30, 31, 33 | 072,077 | 066,067 | 041 | CLOSED |
| P4-RR-009 | REOPENED | P2 | YES | P4-SPEC-016 | §23–25 | Combined Action/Addition and Yeast/Equipment terminal rows | Split rows; Action DENY after CLOSED; addition late ≤24h; yeast annotation ≤7d | 24, 25, 30 | 016,061 | 068 | 042 | CLOSED |

## New finding inventory

| FINDING_ID | ORIGIN | SEVERITY | BLOCKING_STATUS | PRIOR_FINDING_ID | SPEC_REFERENCE | ROOT_CAUSE | REQUIRED_REMEDIATION | AFFECTED_SECTIONS | STATUS |
|---|---|---|---|---|---|---|---|---|---|
| P4-RR-010 | NEW | P3 | NO | none | §58 P4-SPEC-015 RELATED_AC | Stale AC range `001–053` vs defined `001–056` | Correct the historical closure row to the full AC range | 58 | CLOSED |

P4-RR-010 was bounded governance prose. It was repaired without architectural change.

## Root-cause groups

1. **Lifecycle totality (RR-001, RR-003, RR-005).** §9.5 was treated as authority while §9.4 was incomplete; invalidation lacked a reuse rule; time used historical `completed_at` as the live upper bound. Repair: §9.4 is sole transition authority; §9.8 reuses the stage PK with `activation_ordinal` and `current_activation_started_at`; §18 current-activation window; CLOSED stays CLOSED and requalifies from current evidence.
2. **OG waiver mapping (RR-002).** Readiness mentioned a missing-OG waiver that the catalog did not name. Repair: `ORIGINAL_GRAVITY_KNOWN` readiness-only; override bypasses R3 only.
3. **Plato inverse domain (RR-004).** Binary search had no out-of-image or nonconvergence result. Repair: domain is the image of accepted `specific_gravity_to_plato` on SG `[0.900, 1.300]`; hard 422; no clamp.
4. **Plan identity (RR-006).** Schedule keys were consumed but unrecognized; hashing order and requirement IDs were non-deterministic across abort/restart. Repair: recognized keys, ingredient total order, template ID vs session-owned row ID.
5. **OCC / idempotency (RR-007, RR-008).** Race outcomes contradicted `expected_revision`; assessment identity included mutable server evidence; unknown fields were dual-valued. Repair: loser always `409 STALE_REVISION`; client-canonical fingerprint; lookup before evidence reread; `422 UNKNOWN_FIELD`.
6. **Terminal resource split (RR-009).** Combined rows mixed Action vs Addition and Yeast vs Equipment. Repair: one row per class; API rows aligned.
7. **Governance range (RR-010).** §58 RELATED_AC lagged the actual AC set. Repair: full current ranges.

Passing first-remediation contracts were not redesigned: Phase 3 handoff consumption, Phase 5 operational leakage boundary, and §54 formal orphan structure.

## Exact normative changes

- §7.1: handoff timestamps use `*_current_completed_at`; READY/READY_WITH_WAIVERS map to §14.4; CLOSED-path R1/R2 from current evidence.
- §8.4: invalidated CONDITIONING is reactivated, never a second PK.
- §9.4: sole session command authority. Added Abort from PAUSED (both origins) and CONDITIONING_COMPLETE; reassess/handoff from ASSESSED, HANDOFF_READY, CLOSED; failed Complete* increments revision.
- §9.5: remains a non-normative index that must match §9.4.
- §9.7 / §9.8: first vs current timestamps; reactivation contract (PK reuse, ordinal, current-activation start, new timer identities, reminder satisfaction rules).
- §10.1–10.3: recognized `schedule` and `conditioning_schedule`; ingredient total order; template vs row identity; `ORIGINAL_GRAVITY_KNOWN`.
- §13 / safety: Plato image domain; `PLATO_OUT_OF_DOMAIN` / `PLATO_CONVERSION_FAILED`; 100 Plato golden; no clamp.
- §14.3: C1 uses `conditioning_first_started_at`.
- §14.4–14.5: missing-OG waiver; R3-only readiness override; `409 OVERRIDE_PROHIBITED` if R1/R2 fail.
- §14.6: reuse destinations; after CLOSED do not null current completion instants; AssessPackagingReadiness from current evidence without Complete*.
- §18: ACTIVE/PAUSED observations use `[current_activation_started_at - 5m, now + 5m]`; historical `completed_at` is not an active upper bound.
- §24 / §25.1: split Action, Addition, Yeast, Equipment; RecordAction DENY after CLOSED; addition late ≤24h; yeast source-pair DENY, annotation ≤7d; equipment DENY.
- §30 / §31 / §32 / §33: `422 UNKNOWN_FIELD`; client-canonical assessment fingerprint; lookup before evidence reread; OCC loser 409 STALE; new `operation_id` after STALE; failed assessment increments revision.
- Journal: `FERMENTATION_STAGE_REACTIVATED`.
- FR 088–089, AC 057–068, ADV 034–042 added; existing FR texts aligned; §54 rebuilt; §58 historical columns extended.

## Finding-by-finding closure evidence

### P4-RR-001 / P4-SPEC-002

Remaining undecidable behavior: Abort from PAUSED or CONDITIONING_COMPLETE, and next-state for Assess/Handoff from ASSESSED, HANDOFF_READY, CLOSED.

Repair: every §9.5 A cell has a §9.4 row. Abort from PAUSED (both origins) and CONDITIONING_COMPLETE → ABORTED + §9.6. Reassess from ASSESSED stays ASSESSED with a new current packaging assessment. Reassess from HANDOFF_READY stays HANDOFF_READY if still READY/READY_WITH_WAIVERS (handoff unchanged until RecordHandoff); R1/R2 failure → COMPLETION_ASSESSED and current handoff INVALIDATED. CLOSED assess/handoff remain CLOSED.

Proof: P4-AC-057, P4-AC-058, P4-ADV-034. Layers: DOMAIN_UNIT, API_INTEGRATION, POSTGRESQL.

### P4-RR-002 / P4-SPEC-003

Remaining undecidable behavior: missing-OG READY path and which R-predicates override may bypass.

Repair: cataloged `ORIGINAL_GRAVITY_KNOWN` (readiness-only; never silent READY). Override on AssessPackagingReadiness bypasses R3 only; R1 or R2 false → `409 OVERRIDE_PROHIBITED`.

Proof: P4-AC-059, P4-ADV-035. Layers: API_INTEGRATION.

### P4-RR-003 / P4-SPEC-004

Remaining undecidable behavior: second CONDITIONING PK vs reuse; CLOSED requalify with INVALIDATED Complete* rows; current vs first timestamps.

Repair: §9.8 reuses `stage_instance_id`, increments `activation_ordinal`. CLOSED stays CLOSED; AssessPackagingReadiness evaluates current F/C evidence without Complete*; original Complete* rows stay INVALIDATED; `*_current_completed_at` is not nulled after CLOSED; handoff copies those instants plus current evidence IDs. AC-026 fixture is exact.

Proof: P4-AC-026, P4-AC-060, P4-AC-061, P4-ADV-036. Layers: POSTGRESQL, API_INTEGRATION.

### P4-RR-004 / P4-SPEC-006

Remaining undecidable behavior: 100 Plato / nonconvergence / clamp.

Repair: raw Plato must lie in the closed image of accepted `specific_gravity_to_plato` over SG `[0.900, 1.300]`. Outside → `422 PLATO_OUT_OF_DOMAIN` and no row. Inside but 80 iterations miss residual → `422 PLATO_CONVERSION_FAILED`, no clamp.

Proof: P4-AC-062, P4-ADV-037. Layer: DOMAIN_UNIT.

### P4-RR-005 / P4-SPEC-007

Remaining undecidable behavior: day-10 invalidation then a new CONDITIONING_TEMPERATURE rejected by old `completed_at`.

Repair: while ACTIVE/PAUSED, §18 uses `current_activation_started_at`, not historical `completed_at`, as the live bound. First `completed_at` remains immutable.

Proof: P4-AC-063, P4-ADV-038. Layers: API_INTEGRATION, POSTGRESQL.

### P4-RR-006 / P4-SPEC-008

Remaining undecidable behavior: schedule ignored-and-normative; ingredient hash order; abort/restart requirement PK collision.

Repair: `schedule` and `conditioning_schedule` are recognized keys. Ingredients hash in `use_stage ASC, timing_minutes ASC NULLS FIRST, ingredient_id ASC, id ASC`. Template UUIDv5 omits session; session-owned row UUID is unique on `(fermentation_session_id, requirement_template_id)`.

Proof: P4-AC-064, P4-ADV-039. Layer: DOMAIN_UNIT.

### P4-RR-007 / P4-SPEC-011

Remaining undecidable behavior: concurrent complete+measurement with the same initial revision; failed-assessment revision.

Repair: exactly one winner; loser `409 STALE_REVISION` and zero domain rows. Observing the winner requires a new command with a new `operation_id`. `422 COMPLETION_INELIGIBLE` increments revision.

Proof: P4-AC-065, P4-ADV-040. Layer: POSTGRESQL.

### P4-RR-008 / P4-SPEC-012

Remaining undecidable behavior: lost assessment retry after new gravity; unknown fields ignore-or-422.

Repair: fingerprint is the client command plus defaults only. Lookup `(scope, operation_id)` before rereading evidence. Same key/same client payload always replays. Unknown fields `422 UNKNOWN_FIELD`.

Proof: P4-AC-066, P4-AC-067, P4-ADV-041. Layers: API_INTEGRATION, SECURITY.

### P4-RR-009 / P4-SPEC-016

Remaining undecidable behavior: RecordAction vs addition after CLOSED; yeast pair vs annotation; equipment.

Repair: Action CREATE DENY after CLOSED (12h and 25h). Addition execute ≤24h after `closed_at`. Yeast source-pair DENY; annotation ≤7d. Equipment DENY.

Proof: P4-AC-068, P4-ADV-042. Layers: API_INTEGRATION, SECURITY.

### P4-RR-010

Repair: §58 P4-SPEC-015 RELATED_AC/ADV/FR now `001–068` / `001–042` / `001–089`. Historical FAIL is preserved via RE_REVIEW_STATUS.

## Affected FR / AC / ADV (second pass)

Expanded: P4-FR-011, 015, 018, 024, 038, 043, 059, 072, 074, 077.

Added: P4-FR-088, P4-FR-089; P4-AC-057 through P4-AC-068; P4-ADV-034 through P4-ADV-042.

## Final counts

| Family | First remediation | Second remediation |
|---|---:|---:|
| P4-FR | 87 | **89** (P4-FR-001 through P4-FR-089) |
| P4-AC | 56 | **68** (P4-AC-001 through P4-AC-068) |
| P4-ADV | 33 | **42** (P4-ADV-001 through P4-ADV-042) |

`ORPHAN_FR_COUNT=0`  
`ORPHAN_AC_COUNT=0`  
`ORPHAN_ADV_COUNT=0`

Independent parse of §54: 89 unique FR rows; every AC 001–068 and ADV 001–042 cited at least once; no unknown IDs.

## Traceability verification

`TRACEABILITY_DESIGN=PASS`

§54 remains the bidirectional map. New IDs are contiguous with no gaps. Obsolete mappings to superseded IDs were not retained. P4-RR-010 range lag is closed.

`TESTABILITY=PASS`: each remediating FR names a primary executable layer (DOMAIN_UNIT, POSTGRESQL, API_INTEGRATION, SECURITY). Documentation presence is not proof.

## Phase 3 compatibility regression

`PHASE_3_BASELINE_COMPATIBILITY=PASS`

No accepted Phase 0–3 file was edited. OG remains pre-pitch; journal merge key is unchanged; AdditionEvent authority is unchanged; pitch-temperature nullability is unchanged; Phase 4 still consumes rather than rewrites BrewSession.

## Phase 5 leakage regression

`PHASE_5_PLUS_LEAKAGE_CONTROL=PASS`

Phase 4 still emits versioned readiness/lineage facts only. No packaging operations, packaged inventory, keg/bottle/can, tap/menu, sensory, competition, or branding commands were added. CLOSED requalify still cannot create packaging rows (P4-AC-026 / P4-FR-013).

## Other passing-contract regression

Protected and not weakened: `INVENTORY_CONTRACT`, `ACCESSIBILITY_CONTRACT`, `AI_BOUNDARY`, `MIGRATION_ACCEPTANCE_CONTRACT`, `PHASE_1A_REGRESSION_CONTRACT`, `PHASE_2_REGRESSION_CONTRACT`, `PHASE_3_REGRESSION_CONTRACT`.

Security recheck of API/state/idempotency edits: unknown fields cannot mass-assign; OCC loser writes no rows; terminal RecordAction cannot use the addition window; IDOR/CSRF/cross-session rules were not relaxed.

## ADR disposition

`ADR_CANDIDATES_ACTUAL=2` (`P4-DEC-003`, `P4-DEC-004`)  
`ADR_BLOCKERS=0`

No ADR files created. No reopened finding required a new architectural decision.

## Open-question disposition

`OPEN_QUESTIONS_ACTUAL=14`  
`OPEN_BLOCKING_QUESTIONS=0`

P4-OQ-001–003 remain non-blocking. RQ-01–RQ-11 remain the original implicit questions; residual re-review gaps inside RQ-02, RQ-03, RQ-04, RQ-06, RQ-07, RQ-08, and RQ-11 are closed by the contracts above. No new blocking product decision was discovered.

## Self-review result

Adversarial pass over state transitions, completion, invalidation, conditioning, corrections, late entry, terminal mutation, timers/reminders, idempotency, concurrency, API, security, recovery, backup/restore, performance, and traceability.

Contradictions removed before completion:

- §7.1 READY wording vs CLOSED current-evidence R1/R2;
- §14.6 after-CLOSED timestamp nulling vs handoff provenance;
- §18 `conditioning_started_at` vs `conditioning_first_started_at`;
- §24 CLOSED “additions only” wording that collided with measurement late-entry;
- leftover “combined” terminal heading.

No remaining blocking ambiguity was left open.

`SPECIFICATION_SELF_REVIEW=PASS` as an author checklist, not independent acceptance.

## Readiness conclusion

```
PHASE_4_SPECIFICATION_STATUS=REVIEW_CANDIDATE
PHASE_4_SPECIFICATION_ACCEPTANCE=NOT_YET_GRANTED
PHASE_4_IMPLEMENTATION_AUTHORIZATION=NOT_GRANTED
PHASE_4_IMPLEMENTATION_STARTED=NO
PHASE_5_IMPLEMENTATION=NOT_AUTHORIZED
PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED
NAS_ACCESS=NOT_AUTHORIZED
READY_FOR_FINAL_CODEX_SPECIFICATION_VERIFICATION=YES
```

Independent Codex specification verification is requested against the second-remediation commit and SHA-256 recorded after this artifact is committed. Acceptance is not granted by this document.
