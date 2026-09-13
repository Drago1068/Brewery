# BICOS Canonical Branch Lineage

## 1. Repository identity and canonical origin

- Repository name: `Brewing Platform` (repository `Brewery`)
- Canonical origin: `https://github.com/Drago1068/Brewery.git`
- Authoritative checkout location: `B:\brewing-platform`
  (`//NazarioNAS.local/USB_3TB/brewing-platform`)

## 2. Date and authority for the default-branch decision

This document records the GitHub default branch selected to represent the
canonical BICOS implementation lineage. The selection is a repository-governance
decision and does **not** by itself authorize implementation, integration with
the legacy lineage, or deployment.

## 3. Canonical / default branch

`phase5a/recipe-editing-completeness`

## 4. Canonical head at the decision

`885df59895d70e4134f14565dccc829a8d7a6721`

The GitHub default-branch symbolic reference (`HEAD`) resolves to this branch,
and a fresh clone checks out this exact commit.

## 5. Legacy branch

`main`

## 6. Legacy head

`bec32cd2bed5897a6e2ea2899cfbf2e94b928d2a`

## 7. Different root commits and no merge base

The canonical and legacy histories are **unrelated**:

- Canonical root: `a2f83d247bc7b3e484983d58acc77fdad2408cec`
  ("chore: establish Phase 1A accepted architecture baseline")
- Legacy root: `3ccbe70fa78b13e1ff4e18e2010597f5b7d381ce`
  ("chore: initialize BrewingOS Epic 1 greenfield scaffold on NAS external storage")

`git merge-base` returns no common ancestor (exit 1). The repository is not
shallow; object inspection reveals only routine unreachable objects, no
corruption. The two histories genuinely share no ancestor.

## 8. Incompatible application structure and migration chains

The two lineages are different codebases, not divergent versions of one codebase:

| Aspect | Canonical (`phase5a/…`) | Legacy (`main`) |
|---|---|---|
| Layout | `apps/api`, `apps/web`, `database/`, `packages/`, `infrastructure/`, `tests/e2e/` | `backend`, `frontend`, `data/`, `docker-compose.dev.yml` |
| Python package | `brewing_api` (under `apps/api`) | `app` (under `backend`) |
| Migration path | `database/migrations/versions/` | `backend/alembic/versions/` |
| Migration head | `0015_phase4_journal_media_export` (chain `0001…0015`) | `009` (chain `001…009`) |
| Migration revision scheme | Phase-numbered (`0001_phase1a`, `0002_phase2_brewing_core`, …) | Epic-numbered (`001_initial_foundation`, …) |

Only five top-level file paths coincide across both trees (`.env.example`,
`.github/workflows/ci.yml`, `.gitignore`, `README.md`, `docker-compose.yml`); no
source, migration, or `docs/` path overlaps. Merging would produce a broken
dual migration forest and conflicting application packages.

## 9. Legacy `main` is preserved for provenance

Legacy `main` is retained as provenance of the Epic 1 / Epic 2A lineage. It must
**not** be merged into the canonical BICOS lineage, and it must **not** be
treated as the current BICOS implementation.

## 10. Explicitly prohibited operations

- `git merge --allow-unrelated-histories` between the two lineages;
- force-pushing either lineage;
- rebasing one root onto the other;
- deleting either branch without separate archival authority;
- treating legacy `main` as the current BICOS implementation.

## 11. Current Phase 5A specification and review baseline

- Specification: `docs/specifications/PHASE_5A_RECIPE_EDITING_COMPLETENESS_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`
  - SHA-256: `4851E4C1149A5B19BF19ED03CE08D21915E95A5DEA1C32DB6B2FF53DECD465E8`
  - Structure: 57 functional requirements, 11 acceptance criteria, 13
    adversarial scenarios.
- Evidence:
  - `docs/evidence/PHASE_5A_ENGINEERING_SPECIFICATION_INDEPENDENT_REVIEW.md`
  - `docs/evidence/PHASE_5A_ENGINEERING_SPECIFICATION_P3_REMEDIATION.md`
  - `docs/evidence/PHASE_5A_ENGINEERING_SPECIFICATION_FINAL_REVIEW.md`
- Baseline installed on the canonical branch at commit
  `885df59895d70e4134f14565dccc829a8d7a6721` and published to the remote.

## 12. Phase 4 Slice 2 remediation state

The Phase 4 Slice 2 remediation (commits `e962764…` and `e13eb74…`) and its
independent re-review (`PHASE_4_SLICE_2_REMEDIATION_INDEPENDENT_RE_REVIEW.md`)
are preserved on the canonical branch. Findings F-001 through F-004 are closed;
F-005 is not required (calculation authority retained); F-006 closed (scoped);
F-007 not applicable.

## 13. Deferred findings and ADR boundary

- Phase 4 F-008: DEFERRED
- Phase 4 F-009: DEFERRED
- Phase 4 F-010: ADR_REQUIRED_NONBLOCKING (temperature-sensitive method taxonomy)

## 14. Main integration is permanently inapplicable between these unrelated lineages

Because the canonical and legacy histories share no common ancestor and have
incompatible application structures and migration chains, normal Git
integration (merge/rebased fast-forward) is permanently inapplicable between
them. Integration would require a future, explicit **migration program** (for
example, importing selected canonical content into the legacy tree, or
retiring the legacy tree) that is authorized separately. No such program is
authorized by this document.

## 15. Branch protection and CI observations (this work package)

Read-only inspection findings at the time of this document:

- **No classic branch protection** exists on the default branch
  (`gh api …/branches/phase5a%2Frecipe-editing-completeness/protection` → HTTP
  404 "Branch not protected").
- **No classic branch protection** on legacy `main` (HTTP 404).
- **No repository rulesets** (`gh api …/rulesets` → empty array).
- Consequently there are **no required status checks**, no PR merge
  requirements, and no force-push / deletion / administrator-enforcement /
  signed-commit controls on either branch.
- CI workflow: `.github/workflows/ci.yml` ("Phase 1A CI") triggers on `push`
  and `pull_request` with **no branch filter**, so it runs on the default
  branch and has no `main`-specific conditions.
- Jobs and their emitted check names: `backend`, `postgres-integration`,
  `frontend`, `e2e`.
- On the canonical head `885df59`, the last run of these four checks produced:
  `e2e` success; `backend`, `postgres-integration`, and `frontend` failure.
  This is consistent with the pre-existing repository-wide Ruff debt (the
  `backend` job runs `ruff check . ../../database/migrations`, which reports
  ~264 pre-existing errors) and known qualified test-isolation debt. It is
  not caused by the default-branch change.

## 16. Recommended follow-up settings (recommendations, not completed actions)

These are recommendations only; none has been applied:

- Add classic branch protection or a repository ruleset to the default branch
  enforcing pull-request review and the four emitted checks
  (`backend`, `postgres-integration`, `frontend`, `e2e`) once those checks are
  green.
- Remediate or explicitly exclude the pre-existing Ruff debt so the `backend`
  CI check can pass.
- Consider keeping legacy `main` as read-only (protection without PR writes)
  to preserve provenance.
- Decide whether required checks should be "required before merging" or
  informational while the suite is being stabilized.

## 17. Future branch rename

A future rename of the default branch (for example, to a shorter canonical
name) remains a separate governance decision and is not authorized by this
document.