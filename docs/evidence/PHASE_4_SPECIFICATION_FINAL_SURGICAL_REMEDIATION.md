# Phase 4 Final Surgical Specification Remediation

Remediation date: 2026-08-31 (America/New_York)
Work type: specification-only surgical correction. No application code, tests, migrations, merge, tag, deployment, NAS runtime access, or implementation authorization.

## Exact input identity

```text
REPOSITORY=B:\brewing-platform
BRANCH=spec/phase4-fermentation-conditioning-yeast
INPUT_SPEC_COMMIT=96da17c3264a421a13b467bb117ca9b049dabd4f
INPUT_SPEC_SHA256=50AC93DF69965A15FB084207B631316DCEC3D93D85E8DD35CA01AA2119CBC823
PHASE_3_BASELINE_TAG=v0.3.0-phase3
PHASE_3_BASELINE_COMMIT=39c440f234149e67be6dfae948b33393857a153e
FINAL_VERIFICATION_SHA256=86E7EB94C5BD6422B246C618F7A45784E394C3629DA340C974FC562A40FE2CA7
REMAINING_FINDING_ID=P4-FINAL-001
```

All input identities and hashes were verified before editing. The final verification artifact exactly matched the required hash.

## Root cause and selected policy

```text
ROOT_CAUSE=The Section 31 unplanned-addition TERMINAL_BEHAVIOR cell denied all terminal submissions while Sections 24, 25, and 30 allowed a 24-hour CLOSED exception. The prior text also failed to distinguish physical event occurrence from later recording.
CANONICAL_POLICY_SELECTED=BOUNDED_LATE_ENTRY
WHY_THIS_POLICY_MATCHES_EXISTING_SPEC_INTENT=Sections 24, 25, and 30 already treated additions as append-only late evidence; Phase 3 preserves dual-time occurred_at and recorded_at semantics; Section 21 already separates evidence recording from inventory or operational authority. Three aligned contracts supported bounded historical entry while only the stale Section 31 cell said deny.
```

The selected policy is not a new brewing operation. It permits recording historical evidence only when `occurred_at <= closed_at` and the server receives the fresh request by `closed_at + 24 hours`, inclusive. It rejects a claimed occurrence after closure and always rejects new addition evidence for `ABORTED`.

## Canonical contract

Section 31.1, `phase4-terminal-addition-v1`, is the sole authority for planned and unplanned addition submission after `CLOSED`.

A fresh terminal addition command:

1. requires owner, CSRF, `operation_id`, and `expected_revision`;
2. resolves an existing idempotency result before state/window reevaluation;
3. locks the session and checks revision;
4. rejects `occurred_at > closed_at` with `422 TERMINAL_ADDITION_OCCURRED_AFTER_CLOSE`;
5. accepts server receipt through exactly `closed_at + 24 hours`;
6. rejects a fresh later request with `409 LATE_ENTRY_WINDOW_CLOSED`;
7. appends historical evidence with `late_entry=true` and never reopens the session;
8. rejects `ABORTED` with `409 TERMINAL_SESSION_EVIDENCE_PROHIBITED`;
9. replays the same key/body even after the boundary and emits no duplicate journal event.

Close versus addition is serialized by the session lock and OCC. One same-revision command wins; the loser returns `409 STALE_REVISION` with zero domain rows. A fresh retry after Close is evaluated under the canonical terminal rule.

## Surgical change inventory

```text
SECTIONS_CHANGED=21.2,24,25,26,30,31,32,44,45,46,54,58
FR_CHANGED=P4-FR-054,P4-FR-061,P4-FR-074
AC_CHANGED=P4-AC-068
ADV_CHANGED=P4-ADV-042
TERMINAL_MATRIX_CHANGED=YES
API_CONTRACT_CHANGED=YES
IDEMPOTENCY_CONTRACT_CHANGED=YES
CONCURRENCY_CONTRACT_CHANGED=YES
TRACEABILITY_REVALIDATED=PASS
PHASE_3_COMPATIBILITY_REVALIDATED=PASS
PHASE_5_LEAKAGE_REVALIDATED=PASS
FINDING_STATUS=CLOSED
```

Details:

