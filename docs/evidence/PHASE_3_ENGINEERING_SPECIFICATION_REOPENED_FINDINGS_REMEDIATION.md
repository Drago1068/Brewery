# Phase 3 Engineering Specification Reopened-Findings Remediation

## 1. Remediation identity

| Field | Value |
|---|---|
| Repository | `//NazarioNAS/USB_3TB/brewing-platform` (`B:\brewing-platform`) |
| Branch | `main` |
| Review baseline HEAD | `f7904e8b2a8eecb6cafe1da2a04c3b648902c242` |
| Phase 2 tag | `v0.2.0-phase2` |
| Phase 2 tag target | `c3faa93ea1502db63798b8c0dcc10c02741fabf7` |
| Authoritative re-review | `docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_INDEPENDENT_RE_REVIEW.md` |
| Re-review SHA-256 | `3714877F0CF7314BD6DB187F2D065EC8C11CCAA3F98F303135CCBBF817D95193` |
| Authoritative specification | `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` |
| Specification SHA-256 before remediation | `1CB2ED8AAFEBBA2E5F613E28CEE7A86F6086C04899F9646CF14088FC18EA9659` |
| Specification SHA-256 after remediation | `32BE496C83C937582047864A9722474E6578CC0E39C412A849684B7B3BBB5AB6` |
| Specification Git object after remediation | `7cbc627cab03c63c65057fb2e67758602214f38b` |

This is bounded documentation-only remediation of the four findings reopened by the independent re-review. It does not amend that historical FAIL decision, perform another independent review, authorize implementation, or authorize deployment.

## 2. Chosen decisions

The remediation makes one implementation-decidable choice in each affected area:

1. **Plan order:** `phase3-plan-v1` uses a fixed validation, canonical-rank, expansion, source-kind, sequence, occurrence and stable-identity total-order algorithm. Contradictory or malformed source order fails before session creation.
2. **Legacy compatibility:** accepted Phase 1A BrewSessions use the read-only deterministic `legacy-phase1a-session-v1` compatibility projection. Existing IDs/history remain unchanged; missing projected identities use fixed UUIDv5 namespace/name fixtures.
3. **Controlled return:** repeat and return always create a new stage occurrence. A completed occurrence is never continued or reopened; extension before completion is the sole same-occurrence continuation.
4. **Stage abort:** stage `ABORTED` is produced only as an atomic child of BrewSession abort. Independent stage cancellation is only optional `PENDING -> SKIPPED`.
5. **Waiver:** `phase3-waiver-v1` defines actor, reason, eligible and prohibited requirement classes, idempotency, reminder effect, completion meaning and append-only supersession by real evidence.
6. **Late evidence:** fixed five-minute clock tolerance, 24-hour measurement/addition windows, seven-day annotation window and 30-day correction window replace the word “bounded.” New evidence after `ABORTED` is prohibited.
7. **Terminal sessions:** `COMPLETED` and `ABORTED` have an explicit append-only allowlist; all other mutations are prohibited, and original terminal facts remain immutable.

These choices preserve the accepted modular monolith, four-layer architecture, PostgreSQL authority, RecipeVersion lineage, immutable history, deterministic calculations, Phase 2 ledger/reservation semantics, and yeast-pitch Phase 3 boundary.

## 3. Required four-finding closure matrix

| Reopened Finding | Severity | Specification Amendment | Requirement IDs | Acceptance IDs | Status |
|---|---|---|---|---|---|
| `P3SPEC-RR-001` | P1 / HIGH | Section 6.1.1 normative total-order/predecessor algorithm; fixed plan-step UUIDv5; `legacy-phase1a-session-v1` identity/status/read projection and migration rules; persistence invariants | P3-FR-006/007/008/009/090/091 | P3-AC-022/074/078/079; P3-ADV-026/035/036 | CLOSED |
| `P3SPEC-RR-002` | P2 / MEDIUM | Section 6.2 makes repeat/return new occurrences only; contiguous locked numbering, source links, active-stage prohibition, idempotency and API/persistence rules | P3-FR-016/019/092 | P3-AC-060/080; P3-ADV-017/027/037 | CLOSED |
| `P3SPEC-RR-003` | P1 / HIGH | Section 6.7 eight-column effects matrix; session-abort-only stage ABORTED; optional pending skip; `phase3-waiver-v1`; reminder supersession | P3-FR-012/015/025/028/037/093/094 | P3-AC-012/016/018/075/081; P3-ADV-016/028/038 | CLOSED |
| `P3SPEC-RR-004` | P1 / HIGH | Section 6.8 fixed late-evidence windows, state/actor/provenance rules, completed/aborted distinctions, terminal allowlist and reminder/comparison/journal effects | P3-FR-018/036/038/095/096 | P3-AC-018/060/065/082/083; P3-ADV-018/039/040 | CLOSED |

No `ARCHITECT_CONFLICT` was found.

## 4. Compatibility determination

### Phase 1A

