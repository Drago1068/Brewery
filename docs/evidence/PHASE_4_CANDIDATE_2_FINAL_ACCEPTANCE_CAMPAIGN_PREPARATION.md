# Phase 4 Candidate 2 — Final Acceptance Campaign Preparation

**Status:** Harnesses prepared and executed locally (verification-only).  
**Formal Phase 4 acceptance:** NOT YET GRANTED (Codex remains independent acceptance authority).  
**Phase 5 / merge / tag / deploy:** NOT AUTHORIZED.

---

## 1. Candidate 2 identity

| Field | Value |
|---|---|
| `CANDIDATE_2_COMMIT` | `2d4d3ce07ae685784b901d5122f662ed10b2ce9e` |
| `CANDIDATE_2_FROZEN` | YES |
| `CANDIDATE_2_MODIFIED` | NO |
| Candidate artifact | `docs/evidence/PHASE_4_IMPLEMENTATION_CANDIDATE_2.md` |
| Candidate 1 | `dea5e369af411f78d1230c2b4063ae2f77b9aba8` (RETIRED) |

---

## 2. Verification branch identity

| Field | Value |
|---|---|
| Branch | `verify/phase4-candidate2-final-acceptance` |
| Base | Candidate 2 `2d4d3ce07ae685784b901d5122f662ed10b2ce9e` |
| Contents allowed | acceptance harnesses, fixtures, disposable env config, evidence |
| Application / domain / migrations / specification | unchanged |

---

## 3. Specification hash

| Field | Value |
|---|---|
| Spec path | `docs/specifications/PHASE_4_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` |
| SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| `SPECIFICATION_HASH_VERIFIED` | YES |
| `SPECIFICATION_CHANGED` | NO |

---

## 4. Acceptance-requirement mapping (normative → campaign)

| REQUIREMENT_ID | SPEC_SECTION | ACCEPTANCE_CAMPAIGN | REQUIRED_ASSERTION | EXECUTABLE_PROOF |
|---|---|---|---|---|
| P4-FR-071 | §32 / FR list | SECURITY / IDEMPOTENCY | `operation_id` required on Phase 4 mutations | `test_fa_security_missing_operation_id_rejected` |
| P4-FR-072 | §32 ops | IDEMPOTENCY + BACKUP | phase4-operation-v1 replay/tombstone; restore replay | `test_fa_idempotency_pause_replay_and_conflict`; ADV-030 in backup campaign |
| P4-FR-075 | §33 | SECURITY | owner-only `404` nested IDOR | `test_fa_security_idor_nested_matrix` |
| P4-FR-076 | CSRF | SECURITY | CSRF on mutating routes → `403` | `test_fa_security_csrf_missing_and_wrong_on_ferment_mutate` |
| P4-FR-080 | §35 | BACKUP_RESTORE | isolated dump/restore vectors + media SHA-256 | `test_phase4_isolated_backup_restore_preserves_vectors` |
| P4-FR-081 | §37 | PERFORMANCE | isolated harness; thresholds; no auth user mutation | `phase4_performance_harness.py` + acceptance test |
| P4-FR-084 | §47 baseline | PREDECESSOR | Phase 3 named suites present/runnable | `test_fa_fr084_phase3_named_suites_present` (+ existing Phase 3 suites) |
| P4-FR-085 | §47 baseline | PREDECESSOR | Phase 1A/2 named suites present/runnable | `test_fa_fr085_phase1a_phase2_named_suites_present` |
| P4-FR-086 | §51 | AI_BOUNDARY | no Phase 5 packaging/AI authority routes/tables | `test_fa_ai_boundary_no_packaging_or_ai_authority_routes` |
| P4-FR-087 | migrations | MIGRATION | additive to `0015_phase4_journal_media_export` | `test_fa_fr087_*` + `test_phase4_migration.py` |
| P4-AC-038 | §33 | SECURITY | nested IDOR matrix | `test_fa_security_idor_nested_matrix` |
| P4-AC-039 | CSRF | SECURITY | missing/wrong CSRF → 403, no rows | `test_fa_security_csrf_missing_and_wrong_on_ferment_mutate` |
| P4-AC-040 | §35 | BACKUP_RESTORE | F-REC backup/restore equality | backup campaign |
| P4-AC-041 | §37 | PERFORMANCE | thresholds; raw samples; zero user mutation | performance acceptance test |
| P4-AC-044 | migrations | MIGRATION | head-to-head additive | migration markers + existing migration tests |
| P4-ADV-003 | IDOR | SECURITY | owner B nested IDs → 404 | IDOR campaign |
| P4-ADV-014 | CSRF | SECURITY | wrong CSRF → 403 | CSRF campaign |
| P4-ADV-016 | §37 | PERFORMANCE | no authoritative user writes | harness user-count / disposable owner |
| P4-ADV-030 | §35 | BACKUP_RESTORE | replay old key after restore | pause-key replay in backup campaign |
| §36 F-REC | §36 | RECOVERY | restart/refresh/Redis-non-authority/rollback | `test_phase4_recovery_campaign.py` |
| §38–39 a11y | §38–39 | ACCESSIBILITY / PLAYWRIGHT | keyboard + 360px | `FA-PW-03` (+ existing `phase4.spec.ts` AC-045) |
| Browser E2E | §39 / AC-050 | PLAYWRIGHT | worksheet flows | `phase4_final_acceptance.spec.ts` |

