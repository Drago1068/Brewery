# Phase 5A Engineering Specification — Independent Review

## 1. Environment receipt

| Field | Value |
|---|---|
| Root / origin | `B:\brewing-platform` / `https://github.com/Drago1068/Brewery.git` |
| Branch / HEAD / remote | `phase5a/recipe-editing-completeness` / `e5df95507f0f9b113aa50aa8d01501be2bdf59a7` / same (live verified) |
| Tracked tree | CLEAN throughout (no staged/unstaged diffs) |
| Untracked | 74 originals preserved + proposed spec only (75 total) |
| Spec SHA-256 | `06D8D669B54402F9CDDAF801E6907AD3F771B52E3D26269503A2546ED361FB09` (397 lines, 21099 bytes — matches) |
| Competing 5A spec | none (`docs/specifications/` holds only Phase 3, Phase 4, and the proposal) |

## 2. Authority hierarchy (established independently)

1. Project Charter + Architecture Charter + Master Plan (incl. "AI may not
   silently mutate recipes"; recipe changes create new versions).
2. `docs/RECIPE_DOMAIN.md`, ADR-0003/0004/0008/0010/0011,
   `UNITS_AND_ROUNDING`, `CALCULATION_ENGINE`, Phase 2 API schemas, `TESTING`,
   security baseline/architecture.
3. Phase 4 (incl. Slice 2 remediation) specifications and acceptance evidence.
4. The 5A-1 implementation and its tests — behavior evidence only.
5. The proposed specification — lowest authority; it may not override 1–3.

## 3. Independent structural validation (own derivation, own checker)

Derived: 57 FR / 11 AC / 13 ADV — counts accurate. All declarations unique and
contiguous from 1; zero dangling references; zero orphans after range/shorthand
expansion; every AC carries a test/gate oracle; every ADV states an expected
result; vocabulary (§4) covers all normative nouns; no relative links to break;
no positive authorization of excluded scope.

## 4. Retroactive-specification test

Classification of material rules: inherited (immutability, ownership,
canonical units, Decimal authority, snapshots, triggers, audit); explicitly
authorized 5A behavior (sequence-uniqueness guard — the only new server rule,
with test); ordinary implementation freedom (UI helper decomposition, CSS);
current behavior fenced as contract (client-only drafts, no idempotency keys,
unknown-field defaults — each explicitly marked current-contract plus a future
gate in FR-037/§32 rather than architectural principle). No accepted safeguard
is narrowed to match code; no test is cited as the source of architecture;
nothing unauthorized is retroactively authorized.
RETROACTIVE_POLICY_RISK=LOW (residual: future readers mistaking fenced
documentation for principle; mitigated by §32 deferrals).

## 5. Critical-policy determinations

- A. Client-only drafts — PASS. No accepted document defines or requires
  persisted drafts (no Draft entity exists); drafts are not authoritative
  records until publication, so PostgreSQL authority, auditability, and
  recovery are unaffected. Refresh/logout/loss/abandonment/second-device
  answers are deterministic (client state lost; server unaffected); concurrent
  editing is impossible by construction (no shared mutable state); publication
  failure is atomic. No ADR required (no new server policy created).
- B. Publication/immutability — PASS. Code-verified: single-transaction
  version+lines+steps+snapshot+audit writes; clone inserts next versions;
  trigger backstop intact; brew-session snapshots consume, never mutate.
- C. Idempotency/concurrency — PASS (compatible). Accepted operation contracts
  are phase-scoped (Phase 3/4); no platform rule mandates keys for recipe
  create/clone. Duplicate-submit yields distinct valid versions (no
  corruption); recovery via list/reconcile; FR-037 gates future mutating
  commands. No ADR required.
- D. Unknown fields — PASS (compatible). Closed-schema rules are Phase-4
  scoped (P4-FR-077); security architecture mandates auth/authorization/audit,
  not schema closure; Pydantic binds declared fields only (no mass
  assignment). Deferral to a future spec is explicit (ADV-013).
- E. BOIL timing / 4dp — PASS. Server behavior unchanged and exactly stated;
  UI scoping explicit; no UI-only server invariant.
- F. Editing rules — PASS. Deterministic identity/ordering/validation;
  server persists submitted steps verbatim (verified — no synthesis).
- G. Calculation authority — PASS. Engine untouched; IBU golden vs shared
  authority; Decimal/snapshot/version rules preserved.
- H. Authorization/security — PASS. Owner scope, 404 nondisclosure, CSRF,
  server-side checks, audit on publication.
- I. Compatibility — PASS. No model/migration change; 1A–4 suites hold.
- J. Phase boundary — PASS. §23 exclusions explicit; no 5B authorized.

## 6. Acceptance-contract review

All material behaviors carry command/actor/authorization/schema/validation/
transaction/mutation/audit/error/retry/concurrency/recovery/test coverage
except the explicitness gaps in P5ASPEC-001. Required adversarial coverage is
present except: malformed numerics on the API (unit-tested at UI level and by
schema default, but no named API scenario), DB-interruption recovery
(structurally guaranteed, no named scenario), and explicit two-tab/stale
wording (behavior fully determined). None permits an incompatible
implementation choice.

## 7. Findings

- P5ASPEC-001 (P3): §29/§30 lack explicit ADV↔traceability cross-references;
  ADVs 004–008 and 010–012 are covered only implicitly via their FR rows, and
  no named required tests exist for cross-user IDs (005), fractional timing
  (007), empty lists (008), malformed API numerics, or DB-interruption
  recovery. Required remediation: name each ADV in its §30 row and add
  "required test" markers where no existing test pins the scenario.
  Acceptance: updated §29/§30 plus the named tests green. Nonblocking:
  underlying FRs are traced and behaviors verified compatible.
- P5ASPEC-002 (P3): §15 does not state two-tab and stale-catalog determinism
  explicitly (independent creates; publish-time revalidation). Required
  remediation: two sentences plus a double-tab scenario. Nonblocking: outcomes
  already fully determined by create-only semantics.
- No P0/P1/P2. No advisories beyond the spec's own carried-forward items.

## 8. Compatibility, boundary, decidability

Phase 1A–4 compatibility PASS; Slice 2 remediation preserved; no forward
leakage. Implementation and test contracts are decidable; the spec gates
future 5A work (FR-037, §31–32).

## 9. Verdict

PASS: no P0/P1, no P2; structure sound (57/11/13 verified); contracts
decidable with deterministic oracles; no safeguard weakened; draft/idempotency/
unknown-field policies compatible (no ADR needed); compatibility and boundary
hold. The two P3s are explicitness debt, not acceptance blockers.

## Machine-readable result

WORK_PACKAGE=BICOS_PHASE_5A_SPECIFICATION_INDEPENDENT_REVIEW
PHASE_5A_SPECIFICATION_REVIEW=PASS
REPOSITORY_VALID=YES
BRANCH=phase5a/recipe-editing-completeness
HEAD=e5df95507f0f9b113aa50aa8d01501be2bdf59a7
REMOTE_HEAD=e5df95507f0f9b113aa50aa8d01501be2bdf59a7
TRACKED_WORKTREE_CLEAN=YES
ORIGINAL_UNTRACKED_ARTIFACTS_PRESERVED=YES
SPECIFICATION_PATH=docs/specifications/PHASE_5A_RECIPE_EDITING_COMPLETENESS_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md
SPECIFICATION_SHA256=06D8D669B54402F9CDDAF801E6907AD3F771B52E3D26269503A2546ED361FB09
SPECIFICATION_HASH_VERIFIED=YES
FUNCTIONAL_REQUIREMENTS=57
ACCEPTANCE_CRITERIA=11
ADVERSARIAL_SCENARIOS=13
IDENTIFIER_UNIQUENESS=PASS
REFERENCE_INTEGRITY=PASS
TRACEABILITY=PASS
CONFLICT_SCAN=PASS
RETROACTIVE_POLICY_RISK=LOW
CLIENT_ONLY_DRAFT_POLICY=PASS
PUBLICATION_IMMUTABILITY=PASS
IDEMPOTENCY_CONTRACT=PASS
UNKNOWN_FIELD_CONTRACT=PASS
CALCULATION_CONTRACT=PASS
AUTHORIZATION_CONTRACT=PASS
POSTGRESQL_AUTHORITY=PASS
TEST_CONTRACT_DECIDABLE=YES
IMPLEMENTATION_CONTRACT_DECIDABLE=YES
PHASE_1A_4_COMPATIBILITY=PASS
PHASE_4_SLICE_2_REMEDIATION_PRESERVED=YES
FORWARD_PHASE_LEAKAGE=NO
P0_FINDINGS=0
P1_FINDINGS=0
P2_FINDINGS=0
P3_FINDINGS=2
ADVISORY_FINDINGS=0
F_008=DEFERRED
F_009=DEFERRED
F_010=ADR_REQUIRED_NONBLOCKING
REVIEW_ARTIFACT_CREATED=YES
REVIEW_ARTIFACT_STAGED=NO
SPECIFICATION_STAGED=NO
FILES_MODIFIED=0
COMMIT_CREATED=NO
PUSH_PERFORMED=NO
MAIN_MERGED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
DEPLOYMENT_PERFORMED=NO
FURTHER_PHASE_5A_IMPLEMENTATION_AUTHORIZED=NO
