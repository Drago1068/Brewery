# Phase 4 Slice 2 — Review Remediation Evidence

## Identity

| Field | Value |
|---|---|
| Branch | `phase4/slice2-review-remediation` |
| Base HEAD | `9dea54ce421d94accad400815c95cfdbecc43379` |
| Slice 2 baseline | `17bf72aab801169507657ae4e0b54d637a5a830d` |
| Slice 2 implementation | `e2e9049d34295c32db3e310aaf76c6892335a64e` |
| Slice 2 closure | `b53119e868bcfc5be7214bcc5f4e8f0a4d467b26` |
| Governance | `HOLD_PENDING_REMEDIATION_AND_DATABASE_EVIDENCE` |

## Finding dispositions

| ID | Disposition | Change |
|---|---|---|
| F-001 | CLOSED (verified already closed by `385abaf`; gap test added) | `apps/api/tests/test_phase4_slice2_remediation.py::test_f001_unknown_field_on_correction_rejected_without_mutation` proves 422 UNKNOWN_FIELD + zero mutation on the corrections endpoint. All 22 closed schemas structurally guarded by `test_phase4_closed_command_schemas.py`. |
| F-002 | CLOSED | `_parse_decimal_field` in `presentation/routes/fermentation_sessions.py` rejects malformed/non-finite numerics with 422 INVALID_NUMERIC_VALUE on record + correct measurement paths (value, sample_temperature_c). |
| F-003 | CLOSED, no ADR required | Spec §18 is unambiguous: measurement windows are governed by **stage** status (explicit PAUSED-stage window). The session-level `SESSION_PAUSED` deny made that window unreachable and is removed; stage validation is the single authority. Positive + negative tests added. |
| F-004 | CLOSED | Corrections require explicit UTC offset for client-supplied `observed_at` (422 TIMESTAMP_NOT_UTC). Omitted `observed_at` inherits the validated persisted leaf with UTC coercion (SQLite round-trips aware instants as naive; PostgreSQL is unaffected). |
| F-005 | NOT_REQUIRED (removal) + equivalence goldens | The shared `specific_gravity_to_plato` raises below SG 1.000, so the adapter domain (SG 0.900–1.300) cannot delegate unconditionally without changing observable results. Golden test proves coefficient identity where both are defined; source note added. |
| F-006 | CLOSED (bounded scope) | All 5 remediation-owned files pass `ruff check`; 17 pre-existing findings in those files fixed. Repo-wide gate debt (264 errors elsewhere) untouched per scope. |
| F-007 | NOT_APPLICABLE | No authoritative typecheck exists: CI (`.github/workflows/ci.yml`) runs only `ruff check` + `pytest`; no mypy config in repo. No ad-hoc gate established. |
| F-008 | DEFERRED | Composite FK on corrections table needs a migration; app-level scoping verified sufficient for Slice 2. |
| F-009 | DEFERRED | `evaluated_at` ordering tie-break is cosmetic; no normative invariant requires it. |
| F-010 | ADR_REQUIRED (deferred) | No method taxonomy invented; temperature-sensitive methods remain unspecified in the contract. |

## Test evidence (remediation branch)

- New: `apps/api/tests/test_phase4_slice2_remediation.py` — 7 passed (SQLite), 7 passed (PostgreSQL).
- Slice 2 SQLite: domain/entry/api/security/matrix/pitch-rate/closed-schemas — all pass.
- Slice 2 PostgreSQL (disposable `postgres:17.6-alpine`, CI credentials, port 5433):
  `test_phase4_slice2_closure` + `test_phase4_migration` 16 passed;
  full Slice 2 set incl. remediation 60 passed; closure re-run after
  downgrade/upgrade round-trip 6 passed.
- Migration: fresh `alembic upgrade head` 0001→0015 PASS; downgrade to
  `0005_phase4_measurements_derived_gravity` + `upgrade head` round-trip PASS;
  post-round-trip single head `0015`, measurement tables + all 5 Slice 2
  constraints verified present.
- Phase 4/5A affected (lifecycle, conditioning, waivers/readiness, calc
  read-model, timers/reminders, OG reconcile, yeast, actions/additions,
  deviations, journal/media, packaging close, plan/equipment, securities,
  Phase 5A recipe editing): all pass (PG-skipped items noted per-file).
- Phase 1A–3 SQLite: all pass except the single known hygiene artifact below.

## Regression qualifiers (prior non-Slice-2 failures, re-evaluated)

1. Alembic-head-0003 expectation: the `test_phase3_evidence_closure` variant is
   fixed by later history (passes); the identical assertion surviving in
   `test_postgres_integrity.py:45-48` is a **stale test expectation**
   (Phase-1A-era CI gate), pre-existing, untouched by (and unrelated to) this
   remediation. Fixing it would alter evidence policy — out of scope.
2. `apps/api/.test-brewing.db` hygiene artifact: **test-isolation defect** —
   the SQLite suite creates the file the meta-test then flags; pre-exists this
   remediation (file was in the original 74 untracked artifacts).
3. Phase 3 SQLite naive/aware failure (`brew_day.py:659`): no longer reproduces
   at this HEAD (fixed by later history); **pre-existing product defect**,
   outside Slice 2 scope, not affected by this remediation.

## Quality gates

- `ruff check` on 5 remediation-owned files: PASS. Repo-wide authoritative
  command still reports 264 pre-existing errors in untouched files (none in
  remediation files).
- Authoritative typecheck: NOT_APPLICABLE (none configured).
- Build: NOT_APPLICABLE (Python packages; no frontend changes).