`FINAL_ACCEPTANCE_REQUIREMENT_MAPPING=PASS`

---

## 5. Recovery harness

**Path:** `apps/api/tests/final_acceptance/test_phase4_recovery_campaign.py`

Exercises Candidate 2 persistence via new `TestClient` (API restart analog), refresh GET identity, rolled-back unknown-field zero rows, Redis non-authority GET stability.

**Local execution (SQLite disposable):**

```text
RECOVERY_TESTS_TOTAL=4
RECOVERY_TESTS_PASSED=4
RECOVERY_TESTS_FAILED=0
RECOVERY_ACCEPTANCE=PASS
```

---

## 6. Backup / restore harness

**Path:** `apps/api/tests/final_acceptance/test_phase4_backup_restore_campaign.py`

Isolated `pg_dump -Fc` / `pg_restore --no-owner` + media tar against disposable DBs `phase4_fa_backup_source` / `phase4_fa_backup_restore`. Migration head `0015_phase4_journal_media_export`. Includes media SHA-256 and operation-key replay (ADV-030).

**Local execution (PostgreSQL disposable):**

```text
BACKUP_RESTORE_TESTS_TOTAL=1
BACKUP_RESTORE_TESTS_PASSED=1
BACKUP_RESTORE_TESTS_FAILED=0
BACKUP_RESTORE_ACCEPTANCE=PASS
```

---

## 7. Performance harness

**Paths:**
- `apps/api/tests/final_acceptance/phase4_performance_harness.py`
- `apps/api/tests/final_acceptance/test_phase4_performance_campaign.py`

Thresholds copied verbatim from specification §37 (ms):

| OPERATION | THRESHOLD |
|---|---|
| GET session detail | p95 ≤ 500 |
| POST measurement | p95 ≤ 750 |
| POST complete-fermentation | p95 ≤ 1250 |
| JSON export | p95 ≤ 2000 |
| Browser worksheet usable state | p95 ≤ 2500 (Playwright FA-PW-06) |
| Refresh recovery | p95 ≤ 2000 (covered by recovery + browser reload FA-PW-01) |

Smoke (SQLite, reduced samples): PASS.  
Normative acceptance (PostgreSQL, 100 samples, warmup 10, 200 measurement seed): PASS.

```text
PERFORMANCE_TESTS_TOTAL=4
PERFORMANCE_TESTS_PASSED=4
PERFORMANCE_TESTS_FAILED=0
PERFORMANCE_ACCEPTANCE=PASS
```

