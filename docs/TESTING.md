# Testing

## Backend

The fast suite uses SQLite to exercise deterministic calculations, validation, authentication, API use cases, state transitions, timer recovery, deviations, journal events, and append-only corrections.

```powershell
docker compose run --rm --no-deps -e DATABASE_URL=sqlite+pysqlite:///./.test-brewing.db api pytest -q
```

PostgreSQL integration tests verify migration head and both database-level immutability triggers:

```powershell
docker compose exec -e TEST_USE_POSTGRES=1 api pytest -q tests/test_postgres_integrity.py tests/test_phase2_postgres_integrity.py
```

## Frontend

```powershell
docker build --target build -t brewing-platform-web-test -f infrastructure/docker/web.Dockerfile .
docker run --rm brewing-platform-web-test npm test
docker run --rm brewing-platform-web-test npm run lint
```

The production Docker build runs the Next.js TypeScript compilation.

## Browser E2E

```powershell
docker compose --profile test run --rm --build e2e
```

The Playwright suite proves the accepted Phase 1A Mash slice, the Phase 2 designer/inventory path, and the Phase 3 voice-confirmation boundary. Failures retain traces and screenshots inside the ephemeral test container.

Phase 3 API/domain coverage lives in `apps/api/tests/test_phase3_*.py` and includes materialization, CSRF, reminder acknowledgement, timers, additions, waivers, media, idempotency, recovery, and a local p95 dashboard projection check.
