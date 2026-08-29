# Brewing Platform

Phase 3 Brew-Day OS implementation candidate on `codex/phase3-brew-day-os`. Phase 3 is not accepted and is not merged to `main`.

## Status

**Phase 2 Brewing Core remains the accepted `v0.2.0-phase2` baseline**

**Phase 3 Brew-Day OS implementation candidate — not yet independently reviewed or accepted**

The candidate adds persistent multi-stage brew-day execution through yeast-pitch handoff: plan materialization, stage lifecycle, PostgreSQL-authoritative timers/reminders/measurements/additions, CSRF, notes/photos, and journal projection. Phase 4 fermentation management and NAS production deployment are not authorized.

## Repository

```text
apps/web                 Next.js responsive browser application
apps/api                 FastAPI modular-monolith API
packages/calculations    Deterministic brewing calculations
packages/shared-types    Shared-contract boundary
database/migrations      Alembic migrations and integrity triggers
infrastructure/docker    Runtime images and backup/restore helpers
tests/e2e                Playwright Phase 1A, Phase 2, and Phase 3 slices
docs                     Architecture baseline, specifications, and evidence
```

## Quick start

Requirements: Docker Desktop with Compose, Git, and local ports `18100` and `18101` available.

1. Copy `.env.example` to `.env`.
2. Replace every `replace-with-...` value with a unique development secret. Do not commit `.env`.
3. Start the stack:

   ```powershell
   docker compose up -d --build
   ```

4. Open `http://127.0.0.1:18101` and sign in with the configured bootstrap credentials.
5. Stop the stack without deleting PostgreSQL data:

   ```powershell
   docker compose down
   ```

The API is host-local at `http://127.0.0.1:18100`; interactive API documentation is at `/api/docs`.

## Verification

```powershell
docker compose run --rm --no-deps -e DATABASE_URL=sqlite+pysqlite:///./.test-brewing.db api pytest -q
docker compose exec -e TEST_USE_POSTGRES=1 api pytest -q tests/test_postgres_integrity.py tests/test_phase2_postgres_integrity.py
docker build --target build -t brewing-platform-web-test -f infrastructure/docker/web.Dockerfile .
docker run --rm brewing-platform-web-test npm test
docker run --rm brewing-platform-web-test npm run lint
docker compose --profile test run --rm --build e2e
```

See [Local Development](docs/operations/LOCAL_DEVELOPMENT.md), [Database](docs/operations/DATABASE.md), [API](docs/API.md), [Testing](docs/TESTING.md), [Security](docs/security/SECURITY.md), and [Architecture Compliance](docs/ARCHITECTURE_COMPLIANCE.md).

The authoritative long-range product scope and phase boundaries are defined in the [Brewing Intelligence & Competition OS Master Plan](docs/product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md) and [Development Roadmap](docs/DEVELOPMENT_ROADMAP.md).

The next independent review gate is Codex review of the Phase 3 implementation candidate on `codex/phase3-brew-day-os`. Phase 3 acceptance is not granted by this README. Phase 4 implementation and production deployment remain unauthorized.

## Scope gate

Phase 2 remains the accepted `v0.2.0-phase2` baseline on `main`. Phase 3 implementation lives on `codex/phase3-brew-day-os` until independent review and acceptance. Work stops at yeast-pitch handoff: fermentation, packaging, serving, advanced analytics/AI, IoT, inventory reservation-to-consumption, and NAS production deployment are not included.
