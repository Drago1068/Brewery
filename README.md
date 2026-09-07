# Brewing Platform

Accepted Phase 4 Fermentation and Conditioning OS on `main` at `v0.4.0-phase4`. Phase 3 Brew-Day OS is accepted at `v0.3.0-phase3`. Phase 5 and NAS production deployment are not authorized.

## Status

**Latest accepted implementation baseline: Phase 4 — `v0.4.0-phase4`**

**Phase 3 Brew-Day OS accepted — `v0.3.0-phase3`**

Formal acceptance records:

- Phase 3 implementation: [Phase 3 Formal Acceptance Record](docs/evidence/PHASE_3_ACCEPTANCE.md)
- Phase 4 specification: [Phase 4 Formal Specification Acceptance](docs/evidence/PHASE_4_FORMAL_SPECIFICATION_ACCEPTANCE.md)
- Phase 4 implementation: [Phase 4 Formal Implementation Acceptance](docs/evidence/PHASE_4_FORMAL_IMPLEMENTATION_ACCEPTANCE.md)

Phase 2 Brewing Core remains the immutable earlier baseline `v0.2.0-phase2`. Historical specification files keep their original in-document status wording because their exact bytes are bound by those acceptance records; later formal acceptance records establish accepted status. No additional Phase 3 specification freeze is required.

Phase 4 fermentation and conditioning is accepted and formally closed. Phase 5 quality, packaging, and later-phase work, and NAS production deployment, remain unauthorized.

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

The latest accepted implementation baseline is Phase 4. Phase 5 implementation and production deployment remain unauthorized. This README does not grant Phase 5, further implementation, or deployment authorization.

## Scope gate

The latest accepted implementation baseline on `main` is Phase 4 (`v0.4.0-phase4`). Phase 3 (`v0.3.0-phase3`) and Phase 2 (`v0.2.0-phase2`) remain accepted immutable predecessors. Phase 5, later-horizon operational domains, and NAS production deployment are not authorized.
