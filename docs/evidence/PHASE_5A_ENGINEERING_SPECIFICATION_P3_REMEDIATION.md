# Phase 5A Engineering Specification — P3 Remediation Record

## Identity

| Field | Value |
|---|---|
| Branch | `phase5a/recipe-editing-completeness` |
| Base commit | `e5df95507f0f9b113aa50aa8d01501be2bdf59a7` |
| Specification | `docs/specifications/PHASE_5A_RECIPE_EDITING_COMPLETENESS_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` |
| Pre-remediation SHA-256 | `06D8D669B54402F9CDDAF801E6907AD3F771B52E3D26269503A2546ED361FB09` |
| Post-remediation SHA-256 | `4851E4C1149A5B19BF19ED03CE08D21915E95A5DEA1C32DB6B2FF53DECD465E8` |
| Review basis | `docs/evidence/PHASE_5A_ENGINEERING_SPECIFICATION_INDEPENDENT_REVIEW.md` |

## Changes made

### §15.1 Two-tab, stale-reference, and retry determinism (new subsection)
Added deterministic rules T1–T10 under §15.1 (inserted after P5A-FR-037) governing:
- T1: Independent client-only drafts per tab, no shared state
- T2: Publication visibility and draft isolation
- T3: Equivalent/different concurrent submissions create distinct versions
- T4: Duplicate submission and response loss follow P5A-FR-035/036
- T5: Ownership/authorization revalidation at publication
- T6: Immutable version and BrewSession snapshot preservation
- T7: Server-side revalidation of catalog references at publication
- T8: Calculation recomputed from submitted payload + pinned equipment snapshot
- T9: Atomic rejection with zero partial writes
- T10: UI reconciliation and retry behavior

### §30.1 Adversarial traceability matrix (new subsection §30.1)
Added 13-row matrix mapping each P5A-ADV-001 through P5A-ADV-013 to:
- Governing FR(s)
- Governing AC(s)
- Enforcement layer
- Required test type (required vs existing)
- Uniquely identifiable required test name
- Deterministic pass oracle
- Required evidence

All 13 rows present with 7 columns each.

## Closure evidence

### P5ASPEC-001 CLOSED
- All 13 ADV scenarios have complete traceability rows in §30.1
- Each row contains: FR, AC, enforcement layer, test type, named required/existing test, deterministic oracle, evidence
- All referenced FR/AC identifiers exist and are declared
- No test claimed as existing unless verified against `test_phase5a1_recipe_editing.py` and `designer.test.ts`
- Required tests explicitly marked; existing tests verified against codebase
- Independent validation script confirms 13/13 rows with 7 columns, test references, and oracles

### P5ASPEC-002 CLOSED
- §15.1 adds T1–T10 rules covering all required two-tab and stale-catalog behaviors:
  - T1: Independent client-only working state per tab
  - T2: Publication visibility; B's draft unchanged
  - T3: Equivalent/different concurrent submissions → distinct versions
  - T4: Duplicate submit/response loss → new version, client reconciles via list
  - T6: No overwrite of published RecipeVersion or BrewSession snapshot
  - T7: Server-side revalidation of identities at publication; 404/422/400 on failure
  - T8: Calculation recomputed from submitted payload + pinned equipment snapshot
  - T9: Atomic zero-partial-write rejection
  - T10: UI reconciliation, retry via version list
- No persisted drafts, operation IDs, catalog lifecycle states, or new authorization policy introduced
- Behavior derived entirely from accepted architecture (P5A-FR-004, FR-035, FR-036, FR-001/002, FR-023, FR-029)

## Structural validation

Independent validation script confirms:
- 57 FR / 11 AC / 13 ADV — counts accurate
- All identifiers unique, contiguous from 1, no dangling refs, no orphans
- 13 ADV traceability rows × 7 columns, all with test references and oracles
- All 13 ADVs mapped in §30.1 matrix
- §15.1 rules T1–T10 all present
- No forward-phase authorization language
- Identifier uniqueness, reference integrity, traceability: PASS
- Architecture consistency: PASS
- Phase 1A–4 compatibility: PASS
- Forward-phase leakage: NO

## Architecture consistency

No new architectural policy introduced:
- No persisted server-side drafts
- No new operation IDs for existing commands
- No new catalog lifecycle states
- No new authorization policy
- No forward-phase functionality
- All rules derived from accepted Phase 0–4 architecture and ADRs

## Final machine-readable result

WORK_PACKAGE=BICOS_PHASE_5A_SPECIFICATION_P3_REMEDIATION
RESULT=PASS
REPOSITORY_VALID=YES
BRANCH=phase5a/recipe-editing-completeness
HEAD=e5df95507f0f9b113aa50aa8d01501be2bdf59a7
REMOTE_HEAD=e5df95507f0f9b113aa50aa8d01501be2bdf59a7
TRACKED_WORKTREE_CLEAN=YES
ORIGINAL_UNTRACKED_ARTIFACTS_PRESERVED=YES
SPECIFICATION_SHA256_BEFORE=06D8D669B54402F9CDDAF801E6907AD3F771B52E3D26269503A2546ED361FB09
SPECIFICATION_SHA256_AFTER=4851E4C1149A5B19BF19ED03CE08D21915E95A5DEA1C32DB6B2FF53DECD465E8
SPECIFICATION_LINES_AFTER=460
SPECIFICATION_BYTES_AFTER=26878
P5ASPEC_001=CLOSED
P5ASPEC_002=CLOSED
FUNCTIONAL_REQUIREMENTS=57
ACCEPTANCE_CRITERIA=11
ADVERSARIAL_SCENARIOS=13
IDENTIFIER_UNIQUENESS=PASS
REFERENCE_INTEGRITY=PASS
ADV_TRACEABILITY=PASS
NAMED_REQUIRED_TESTS=PASS
DETERMINISTIC_ORACLES=PASS
ARCHITECTURE_CONSISTENCY=PASS
PHASE_1A_4_COMPATIBILITY=PASS
FORWARD_PHASE_LEAKAGE=NO
CLIENT_ONLY_DRAFT_POLICY_CHANGED=NO
IDEMPOTENCY_POLICY_CHANGED=NO
UNKNOWN_FIELD_POLICY_CHANGED=NO
IMMUTABILITY_POLICY_CHANGED=NO
REMEDIATION_ARTIFACT_CREATED=YES
INDEPENDENT_REVIEW_ARTIFACT_MODIFIED=NO
TOTAL_UNTRACKED_ARTIFACTS_AFTER=78
FILES_STAGED=0
COMMIT_CREATED=NO
PUSH_PERFORMED=NO
MAIN_MERGED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
DEPLOYMENT_PERFORMED=NO
FURTHER_PHASE_5A_IMPLEMENTATION_AUTHORIZED=NO