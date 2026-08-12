# Phase 1A Independent Architecture Acceptance

## Decision

`PASS`

## Scope

Acceptance covers Phase 1 Platform Foundation and the Phase 1A architecture-proving vertical slice only. It closes the validated recipe-to-completed-Mash implementation as a reproducible baseline. It does not authorize or include Phase 2.

## Architecture

- ADR-0001: PASS. The backend remains one modular monolith with explicit identity, recipes, brew sessions, measurements, notifications, and audit domain modules.
- ADR-0002: PASS. Platform services, brewing domain models, application use cases, presentation/API/UI, and implementation infrastructure remain separated.
- ADR-0003: PASS. Corrections append new measurements and audit/journal events; PostgreSQL triggers reject silent mutation of completed observations and recipe versions already used by a session.
- ADR-0004: PASS. Authoritative tolerance and variance decisions remain deterministic functions under `packages/calculations` and are unit tested.
- ADR-0005: PASS. Inventory is not implemented and no mutable quantity-only model contradicts the future ledger requirement.
- ADR-0006: PASS. Mash timer state is PostgreSQL-backed and the browser E2E test proves continuity through refresh.
- ADR-0007: PASS. No digital-menu or other public endpoint was introduced. Development web/API ports bind only to loopback.

Domain rules are coordinated by backend application services rather than UI components. Redis has no authoritative persistence responsibility. Recipes and recipe versions are separate tables and models. Planned session targets, actual measurements, tolerances, variances, and deviations remain distinct. Physical measurements carry explicit units. Authoritative timestamps use UTC-aware database types and `utc_now()`. No AI mutation capability exists.

## Implementation Evidence

The baseline includes a responsive Next.js application, FastAPI modular monolith, PostgreSQL/Alembic schema, Redis supporting boundary, opaque authenticated sessions, ownership authorization, structured logging, audit records, versioned recipes, brew sessions, Mash workflow, persisted timer, pH and gravity reminders, validated measurements, deterministic comparisons, deviations, automatic journal entries, append-only corrections, planned-versus-actual display, Docker Compose, CI workflow, and backup/restore helpers.

## Test Evidence

Validation was rerun on 2026-08-11 against the exact source tree prepared for the baseline.

### Backend and PostgreSQL

```powershell
docker compose exec api ruff check . /workspace/database/migrations
docker compose run --rm --no-deps -e DATABASE_URL=sqlite+pysqlite:///./.test-brewing.db api pytest -q
docker compose exec -e TEST_USE_POSTGRES=1 api pytest -q tests/test_postgres_integrity.py
```

Results: Ruff PASS. Lightweight domain/API/authentication/calculation/brew-day suite PASS with 11 passed and 2 PostgreSQL-only tests skipped by design. The separately executed PostgreSQL integrity suite PASS with 2 passed, so no PostgreSQL-only acceptance check remained unexecuted. The test client emitted one non-blocking dependency deprecation warning concerning future `httpx2` migration.

### Frontend, type check, and production build

```powershell
docker build --no-cache --target build -t brewing-platform-web-closure -f infrastructure/docker/web.Dockerfile .
docker run --rm brewing-platform-web-closure npm test
docker run --rm brewing-platform-web-closure npm run lint
docker run --rm brewing-platform-web-closure npm run build
```

Results: Vitest PASS, 3 passed. ESLint PASS. Next.js production compilation PASS, including TypeScript. Routes `/`, `/login`, and `/brew/[id]` built successfully.

### Browser E2E

```powershell
docker compose --profile test build --no-cache e2e
docker compose --profile test run --rm e2e
```

Result: Playwright PASS, 1 passed. The test created a recipe, started a brew session and Mash, observed persisted reminders/timer, refreshed the active page and verified elapsed time continuity, recorded pH and gravity, completed Mash, and reviewed planned-versus-actual and journal evidence.

### Dependency audits

```powershell
docker run --rm brewing-platform-web-closure npm audit
docker run --rm brewing-platform-e2e npm audit
```

Results: PASS, zero known vulnerabilities in both locked npm dependency sets.

## Runtime Evidence

```powershell
docker compose config --quiet
docker compose up -d --build db redis api web
docker compose ps
```

PostgreSQL, Redis, FastAPI, and Next.js reported `healthy`. `/health/live`, `/health/ready`, and `/login` returned HTTP 200. A cookie-backed login and authenticated `/api/v1/auth/me` request both returned HTTP 200 and the expected configured test identity. PostgreSQL and Redis had no published host ports; API `18100` and web `18101` were bound to `127.0.0.1`. The disposable stack and named test-data volume were removed after validation.

## Backup Evidence

- Backup path: `B:\brewing-platform-backups\brewing-20260811-221207.dump`
- Location boundary: external to `B:\brewing-platform` and therefore outside the Git repository.
- Catalog validation: PASS; PostgreSQL custom-format archive, 87 catalog entries, gzip compression.
- Isolated restore validation: PASS. The dump restored with `--no-owner --no-acl --exit-on-error` into a standalone PostgreSQL 17.6 container with no published ports and no shared development volume.
- Restored migration state: `0001_phase1a`.
- Restored schema: all nine required core tables were present: recipes, recipe_versions, brew_sessions, brew_stages, brew_timers, measurements, deviations, brew_journal_events, and audit_events.
- Integrity: both `recipe_version_immutable` and `measurement_completed_immutable` triggers and 34 primary/foreign/unique/check constraints were present.
- Representative records: 2 recipes, 2 recipe versions, 2 brew sessions, 4 measurements, 18 journal events, and 18 audit events.
- Read-only relational smoke query: PASS.
- Cleanup: the disposable restore container was destroyed after validation.

## Security Evidence

The pre-commit review found no real `.env`, credentials, API keys, auth tokens, private-key markers, or database dump inside the repository. `.env.example` contains placeholders only. The external backup directory is not under the repository. `.gitignore` excludes environment files, dependency/generated directories, test artifacts, logs, and backup artifacts. The partial generated `apps/web/node_modules` directory from an interrupted local install was moved intact outside the repository to `B:\brewing-platform-local-artifacts\apps-web-node_modules-20260811`; it is not part of the baseline. Authentication and ownership authorization remain server-enforced. Production credentials were not required. No production NAS deployment or public exposure occurred.

## Known Limitations

- NAS deployment, TLS/private access, secure-cookie mode, encrypted off-device backup, and production restore drills remain deployment gates.
- Bootstrap environment changes do not rotate an existing user's password.
- Explicit anti-CSRF tokens should be reviewed before any broader deployment surface.
- Timer pause/resume behavior and actual Mash-temperature capture remain deferred.
- OpenAPI-generated frontend types, durable CI browser artifacts, and the `httpx2` test-client migration remain technical debt.
- The authored GitHub Actions workflow has not run because no Git remote is configured.

## Phase Boundary

`PHASE_2_NOT_INCLUDED`

`NAS_PRODUCTION_DEPLOYMENT_NOT_AUTHORIZED`

## Baseline

- Branch: `main`
- Accepted implementation commit: `PENDING_BASELINE_COMMIT`
- Evidence-complete commit: `PENDING_EVIDENCE_COMMIT`
- Tag: `v0.1.0-phase1a` (to be created after the evidence-complete commit)
