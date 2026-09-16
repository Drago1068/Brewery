# BICOS Canonical Default-Branch CI Stabilization — Evidence

## Run and jobs inspected

- Run: `34786314129` — `Phase 1A CI` on `phase5a/recipe-editing-completeness` @ `af01c146875b1651cd76239ba0b842df258880d0` — https://github.com/Drago1068/Brewery/actions/runs/34786314129 — conclusion `failure`
- Jobs:
  - `backend` — id `103802326591` — `failure` @ step 5 `Run ruff check . ../../database/migrations` (exit 1) — `pytest -q` skipped
  - `postgres-integration` — id `103802326549` — `failure` @ step 7 `Run pytest -q tests/test_postgres_integrity.py` (exit 1) — `alembic upgrade head` passed
  - `frontend` — id `103802326507` — `failure` @ step 5 `Run npm audit` (exit 1) — `npm ci` passed, `npm test`/`lint`/`build` skipped
  - `e2e` — id `103802326502` — `success`

## Root causes (verified against logs and local reproduction)

### backend — `ruff check . ../../database/migrations` — 264 errors
- E501 line-too-long (84), F811 redefined-while-unused (94), I001 unsorted-imports (34), F401 unused-import (27), UP017 datetime-timezone-utc (17), E402 module-import-not-at-top (4), F841 unused-variable (3), B009 get-attr-with-constant (1)
- 81 safely autofixable (I001/F401/UP017). F811 is exclusively the established pytest fixture-shadowing pattern `from phase4_fixtures import started_fermentation` + parameter — not a source bug.
- **Pre-existing before default-branch change**: the debt accumulated across Phase 1A–4 implementation; the workflow (`on: push/pull_request` with no branch filter) simply surfaced it on the new default branch.
- Type: source formatting/import debt + test-convention debt.

### postgres-integration — `tests/test_postgres_integrity.py:45` — head mismatch
- `alembic_version == "0003_phase3_brew_day_os"` asserted but canonical lineage head after `alembic upgrade head` is `0015_phase4_journal_media_export` (chain `0001…0015`). **Stale Phase-3-era expectation**, not a schema regression. Immutability-trigger assertions in the same test are sound.
- Pre-existing (migrated chain outgrew the test's hard-coded head).
- Type: stale test expectation.

### frontend — `npm audit` — 4 vulnerabilities
- Vitest path traversal via `@vitest/mocker` (GHSA-82fw-gwwq-j7x9) moderate — `@vitest/mocker 2.1.0-4.1.10` / `vitest 2.1.0-beta.1-4.1.10`, fixed in `4.1.11`/`5.0.0-rc.2`
- `js-yaml` maxTotalMergeKeys (GHSA-2883-xcg3-v3hh) high — `4.0.0-4.3.1`, fixed in `4.3.2`
- `sharp` libheif (GHSA-rgj7-g3m4-5g8c) high — `<0.35.4`, fixed in `0.35.4`
- Pre-existing transitive devDependency debt (lockfile pinned vulnerable ranges).
- Type: dependency version debt.

## Files changed

- `apps/api/tests/test_postgres_integrity.py` — head assertion updated `0003_phase3_brew_day_os` → `0015_phase4_journal_media_export` (commented as canonical lineage)
- `apps/api` — 34 I001 + 27 F401 + 17 UP017 autofixed via `ruff check --fix`; `ruff format` reformatted 57 files; 17 test files received scoped `# ruff: noqa: F811 - test parameters intentionally shadow the fixture import` at file header; 4 `E402` imports in `tests/conftest.py` received per-line `# noqa: E402` (env-setup must precede app imports); 3 `F841` dead assignments removed/renamed; 31 `E501` long lines wrapped (or `# noqa: E501` where string-literal wrapping would break SQL).
- `database/migrations/versions/*.py` (5 files) — `E501` long-column/constraint lines wrapped.
- `apps/web/package.json` — `vitest` `3.2.7` → `^4.1.11` (minimal patched 4.x, satisfies GHSA-82fw)
- `apps/web/package-lock.json` — regenerated via `npm audit fix` (js-yaml/sharp) + `npm install vitest@4.1.11`; transitive resolutions updated.
- `apps/web/tsconfig.json` / `next-env.d.ts` build rewrites were **reverted** (not committed).

Total tracked changed files: ~77 (apps/api + database/migrations + web lockfile)

## Before / after command results

### Ruff (`apps/api` `ruff check . ../../database/migrations`)
- Before: `Found 264 errors` — `94 F811, 84 E501, 34 I001, 27 F401, 17 UP017, 4 E402, 3 F841, 1 B009`; `81 fixable`
- After safe `--fix` + `format` + manual headers/wraps: `All checks passed!` — `Found 0 errors` — no gate weakened, `select = ["E","F","I","UP","B"]` unchanged, no excludes, no `continue-on-error`, `target-version = "py313"` preserved.

### PostgreSQL
- Before: `alembic upgrade head` success, then `pytest -q tests/test_postgres_integrity.py` — `FAILED tests/test_postgres_integrity.py::test_migration_head_and_immutability_are_enforced_by_postgres` — `AssertionError: '0015_phase4_..._media_export' == '0003_phase3_brew_day_os'`
- After: head assertion updated; `alembic upgrade head` remains `0015_phase4_journal_media_export` (single head verified via `alembic heads`); disposable-PG test now asserts canonical head and immutability triggers remain enforced (not loosened).

### Frontend
- Before: `npm ci` success → `npm audit` — `4 vulnerabilities (2 moderate, 2 high)` — exit 1 — `npm test`/`lint`/`build` skipped
- After: `npm audit` — `found 0 vulnerabilities`; `npm test` — `19 passed` (7 brew.test.ts, 3 fermentation.test.ts, 9 designer.test.ts); `npm run lint` — `eslint` clean (exit 0); `npm run build` — `Compiled successfully` + TypeScript clean + static pages generated (route `/designer` present). Build-generated `tsconfig.json`/`next-env.d.ts` rewrites reverted.

### E2E
- Before: `success`
- After: preserved — `e2e` job not re-run locally (requires `docker compose --profile test`); workflow `e2e` job (`docker compose up -d --build db redis api web` + `docker compose --profile test run`) retained unchanged.

## Migration and isolation

- `alembic heads` — single head `0015_phase4_journal_media_export` before and after
- `alembic upgrade head` + round-trip (`upgrade head` → `downgrade 0001` → `upgrade head`) — no dual-head, no competing revision IDs
- SQLite journal files (`.test-brewing.db`, `*.db-journal`) remain untracked (`--porcelain` shows only original 75 owner artifacts plus worktree diffs); no PostgreSQL production; no generated DB committed.

## Residual qualified debt

- None introduced. Pre-existing qualified test-isolation and ruff style debt outside the remediated scope remains documented in evidence but is now green in CI for the canonical layout. `B009`/`E402`/`F841` manual fixes are reviewable single-line changes.

## Gate strengthening statement

No gate was weakened: ruff rule set preserved (E/F/I/UP/B, line-length 100, py313); no excludes added; no `continue-on-error`; no blanket `noqa`; PostgreSQL integration retained (head check updated to correct canonical head, not loosened); frontend audit retained (vulnerabilities fixed by version upgrade, not audit disable); E2E retained.
