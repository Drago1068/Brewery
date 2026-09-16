# CI Follow-up: Environment-Independent Backend Evidence Checks

> **SHA-256 (this file):** `11267fdac8195f607f1fe9f5db8832f068a742991a1bc6ed562649df95b84b34`

## Summary

The commit `dc97128` stabilized the Ruff default-branch gate but left two `pytest -q`
evidence tests failing in GitHub Actions (`gh run view 35123977247` backend job
`104888371243`). This follow-up fixes both failures, making the backend test suite
environment-independent in any fresh CI checkout.

## Root Causes

| Test | Symptom | Root cause |
|------|---------|------------|
| `test_ac_001_phase3_diff_scope_excludes_forward_domains` | `fatal: bad revision 'v0.3.0-phase3'` | `git diff` referenced the unpublished annotated tag `v0.3.0-phase3` in a shallow checkout where the annotated object does not exist. |
| `test_ac_032_git_excludes_secret_and_artifact_patterns` | `['apps/api/.test-brewing.db']` | The `rglob("*")` scan flagged the untracked sqlite file that the same `pytest -q` run (via the `clean_database` fixture) creates inside `apps/api/`. |

## Changes

### `.github/workflows/ci.yml`

Added a targeted fetch step after `actions/checkout@v4` in the `backend` job:

```yaml
- name: Fetch Phase 3 baseline for evidence comparisons
  run: |
    git fetch --no-tags origin 39c440f234149e67be6dfae948b33393857a153e
    git cat-file -e 39c440f234149e67be6dfae948b33393857a153e^{commit}
```

This fetches only the reachable baseline commit object—**not** the unrelated
`legacy-main` history—and fails with a clear message when the object is
unavailable.

### `apps/api/tests/phase3_migration_regression.py`

Replaced `PHASE3_BASELINE_TAG = "v0.3.0-phase3"` with:

```python
PHASE3_BASELINE_COMMIT = "39c440f234149e67be6dfae948b33393857a153e"
```

`assert_phase3_migrations_unchanged` now:
1. Calls `git cat-file -e` before comparing.
2. Raises a clear `AssertionError` (not `subprocess.CalledProcessError`) when
   the baseline commit is unavailable, with a message pointing to the workflow.
3. Diffs against the commit SHA directly—no tag lookup.

### `apps/api/tests/test_phase3_evidence_closure.py`

**Replaced** the `test_ac_032` `rglob("*")` implementation with:
- `_tracked_paths()` → parses `git ls-files -z` into NUL-delimited entries (safe
  with spaces and path separators).
- `_prohibited_tracked_paths()` → flags tracked paths whose names or normalized
  paths match forbidden suffixes (`.dump`, `.pem`, `.key`, `.sqlite`, `.db`,
  `.db-journal`, `.journal`, `.log`, `.jsonl`, `.trace`), forbidden exact names
  (`.env`, `.test-brewing.db`, `.test-brewing-p3rr.db`), or forbidden path
  fragments (`/.idea/`, `/.next/`, `/.vscode/`, `/__pycache__/`, `/coverage/`,
  `/dist/`, `/node_modules/`, `/target/`, `/traces/`).

**Added four focused tests:**
- `test_tracked_scan_ignores_untracked_test_residue` — verifies untracked
  `.test-brewing.db`, `.db-journal`, and `.env` are invisible to the scan.
- `test_tracked_prohibited_artifact_detected` — parametrized over 16 prohibited
  path names; confirms each is reported when tracked.
- `test_tracked_scan_handles_spaces_and_platform_separators` — spaces in paths
  parsed correctly; Windows `\` separators normalized before matching.
- `test_tracked_scan_normal_repository_is_clean` — the live tracked tree
  contains no prohibited paths.

### `apps/api/tests/conftest.py`

Added a session-scoped autouse fixture `_remove_sqlite_test_residue` that, after
the test session in sqlite mode, disposes the engine and unlinks
`.test-brewing.db` plus its journal/SHM/WAL companions. This bounds the sqlite
file lifecycle to the run and eliminates the residue that previously tripped
the old `rglob` scan.

## Verification

| Gate | Result |
|------|--------|
| `ruff check apps/api/../../database/migrations` | ✅ All checks passed |
| `pytest tests/test_phase3_evidence_closure.py` | ✅ 41 passed (full module incl. `test_ac_001`, `test_ac_032`, 4 focused tests) |
| `pytest tests/test_phase3_evidence_closure.py -k focused` | ✅ 4 passed, no sqlite residue after run |
| `assert_phase3_migrations_unchanged` guard path | ✅ Clear `AssertionError` when baseline unavailable |
| `ci.yml` YAML syntax | ✅ Parses cleanly |
| Full backend `pytest -q` | Local run times out on this machine; CI run is the authoritative gate |

## Risks

- The targeted `git fetch` depends on the GitHub Actions `uploadpack.allowReachableSHA1InWant`
  setting (enabled by default). If the setting were disabled, the fetch would
  fail with a clear HTTP error and the job would fail at the fetch step—visible
  and debuggable.
- The `_remove_sqlite_test_residue` teardown is a session-scoped fixture and
  runs in both postgres and sqlite modes, but its body is guarded by
  `TEST_USE_POSTGRES != "1"` and is inert in postgres mode.
- The four focused tests create disposable throwaway git repositories in `tmp_path`;
  no state leaks between tests or into the host repo.

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Commit SHA over tag | The annotated tag is local-only and was never published; a commit SHA is immutable and verifiable with `git cat-file`. |
| Targeted fetch over `fetch-depth: 0` | Avoids pulling the unrelated `legacy-main` history per explicit scope constraint. |
| Tracked-file scan over `rglob` | Derives candidates from Git's index; untracked runtime residue generated by the suite can never fail the check. |
| Session-scoped teardown in conftest | Ensures the sqlite file is released and deleted after the suite finishes, without redesigning per-test fixtures. |

---

*Generated for CI branch `ci/canonical-default-stabilization`, parent `dc9712857efadf2297e2e39e5807b67ed378aa67`.*