Specification-level compatibility is restored. Existing session, Mash stage, timer, reminder, measurement, deviation and event IDs remain authoritative. Compatibility projection identities are deterministic across reads, restarts and migration round trips. Phase 1A routes resolve the same identities and call the Phase 3 services without duplicate Mash rows or alternate business logic.

### Phase 2

Specification-level compatibility is restored. RecipeVersion source order is validated rather than informally reinterpreted. Phase 3 consumes immutable process, ingredient, equipment, calculation and addition data into a session-scoped snapshot without mutating RecipeVersion, inventory transactions or reservations.

### Phase boundary

Phase 3 still ends at the yeast-pitch handoff. No fermentation, conditioning, packaging, quality, advanced inventory, Academy, sensory, competition, branding/menu, Knowledge Engine, AI, IoT, public route, deployment, BrewPlan/BrewBatch aggregate, outbox, distributed worker or offline-sync engine was introduced.

## 5. Count and traceability receipt

| Identifier family | Before | After | Unique | Dangling references |
|---|---:|---:|---|---:|
| Functional requirements | 84 | 91 | PASS | 0 |
| Acceptance criteria | 51 | 57 | PASS | 0 |
| Adversarial scenarios | 34 | 40 | PASS | 0 |

New requirements: `P3-FR-090` through `P3-FR-096`.

New acceptance criteria: `P3-AC-078` through `P3-AC-083`.

New adversarial scenarios: `P3-ADV-035` through `P3-ADV-040`.

Each new normative requirement maps to at least one deterministic acceptance criterion and adversarial or boundary-value scenario. No prior requirement, criterion or scenario was removed.

## 6. Documentation-only scope receipt

- Modified by this remediation: `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`.
- Created by this remediation: `docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_REOPENED_FINDINGS_REMEDIATION.md`.
- Preserved unchanged from the immediately preceding review task: `docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_INDEPENDENT_RE_REVIEW.md`.
- Application code, migrations, tests, dependencies, Docker/runtime configuration, ADRs and accepted Phase 0-2 evidence were not changed.
- Nothing was staged or committed.

## 7. Validation receipt

```text
repository/branch/HEAD                              -> PASS
Phase 2 tag target                                  -> PASS
complete independent re-review read                 -> PASS (302 lines)
reopened finding extraction                         -> PASS (4)
specification complete read                         -> PASS
functional requirements                             -> PASS (91 definitions; 91 unique)
acceptance criteria                                  -> PASS (57 definitions; 57 unique)
adversarial scenarios                                -> PASS (40 definitions; 40 unique)
dangling FR/AC/ADV references                        -> PASS (0)
four-finding closure matrix                          -> PASS (4 CLOSED; 0 OPEN/CONFLICT)
documentation-only path scope                       -> PASS
git diff --check                                    -> PASS
staged files                                         -> 0
commit                                               -> NOT CREATED
```

## 8. Final machine-readable result

```text
PHASE_3_REOPENED_FINDINGS_REMEDIATION=COMPLETE

REOPENED_FINDINGS_EXPECTED=4
REOPENED_FINDINGS_CLOSED=4
REOPENED_FINDINGS_OPEN=0

PLAN_ORDERING=CLOSED
LEGACY_SESSION_BACKFILL=CLOSED
CONTROLLED_RETURN_SEMANTICS=CLOSED
STAGE_ABORT_POLICY=CLOSED
WAIVER_POLICY=CLOSED
LATE_ENTRY_BOUNDS=CLOSED
TERMINAL_SESSION_BEHAVIOR=CLOSED

REMINDER_MODEL=PASS
MEASUREMENT_CONTEXT=PASS
PHASE_1A_COMPATIBILITY=PASS
PHASE_2_COMPATIBILITY=PASS
PHASE_3_SCOPE_CONFORMANCE=PASS
PHASE_4_10_OPERATIONAL_LEAKAGE=NO

FUNCTIONAL_REQUIREMENTS_BEFORE=84
FUNCTIONAL_REQUIREMENTS_AFTER=91
ACCEPTANCE_CRITERIA_BEFORE=51
ACCEPTANCE_CRITERIA_AFTER=57
ADVERSARIAL_SCENARIOS_BEFORE=34
ADVERSARIAL_SCENARIOS_AFTER=40
IDENTIFIER_UNIQUENESS=PASS

APPLICATION_CODE_CHANGED=NO
MIGRATIONS_CHANGED=NO
TEST_CODE_CHANGED=NO
DEPENDENCIES_CHANGED=NO

DOCUMENTATION_FILES_CHANGED=docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md,docs/evidence/PHASE_3_ENGINEERING_SPECIFICATION_REOPENED_FINDINGS_REMEDIATION.md

READY_FOR_CHIEF_ARCHITECT_REVIEW=YES
READY_FOR_NEW_SPEC_BASELINE=NO
READY_FOR_INDEPENDENT_RE_REVIEW=NO
PHASE_3_IMPLEMENTATION=NOT_AUTHORIZED
```

## 9. Stop boundary

`PHASE_3_IMPLEMENTATION_NOT_AUTHORIZED`

`NO_COMMIT_NO_TAG_NO_PUSH_NO_DEPLOYMENT`
