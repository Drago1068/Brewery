# Brewing Platform

Phase 2 accepted baseline for a private Brewing Knowledge & Execution Platform.

## Status

**Phase 2 Brewing Core accepted baseline**

**Phase 3 awaiting explicit authorization**

The platform now provides owned equipment profiles, a category-aware ingredient catalog, lot inventory derived from an append-only ledger, safety-stock warnings, a responsive Recipe Designer, immutable calculation snapshots, process-aware scaling, availability checks, and manual substitution metadata. The accepted Phase 1A Mash slice remains intact. Later roadmap phases are intentionally absent.

## Repository

```text
apps/web                 Next.js responsive browser application
apps/api                 FastAPI modular-monolith API
packages/calculations    Deterministic brewing calculations
packages/shared-types    Shared-contract boundary
database/migrations      Alembic migrations and integrity triggers
infrastructure/docker    Runtime images and backup/restore helpers
tests/e2e                Complete Playwright vertical slice
docs                     Architecture baseline and runbooks
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

## Scope gate

Phase 2 is closed as the accepted `v0.2.0-phase2` baseline. Work stops here: Phase 3 and NAS production deployment are not authorized, and no fermentation, packaging, serving, advanced analytics/AI, IoT, or production deployment capability is included.
