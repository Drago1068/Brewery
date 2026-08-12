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

The Playwright suite proves both the accepted Phase 1A Mash slice and the Phase 2 path from equipment/catalog/inventory through calculation, availability, scaling, immutable cloning, and original-version verification. Failures retain traces and screenshots inside the ephemeral test container.
