# Phase 3 Next.js Runtime Compatibility Remediation

Status: bounded runtime/dependency remediation on `codex/phase3-brew-day-os`. This artifact
closes the independent review Playwright blocker caused by Next.js 16.3.0 standalone manifest
generation. It does **not** grant Phase 3 acceptance. Phase 4 and production remain unauthorized.

## Blocking review reference

| Field | Value |
|---|---|
| Review artifact | `docs/evidence/PHASE_3_FINAL_INDEPENDENT_IMPLEMENTATION_ACCEPTANCE_REVIEW.md` |
| Verdict | FAIL (Playwright E2E not independently reproducible) |
| Blocked candidate | `1218be8211bb084a6e067c17d1584db6d29534f1` |
| Blocker | `Invariant: The client reference manifest for route "/login" does not exist` |
| Runtime | Next.js 16.3.0 + App Router + `output: standalone` + Docker production web image |
| Non-browser gates | All independently passed (PostgreSQL 144/144, traceability 97/63/58, security, migration, backup, performance, scope) |

## Framework upgrade

| Field | Value |
|---|---|
| NEXT_VERSION_BEFORE | 16.3.0 |
| NEXT_VERSION_AFTER | 16.3.3 |
| LOCKFILE_CHANGED | YES (`apps/web/package-lock.json`) |
| OTHER_DEPENDENCIES_CHANGED | `eslint-config-next` 16.3.0 → 16.3.3 (matching framework peer) |
| Reason for 16.3.3 | Patched Active LTS release within accepted Next.js 16.3 family; resolves standalone client-reference-manifest generation without major downgrade |

No application behavior, specification, migration, or Phase 3 domain code was changed.

## Clean build procedure

```text
docker builder prune -f
docker compose -p bicos_phase3_remed down web
docker compose -p bicos_phase3_remed build --no-cache web
docker compose -p bicos_phase3_remed up -d --force-recreate web api
```

Evidence: `build-web-next1633.txt`

Stale `.next` output, prior web container, and Docker build cache layers were not reused.

## Production standalone validation

| Gate | Result | Evidence |
|---|---|---|
| NEXT_BUILD | PASS | `docker compose -p bicos_phase3_remed build --no-cache web` exit 0 |
| STANDALONE_SERVER_START | PASS | Web logs: `Next.js 16.3.3` / `Ready` — no crash |
| LOGIN_ROUTE | PASS | `GET http://127.0.0.1:18101/login` → HTTP 200 |
| `/` | PASS | HTTP 200 |
| `/designer` | PASS | HTTP 200 |
| CLIENT_REFERENCE_MANIFEST_ERROR | ABSENT | No `Invariant` / manifest errors in web logs after route probes |

## Docker standalone layout audit

Inside `bicos_phase3_remed-web-1`:

- `server.js` present (standalone entry)
- `.next/static/` present
- `public/` copied by Dockerfile runtime stage
- Client reference manifests present, including:
  - `.next/server/app/login/page_client-reference-manifest.js`
  - `.next/server/app/brew/[id]/page_client-reference-manifest.js`
  - `.next/server/app/designer/page_client-reference-manifest.js`

Dockerfile COPY operations (`standalone`, `.next/static`, `public`) match generated Next.js layout. No missing manifest due to packaging omission.

Classification: **NEXT_FRAMEWORK** (16.3.0 bug) — not BICOS application code or Docker COPY defect.

## Playwright re-run (production Docker runtime)

Command:

```text
docker compose -p bicos_phase3_remed --profile test run --rm e2e
```

| Metric | Value |
|---|---|
| PLAYWRIGHT_TESTS_TOTAL | 9 |
| PLAYWRIGHT_TESTS_PASSED | 8 |
| PLAYWRIGHT_TESTS_FAILED | 0 |
| PLAYWRIGHT_TESTS_SKIPPED | 1 |
| PLAYWRIGHT_REQUIRED_SKIPS | 0 |
| Exit code | 0 |

Skipped test: `browser performance sampler records navigation and recovery samples` (`PHASE3_PERF_BROWSER=1` opt-in). Separate acceptance via PostgreSQL `test_phase3_performance_acceptance_reference_class`.

### Required browser gates

| Gate | Result |
|---|---|
| FULL_STAGE_AWARE_UI | PASS (canonical Phase 3 brew-day flow PRE_BREW through BREW_COMPLETE) |
| CANONICAL_PHASE3_E2E | PASS |
| ACCESSIBILITY_REVIEW | PASS (phone/tablet viewport + keyboard focus tests) |
| PHASE_1A_BROWSER_REGRESSION | PASS (`phase1a.spec.ts`) |
| PHASE_2_BROWSER_REGRESSION | PASS (`phase2.spec.ts`) |

## Frontend quality regression

Executed in clean Docker Node 22.19.0-alpine container with `npm ci` on upgraded lockfile:

| Gate | Command | Result |
|---|---|---|
| FRONTEND_LINT | `npm run lint` | PASS |
| TYPECHECK | `npx tsc --noEmit` | PASS |
| FRONTEND_TESTS | `npm test -- --run` | 9 passed, 0 failed |
| FRONTEND_BUILD | `docker compose build --no-cache web` (`npm run build`) | PASS |

## Dependency security

| Gate | Command | Result |
|---|---|---|
| DEPENDENCY_SECURITY_REVIEW | `npm audit --package-lock-only --audit-level=high` | PASS (0 vulnerabilities) |
| NEXTJS_SECURITY_BASELINE | Next.js 16.3.3 Active LTS patch | PASS |

## Backend / scope preservation

| Check | Result |
|---|---|
| APPLICATION_BEHAVIOR_CHANGED | NO |
| MIGRATION_CHANGED | NO |
| SPECIFICATION_CHANGED | NO |
| PHASE_3_SCOPE_CONFORMANCE | PASS (no source/spec/migration edits) |
| PHASE_4_10_OPERATIONAL_LEAKAGE | NO |

PostgreSQL 144/144 and other independently proven non-browser gates were not invalidated; only
`apps/web/package.json` and `apps/web/package-lock.json` changed.

## Remaining limitations

- Opt-in browser performance sampler remains skipped in default `e2e` run.
- Independent Codex browser re-verification is still required; this document is implementation-team evidence only.

## Authorization

```text
PHASE_3_ACCEPTANCE=NOT_YET_GRANTED
PHASE_4_IMPLEMENTATION=NOT_AUTHORIZED
PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED
READY_FOR_CODEX_FINAL_BROWSER_REVERIFICATION=YES
```
