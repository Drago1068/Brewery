# Phase 3 Final Acceptance Evidence Closure

Status: evidence-closure candidate on `codex/phase3-brew-day-os`. This artifact closes
remaining FR/AC/ADV traceability gaps with executable one-to-one proofs. It does **not**
grant Phase 3 acceptance. Phase 4 and production remain unauthorized.

## Identity

| Field | Value |
|---|---|
| Starting candidate | `594a73606123ae152ce94d98fbe27d4b425feebe` |
| Branch | `codex/phase3-brew-day-os` |
| Closure candidate | git commit containing this file (`git rev-parse HEAD`) |
| Specification | `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` |
| Specification SHA-256 | `6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF` |
| Specification changed | NO |
| Compose project | `bicos_phase3_remed` |
| Immutable FAIL re-review | `docs/evidence/PHASE_3_INDEPENDENT_IMPLEMENTATION_RE_REVIEW.md` (unchanged) |

## Initial evidence gaps (at `594a736…`)

| Metric | Before | After |
|---|---|---|
| FR tested | 86 / 97 | 97 / 97 |
| AC passed | 40 / 63 | 63 / 63 |
| ADV validated | 46 / 58 | 58 / 58 |
| NOT_PROVEN | 46 rows | 0 |

### Previously missing FR IDs (11)

`P3-FR-030`, `P3-FR-033`, `P3-FR-045`, `P3-FR-054`, `P3-FR-057`, `P3-FR-058`,
`P3-FR-064`, `P3-FR-065`, `P3-FR-079`, `P3-FR-082`, `P3-FR-095`

### Previously unproven AC IDs (23)

`P3-AC-001`, `P3-AC-002`, `P3-AC-003`, `P3-AC-012`, `P3-AC-015`, `P3-AC-024`,
`P3-AC-030`, `P3-AC-031`, `P3-AC-032`, `P3-AC-033`, `P3-AC-050`, `P3-AC-051`,
`P3-AC-052`, `P3-AC-054`, `P3-AC-063`, `P3-AC-065`, `P3-AC-068`, `P3-AC-069`,
`P3-AC-075`, `P3-AC-079`, `P3-AC-082`, `P3-AC-085`, `P3-AC-088`

### Previously unvalidated ADV IDs (12)

`P3-ADV-010`, `P3-ADV-011`, `P3-ADV-019`, `P3-ADV-030`, `P3-ADV-031`, `P3-ADV-032`,
`P3-ADV-036`, `P3-ADV-039`, `P3-ADV-047`, `P3-ADV-048`, `P3-ADV-054`, `P3-ADV-055`

## Tests added

New file: `apps/api/tests/test_phase3_evidence_closure.py` (22 named executables).

| Test | Closes |
|---|---|
| `test_ac_001_phase3_diff_scope_excludes_forward_domains` | AC-001 |
| `test_ac_002_045_065_no_ai_or_always_listening` | AC-002, FR-045, FR-065, AC-065 |
| `test_ac_003_leakage_scan_maps_phase3_tables_and_routes` | AC-003 |
| `test_ac_032_git_excludes_secret_and_artifact_patterns` | AC-032 |
| `test_ac_033_051_dependency_and_compose_validation` | AC-033, AC-051 |
| `test_ac_050_toolchain_markers_present` | AC-050 |
| `test_ac_054_disposable_env_scripts_do_not_target_nas_production` | AC-054 |
| `test_fr_030_033_ac_015_065_adv_030_all_process_point_types` | FR-030, FR-033, AC-015, AC-065, ADV-030 |
| `test_fr_095_ac_082_late_evidence_time_boundaries` | FR-095, AC-082, ADV-039 |
| `test_fr_054_ac_068_soft_remove_attachment_is_audited` | FR-054, AC-068 |
| `test_fr_057_058_export_json_and_human_formats` | FR-057, FR-058 |
| `test_fr_064_voice_confirmed_entry_method_persisted` | FR-064 |
| `test_fr_079_ac_024_069_recovery_matrix_session_survives_redis_flush` | FR-079, AC-024, AC-069 |
| `test_fr_082_security_audit_covers_waiver_correction_media_removal` | FR-082 |
| `test_ac_012_075_pause_abort_child_effects` | AC-012, AC-075 |
| `test_ac_030_idor_identifier_classes` | AC-030 |
| `test_ac_031_adv_019_032_media_security_matrix` | AC-031, ADV-019, ADV-032 |
| `test_ac_052_079_adv_036_legacy_and_phase2_compat` | AC-052, AC-079, ADV-036 |
| `test_ac_063_adv_031_operation_fingerprint_and_tombstone` | AC-063, ADV-031 |
| `test_ac_085_088_adv_054_055_repeat_policy_matrix_executable` | AC-085, AC-088, ADV-054, ADV-055 |
| `test_adv_010_011_timer_deadline_and_no_partial_on_conflict` | ADV-010, ADV-011 |
| `test_adv_047_048_addition_correction_lineage` | ADV-047, ADV-048 |

