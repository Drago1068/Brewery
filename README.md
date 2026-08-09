# Brewing Intelligence & Competition OS

Homebrewer-first brewing application. Epic 1 — Brewery + Recipe Foundation.

## Principles

- PostgreSQL is the authoritative operational database
- NAS-mounted persistent storage; containers are replaceable
- Recipe versions support immutability once locked / referenced
- Inventory movements use a transaction ledger
- Brewing calculations are deterministic (never AI-authoritative)

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Vite |
| Backend | FastAPI + SQLAlchemy (async) |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Runtime | Docker Compose (NAS-ready bind mounts) |

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |
| Liveness | http://localhost:8000/health |
| Readiness | http://localhost:8000/health/ready |

## NAS persistence

Configure host paths in `.env`:

```text
BREWINGOS_POSTGRES_DATA=./data/postgres   # or /volume1/BrewingOS/database/postgres
BREWINGOS_STORAGE=./data/storage
BREWINGOS_BACKUPS=./data/backups
BREWINGOS_LOGS=./data/logs
```

Documentation drives are not runtime dependencies.

## Tests

```bash
cd backend && pip install -r requirements.txt && pytest
cd frontend && npm install && npm test
```

## Epic 1 scope

Brewery setup, equipment, ingredient library, inventory ledger, recipes + versions,
deterministic predictions, ready-to-brew checks. Brew Day execution starts in Epic 2.

## License

Private — personal use.
