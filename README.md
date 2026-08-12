# Brewing Platform

Phase 1/1A architecture-review candidate for a private Brewing Knowledge & Execution Platform.

## Status

**Phase 1 + Phase 1A baseline accepted**

**Phase 2 awaiting explicit authorization**

The implemented slice creates a versioned recipe, starts a brew session and Mash stage, persists an authoritative timer and reminders, captures pH and gravity, records deviations, completes Mash, and displays planned-versus-actual evidence with an automatic journal. Later roadmap phases are intentionally absent.

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
docker compose exec -e TEST_USE_POSTGRES=1 api pytest -q tests/test_postgres_integrity.py
docker build --target build -t brewing-platform-web-test -f infrastructure/docker/web.Dockerfile .
docker run --rm brewing-platform-web-test npm test
docker run --rm brewing-platform-web-test npm run lint
docker compose --profile test run --rm --build e2e
```

See [Local Development](docs/operations/LOCAL_DEVELOPMENT.md), [Database](docs/operations/DATABASE.md), [API](docs/API.md), [Testing](docs/TESTING.md), [Security](docs/security/SECURITY.md), and [Architecture Compliance](docs/ARCHITECTURE_COMPLIANCE.md).

## Scope gate

Phase 2 is not authorized. The accepted baseline is closed and tagged for reproducible future work; no later-phase capability is included.