Supporting changes required by process-gate scanners:

- `scripts/generate_phase3_traceability.py` — map every former NOT_PROVEN row to the named
  evidence-closure tests; fail generation unless 97/63/58 PASS with 0 NOT_PROVEN.
- `docs/evidence/PHASE_3_TRACEABILITY.md` — regenerated.
- `infrastructure/docker/api.Dockerfile` — copy `docker-compose.yml`, `apps/web/package.json`,
  and `tests/e2e/` into the API image so in-container scanners can see compose/toolchain/e2e markers.
- `.dockerignore` — exclude local SQLite test DBs from image context.
- `apps/api/tests/test_phase3_adversarial.py` — import-order fix only (ruff I001).

No Phase 3 product behavior was added beyond executable acceptance oracles and scanner support.

## Final one-to-one traceability

Command:

```text
python scripts/generate_phase3_traceability.py
```

Result (deterministic; regenerated twice with identical output):

```text
fr=97 ac=63 adv=58 fr_pass=97 fr_np=0 ac_pass=63 ac_np=0 adv_pass=58 adv_np=0
NOT_PROVEN=(none)
```

Every referenced TEST_FILE/TEST_NAME exists, executes in the PostgreSQL suite and/or
Playwright profile, and asserts the mapped behavior.

## PostgreSQL evidence

### Intermediate run — SUPERSEDED_ENVIRONMENTAL_RUN

| Field | Value |
|---|---|
| Classification | `SUPERSEDED_ENVIRONMENTAL_RUN` |
| Background task | 791164 |
| Evidence file | `pytest-pg-evidence-final2.txt` / terminal 791164 |
| Result | 5 FAILED, 12 ERROR, exit 1 |
| Root cause | Fixture/bootstrap instability after the stack was recreated mid-run (API unavailable; bootstrap user missing after truncate). Not a product defect in the evidence-closure tests. |

This run is preserved and is **not** labeled PASS.

### Final rebuilt reproducible run

| Field | Value |
|---|---|
| Classification | FINAL_REPRODUCIBLE_PASS |
| Preconditions | `docker compose -p bicos_phase3_remed up -d --build db redis api web`; services healthy before pytest |
| Command | `docker compose -p bicos_phase3_remed exec -e TEST_USE_POSTGRES=1 -T api pytest -q --tb=line` |
| Evidence file | `pytest-pg-evidence-final4.txt` (also prior clean `pytest-pg-evidence-final3.txt`) |
| Collect-only | `144 tests collected` |
| POSTGRESQL_TESTS_TOTAL | 144 |
| POSTGRESQL_TESTS_PASSED | 144 |
| POSTGRESQL_TESTS_FAILED | 0 |
| POSTGRESQL_TESTS_SKIPPED | 0 |
| Exit code | 0 |

## Playwright evidence

### Intermediate attempt — SUPERSEDED_ENVIRONMENTAL_RUN

| Field | Value |
|---|---|
| Classification | `SUPERSEDED_ENVIRONMENTAL_RUN` |
| Evidence | `playwright-evidence-closure.txt`, `playwright-evidence-final.txt` |
| Result | 8 failed, 1 skipped |
| Root cause | Stale web image and/or post-pytest bootstrap-user absence (login never reached dashboard heading). |

### Final rebuilt / recovered run

| Field | Value |
|---|---|
| Preconditions | Fresh `--build` of api/web where needed; API restart after pytest to restore bootstrap user; stack left stable (no mid-suite recreate) |
| Command | `docker compose -p bicos_phase3_remed --profile test run --rm e2e` |
| Evidence file | `playwright-evidence-final2.txt` (also `playwright-evidence-closure2.txt`) |
| PLAYWRIGHT_TESTS_TOTAL | 9 |
| PLAYWRIGHT_TESTS_PASSED | 8 |
| PLAYWRIGHT_TESTS_FAILED | 0 |
| PLAYWRIGHT_TESTS_SKIPPED | 1 |
| Exit code | 0 |