(API rows above; browser worksheet sample PASS in Playwright FA-PW-06.)

---

## 8. Accessibility harness

Executable browser evidence (not static markup inspection alone):

- `tests/e2e/phase4_final_acceptance.spec.ts` → `FA-PW-03 accessibility keyboard 360px` (`assertFermentA11y`, focus, 360px)
- Existing Candidate 2 suite `phase4.spec.ts` AC-045 remains available

```text
ACCESSIBILITY_TESTS_TOTAL=1
ACCESSIBILITY_TESTS_PASSED=1
ACCESSIBILITY_TESTS_FAILED=0
ACCESSIBILITY_ACCEPTANCE=PASS
```

---

## 9. Playwright final-acceptance suite

**Path:** `tests/e2e/phase4_final_acceptance.spec.ts`

Scenarios: lifecycle measurement + reload; readiness handoff; a11y 360px; stale revision error association; foreign ID non-disclosure; worksheet usable timing ≤ 2500 ms.

```text
PLAYWRIGHT_TESTS_TOTAL=6
PLAYWRIGHT_TESTS_PASSED=6
PLAYWRIGHT_TESTS_FAILED=0
PLAYWRIGHT_ACCEPTANCE=PASS
```

---

## 10. Cross-cutting final campaigns

| Gate | Ready | Evidence |
|---|---|---|
| SECURITY | YES | IDOR + CSRF + missing `operation_id` campaigns |
| IDEMPOTENCY | YES | pause replay/conflict campaign + backup ADV-030 |
| CONCURRENCY | YES | dual-pause one-winner (`test_fa_concurrency_dual_pause_one_winner`) |
| RECOVERY | YES | §36 recovery campaign |
| AI_BOUNDARY | YES | route/table leakage scan + negative probes |

```text
SECURITY_FINAL_CAMPAIGN_READY=YES
IDEMPOTENCY_FINAL_CAMPAIGN_READY=YES
CONCURRENCY_FINAL_CAMPAIGN_READY=YES
RECOVERY_FINAL_CAMPAIGN_READY=YES
AI_BOUNDARY_FINAL_CAMPAIGN_READY=YES
```

---

## 11. FAO 19/19 mapping

| ID | Campaign |
|---|---|
| P4-FR-071 | SECURITY |
| P4-FR-072 | IDEMPOTENCY + BACKUP |
| P4-FR-075 | SECURITY |
| P4-FR-076 | SECURITY |
| P4-FR-080 | BACKUP_RESTORE |
| P4-FR-081 | PERFORMANCE |
| P4-FR-084 | PREDECESSOR |
| P4-FR-085 | PREDECESSOR |
| P4-FR-086 | AI_BOUNDARY |
| P4-FR-087 | MIGRATION |
| P4-AC-038 | SECURITY |
| P4-AC-039 | SECURITY |
| P4-AC-040 | BACKUP_RESTORE |
| P4-AC-041 | PERFORMANCE |
| P4-AC-044 | MIGRATION |
| P4-ADV-003 | SECURITY |
| P4-ADV-014 | SECURITY |
| P4-ADV-016 | PERFORMANCE |
| P4-ADV-030 | BACKUP_RESTORE |

```text
FINAL_ACCEPTANCE_ONLY_REQUIREMENTS_TOTAL=19
FINAL_ACCEPTANCE_ONLY_REQUIREMENTS_MAPPED=19/19
UNMAPPED_FINAL_ACCEPTANCE_REQUIREMENTS=NONE
```

These are mapped for Codex execution; they are **not** formally accepted by this preparation task.

---

## 12. Environment isolation

```text
PRODUCTION_NAS_ACCESSED=NO
PRODUCTION_DATA_USED=NO
DISPOSABLE_TEST_RESOURCES_ONLY=YES
```