- §21.2 distinguishes normal execution, nonterminal completed-stage late entry, and the sole CLOSED historical exception.
- §24 no longer independently authorizes terminal additions and points only to §31.
- §25's Addition row points only to §31 for terminal create/late-entry behavior.
- §26 projects occurrence time, recording time, late-entry flag, terminal state, operation identity, and correction lineage; replay emits no duplicate event.
- §30 supplies one API path/result and requires revision for CLOSED addition submission.
- §31 defines the sole policy, exact inclusive boundaries, validation/conflict codes, idempotent replay, ABORTED denial, and no-reopen effects.
- §32 adds R14 for Close versus planned/unplanned late addition.
- FR-054, FR-061, and FR-074 express the state, time, and OCC requirements.
- AC-068 proves allowed, denied, exact-boundary, replay, changed-payload, and stale-race results.
- ADV-042 proves the lost-response retry cannot cross the terminal boundary into a different domain result.
- §54 links AC-068/ADV-042 to FR-054, FR-061, FR-072, and FR-074.
- §58 appends the P4-FINAL-001 closure without erasing prior FAIL history.

## Self-verification

The entire Phase 4 specification was searched for unplanned addition, post-terminal/post-CLOSED addition, late addition/entry, 24-hour, CLOSED, and terminal-addition wording. The stale `deny after terminal` unplanned-addition cell is gone. The earlier §21 “only ACTIVE/CONDITIONING” wording now distinguishes normal execution from §24 and §31 historical late entry.

Reconstruction of the four required sections:

| Section | Result |
|---|---|
| §24 | No independent terminal-addition authority; points to §31 |
| §25 | Addition terminal CREATE/LATE_ENTRY allowed only under §31 |
| §30 | API validates nonterminal late entry under §24 and CLOSED late entry only under §31 |
| §31 | Sole BOUNDED_LATE_ENTRY authority, with exact time, retry, conflict, journal, and ABORTED rules |

```text
FUNCTIONAL_REQUIREMENTS_COUNT=89
ACCEPTANCE_CRITERIA_COUNT=68
ADVERSARIAL_SCENARIOS_COUNT=42
ORPHAN_FR_COUNT=0
ORPHAN_AC_COUNT=0
ORPHAN_ADV_COUNT=0
INVALID_TRACEABILITY_REFERENCE_COUNT=0
PHASE_3_BASELINE_COMPATIBILITY=PASS
PHASE_5_PLUS_LEAKAGE_CONTROL=PASS
ACTION_ADDITION_CONTRACT=PASS
LATE_ENTRY_CONTRACT=PASS
TERMINAL_BEHAVIOR_CONTRACT=PASS
API_CONTRACT=PASS
IDEMPOTENCY_CONTRACT=PASS
CONCURRENCY_CONTRACT=PASS
JOURNAL_CONTRACT=PASS
TRACEABILITY_DESIGN=PASS
TESTABILITY=PASS
SPECIFICATION_SELF_REVIEW=PASS
```

Phase 3 AdditionEvent compatibility is preserved: append-only evidence, dual timestamps, operation idempotency, correction lineage, PostgreSQL authority, and zero Phase 4 inventory consumption remain unchanged.

No Phase 5 packaging, finished inventory, keg/bottle/can, tap/menu, sensory, competition, branding, Academy, experiment, or Knowledge Engine operation was introduced.

## Output identity and readiness

```text
FINAL_REMEDIATED_PHASE_4_SPEC_SHA256=EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D
PRIOR_P0_OPEN=0
PRIOR_P1_OPEN=0
PRIOR_BLOCKING_P2_OPEN=0
PRIOR_P3_OPEN=0
TOTAL_P0_OPEN=0
TOTAL_P1_OPEN=0
TOTAL_BLOCKING_P2_OPEN=0
TOTAL_P3_OPEN=0
OPEN_QUESTIONS_ACTUAL=14
OPEN_BLOCKING_QUESTIONS=0
ADR_CANDIDATES_ACTUAL=2
ADR_BLOCKERS=0
PHASE_4_SPECIFICATION_STATUS=REVIEW_CANDIDATE
PHASE_4_SPECIFICATION_ACCEPTANCE=NOT_YET_GRANTED
PHASE_4_IMPLEMENTATION_AUTHORIZATION=NOT_GRANTED
PHASE_4_IMPLEMENTATION_STARTED=NO
PHASE_5_IMPLEMENTATION=NOT_AUTHORIZED
NAS_ACCESSED=NO
NAS_CHANGED=NO
PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED
```

The semantic closure gates pass. The repository contained unrelated pre-existing untracked evidence, database, build, and test-output files before this remediation. They were preserved and excluded from the commit. Therefore the full Git worktree remains dirty even though the remediation's tracked paths are clean after commit.

```text
READY_FOR_FINAL_CODEX_CLOSURE_CHECK=NO
WORKING_TREE=DIRTY
READINESS_BLOCKER=PRE_EXISTING_UNTRACKED_FILES_ONLY
```