### Skipped-test disposition

| Field | Value |
|---|---|
| PLAYWRIGHT_SKIPPED_TEST | `browser performance sampler records navigation and recovery samples` (`tests/e2e/phase3-performance.spec.ts`) |
| SKIP_REASON | `test.skip(process.env.PHASE3_PERF_BROWSER !== "1")` — opt-in two-tab normative browser sampler |
| REQUIRED_FOR_ACCEPTANCE | NO |
| SEPARATE_ACCEPTANCE_EVIDENCE | PostgreSQL `test_phase3_performance_acceptance_reference_class` (n=100) plus optional `PHASE3_PERF_BROWSER=1` sampler evidence |
| PLAYWRIGHT_REQUIRED_SKIPS | 0 |

## Quality toolchain (final)

| Gate | Command | Result |
|---|---|---|
| Ruff | `docker compose -p bicos_phase3_remed exec -T api ruff check brewing_api tests` | PASS, exit 0 |
| Frontend lint | `cd apps/web; npm run lint` | PASS, exit 0 |
| Typecheck | `cd apps/web; npx tsc --noEmit` | PASS, exit 0 |
| Frontend build | `cd apps/web; npm run build` | PASS, exit 0 |
| Vitest | `cd apps/web; npm test -- --run` | 9 passed, 0 failed, exit 0 |

## Preserved prior green gates

Evidence-closure work did not reopen these gates. PostgreSQL + Playwright final runs re-executed the covering suites:

| Gate | Status | Evidence |
|---|---|---|
| DATABASE_INVARIANTS | PASS | `test_phase3_invariants.py` in PG suite |
| CROSS_SESSION_INTEGRITY | PASS | invariant suite |
| CORRECTION_LINEAGE | PASS | ADV + `test_adv_047_048_addition_correction_lineage` |
| ADDITION_EVENT_IMMUTABILITY | PASS | invariant suite |
| MIGRATION_VALIDATION | PASS | `test_phase3_migration.py` |
| FULL_STAGE_AWARE_UI | PASS | canonical Playwright |
| CANONICAL_PHASE3_E2E | PASS | `canonical Phase 3 brew-day flow PRE_BREW through BREW_COMPLETE` |
| MEDIA_PERSISTENCE | PASS | engines + security + backup tests |
| MEDIA_BACKUP_RESTORE | PASS | `test_pg_dump_restore_preserves_attachment_metadata_and_media_bytes` |
| BACKUP_RESTORE_VALIDATION | PASS | same |
| REFRESH_RECOVERY | PASS | Playwright pause/refresh + ADV recovery |
| API_RESTART_RECOVERY | PASS | prior remediation evidence; API restart used for E2E recovery |
| REDIS_LOSS_RECOVERY | PASS | prior remediation + `test_fr_079_ac_024_069_recovery_matrix_session_survives_redis_flush` |
| RECOVERY_VALIDATION | PASS | combined |
| SECURITY_REVIEW | PASS | `test_phase3_security.py` + evidence-closure IDOR/media matrix |
| ACCESSIBILITY_REVIEW | PASS | phone/tablet/keyboard Playwright |
| PERFORMANCE_ACCEPTANCE | PASS | isolated n=100 harness; browser sampler opt-in |
| PHASE_1A_REGRESSION | PASS | `phase1a.spec.ts` |
| PHASE_2_REGRESSION | PASS | `phase2.spec.ts` |
| PHASE_3_SCOPE_CONFORMANCE | PASS | AC-001/003 scanners |
| PHASE_4_10_OPERATIONAL_LEAKAGE | NO | AC-001/003 scanners |

## Remaining limitations

- Opt-in browser performance sampler is not part of the default `e2e` command; performance acceptance is proven by the PostgreSQL reference-class harness.
- Historical environmental failure runs are retained as SUPERSEDED and must not be cited as PASS.
- Independent Codex acceptance is not granted by this closure.

## Authorization

```text
PHASE_3_ACCEPTANCE=NOT_YET_GRANTED
PHASE_4_IMPLEMENTATION=NOT_AUTHORIZED
PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED
READY_FOR_CODEX_FINAL_INDEPENDENT_IMPLEMENTATION_RE_REVIEW=YES
```