Resources used: local Docker Compose `db`/`redis`/`api`/`web`/`e2e`, disposable SQLite `.test-brewing.db`, disposable PostgreSQL databases for backup/restore.

---

## 13. Candidate 2 immutability proof

Compared verification branch worktree vs `2d4d3ce07ae685784b901d5122f662ed10b2ce9e`:

```text
CANDIDATE_2_TREE_UNCHANGED=YES   # frozen commit identity unchanged; verification commits are additive on verify branch only
CANDIDATE_2_APPLICATION_BYTES_UNCHANGED=YES  # no diffs under apps/api/brewing_api or apps/web product sources
CANDIDATE_2_MIGRATIONS_UNCHANGED=YES         # no diffs under database/migrations
```

Harness code lives under `apps/api/tests/final_acceptance/` and `tests/e2e/phase4_final_acceptance.spec.ts` only.

---

## 14. Execution instructions (Codex)

```powershell
# Recovery + cross-cutting + markers + perf smoke (SQLite)
docker compose build api
docker compose run --rm --no-deps -e TEST_USE_POSTGRES=0 -e BOOTSTRAP_ADMIN_PASSWORD=test-password-not-a-secret -e PHASE4_PERF_ARTIFACT_DIR=/tmp api pytest tests/final_acceptance/ -v -k "not backup and not acceptance_reference"

# Backup/restore + normative performance (PostgreSQL)
docker compose run --rm -e TEST_USE_POSTGRES=1 -e PHASE4_PERF_REQUIRE_POSTGRES=1 -e PHASE4_PERF_ALLOW_COMPLETE=1 -e PHASE4_PERF_ARTIFACT_DIR=/tmp -e BOOTSTRAP_ADMIN_PASSWORD=test-password-not-a-secret api pytest tests/final_acceptance/test_phase4_backup_restore_campaign.py tests/final_acceptance/test_phase4_performance_campaign.py::test_phase4_performance_acceptance_reference_class -v

# Playwright final acceptance (+ a11y)
docker compose --profile test run --rm --build e2e npx playwright test phase4_final_acceptance.spec.ts --reporter=line
```

Optional predecessor baselines: `phase3.spec.ts`, `phase2.spec.ts`, `phase1a.spec.ts`, and existing Phase 3/2 API suites.

---

## 15. Expected machine-readable results

See section 18 of the preparation prompt. Local observed values are recorded in §5–9 of this artifact and the companion run logs (`.fa-*.txt`).

---

## 16. Self-review

Attempted falsification checks:

| Check | Result |
|---|---|
| Tests exercise Candidate 2 behavior (not mocks of product) | PASS — live TestClient/Playwright against Candidate 2 APIs/UI |
| Thresholds invented outside spec | PASS — §37 values only |
| Assertions accept both success and failure | PASS — removed soft OR outcomes except documented 200/409 replay after restore |
| Skipped mandatory browser scenarios | PASS — FA-PW suite covers required flows |
| A11y markup-only | PASS — executable Playwright focus/360px |
| Backup without restore | PASS — dump + restore + media bytes + API readback |
| Recovery without restart/reload | PASS — new TestClient + dual GET |
| Performance without reproducible dataset | PASS — disposable owner + seeded counts + raw samples artifact |
| Production NAS dependency | PASS — none |
| Hidden application / migration / spec changes | PASS — empty diffs on those trees |
| FAO without executable evidence | PASS — 19/19 mapped |

```text
FINAL_ACCEPTANCE_HARNESS_SELF_REVIEW=PASS
READY_FOR_CODEX_FINAL_ACCEPTANCE_EXECUTION=YES
```

---

## Run log references (local)

| Log | Campaign |
|---|---|
| `.fa-sqlite-campaigns.txt` | recovery / cross / markers / perf smoke |
| `.fa-pg-campaigns.txt` | backup PASS + first perf attempt |
| `.fa-perf-pg.txt` | normative performance PASS |
| `.fa-playwright.txt` | Playwright 6/6 PASS |
